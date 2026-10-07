"""PostgreSQL cho giỏ hàng, đơn đặt chỗ, thanh toán và đọc catalog — qua DATABASE_URL (role vota_app).

Chỉ đọc `cdp.products` (vota_app được SELECT); không chạm `cdp.events`/`cdp.profiles`, mọi việc với CDP đi qua CdpClient.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import AsyncIterator, Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.backend.app.application.booking.errors import ValidationFailed
from src.backend.app.application.ports.booking_store import PendingBookingExists, ReferenceCodeTaken
from src.backend.app.domain.booking import (
    Booking, BookingDraft, BookingItem, BookingOverview, Cart, CartLine, FareLine, Payment, RoomAllocation, Traveler,
    TravelerType,
)
from src.backend.app.domain.booking.party import TravelerDocuments
from src.backend.app.domain.booking.status import BookingStatus, PaymentStatus
from src.backend.app.domain.catalog.models import Product


def _uuid_or_none(value: str) -> str | None:
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        return None


def _nights(start: date, end: date | None) -> int | None:
    return (end - start).days if end else None


class PostgresProductCatalog:
    def __init__(self, database_url: str):
        self._database_url = database_url

    async def get_products(self, product_ids: Sequence[str]) -> dict[str, Product]:
        ids = [i for i in (_uuid_or_none(p) for p in product_ids) if i]
        if not ids:
            return {}
        async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
            rows = await (await conn.execute(
                """
                SELECT product_id::text AS product_id, name, taxonomy, destination, description, attributes,
                       unit_price, currency, available, available_from, available_to, image_url
                  FROM cdp.products WHERE product_id = ANY(%s::uuid[])
                """, (ids,))).fetchall()
        return {
            r["product_id"]: Product(
                product_id=r["product_id"], name=r["name"], taxonomy=r["taxonomy"], destination=r["destination"],
                description=r["description"] or "", attributes=r["attributes"] or {},
                unit_price=float(r["unit_price"]) if r["unit_price"] is not None else None,
                currency=r["currency"].strip(), available=r["available"], available_from=r["available_from"],
                available_to=r["available_to"], image_url=r["image_url"])
            for r in rows
        }


def _line_of(r: dict) -> CartLine:
    """Một dòng `app.cart_items` hoặc `app.booking_draft_items` (cột mã mục đã đặt bí danh `cart_item_id`)."""
    return CartLine(
        cart_item_id=r["cart_item_id"], product_id=r["product_id"], quantity=r["quantity"],
        using_date=r["using_date"], nights=_nights(r["using_date"], r["using_date_to"]),
        unit_price_snapshot=int(r["unit_price_snapshot"]), added_at=r["added_at"], adults=r["adults"],
        children=r["children"],
        child_unit_price_snapshot=(int(r["child_unit_price_snapshot"])
                                   if r["child_unit_price_snapshot"] is not None else None))


class PostgresCartRepository:
    def __init__(self, database_url: str):
        self._database_url = database_url

    async def _cart_row(self, conn, cdp_user_id: str) -> dict:
        await conn.execute(
            "INSERT INTO app.carts (cdp_user_id) VALUES (%s) ON CONFLICT (cdp_user_id) DO NOTHING", (cdp_user_id,))
        return await (await conn.execute(
            "SELECT cart_id::text AS cart_id, updated_at FROM app.carts WHERE cdp_user_id = %s", (cdp_user_id,)
        )).fetchone()

    async def get(self, cdp_user_id: str) -> Cart:
        async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
            cart = await self._cart_row(conn, cdp_user_id)
            rows = await (await conn.execute(
                """
                SELECT cart_item_id::text AS cart_item_id, product_id::text AS product_id, quantity, using_date,
                       using_date_to, unit_price_snapshot, added_at, adults, children, child_unit_price_snapshot
                  FROM app.cart_items WHERE cart_id = %s::uuid ORDER BY added_at, cart_item_id
                """, (cart["cart_id"],))).fetchall()
        lines = [_line_of(r) for r in rows]
        return Cart(cart_id=cart["cart_id"], cdp_user_id=cdp_user_id, lines=lines, updated_at=cart["updated_at"])

    async def upsert(
        self, cdp_user_id: str, *, product_id: str, using_date: date, quantity: int, nights: int | None,
        unit_price: int, adults: int, children: int, child_unit_price: int | None,
    ) -> None:
        end = using_date + timedelta(days=nights) if nights else None
        async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
            cart = await self._cart_row(conn, cdp_user_id)
            await conn.execute(
                """
                INSERT INTO app.cart_items
                    (cart_id, product_id, quantity, using_date, using_date_to, unit_price_snapshot, adults, children,
                     child_unit_price_snapshot)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (cart_id, product_id, using_date) DO UPDATE
                   SET quantity = EXCLUDED.quantity,
                       using_date_to = EXCLUDED.using_date_to,
                       unit_price_snapshot = EXCLUDED.unit_price_snapshot,
                       adults = EXCLUDED.adults,
                       children = EXCLUDED.children,
                       child_unit_price_snapshot = EXCLUDED.child_unit_price_snapshot
                """, (cart["cart_id"], product_id, quantity, using_date, end, unit_price, adults, children,
                      child_unit_price))
            await conn.execute("UPDATE app.carts SET updated_at = now() WHERE cart_id = %s::uuid", (cart["cart_id"],))
            await conn.commit()

    async def update(
        self, cdp_user_id: str, cart_item_id: str, *, using_date: date | None, quantity: int, nights: int | None,
        nights_given: bool, unit_price: int, adults: int, children: int, child_unit_price: int | None,
    ) -> bool:
        item_id = _uuid_or_none(cart_item_id)
        if item_id is None:
            return False
        try:
            async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
                cart = await self._cart_row(conn, cdp_user_id)
                row = await (await conn.execute(
                    """
                    UPDATE app.cart_items
                       SET using_date = COALESCE(%s::date, using_date),
                           quantity = %s::int,
                           using_date_to = CASE WHEN %s::int IS NULL THEN NULL
                                                ELSE COALESCE(%s::date, using_date) + %s::int END,
                           unit_price_snapshot = %s,
                           adults = %s,
                           children = %s,
                           child_unit_price_snapshot = %s
                     WHERE cart_item_id = %s::uuid AND cart_id = %s::uuid
                 RETURNING cart_item_id
                    """, (using_date, quantity, nights, using_date, nights, unit_price, adults, children,
                          child_unit_price, item_id, cart["cart_id"])
                )).fetchone()
                if row:
                    await conn.execute(
                        "UPDATE app.carts SET updated_at = now() WHERE cart_id = %s::uuid", (cart["cart_id"],))
                await conn.commit()
        except psycopg.errors.UniqueViolation as exc:
            raise ValidationFailed("đã có mục cùng sản phẩm và ngày này trong giỏ") from exc
        return row is not None

    async def remove(self, cdp_user_id: str, cart_item_id: str) -> bool:
        item_id = _uuid_or_none(cart_item_id)
        if item_id is None:
            return False
        async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
            cart = await self._cart_row(conn, cdp_user_id)
            row = await (await conn.execute(
                "DELETE FROM app.cart_items WHERE cart_item_id = %s::uuid AND cart_id = %s::uuid RETURNING 1",
                (item_id, cart["cart_id"]))).fetchone()
            if row:
                await conn.execute("UPDATE app.carts SET updated_at = now() WHERE cart_id = %s::uuid", (cart["cart_id"],))
            await conn.commit()
        return row is not None


class PostgresBookingDraftRepository:
    """Đơn nháp của người đã đăng nhập (app.booking_drafts, app.booking_draft_items); spec dat-truc-tiep-theo-don-nhap.md §4."""

    def __init__(self, database_url: str):
        self._database_url = database_url

    @staticmethod
    async def _insert(conn, draft: BookingDraft) -> None:
        await conn.execute(
            "INSERT INTO app.booking_drafts (draft_id, cdp_user_id, created_at, expires_at) VALUES (%s::uuid, %s, %s, %s)",
            (draft.draft_id, draft.owner_key, draft.created_at, draft.expires_at))
        for line in draft.lines:
            end = line.using_date + timedelta(days=line.nights) if line.nights else None
            await conn.execute(
                """
                INSERT INTO app.booking_draft_items
                    (draft_item_id, draft_id, product_id, quantity, using_date, using_date_to, unit_price_snapshot,
                     adults, children, child_unit_price_snapshot)
                VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s)
                """, (line.cart_item_id, draft.draft_id, line.product_id, line.quantity, line.using_date, end,
                      line.unit_price_snapshot, line.adults, line.children, line.child_unit_price_snapshot))

    async def create(self, draft: BookingDraft, *, copy_to_cart: Sequence[CartLine], now: datetime, max_live: int) -> None:
        # Một transaction: dọn đơn nháp cũ, ghi đơn nháp mới và chép mục vào giỏ cùng thành công hoặc cùng không (R-CPY-03).
        async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
            await conn.execute(
                "DELETE FROM app.booking_drafts WHERE cdp_user_id = %s AND expires_at <= %s", (draft.owner_key, now))
            # Giữ tối đa max_live đơn nháp còn hạn kể cả cái sắp ghi: bỏ các cái cũ nhất (R-DRF-07).
            await conn.execute(
                """
                DELETE FROM app.booking_drafts WHERE draft_id IN (
                    SELECT draft_id FROM app.booking_drafts WHERE cdp_user_id = %s
                     ORDER BY created_at DESC, draft_id OFFSET %s)
                """, (draft.owner_key, max(0, max_live - 1)))
            await self._insert(conn, draft)
            if copy_to_cart:
                await conn.execute(
                    "INSERT INTO app.carts (cdp_user_id) VALUES (%s) ON CONFLICT (cdp_user_id) DO NOTHING",
                    (draft.owner_key,))
                for line in copy_to_cart:
                    end = line.using_date + timedelta(days=line.nights) if line.nights else None
                    # Giỏ đã có mục cùng sản phẩm và ngày thì giữ nguyên: không cộng dồn, không ghi đè (R-CPY-02).
                    await conn.execute(
                        """
                        INSERT INTO app.cart_items
                            (cart_id, product_id, quantity, using_date, using_date_to, unit_price_snapshot, adults,
                             children, child_unit_price_snapshot)
                        SELECT c.cart_id, %s::uuid, %s, %s, %s, %s, %s, %s, %s FROM app.carts c WHERE c.cdp_user_id = %s
                        ON CONFLICT (cart_id, product_id, using_date) DO NOTHING
                        """, (line.product_id, line.quantity, line.using_date, end, line.unit_price_snapshot,
                              line.adults, line.children, line.child_unit_price_snapshot, draft.owner_key))
                await conn.execute("UPDATE app.carts SET updated_at = now() WHERE cdp_user_id = %s", (draft.owner_key,))
            await conn.commit()

    async def get(self, owner_key: str, draft_id: str) -> BookingDraft | None:
        draft_id = _uuid_or_none(draft_id)
        if draft_id is None:
            return None
        async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
            # Lọc theo chủ ngay trong WHERE: đơn nháp của người khác coi như không tồn tại (auth §14.2).
            head = await (await conn.execute(
                "SELECT created_at, expires_at FROM app.booking_drafts WHERE draft_id = %s::uuid AND cdp_user_id = %s",
                (draft_id, owner_key))).fetchone()
            if head is None:
                return None
            rows = await (await conn.execute(
                """
                SELECT draft_item_id::text AS cart_item_id, product_id::text AS product_id, quantity, using_date,
                       using_date_to, unit_price_snapshot, added_at, adults, children, child_unit_price_snapshot
                  FROM app.booking_draft_items WHERE draft_id = %s::uuid ORDER BY using_date, added_at, draft_item_id
                """, (draft_id,))).fetchall()
        return BookingDraft(draft_id, owner_key, [_line_of(r) for r in rows], head["created_at"], head["expires_at"])

    async def update_item(
        self, owner_key: str, draft_id: str, cart_item_id: str, *, using_date: date | None, quantity: int,
        nights: int | None, unit_price: int, adults: int, children: int, child_unit_price: int | None,
    ) -> bool:
        draft_id, item_id = _uuid_or_none(draft_id), _uuid_or_none(cart_item_id)
        if draft_id is None or item_id is None:
            return False
        try:
            async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
                row = await (await conn.execute(
                    """
                    UPDATE app.booking_draft_items i
                       SET using_date = COALESCE(%s::date, i.using_date),
                           quantity = %s::int,
                           using_date_to = CASE WHEN %s::int IS NULL THEN NULL
                                                ELSE COALESCE(%s::date, i.using_date) + %s::int END,
                           unit_price_snapshot = %s,
                           adults = %s,
                           children = %s,
                           child_unit_price_snapshot = %s
                      FROM app.booking_drafts d
                     WHERE i.draft_item_id = %s::uuid AND i.draft_id = d.draft_id AND d.draft_id = %s::uuid
                       AND d.cdp_user_id = %s
                 RETURNING i.draft_item_id
                    """, (using_date, quantity, nights, using_date, nights, unit_price, adults, children,
                          child_unit_price, item_id, draft_id, owner_key))).fetchone()
                await conn.commit()
        except psycopg.errors.UniqueViolation as exc:
            raise ValidationFailed("đã có mục cùng sản phẩm và ngày này trong lần đặt") from exc
        return row is not None

    async def remove_item(self, owner_key: str, draft_id: str, cart_item_id: str) -> bool:
        draft_id, item_id = _uuid_or_none(draft_id), _uuid_or_none(cart_item_id)
        if draft_id is None or item_id is None:
            return False
        async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
            row = await (await conn.execute(
                """
                DELETE FROM app.booking_draft_items i USING app.booking_drafts d
                 WHERE i.draft_item_id = %s::uuid AND i.draft_id = d.draft_id AND d.draft_id = %s::uuid
                   AND d.cdp_user_id = %s
             RETURNING i.draft_item_id
                """, (item_id, draft_id, owner_key))).fetchone()
            if row:
                # Đơn nháp không còn mục nào thì xoá luôn: không để lại đơn nháp rỗng (R-DRF-14).
                await conn.execute(
                    """
                    DELETE FROM app.booking_drafts d WHERE d.draft_id = %s::uuid
                       AND NOT EXISTS (SELECT 1 FROM app.booking_draft_items i WHERE i.draft_id = d.draft_id)
                    """, (draft_id,))
            await conn.commit()
        return row is not None

    async def adopt(self, draft: BookingDraft) -> bool:
        if _uuid_or_none(draft.draft_id) is None:
            return False
        try:
            async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
                await self._insert(conn, draft)
                await conn.commit()
        except psycopg.errors.UniqueViolation:
            return False  # đã gộp ở lần gọi trước (R-MRG-04)
        return True


_BOOKING_SELECT = """
    SELECT b.booking_id::text AS booking_id, b.reference_code, b.cdp_user_id, b.event_group_id, b.status,
           b.contact_name, b.contact_email, b.contact_phone, b.currency, b.created_at, b.hold_expires_at,
           b.confirmed_at, b.cancelled_at, b.cancel_reason, b.purchase_events_cancelled_at,
           p.payment_id::text AS payment_id, p.provider, p.checkout_session_id, p.payment_intent_id, p.checkout_url,
           p.amount AS payment_amount, p.currency AS payment_currency, p.status AS payment_status,
           p.failed_attempts, p.last_failure_code, p.refund_id, p.updated_at AS payment_updated_at
      FROM app.bookings b LEFT JOIN app.payments p ON p.booking_id = b.booking_id
