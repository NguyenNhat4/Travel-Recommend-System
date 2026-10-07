"""Kiến trúc Phase A trong `SearchProducts` — filter-first cho F3 phủ định, F4 loại sản phẩm, F5 chiều bay, F6 giá/sao (cờ mặc định
tắt; tham số request tường minh luôn áp; F rỗng không nới).

Fixture (tests/conftest.py ROWS): H1 Vinpearl Resort Nha Trang (5 sao, amenities bãi biển riêng + hồ bơi, phòng R1 3,4 M), H2 Khách sạn B
Nha Trang (4 sao, không tiện ích, không giá), H3 Resort Phú Quốc (5 sao, phòng R3 5 M), F1 tuyến Hà Nội → Nha Trang (chuyến FL1 1,89 M),
A1 VinWonders Nha Trang 880 k, A2 Bãi biển Trần Phú (không giá), C1 Combo 9,8 M, G1 Vinpearl Golf Nha Trang 2 M."""
import json

from jsonschema import Draft202012Validator

from src.backend.app.application.itinerary.tool_contracts import contracts
from src.backend.app.application.search import SearchProducts
from src.backend.app.domain.search import HybridConfig
from src.backend.tests.conftest import FakeEmbedder

ALL = dict(negation_filter=True, taxonomy_filter=True, route_filter=True, numeric_filter=True)


class SpyEmbedder(FakeEmbedder):
    calls = 0

    def embed_query(self, q):
        self.calls += 1
        return super().embed_query(q)


def _engine(services, **kw):
    kw.setdefault("cutoff", -1.0)
    return SearchProducts(services["index"], services["vectors"], kw.pop("embedder", FakeEmbedder()), **kw)


def _ids(r):
    return [x["productId"] for x in r["results"]]


def _strip(r: dict) -> dict:
    d = {k: v for k, v in r["diagnostics"].items() if k != "stageMs"}
    return {**r, "diagnostics": d}


def test_flags_off_is_todays_behaviour_and_declares_the_plan(services):
    base = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0)
    off = _engine(services, negation_filter=False, taxonomy_filter=False, route_filter=False, numeric_filter=False)
    for q in ("khách sạn Nha Trang không có hồ bơi", "resort 5 sao Phú Quốc dưới 2 triệu", "vé máy bay từ Hà Nội đến Nha Trang",
              "khách sạn, vé máy bay và vé tham quan ở Nha Trang", "resort Phú Quốc"):
        a, b = base(q, limit=50), off(q, limit=50)
        assert _strip(a) == _strip(b), q
        assert "appliedFilters" not in b and len(b["results"]) == len(services["index"].units) - 0 or b["total"] >= 1
    qp = off("khách sạn Nha Trang không có hồ bơi", limit=50)["diagnostics"]["queryPlan"]
    assert qp["mustNot"] == {"amenities": ["pool"], "brands": []} and "applied" not in qp
    assert qp["taxonomy"] == {"value": "hotel", "source": "query", "candidates": ["hotel"]}


def test_negation_excludes_units_that_record_the_amenity_only(services):
    r = _engine(services, negation_filter=True)("khách sạn Nha Trang không có hồ bơi", limit=50)
    ids = _ids(r)
    assert "H1" not in ids                      # có ghi "hồ bơi" → loại
    assert "H2" in ids and "H3" in ids          # không có dữ liệu tiện ích → qua ([C2] vắng = không biết)
    assert r["diagnostics"]["filteredCount"] == len(services["index"].units) - 1
    assert r["appliedFilters"] == {"hard": {"mustNotAmenities": ["pool"]}, "soft": {}}
    qp = r["diagnostics"]["queryPlan"]
    assert qp["applied"] == ["mustNot"] and "hồ bơi" not in qp["lexicalText"] and "Nha Trang" in qp["lexicalText"]


