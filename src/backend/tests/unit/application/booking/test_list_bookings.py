"""Danh sách đơn của chính người dùng: tab, lọc, phân trang, cách ly người dùng (FR-BKG-14, AC-BKG-18)."""
import asyncio
from datetime import date, timedelta

import pytest

from src.backend.app.domain.booking import Booking, BookingItem, BookingStatus, BookingTab, Payment, PaymentStatus
from src.backend.tests.fakes.booking import NOW, PRINCIPAL, USER, World

run = asyncio.run
TODAY = NOW.date()  # 16/09/2026


def add(w: World, n: int, status=BookingStatus.CONFIRMED, *, taxonomy="hotel", end_in_days=10, age_days=0,
        user=USER, hold=None, pay=PaymentStatus.SUCCEEDED) -> Booking:
    using = TODAY + timedelta(days=end_in_days)
    item = BookingItem(f"bi{n}", f"p{n}", taxonomy, f"Dịch vụ {n}", 1_000_000, 1, using,
                       nights=1 if taxonomy == "hotel" else None)
    booking = Booking(f"b{n}", f"VOTA-20260916-{n:04d}", user, f"OFF{n}", "A", "a@b.vn", "0912345678",
                      NOW - timedelta(days=age_days, minutes=n), [item], status=status, hold_expires_at=hold,
                      payment=Payment(f"pay{n}", "fake", 1_000_000, status=pay))
    w.store.bookings[booking.booking_id] = booking
    return booking


def listing(w: World, **kw):
    return run(w.list(PRINCIPAL, **kw))


def refs(page) -> list[str]:
    return [b["referenceCode"] for b in page["data"]]


def test_each_booking_lands_in_exactly_one_tab_newest_first():
    w = World()
    add(w, 1, end_in_days=5)                                        # sắp đến
    add(w, 2, end_in_days=-3)                                       # hoàn thành
    add(w, 3, BookingStatus.CANCELLED, pay=PaymentStatus.REFUNDED)  # đã huỷ
    add(w, 4, BookingStatus.PENDING_PAYMENT, hold=NOW + timedelta(minutes=20), pay=PaymentStatus.OPEN)
    add(w, 5, BookingStatus.PENDING_PAYMENT, hold=NOW - timedelta(minutes=1), pay=PaymentStatus.OPEN)
    seen = {t: set(refs(listing(w, tab=t))) for t in BookingTab}
    assert seen[BookingTab.UPCOMING] == {"VOTA-20260916-0001", "VOTA-20260916-0004"}
    assert seen[BookingTab.DONE] == {"VOTA-20260916-0002"}
    assert seen[BookingTab.CANCELLED] == {"VOTA-20260916-0003", "VOTA-20260916-0005"}
    assert sum(len(v) for v in seen.values()) == 5


def test_newest_booking_comes_first():
    w = World()
    add(w, 1, age_days=3)
    add(w, 2, age_days=1)
    add(w, 3, age_days=2)
    assert refs(listing(w)) == ["VOTA-20260916-0002", "VOTA-20260916-0003", "VOTA-20260916-0001"]


def test_taxonomy_filter_keeps_bookings_with_at_least_one_such_service():
    w = World()
    add(w, 1, taxonomy="hotel")
    add(w, 2, taxonomy="flight")
    mixed = add(w, 3, taxonomy="hotel")
    mixed.items.append(BookingItem("bi3b", "p3b", "attraction", "Vé", 500_000, 2, TODAY + timedelta(days=11)))
    assert set(refs(listing(w, taxonomy="flight"))) == {"VOTA-20260916-0002"}
    assert set(refs(listing(w, taxonomy="attraction"))) == {"VOTA-20260916-0003"}
    assert set(refs(listing(w, taxonomy="hotel"))) == {"VOTA-20260916-0001", "VOTA-20260916-0003"}
    assert refs(listing(w, taxonomy="golf")) == []


@pytest.mark.parametrize("days, expected", [(1, 1), (7, 2), (30, 3), (60, 4), (None, 5)])
def test_days_keeps_bookings_made_within_the_window(days, expected):
    w = World()
    for n, age in enumerate([0, 5, 20, 45, 100], start=1):
        add(w, n, age_days=age)
    assert len(listing(w, days=days)["data"]) == expected


def test_pagination_reports_totals_and_page_beyond_the_end_is_empty():
    w = World()
    for n in range(1, 13):
        add(w, n, age_days=0)
    first = listing(w, page=1, page_size=5)
    assert len(first["data"]) == 5 and first["pagination"] == {"page": 1, "pageSize": 5, "totalItems": 12, "totalPages": 3}
    assert len(listing(w, page=3, page_size=5)["data"]) == 2
    beyond = listing(w, page=9, page_size=5)
    assert beyond["data"] == [] and beyond["pagination"]["totalItems"] == 12
    pages = [refs(listing(w, page=p, page_size=5)) for p in (1, 2, 3)]
    assert len({r for page in pages for r in page}) == 12  # không đơn nào xuất hiện hai lần


def test_empty_history_is_an_empty_page_with_zero_pages():
    page = listing(World())
    assert page == {"data": [], "pagination": {"page": 1, "pageSize": 20, "totalItems": 0, "totalPages": 0}}


def test_only_own_bookings_are_listed():
    w = World()
    add(w, 1, user=USER)
    add(w, 2, user="VP0000999")
    assert refs(listing(w)) == ["VOTA-20260916-0001"]


def test_summary_carries_what_the_card_needs_and_nothing_private():
    w = World()
    add(w, 1, BookingStatus.PAYMENT_FAILED, pay=PaymentStatus.FAILED).payment.last_failure_code = "TOO_MANY_ATTEMPTS"
    add(w, 2, end_in_days=8)
    failed = listing(w, tab=BookingTab.CANCELLED)["data"][0]
    assert failed["status"] == "PAYMENT_FAILED" and failed["paymentStatus"] == "FAILED"
    assert failed["paymentFailureReason"] == "TOO_MANY_ATTEMPTS" and failed["cancellableUntil"] is None
    ok = listing(w, tab=BookingTab.UPCOMING)["data"][0]
    assert ok["cancellableUntil"] is not None and ok["total"] == 1_000_000
    item = ok["items"][0]
    assert item["usingDateTo"] == (TODAY + timedelta(days=9)).isoformat() and item["nights"] == 1
    assert not {"contact", "travelers", "payment", "groups"} & ok.keys()
