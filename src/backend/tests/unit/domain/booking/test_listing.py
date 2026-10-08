"""Xếp đơn vào ba tab của trang Đơn hàng của tôi (FR-BKG-14, AC-BKG-18)."""
from datetime import date, datetime, timedelta, timezone

import pytest

from src.backend.app.domain.booking import BookingItem, BookingOverview, BookingStatus, BookingTab, item_end_date, tab_of

UTC = timezone.utc
# 06/10/2026 18:30 UTC = 01:30 ngày 07/10/2026 giờ Việt Nam: ranh giới ngày phải tính theo giờ Việt Nam.
NOW = datetime(2026, 10, 6, 18, 30, tzinfo=UTC)


def overview(status, *, end=date(2026, 10, 20), hold=None) -> BookingOverview:
    return BookingOverview("b", status, NOW - timedelta(days=1), hold, end, ("hotel",))


@pytest.mark.parametrize("end, tab", [
    (date(2026, 10, 8), BookingTab.UPCOMING),
    (date(2026, 10, 7), BookingTab.UPCOMING),   # kết thúc đúng hôm nay (giờ Việt Nam) vẫn là sắp đến
    (date(2026, 10, 6), BookingTab.DONE),       # hôm qua theo giờ Việt Nam, dù còn là ngày 06 theo UTC
])
def test_confirmed_booking_moves_to_done_after_its_last_service_day(end, tab):
    assert tab_of(overview(BookingStatus.CONFIRMED, end=end), NOW) is tab


def test_pending_payment_is_upcoming_while_held_and_cancelled_after_the_hold_ends():
    assert tab_of(overview(BookingStatus.PENDING_PAYMENT, hold=NOW + timedelta(minutes=5)), NOW) is BookingTab.UPCOMING
    assert tab_of(overview(BookingStatus.PENDING_PAYMENT, hold=NOW - timedelta(seconds=1)), NOW) is BookingTab.CANCELLED
    assert tab_of(overview(BookingStatus.PENDING_PAYMENT, hold=NOW), NOW) is BookingTab.CANCELLED


@pytest.mark.parametrize("status", [BookingStatus.CANCELLED, BookingStatus.EXPIRED, BookingStatus.PAYMENT_FAILED])
def test_closed_bookings_are_cancelled_whatever_their_dates(status):
    assert tab_of(overview(status, end=date(2027, 1, 1)), NOW) is BookingTab.CANCELLED


def test_hotel_ends_on_checkout_day_and_other_services_on_their_using_date():
    hotel = BookingItem("i", "p", "hotel", "Phòng", 1_000_000, 1, date(2026, 10, 12), nights=2)
    ticket = BookingItem("i", "p", "attraction", "Vé", 500_000, 2, date(2026, 10, 13), nights=None)
    assert item_end_date(hotel) == date(2026, 10, 14) and item_end_date(ticket) == date(2026, 10, 13)
