"""Thuộc tính lọc theo unit (`domain/catalog/unit_attributes.py`): tiện ích + con, giá thấp nhất, sao, chặng bay; thuần."""
import math

import numpy as np
import pytest

from src.backend.app.domain.catalog import Product, UnitAttributes
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
