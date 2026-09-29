from __future__ import annotations

import pandas as pd
import pytest

from evaluation.search_bench import catalog_lookup as C
from evaluation.search_bench.store import filters as F

VOCAB = {"1": {"key": "pool", "label": "hồ bơi", "source": "seed", "freq": 3},
         "2": {"key": "spa", "label": "spa", "source": "seed", "freq": 2},
         "3": {"key": "raw:ban-lam-viec", "label": "Bàn làm việc", "source": "raw", "freq": 1}}


def _items() -> pd.DataFrame:
    rows = [
        ("p1", "Vinpearl Resort Nha Trang", "Vinpearl", "hotel_property", "Nha Trang", "Khánh Hòa", 5.0, 2_000_000, [1, 2], ["Villa"], 3),
        ("p2", "Khách sạn Biển Nha Trang", "", "hotel_property", "Nha Trang", "Khánh Hòa", 3.0, 600_000, [1], ["Deluxe"], 2),
        ("p3", "Khách sạn Cầu Rồng", "", "hotel_property", "Đà Nẵng", "Đà Nẵng", 4.0, 900_000, [3], [], 1),
        ("p4", "VinWonders Nha Trang", "", "attraction", "Nha Trang", "Khánh Hòa", None, 800_000, [], [], 0),
        ("p5", "Hostel - Ha Giang Loop Office", "", "hotel_property", "Hà Nội", "Hà Nội", None, 200_000, [2], [], 0),
    ]
    cols = ["product_id", "name", "brand", "variant", "destination", "province", "star_rating", "unit_price_min",
            "amenity_ids", "room_vocab", "n_children"]
    df = pd.DataFrame(rows, columns=cols)
    df["city"] = None
    return df


@pytest.fixture()
def cat():
    return C.catalog_from(_items(), VOCAB)


def test_destination_table(cat):
    t = C.destination_table(cat)
    assert list(t.columns) == ["điểm đến", *C.VARIANTS, "tổng"]
    assert t.iloc[0]["điểm đến"] == "Nha Trang" and t.iloc[0]["tổng"] == 3 and t["tổng"].sum() == 5
    assert t.set_index("điểm đến").loc["Nha Trang", "attraction"] == 1


def test_criteria_filter_matches_filters_module(cat):
    f = C.criteria_filter(destinations=["Nha Trang"], variants=["hotel_property"], star_min=4, price_max=2_500_000,
                          amenities_all=["pool"], amenities_none=["raw:ban-lam-viec"])
    F.validate(f)
    assert f["and"][0] == {"eq": ["destination", "Nha Trang"]} and f["and"][2] == {"gte": ["star_rating", 4]}
    assert list(cat.items.index[C.filter_mask(cat, f)]) == ["p1"]
    assert C.criteria_filter() is None and C.filter_mask(cat, None).all()
    assert C.criteria_filter(destinations=["A", "B"]) == {"in": ["destination", ["A", "B"]]}


def test_search_words_any_order_without_diacritics(cat):
    res = C.search(cat, text="nha trang vinpearl")
    assert list(res["product_id"]) == ["p1"]
    res = C.search(cat, text="nha trang")
    assert res.iloc[0]["loại"] == "hotel_property" and set(res["product_id"]) == {"p1", "p2", "p4"}
    assert C.search(cat, text="khach san", filter_ast={"eq": ["destination", "Đà Nẵng"]})["product_id"].tolist() == ["p3"]
    assert "hồ bơi" in C.search(cat, text="vinpearl").iloc[0]["tiện ích"]


def test_place_hits_whole_phrase(cat):
    assert len(C.place_hits(cat, "Hà Giang")) == 1                       # tên sản phẩm (bài học c0571)
    assert len(C.place_hits(cat, "khanh hoa")) == 3                      # tỉnh
    assert len(C.place_hits(cat, "Cà Mau")) == 0 and len(C.place_hits(cat, "")) == 0
    assert len(C.place_hits(cat, "Giang Lo")) == 0                       # nguyên cụm từ, không phải chuỗi con


def test_amenity_coverage(cat):
    cov = C.amenity_coverage(cat, "Nha Trang")
    assert cov.iloc[0]["khoá"] == "pool" and cov.iloc[0]["tỷ lệ có"] == 1.0
    assert cov.set_index("khoá").loc["spa", "tỷ lệ có"] == 0.5
    assert C.known_refs(cat, ["p1", "zz"]) == (["p1"], ["zz"])


def test_load_catalog_on_sample(cfg, home):
    from evaluation.search_bench import catalog
    catalog.build_catalog(cfg, "sample")
    cat = C.load_catalog("sample")
    assert len(C.destination_table(cat)["tổng"]) and int(C.destination_table(cat)["tổng"].sum()) == len(cat.items)
    assert len(C.search(cat, text="")) == min(200, len(cat.items))


def test_describe_label_context(cat):
    info = C.describe(cat, ["p2", "zz", "p1", "p2"])
    assert list(info["product_id"]) == ["p2", "p1"]
    assert C.short_label(cat, "p1") == "Vinpearl Resort Nha Trang · hotel_property · Nha Trang · 5★ · từ 2.000.000đ"
    assert "không có trong catalog" in C.short_label(cat, "zz")
    assert C.context_of(cat, ["p1", "p2", "p3"]) == ("Nha Trang", "hotel_property")
    assert C.context_of(cat, ["zz"]) == (None, None)
