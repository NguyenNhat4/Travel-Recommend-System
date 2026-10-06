"""Luồng giữ chỗ, thanh toán, thất bại, huỷ và đối soát (spec booking §6–§9) trên bản giả, không cần mạng."""
import asyncio
from datetime import date, timedelta

import pytest

from src.backend.app.application.booking import Contact, ItemDetail
from src.backend.app.application.booking.errors import (
    BookingAlreadyPaid, BookingNotCancellable, BookingNotFound, CartEmpty, DirectBookingOnly, LineRejected,
    PaymentUnavailable, PendingPaymentExists, ValidationFailed,
)
from src.backend.app.domain.booking.status import BookingStatus, PaymentStatus
from src.backend.tests.fakes.booking import HOTEL, PRINCIPAL, TICKET, USER, World, product

CONTACT = Contact("Nguyễn Minh Anh", "minh@example.vn", "0912345678")
run = asyncio.run


GOLF = "33333333-3333-3333-3333-333333333333"


async def hold(w: World, **kw):
    """Giữ chỗ cho một lần Đặt ngay gồm phòng khách sạn và vé tham quan (đơn nháp)."""
    await w.fill_cart(**kw)
    return await w.create(PRINCIPAL, CONTACT, await w.details())


async def cart_hold(w: World):
    """Giữ chỗ từ giỏ hàng: giỏ chỉ có vé tham quan (khách sạn, vé máy bay không vào giỏ)."""
    if not (await w.carts.get(USER)).lines:
        await w.cart.add(PRINCIPAL, product_id=TICKET, using_date=date(2026, 10, 15), quantity=2, nights=None)
    return await w.create(PRINCIPAL, CONTACT, await w.details())


def session_of(w: World, ref: str) -> str:
    return w.booking(ref).payment.checkout_session_id


# --- giỏ hàng -----------------------------------------------------------------------------------

def test_cart_adds_merges_and_computes_totals_and_tracks_add_to_cart():
    async def go():
        w = World()
        await w.cart.add(PRINCIPAL, product_id=TICKET, using_date=date(2026, 10, 15), quantity=1, nights=None)
        cart = await w.cart.add(PRINCIPAL, product_id=TICKET, using_date=date(2026, 10, 15), quantity=1, nights=None)
        assert cart["itemCount"] == 1 and cart["items"][0]["quantity"] == 2  # cộng dồn
        assert cart["items"][0]["lineTotal"] == 880_000 * 2 and cart["total"] == cart["subtotal"]
        assert cart["cdpUserId"] == USER
        return w
    w = run(go())
    assert [e.event_name for e in w.recorder.events] == ["add_to_cart", "add_to_cart"]


def test_cart_rejects_unknown_unavailable_and_out_of_range_products():
    async def go():
        w = World(products=[product(), product(TICKET, "attraction", available=False), product(GOLF, "golf", 2_600_000)])
        with pytest.raises(LineRejected) as e:
            await w.cart.add(PRINCIPAL, product_id=TICKET, using_date=date(2026, 10, 15), quantity=1, nights=None)
        assert e.value.code == "PRODUCT_UNAVAILABLE" and e.value.http_status == 409
        with pytest.raises(LineRejected) as e:
            await w.cart.add(PRINCIPAL, product_id=GOLF, using_date=date(2027, 6, 1), quantity=1, nights=None)
        assert e.value.code == "DATE_OUT_OF_RANGE" and e.value.http_status == 422
        from src.backend.app.application.booking.errors import ProductNotFound
        with pytest.raises(ProductNotFound):
            await w.cart.add(PRINCIPAL, product_id="nope", using_date=date(2026, 10, 15), quantity=1, nights=None)
        assert w.recorder.events == []  # thêm thất bại không ghi event
    run(go())


# --- Case 1: đặt chỗ thành công -----------------------------------------------------------------

