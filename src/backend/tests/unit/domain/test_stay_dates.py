"""Luật ngày dùng chung cho đặt phòng và bộ lọc ngày của /search (`domain/catalog/stay_dates.py`)."""
from datetime import date

import pytest

from src.backend.app.domain.catalog.stay_dates import (
    StayDates,
    calendar_open,
    hotel_booking_window,
    parse_calendar,
)

D = date.fromisoformat


def test_hotel_booking_window_is_today_to_three_months_clamped_to_month_end():
    assert hotel_booking_window(D("2026-10-07")) == (D("2026-10-07"), D("2027-01-07"))
    assert hotel_booking_window(D("2026-11-30")) == (D("2026-11-30"), D("2027-02-28"))   # tháng 2 ngắn hơn
    assert hotel_booking_window(D("2027-11-30")) == (D("2027-11-30"), D("2028-02-29"))   # năm nhuận


def test_stay_dates_nights_and_validation():
    one = StayDates(D("2026-10-10"), None, D("2026-10-07"))
    assert one.nights == 1 and one.end == one.start + 1
    two = StayDates(D("2026-10-10"), D("2026-10-12"), D("2026-10-07"))
    assert two.nights == 2 and two.end == two.start + 2
    with pytest.raises(ValueError):
        StayDates(D("2026-10-10"), D("2026-10-10"), D("2026-10-07"))
    with pytest.raises(ValueError):
        StayDates(D("2026-10-10"), D("2026-10-09"), D("2026-10-07"))


def test_hotel_window_ok_follows_the_booking_rule():
    today = D("2026-10-07")
    ok = lambda ci, co=None: StayDates(D(ci), D(co) if co else None, today).hotel_window_ok()   # noqa: E731
    assert ok("2026-10-07") and ok("2026-10-10", "2026-10-12") and ok("2027-01-07")
    assert not ok("2026-10-06")                                  # quá khứ
    assert not ok("2027-01-08")                                  # quá 3 tháng
    assert ok("2026-10-10", "2026-11-09") and not ok("2026-10-10", "2026-11-10")   # 30 đêm là tối đa


def test_parse_calendar_accepts_only_well_formed_availability():
    assert parse_calendar({"availability": {"from": "2026-10-01", "days": 3, "calendar": "101"}}) == (D("2026-10-01").toordinal(), "101")
    for bad in ({}, {"availability": None}, {"availability": {"from": "2026-10-01"}},
                {"availability": {"from": "2026-10-01", "calendar": ""}},
                {"availability": {"from": "2026-10-01", "calendar": "10x"}},
                {"availability": {"from": "không phải ngày", "calendar": "101"}},
                {"availability": {"from": 20261001, "calendar": "101"}}):
        assert parse_calendar(bad) is None, bad


def test_calendar_open_only_fails_on_a_known_closed_night():
    cal = (D("2026-10-01").toordinal(), "1101")                  # 01 mở, 02 mở, 03 kín, 04 mở
    start = lambda d: D(d).toordinal()                            # noqa: E731
    assert calendar_open(cal, start("2026-10-01"), start("2026-10-03"))
    assert not calendar_open(cal, start("2026-10-02"), start("2026-10-04"))     # có đêm 03 kín
    assert calendar_open(cal, start("2026-10-04"), start("2026-10-07"))         # đêm ngoài khoảng lịch = chưa biết
    assert calendar_open(cal, start("2026-09-28"), start("2026-10-01"))         # trước khoảng lịch
