"""Hạng vé cùng hành trình (domain/catalog/fares.py, contract FareClass 1.9.0)."""
from datetime import date

from src.backend.app.domain.catalog import Product
from src.backend.app.domain.catalog.fares import fare_class, fare_classes_by_product, itinerary_key
from src.backend.tests.conftest import P

OUT = {"flightNumber": "VN123", "departureAt": "2026-10-17T08:00:00+07:00", "parentProductId": "RT"}
FLIGHTS = [
    P("ECO", "VN123 phổ thông", "flight", "Hồ Chí Minh",
      {"level": "flight", "tripType": "oneWay", "cabinClass": "ECONOMY", **OUT}, price=1_200_000),
    P("BUS", "VN123 thương gia", "flight", "Hồ Chí Minh",
      {"level": "flight", "tripType": "oneWay", "cabinClass": "BUSINESS", **OUT}, price=3_500_000),
    # trip.com: cùng chuyến, không ghi hạng, không ghi tripType (dòng cũ)
    P("TRIP", "VN123 giá rẻ nhất", "flight", "Hồ Chí Minh", {"level": "flight", **OUT}, price=1_100_000),
    P("OTHER", "VN125", "flight", "Hồ Chí Minh",
      {"level": "flight", "tripType": "oneWay", "cabinClass": "ECONOMY", "flightNumber": "VN125",
       "departureAt": "2026-10-17T10:00:00+07:00", "parentProductId": "RT"}, price=1_300_000),
    P("RTRIP", "Khứ hồi VJ771 / VJ776", "flight", "Nha Trang",
      {"level": "flight", "tripType": "roundTrip", "flightNumber": "VJ771", "departureAt": "2026-10-19T04:45:00+07:00",
       "returnDate": "2026-10-22", "parentProductId": "RT",
       "returnFlight": {"flightNumber": "VJ776", "departureAt": "2026-10-22T06:00:00+07:00"},
       "priceValidUntil": "2026-09-30", "priceBasis": "per_person"}, price=1_322_000),
    P("ELSE", "VN123 tuyến khác", "flight", "Đà Nẵng",
      {"level": "flight", "cabinClass": "ECONOMY", **dict(OUT, parentProductId="RT2")}, price=900_000),
]
PRODUCTS = [Product.from_cdp(r) for r in FLIGHTS]
BY_ID = {p.product_id: p for p in PRODUCTS}


def test_same_itinerary_groups_every_cabin_and_keeps_one_product_id_each():
    fares = fare_classes_by_product(PRODUCTS, date(2026, 9, 29))
    group = fares["ECO"]
    assert [f["productId"] for f in group] == ["ECO", "BUS", "TRIP"]  # ECO, BUS rồi hạng chưa rõ
    assert fares["BUS"] is group and fares["TRIP"] is group
    assert [f["code"] for f in group] == ["ECO", "BUS", None]
    assert [f["name"] for f in group] == ["Phổ thông", "Thương gia", "Giá rẻ nhất"]
    assert [f["price"] for f in group] == [1_200_000, 3_500_000, 1_100_000]
    assert [f["productId"] for f in fares["OTHER"]] == ["OTHER"]  # chuyến khác, hành trình khác
    assert [f["productId"] for f in fares["ELSE"]] == ["ELSE"]  # cùng số hiệu nhưng tuyến khác


def test_round_trip_is_its_own_itinerary_and_quote_expiry_is_not_sold_out():
    fares = fare_classes_by_product(PRODUCTS, date(2026, 9, 29))["RTRIP"]
    assert len(fares) == 1 and fares[0]["availabilityStatus"] == "AVAILABLE"
    assert fares[0]["priceValidUntil"] == "2026-09-30"
    expired = fare_classes_by_product(PRODUCTS, date(2026, 10, 1))["RTRIP"][0]
    assert expired["availabilityStatus"] == "EXPIRED" and expired["soldOut"] is None
    assert itinerary_key(BY_ID["RTRIP"]) != itinerary_key(BY_ID["ECO"])


def test_unknown_facts_stay_null_and_other_products_have_no_fares():
    fare = fare_class(BY_ID["ECO"], date(2026, 9, 29))
    assert {k: fare[k] for k in ("soldOut", "carryOnKg", "checkedKg", "mealIncluded", "changeRule")} == dict.fromkeys(
        ("soldOut", "carryOnKg", "checkedKg", "mealIncluded", "changeRule"))
    closed = Product.from_cdp(dict(FLIGHTS[0], available=False))
    assert fare_class(closed, date(2026, 9, 29))["availabilityStatus"] == "NOT_CHECKED"
    route = Product.from_cdp(P("RT", "Tuyến", "flight", "Hồ Chí Minh", {"level": "route"}, price=None))
    hotel = Product.from_cdp(P("R", "Phòng", "hotel", "Nha Trang", {"level": "room"}))
    no_number = Product.from_cdp(P("FL", "Chuyến", "flight", "Nha Trang", {"level": "flight"}))
    assert fare_classes_by_product([route, hotel, no_number], date(2026, 9, 29)) == {}


def test_same_flight_on_another_day_is_another_itinerary():
    next_day = Product.from_cdp(P("ECO_NEXT", "VN123 hôm sau", "flight", "Hồ Chí Minh",
                                  {"level": "flight", "tripType": "oneWay", "cabinClass": "ECONOMY",
                                   **dict(OUT, departureAt="2026-10-18T08:00:00+07:00")}, price=1_250_000))
    fares = fare_classes_by_product([*PRODUCTS, next_day], date(2026, 9, 29))
    assert [f["productId"] for f in fares["ECO_NEXT"]] == ["ECO_NEXT"]
    assert "ECO_NEXT" not in [f["productId"] for f in fares["ECO"]]
    # khứ hồi cùng chuyến đi nhưng ngày về khác cũng là hành trình khác
    other_return = Product.from_cdp(dict(FLIGHTS[4], productId="RTRIP2", attributes=dict(
        FLIGHTS[4]["attributes"], returnFlight={"flightNumber": "VJ776", "departureAt": "2026-10-23T06:00:00+07:00"})))
    assert itinerary_key(other_return) != itinerary_key(BY_ID["RTRIP"])
