"""Adapter giỏ, booking và catalog trên PostgreSQL local đã seed (role `vota_app`).

Ghi vào giỏ và `app.bookings` của một tài khoản test seed rồi tự dọn lại; không chạm `cdp.*`.
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from src.backend.app.application.ports.booking_repository import Booking, BookingLine
from src.backend.app.domain.booking import reference_code
from src.backend.app.infrastructure.persistence.postgres_bookings import PostgresBookingRepository
from src.backend.app.infrastructure.persistence.postgres_cart import PostgresCartRepository
from src.backend.app.infrastructure.persistence.postgres_catalog import PostgresProductCatalog

APP_URL = os.getenv("DATABASE_URL", "postgresql://vota_app_login:vota@localhost:5432/vota")

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="set RUN_POSTGRES_INTEGRATION=1 to test the seeded local database",
)


@pytest.fixture
def seeded():
    with psycopg.connect(APP_URL, autocommit=True) as conn:
        user = conn.execute("SELECT cdp_user_id FROM app.users WHERE email = 'test50@vota.demo'").fetchone()
        room = conn.execute(
            "SELECT p.product_id::text, p.attributes->>'parentProductId' FROM cdp.products p "
            "JOIN catalog.product_meta m USING (product_id) "
            "WHERE m.variant = 'hotel_room' AND m.is_bookable AND p.available LIMIT 1").fetchone()
    assert user and room, "cần database đã seed (make demo-db)"
    yield {"user": user[0], "room": room[0], "property": room[1]}
    with psycopg.connect(APP_URL, autocommit=True) as conn:  # dọn: không để lại giỏ hay đơn của test
        conn.execute("DELETE FROM app.bookings WHERE cdp_user_id = %s AND event_group_id LIKE 'WEBTEST%%'",
                     (user[0],))
        conn.execute("DELETE FROM app.cart_items WHERE cart_id IN (SELECT cart_id FROM app.carts WHERE cdp_user_id = %s)",
                     (user[0],))


def test_catalog_reads_any_level_and_children(seeded):
    async def scenario():
        catalog = PostgresProductCatalog(APP_URL)
        room = await catalog.get(seeded["room"])
        assert room is not None and room.is_bookable and room.parent_id == seeded["property"]
        parent = await catalog.get(seeded["property"])
        assert parent is not None and not parent.is_bookable
        assert seeded["room"] in {child.product_id for child in await catalog.children(seeded["property"])}
        assert await catalog.get("not-a-uuid") is None
        assert await catalog.get_many([seeded["room"], "not-a-uuid"]) == {seeded["room"]: room}

    asyncio.run(scenario())


def test_cart_merges_updates_and_removes(seeded):
    async def scenario():
        carts, user, room = PostgresCartRepository(APP_URL), seeded["user"], seeded["room"]
        day = datetime.now(timezone.utc).date() + timedelta(days=3)
        await carts.add(user, room, day, day + timedelta(days=1), 1, 1_000_000)
        await carts.add(user, room, day, day + timedelta(days=1), 2, 1_000_000)
        [line] = (await carts.load(user)).lines
        assert (line.product_id, line.quantity, line.unit_price_snapshot) == (room, 3, 1_000_000)
        assert await carts.update(user, line.cart_item_id, day, day + timedelta(days=2), 1)
        assert (await carts.load(user)).lines[0].using_date_to == day + timedelta(days=2)
        assert not await carts.update("VP-khac", line.cart_item_id, day, None, 1)
        assert not await carts.remove(user, "not-a-uuid")
        assert await carts.remove(user, line.cart_item_id)
        assert (await carts.load(user)).lines == ()

    asyncio.run(scenario())


def test_booking_save_clears_the_cart_and_reads_back_for_the_owner_only(seeded):
    async def scenario():
        carts, bookings = PostgresCartRepository(APP_URL), PostgresBookingRepository(APP_URL)
        user, room = seeded["user"], seeded["room"]
        now = datetime.now(timezone.utc).replace(microsecond=0)
        day = now.date() + timedelta(days=3)
        await carts.add(user, room, day, day + timedelta(days=2), 1, 1_000_000)
        booking = Booking(
            reference_code=reference_code(now.date()), cdp_user_id=user,
            event_group_id=f"WEBTEST{now:%Y%m%d%H%M%S}",  # tiền tố riêng để fixture dọn đúng đơn của test
            contact_name="Khách Test", contact_email="khach@example.com", contact_phone="0912345678",
            special_request=None, total_amount=2_000_000, currency="VND", created_at=now,
            lines=(BookingLine(booking_item_id="00000000-0000-4000-8000-000000000001", product_id=room,
                               taxonomy="hotel", product_name="Phòng test", unit_price=1_000_000, quantity=1,
                               using_date=day, using_date_to=day + timedelta(days=2), guest_names=("Khách",)),),
        )
        assert not await bookings.reference_taken(booking.reference_code)
        await bookings.save(booking)
        assert await bookings.reference_taken(booking.reference_code)
        assert (await carts.load(user)).lines == ()  # cùng transaction với booking
        assert await bookings.find(booking.reference_code, user) == booking
        assert await bookings.find(booking.reference_code, "VP-khac") is None

    asyncio.run(scenario())