def test_cart_rejects_hotels_and_flights_which_are_booked_directly():
    """R-DIR-01 (AC-BKG-15): khách sạn và vé máy bay không vào giỏ; giỏ không đổi, không ghi add_to_cart."""
    async def go():
        flight = "44444444-4444-4444-4444-444444444444"
        day = date(2026, 10, 15)
        w = World(products=[product(), product(flight, "flight", 634_000, available_from=day, available_to=day)])
        for pid, taxonomy in ((HOTEL, "hotel"), (flight, "flight")):
            with pytest.raises(DirectBookingOnly) as e:
                await w.cart.add(PRINCIPAL, product_id=pid, using_date=day, quantity=1, nights=1)
            assert (e.value.code, e.value.http_status) == ("DIRECT_BOOKING_ONLY", 422)
            assert e.value.details == {"productId": pid, "taxonomy": taxonomy}
        assert (await w.carts.get(USER)).lines == [] and w.recorder.events == []
    run(go())


def test_create_hold_returns_pending_payment_with_checkout_url_and_does_not_touch_cdp_or_cart():
    async def go():
        w = World()
        res = await hold(w)
        assert res["status"] == "PENDING_PAYMENT" and res["cancellableUntil"] is None
        assert res["holdExpiresAt"] == "2026-09-16T03:31:00Z"  # 30 phút + đệm 60 giây cho Stripe
        assert res["payment"]["status"] == "OPEN" and res["payment"]["checkoutUrl"].startswith("https://checkout.fake/")
        assert res["payment"]["amount"] == res["total"] == 3_400_000 * 3 + 2 * 880_000
        assert w.cdp.recorded == []                            # purchase chưa ghi
        assert [l.product_id for l in (await w.carts.get(USER)).lines] == [TICKET]   # vé tham quan nằm trong giỏ, phòng thì không
        assert w.basket.draft_id not in w.draft_repo.drafts    # đơn nháp đã thành đơn giữ chỗ (R-CHK-05)
        return w
    run(go())


def test_successful_payment_confirms_records_purchase_and_clears_cart():
    async def go():
        w = World()
        res = await hold(w)
        ref = res["referenceCode"]
        await w.handler(w.gateway.pay(session_of(w, ref)))
        booking = w.booking(ref)
        assert booking.status is BookingStatus.CONFIRMED and booking.payment.status is PaymentStatus.SUCCEEDED
        assert [e.booking_item_id for e in w.cdp.recorded[0]] == [i.booking_item_id for i in booking.items]
        assert {e.event_group_id for e in w.cdp.recorded[0]} == {booking.event_group_id}
        assert (await w.carts.get(USER)).lines == []
        shown = await w.get(PRINCIPAL, ref)
        assert shown["status"] == "CONFIRMED" and shown["payment"]["checkoutUrl"] is None
        assert shown["cancellableUntil"] == "2026-10-13T17:00:00Z"
    run(go())


def test_duplicate_webhook_changes_nothing_and_records_no_second_purchase():
    async def go():
        w = World()
        ref = (await hold(w))["referenceCode"]
        event = w.gateway.pay(session_of(w, ref))
        await w.handler(event); await w.handler(event)
        assert len(w.cdp.recorded) == 1 and w.booking(ref).status is BookingStatus.CONFIRMED
    run(go())


def test_cdp_down_keeps_payment_succeeded_and_retry_confirms_without_cancelling_events():
    async def go():
        w = World()
        ref = (await hold(w))["referenceCode"]
        event = w.gateway.pay(session_of(w, ref))
        w.cdp.down = True
        from src.backend.app.application.ports.cdp_client import CdpUnavailableError
        with pytest.raises(CdpUnavailableError):
            await w.handler(event)
        b = w.booking(ref)
        assert (b.status, b.payment.status) == (BookingStatus.PENDING_PAYMENT, PaymentStatus.SUCCEEDED)
        assert w.cdp.cancelled == []                          # tiền đã thu: không huỷ event
        w.cdp.down = False
        await w.handler(event)                                # Stripe gửi lại webhook
        assert w.booking(ref).status is BookingStatus.CONFIRMED
    run(go())


