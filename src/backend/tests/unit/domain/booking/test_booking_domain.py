"""Máy trạng thái, chính sách huỷ, giữ chỗ và bảng lỗi thẻ (spec booking §5, §9, §10.2)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from src.backend.app.domain.booking import (
    Booking, BookingItem, BookingStatus, HoldPolicy, InvalidTransition, Payment, PaymentStatus, cancellable_until,
    check_product, decide_cancellation, failure_reason_from_stripe, line_total, new_reference_code,
)
from src.backend.app.domain.booking.cancellation import CancelDecision
from src.backend.tests.fakes.booking import NOW, product

UTC = timezone.utc


def booking(status=BookingStatus.PENDING_PAYMENT, pay=PaymentStatus.OPEN, using=date(2026, 10, 15)) -> Booking:
    item = BookingItem("bi", "p", "hotel", "Phòng", 1_000_000, 1, using, nights=2)
    return Booking("b", "VOTA-20260916-ABCD", "VP1", "OFF1", "A", "a@b.vn", "0912345678", NOW, [item], status=status,
                   hold_expires_at=NOW + timedelta(minutes=31),
                   payment=Payment("pay", "fake", 2_000_000, status=pay, checkout_session_id="cs", checkout_url="u"))


def test_line_total_multiplies_nights_only_for_hotels():
    assert line_total("hotel", 1000, 2, 3) == 6000
    assert line_total("attraction", 1000, 2, 3) == 2000  # nights bị bỏ qua
    assert line_total("hotel", 1000, 1, None) == 1000


def test_hold_policy_rejects_below_30_minutes_and_adds_stripe_buffer():
    with pytest.raises(ValueError):
        HoldPolicy(29)
    assert HoldPolicy(30).expires_at(NOW) == NOW + timedelta(minutes=30, seconds=60)
    assert HoldPolicy.is_active(NOW + timedelta(seconds=1), NOW) and not HoldPolicy.is_active(NOW, NOW)


def test_reference_code_matches_contract_pattern():
    import re
    assert re.fullmatch(r"VOTA-[0-9]{8}-[A-Z0-9]{4}", new_reference_code(date(2026, 9, 16)))


def test_happy_path_pending_to_confirmed():
    b = booking()
    b.record_payment_received("pi_1")
    assert b.payment.status is PaymentStatus.SUCCEEDED and b.status is BookingStatus.PENDING_PAYMENT
    b.confirm(NOW)
    assert b.status is BookingStatus.CONFIRMED and b.hold_expires_at is None and b.confirmed_at == NOW
    assert b.payment.checkout_url is None


def test_confirm_requires_money_received():
    with pytest.raises(InvalidTransition):
        booking().confirm(NOW)


def test_third_card_failure_fails_the_booking():
    b = booking()
    assert b.register_card_failure("CARD_DECLINED", 3) is False
    assert b.register_card_failure("INSUFFICIENT_FUNDS", 3) is False
    assert b.payment.last_failure_code == "INSUFFICIENT_FUNDS" and b.status is BookingStatus.PENDING_PAYMENT
    assert b.register_card_failure("CARD_DECLINED", 3) is True
    assert (b.status, b.payment.status, b.payment.last_failure_code) == (
        BookingStatus.PAYMENT_FAILED, PaymentStatus.FAILED, "TOO_MANY_ATTEMPTS")


def test_expire_and_cancel_unpaid_close_the_payment():
    b = booking(); b.expire()
    assert (b.status, b.payment.status) == (BookingStatus.EXPIRED, PaymentStatus.EXPIRED)
    c = booking(); c.cancel_unpaid(NOW, "đổi ý")
    assert (c.status, c.payment.status, c.cancel_reason) == (BookingStatus.CANCELLED, PaymentStatus.EXPIRED, "đổi ý")


@pytest.mark.parametrize("call", ["expire", "register", "confirm", "cancel_unpaid"])
def test_closed_booking_rejects_further_transitions(call):
    b = booking(BookingStatus.EXPIRED, PaymentStatus.EXPIRED)
    with pytest.raises(InvalidTransition):
        {"expire": b.expire, "register": lambda: b.register_card_failure("x", 3), "confirm": lambda: b.confirm(NOW),
         "cancel_unpaid": lambda: b.cancel_unpaid(NOW, None)}[call]()


def test_cancel_paid_then_refund_lifecycle():
    b = booking(BookingStatus.CONFIRMED, PaymentStatus.SUCCEEDED)
    b.cancel_paid(NOW, None)
    assert (b.status, b.payment.status) == (BookingStatus.CANCELLED, PaymentStatus.REFUND_PENDING)
    b.start_refund("re_1"); b.finish_refund(True)
    assert b.payment.status is PaymentStatus.REFUNDED and b.payment.refund_id == "re_1"
    with pytest.raises(InvalidTransition):
        b.finish_refund(True)


def test_reject_paid_on_pending_fails_booking_and_refunds():
    b = booking(); b.record_payment_received("pi"); b.reject_paid("AMOUNT_MISMATCH")
    assert (b.status, b.payment.status) == (BookingStatus.PAYMENT_FAILED, PaymentStatus.REFUND_PENDING)


def test_cancellable_until_is_midnight_vietnam_the_day_before_earliest_usingdate():
    items = [BookingItem("a", "p", "hotel", "n", 1, 1, date(2026, 10, 16)), BookingItem("b", "p", "hotel", "n", 1, 1, date(2026, 10, 15))]
    assert cancellable_until(items) == datetime(2026, 10, 13, 17, 0, tzinfo=UTC)  # 00:00 ngày 14/10 giờ VN


@pytest.mark.parametrize("now,expected", [
    (datetime(2026, 10, 13, 16, 59, tzinfo=UTC), CancelDecision.REFUND_FULL),   # 23:59 ngày 13/10 giờ VN
    (datetime(2026, 10, 13, 17, 0, tzinfo=UTC), CancelDecision.TOO_LATE),       # đúng 00:00 ngày 14/10
])
def test_cancellation_boundary(now, expected):
    assert decide_cancellation(booking(BookingStatus.CONFIRMED, PaymentStatus.SUCCEEDED), now) is expected


def test_cancellation_decisions_by_state():
    assert decide_cancellation(booking(), NOW) is CancelDecision.EXPIRE_SESSION
    assert decide_cancellation(booking(pay=PaymentStatus.SUCCEEDED), NOW) is CancelDecision.ALREADY_PAID
    assert decide_cancellation(booking(BookingStatus.CANCELLED, PaymentStatus.EXPIRED), NOW) is CancelDecision.ALREADY_CANCELLED
    assert decide_cancellation(booking(BookingStatus.EXPIRED, PaymentStatus.EXPIRED), NOW) is CancelDecision.NOT_ACTIVE
    assert decide_cancellation(booking(BookingStatus.PAYMENT_FAILED, PaymentStatus.FAILED), NOW) is CancelDecision.NOT_ACTIVE


@pytest.mark.parametrize("decline,error,reason", [
    ("insufficient_funds", None, "INSUFFICIENT_FUNDS"), ("expired_card", None, "EXPIRED_CARD"),
    ("incorrect_cvc", None, "INCORRECT_CVC"), (None, "payment_intent_authentication_failure", "AUTHENTICATION_FAILED"),
    ("processing_error", None, "PROCESSING_ERROR"), ("generic_decline", "card_declined", "CARD_DECLINED"),
    (None, None, "CARD_DECLINED"),
])
def test_stripe_failure_codes(decline, error, reason):
    assert failure_reason_from_stripe(decline, error) == reason


def test_check_product_reports_unavailable_price_change_and_date():
    p = product()
    assert check_product(p, date(2026, 10, 1)) is None
    assert check_product(product(available=False), date(2026, 10, 1)).code == "PRODUCT_UNAVAILABLE"
    issue = check_product(p, date(2026, 10, 1), snapshot_price=3_000_000)
    assert issue.code == "PRICE_CHANGED" and issue.details["oldPrice"] == 3_000_000 and issue.details["newPrice"] == 3_400_000
    assert check_product(p, date(2027, 1, 1)).code == "DATE_OUT_OF_RANGE"


TODAY = date(2026, 10, 2)


def test_hotel_check_in_window_is_today_to_three_months_ahead():
    p = product(available_from=date(2026, 10, 15), available_to=date(2026, 10, 16))
    # Không dùng cửa sổ mở bán của dữ liệu: nhận phòng ngay hôm nay và đến đúng hôm nay + 3 tháng đều hợp lệ.
    assert check_product(p, TODAY, today=TODAY) is None
    assert check_product(p, date(2027, 1, 2), today=TODAY) is None
    past = check_product(p, date(2026, 10, 1), today=TODAY)
    assert past.code == "DATE_OUT_OF_RANGE"
    assert past.details["availableFrom"] == "2026-10-02" and past.details["availableTo"] == "2027-01-02"
    assert check_product(p, date(2027, 1, 3), today=TODAY).code == "DATE_OUT_OF_RANGE"


def test_hotel_window_clamps_to_end_of_short_month():
    p = product()
    assert check_product(p, date(2027, 2, 28), today=date(2026, 11, 30)) is None
    assert check_product(p, date(2027, 3, 1), today=date(2026, 11, 30)).code == "DATE_OUT_OF_RANGE"


def test_hotel_sold_out_calendar_reports_unavailable_not_date_error():
    calendar = "1" * 5 + "0" + "1" * 24  # kín đêm 07/10 (from + 5)
    p = product(attributes={"level": "room", "availability": {"from": "2026-10-02", "days": 30, "calendar": calendar}})
    assert check_product(p, date(2026, 10, 3), today=TODAY, nights=2) is None
    assert check_product(p, date(2026, 10, 6), today=TODAY, nights=2).code == "PRODUCT_UNAVAILABLE"
    assert check_product(p, date(2026, 10, 7), today=TODAY, nights=1).code == "PRODUCT_UNAVAILABLE"
    assert check_product(p, date(2026, 10, 8), today=TODAY, nights=2) is None
    # Ngoài khoảng lịch đã nạp (không có dữ liệu) thì không chặn.
    assert check_product(p, date(2026, 12, 20), today=TODAY, nights=3) is None


def test_non_hotel_keeps_source_window_even_with_today():
    p = product(taxonomy="attraction", available_from=date(2026, 10, 15), available_to=date(2026, 10, 16))
    assert check_product(p, date(2026, 10, 20), today=TODAY).code == "DATE_OUT_OF_RANGE"
