"""`UnitIndex.mask` mở rộng cho filter cứng Phase A (F3/F5/F6) + hai hàm hỗ trợ ở `domain/search/scoring.py`.

Mặc định phải giữ nguyên hành vi cũ; quy ước "không biết" theo spec §2.7 [C2]: giá NaN bị loại khi có biên giá,
sao NaN được giữ, tiện ích vắng khoá được giữ."""
import numpy as np
import pytest

from src.backend.app.application.ports import UnitIndex
from src.backend.app.domain.catalog import Product, UnitAttributes
from src.backend.app.domain.search.scoring import revalidate, soft_star_order
from src.backend.tests.conftest import P

ROWS = [
    P("H1", "Resort A", "hotel", "Nha Trang", {"level": "property", "starRating": 5, "amenities": ["Hồ bơi", "Bãi biển riêng"]}, price=None),
    P("H2", "Khách sạn B", "hotel", "Nha Trang", {"level": "property", "starRating": 3}, price=None),
    P("H3", "Resort C", "hotel", "Phú Quốc", {"level": "property"}, price=None),                           # sao không biết
    P("F1", "HAN - CXR", "flight", "Nha Trang", {"level": "route", "originCity": "Hà Nội", "destinationCity": "Nha Trang"}, price=None),
    P("F2", "SGN - CXR", "flight", "Nha Trang", {"level": "route", "originCity": "Hồ Chí Minh", "destinationCity": "Nha Trang"}, price=None),
    P("A1", "VinWonders", "attraction", "Nha Trang", {}, price=880000, avail=False),
]
CHILD_ROWS = {
    "H1": [P("R1", "Deluxe", "hotel", "Nha Trang", {"level": "room", "parentProductId": "H1", "amenities": ["Sân golf"]}, price=3400000)],
    "H2": [P("R2", "Standard", "hotel", "Nha Trang", {"level": "room", "parentProductId": "H2"}, price=900000)],
    # H3 không có con → giá NaN
}
IDS = [r["productId"] for r in ROWS]


def _index(with_attrs: bool = True) -> UnitIndex:
    units = [Product.from_cdp(r) for r in ROWS]
    children = {pid: [Product.from_cdp(k) for k in kids] for pid, kids in CHILD_ROWS.items()}
    kw = {"attrs": UnitAttributes.build(units, children)} if with_attrs else {}
    return UnitIndex(units=units, taxonomy=np.array([p.taxonomy for p in units]),
                     destination=np.array([p.destination for p in units]),
                     available=np.array([p.available for p in units]), recommendable=np.ones(len(units), dtype=bool),
                     parent_of={k["productId"]: pid for pid, kids in CHILD_ROWS.items() for k in kids}, model_version="t", **kw)


@pytest.fixture(scope="module")
def ix() -> UnitIndex:
    return _index()


def ids(ix: UnitIndex, m: np.ndarray) -> list[str]:
    return [ix.units[i].product_id for i in np.flatnonzero(m)]


# --- mặc định không đổi hành vi cũ
def test_defaults_match_legacy_mask(ix):
    legacy = ix.available.copy()
    assert (ix.mask() == legacy).all()
    assert (ix.mask(only_available=False) == np.ones(len(IDS), dtype=bool)).all()
    assert ids(ix, ix.mask(taxonomy="hotel")) == ["H1", "H2", "H3"]
    assert ids(ix, ix.mask(taxonomy=["hotel", "flight"], destination="Nha Trang")) == ["H1", "H2", "F1", "F2"]


def test_attrs_is_built_from_units_when_omitted():
    ix = _index(with_attrs=False)
    assert ix.attrs is not None and len(ix.attrs) == len(IDS)
    assert np.isnan(ix.attrs.min_price[0])                      # không có con → H1 không có giá
    assert ix.attrs.amenities[0] == {"pool", "privateBeach", "nearBeach"}


# --- F3: phủ định tiện ích
def test_exclude_amenities_drops_only_units_with_the_key(ix):
    assert ids(ix, ix.mask(exclude_amenities=["pool"])) == ["H2", "H3", "F1", "F2"]
    assert ids(ix, ix.mask(exclude_amenities={"golf"})) == ["H2", "H3", "F1", "F2"]        # khoá từ phòng con
    assert ids(ix, ix.mask(exclude_amenities=["spa"])) == ["H1", "H2", "H3", "F1", "F2"]   # không ai ghi spa → giữ hết
    assert (ix.mask(exclude_amenities=()) == ix.mask()).all()