def test_reconcile_finishes_a_paid_but_unconfirmed_booking():
    async def go():
        w = World()
        ref = (await hold(w))["referenceCode"]
        event = w.gateway.pay(session_of(w, ref))
        w.cdp.down = True
        with pytest.raises(Exception):
            await w.handler(event)
        w.cdp.down = False
        assert await w.reconciler() == 1
        assert w.booking(ref).status is BookingStatus.CONFIRMED
    run(go())


def test_wrong_amount_is_refunded_and_booking_fails():
    async def go():
        w = World()
        ref = (await hold(w))["referenceCode"]
        await w.handler(w.gateway.pay(session_of(w, ref), amount=1))
        b = w.booking(ref)
        assert b.status is BookingStatus.PAYMENT_FAILED and b.payment.status is PaymentStatus.REFUNDED
        assert w.cdp.recorded == [] and (await w.get(PRINCIPAL, ref))["payment"]["failureReason"] == "AMOUNT_MISMATCH"
    run(go())


# --- kiểm tra khi tạo đơn ----------------------------------------------------------------------

def test_create_rejects_empty_cart_price_change_unavailable_and_unknown_item():
    async def go():
        w = World()
        with pytest.raises(CartEmpty):
            await w.create(PRINCIPAL, CONTACT, [])
        await w.fill_cart()
        with pytest.raises(ValidationFailed) as unknown:
            await w.create(PRINCIPAL, CONTACT, [ItemDetail("lạ")])
        assert {f["reason"] for f in unknown.value.details["fields"]} == {"ITEM_DETAIL_UNKNOWN", "ITEM_DETAIL_MISSING"}
        details = await w.details()
        w.catalog.products[HOTEL].unit_price = 3_900_000
        with pytest.raises(LineRejected) as e:
            await w.create(PRINCIPAL, CONTACT, details)
        assert e.value.code == "PRICE_CHANGED" and e.value.details["newPrice"] == 3_900_000
        w.catalog.products[HOTEL].available = False
        with pytest.raises(LineRejected) as e:
            await w.create(PRINCIPAL, CONTACT, details)
        assert e.value.code == "PRODUCT_UNAVAILABLE"
        assert w.store.bookings == {} and w.gateway.sessions == {}   # không tạo phiên Stripe khi kiểm giỏ hỏng
    run(go())


def test_item_details_are_stored_per_item():
    async def go():
        w = World()
        await w.fill_cart()
        line = (await w.lines())[0]
        details = [ItemDetail(line.cart_item_id, ["An"], "Tầng cao"), *(await w.details())[1:]]
        res = await w.create(PRINCIPAL, CONTACT, details)
        first = res["groups"][0]["items"][0]
        assert first["guestNames"] == ["An"] and first["specialRequest"] == "Tầng cao"
    run(go())


def test_stripe_timeout_creates_no_booking_and_keeps_cart():
    async def go():
        w = World()
        await w.fill_cart()
        w.gateway.mode = "timeout"
        with pytest.raises(PaymentUnavailable) as e:
            await w.create(PRINCIPAL, CONTACT, await w.details())
        assert e.value.http_status == 503 and e.value.retryable
        assert w.store.bookings == {} and len(await w.lines()) == 2   # đơn nháp còn nguyên để bấm lại
    run(go())


def test_db_failure_after_session_created_closes_the_stripe_session():
    async def go():
        w = World()
        await w.fill_cart()
        w.store.fail_insert = True
        with pytest.raises(RuntimeError):
            await w.create(PRINCIPAL, CONTACT, await w.details())
        (session,) = w.gateway.sessions.values()
        assert session["status"] == "expired"
    run(go())


# --- Case 2: thanh toán thất bại ----------------------------------------------------------------

