"""Phase A (05/10) — `store/filters.py`: cột RAM `origin_city` / `destination_city` (keyword có thể null), mảng khoá chuỗi
`features`, `not` bọc `and` / `or`, `not(eq brand)` (mustNotBrands của arm APP). Chỉ evaluator pandas `mask()`; `to_weaviate`
phải từ chối rõ các hình dạng này."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from evaluation.search_bench.store import filters as F


@pytest.fixture()
def df():
    # 5 dòng: 2 tuyến bay, 2 khách sạn, 1 điểm tham quan (không tiện ích)
    return pd.DataFrame({
        "variant": ["flight_route", "flight_route", "hotel_property", "hotel_property", "attraction"],
        "taxonomy": ["flight", "flight", "hotel", "hotel", "attraction"],
        "origin_city": ["Buôn Ma Thuột", "Hà Nội", "", "", ""],
        "destination_city": ["Hà Nội", "Đà Nẵng", "", "", ""],
        "features": [[], [], ["pool", "kitchen"], ["balcony"], None],
        "amenity_ids": [[], [], [1, 2], [3], None],
        "brand": [None, None, "Vinpearl", "Mường Thanh", None],
    })


ROUTE_BMT_HN = {"and": [{"eq": ["variant", "flight_route"]},
                        {"not": {"and": [{"eq": ["origin_city", "Buôn Ma Thuột"]}, {"eq": ["destination_city", "Hà Nội"]}]}}]}


def test_validate_accepts_phase_a_shapes():
    F.validate(ROUTE_BMT_HN)
    F.validate({"and": [{"eq": ["variant", "flight_route"]}, {"not": {"eq": ["destination_city", "Hà Nội"]}}]})
    F.validate({"contains_any": ["features", ["pool"]]})
    F.validate({"not": {"contains_any": ["features", ["pool", "kitchen"]]}})
    F.validate({"not": {"or": [{"eq": ["taxonomy", "hotel"]}, {"eq": ["origin_city", "Hà Nội"]}]}})
    F.validate({"in": ["origin_city", ["Hà Nội", "Đà Nẵng"]]})
    F.validate({"not": {"eq": ["brand", "Vinpearl"]}})                      # mustNotBrands của arm APP


@pytest.mark.parametrize("bad, msg", [
    ({"not": {"eq": ["province", "Khánh Hoà"]}}, "not chỉ bọc"),              # province có thể null, không trong NOT_EQ_NULLABLE
    ({"contains_any": ["features", [1]]}, "khoá chuỗi"),                       # features chỉ nhận chuỗi
    ({"contains_all": ["features", []]}, "khác rỗng"),
    ({"not": {"lte": ["unit_price_min", 5]}}, "not chỉ bọc"),
    ({"eq": ["features", "pool"]}, "eq features"),
])
def test_validate_rejects(bad, msg):
    with pytest.raises(F.FilterError, match=msg):
        F.validate(bad)


def test_resolve_keeps_features_as_strings():
    idx = F.amenity_key_index({"1": {"key": "pool"}})
    node = {"and": [{"contains_any": ["features", ["kitchen", "pool", "pool"]]}, {"contains_all": ["amenity_ids", ["pool"]]}]}
    assert F.resolve(node, idx) == {"and": [{"contains_any": ["features", ["kitchen", "pool"]]}, {"contains_all": ["amenity_ids", [1]]}]}
    assert F.resolve(ROUTE_BMT_HN, idx) == ROUTE_BMT_HN


def test_mask_features(df):
    assert F.mask({"contains_any": ["features", ["pool"]]}, df).tolist() == [False, False, True, False, False]
    assert F.mask({"contains_all": ["features", ["pool", "kitchen"]]}, df).tolist() == [False, False, True, False, False]
    # phủ định tiện ích: giữ dòng không ghi nhận (mảng rỗng / None)
    assert F.mask({"not": {"contains_any": ["features", ["pool"]]}}, df).tolist() == [True, True, False, True, True]


def test_mask_route_direction(df):
    # chặng khác BMT→HN trong các tuyến bay: chỉ HN→ĐN; khách sạn / điểm tham quan không bị cấm
    assert F.mask(ROUTE_BMT_HN, df).tolist() == [False, True, False, False, False]
    dest_hn = {"and": [{"eq": ["variant", "flight_route"]}, {"not": {"eq": ["destination_city", "Hà Nội"]}}]}
    assert F.mask(dest_hn, df).tolist() == [False, True, False, False, False]
    # not(eq) trên keyword có thể null: chuỗi rỗng cũng là "không phải Hà Nội"
    assert F.mask({"not": {"eq": ["origin_city", "Hà Nội"]}}, df).tolist() == [True, False, True, True, True]
    assert F.mask({"not": {"or": [{"eq": ["taxonomy", "hotel"]}, {"eq": ["origin_city", "Hà Nội"]}]}}, df).tolist() == \
        [True, False, False, False, True]


def test_mask_not_eq_brand_keeps_unbranded(df):
    # mustNotBrands: "không phải Vinpearl" giữ cả dòng không ghi thương hiệu (None)
    assert F.mask({"not": {"eq": ["brand", "Vinpearl"]}}, df).tolist() == [True, True, False, True, True]
    assert F.mask({"eq": ["brand", "Vinpearl"]}, df).tolist() == [False, False, True, False, False]


def test_to_weaviate_refuses_ram_only_shapes():
    for node in (ROUTE_BMT_HN, {"contains_any": ["features", ["pool"]]}, {"eq": ["origin_city", "Hà Nội"]},
                 {"not": {"eq": ["destination_city", "Hà Nội"]}}, {"not": {"and": [{"eq": ["taxonomy", "hotel"]}]}},
                 {"not": {"eq": ["brand", "Vinpearl"]}}):
        with pytest.raises(F.FilterError, match="to_weaviate"):
            F.to_weaviate(node)
    # hình dạng cũ vẫn dựng được; brand là thuộc tính thật của collection nên `eq brand` vẫn dựng được
    assert F.to_weaviate({"not": {"eq": ["taxonomy", "hotel"]}}) is not None
    assert F.to_weaviate({"eq": ["brand", "Vinpearl"]}) is not None


def test_old_amenity_ids_semantics_unchanged(df):
    assert F.mask({"contains_any": ["amenity_ids", [1]]}, df).tolist() == [False, False, True, False, False]
    assert F.mask({"not": {"contains_any": ["amenity_ids", [3]]}}, df).tolist() == [True, True, True, False, True]
    assert F.mask(None, df).all() and F.mask(None, df).dtype == np.bool_
