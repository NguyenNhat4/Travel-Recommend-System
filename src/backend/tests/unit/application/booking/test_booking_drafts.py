"""Đặt trực tiếp qua đơn nháp, chép vào giỏ, khách chưa đăng nhập và gộp (spec dat-truc-tiep-theo-don-nhap.md) trên bản giả."""
import asyncio
from datetime import date

import pytest

from src.backend.app.application.auth.errors import Unauthenticated
from src.backend.app.application.booking import CartOwner, Contact, DraftItemRequest, ItemDetail
from src.backend.app.application.booking.errors import (
    BookingDraftExpired, BookingDraftNotFound, BookingNotFound, CartEmpty, DirectBookingOnly, LineRejected,
    ProductNotFound, ValidationFailed,
)
from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.domain.booking import DraftPolicy, is_cart_eligible
from src.backend.app.domain.booking.party import Guests
from src.backend.app.domain.booking.status import BookingStatus
from src.backend.tests.fakes.booking import GUEST, HOTEL, NOW, PRINCIPAL, TICKET, USER, World, product

CONTACT = Contact("Nguyễn Minh Anh", "minh@example.vn", "0912345678")
DAY = date(2026, 10, 15)
COMBO, FLIGHT = "55555555-5555-5555-5555-555555555555", "44444444-4444-4444-4444-444444444444"
GUEST_OWNER = CartOwner.guest(GUEST)
OTHER = AuthPrincipal(user_id="u-2", cdp_user_id="VP0000002", email="other@example.vn")
run = asyncio.run


def world() -> World:
    return World(products=[
        product(), product(TICKET, "attraction", 880_000), product(COMBO, "combo", 5_990_000),
        product(FLIGHT, "flight", 634_000, available_from=DAY, available_to=DAY)])


def hotel_item(**kw) -> DraftItemRequest:
    return DraftItemRequest(HOTEL, DAY, kw.get("quantity", 1), kw.get("nights", 2), kw.get("guests"))


def ticket_item(guests=Guests(2, 0)) -> DraftItemRequest:
    return DraftItemRequest(TICKET, DAY, None, None, guests)


async def details_of(w: World, draft: dict) -> list[ItemDetail]:
    out = []
    for item in draft["items"]:
        taxonomy = item["product"]["taxonomy"]
        names = ["Nguyễn Minh Anh"] * (item["quantity"] if taxonomy == "flight" else 1 if taxonomy == "hotel" else 0)
        out.append(ItemDetail(item["cartItemId"], names))
    return out


# --- luật theo loại sản phẩm, hiệu lực ----------------------------------------------------------------

def test_only_tours_and_utilities_are_cart_eligible_and_draft_lives_thirty_minutes():
    assert [is_cart_eligible(t) for t in ("hotel", "flight", "attraction", "golf", "combo")] == [False, False, True, True, True]
    assert DraftPolicy().expires_at(NOW).isoformat() == "2026-09-16T03:30:00+00:00"
    with pytest.raises(ValueError):
        DraftPolicy(0)


# --- tạo đơn nháp ---------------------------------------------------------------------------------------

def test_book_now_on_a_hotel_creates_a_draft_with_only_that_room_and_leaves_the_cart_alone():
    async def go():
        w = world()
        await w.cart.add(PRINCIPAL, product_id=COMBO, using_date=DAY, quantity=1, nights=None)   # giỏ đang có hàng
        draft = await w.drafts.create(PRINCIPAL, items=[hotel_item()])
        assert draft["itemCount"] == 1 and draft["items"][0]["product"]["productId"] == HOTEL
        assert draft["total"] == 3_400_000 * 2 and draft["cdpUserId"] == USER
        assert draft["expiresAt"] == "2026-09-16T03:30:00Z" and "rejectedItems" not in draft
        assert [l.product_id for l in (await w.carts.get(USER)).lines] == [COMBO]       # phòng không vào giỏ
        # Thanh toán đơn nháp chỉ gồm phòng, không kèm combo trong giỏ (R-CHK-01).
        held = await w.create_hold(PRINCIPAL, CONTACT, await details_of(w, draft), draft_id=draft["draftId"])
        assert held["total"] == 3_400_000 * 2
        assert [i["product"]["productId"] for g in held["groups"] for i in g["items"]] == [HOTEL]
        assert await w.draft_repo.get(USER, draft["draftId"]) is None                   # R-CHK-05
        return w
    w = run(go())
    assert [(e.event_name, e.product_id) for e in w.recorder.events] == [("add_to_cart", COMBO), ("add_to_cart", HOTEL)]


