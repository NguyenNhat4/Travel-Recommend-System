"""Thuộc tính lọc theo unit (`domain/catalog/unit_attributes.py`): tiện ích + con, giá thấp nhất, sao, chặng bay, cờ loại
sản phẩm, sức chứa, danh sách con; thuần."""
import math

import numpy as np
import pytest

from src.backend.app.domain.catalog import Product, UnitAttributes
from src.backend.app.domain.catalog.unit_attributes import FLAG_INCLUDES_FLIGHT, FLAG_INCLUDES_HOTEL, FLAG_TICKETED, FLAGS
from src.backend.tests.conftest import P

H1 = Product.from_cdp(P("H1", "Vinpearl Resort Nha Trang", "hotel", "Nha Trang",
                        {"level": "property", "starRating": 5, "brand": "Vinpearl",
                         "amenities": ["Bãi biển riêng", "Hồ bơi ngoài trời"], "highlights": ["Sân golf"]}, price=None))
R1 = Product.from_cdp(P("R1", "Vinpearl Resort Nha Trang - Deluxe", "hotel", "Nha Trang",
                        {"level": "room", "parentProductId": "H1", "amenities": ["Ban công"]}, price=3400000))
R1B = Product.from_cdp(P("R1B", "Vinpearl Resort Nha Trang - Suite", "hotel", "Nha Trang",
                         {"level": "room", "parentProductId": "H1"}, price=None))
H2 = Product.from_cdp(P("H2", "Khách sạn B Nha Trang", "hotel", "Nha Trang", {"level": "property", "starRating": 4}, price=None))
F1 = Product.from_cdp(P("F1", "Vé máy bay Hà Nội - Cam Ranh", "flight", "Nha Trang",
                        {"level": "route", "originCity": "Hà Nội", "destinationCity": "Nha Trang"}, price=None))
A1 = Product.from_cdp(P("A1", "VinWonders Nha Trang", "attraction", "Nha Trang", {"amenities": None}, price=880000))

UNITS = [H1, H2, F1, A1]
CHILDREN = {"H1": [R1, R1B]}


@pytest.fixture(scope="module")
def attrs() -> UnitAttributes:
    return UnitAttributes.build(UNITS, CHILDREN)


def test_shapes_follow_units(attrs):
    assert len(attrs) == len(UNITS)
    for arr in (attrs.brand, attrs.star_rating, attrs.min_price, attrs.origin_city, attrs.destination_city):
        assert arr.shape == (len(UNITS),)
    assert attrs.star_rating.dtype == np.float64 and attrs.min_price.dtype == np.float64
    assert attrs.brand.dtype == object and attrs.origin_city.dtype == object


def test_amenities_merge_unit_and_children_but_not_highlights(attrs):
    assert attrs.amenities[0] == {"privateBeach", "nearBeach", "pool", "balcony"}   # "Sân golf" ở highlights → không tính
    assert attrs.amenities[1] == frozenset()                                       # không có dữ liệu = không biết
    assert attrs.amenities[3] == frozenset()                                       # amenities None → bỏ qua


def test_min_price_is_min_over_unit_and_priced_children(attrs):
    assert attrs.min_price[0] == pytest.approx(3.4e6)       # H1 giá None, lấy của R1; R1B giá None bỏ qua
    assert math.isnan(attrs.min_price[1])                   # H2 không con, không giá
    assert math.isnan(attrs.min_price[2])
    assert attrs.min_price[3] == pytest.approx(880000)      # unit tự có giá


def test_star_rating_and_brand(attrs):
    assert attrs.star_rating[0] == 5.0 and attrs.star_rating[1] == 4.0
    assert math.isnan(attrs.star_rating[2]) and math.isnan(attrs.star_rating[3])
    assert attrs.brand.tolist() == ["Vinpearl", "", "", ""]


def test_flight_route_cities(attrs):
    assert attrs.origin_city.tolist() == ["", "", "Hà Nội", ""]
    assert attrs.destination_city.tolist() == ["", "", "Nha Trang", ""]


@pytest.mark.parametrize("star", ["5", True, None, {"x": 1}])
def test_non_numeric_star_is_nan(star):
    p = Product.from_cdp(P("X", "x", "hotel", "d", {"starRating": star}, price=None))
    assert math.isnan(UnitAttributes.build([p]).star_rating[0])


