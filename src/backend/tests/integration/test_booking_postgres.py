"""Adapter Postgres của giỏ hàng, đơn giữ chỗ, đoàn khách và thanh toán trên database local đã seed + migrate (0003…0005).

Chạy bằng role `vota_app` (DATABASE_URL) như Backend thật. Dùng một user test seed và tự dọn mọi dòng đã tạo.
"""
import asyncio
import os
import uuid
from datetime import date, datetime, timedelta, timezone

import psycopg
import pytest

from src.backend.app.application.ports.booking_store import PendingBookingExists
from src.backend.app.domain.booking import (
    Booking, BookingItem, FareLine, FareType, Payment, RoomAllocation, Traveler, TravelerType,
)
from src.backend.app.domain.booking.party import TravelerDocuments
from src.backend.app.domain.booking.status import BookingStatus, PaymentStatus
from src.backend.app.infrastructure.persistence.postgres_booking import (
    PostgresBookingStore,
    PostgresCartRepository,
    PostgresProductCatalog,
)

APP_URL = os.getenv("DATABASE_URL", "postgresql://vota_app_login:vota@localhost:5432/vota")
USER = os.getenv("BOOKING_TEST_CDP_USER_ID", "VP0000054")       # test50@vota.demo — không phải persona

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="set RUN_POSTGRES_INTEGRATION=1 to test the seeded local database",
)


def _cleanup() -> None:
    with psycopg.connect(APP_URL, autocommit=True) as conn:
        conn.execute("DELETE FROM app.bookings WHERE cdp_user_id = %s", (USER,))   # payments, items: ON DELETE CASCADE
        conn.execute("DELETE FROM app.carts WHERE cdp_user_id = %s", (USER,))


@pytest.fixture
def bookable_hotel_room() -> str:
    _cleanup()
    with psycopg.connect(APP_URL) as conn:
        row = conn.execute(
            """
            SELECT product_id::text FROM cdp.products
             WHERE taxonomy = 'hotel' AND attributes->>'level' = 'room' AND available AND unit_price IS NOT NULL
               AND available_from IS NOT NULL
             ORDER BY product_id LIMIT 1
            """).fetchone()
    if row is None:
        pytest.skip("không có phòng khách sạn bán được trong catalog local")
    yield row[0]
    _cleanup()


def _booking(product, using: date, *, status=BookingStatus.PENDING_PAYMENT, party: bool = False) -> Booking:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    booking_id = str(uuid.uuid4())
    item = BookingItem(str(uuid.uuid4()), product.product_id, "hotel", product.name, int(product.unit_price), 1,
                       using, nights=2, guest_names=["Test"], special_request="Tầng cao")
    travelers: list[Traveler] = []
    if party:  # một phòng, 2 người lớn + 1 trẻ em; dòng giá ROOM 1 phòng × 2 đêm
        travelers = [Traveler("t1", TravelerType.ADULT, "Nguyễn", "Minh Anh", None,
                              TravelerDocuments("MS", "KR", "PASSPORT", "C1234567", date(2031, 1, 1))),
                     Traveler("t2", TravelerType.ADULT, "Trần", "Thu Hà"),
                     Traveler("t3", TravelerType.CHILD, "Nguyễn", "Gia Bảo", date(2019, 5, 12),
                              TravelerDocuments("MSTR", "VN", escort_ref="t1"))]
        item.fares = [FareLine(FareType.ROOM, int(product.unit_price), 1, 2)]
        item.traveler_refs = ["t1", "t2", "t3"]
        item.rooms = [RoomAllocation(("t1", "t2", "t3"), "t1")]
        item.guest_names = [t.full_name for t in travelers]
    booking = Booking(
        booking_id=booking_id, reference_code=f"VOTA-{now:%Y%m%d}-{uuid.uuid4().hex[:4].upper()}", cdp_user_id=USER,
        event_group_id=f"OFFIT{uuid.uuid4().hex[:10].upper()}", contact_name="Test", contact_email="t@vota.demo",
        contact_phone="0912345678", created_at=now, status=status, hold_expires_at=now + timedelta(minutes=31),
        items=[item], travelers=travelers,
    )
    booking.payment = Payment(str(uuid.uuid4()), "fake", booking.total_amount,
                              checkout_session_id=f"cs_it_{uuid.uuid4().hex[:12]}", checkout_url="https://checkout.fake/x")
    return booking


