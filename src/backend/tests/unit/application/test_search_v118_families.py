"""SearchProducts — ba họ 07/10 (contract 1.18.0; spec docs/spec/bench/tong-hop-chinh-sua-luong-search-ota.md): F7 thời lượng
(`duration_filter`), địa danh gazetteer → F1 (`poi_resolve`), entity gate cứng (`entity_filter`). Cờ tắt thì KHÔNG parse, không
khai — response y hệt 1.17.0; `derive_plan` bật/tắt cả ba cho riêng lượt gọi (Agent).

Hai catalog: `services` của tests/conftest.py (cờ tắt ≡ engine gốc) và `v118` dựng ở đây = ROWS của conftest cộng hai unit tái
hiện lỗi production:
  HD1 "Khách sạn Ngay Chợ Đêm Đà Lạt" — tên có cả "ngay" lẫn "dem" → bị vớt BM25 cho câu "vinwonder 3 ngay 2 dem" khi F7 tắt
  A3  "Vé tắm bùn Hòn Tằm" — entity venue một site (`hon_tam`, Nha Trang) để có khoá entity ngoài `vinwonders` (A1).
Catalog không có Hà Nội → "Hồ Hoàn Kiếm" bị `place_table(destinations)` bỏ lúc nạp; Grand Park không có unit → không gate."""
import json

import pytest

from src.backend.app.application.search import SearchProducts
from src.backend.app.application.search.use_cases import FALLBACK_DROPPED_EMPTY
from src.backend.app.domain.search import (
    HybridConfig,
    PlanFlags,
    PlanGazetteers,
    PlanParams,
    build_query_plan,
    entity_table,
)
from src.backend.tests.conftest import ROWS, FakeEmbedder, P
from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore

V118_ROWS = [
    *ROWS,
    P("HD1", "Khách sạn Ngay Chợ Đêm Đà Lạt", "hotel", "Đà Lạt", {"level": "property", "starRating": 3}, price=None),
    P("A3", "Vé tắm bùn Hòn Tằm", "attraction", "Nha Trang", {}, price=350000),
]
#: Ba câu gốc của tài liệu lỗi production (spec §1).
ROOT_CAUSE_QUERIES = ("vinwonder 3 ngay 2 dem", "khách sạn gần Hồ Hoàn Kiếm", "khách sạn Nha Trang 2 đêm")
NEW_FLAGS = dict(duration_filter=True, poi_resolve=True, entity_filter=True)
NEW_KEYS = {"duration", "entity", "location"}


@pytest.fixture(scope="module")
def v118(tmp_path_factory):
    d = tmp_path_factory.mktemp("v118")
    (d / "products.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in V118_ROWS), encoding="utf-8")
    index, vectors = InMemoryVectorStore(str(d / "products.jsonl"), FakeEmbedder(), str(d / ".emb")).load()
    return {"index": index, "vectors": vectors}


def _engine(cat, **kw):
    kw.setdefault("cutoff", -1.0)
    return SearchProducts(cat["index"], cat["vectors"], FakeEmbedder(), **kw)


def _rescue_engine(cat, **kw):
    """Chỉ còn đường vớt BM25 (cutoff 2.0: không hit dense nào qua; lexical_cutoff −1: cosine giả không chặn) — như
    tests/unit/application/test_hybrid_search.py `rescue_only`."""
    return SearchProducts(cat["index"], cat["vectors"], FakeEmbedder(), cutoff=2.0, lexical=cat["vectors"],
                          hybrid=HybridConfig(lexical_cutoff=-1.0), **kw)


def _ids(r):
    return [x["productId"] for x in r["results"]]


def _strip(r):
    return {**r, "diagnostics": {k: v for k, v in r["diagnostics"].items() if k != "stageMs"}}


def _qp(r):
    return r["diagnostics"].get("queryPlan", {})


# ------------------------------------------------------------------ cờ tắt ≡ 1.17.0
def test_flags_off_is_identical_to_the_base_engine(services):
    base = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0)
    off = _engine(services, duration_filter=False, poi_resolve=False, entity_filter=False)
    for q in (*ROOT_CAUSE_QUERIES, "VinWonders 3 ngày 2 đêm", "resort gần Bãi Sao", "VinWonders Nha Trang"):
        a, b = base(q, limit=50), off(q, limit=50)
        assert _strip(a) == _strip(b), q
        assert not NEW_KEYS & set(_qp(b)) and "appliedFilters" not in b, q   # tắt: không parse, không khai