def test_non_list_amenities_are_ignored():
    p = Product.from_cdp(P("X", "x", "hotel", "d", {"amenities": "Hồ bơi"}, price=None))
    assert UnitAttributes.build([p]).amenities == (frozenset(),)


def test_build_without_children_uses_unit_only():
    a = UnitAttributes.build(UNITS)
    assert a.amenities[0] == {"privateBeach", "nearBeach", "pool"}
    assert math.isnan(a.min_price[0])


def test_empty_units():
    a = UnitAttributes.build([])
    assert len(a) == 0 and a.brand.shape == (0,) and a.min_price.shape == (0,)


# --- cờ, sức chứa, con (kiến trúc §6 filter-first, checklist dữ liệu §15)
C1 =Product.from_cdp(P("C1", "Combo bay + ở Phú Quốc", "combo", "Phú Quốc", {}, price=5_000_000))
C2 = Product.from_cdp(P("C2", "Combo VinWonders + buffet", "combo", "Nha Trang", {}, price=900_000))
A2 = Product.from_cdp(P("A2", "Bãi biển Trần Phú", "attraction", "Nha Trang", {"ticketed": False}, price=None))
A3 = Product.from_cdp(P("A3", "Vé VinWonders", "attraction", "Nha Trang", {"ticketed": True}, price=880000))
A4 = Product.from_cdp(P("A4", "Vé chữ", "attraction", "Nha Trang", {"ticketed": "true"}, price=1))
H3 = Product.from_cdp(P("H3", "Villa", "hotel", "Phú Quốc", {"level": "property", "maxOccupancy": 6}, price=None))
R3A = Product.from_cdp(P("R3A", "Villa - A", "hotel", "Phú Quốc", {"level": "room", "parentProductId": "H3", "maxOccupancy": 12},
                         price=9_000_000))
R3B = Product.from_cdp(P("R3B", "Villa - B", "hotel", "Phú Quốc", {"level": "room", "parentProductId": "H3", "maxOccupancy": "4"},
                         price=2_000_000))
R3C = Product.from_cdp(P("R3C", "Villa - C", "hotel", "Phú Quốc", {"level": "room", "parentProductId": "H3", "maxOccupancy": 2},
                         price=None))
R3D = Product.from_cdp(P("R3D", "Villa - D", "hotel", "Phú Quốc", {"level": "room", "parentProductId": "H3"}, price=2_000_000))
UNITS2 = [C1, C2, A2, A3, A4, H3, H1]
KIDS2 = {"H3": [R3A, R3B, R3C, R3D], "H1": [R1, R1B]}
KINDS = {"C1": ["flight", "hotel"], "C2": ["attraction", "meal"], "A3": ["flight"]}   # A3 không phải combo → bỏ qua


@pytest.fixture(scope="module")
def attrs2() -> UnitAttributes:
    return UnitAttributes.build(UNITS2, KIDS2, KINDS)


def test_flags_from_combo_kinds_and_ticketed(attrs2):
    assert FLAGS == {FLAG_INCLUDES_FLIGHT, FLAG_INCLUDES_HOTEL, FLAG_TICKETED}
    assert attrs2.flags[0] == {"includesFlight", "includesHotel"}
    assert attrs2.flags[1] == frozenset()                      # combo không có chặng bay / khách sạn
    assert attrs2.flags[2] == frozenset()                      # ticketed False
    assert attrs2.flags[3] == {"ticketed"}                     # chỉ True thật; kinds của unit không phải combo bị bỏ qua
    assert attrs2.flags[4] == frozenset()                      # "true" (chuỗi) không tính
    assert attrs2.flags[5] == frozenset() and attrs2.flags[6] == frozenset()
    assert UnitAttributes.build(UNITS2, KIDS2).flags[0] == frozenset()   # không truyền thành phần combo → không cờ


def test_max_occupancy_over_unit_and_children(attrs2):
    occ = attrs2.max_occupancy
    assert occ.dtype == np.float64 and occ.shape == (len(UNITS2),)
    assert occ[5] == 12.0                                      # max(6 của property, 12, 2); "4" (chuỗi) bị bỏ
    assert math.isnan(occ[0]) and math.isnan(occ[6])           # không ai khai