def test_book_now_copies_tours_into_the_cart_once_and_never_overwrites_an_existing_cart_item():
    async def go():
        w = world()
        await w.cart.add(PRINCIPAL, product_id=TICKET, using_date=DAY, quantity=None, nights=None, guests=Guests(1, 0))
        first = await w.drafts.create(PRINCIPAL, items=[hotel_item(), ticket_item(Guests(2, 1)), DraftItemRequest(COMBO, DAY, 1)])
        await w.drafts.create(PRINCIPAL, items=[DraftItemRequest(COMBO, DAY, 2)])         # bấm Đặt ngay lần hai
        lines = {l.product_id: l for l in (await w.carts.get(USER)).lines}
        assert set(lines) == {TICKET, COMBO}                                              # không có phòng (R-CPY-01)
        assert (lines[TICKET].adults, lines[TICKET].children) == (1, 0)                   # mục giỏ có sẵn giữ nguyên (R-CPY-02)
        assert lines[COMBO].quantity == 1                                                 # không cộng dồn, không ghi đè
        # Sửa mục của đơn nháp không đổi mục giỏ đã chép (R-CPY-04).
        combo = next(i for i in first["items"] if i["product"]["productId"] == COMBO)
        patched = await w.drafts.update_item(PRINCIPAL, first["draftId"], combo["cartItemId"], using_date=None,
                                             quantity=3, nights=None, nights_given=False)
        assert next(i for i in patched["items"] if i["product"]["productId"] == COMBO)["quantity"] == 3
        assert {l.product_id: l.quantity for l in (await w.carts.get(USER)).lines}[COMBO] == 1
    run(go())


def test_draft_rejects_duplicates_empty_and_invalid_items_and_creates_nothing():
    async def go():
        w = world()
        with pytest.raises(ValidationFailed) as e:
            await w.drafts.create(PRINCIPAL, items=[ticket_item(), ticket_item()])
        assert e.value.details["fields"][0]["reason"] == "DUPLICATE_ITEM" and e.value.details["fields"][0]["field"] == "items[1]"
        with pytest.raises(ValidationFailed):
            await w.drafts.create(PRINCIPAL, items=[])
        with pytest.raises(ProductNotFound):
            await w.drafts.create(PRINCIPAL, items=[hotel_item(), DraftItemRequest("nope", DAY, 1)])
        with pytest.raises(LineRejected) as e:
            await w.drafts.create(PRINCIPAL, items=[DraftItemRequest(FLIGHT, date(2026, 10, 16), 1)])
        assert e.value.code == "DATE_OUT_OF_RANGE"
        assert w.draft_repo.drafts == {} and (await w.carts.get(USER)).lines == [] and w.recorder.events == []
    run(go())


def test_allow_partial_skips_unbookable_items_and_fails_only_when_nothing_is_left():
    async def go():
        w = world()
        w.catalog.products[TICKET].available = False
        draft = await w.drafts.create(PRINCIPAL, allow_partial=True, items=[
            hotel_item(), ticket_item(), DraftItemRequest("nope", DAY, 1)])
        assert [i["product"]["productId"] for i in draft["items"]] == [HOTEL]
        assert [(r["productId"], r["code"]) for r in draft["rejectedItems"]] == [
            (TICKET, "PRODUCT_UNAVAILABLE"), ("nope", "PRODUCT_NOT_FOUND")]
        assert all(r["message"] and r["usingDate"] == "2026-10-15" for r in draft["rejectedItems"])
        with pytest.raises(LineRejected) as e:
            await w.drafts.create(PRINCIPAL, allow_partial=True, items=[ticket_item()])
        assert e.value.code == "PRODUCT_UNAVAILABLE" and e.value.details["rejectedItems"][0]["productId"] == TICKET
    run(go())


def test_at_most_five_live_drafts_and_expired_ones_are_swept_on_create():
    async def go():
        w = world()
        ids = []
        for _ in range(6):
            ids.append((await w.drafts.create(PRINCIPAL, items=[hotel_item()]))["draftId"])
            w.clock.advance(seconds=1)
        assert set(w.draft_repo.drafts) == set(ids[1:])                                  # cái cũ nhất bị bỏ (R-DRF-07)
        w.clock.advance(minutes=31)
        last = (await w.drafts.create(PRINCIPAL, items=[hotel_item()]))["draftId"]
        assert set(w.draft_repo.drafts) == {last}
    run(go())


# --- đọc, hết hạn, quyền -------------------------------------------------------------------------------