def test_two_declines_keep_holding_third_fails_booking_and_closes_session():
    async def go():
        w = World()
        ref = (await hold(w))["referenceCode"]
        sid = session_of(w, ref)
        await w.handler(w.gateway.decline(sid, "insufficient_funds"))
        shown = await w.get(PRINCIPAL, ref)
        assert shown["status"] == "PENDING_PAYMENT" and shown["payment"]["failedAttempts"] == 1
        assert shown["payment"]["failureReason"] == "INSUFFICIENT_FUNDS"
        await w.handler(w.gateway.decline(sid))
        assert w.booking(ref).status is BookingStatus.PENDING_PAYMENT
        await w.handler(w.gateway.decline(sid))
        shown = await w.get(PRINCIPAL, ref)
        assert (shown["status"], shown["payment"]["status"], shown["payment"]["failureReason"]) == (
            "PAYMENT_FAILED", "FAILED", "TOO_MANY_ATTEMPTS")
        assert w.gateway.sessions[sid]["status"] == "expired" and w.cdp.recorded == []
        # Không hoàn thành thanh toán: vé tham quan nằm lại trong giỏ, phòng khách sạn thì không (AC-BKG-02, AC-BKG-16).
        assert [l.product_id for l in (await w.carts.get(USER)).lines] == [TICKET]
    run(go())


def test_money_arriving_for_a_closed_booking_is_refunded_automatically():
    async def go():
        w = World()
        ref = (await hold(w))["referenceCode"]
        sid = session_of(w, ref)
        for _ in range(3):
            await w.handler(w.gateway.decline(sid))
        await w.handler(w.gateway.pay(sid))                   # phiên chưa kịp đóng, khách vẫn trả được
        b = w.booking(ref)
        assert b.status is BookingStatus.PAYMENT_FAILED and b.payment.status is PaymentStatus.REFUNDED
        assert w.cdp.recorded == []
    run(go())


# --- Case 3: giữ chỗ ---------------------------------------------------------------------------

def test_second_hold_while_pending_is_rejected_with_reference_code():
    async def go():
        w = World()
        await w.fill_cart()
        details = await w.details()
        first = await w.create(PRINCIPAL, CONTACT, details)
        with pytest.raises(PendingPaymentExists) as e:
            await w.create(PRINCIPAL, CONTACT, details)
        assert e.value.http_status == 409 and e.value.details["referenceCode"] == first["referenceCode"]
        assert len(w.gateway.sessions) == 1
    run(go())


def test_expired_hold_is_released_on_next_attempt_without_waiting_for_webhook():
    async def go():
        w = World()
        first = (await cart_hold(w))["referenceCode"]
        w.clock.advance(minutes=32)
        second = await cart_hold(w)                           # giỏ còn nguyên nên bấm Thanh toán lại được
        assert w.booking(first).status is BookingStatus.EXPIRED and second["status"] == "PENDING_PAYMENT"
    run(go())


def test_expired_webhook_and_reconcile_expire_the_booking_and_keep_cart():
    async def go():
        w = World()
        ref = (await cart_hold(w))["referenceCode"]
        await w.handler(w.gateway.expire_event(session_of(w, ref)))
        b = w.booking(ref)
        assert (b.status, b.payment.status) == (BookingStatus.EXPIRED, PaymentStatus.EXPIRED)
        assert len((await w.carts.get(USER)).lines) == 1
        ref2 = (await cart_hold(w))["referenceCode"]                         # bấm lại được sau khi hết hạn
        w.clock.advance(minutes=45)                                          # webhook lỡ
        assert await w.reconciler() == 1 and w.booking(ref2).status is BookingStatus.EXPIRED
    run(go())


def test_reconcile_confirms_when_stripe_says_paid_but_webhook_was_lost():
    async def go():
        w = World()
        ref = (await hold(w))["referenceCode"]
        w.gateway.pay(session_of(w, ref))                     # Stripe đã thu tiền, webhook không tới
        w.clock.advance(minutes=45)
        await w.reconciler()
        assert w.booking(ref).status is BookingStatus.CONFIRMED and len(w.cdp.recorded) == 1
    run(go())


# --- Case 4: huỷ -------------------------------------------------------------------------------

