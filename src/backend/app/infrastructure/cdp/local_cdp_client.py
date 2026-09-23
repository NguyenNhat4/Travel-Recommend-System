"""PostgreSQL implementation of CdpClient for the local week-1 CDP schema."""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

import psycopg
from psycopg.rows import dict_row

from src.backend.app.application.ports.cdp_client import (
    BrowseEvent,
    CdpProfile,
    CdpUnavailableError,
    PurchaseEvent,
    UserEvent,
)


class LocalCdpClient:
    """Access only ``cdp.*`` through the restricted ``cdp_writer`` role.

    The official local DDL intentionally has no external event-id, cancellation
    flag, or search-query column. Purchase retries are therefore deduplicated by
    their booking key, cancellation deletes the matching local event, and search
    query text remains owned by ``app.search_logs``.
    """

    def __init__(self, database_url: str):
        self._database_url = database_url

    async def record_purchases(self, events: Sequence[PurchaseEvent]) -> None:
        if not events:
            return
        try:
            async with await psycopg.AsyncConnection.connect(self._database_url) as conn:
                for event in events:
                    # Serialize retries for one user because the official DDL has
                    # no external event-id unique key.
                    await conn.execute(
                        "SELECT 1 FROM cdp.profiles WHERE cdp_user_id = %s FOR UPDATE",
                        (event.cdp_user_id,),
                    )
                    await conn.execute(
                        """
                        INSERT INTO cdp.events
                            (cdp_user_id, event_name, "timestamp", product_id, taxonomy,
                             event_group_id, quantity, unit_price, using_date)
                        SELECT %s, 'purchase', %s, %s::uuid, %s, %s, %s, %s, %s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM cdp.events
                            WHERE cdp_user_id = %s AND event_name = 'purchase'
                              AND event_group_id = %s AND product_id = %s::uuid AND using_date = %s
                        )
                        """,
                        (
                            event.cdp_user_id, event.timestamp, event.product_id, event.taxonomy,
                            event.event_group_id, event.quantity, event.unit_price, event.using_date,
                            event.cdp_user_id, event.event_group_id, event.product_id, event.using_date,
                        ),
                    )
        except (psycopg.Error, OSError) as exc:
            raise CdpUnavailableError(f"Local CDP purchase write failed: {type(exc).__name__}") from exc

    async def cancel_purchases(self, events: Sequence[PurchaseEvent]) -> None:
        if not events:
            return
        try:
            async with await psycopg.AsyncConnection.connect(self._database_url) as conn:
                for event in events:
                    await conn.execute(
                        """
                        DELETE FROM cdp.events
                        WHERE cdp_user_id = %s AND event_name = 'purchase'
                          AND event_group_id = %s AND product_id = %s::uuid AND using_date = %s
                        """,
                        (event.cdp_user_id, event.event_group_id, event.product_id, event.using_date),
                    )
        except (psycopg.Error, OSError) as exc:
            raise CdpUnavailableError(f"Local CDP cancellation failed: {type(exc).__name__}") from exc

    async def record_browse_events(self, events: Sequence[BrowseEvent], *, request_id: str | None = None) -> None:
        del request_id  # request correlation is logged by Backend; the local DDL has no request-id column.
        if not events:
            return
        rows = [
            (
                event.cdp_user_id, event.event_name, event.timestamp, event.product_id,
                event.taxonomy, event.quantity, event.unit_price, event.using_date,
            )
            for event in events
        ]
        try:
            async with await psycopg.AsyncConnection.connect(self._database_url) as conn:
                async with conn.cursor() as cursor:
                    await cursor.executemany(
                        """
                        INSERT INTO cdp.events
                            (cdp_user_id, event_name, "timestamp", product_id, taxonomy,
                             quantity, unit_price, using_date)
                        VALUES (%s, %s, %s, %s::uuid, %s, %s, %s, %s)
                        """,
                        rows,
                    )
        except (psycopg.Error, OSError) as exc:
            raise CdpUnavailableError(f"Local CDP browse write failed: {type(exc).__name__}") from exc

    async def list_events(
        self,
        cdp_user_id: str,
        *,
        since: datetime | None = None,
        event_name: str | None = None,
        max_events: int = 500,
    ) -> list[UserEvent]:
        if max_events <= 0:
            return []
        clauses = ["cdp_user_id = %s"]
        params: list[object] = [cdp_user_id]
        if since is not None:
            clauses.append('"timestamp" >= %s')
            params.append(since)
        if event_name is not None:
            clauses.append("event_name = %s")
            params.append(event_name)
        params.append(min(max_events, 500))
        query = f"""
            SELECT event_id::text AS event_id, cdp_user_id, event_name, "timestamp",
                   product_id::text AS product_id, taxonomy, event_group_id,
                   quantity, unit_price, using_date
            FROM cdp.events
            WHERE {' AND '.join(clauses)}
            ORDER BY "timestamp" DESC, event_id DESC
            LIMIT %s
        """
        try:
            async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
                cursor = await conn.execute(query, params)
                rows = await cursor.fetchall()
                return [_to_event(row) for row in rows]
        except (psycopg.Error, OSError) as exc:
            raise CdpUnavailableError(f"Local CDP history read failed: {type(exc).__name__}") from exc

    async def get_profile(self, cdp_user_id: str) -> CdpProfile | None:
        try:
            async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
                row = await (
                    await conn.execute(
                        """
                        SELECT cdp_user_id, lifecycle_stage, days_since_last_booking,
                               lifetime_order_count, vinclub_tier, purchased_verticals,
                               home_city, last_destination, email_optin, sms_optin,
                               push_optin, updated_at
                        FROM cdp.profiles WHERE cdp_user_id = %s
                        """,
                        (cdp_user_id,),
                    )
                ).fetchone()
        except (psycopg.Error, OSError) as exc:
            raise CdpUnavailableError(f"Local CDP profile read failed: {type(exc).__name__}") from exc
        return _to_profile(row) if row else None

    async def ensure_profile(self, cdp_user_id: str, *, home_city: str | None = None) -> None:
        """Tạo hồ sơ rỗng cho tài khoản mới đăng ký (auth §3.6.3 bước ③).

        ON CONFLICT DO NOTHING để idempotent: caller thử lại sau lỗi mạng không bị 409, và chạy
        lại seed không đè hồ sơ đã có. Mọi cột khác lấy DEFAULT của DDL — tài khoản mới có 0 event
        nên lifecycle_stage='new', purchased_verticals='{}', và /recommendations trả coldStart=true.

        cdp_writer có INSERT/UPDATE trên cdp.profiles nhưng KHÔNG có DELETE, nên hồ sơ tạo ở đây
        không rút lại được. Đó là lý do use case để hồ sơ mồ côi lại và chỉ ghi log khi bước ④ hỏng.
        """
        try:
            async with await psycopg.AsyncConnection.connect(self._database_url) as conn:
                await conn.execute(
                    """
                    INSERT INTO cdp.profiles (cdp_user_id, home_city)
                    VALUES (%s, %s)
                    ON CONFLICT (cdp_user_id) DO NOTHING
                    """,
                    (cdp_user_id, home_city),
                )
                await conn.commit()
        except (psycopg.Error, OSError) as exc:
            raise CdpUnavailableError(f"Local CDP profile create failed: {type(exc).__name__}") from exc


def _to_event(row: dict) -> UserEvent:
    return UserEvent(
        event_id=row["event_id"],
        cdp_user_id=row["cdp_user_id"],
        event_name=row["event_name"],
        timestamp=row["timestamp"],
        product_id=row["product_id"],
        taxonomy=row["taxonomy"],
        event_group_id=row["event_group_id"],
        quantity=row["quantity"],
        unit_price=float(row["unit_price"]) if row["unit_price"] is not None else None,
        using_date=row["using_date"],
        search_query=None,
    )


def _to_profile(row: dict) -> CdpProfile:
    return CdpProfile(
        cdp_user_id=row["cdp_user_id"],
        lifecycle_stage=row["lifecycle_stage"],
        days_since_last_booking=row["days_since_last_booking"],
        lifetime_order_count=row["lifetime_order_count"],
        vinclub_tier=row["vinclub_tier"],
        purchased_verticals=tuple(row["purchased_verticals"] or ()),
        home_city=row["home_city"],
        last_destination=row["last_destination"],
        email_optin=row["email_optin"],
        sms_optin=row["sms_optin"],
        push_optin=row["push_optin"],
        gdpr_optin=None,
        updated_at=row["updated_at"],
    )
