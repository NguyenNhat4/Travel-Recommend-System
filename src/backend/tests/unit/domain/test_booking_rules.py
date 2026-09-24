"""Luật đặt chỗ thuần: đơn vị đặt được (FR-CAT-02), cửa sổ ngày + lịch trống (AC-BKG-01), thành tiền (backend §2.6)."""
import re
from datetime import date

import pytest

from src.backend.app.domain.booking import (
    DateOutOfRange,
    InvalidField,
    NotBookable,
    ProductNotFound,
    ProductUnavailable,
    bookable_product,
    calendar_open,
    ensure_open,
    event_group_id,
    line_total,
    reference_code,
    stay_nights,
)
from src.backend.app.domain.catalog import Product

ROOM = Product(product_id="R1", name="Resort - Deluxe", taxonomy="hotel", destination="Đà Nẵng", description="",
               attributes={"level": "room", "parentProductId": "H1",
                           "availability": {"from": "2026-09-24", "days": 30, "calendar": "1100" + "1" * 26}},
               unit_price=1_000_000, available_from=date(2026, 9, 24), available_to=date(2026, 10, 23))
PROPERTY = Product(product_id="H1", name="Resort", taxonomy="hotel", destination="Đà Nẵng", description="",
                   attributes={"level": "property"}, unit_price=900_000)
FLIGHT = Product(product_id="FL1", name="VJ123", taxonomy="flight", destination="Đà Nẵng", description="",
                 attributes={"level": "flight", "parentProductId": "F1"}, unit_price=1_500_000,
                 available_from=date(2026, 10, 1), available_to=date(2026, 10, 1))


def test_only_concrete_units_are_bookable():
    assert bookable_product(ROOM, "R1") is ROOM
    assert bookable_product(FLIGHT, "FL1") is FLIGHT
    with pytest.raises(NotBookable):
        bookable_product(PROPERTY, "H1")
    with pytest.raises(ProductNotFound):
        bookable_product(None, "nope")
    with pytest.raises(ProductUnavailable):
        bookable_product(Product(**{**ROOM.__dict__, "available": False}), "R1")


def test_nights_are_required_for_hotels_and_ignored_otherwise():
    assert stay_nights(ROOM, 2) == 2
    assert stay_nights(FLIGHT, 5) is None
    with pytest.raises(InvalidField):
        stay_nights(ROOM, None)


def test_calendar_needs_every_night_open():
    availability = ROOM.attributes["availability"]
    assert calendar_open(availability, date(2026, 9, 24), 2)          # "11"
    assert not calendar_open(availability, date(2026, 9, 25), 2)      # "10"
    assert not calendar_open(availability, date(2026, 10, 22), 3)     # vượt cuối lịch: không kiểm được, coi là kín
    assert not calendar_open(availability, date(2026, 9, 23), 1)      # trước ngày đầu lịch
    assert calendar_open(None, date(2026, 9, 25), 7)                  # không có lịch thì không chặn


def test_ensure_open_checks_window_then_calendar():
    ensure_open(ROOM, date(2026, 9, 24), 2)
    with pytest.raises(DateOutOfRange) as out_of_range:
        ensure_open(ROOM, date(2026, 11, 1), 1)
    assert out_of_range.value.details == {"productId": "R1", "availableFrom": "2026-09-24",
                                          "availableTo": "2026-10-23"}
    with pytest.raises(ProductUnavailable):
        ensure_open(ROOM, date(2026, 9, 26), 1)
    with pytest.raises(DateOutOfRange):
        ensure_open(FLIGHT, date(2026, 10, 2), None)


def test_line_total_multiplies_nights_only_per_night():
    assert line_total(1_000_000, "PER_NIGHT", 2, 3) == 6_000_000
    assert line_total(1_500_000, "PER_PERSON", 2, 3) == 3_000_000
    assert line_total(9_800_000, "PER_PACKAGE", 1, None) == 9_800_000


def test_codes_follow_the_contract_patterns():
    assert re.fullmatch(r"VOTA-20260924-[A-Z0-9]{4}", reference_code(date(2026, 9, 24)))
    assert reference_code(date(2026, 9, 24), "8K3F") == "VOTA-20260924-8K3F"
    assert re.fullmatch(r"WEB20260924[A-Z0-9]{6}", event_group_id(date(2026, 9, 24)))