# ------------------------------------------------------------------ F7 thời lượng
def test_duration_is_declared_and_consumed_from_the_bm25_text(v118):
    r = _engine(v118, duration_filter=True)("VinWonders 3 ngày 2 đêm", limit=50)
    qp = _qp(r)
    assert qp["duration"] == {"days": 3, "nights": 2, "source": "query"}
    assert "duration" in qp["applied"] and "3 ngày" not in qp["lexicalText"] and "2 đêm" not in qp["lexicalText"]
    assert qp["lexicalText"] == "VinWonders"
    assert "appliedFilters" not in r                       # không vào mask (catalog chưa có trường thời lượng) → không có khối
    assert r["total"] == len(v118["index"].units)          # không lọc gì
    compact = _qp(_engine(v118, duration_filter=True)("combo VinWonders 3N2Đ", limit=50))
    assert compact["duration"] == {"days": 3, "nights": 2, "source": "query"} and "3N2Đ" not in compact["lexicalText"]


def test_duration_stops_bm25_rescuing_the_night_market_hotel(v118):
    """Lỗi production 1 (spec §1): "vinwonder 3 ngay 2 dem" → token truy vấn [vinwonder, ngay, dem] (số 1 ký tự bị bỏ) →
    tên "Khách sạn Ngay Chợ Đêm Đà Lạt" phủ 2/3 ≥ 0,6 → được vớt. F7 bỏ cụm thời lượng khỏi câu BM25 → hết đường vớt."""
    for q in ("VinWonders 3 ngày 2 đêm", "vinwonder 3 ngay 2 dem"):
        off = _rescue_engine(v118)(q, limit=50)
        assert "HD1" in _ids(off), q                                       # tái hiện lỗi khi cờ tắt
        assert "queryPlan" not in off["diagnostics"] or "duration" not in _qp(off)
        on = _rescue_engine(v118, duration_filter=True)(q, limit=50)
        assert "HD1" not in _ids(on), q
        assert _qp(on)["duration"] == {"days": 3, "nights": 2, "source": "query"}
    assert _ids(_rescue_engine(v118, duration_filter=True)("VinWonders 3 ngày 2 đêm", limit=50)) == ["A1"]


def test_duration_only_query_has_no_applied_filters(v118):
    r = _engine(v118, duration_filter=True)("khách sạn Nha Trang 2 đêm", limit=50)   # dest_filter tắt
    qp = _qp(r)
    assert qp["duration"] == {"days": None, "nights": 2, "source": "query"} and qp["applied"] == ["duration"]
    assert qp["lexicalText"] == "khách sạn Nha Trang"
    assert "appliedFilters" not in r and r["total"] == len(v118["index"].units)
    assert r["diagnostics"]["derivedDestinations"] == ["Nha Trang"]
    none = _engine(v118, duration_filter=True)("resort 2 triệu/đêm Phú Quốc", limit=50)   # "/đêm" thuộc span giá
    assert "duration" not in _qp(none) and "applied" not in _qp(none)


