"""Part 3 — evaluator tham chiếu, validator, sinh filter tất định."""
from __future__ import annotations

import json

import numpy as np
import pytest

from evaluation.vector_bench.filters import (EARTH_R_M, InvalidFilter, Table, boundary, haversine_m, mask, strict_mask,
                                             validate)
from evaluation.vector_bench.querygen import generate_filters


def _r(i, **kw):
    base = {"id": f"id{i}", "variant": "hotel_property", "taxonomy": "hotel", "destination": "Nha Trang", "available": True,
            "amenity_ids": [], "unit_price": 1000.0, "star_rating": 4.0, "lat": 12.0, "lon": 109.0}
    return {**base, **kw}


@pytest.fixture()
def t():
    return Table.from_records([
        _r(0, amenity_ids=[1, 2, 3], unit_price=None, star_rating=None),
        _r(1, amenity_ids=[], unit_price=500.0),
        _r(2, amenity_ids=[1, 2], destination="Phú Quốc", taxonomy="attraction", variant="attraction", unit_price=2000.0),
        _r(3, amenity_ids=[3], available=False, star_rating=5.0),
    ])


def test_range_never_matches_null(t):
    assert mask({"range": ["unit_price", {"lte": 10_000}]}, t).tolist() == [False, True, True, True]
    assert mask({"range": ["star_rating", {"gte": 0}]}, t).tolist() == [False, True, True, True]
    assert mask({"range": ["unit_price", {"gt": 500, "lt": 2000}]}, t).tolist() == [False, False, False, True]


def test_not_any_on_empty_array_matches(t):
    # mảng rỗng thoả not any — "không có dữ liệu ≠ có"
    assert mask({"not": {"any": ["amenity_ids", [3]]}}, t).tolist() == [False, True, True, False]


def test_all_three_ids(t):
    assert mask({"all": ["amenity_ids", [1, 2, 3]]}, t).tolist() == [True, False, False, False]
    assert mask({"all": ["amenity_ids", [1, 2]]}, t).tolist() == [True, False, True, False]
    assert mask({"all": ["amenity_ids", [99]]}, t).tolist() == [False] * 4       # id ngoài vocab


def test_or_and_in(t):
    f = {"or": [{"in": ["destination", ["Phú Quốc", "Hội An"]]}, {"eq": ["available", False]}]}
    assert mask(f, t).tolist() == [False, False, True, True]
    assert mask({"in": ["taxonomy", ["golf"]]}, t).tolist() == [False] * 4


def test_mask_returns_fresh_array(t):
    f = {"eq": ["destination", "Nha Trang"]}
    m = mask(f, t)
    m[:] = False                                            # sửa kết quả không được làm hỏng cache của Table
    assert mask(f, t).tolist() == [True, True, False, True]


def test_geo_inside_outside_boundary():
    lat0, lon0 = 12.0, 109.0
    r = 5000.0

    def at(dist_m):   # điểm cách tâm dist_m về phía bắc
        return lat0 + np.degrees(dist_m / EARTH_R_M)
    tb = Table.from_records([_r(0, lat=at(1000), lon=lon0), _r(1, lat=at(4990), lon=lon0), _r(2, lat=at(5010), lon=lon0),
                             _r(3, lat=at(9000), lon=lon0)])
    f = {"geo": {"lat": lat0, "lon": lon0, "radius_m": r}}
    assert mask(f, tb).tolist() == [True, True, False, False]
    tol = 0.005                                            # ±25 m quanh 5 km
    assert boundary(f, tb, tol).tolist() == [False, True, True, False]
    m, b = strict_mask(f, tb, tol)
    assert (m & ~b).tolist() == [True, False, False, False]
    d = haversine_m(lat0, lon0, np.array([at(1000)]), np.array([lon0]))
    assert abs(d[0] - 1000) < 0.01


@pytest.mark.parametrize("bad", [
    {"not": {"range": ["unit_price", {"lte": 5}]}},        # not trên trường nullable
    {"all": ["amenity_ids", []]},
    {"any": ["amenity_ids", []]},
    {"not": {"geo": {"lat": 1.0, "lon": 1.0, "radius_m": 10.0}}},
    {"eq": ["unit_price", 5]},
    {"range": ["unit_price", {"eq": 5}]},
    {"and": []},
    {"in": ["destination", []]},
    {"foo": 1},
])
def test_validator_rejects(bad):
    with pytest.raises(InvalidFilter):
        validate(bad)


def test_validator_accepts():
    validate(None)
    validate({"and": [{"eq": ["destination", "Nha Trang"]}, {"not": {"any": ["amenity_ids", [3]]}},
                      {"not": {"eq": ["available", False]}}, {"range": ["star_rating", {"gte": 4}]},
                      {"geo": {"lat": 12.0, "lon": 109.0, "radius_m": 1000}}, {"id_in": ["a"]}]})


def test_generated_filters_deterministic_and_nmatch_consistent(cfg):
    rng = np.random.default_rng(0)
    recs = []
    dests = ["Nha Trang", "Phú Quốc", "Đà Nẵng", "Hội An"]
    for i in range(3000):
        v = ["hotel_property", "attraction", "combo"][i % 3]
        tax = {"hotel_property": "hotel", "attraction": "attraction", "combo": "combo"}[v]
        recs.append(_r(i, variant=v, taxonomy=tax, destination=dests[int(rng.integers(4))],
                       amenity_ids=sorted({int(x) for x in rng.integers(1, 12, size=int(rng.integers(0, 6)))}),
                       unit_price=None if rng.random() < 0.1 else float(rng.lognormal(13, 0.5)),
                       star_rating=None if rng.random() < 0.5 else float(rng.integers(3, 6)),
                       lat=12 + rng.normal(0, 0.05), lon=109 + rng.normal(0, 0.05), available=bool(rng.random() < 0.9)))
    t = Table.from_records(recs)
    a, _ = generate_filters(t, cfg, seed=7)
    b, _ = generate_filters(Table.from_records(recs), cfg, seed=7)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    for q in a:
        validate(q["filter"])
        assert int(mask(q["filter"], t).sum()) == q["n_match"]


def test_take_matches_full_mask_and_builds_csr_once(t):
    f = {"and": [{"any": ["amenity_ids", [1, 3]]}, {"range": ["unit_price", {"lte": 5000}]}]}
    full = mask(f, t)
    rows = np.array([3, 0, 2])
    assert mask(f, t.take(rows)).tolist() == full[rows].tolist()
    csr = t._amen_csr
    t.take(np.array([1]))
    assert csr is not None and t._amen_csr is csr                  # không chuyển CSC→CSR lại mỗi lần