def test_draft_reads_current_price_and_checkout_rejects_until_customer_has_seen_it():
    """AC-BKG-13."""
    async def go():
        w = world()
        draft = await w.drafts.create(PRINCIPAL, items=[hotel_item()])
        w.catalog.products[HOTEL].unit_price = 3_900_000
        shown = await w.drafts.get(PRINCIPAL, draft["draftId"])
        assert shown["items"][0]["product"]["unitPrice"] == 3_900_000 and shown["total"] == 3_900_000 * 2
        details = await details_of(w, draft)
        with pytest.raises(LineRejected) as e:
            await w.create_hold(PRINCIPAL, CONTACT, details, draft_id=draft["draftId"])
        assert e.value.code == "PRICE_CHANGED" and (e.value.details["oldPrice"], e.value.details["newPrice"]) == (3_400_000, 3_900_000)
        assert w.store.bookings == {} and w.gateway.sessions == {}
        item = shown["items"][0]
        await w.drafts.update_item(PRINCIPAL, draft["draftId"], item["cartItemId"], using_date=None, quantity=1,
                                   nights=None, nights_given=False)                      # khách đã thấy giá mới
        held = await w.create_hold(PRINCIPAL, CONTACT, details, draft_id=draft["draftId"])
        assert held["total"] == 3_900_000 * 2
    run(go())


def test_expired_draft_cannot_be_read_or_paid_and_tells_which_items_remain_in_the_cart():
    """AC-BKG-14, R-DRF-12, R-DRF-20…22."""
    async def go():
        w = world()
        draft = await w.drafts.create(PRINCIPAL, items=[hotel_item(), ticket_item()])
        details = await details_of(w, draft)
        w.clock.advance(minutes=30)
        with pytest.raises(BookingDraftExpired) as e:
            await w.drafts.get(PRINCIPAL, draft["draftId"])
        assert e.value.http_status == 410 and e.value.details["draftId"] == draft["draftId"]
        assert {(i["taxonomy"], i["inCart"]) for i in e.value.details["items"]} == {("hotel", False), ("attraction", True)}
        with pytest.raises(BookingDraftExpired):
            await w.create_hold(PRINCIPAL, CONTACT, details, draft_id=draft["draftId"])
        with pytest.raises(BookingDraftExpired):
            await w.drafts.update_item(PRINCIPAL, draft["draftId"], draft["items"][0]["cartItemId"], using_date=None,
                                       quantity=1, nights=None, nights_given=False)
        assert w.store.bookings == {}
    run(go())


def test_removing_an_item_keeps_the_rest_and_removing_the_last_one_deletes_the_draft():
    """R-DRF-14: bỏ mục khỏi lần đặt; mục giỏ đã chép không đổi; không để lại đơn nháp rỗng."""
    async def go():
        from src.backend.app.application.booking.errors import CartItemNotFound
        w = world()
        draft = await w.drafts.create(PRINCIPAL, items=[hotel_item(), ticket_item()])
        ids = {i["product"]["productId"]: i["cartItemId"] for i in draft["items"]}
        left = await w.drafts.remove_item(PRINCIPAL, draft["draftId"], ids[TICKET])
        assert [i["product"]["productId"] for i in left["items"]] == [HOTEL] and left["total"] == 3_400_000 * 2
        assert [l.product_id for l in (await w.carts.get(USER)).lines] == [TICKET]     # mục giỏ đã chép vẫn còn
        with pytest.raises(CartItemNotFound):
            await w.drafts.remove_item(PRINCIPAL, draft["draftId"], ids[TICKET])
        with pytest.raises(BookingDraftNotFound):
            await w.drafts.remove_item(OTHER, draft["draftId"], ids[HOTEL])
        gone = await w.drafts.remove_item(PRINCIPAL, draft["draftId"], ids[HOTEL])
        assert gone["items"] == [] and gone["total"] == 0
        with pytest.raises(BookingDraftNotFound):
            await w.drafts.get(PRINCIPAL, draft["draftId"])
    run(go())


def test_another_users_draft_and_unknown_draft_are_both_not_found():
    async def go():
        w = world()
        draft = await w.drafts.create(PRINCIPAL, items=[hotel_item()])
        for draft_id in (draft["draftId"], "không-có"):
            with pytest.raises(BookingDraftNotFound) as e:
                await w.drafts.get(OTHER, draft_id)
            assert e.value.http_status == 404
        with pytest.raises(BookingDraftNotFound):
            await w.create_hold(OTHER, CONTACT, await details_of(w, draft), draft_id=draft["draftId"])
        with pytest.raises(BookingDraftNotFound):                                         # đơn nháp của khách cũng không lộ
            await w.drafts.get(GUEST_OWNER, draft["draftId"])
    run(go())