def test_cart_repository_upserts_updates_and_removes(bookable_hotel_room) -> None:
    async def scenario() -> None:
        catalog, carts = PostgresProductCatalog(APP_URL), PostgresCartRepository(APP_URL)
        product = (await catalog.get_products([bookable_hotel_room, "not-a-uuid"]))[bookable_hotel_room]
        using = product.available_from
        price = int(product.unit_price)
        # upsert ghi giá trị TUYỆT ĐỐI: cùng productId + usingDate thì ghi đè một dòng (cộng dồn do use case làm)
        await carts.upsert(USER, product_id=product.product_id, using_date=using, quantity=1, nights=2, unit_price=price,
                           adults=1, children=0, child_unit_price=None)
        await carts.upsert(USER, product_id=product.product_id, using_date=using, quantity=2, nights=2, unit_price=price,
                           adults=3, children=1, child_unit_price=None)
        cart = await carts.get(USER)
        assert len(cart.lines) == 1 and cart.lines[0].quantity == 2 and cart.lines[0].nights == 2
        assert (cart.lines[0].adults, cart.lines[0].children, cart.lines[0].child_unit_price_snapshot) == (3, 1, None)
        line = cart.lines[0]
        assert await carts.update(USER, line.cart_item_id, using_date=None, quantity=3, nights=4, nights_given=True,
                                  unit_price=price, adults=4, children=2, child_unit_price=450_000)
        line = (await carts.get(USER)).lines[0]
        assert (line.quantity, line.nights, line.unit_price_snapshot) == (3, 4, price)
        assert (line.guests.adults, line.guests.children, line.child_unit_price_snapshot) == (4, 2, 450_000)
        assert not await carts.update(USER, str(uuid.uuid4()), using_date=None, quantity=1, nights=None,
                                      nights_given=False, unit_price=1, adults=1, children=0, child_unit_price=None)
        assert await carts.remove(USER, line.cart_item_id)
        assert not await carts.remove(USER, "not-a-uuid")
        assert (await carts.get(USER)).lines == []
    asyncio.run(scenario())


def test_booking_store_round_trip_one_pending_per_user_and_reconcile_query(bookable_hotel_room) -> None:
    async def scenario() -> None:
        catalog, carts, store = (PostgresProductCatalog(APP_URL), PostgresCartRepository(APP_URL),
                                 PostgresBookingStore(APP_URL))
        product = (await catalog.get_products([bookable_hotel_room]))[bookable_hotel_room]
        using = product.available_from
        await carts.upsert(USER, product_id=product.product_id, using_date=using, quantity=1, nights=2,
                           unit_price=int(product.unit_price), adults=1, children=0, child_unit_price=None)

        booking = _booking(product, using)
        async with store.transaction() as tx:
            await tx.insert(booking)
        with pytest.raises(PendingBookingExists):                  # unique index bookings_one_pending_per_user
            async with store.transaction() as tx:
                await tx.insert(_booking(product, using))

        async with store.transaction() as tx:
            loaded = await tx.get_by_session(booking.payment.checkout_session_id, lock=True)
            assert loaded.reference_code == booking.reference_code and loaded.total_amount == booking.total_amount
            assert loaded.items[0].nights == 2 and loaded.items[0].special_request == "Tầng cao"
            assert loaded.payment.status is PaymentStatus.OPEN
            assert (await tx.get_pending_for_user(USER)).booking_id == booking.booking_id
            assert await tx.get_by_reference(booking.reference_code, "VP0000001") is None   # đơn người khác
            assert await tx.get_by_id("not-a-uuid") is None

            loaded.record_payment_received("pi_it_1")
            await tx.save(loaded)
        async with store.transaction() as tx:
            ids = await tx.find_reconcile_ids(datetime.now(timezone.utc), 100)
        assert booking.booking_id in ids                           # đã thu tiền nhưng chưa xác nhận

        async with store.transaction() as tx:
            loaded = await tx.get_by_id(booking.booking_id, lock=True)
            loaded.confirm(datetime.now(timezone.utc))
            await tx.save(loaded)
            await tx.clear_cart_items(USER, [(i.product_id, i.using_date) for i in loaded.items])
        async with store.transaction() as tx:
            confirmed = await tx.get_by_id(booking.booking_id)
            assert confirmed.status is BookingStatus.CONFIRMED and confirmed.payment.payment_intent_id == "pi_it_1"
            assert confirmed.hold_expires_at is None and confirmed.payment.checkout_url is None
            assert booking.booking_id not in await tx.find_reconcile_ids(datetime.now(timezone.utc), 100)
        assert (await carts.get(USER)).lines == []
    asyncio.run(scenario())


