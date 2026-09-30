"""Bộ luật đoàn khách, phân bổ, giỏ và dòng giá — chạy trên bộ ca dùng chung với Web.

Nguồn ca: `src/shared/contracts/tests/booking-rules-cases.json` (spec checkout-nhieu-buoc-hanh-khach.md §12). Web chạy cùng file
này ở `src/frontend/tests/unit/checkoutRules.test.ts`; hai phía phải cho cùng kết quả.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.backend.app.domain.booking.fares import fare_lines, lines_total
from src.backend.app.domain.booking.party import (
    Guests, Traveler, TravelerType, adult_from, age_on, fare_type_on, is_infant_on,
)
from src.backend.app.domain.booking.party_rules import (
    CartFacts, ContactInput, ItemInput, RoomInput, TravelerInput, check_checkout, check_contact, check_items,
    check_legacy, check_party, resolve_cart_guests,
)

CASES = json.loads((Path(__file__).resolve().parents[5] / "shared/contracts/tests/booking-rules-cases.json")
                   .read_text(encoding="utf-8"))
TODAY = date.fromisoformat(CASES["base"]["today"])


def _build(case: dict):
    data = {**CASES["base"], **case["override"]}
    contact = ContactInput(data["contact"]["fullName"], data["contact"]["email"], data["contact"]["phone"])
    travelers = [TravelerInput(t["travelerRef"], t["type"], t["surname"], t["givenNames"], t.get("birthDate"))
                 for t in data["travelers"]]
    cart = [CartFacts(c["cartItemId"], c["name"], c["taxonomy"], date.fromisoformat(c["usingDate"]), c["quantity"],
                      c["guests"]["adults"], c["guests"]["children"], c["maxOccupancy"]) for c in data["cart"]]
    details = [ItemInput(
        d["cartItemId"], d.get("travelerRefs"),
        [RoomInput(r["travelerRefs"], r.get("leadTravelerRef")) for r in d["rooms"]] if "rooms" in d else None)
        for d in data["itemDetails"]]
    return contact, travelers, cart, details


def _key(item) -> tuple:
    if isinstance(item, dict):
        return item["field"], item["reason"], item.get("cartItemId")
    return item.field, item.reason, item.cart_item_id


@pytest.mark.parametrize("case", CASES["checkout"], ids=lambda c: c["name"][:70])
def test_checkout_rules_match_shared_cases(case):
    contact, inputs, cart, details = _build(case)
    earliest = min(c.using_date for c in cart)
    if case["scope"] == "party":
        travelers, party = check_party(inputs, earliest=earliest, today=TODAY)
        got = [*check_contact(contact), *party]
    elif case["scope"] == "items":
        travelers, _ = check_party(inputs, earliest=earliest, today=TODAY)
        got = check_items(travelers, details, cart)
    else:
        got = check_checkout(contact, inputs, details, cart, today=TODAY)[1]
    assert sorted(map(_key, got), key=str) == sorted(map(_key, case["expect"]), key=str)


@pytest.mark.parametrize("case", CASES["age"], ids=lambda c: c["name"][:70])
def test_age_and_infant_rules_match_shared_cases(case):
    birth, day = date.fromisoformat(case["birth"]), date.fromisoformat(case["day"])
    assert age_on(birth, day) == case["age"]
    child = Traveler("t", TravelerType.CHILD, "Nguyễn", "An", birth)
    assert is_infant_on(child, day) is case["infant"]


@pytest.mark.parametrize("case", CASES["turnsAdult"], ids=lambda c: c["name"][:70])
def test_child_turns_adult_on_their_twelfth_birthday(case):
    birth, on = date.fromisoformat(case["birth"]), date.fromisoformat(case["on"])
    assert adult_from(birth) == on
    child = Traveler("t", TravelerType.CHILD, "Nguyễn", "An", birth)
    assert fare_type_on(child, on).value == "ADULT"
    assert fare_type_on(child, date.fromordinal(on.toordinal() - 1)).value == "CHILD"


def test_child_without_a_valid_birth_date_is_priced_as_a_child_and_never_an_infant():
    child = Traveler("t", TravelerType.CHILD, "Nguyễn", "An", None)
    assert fare_type_on(child, date(2026, 10, 17)).value == "CHILD"
    assert is_infant_on(child, date(2026, 10, 17)) is False
    assert fare_type_on(Traveler("a", TravelerType.ADULT, "Nguyễn", "An"), date(2026, 10, 17)).value == "ADULT"


@pytest.mark.parametrize("case", CASES["cart"], ids=lambda c: c["name"][:70])
def test_cart_guest_rules_match_shared_cases(case):
    def guests(value):
        return Guests(value["adults"], value["children"]) if value else None

    existing = case["existing"]
    result = resolve_cart_guests(
        case["taxonomy"], mode=case["mode"], request_quantity=case["request"]["quantity"],
        request_guests=guests(case["request"]["guests"]),
        existing_quantity=existing["quantity"] if existing else None,
        existing_guests=guests(existing["guests"]) if existing else None, max_occupancy=case["maxOccupancy"])
    if "violations" in case:
        assert sorted((v.field, v.reason) for v in result.violations) == sorted(
            (v["field"], v["reason"]) for v in case["violations"])
    else:
        assert result.violations == []
        assert result.quantity == case["expect"]["quantity"]
        assert result.guests == guests(case["expect"]["guests"])


@pytest.mark.parametrize("case", CASES["fares"], ids=lambda c: c["name"][:70])
def test_fare_lines_match_shared_cases(case):
    lines = fare_lines(
        case["taxonomy"], case["unitPrice"], case["attributes"], quantity=case["quantity"], nights=case["nights"],
        adults=case["guests"]["adults"], children=case["guests"]["children"])
    assert [line.to_json() for line in lines] == case["expect"]["lines"]
    assert lines_total(lines) == case["expect"]["total"]


def test_legacy_request_without_travelers_is_checked_for_real_now():
    hotel = CartFacts("ci-h", "Khách sạn", "hotel", date(2026, 10, 15), 1, 1, 0, 3)
    flight = CartFacts("ci-f", "Chuyến bay", "flight", date(2026, 10, 15), 2, 2, 0)
    ticket = CartFacts("ci-t", "Vé", "attraction", date(2026, 10, 15), 1, 1, 0)
    # thiếu tên vé máy bay và không có itemDetails cho vé tham quan (lỗi L5: trước đây vẫn nhận 201)
    got = check_legacy([ItemInput("ci-h", guest_names=["Nguyễn Minh Anh"]), ItemInput("ci-f", guest_names=["Chỉ Một"])],
                       [hotel, flight, ticket])
    assert sorted((v.field, v.reason) for v in got) == [
        ("itemDetails", "ITEM_DETAIL_MISSING"), ("itemDetails[1].guestNames", "REQUIRED")]
    ok = check_legacy([ItemInput("ci-h", guest_names=["A B"]), ItemInput("ci-f", guest_names=["A B", "C D"]),
                       ItemInput("ci-t")], [hotel, flight, ticket])
    assert ok == []


def test_legacy_request_is_rejected_when_the_cart_has_children():
    ticket = CartFacts("ci-t", "Vé", "attraction", date(2026, 10, 15), 3, 2, 1)
    got = check_legacy([ItemInput("ci-t")], [ticket])
    assert [(v.field, v.reason) for v in got] == [("travelers", "TRAVELERS_REQUIRED")]