def test_cancel_before_payment_closes_session_and_cannot_be_paid_afterwards():
    async def go():
        w = World()
        ref = (await hold(w))["referenceCode"]
        res = await w.cancel(PRINCIPAL, ref, "đổi kế hoạch")
        assert res["status"] == "CANCELLED" and res["cancellation"]["refundAmount"] == 0
        assert w.gateway.sessions[session_of(w, ref)]["status"] == "expired"
        again = await w.cancel(PRINCIPAL, ref, None)         # huỷ lặp lại trả kết quả cũ
        assert again["status"] == "CANCELLED" and w.gateway.calls.count("expire_checkout_session") == 1
    run(go())


def test_cancel_paid_in_time_refunds_full_once_and_cancels_purchase_events():
    async def go():
        w = World()
        res = await hold(w)
        ref = res["referenceCode"]
        await w.handler(w.gateway.pay(session_of(w, ref)))
        out = await w.cancel(PRINCIPAL, ref, None)
        assert out["status"] == "CANCELLED" and out["payment"]["status"] == "REFUNDED"
        assert out["payment"]["refundedAmount"] == res["total"] == out["cancellation"]["refundAmount"]
        assert len(w.cdp.cancelled) == 1 and w.booking(ref).purchase_events_cancelled_at is not None
        await w.cancel(PRINCIPAL, ref, None)
        assert w.gateway.calls.count("create_refund") == 1    # không hoàn hai lần
    run(go())


def test_cancel_too_late_is_rejected_with_reason_and_deadline():
    async def go():
        w = World()
        ref = (await hold(w, using=date(2026, 9, 17)))["referenceCode"]   # ngày mai
        await w.handler(w.gateway.pay(session_of(w, ref)))
        with pytest.raises(BookingNotCancellable) as e:
            await w.cancel(PRINCIPAL, ref, None)
        assert e.value.http_status == 409 and e.value.details["reason"] == "TOO_LATE"
        assert e.value.details["cancellableUntil"] == "2026-09-15T17:00:00Z"
        assert w.booking(ref).status is BookingStatus.CONFIRMED and w.gateway.calls.count("create_refund") == 0
    run(go())


def test_cancel_closed_booking_and_foreign_booking():
    async def go():
        w = World()
        ref = (await hold(w))["referenceCode"]
        await w.handler(w.gateway.expire_event(session_of(w, ref)))
        with pytest.raises(BookingNotCancellable) as e:
            await w.cancel(PRINCIPAL, ref, None)
        assert e.value.details["reason"] == "NOT_ACTIVE"
        from src.backend.app.application.auth.principal import AuthPrincipal
        other = AuthPrincipal(user_id="u-2", cdp_user_id="VP9", email="x@y.vn")
        with pytest.raises(BookingNotFound):
            await w.cancel(other, ref, None)
        with pytest.raises(BookingNotFound):
            await w.get(other, ref)                            # người khác: 404, không lộ mã tồn tại
    run(go())


def test_cancel_unpaid_when_stripe_already_collected_reports_already_paid():
    async def go():
        w = World()
        ref = (await hold(w))["referenceCode"]
        w.gateway.pay(session_of(w, ref))                      # khách vừa trả, webhook chưa tới
        with pytest.raises(BookingAlreadyPaid):
            await w.cancel(PRINCIPAL, ref, None)
        assert w.booking(ref).status is BookingStatus.PENDING_PAYMENT
    run(go())


def test_refund_failure_at_stripe_is_retried_by_reconcile_and_events_still_cancelled():
    async def go():
        w = World()
        ref = (await hold(w))["referenceCode"]
        await w.handler(w.gateway.pay(session_of(w, ref)))
        w.gateway.mode = "timeout"
        out = await w.cancel(PRINCIPAL, ref, None)
        assert out["status"] == "CANCELLED" and out["payment"]["status"] == "REFUND_PENDING"
        w.gateway.mode = "ok"
        await w.reconciler()
        assert w.booking(ref).payment.status is PaymentStatus.REFUNDED
    run(go())