# ------------------------------------------------------------------ entity gate cứng
def test_entity_gate_keeps_only_named_attraction_or_combo(v118):
    r = _engine(v118, entity_filter=True)("VinWonders Nha Trang", limit=50)
    assert _ids(r) == ["A1"] and r["total"] == 1                           # C1 "Combo 3N2Đ Vinpearl Nha Trang": tên không có VinWonders
    assert r["facets"]["taxonomy"] == {"attraction": 1}
    assert r["appliedFilters"] == {"hard": {"entity": ["vinwonders"]}, "soft": {}}
    qp = _qp(r)
    assert qp["entity"] == {"keys": ["vinwonders"], "role": "gate"} and qp["applied"] == ["entity"]
    assert qp["lexicalText"] == "VinWonders Nha Trang"                     # cụm entity không bị tiêu (tên sản phẩm, BM25 cần)
    venue = _engine(v118, entity_filter=True)("vé Hòn Tằm", limit=50)
    assert _ids(venue) == ["A3"] and venue["appliedFilters"]["hard"] == {"entity": ["hon_tam"]}


def test_entity_gate_with_request_taxonomy_hotel_is_empty_with_reason_entity(v118):
    r = _engine(v118, entity_filter=True)("VinWonders Nha Trang", taxonomy="hotel", limit=50)
    assert r["total"] == 0 and r["results"] == [] and r["facets"]["taxonomy"] == {}
    qp = _qp(r)
    assert qp["emptyReason"] == "entity" and qp["entity"] == {"keys": ["vinwonders"], "role": "gate"}
    assert r["appliedFilters"]["hard"] == {"taxonomy": "hotel", "entity": ["vinwonders"]}   # tham số không đổi vai trò


def test_entity_with_another_vertical_cue_only_locates(v118):
    r = _engine(v118, entity_filter=True)("khách sạn gần Hòn Tằm", limit=50)
    assert _qp(r)["entity"] == {"keys": ["hon_tam"], "role": "location"}
    assert "applied" not in _qp(r) and "appliedFilters" not in r
    assert {"H1", "H2", "H3", "HD1"} <= set(_ids(r)) and r["total"] == len(v118["index"].units)


def test_entity_without_any_catalog_unit_never_gates(v118):
    """`_plan_gazetteers(units, entities=attrs.entities)` thu bảng entity về khoá có mặt trong catalog: Grand Park không có
    unit → câu "vé Grand Park" không có khối entity (bảng đầy đủ của domain thì gate)."""
    engine = _engine(v118, entity_filter=True)
    assert "grand park" in entity_table() and "grand park" not in engine._gaz.entities
    assert set(engine._gaz.entities.values()) == {"vinwonders", "hon_tam"}
    r = engine("vé Grand Park", limit=50)
    assert "entity" not in _qp(r) and "appliedFilters" not in r and r["total"] == len(v118["index"].units)
    full = build_query_plan(engine._normalizer("vé Grand Park"), "vé Grand Park", PlanParams(), PlanFlags(entity=True),
                            PlanGazetteers())
    assert full.entity_keys == ("grand_park",) and full.entity_role == "gate"


def test_entity_and_duration_together(v118):
    r = _engine(v118, duration_filter=True, entity_filter=True)("vé VinWonders 3 ngày 2 đêm", limit=50)
    assert _ids(r) == ["A1"]
    qp = _qp(r)
    assert qp["applied"] == ["duration", "entity"] and qp["lexicalText"] == "vé VinWonders"
    assert qp["duration"] == {"days": 3, "nights": 2, "source": "query"} and qp["entity"]["role"] == "gate"
    assert r["appliedFilters"]["hard"] == {"entity": ["vinwonders"]}


# ------------------------------------------------------------------ địa danh gazetteer → F1
def test_poi_resolves_to_the_catalog_destination_and_filters_like_f1(v118):
    r = _engine(v118, poi_resolve=True, dest_filter=True)("resort gần Bãi Sao", limit=50)
    assert _ids(r) == ["H3"]
    d = r["diagnostics"]
    assert d["destinationFilter"] == {"source": "query", "value": "Phú Quốc"}   # enum source đóng: POI vẫn là query
    assert d["derivedDestinations"] == ["Phú Quốc"]
    assert r["appliedFilters"]["hard"] == {"destination": "Phú Quốc", "destinationSource": "poi"}
    assert _qp(r)["location"] == {"key": "bai_sao", "name": "Bãi Sao", "kind": "landmark", "destination": "Phú Quốc"}
    assert "applied" not in _qp(r)                                          # F1 không nằm trong `applied`
    venue = _engine(v118, poi_resolve=True, dest_filter=True)("khách sạn gần Hòn Tre", limit=50)
    assert {x["destination"] for x in venue["results"]} == {"Nha Trang"} and venue["appliedFilters"]["hard"] == {
        "destination": "Nha Trang", "destinationSource": "poi"}
    assert _qp(venue)["location"]["kind"] == "area"