def test_empty_cart_checkout_is_unchanged_when_no_draft_is_given():
    async def go():
        w = world()
        await w.drafts.create(PRINCIPAL, items=[hotel_item()])
        with pytest.raises(CartEmpty):                        # đơn nháp có sẵn không tự biến thành nguồn thanh toán
            await w.create_hold(PRINCIPAL, CONTACT, [])
    run(go())


# --- không hoàn thành thanh toán, đặt lại ----------------------------------------------------------------

def test_unfinished_payment_leaves_tours_in_the_cart_and_success_removes_them():
    """AC-BKG-16: hết hạn giữ chỗ thì vé tham quan nằm lại trong giỏ, phòng thì không; thanh toán xong thì vé rời giỏ."""
    async def go():
        w = world()
        draft = await w.drafts.create(PRINCIPAL, items=[hotel_item(), ticket_item()])
        held = await w.create_hold(PRINCIPAL, CONTACT, await details_of(w, draft), draft_id=draft["draftId"])
        session = w.booking(held["referenceCode"]).payment.checkout_session_id
        await w.handler(w.gateway.expire_event(session))
        assert w.booking(held["referenceCode"]).status is BookingStatus.EXPIRED
        assert [l.product_id for l in (await w.carts.get(USER)).lines] == [TICKET]
        # Đặt lại (R-RBK): đơn nháp mới từ các mục của đơn hết hạn, giá hiện tại.
        w.catalog.products[HOTEL].unit_price = 3_600_000
        again = await w.drafts.create(PRINCIPAL, from_booking=held["referenceCode"])
        assert {i["product"]["productId"] for i in again["items"]} == {HOTEL, TICKET}
        assert again["total"] == 3_600_000 * 2 + 2 * 880_000
        assert len((await w.carts.get(USER)).lines) == 1                                  # không chép trùng vào giỏ
        paid = await w.create_hold(PRINCIPAL, CONTACT, await details_of(w, again), draft_id=again["draftId"])
        await w.handler(w.gateway.pay(w.booking(paid["referenceCode"]).payment.checkout_session_id))
        assert w.booking(paid["referenceCode"]).status is BookingStatus.CONFIRMED
        assert (await w.carts.get(USER)).lines == []                                      # R-CPY-05
    run(go())


def test_rebook_needs_an_own_failed_or_expired_booking_and_drops_items_no_longer_sold():
    async def go():
        w = world()
        draft = await w.drafts.create(PRINCIPAL, items=[hotel_item(), ticket_item()])
        held = await w.create_hold(PRINCIPAL, CONTACT, await details_of(w, draft), draft_id=draft["draftId"])
        ref = held["referenceCode"]
        with pytest.raises(ValidationFailed) as e:                                        # còn đang giữ chỗ
            await w.drafts.create(PRINCIPAL, from_booking=ref)
        assert e.value.details["fields"][0] == {
            "field": "fromBooking", "reason": "NOT_REBOOKABLE", "message": "Đơn này không đặt lại được."}
        with pytest.raises(BookingNotFound):
            await w.drafts.create(OTHER, from_booking=ref)
        with pytest.raises(Unauthenticated):
            await w.drafts.create(GUEST_OWNER, from_booking=ref)
        w.clock.advance(minutes=32)                           # hết hạn giữ chỗ, webhook chưa tới: tự đối soát rồi đặt lại
        w.catalog.products[TICKET].available = False
        again = await w.drafts.create(PRINCIPAL, from_booking=ref)
        assert w.booking(ref).status is BookingStatus.EXPIRED
        assert [i["product"]["productId"] for i in again["items"]] == [HOTEL]
        assert [r["productId"] for r in again["rejectedItems"]] == [TICKET]
    run(go())


# --- khách chưa đăng nhập ---------------------------------------------------------------------------------

def test_guest_uses_cart_and_book_now_without_any_cdp_event_and_gets_null_identity():
    """AC-BKG-17 (phần trước khi đăng nhập), R-GST-10…13."""
    async def go():
        w = world()
        cart = await w.cart.add(GUEST_OWNER, product_id=TICKET, using_date=DAY, quantity=None, nights=None, guests=Guests(2, 0))
        assert cart["cdpUserId"] is None and cart["itemCount"] == 1
        with pytest.raises(DirectBookingOnly):
            await w.cart.add(GUEST_OWNER, product_id=HOTEL, using_date=DAY, quantity=1, nights=1)
        draft = await w.drafts.create(GUEST_OWNER, items=[hotel_item(), DraftItemRequest(COMBO, DAY, 1)])
        assert draft["cdpUserId"] is None and draft["itemCount"] == 2
        assert {l.product_id for l in (await w.guest_carts.get(GUEST)).lines} == {TICKET, COMBO}
        assert (await w.drafts.get(GUEST_OWNER, draft["draftId"]))["total"] == draft["total"]
        with pytest.raises(BookingDraftNotFound):                                         # phiên khách khác không đọc được
            await w.drafts.get(CartOwner.guest("g_" + "b" * 22), draft["draftId"])
        with pytest.raises(BookingDraftNotFound):                                         # người đã đăng nhập cũng không
            await w.drafts.get(PRINCIPAL, draft["draftId"])
        assert (await w.carts.get(USER)).lines == [] and w.draft_repo.drafts == {}        # không ghi gì vào kho của tài khoản
        return w
    w = run(go())
    assert w.recorder.events == []