# --- F6: giá
def test_price_excludes_nan_only_when_a_bound_is_given(ix):
    assert "H3" in ids(ix, ix.mask())                                                # không biên → NaN giữ
    assert ids(ix, ix.mask(price_max=1_000_000)) == ["H2"]
    assert ids(ix, ix.mask(price_min=1_000_000)) == ["H1"]
    assert ids(ix, ix.mask(price_min=900_000, price_max=3_400_000)) == ["H1", "H2"]     # biên đóng
    assert ids(ix, ix.mask(price_min=0)) == ["H1", "H2"]                                # biên 0 vẫn là biên → loại NaN
    assert ids(ix, ix.mask(price_min=0, only_available=False)) == ["H1", "H2", "A1"]


# --- F6: sao
def test_star_min_keeps_unknown_and_drops_known_low(ix):
    assert ids(ix, ix.mask(taxonomy="hotel", star_min=4)) == ["H1", "H3"]
    assert ids(ix, ix.mask(taxonomy="hotel", star_min=5)) == ["H1", "H3"]
    assert ids(ix, ix.mask(taxonomy="hotel", star_min=3)) == ["H1", "H2", "H3"]


def test_star_known_ok(ix):
    assert ids(ix, ix.star_known_ok(4)) == ["H1"]
    assert ids(ix, ix.star_known_ok(3)) == ["H1", "H2"]
    assert ix.star_known_ok(4).dtype == bool and ix.star_known_ok(4).shape == (len(IDS),)


# --- F5: chặng bay
def test_origin_destination_equality(ix):
    assert ids(ix, ix.mask(origin_city="Hà Nội")) == ["F1"]
    assert ids(ix, ix.mask(destination_city="Nha Trang")) == ["F1", "F2"]
    assert ids(ix, ix.mask(origin_city="Hồ Chí Minh", destination_city="Nha Trang")) == ["F2"]
    assert ids(ix, ix.mask(origin_city="Đà Nẵng")) == []
    assert (ix.mask(origin_city="", destination_city=None) == ix.mask()).all()           # rỗng = không lọc


def test_filters_combine_with_and(ix):
    m = ix.mask(taxonomy="hotel", destination="Nha Trang", star_min=4, exclude_amenities=["pool"])
    assert ids(ix, m) == []
    assert ix.allowed_ids(m) == []
    assert ix.allowed_ids(ix.mask(only_available=False)) is None


# --- scoring helpers
def test_soft_star_order_is_stable_partition():
    known_ok = np.array([False, True, False, True, True])
    assert soft_star_order([4, 2, 0, 1, 3], known_ok) == [4, 1, 3, 2, 0]
    assert soft_star_order([], known_ok) == []
    assert soft_star_order([0, 2], known_ok) == [0, 2]
    assert soft_star_order((1, 3), known_ok) == [1, 3]


def test_revalidate_drops_masked_out_and_counts():
    mask = np.array([True, False, True, False])
    assert revalidate([3, 2, 1, 0], mask) == ([2, 0], 2)
    assert revalidate([0, 2], mask) == ([0, 2], 0)
    assert revalidate([], mask) == ([], 0)


# --- kiến trúc Phase A/B §6: loại taxonomy, cờ, sức chứa; lọc phòng/chuyến con
ROWS2 = [
    P("H1", "Resort A", "hotel", "Nha Trang", {"level": "property", "maxOccupancy": 2}, price=None),
    P("H2", "Villa B", "hotel", "Phú Quốc", {"level": "property"}, price=None),                       # sức chứa từ con
    P("H3", "Khách sạn C", "hotel", "Nha Trang", {"level": "property"}, price=None),                  # không biết sức chứa
    P("C1", "Combo bay + ở", "combo", "Phú Quốc", {}, price=5_000_000),
    P("C2", "Combo vé + buffet", "combo", "Nha Trang", {}, price=900_000),
    P("A1", "Vé VinWonders", "attraction", "Nha Trang", {"ticketed": True}, price=880_000),
    P("A2", "Bãi biển", "attraction", "Nha Trang", {"ticketed": False}, price=None),
]
CHILD_ROWS2 = {
    "H2": [P("R2A", "Villa B - 12 khách", "hotel", "Phú Quốc", {"level": "room", "parentProductId": "H2", "maxOccupancy": 12}, price=9_000_000),
           P("R2B", "Villa B - 4 khách", "hotel", "Phú Quốc", {"level": "room", "parentProductId": "H2", "maxOccupancy": 4}, price=2_500_000),
           P("R2C", "Villa B - giá ẩn", "hotel", "Phú Quốc", {"level": "room", "parentProductId": "H2", "maxOccupancy": 6}, price=None),
           P("R2D", "Villa B - chưa rõ", "hotel", "Phú Quốc", {"level": "room", "parentProductId": "H2"}, price=3_000_000)],
    "H3": [P("R3A", "C - Standard", "hotel", "Nha Trang", {"level": "room", "parentProductId": "H3"}, price=700_000)],
}
KINDS2 = {"C1": ["flight", "hotel"], "C2": ["attraction", "meal"]}