def test_poi_falls_back_when_the_filtered_set_is_empty(v118):
    r = _engine(v118, poi_resolve=True, dest_filter=True)("resort gần Bãi Sao", taxonomy="golf", limit=50)
    assert _ids(r) == ["G1"]                                                # Phú Quốc không có golf → lượt không lọc (FR-SRC-04)
    assert r["diagnostics"]["destinationFilter"] == {"source": "query", "value": "Phú Quốc",
                                                     "fallback": FALLBACK_DROPPED_EMPTY}
    assert r["appliedFilters"]["hard"] == {"taxonomy": "golf"}             # điểm đến đã nới → không khai
    assert _qp(r)["location"]["destination"] == "Phú Quốc"


def test_poi_without_dest_filter_only_declares(v118):
    r = _engine(v118, poi_resolve=True)("resort gần Bãi Sao", limit=50)
    assert _qp(r)["location"]["key"] == "bai_sao" and r["diagnostics"]["derivedDestinations"] == ["Phú Quốc"]
    assert "destinationFilter" not in r["diagnostics"] and "appliedFilters" not in r
    assert r["total"] == len(v118["index"].units)
    off = _engine(v118, dest_filter=True)("resort gần Bãi Sao", limit=50)   # POI tắt: địa danh không được nhận ra
    assert "location" not in _qp(off) and off["diagnostics"]["destinationFilter"] == {"source": "none", "value": None}


def test_poi_venue_entity_in_hotel_query_locates_and_filters(v118):
    r = _engine(v118, poi_resolve=True, entity_filter=True, dest_filter=True)("khách sạn gần Hòn Tằm", limit=50)
    assert {x["destination"] for x in r["results"]} == {"Nha Trang"} and "HD1" not in _ids(r)
    qp = _qp(r)
    assert qp["entity"] == {"keys": ["hon_tam"], "role": "location"}
    assert qp["location"] == {"key": "hon_tam", "name": "Hòn Tằm", "kind": "venue", "destination": "Nha Trang"}
    assert r["appliedFilters"]["hard"] == {"destination": "Nha Trang", "destinationSource": "poi"}


# ------------------------------------------------------------------ derive_plan (Agent)
def test_derive_plan_toggles_all_three_families_per_call(v118):
    off = _engine(v118)
    on_call = off("VinWonders 3 ngày 2 đêm", derive_plan=True, limit=50)
    assert _ids(on_call) == ["A1"]
    qp = _qp(on_call)
    assert {"duration", "entity"} <= set(qp) and {"duration", "entity"} <= set(qp["applied"])
    assert on_call["appliedFilters"]["hard"]["entity"] == ["vinwonders"]
    poi = off("resort gần Bãi Sao", derive_plan=True, derive_destination=True, limit=50)
    assert _ids(poi) == ["H3"] and poi["appliedFilters"]["hard"]["destinationSource"] == "poi"
    assert _qp(poi)["location"]["destination"] == "Phú Quốc"
    all_on = _engine(v118, dest_filter=True, **NEW_FLAGS)
    for q in ("VinWonders 3 ngày 2 đêm", "resort gần Bãi Sao"):
        forced_off = all_on(q, derive_plan=False, limit=50)
        assert not NEW_KEYS & set(_qp(forced_off)) and "appliedFilters" not in forced_off, q
        assert forced_off["total"] == len(v118["index"].units), q