def test_guest_cart_is_capped_at_twenty_items():
    async def go():
        products = [product(f"{i:08d}-0000-0000-0000-000000000000", "attraction", 100_000) for i in range(1, 22)]
        w = World(products=products)
        for p in products[:20]:
            await w.cart.add(GUEST_OWNER, product_id=p.product_id, using_date=DAY, quantity=1, nights=None)
        with pytest.raises(ValidationFailed) as e:
            await w.cart.add(GUEST_OWNER, product_id=products[20].product_id, using_date=DAY, quantity=1, nights=None)
        assert e.value.details["fields"][0]["reason"] == "CART_FULL"
        # Mục đã có trong giỏ vẫn cộng dồn được; người đã đăng nhập không bị giới hạn này.
        await w.cart.add(GUEST_OWNER, product_id=products[0].product_id, using_date=DAY, quantity=1, nights=None)
    run(go())


# --- gộp khi đăng nhập ----------------------------------------------------------------------------------

def test_login_merges_guest_cart_and_live_drafts_keeps_one_of_each_duplicate_and_tracks_once():
    """R-MRG-01…05, Q4c, Q4d."""
    async def go():
        w = world()
        await w.cart.add(PRINCIPAL, product_id=TICKET, using_date=DAY, quantity=None, nights=None, guests=Guests(1, 0))
        w.recorder.events.clear()
        await w.cart.add(GUEST_OWNER, product_id=TICKET, using_date=DAY, quantity=None, nights=None, guests=Guests(4, 0))
        await w.cart.add(GUEST_OWNER, product_id=COMBO, using_date=DAY, quantity=1, nights=None)
        stale = await w.drafts.create(GUEST_OWNER, items=[DraftItemRequest(FLIGHT, DAY, 1)])
        w.clock.advance(minutes=31)                                                       # đơn nháp này đã hết hạn
        live = await w.drafts.create(GUEST_OWNER, items=[hotel_item(), DraftItemRequest(COMBO, DAY, 1)])

        result = await w.merge(PRINCIPAL, GUEST)
        assert result == {"mergedCartItems": 1, "skippedDuplicates": 1, "mergedDrafts": 1}
        lines = {l.product_id: l for l in (await w.carts.get(USER)).lines}
        assert set(lines) == {TICKET, COMBO} and lines[TICKET].adults == 1               # trùng: giữ mục của tài khoản
        moved = await w.drafts.get(PRINCIPAL, live["draftId"])                            # cùng draftId, cùng hạn
        assert moved["expiresAt"] == live["expiresAt"] and moved["cdpUserId"] == USER
        with pytest.raises(BookingDraftNotFound):
            await w.drafts.get(PRINCIPAL, stale["draftId"])
        assert (await w.guest_store.export(GUEST))[1] == []                               # Redis của khách đã xoá
        assert (await w.guest_carts.get(GUEST)).lines == []
        # Mỗi cặp (sản phẩm, ngày) thực sự vào tài khoản ghi một add_to_cart; mục trùng bị bỏ thì không ghi.
        assert sorted(e.product_id for e in w.recorder.events) == sorted([COMBO, HOTEL])
        assert all(e.event_name == "add_to_cart" and e.cdp_user_id == USER for e in w.recorder.events)
        assert await w.merge(PRINCIPAL, GUEST) == {"mergedCartItems": 0, "skippedDuplicates": 0, "mergedDrafts": 0}
        # Đơn nháp đã chuyển thanh toán được ngay bằng tài khoản.
        held = await w.create_hold(PRINCIPAL, CONTACT, await details_of(w, moved), draft_id=live["draftId"])
        assert held["status"] == "PENDING_PAYMENT"
    run(go())


def test_merge_rejects_a_malformed_guest_id():
    async def go():
        w = world()
        with pytest.raises(ValidationFailed):
            await w.merge(PRINCIPAL, "VP0000002")
    run(go())
