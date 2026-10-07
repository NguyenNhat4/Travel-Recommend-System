"""Adapter Postgres của giỏ hàng, đơn nháp, đơn giữ chỗ, đoàn khách và thanh toán trên database local đã seed + migrate (0003…0007).

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
    Booking, BookingDraft, BookingItem, BookingTab, CartLine, FareLine, FareType, Payment, RoomAllocation, Traveler,
    TravelerType, tab_of,
)
from src.backend.app.domain.booking.party import TravelerDocuments
from src.backend.app.domain.booking.status import BookingStatus, PaymentStatus
from src.backend.app.infrastructure.persistence.postgres_booking import (
    PostgresBookingDraftRepository,
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
        conn.execute("DELETE FROM app.booking_drafts WHERE cdp_user_id = %s", (USER,))   # items: ON DELETE CASCADE


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


# --- đơn nháp của Đặt ngay (migration 0007; spec dat-truc-tiep-theo-don-nhap.md §4, §5, §11) -------------------------

@pytest.fixture
def ticket_id(bookable_hotel_room) -> str:
    with psycopg.connect(APP_URL) as conn:
        row = conn.execute(
            """
            SELECT product_id::text FROM cdp.products
             WHERE taxonomy = 'attraction' AND available AND unit_price IS NOT NULL ORDER BY product_id LIMIT 1
            """).fetchone()
    if row is None:
        pytest.skip("không có vé tham quan bán được trong catalog local")
    return row[0]


def _draft(lines, *, minutes=30, created=None) -> BookingDraft:
    created = created or datetime.now(timezone.utc).replace(microsecond=0)
    return BookingDraft(str(uuid.uuid4()), USER, lines, created, created + timedelta(minutes=minutes))


def _line(product_id: str, using: date, **kw) -> CartLine:
    return CartLine(str(uuid.uuid4()), product_id, kw.get("quantity", 1), using, kw.get("nights"), kw.get("price", 500_000),
                    adults=kw.get("adults", 2), children=kw.get("children", 1), child_unit_price_snapshot=kw.get("child"))


def test_draft_round_trip_copies_tours_to_cart_once_and_is_scoped_to_its_owner(bookable_hotel_room, ticket_id):
    async def scenario():
        drafts, carts = PostgresBookingDraftRepository(APP_URL), PostgresCartRepository(APP_URL)
        using = date.today() + timedelta(days=3)
        room = _line(bookable_hotel_room, using, nights=2, price=1_200_000)
        ticket = _line(ticket_id, using, quantity=3, child=250_000)
        now = datetime.now(timezone.utc)
        draft = _draft([room, ticket])
        await drafts.create(draft, copy_to_cart=[ticket], now=now, max_live=5)

        loaded = await drafts.get(USER, draft.draft_id)
        assert loaded.created_at == draft.created_at and loaded.expires_at == draft.expires_at
        by = {l.product_id: l for l in loaded.lines}
        assert set(by) == {bookable_hotel_room, ticket_id} and by[bookable_hotel_room].nights == 2
        assert (by[ticket_id].cart_item_id, by[ticket_id].quantity, by[ticket_id].adults, by[ticket_id].children,
                by[ticket_id].unit_price_snapshot, by[ticket_id].child_unit_price_snapshot) == (
            ticket.cart_item_id, 3, 2, 1, 500_000, 250_000)
        assert await drafts.get("VP0000001", draft.draft_id) is None            # của người khác: như không tồn tại
        assert await drafts.get(USER, "not-a-uuid") is None

        cart = await carts.get(USER)
        assert [(l.product_id, l.quantity) for l in cart.lines] == [(ticket_id, 3)]   # phòng không vào giỏ
        # Lần Đặt ngay thứ hai với số khác: mục giỏ có sẵn giữ nguyên (R-CPY-02).
        again = _line(ticket_id, using, quantity=9, adults=9, children=0)
        await drafts.create(_draft([again]), copy_to_cart=[again], now=now, max_live=5)
        assert [(l.product_id, l.quantity) for l in (await carts.get(USER)).lines] == [(ticket_id, 3)]

        # Sửa mục đơn nháp: ghi lại snapshot, không đổi giỏ (R-DRF-13, R-CPY-04).
        changes = dict(using_date=None, quantity=4, nights=None, unit_price=650_000, adults=3, children=1, child_unit_price=None)
        assert await drafts.update_item(USER, draft.draft_id, ticket.cart_item_id, **changes) is True
        assert await drafts.update_item("VP0000001", draft.draft_id, ticket.cart_item_id, **changes) is False
        assert await drafts.update_item(USER, draft.draft_id, str(uuid.uuid4()), **changes) is False
        patched = next(l for l in (await drafts.get(USER, draft.draft_id)).lines if l.product_id == ticket_id)
        assert (patched.quantity, patched.unit_price_snapshot, patched.adults, patched.child_unit_price_snapshot) == (
            4, 650_000, 3, None)
        assert (await carts.get(USER)).lines[0].quantity == 3

        # Bỏ mục: còn lại mục kia; bỏ mục cuối thì đơn nháp bị xoá; giỏ không đổi (R-DRF-14).
        assert await drafts.remove_item("VP0000001", draft.draft_id, ticket.cart_item_id) is False
        assert await drafts.remove_item(USER, draft.draft_id, ticket.cart_item_id) is True
        assert [l.product_id for l in (await drafts.get(USER, draft.draft_id)).lines] == [bookable_hotel_room]
        assert await drafts.remove_item(USER, draft.draft_id, room.cart_item_id) is True
        assert await drafts.get(USER, draft.draft_id) is None and len((await carts.get(USER)).lines) == 1
    asyncio.run(scenario())


def test_drafts_keep_five_live_ones_sweep_expired_and_adopt_is_idempotent(bookable_hotel_room):
    async def scenario():
        drafts = PostgresBookingDraftRepository(APP_URL)
        using = date.today() + timedelta(days=3)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        expired = _draft([_line(bookable_hotel_room, using, nights=1)], created=now - timedelta(hours=2))
        await drafts.create(expired, copy_to_cart=[], now=now - timedelta(hours=2), max_live=5)
        made = []
        for i in range(6):
            draft = _draft([_line(bookable_hotel_room, using, nights=1)], created=now + timedelta(seconds=i))
            await drafts.create(draft, copy_to_cart=[], now=now, max_live=5)
            made.append(draft.draft_id)
        assert await drafts.get(USER, expired.draft_id) is None                 # đã hết hạn: bị dọn khi tạo mới
        assert await drafts.get(USER, made[0]) is None                          # cái cũ nhất nhường chỗ (R-DRF-07)
        assert all([await drafts.get(USER, d) is not None for d in made[1:]])

        guest_draft = _draft([_line(bookable_hotel_room, using, nights=2)])     # gộp từ khách: giữ nguyên mã và hạn
        assert await drafts.adopt(guest_draft) is True and await drafts.adopt(guest_draft) is False
        adopted = await drafts.get(USER, guest_draft.draft_id)
        assert adopted.expires_at == guest_draft.expires_at and len(adopted.lines) == 1
    asyncio.run(scenario())


def test_draft_is_deleted_in_the_booking_transaction_and_old_expired_drafts_are_purged(bookable_hotel_room):
    async def scenario():
        store, drafts = PostgresBookingStore(APP_URL), PostgresBookingDraftRepository(APP_URL)
        products = await PostgresProductCatalog(APP_URL).get_products([bookable_hotel_room])
        product = products[bookable_hotel_room]
        using = max(product.available_from, date.today()) + timedelta(days=1)
        now = datetime.now(timezone.utc)
        draft = _draft([_line(bookable_hotel_room, using, nights=2)])
        await drafts.create(draft, copy_to_cart=[], now=now, max_live=5)

        # Ghi đơn lỗi (rollback): đơn nháp còn nguyên (R-CHK-05).
        with pytest.raises(RuntimeError):
            async with store.transaction() as tx:
                await tx.delete_draft(USER, draft.draft_id)
                raise RuntimeError("ghi đơn lỗi")
        assert await drafts.get(USER, draft.draft_id) is not None
        async with store.transaction() as tx:
            await tx.delete_draft("VP0000001", draft.draft_id)                  # không phải chủ: không xoá
        assert await drafts.get(USER, draft.draft_id) is not None
        async with store.transaction() as tx:
            await tx.insert(_booking(product, using))
            await tx.delete_draft(USER, draft.draft_id)
        assert await drafts.get(USER, draft.draft_id) is None

        old = _draft([_line(bookable_hotel_room, using, nights=1)], created=now - timedelta(days=3))
        fresh = _draft([_line(bookable_hotel_room, using, nights=1)], created=now - timedelta(hours=2))   # hết hạn < 1 ngày
        await drafts.adopt(old)
        await drafts.adopt(fresh)
        async with store.transaction() as tx:
            purged = await tx.purge_expired_drafts(now - timedelta(days=1))
        assert purged >= 1 and await drafts.get(USER, old.draft_id) is None
        assert await drafts.get(USER, fresh.draft_id) is not None               # còn để trang thanh toán báo "hết hạn"
    asyncio.run(scenario())


def test_booking_store_lists_own_bookings_newest_first_and_loads_a_page_in_order(bookable_hotel_room) -> None:
    async def scenario() -> None:
        catalog, store = PostgresProductCatalog(APP_URL), PostgresBookingStore(APP_URL)
        product = (await catalog.get_products([bookable_hotel_room]))[bookable_hotel_room]
        now = datetime.now(timezone.utc).replace(microsecond=0)
        using = product.available_from
        old = _booking(product, using, status=BookingStatus.CONFIRMED)
        old.created_at, old.hold_expires_at = now - timedelta(days=40), None
        new = _booking(product, using, status=BookingStatus.PENDING_PAYMENT)
        new.created_at = now - timedelta(days=1)
        for booking in (old, new):
            async with store.transaction() as tx:
                await tx.insert(booking)

        async with store.transaction() as tx:
            everything = await tx.list_overviews(USER, None)
            recent = await tx.list_overviews(USER, now - timedelta(days=7))
            nobody = await tx.list_overviews("VP0000001", now + timedelta(days=1))
            page = await tx.get_many([old.booking_id, "not-a-uuid", new.booking_id])
        assert [o.booking_id for o in everything] == [new.booking_id, old.booking_id]   # mới nhất trước
        assert [o.booking_id for o in recent] == [new.booking_id] and nobody == []
        first = everything[0]
        assert first.taxonomies == ("hotel",) and first.last_end_date == using + timedelta(days=2)   # trả phòng sau 2 đêm
        assert tab_of(first, now) is BookingTab.UPCOMING                                   # đang giữ chỗ
        assert [b.booking_id for b in page] == [old.booking_id, new.booking_id]            # đúng thứ tự yêu cầu, bỏ mã sai
        assert page[0].payment.status is PaymentStatus.OPEN and page[0].items[0].nights == 2
        assert page[0].total_amount == old.total_amount and page[0].travelers == []
    asyncio.run(scenario())