def test_children_sorted_by_price_none_last_then_id(attrs2):
    # (id, giá, sức chứa, lịch, đang bán được): phòng không giá chưa bán được trên V-OTA
    assert attrs2.children[5] == (("R3B", 2_000_000.0, None, None, True), ("R3D", 2_000_000.0, None, None, True),
                                  ("R3A", 9_000_000.0, 12.0, None, True), ("R3C", None, 2.0, None, False))
    assert attrs2.children[6] == (("R1", 3_400_000.0, None, None, True), ("R1B", None, None, None, False))
    assert attrs2.children[0] == ()


def test_new_fields_default_when_constructed_by_hand():
    base = UnitAttributes.build(UNITS)
    legacy = UnitAttributes(amenities=base.amenities, brand=base.brand, star_rating=base.star_rating,
                            min_price=base.min_price, origin_city=base.origin_city, destination_city=base.destination_city)
    assert legacy.flags == (frozenset(),) * len(UNITS) and legacy.children == ((),) * len(UNITS)
    assert legacy.max_occupancy.shape == (len(UNITS),) and np.isnan(legacy.max_occupancy).all()
    assert legacy.entities == (frozenset(),) * len(UNITS)              # 1.18.0: không có entity = không gate được
    with pytest.raises(ValueError):
        UnitAttributes(amenities=base.amenities, brand=base.brand, star_rating=base.star_rating, min_price=base.min_price,
                       origin_city=base.origin_city, destination_city=base.destination_city, flags=(frozenset(),))
    with pytest.raises(ValueError):
        UnitAttributes(amenities=base.amenities, brand=base.brand, star_rating=base.star_rating, min_price=base.min_price,
                       origin_city=base.origin_city, destination_city=base.destination_city, entities=(frozenset(),))


# --- entity gazetteer từ TÊN unit (contract 1.18.0, `domain/search/gazetteer.py`): chỉ attraction/combo
def test_entities_from_name_only_for_attraction_and_combo(attrs, attrs2):
    assert len(attrs.entities) == len(UNITS) and len(attrs2.entities) == len(UNITS2)
    assert attrs.entities == (frozenset(), frozenset(), frozenset(), frozenset({"vinwonders"}))   # H1, H2, F1, A1
    assert attrs2.entities == (frozenset(), frozenset({"vinwonders"}), frozenset(), frozenset({"vinwonders"}),
                               frozenset(), frozenset(), frozenset())                                # C1 C2 A2 A3 A4 H3 H1
    assert UnitAttributes.build(UNITS2, KIDS2).entities == attrs2.entities                          # không phụ thuộc kinds/con


def test_entities_cover_brand_sites_and_skip_hotels_named_after_them():
    units = [
        Product.from_cdp(P("S1", "Vé Vinpearl Safari Phú Quốc", "attraction", "Phú Quốc", {}, price=650_000)),
        Product.from_cdp(P("G1", "[Grand World Phú Quốc] Combo vé VinWonders + Safari", "combo", "Phú Quốc", {}, price=1)),
        Product.from_cdp(P("W1", "VinWonders Wave Park & Water Park", "attraction", "Hà Nội", {}, price=1)),
        Product.from_cdp(P("HG", "Khách sạn Grand World Phú Quốc", "hotel", "Phú Quốc", {"level": "property"}, price=None)),
        Product.from_cdp(P("GF", "Sân golf Vinpearl Safari", "golf", "Phú Quốc", {}, price=None)),
        Product.from_cdp(P("N0", "", "attraction", "Phú Quốc", {}, price=None)),
    ]
    assert UnitAttributes.build(units).entities == (
        frozenset({"safari"}), frozenset({"grand_world", "vinwonders", "safari"}), frozenset({"vinwonders", "wave_park"}),
        frozenset(), frozenset(), frozenset(),
    )


def test_existing_fields_unchanged_by_new_arguments(attrs2):
    old = UnitAttributes.build(UNITS2, KIDS2)
    assert old.amenities == attrs2.amenities and (old.brand == attrs2.brand).all()
    assert np.array_equal(old.min_price, attrs2.min_price, equal_nan=True)
    assert np.array_equal(old.star_rating, attrs2.star_rating, equal_nan=True)
    e = UnitAttributes.build([])
    assert e.flags == () and e.children == () and e.max_occupancy.shape == (0,)