def test_booking_store_persists_travelers_fares_and_rooms_and_keeps_birth_date_private(bookable_hotel_room) -> None:
    async def scenario() -> None:
        catalog, store = PostgresProductCatalog(APP_URL), PostgresBookingStore(APP_URL)
        product = (await catalog.get_products([bookable_hotel_room]))[bookable_hotel_room]
        booking = _booking(product, product.available_from, party=True)
        async with store.transaction() as tx:
            await tx.insert(booking)

        async with store.transaction() as tx:
            loaded = await tx.get_by_id(booking.booking_id)
        assert [(t.ref, t.type, t.full_name, t.birth_date) for t in loaded.travelers] == [
            ("t1", TravelerType.ADULT, "Nguyễn Minh Anh", None), ("t2", TravelerType.ADULT, "Trần Thu Hà", None),
            ("t3", TravelerType.CHILD, "Nguyễn Gia Bảo", date(2019, 5, 12))]
        assert loaded.travelers[0].documents == TravelerDocuments("MS", "KR", "PASSPORT", "C1234567", date(2031, 1, 1))
        assert loaded.travelers[1].documents is None
        assert loaded.travelers[2].documents == TravelerDocuments("MSTR", "VN", escort_ref="t1")
        item = loaded.items[0]
        assert item.fares == [FareLine(FareType.ROOM, int(product.unit_price), 1, 2)]
        assert item.traveler_refs == ["t1", "t2", "t3"] and item.rooms == [RoomAllocation(("t1", "t2", "t3"), "t1")]
        assert item.line_total == booking.total_amount == int(product.unit_price) * 2

        with psycopg.connect(APP_URL) as conn:  # cột line_total do Backend ghi, khớp tổng đơn
            (line_total,) = conn.execute(
                "SELECT line_total FROM app.booking_items WHERE booking_item_id = %s::uuid",
                (item.booking_item_id,)).fetchone()
            (children,) = conn.execute(
                "SELECT count(*) FROM app.booking_travelers WHERE booking_id = %s::uuid AND traveler_type = 'child' "
                "AND birth_date IS NOT NULL", (booking.booking_id,)).fetchone()
        assert int(line_total) == booking.total_amount and children == 1

        _cleanup()                                 # xoá đơn kéo theo đoàn khách (ON DELETE CASCADE)
        with psycopg.connect(APP_URL) as conn:
            (left,) = conn.execute("SELECT count(*) FROM app.booking_travelers WHERE booking_id = %s::uuid",
                                   (booking.booking_id,)).fetchone()
        assert left == 0
    asyncio.run(scenario())


def test_database_rejects_a_child_without_birth_date_and_a_cart_over_nine_guests(bookable_hotel_room) -> None:
    async def scenario() -> None:
        catalog, store, carts = PostgresProductCatalog(APP_URL), PostgresBookingStore(APP_URL), PostgresCartRepository(APP_URL)
        product = (await catalog.get_products([bookable_hotel_room]))[bookable_hotel_room]
        booking = _booking(product, product.available_from, party=True)
        booking.travelers[2] = Traveler("t3", TravelerType.CHILD, "Nguyễn", "Gia Bảo", None)
        with pytest.raises(psycopg.errors.CheckViolation):     # booking_travelers_child_birth
            async with store.transaction() as tx:
                await tx.insert(booking)
        with pytest.raises(psycopg.errors.CheckViolation):     # cart_items_party_size
            await carts.upsert(USER, product_id=product.product_id, using_date=product.available_from, quantity=1,
                               nights=1, unit_price=int(product.unit_price), adults=8, children=2, child_unit_price=None)
    asyncio.run(scenario())