"""


def _documents_to_json(docs: TravelerDocuments) -> dict:
    return {"title": docs.title, "nationality": docs.nationality, "docType": docs.doc_type, "docNumber": docs.doc_number,
            "docExpiry": docs.doc_expiry.isoformat() if docs.doc_expiry else None, "escortTravelerRef": docs.escort_ref}


def _documents_from_json(raw: dict | None) -> TravelerDocuments | None:
    if not raw:
        return None
    expiry = raw.get("docExpiry")
    return TravelerDocuments(raw["title"], raw["nationality"], raw.get("docType"), raw.get("docNumber"),
                             date.fromisoformat(expiry) if expiry else None, raw.get("escortTravelerRef"))


def _metadata_of(item: BookingItem) -> dict:
    return {
        "fares": [fare.to_json() for fare in item.fares],
        "travelerRefs": list(item.traveler_refs),
        "rooms": [{"travelerRefs": list(r.traveler_refs), "leadTravelerRef": r.lead_traveler_ref} for r in item.rooms],
    }


def _item_metadata(metadata: dict | None) -> dict:
    """`booking_items.metadata` → các trường của BookingItem. Đơn tạo trước khi có dòng giá thì metadata rỗng."""
    meta = metadata or {}
    return {
        "fares": [FareLine.from_json(f) for f in meta.get("fares", [])],
        "traveler_refs": list(meta.get("travelerRefs", [])),
        "rooms": [RoomAllocation(tuple(r["travelerRefs"]), r["leadTravelerRef"]) for r in meta.get("rooms", [])],
    }


def _payment_of(row: dict) -> Payment | None:
    if not row["payment_id"]:
        return None
    return Payment(
        payment_id=row["payment_id"], provider=row["provider"], amount=int(row["payment_amount"]),
        currency=row["payment_currency"].strip(), status=PaymentStatus(row["payment_status"]),
        checkout_session_id=row["checkout_session_id"], payment_intent_id=row["payment_intent_id"],
        checkout_url=row["checkout_url"], failed_attempts=row["failed_attempts"],
        last_failure_code=row["last_failure_code"], refund_id=row["refund_id"], updated_at=row["payment_updated_at"])


_ITEM_SELECT = """
    SELECT booking_item_id::text AS booking_item_id, booking_id::text AS booking_id, product_id::text AS product_id,
           taxonomy, product_name, unit_price, quantity, using_date, using_date_to, guest_names, special_request, metadata
      FROM app.booking_items
