"""Part 1 — 7 variant (có attraction ticketed=false, property không có phòng): đúng variant, min giá, hợp amenity."""
from __future__ import annotations

from evaluation.vector_bench.dataset import amenities
from evaluation.vector_bench.dataset.catalog import build_items, variant_of
from evaluation.vector_bench.lexical import fold, strip_accents


def _rec(pid, name, tax, attrs, price=None, dest="Nha Trang"):
    a = {"latitude": 12.24, "longitude": 109.19, "province": "Khánh Hòa", **attrs}
    return {"productId": pid, "name": name, "taxonomy": tax, "destination": dest, "description": "Mô tả ngắn về sản phẩm.",
            "attributes": a, "unitPrice": price, "currency": "VND", "available": True}


RECORDS = [
    _rec("P1", "Khách sạn A", "hotel", {"level": "property", "starRating": 5.0, "amenities": ["Hồ bơi ngoài trời", "WiFi miễn phí"]},
         price=9_000_000),
    _rec("R1", "Khách sạn A - Deluxe", "hotel", {"level": "room", "parentProductId": "P1", "roomName": "Deluxe",
                                                 "amenities": ["Phòng tập", "Wi-Fi ở nơi công cộng"]}, price=2_000_000),
    _rec("R2", "Khách sạn A - Suite", "hotel", {"level": "room", "parentProductId": "P1", "roomName": "Suite"}, price=3_500_000),
    _rec("P2", "Nhà nghỉ B", "hotel", {"level": "property", "amenities": ["Bể bơi [ngoài trời]"]}, price=700_000),   # không có phòng
    _rec("FR", "Vé máy bay Hà Nội - Nha Trang", "flight", {"level": "route", "originCity": "Hà Nội", "destinationCity": "Nha Trang"}),
    _rec("F1", "Vé máy bay Hà Nội - Nha Trang", "flight", {"level": "flight", "parentProductId": "FR", "airline": "VietJet Air"},
         price=1_500_000),
    _rec("F2", "Vé máy bay Hà Nội - Nha Trang", "flight", {"level": "flight", "parentProductId": "FR", "airline": "Vietnam Airlines"},
         price=1_200_000),
    _rec("A1", "Tháp Bà Ponagar", "attraction", {"ticketed": False}, price=None),
    _rec("C1", "Combo 3N2Đ", "combo", {}, price=5_000_000),
    _rec("G1", "Sân golf Vinpearl", "golf", {}, price=2_500_000),
]


def test_variant_of_all_seven():
    got = {r["productId"]: variant_of(r) for r in RECORDS}
    assert got == {"P1": "hotel_property", "R1": "hotel_room", "R2": "hotel_room", "P2": "hotel_property",
                   "FR": "flight_route", "F1": "flight", "F2": "flight", "A1": "attraction", "C1": "combo", "G1": "golf"}


def test_items_min_price_amenity_union_and_units(cfg):
    df, vocab, stats = build_items(RECORDS, cfg, use_backend_builder=False)
    by = df.set_index("id")
    assert set(by.index) == {"P1", "P2", "FR", "A1", "C1", "G1"}            # phòng, chuyến bay không thành dòng riêng
    assert stats["n_search_units"] == 6
    assert by.loc["P1", "unit_price"] == 2_000_000                           # min giá phòng con, không lấy giá property
    assert by.loc["P2", "unit_price"] == 700_000                             # property không phòng: giá của chính nó
    assert by.loc["FR", "unit_price"] == 1_200_000                           # route: min giá chuyến con
    assert by.loc["A1", "unit_price"] is None or by.loc["A1", "unit_price"] != by.loc["A1", "unit_price"]   # null
    assert by.loc["P1", "n_children"] == 2 and by.loc["FR", "n_children"] == 2
    key_of = {i: e["key"] for i, e in vocab.entries.items()}
    p1 = {key_of[i] for i in by.loc["P1", "amenity_ids"]}
    assert p1 == {"pool", "wifi", "fitness"}                                  # hợp property + phòng con, alias đã gộp
    assert {key_of[i] for i in by.loc["P2", "amenity_ids"]} == {"pool"}      # "Bể bơi [ngoài trời]" → pool (cụm token)
    assert "không cần vé" in by.loc["A1", "embed_text"]
    assert "5 sao" in by.loc["P1", "embed_text"] and "Deluxe" in by.loc["P1", "embed_text"]
    assert all(t.strip() for t in df["embed_text"])


def test_fold_and_matcher():
    assert fold("Hồ bơi Ngoài-Trời!") == "ho boi ngoai troi"
    assert fold("Đưa đón sân bay") == "dua don san bay"
    assert strip_accents("Khách Sạn Đà Nẵng") == "Khach San Da Nang"
    m = amenities.AmenityMatcher(amenities.load_seed())
    assert m.match("Pool bar") == ("seed", "bar")          # alias dài nhất thắng ("pool bar" 2 token > "pool")
    assert m.match("Xe đưa đón sân bay") == ("seed", "airport_shuttle")
    assert m.match("TV màn hình phẳng") == ("raw", "tv man hinh phang")


def test_raw_min_freq_and_id_order():
    m = amenities.AmenityMatcher(amenities.load_seed())
    units = [["Minibar", "Hồ bơi"]] * 5 + [["Ghế sofa"]] * 2
    vocab, ids = amenities.build_vocab(units, m, min_freq=5)
    keys = [vocab.entries[i]["key"] for i in sorted(vocab.entries)]
    seed_keys = sorted(s.key for s in amenities.load_seed())
    assert keys[: len(seed_keys)] == seed_keys                   # seed theo alphabet trước
    assert keys[len(seed_keys):] == ["raw:minibar"]              # raw ≥ min_freq, "ghe sofa" (2 lần) bị bỏ
    assert vocab.dropped_distinct == 1 and vocab.dropped_occurrences == 2
    assert ids[-1] == []