def test_taxonomy_from_query_filters_single_vertical_only(services):
    e = _engine(services, taxonomy_filter=True)
    one = e("resort Nha Trang", limit=50)
    assert {x["taxonomy"] for x in one["results"]} == {"hotel"}
    assert one["appliedFilters"]["hard"] == {"taxonomy": "hotel", "taxonomySource": "query"}
    multi = e("khách sạn, vé máy bay và vé tham quan ở Nha Trang", limit=50)
    assert len({x["taxonomy"] for x in multi["results"]}) > 1 and "appliedFilters" not in multi
    assert multi["diagnostics"]["queryPlan"]["taxonomy"]["skipped"] == "multi"
    param = e("resort Nha Trang", taxonomy="golf", limit=50)
    assert _ids(param) == ["G1"] and param["diagnostics"]["queryPlan"]["taxonomy"]["source"] == "param"


def test_route_filters_origin_and_destination_and_never_relaxes(services):
    spy = SpyEmbedder()
    e = _engine(services, embedder=spy, route_filter=True, dest_filter=True)
    fwd = e("vé máy bay từ Hà Nội đến Nha Trang", limit=50)
    assert _ids(fwd) == ["F1"]
    assert fwd["appliedFilters"]["hard"] == {"destination": "Nha Trang", "destinationSource": "query", "origin": "Hà Nội",
                                             "originSource": "query", "destinationCity": "Nha Trang"}
    assert fwd["diagnostics"]["queryPlan"]["route"] == {"origin": "Hà Nội", "destinationCity": "Nha Trang",
                                                        "direction": "explicit", "source": "query"}
    spy.calls = 0
    rev = e("vé máy bay từ Nha Trang đến Hà Nội", limit=50)
    assert rev["total"] == 0 and spy.calls == 1                                  # không bịa chiều ngược, không embed lại
    assert rev["diagnostics"]["queryPlan"]["emptyReason"] == "route"             # sau khi fallback bỏ điểm đến, origin vẫn rỗng
    assert rev["diagnostics"]["destinationFilter"]["fallback"] == "dropped_empty"


def test_origin_param_applies_without_flag_and_is_ignored_for_non_flight(services):
    r = _engine(services)("Nha Trang", taxonomy="flight", origin="Hà Nội", limit=50)
    assert _ids(r) == ["F1"] and r["appliedFilters"]["hard"] == {"taxonomy": "flight", "origin": "Hà Nội", "originSource": "param"}
    other = _engine(services)("Nha Trang", taxonomy="flight", origin="Đà Nẵng", limit=50)
    assert other["total"] == 0 and other["diagnostics"]["queryPlan"]["emptyReason"] == "route"
    hotel = _engine(services)("resort Nha Trang", origin="Hà Nội", limit=50)
    assert len(hotel["results"]) > 1 and hotel["diagnostics"]["queryPlan"]["ignored"] == ["origin"]


def test_price_param_is_hard_and_drops_units_without_price(services):
    r = _engine(services)("khách sạn Nha Trang", price_max=4000000, limit=50)
    ids = _ids(r)
    assert "H1" in ids and "A1" in ids and "G1" in ids and "F1" in ids     # H1 qua giá phòng R1 3,4 M; F1 qua chuyến FL1 1,89 M
    assert not {"H2", "A2", "H3", "C1"} & set(ids)                        # không giá (H2, A2) hoặc quá giá (H3 5 M, C1 9,8 M)
    assert r["appliedFilters"]["hard"] == {"priceMax": 4000000, "priceSource": "param"}
    both = _engine(services)("khách sạn Nha Trang", price_min=3000000, price_max=4000000, limit=50)
    assert _ids(both) == ["H1"]


def test_star_param_is_soft_known_low_dropped_unknown_demoted(services):
    r = _engine(services)("khách sạn Nha Trang", star_min=5, limit=50)
    ids = _ids(r)
    assert "H2" not in ids                                                  # khai 4 sao < 5 → loại
    assert {"H1", "H3"} <= set(ids) and {"A1", "G1", "C1"} <= set(ids)     # không khai sao → giữ
    assert set(ids[:2]) == {"H1", "H3"}                                    # … nhưng xếp sau unit thoả
    assert r["appliedFilters"] == {"hard": {}, "soft": {"starRatingMin": 5, "starRatingSource": "param"}}