@pytest.fixture(scope="module")
def ix2() -> UnitIndex:
    units = [Product.from_cdp(r) for r in ROWS2]
    children = {pid: [Product.from_cdp(k) for k in kids] for pid, kids in CHILD_ROWS2.items()}
    return UnitIndex(units=units, taxonomy=np.array([p.taxonomy for p in units]),
                     destination=np.array([p.destination for p in units]),
                     available=np.array([p.available for p in units]), recommendable=np.ones(len(units), dtype=bool),
                     parent_of={k["productId"]: pid for pid, kids in CHILD_ROWS2.items() for k in kids}, model_version="t",
                     attrs=UnitAttributes.build(units, children, KINDS2))


def test_new_kwargs_defaults_identical(ix, ix2):
    for index in (ix, ix2):
        for kw in ({}, {"only_available": False}, {"taxonomy": "hotel"}, {"price_max": 3_000_000}, {"star_min": 4},
                   {"exclude_amenities": ["pool"]}, {"destination": "Nha Trang", "origin_city": "Hà Nội"}):
            assert (index.mask(**kw) == index.mask(**kw, exclude_taxonomies=(), exclude_flags=(), min_occupancy=None)).all()
            assert (index.mask(**kw) == index.mask(**kw, exclude_taxonomies=[""], exclude_flags=[""])).all()   # rỗng = không lọc


def test_exclude_taxonomies(ix2):
    assert ids(ix2, ix2.mask(exclude_taxonomies=["combo"])) == ["H1", "H2", "H3", "A1", "A2"]
    assert ids(ix2, ix2.mask(exclude_taxonomies={"combo", "attraction"})) == ["H1", "H2", "H3"]
    assert ids(ix2, ix2.mask(taxonomy="hotel", exclude_taxonomies=["hotel"])) == []
    assert ids(ix2, ix2.mask(exclude_taxonomies=["golf"])) == [r["productId"] for r in ROWS2]   # không ai là golf


def test_exclude_flags_drops_only_units_with_the_flag(ix2):
    assert ids(ix2, ix2.mask(exclude_flags=["includesFlight"])) == ["H1", "H2", "H3", "C2", "A1", "A2"]
    assert ids(ix2, ix2.mask(exclude_flags={"ticketed", "includesHotel"})) == ["H1", "H2", "H3", "C2", "A2"]
    assert ids(ix2, ix2.mask(taxonomy="combo", exclude_flags=["includesFlight"])) == ["C2"]


def test_min_occupancy_keeps_unknown_drops_known_small(ix2):
    assert ix2.attrs.max_occupancy[1] == 12.0                                       # H2 = max của con
    assert ids(ix2, ix2.mask(taxonomy="hotel", min_occupancy=4)) == ["H2", "H3"]    # H1 = 2 bị loại; H3 không biết → giữ
    assert ids(ix2, ix2.mask(taxonomy="hotel", min_occupancy=2)) == ["H1", "H2", "H3"]
    assert ids(ix2, ix2.mask(taxonomy="hotel", min_occupancy=13)) == ["H3"]


def test_matched_children(ix2):
    h2, h3 = ix2.idx["H2"], ix2.idx["H3"]
    assert ix2.matched_children(h2) == []                                           # không điều kiện → []
    assert ix2.matched_children(h2, price_max=3_000_000) == ["R2B", "R2D"]          # giá null (R2C) bị loại khi có biên
    assert ix2.matched_children(h2, price_min=2_600_000) == ["R2D", "R2A"]          # thứ tự đã lưu = giá tăng dần
    assert ix2.matched_children(h2, min_occupancy=6) == ["R2D", "R2A", "R2C"]       # R2D không biết sức chứa → giữ; R2B 4 < 6
    assert ix2.matched_children(h2, price_max=3_000_000, min_occupancy=6) == ["R2D"]
    assert ix2.matched_children(h2, min_occupancy=1, limit=2) == ["R2B", "R2D"]
    assert ix2.matched_children(h2, min_occupancy=1, limit=0) == []
    assert ix2.matched_children(h3, price_max=500_000) == [] and ix2.matched_children(h3, price_max=700_000) == ["R3A"]
    assert ix2.matched_children(ix2.idx["C1"], price_max=10**9) == []               # không có con