"""


def _item_of(i: dict) -> BookingItem:
    return BookingItem(
        booking_item_id=i["booking_item_id"], product_id=i["product_id"], taxonomy=i["taxonomy"],
        product_name=i["product_name"], unit_price=int(i["unit_price"]), quantity=i["quantity"],
        using_date=i["using_date"], nights=_nights(i["using_date"], i["using_date_to"]),
        guest_names=list(i["guest_names"] or []), special_request=i["special_request"],
        **_item_metadata(i["metadata"]))


class _Tx:
    def __init__(self, conn: psycopg.AsyncConnection):
        self._conn = conn

    async def _load(self, where: str, params: tuple, lock: bool) -> Booking | None:
        sql = f"{_BOOKING_SELECT} WHERE {where} LIMIT 1" + (" FOR UPDATE OF b" if lock else "")
        row = await (await self._conn.execute(sql, params)).fetchone()
        if row is None:
            return None
        items = await (await self._conn.execute(
            """
            SELECT booking_item_id::text AS booking_item_id, product_id::text AS product_id, taxonomy, product_name,
                   unit_price, quantity, using_date, using_date_to, guest_names, special_request, metadata
              FROM app.booking_items WHERE booking_id = %s::uuid ORDER BY using_date, booking_item_id
            """, (row["booking_id"],))).fetchall()
        travelers = await (await self._conn.execute(
            """
            SELECT traveler_ref, traveler_type, surname, given_names, birth_date, documents
              FROM app.booking_travelers WHERE booking_id = %s::uuid ORDER BY position
            """, (row["booking_id"],))).fetchall()
        return Booking(
            booking_id=row["booking_id"], reference_code=row["reference_code"], cdp_user_id=row["cdp_user_id"],
            event_group_id=row["event_group_id"], contact_name=row["contact_name"], contact_email=row["contact_email"],
            contact_phone=row["contact_phone"], created_at=row["created_at"], status=BookingStatus(row["status"]),
            currency=row["currency"].strip(), hold_expires_at=row["hold_expires_at"],
            confirmed_at=row["confirmed_at"], cancelled_at=row["cancelled_at"], cancel_reason=row["cancel_reason"],
            purchase_events_cancelled_at=row["purchase_events_cancelled_at"], payment=_payment_of(row),
            items=[_item_of(i) for i in items],
            travelers=[
                Traveler(t["traveler_ref"], TravelerType(t["traveler_type"]), t["surname"], t["given_names"],
                         t["birth_date"], _documents_from_json(t["documents"]))
                for t in travelers
            ])

    async def get_by_id(self, booking_id: str, *, lock: bool = False) -> Booking | None:
        # Kiểm uuid trước khi truy vấn: lỗi ép kiểu trong Postgres làm hỏng cả transaction đang mở.
        booking_id = _uuid_or_none(booking_id)
        return await self._load("b.booking_id = %s::uuid", (booking_id,), lock) if booking_id else None

    async def get_by_reference(self, reference_code: str, cdp_user_id: str, *, lock: bool = False) -> Booking | None:
        return await self._load("b.reference_code = %s AND b.cdp_user_id = %s", (reference_code, cdp_user_id), lock)

    async def get_by_session(self, session_id: str, *, lock: bool = False) -> Booking | None:
        return await self._load("p.checkout_session_id = %s", (session_id,), lock)

    async def get_pending_for_user(self, cdp_user_id: str, *, lock: bool = False) -> Booking | None:
        return await self._load("b.cdp_user_id = %s AND b.status = 'pending_payment'", (cdp_user_id,), lock)

    async def list_overviews(self, cdp_user_id: str, since: datetime | None) -> list[BookingOverview]:
        rows = await (await self._conn.execute(
            """
            SELECT b.booking_id::text AS booking_id, b.status, b.created_at, b.hold_expires_at,
                   max(COALESCE(i.using_date_to, i.using_date)) AS last_end_date,
                   array_agg(DISTINCT i.taxonomy ORDER BY i.taxonomy) AS taxonomies
              FROM app.bookings b JOIN app.booking_items i ON i.booking_id = b.booking_id
             WHERE b.cdp_user_id = %s AND (%s::timestamptz IS NULL OR b.created_at >= %s::timestamptz)
             GROUP BY b.booking_id
             ORDER BY b.created_at DESC, b.booking_id DESC
            """, (cdp_user_id, since, since))).fetchall()
        return [BookingOverview(r["booking_id"], BookingStatus(r["status"]), r["created_at"], r["hold_expires_at"],
                                r["last_end_date"], tuple(r["taxonomies"])) for r in rows]

    async def get_many(self, booking_ids: Sequence[str]) -> list[Booking]:
        ids = [i for i in (_uuid_or_none(b) for b in booking_ids) if i]
        if not ids:
            return []
        rows = await (await self._conn.execute(f"{_BOOKING_SELECT} WHERE b.booking_id = ANY(%s::uuid[])", (ids,))).fetchall()
        items = await (await self._conn.execute(
            f"{_ITEM_SELECT} WHERE booking_id = ANY(%s::uuid[]) ORDER BY using_date, booking_item_id", (ids,))).fetchall()
        by_booking: dict[str, list[dict]] = {}
        for item in items:
            by_booking.setdefault(item["booking_id"], []).append(item)
        found = {
            row["booking_id"]: Booking(
                booking_id=row["booking_id"], reference_code=row["reference_code"], cdp_user_id=row["cdp_user_id"],
                event_group_id=row["event_group_id"], contact_name=row["contact_name"],
                contact_email=row["contact_email"], contact_phone=row["contact_phone"], created_at=row["created_at"],
                status=BookingStatus(row["status"]), currency=row["currency"].strip(),
                hold_expires_at=row["hold_expires_at"], confirmed_at=row["confirmed_at"],
                cancelled_at=row["cancelled_at"], cancel_reason=row["cancel_reason"],
                purchase_events_cancelled_at=row["purchase_events_cancelled_at"], payment=_payment_of(row),
                items=[_item_of(i) for i in by_booking.get(row["booking_id"], [])])
            for row in rows
        }
        return [found[i] for i in ids if i in found]

    async def insert(self, booking: Booking) -> None:
        try:
            await self._conn.execute(
                """
                INSERT INTO app.bookings
                    (booking_id, reference_code, cdp_user_id, event_group_id, status, contact_name, contact_email,
                     contact_phone, total_amount, currency, created_at, hold_expires_at)
                VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (booking.booking_id, booking.reference_code, booking.cdp_user_id, booking.event_group_id,
                 booking.status.value, booking.contact_name, booking.contact_email, booking.contact_phone,
                 booking.total_amount, booking.currency, booking.created_at, booking.hold_expires_at))
        except psycopg.errors.UniqueViolation as exc:
            # Transaction đã hỏng; caller thoát khối `async with` nên sẽ rollback.
            constraint = getattr(exc.diag, "constraint_name", "") or ""
            if "one_pending" in constraint:
                raise PendingBookingExists(booking.cdp_user_id) from exc
            if "reference_code" in constraint:
                raise ReferenceCodeTaken(booking.reference_code) from exc
            raise
        for item in booking.items:
            end = item.using_date + timedelta(days=item.nights) if item.nights else None
            await self._conn.execute(
                """
                INSERT INTO app.booking_items
                    (booking_item_id, booking_id, product_id, taxonomy, product_name, unit_price, quantity,
                     using_date, using_date_to, guest_names, special_request, line_total, metadata)
                VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (item.booking_item_id, booking.booking_id, item.product_id, item.taxonomy, item.product_name,
                 item.unit_price, item.quantity, item.using_date, end, item.guest_names or None, item.special_request,
                 item.line_total, Jsonb(_metadata_of(item))))
        # Đoàn khách: ngày sinh chỉ nằm ở đây, không ra khỏi database (không API, không CDP, Insider hay Stripe).
        for position, traveler in enumerate(booking.travelers, start=1):
            await self._conn.execute(
                """
                INSERT INTO app.booking_travelers
                    (booking_id, traveler_ref, position, traveler_type, surname, given_names, full_name, birth_date,
                     documents)
                VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (booking.booking_id, traveler.ref, position, traveler.type.value, traveler.surname,
                 traveler.given_names, traveler.full_name, traveler.birth_date,
                 Jsonb(_documents_to_json(traveler.documents)) if traveler.documents else None))
        payment = booking.payment
        if payment is not None:
            await self._conn.execute(
                """
                INSERT INTO app.payments
                    (payment_id, booking_id, provider, checkout_session_id, payment_intent_id, checkout_url, amount,
                     currency, status, failed_attempts, last_failure_code, refund_id)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (payment.payment_id, booking.booking_id, payment.provider, payment.checkout_session_id,
                 payment.payment_intent_id, payment.checkout_url, payment.amount, payment.currency,
                 payment.status.value, payment.failed_attempts, payment.last_failure_code, payment.refund_id))

    async def save(self, booking: Booking) -> None:
        await self._conn.execute(
            """
            UPDATE app.bookings
               SET status = %s, hold_expires_at = %s, confirmed_at = %s, cancelled_at = %s, cancel_reason = %s,
                   purchase_events_cancelled_at = %s, updated_at = now()
             WHERE booking_id = %s::uuid
            """,
            (booking.status.value, booking.hold_expires_at, booking.confirmed_at, booking.cancelled_at,
             booking.cancel_reason, booking.purchase_events_cancelled_at, booking.booking_id))
        payment = booking.payment
        if payment is not None:
            await self._conn.execute(
                """
                UPDATE app.payments
                   SET payment_intent_id = %s, checkout_url = %s, status = %s, failed_attempts = %s,
                       last_failure_code = %s, refund_id = %s, updated_at = now()
                 WHERE payment_id = %s::uuid
                """,
                (payment.payment_intent_id, payment.checkout_url, payment.status.value, payment.failed_attempts,
                 payment.last_failure_code, payment.refund_id, payment.payment_id))

    async def clear_cart_items(self, cdp_user_id: str, keys: Sequence[tuple[str, date]]) -> None:
        for product_id, using_date in keys:
            await self._conn.execute(
                """
                DELETE FROM app.cart_items ci USING app.carts c
                 WHERE ci.cart_id = c.cart_id AND c.cdp_user_id = %s AND ci.product_id = %s::uuid
                   AND ci.using_date = %s
                """, (cdp_user_id, product_id, using_date))

    async def delete_draft(self, cdp_user_id: str, draft_id: str) -> None:
        draft_id = _uuid_or_none(draft_id)
        if draft_id is not None:
            await self._conn.execute(
                "DELETE FROM app.booking_drafts WHERE draft_id = %s::uuid AND cdp_user_id = %s", (draft_id, cdp_user_id))

    async def purge_expired_drafts(self, before: datetime) -> int:
        cursor = await self._conn.execute("DELETE FROM app.booking_drafts WHERE expires_at < %s", (before,))
        return cursor.rowcount

    async def find_reconcile_ids(self, now: datetime, limit: int) -> list[str]:
        rows = await (await self._conn.execute(
            """
            SELECT b.booking_id::text AS booking_id
              FROM app.bookings b JOIN app.payments p ON p.booking_id = b.booking_id
             WHERE (b.status = 'pending_payment'
                    AND (p.status = 'succeeded' OR (p.status = 'open' AND b.hold_expires_at < %s)))
                OR (p.status = 'refund_pending' AND p.refund_id IS NULL)
                OR (b.status = 'cancelled' AND b.confirmed_at IS NOT NULL AND b.purchase_events_cancelled_at IS NULL)
             ORDER BY b.updated_at
             LIMIT %s
               FOR UPDATE OF b SKIP LOCKED
            """, (now, limit))).fetchall()
        return [r["booking_id"] for r in rows]


#: Khoá advisory của job đối soát (hằng số cố định để mọi bản sao backend tranh cùng một khoá).
RECONCILE_LOCK_KEY = 0x564F5441_0001   # "VOTA" + 1


class PostgresBookingStore:
    def __init__(self, database_url: str, leader_lock_database_url: str | None = None):
        self._database_url = database_url
        # Khoá advisory mức session cần một connection Postgres thật; qua pgbouncer chế độ transaction nó rơi vào
        # connection phía server của người khác. Vì vậy DSN trực tiếp (không qua pooler), mặc định bằng database_url.
        self._leader_url = leader_lock_database_url or database_url

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[_Tx]:
        # `async with connection` commit khi thoát bình thường và rollback khi có exception.
        async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
            yield _Tx(conn)

    @asynccontextmanager
    async def reconcile_leader(self) -> AsyncIterator[bool]:
        # Advisory lock mức session trên một connection riêng: đóng connection là nhả khoá, kể cả khi
        # tiến trình chết. Phải dùng DSN trực tiếp, không qua pgbouncer chế độ transaction.
        async with await psycopg.AsyncConnection.connect(self._leader_url, autocommit=True) as conn:
            cur = await conn.execute("SELECT pg_try_advisory_lock(%s)", (RECONCILE_LOCK_KEY,))
            acquired = bool((await cur.fetchone())[0])
            try:
                yield acquired
            finally:
                if acquired:
                    await conn.execute("SELECT pg_advisory_unlock(%s)", (RECONCILE_LOCK_KEY,))