def test_numeric_from_query_behind_flag(services):
    on = _engine(services, numeric_filter=True)("khách sạn 5 sao Nha Trang dưới 4 triệu", limit=50)
    ids = _ids(on)
    assert "H2" not in ids and "H3" not in ids and "H1" in ids
    qp = on["diagnostics"]["queryPlan"]
    assert qp["price"] == {"min": None, "max": 4000000, "source": "query"} and qp["star"] == {"min": 5.0, "source": "query"}
    assert set(qp["applied"]) == {"price", "star"} and "4 triệu" not in qp["lexicalText"] and "5 sao" not in qp["lexicalText"]
    off = _engine(services)("khách sạn 5 sao Nha Trang dưới 4 triệu", limit=50)
    assert {"H2", "H3"} <= set(_ids(off)) and "appliedFilters" not in off
    assert off["diagnostics"]["queryPlan"]["price"]["source"] == "query"   # tắt vẫn khai


def test_empty_filtered_set_from_params_is_not_relaxed(services):
    r = _engine(services)("resort Phú Quốc", destination="Phú Quốc", price_max=1000, limit=50)
    assert r["total"] == 0 and r["diagnostics"]["filteredCount"] == 0
    assert r["diagnostics"]["queryPlan"]["emptyReason"] == "price"
    assert r["appliedFilters"]["hard"] == {"destination": "Phú Quốc", "destinationSource": "param", "priceMax": 1000,
                                           "priceSource": "param"}


def test_agent_can_override_plan_flags_per_call(services):
    off = _engine(services)
    on_call = off("khách sạn Nha Trang không có hồ bơi", limit=50, derive_plan=True)
    assert "H1" not in _ids(on_call) and on_call["appliedFilters"]["hard"]["mustNotAmenities"] == ["pool"]
    forced_off = _engine(services, **ALL)("khách sạn Nha Trang không có hồ bơi", limit=50, derive_plan=False)
    assert "H1" in _ids(forced_off) and "appliedFilters" not in forced_off


def test_responses_match_contract(services):
    e = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=0.0, lexical=services["vectors"],
                       hybrid=HybridConfig(lexical_cutoff=0.0), dest_filter=True, **ALL)
    schema = contracts()["search_products"]["response"]
    cases = (("khách sạn Nha Trang không có hồ bơi", {}), ("resort 5 sao Phú Quốc dưới 2 triệu", {}),
             ("vé máy bay từ Hà Nội đến Nha Trang", {}), ("vé máy bay từ Nha Trang đến Hà Nội", {}),
             ("khách sạn, vé máy bay và vé tham quan ở Nha Trang", {}), ("Nha Trang", {"taxonomy": "flight", "origin": "Hà Nội"}),
             ("resort Nha Trang", {"origin": "Hà Nội", "price_max": 4000000, "star_min": 4, "available_only": False}),
             ("zzzz không khớp gì", {}))
    for q, kw in cases:
        r = e(q, limit=5, **kw)
        r["diagnostics"]["latencyMs"] = 0
        errors = [er.message for er in Draft202012Validator(schema).iter_errors(r)]
        assert errors == [], (q, errors)
        json.dumps(r)


def test_parsed_but_inactive_star_does_not_reorder_results(services):
    # Câu không có alias: normalizer không đổi text → vector như nhau → thứ tự cosine phải y hệt engine không chuẩn hoá,
    # dù plan parse ra "5 sao" (cờ numeric tắt). Lỗi bắt được ở bench 06/10: 7 câu multi_constraint bị xếp lại khi cờ tắt.
    q = "khách sạn 5 sao Nha Trang"
    with_plan = _engine(services)(q, limit=50)
    raw = _engine(services, normalize=False)(q, limit=50)
    assert with_plan["diagnostics"]["queryPlan"]["star"] == {"min": 5.0, "source": "query"}
    assert _ids(with_plan) == _ids(raw)
