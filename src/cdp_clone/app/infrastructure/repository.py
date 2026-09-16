from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import Engine, func, select, update
from sqlalchemy.dialects import postgresql, sqlite

from src.cdp_clone.app.domain.events import UserEvent
from src.cdp_clone.app.domain.profiles import Profile, ProfileAttributes
from src.cdp_clone.app.infrastructure.tables import events, profiles

_INSERTS = {"postgresql": postgresql.insert, "sqlite": sqlite.insert}


class CdpRepository:
    def __init__(self, engine: Engine):
        if engine.dialect.name not in _INSERTS:
            raise ValueError(f"Unsupported database dialect: {engine.dialect.name}")
        self._engine = engine
        self._insert = _INSERTS[engine.dialect.name]

    def insert_events(self, new_events: list[UserEvent], received_at: datetime) -> list[bool]:
        """Insert atomically; returns True per event when created, False when (cdp_user_id, event_id) existed."""
        created: list[bool] = []
        with self._engine.begin() as conn:
            for event in new_events:
                stmt = (
                    self._insert(events)
                    .values(**asdict(event) | {"cancelled_at": None}, received_at=received_at)
                    .on_conflict_do_nothing(index_elements=["cdp_user_id", "event_id"])
                    .returning(events.c.id)
                )
                created.append(conn.execute(stmt).first() is not None)
        return created

    def list_events(
        self,
        cdp_user_id: str,
        *,
        event_name: str | None,
        since: datetime | None,
        until: datetime | None,
        include_cancelled: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[UserEvent], int]:
        conditions = [events.c.cdp_user_id == cdp_user_id]
        if not include_cancelled:
            conditions.append(events.c.cancelled_at.is_(None))
        if event_name:
            conditions.append(events.c.event_name == event_name)
        if since:
            conditions.append(events.c.timestamp >= since)
        if until:
            conditions.append(events.c.timestamp < until)
        with self._engine.connect() as conn:
            total = conn.execute(select(func.count()).select_from(events).where(*conditions)).scalar_one()
            rows = conn.execute(
                select(events)
                .where(*conditions)
                .order_by(events.c.timestamp.desc(), events.c.id.desc())
                .limit(limit)
                .offset(offset)
            ).mappings()
            return [_to_event(row) for row in rows], total

    def cancel_event(self, cdp_user_id: str, event_id: str, cancelled_at: datetime) -> UserEvent | None:
        """Mark an event cancelled; keeps the first cancelledAt when called again. None if it does not exist."""
        match = (events.c.cdp_user_id == cdp_user_id) & (events.c.event_id == event_id)
        with self._engine.begin() as conn:
            conn.execute(update(events).where(match, events.c.cancelled_at.is_(None)).values(cancelled_at=cancelled_at))
            row = conn.execute(select(events).where(match)).mappings().first()
        return _to_event(row) if row else None

    def get_profile(self, cdp_user_id: str) -> Profile | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(profiles).where(profiles.c.cdp_user_id == cdp_user_id)).mappings().first()
        return _to_profile(row) if row else None

    def upsert_profile(self, cdp_user_id: str, attributes: ProfileAttributes, updated_at: datetime) -> Profile:
        values = asdict(attributes)
        values["purchased_verticals"] = list(attributes.purchased_verticals)
        values["updated_at"] = updated_at
        stmt = self._insert(profiles).values(cdp_user_id=cdp_user_id, **values)
        stmt = stmt.on_conflict_do_update(index_elements=["cdp_user_id"], set_=values)
        with self._engine.begin() as conn:
            conn.execute(stmt)
        return Profile(cdp_user_id=cdp_user_id, attributes=attributes, updated_at=updated_at)


def _utc(value: datetime) -> datetime:
    # SQLite drops tzinfo; everything is written in UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _to_event(row) -> UserEvent:
    return UserEvent(
        event_id=row["event_id"],
        cdp_user_id=row["cdp_user_id"],
        event_name=row["event_name"],
        timestamp=_utc(row["timestamp"]),
        product_id=row["product_id"],
        taxonomy=row["taxonomy"],
        event_group_id=row["event_group_id"],
        quantity=row["quantity"],
        unit_price=row["unit_price"],
        using_date=row["using_date"],
        search_query=row["search_query"],
        cancelled_at=_utc(row["cancelled_at"]) if row["cancelled_at"] else None,
    )


def _to_profile(row) -> Profile:
    return Profile(
        cdp_user_id=row["cdp_user_id"],
        attributes=ProfileAttributes(
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
            gdpr_optin=row["gdpr_optin"],
        ),
        updated_at=_utc(row["updated_at"]),
    )
