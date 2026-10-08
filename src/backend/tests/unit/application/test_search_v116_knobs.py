"""SearchProducts — các núm 06/10 (contract 1.16.0): kênh fuzzy + trọng số RRF, số khách (travelContext.guests / "3 người"),
F4 chỉ cue mạnh, chuẩn hoá dấu thanh, `matchedChildren` và kiểm giá + số khách đồng thời trên phòng con.

Hai catalog: `services` của tests/conftest.py (không có sức chứa) cho fuzzy / trọng số / F4; `party` dựng ở đây — property có
hạng phòng khác giá và sức chứa:
  H1 Vinpearl Resort Nha Trang: R1a 2 M (2 người) · R1b 6 M (4 người)      H2 Khách sạn Biển Nha Trang: R2b 1,5 M (2) · R2a 3 M (4)
  H3 Mường Thanh Nha Trang: R3a 2,5 M (không rõ sức chứa)                   H4 Homestay Nha Trang: R4a 0,8 M (2)
  A1 VinWonders Nha Trang 880 k (không con) · C1 Combo 9,8 M · A2 Thủy Cung Hòa Bình Nha Trang (tên kiểu dấu cũ) 300 k."""
import json

import numpy as np
import pytest

from src.backend.app.application.search import SearchProducts
from src.backend.app.domain.search import HybridConfig
from src.backend.tests.conftest import P, FakeEmbedder
from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore

PARTY_ROWS = [
    P("H1", "Vinpearl Resort Nha Trang", "hotel", "Nha Trang", {"level": "property", "starRating": 5}, price=None),
    P("R1a", "Vinpearl Resort Nha Trang - Deluxe", "hotel", "Nha Trang",
      {"level": "room", "parentProductId": "H1", "maxOccupancy": 2}, price=2000000),
    P("R1b", "Vinpearl Resort Nha Trang - Family Suite", "hotel", "Nha Trang",
      {"level": "room", "parentProductId": "H1", "maxOccupancy": 4}, price=6000000),
    P("H2", "Khách sạn Biển Nha Trang", "hotel", "Nha Trang", {"level": "property", "starRating": 4}, price=None),
    P("R2a", "Khách sạn Biển Nha Trang - Family", "hotel", "Nha Trang",
      {"level": "room", "parentProductId": "H2", "maxOccupancy": 4}, price=3000000),
    P("R2b", "Khách sạn Biển Nha Trang - Standard", "hotel", "Nha Trang",
      {"level": "room", "parentProductId": "H2", "maxOccupancy": 2}, price=1500000),
    P("H3", "Mường Thanh Nha Trang", "hotel", "Nha Trang", {"level": "property"}, price=None),
    P("R3a", "Mường Thanh Nha Trang - Superior", "hotel", "Nha Trang", {"level": "room", "parentProductId": "H3"},
      price=2500000),
    P("H4", "Homestay Nha Trang", "hotel", "Nha Trang", {"level": "property"}, price=None),
    P("R4a", "Homestay Nha Trang - Phòng đôi", "hotel", "Nha Trang",
      {"level": "room", "parentProductId": "H4", "maxOccupancy": 2}, price=800000),
    P("A1", "VinWonders Nha Trang", "attraction", "Nha Trang", {}, price=880000),
    P("C1", "Combo 3N2Đ Vinpearl Nha Trang", "combo", "Nha Trang", {"nights": 2}, price=9800000),
    P("A2", "Thủy Cung Hòa Bình Nha Trang", "attraction", "Nha Trang", {}, price=300000),
]


@pytest.fixture(scope="module")
def party(tmp_path_factory):
    d = tmp_path_factory.mktemp("party")
    (d / "products.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in PARTY_ROWS), encoding="utf-8")
    emb = FakeEmbedder()
    index, vectors = InMemoryVectorStore(str(d / "products.jsonl"), emb, str(d / ".emb")).load()
    return {"index": index, "vectors": vectors, "emb": emb}


def _engine(cat, **kw):
    kw.setdefault("cutoff", -1.0)
    return SearchProducts(cat["index"], cat["vectors"], kw.pop("embedder", cat.get("emb") or FakeEmbedder()), **kw)


def _ids(r):
    return [x["productId"] for x in r["results"]]


def _by_id(r):
    return {x["productId"]: x for x in r["results"]}


# ------------------------------------------------------------------ kênh fuzzy
class _SpyVectors:
    """Kho vector không trả gì ở dense / BM25 (để chỉ kênh fuzzy còn đường vớt) và ghi lại lượt lấy vector theo id."""

    def __init__(self, inner, *, fail=False):
        self.inner, self.fail, self.calls = inner, fail, []
        self.dimension = getattr(inner, "dimension", None)

    def near_vector(self, *a, **k):
        return []

    def bm25(self, *a, **k):
        return []

    def vectors(self, ids):
        self.calls.append(list(ids))
        if self.fail:
            raise RuntimeError("weaviate down")
        return self.inner.vectors(ids)


def _fuzzy_engine(services, spy, **cfg):
    cfg = {"lexical_k": 0, "lexical_cutoff": -1.0, "fuzzy_k": 3, "fuzzy_min_sim": 0.75, **cfg}
    return SearchProducts(services["index"], spy, FakeEmbedder(), cutoff=2.0, lexical=spy, hybrid=HybridConfig(**cfg))


def test_fuzzy_rescues_a_typo_name_and_fetches_its_vector(services):
    spy = _SpyVectors(services["vectors"])
    r = _fuzzy_engine(services, spy)("Vinwondrs Nha Trang", limit=5)
    assert _ids(r) == ["A1"] and r["total"] == 1
    d = r["diagnostics"]
    assert d["fuzzyCount"] == 1 and d["lexicalCount"] == 0 and "fuzzy" in d["stageMs"]
    assert spy.calls == [["A1"]]          # chỉ unit đạt cổng (rank ≤ fuzzy_k, độ giống ≥ min_sim) mới được lấy vector
    off = _fuzzy_engine(services, _SpyVectors(services["vectors"]), fuzzy_k=0)("Vinwondrs Nha Trang", limit=5)
    assert off["results"] == [] and "fuzzyCount" not in off["diagnostics"] and "fuzzy" not in off["diagnostics"]["stageMs"]


def test_fuzzy_matches_below_threshold_do_not_reorder(services):
    """06/10: khớp dưới `fuzzy_min_sim` không vào danh sách kênh → không cộng RRF; ngưỡng cao ≡ kênh tắt về thứ tự."""
    q = "khách sạn gần biển cho gia đình"
    base = dict(lexical_k=10, lexical_cutoff=-1.0)
    off = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0, lexical=services["vectors"],
                         hybrid=HybridConfig(**base))(q, limit=20)
    high = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0, lexical=services["vectors"],
                          hybrid=HybridConfig(**base, fuzzy_k=3, fuzzy_min_sim=0.99))(q, limit=20)
    assert _ids(high) == _ids(off) and high["diagnostics"]["fuzzyCount"] == 0


def test_fuzzy_gate_mask_and_vector_failure(services):
    strict = _SpyVectors(services["vectors"])
    assert _fuzzy_engine(services, strict, fuzzy_min_sim=0.9)("Vinwondrs Nha Trang")["results"] == []
    assert strict.calls == []                                              # dưới ngưỡng → không lấy vector
    masked = _SpyVectors(services["vectors"])
    r = _fuzzy_engine(services, masked)("Vinwondrs Nha Trang", taxonomy="hotel")
    assert r["results"] == [] and masked.calls == []                      # A1 ngoài F (taxonomy hotel) → kênh không thấy
    broken = _SpyVectors(services["vectors"], fail=True)
    r = _fuzzy_engine(services, broken)("Vinwondrs Nha Trang")
    assert r["results"] == [] and r["diagnostics"]["fuzzyCount"] == 0     # thiếu cosine → không vớt, không 500


def test_rrf_weights_reorder_without_changing_the_result_set(services):
    def engine(**w):
        return SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0,
                              lexical=services["vectors"], hybrid=HybridConfig(**w))
    q = "VinWonders Nha Trang"
    base, dense_only, lex_only = engine()(q, limit=50), engine(lexical_weight=0.0)(q, limit=50), engine(dense_weight=0.0)(q, limit=50)
    assert set(_ids(base)) == set(_ids(dense_only)) == set(_ids(lex_only)) and base["total"] == lex_only["total"]
    scores = [x["score"] for x in dense_only["results"]]
    assert scores == sorted(scores, reverse=True)                         # chỉ còn nhánh dense → thứ tự cosine
    bm25 = [h.product_id for h in services["vectors"].bm25(q, None, 50)]
    assert _ids(lex_only)[:len(bm25)] == bm25                              # chỉ còn nhánh BM25 → hit BM25 lên đầu theo rank
    explicit = engine(fuzzy_k=0, fuzzy_candidate_k=50, fuzzy_min_sim=0.75, dense_weight=1.0, lexical_weight=1.0,
                      fuzzy_weight=1.0)(q, limit=50)
    assert _ids(explicit) == _ids(base)                                    # giá trị main.py dựng khi mọi biến ở mặc định


# ------------------------------------------------------------------ số khách
def test_guests_param_filters_known_occupancy_and_declares_party(party):
    r = _engine(party)("khách sạn Nha Trang", adults=2, children=1, limit=50)
    ids = _ids(r)
    assert "H4" not in ids                                                 # sức chứa đã biết 2 < 3
    assert {"H1", "H2", "H3", "A1", "C1"} <= set(ids)                      # 4 người / không biết sức chứa → giữ
    assert r["appliedFilters"] == {"hard": {"minOccupancy": 3, "partySource": "param"}, "soft": {}}
    assert r["diagnostics"]["queryPlan"]["party"] == {"adults": 2, "children": 1, "total": 3, "source": "param"}
    kids = {pid: x.get("matchedChildren") for pid, x in _by_id(r).items()}
    assert kids["H1"] == ["R1b"] and kids["H2"] == ["R2a"] and kids["H3"] == ["R3a"] and kids["A1"] is None
    only_children = _engine(party)("khách sạn Nha Trang", children=2, limit=50)
    assert "H4" in _ids(only_children) and "appliedFilters" not in only_children   # không bịa số người lớn → không lọc


def test_party_from_query_only_behind_flag(party):
    q = "khách sạn cho 3 người ở Nha Trang"
    off = _engine(party)(q, limit=50)
    assert "H4" in _ids(off) and "appliedFilters" not in off
    assert "party" not in off["diagnostics"]["queryPlan"]                 # cờ tắt: không khai khoá 1.16.0
    on = _engine(party, party_filter=True)(q, limit=50)
    assert "H4" not in _ids(on)
    assert on["appliedFilters"]["hard"] == {"minOccupancy": 3, "partySource": "query"}
    qp = on["diagnostics"]["queryPlan"]
    assert qp["party"] == {"adults": None, "children": None, "total": 3, "source": "query"}
    assert "party" in qp["applied"] and "3 người" not in qp["lexicalText"]
    param_wins = _engine(party, party_filter=True)(q, adults=1, limit=50)
    assert "H4" in _ids(param_wins) and param_wins["appliedFilters"]["hard"]["minOccupancy"] == 1
    assert param_wins["diagnostics"]["queryPlan"]["party"]["source"] == "param"
    agent = _engine(party)(q, derive_plan=True, limit=50)                 # Agent bật mọi họ cho riêng lượt gọi
    assert "H4" not in _ids(agent)


def test_matched_children_only_when_price_or_party_is_active(party):
    plain = _engine(party)("khách sạn Nha Trang", limit=50)
    assert all("matchedChildren" not in x for x in plain["results"])
    priced = _by_id(_engine(party)("khách sạn Nha Trang", price_max=2600000, limit=50))
    assert priced["H1"]["matchedChildren"] == ["R1a"] and priced["H2"]["matchedChildren"] == ["R2b"]
    assert priced["H3"]["matchedChildren"] == ["R3a"] and priced["H4"]["matchedChildren"] == ["R4a"]
    assert "matchedChildren" not in priced["A1"]                          # không có con
    parsed_not_applied = _engine(party)("khách sạn Nha Trang dưới 3 triệu", limit=50)   # giá suy từ câu, cờ numeric tắt
    assert all("matchedChildren" not in x for x in parsed_not_applied["results"])
    applied = _by_id(_engine(party, numeric_filter=True)("khách sạn Nha Trang dưới 3 triệu", limit=50))
    assert applied["H2"]["matchedChildren"] == ["R2b", "R2a"]             # giá tăng dần


def test_price_and_party_must_hold_on_the_same_child(party):
    price_only = _engine(party)("khách sạn Nha Trang", price_max=4000000, limit=50)
    assert "H1" in _ids(price_only)                                        # phòng 2 M qua giá
    both = _engine(party)("khách sạn Nha Trang", price_max=4000000, adults=4, limit=50)
    ids = _ids(both)
    assert "H1" not in ids                                                 # 2 M chỉ 2 người, 4 người thì 6 M > 4 M
    assert "H4" not in ids and {"H2", "H3", "A1"} <= set(ids)              # H4 bị mask (2 người); A1 không con → giữ
    assert _by_id(both)["H2"]["matchedChildren"] == ["R2a"] and _by_id(both)["H3"]["matchedChildren"] == ["R3a"]
    d = both["diagnostics"]
    # từ 1.19.0 mask kiểm giá + sức chứa trên CÙNG một phòng nên H1 bị loại ngay ở mask, không còn là drop ở bước kiểm lại
    assert "revalidatedDrops" not in d["queryPlan"] and d["relevantCount"] == both["total"] == len(ids)
    assert sum(both["facets"]["taxonomy"].values()) == both["total"]       # [C4] facets đếm lại sau khi loại
    assert both["appliedFilters"]["hard"] == {"priceMax": 4000000, "priceSource": "param", "minOccupancy": 4,
                                              "partySource": "param"}


def test_empty_filtered_set_from_party_reports_party(party):
    r = _engine(party)("khách sạn Nha Trang", taxonomy="hotel", destination="Nha Trang", adults=5, price_max=10000000,
                       limit=50)
    # khách sạn có sức chứa đã biết đều < 5, H3 không rõ sức chứa → còn H3
    assert _ids(r) == ["H3"]
    none = _engine(party)("homestay", taxonomy="hotel", adults=30, price_max=900000, limit=50)
    assert none["total"] == 0 and none["diagnostics"]["queryPlan"]["emptyReason"] == "party"


# ------------------------------------------------------------------ F4 chỉ cue mạnh
def test_taxonomy_strong_only_skips_weak_cues(services):
    loose = _engine(services, taxonomy_filter=True)
    strict = _engine(services, taxonomy_filter=True, taxonomy_strong_only=True)
    weak = "nghỉ dưỡng ở Nha Trang"
    assert {x["taxonomy"] for x in loose(weak, limit=50)["results"]} == {"hotel"}
    assert "strength" not in loose(weak, limit=50)["diagnostics"]["queryPlan"]["taxonomy"]   # núm tắt: không khai
    r = strict(weak, limit=50)
    assert len({x["taxonomy"] for x in r["results"]}) > 1 and "appliedFilters" not in r
    assert r["diagnostics"]["queryPlan"]["taxonomy"]["strength"] == "weak"
    assert "weak_taxonomy_cue" in r["diagnostics"]["queryPlan"]["fallbackReasons"]
    strong = strict("khách sạn Nha Trang", limit=50)
    assert {x["taxonomy"] for x in strong["results"]} == {"hotel"}
    assert strong["diagnostics"]["queryPlan"]["taxonomy"]["strength"] == "strong"
    assert strong["appliedFilters"]["hard"] == {"taxonomy": "hotel", "taxonomySource": "query"}


# ------------------------------------------------------------------ dấu thanh
class _SpyEmbedder(FakeEmbedder):
    def __init__(self):
        self.seen = []

    def embed_query(self, q):
        self.seen.append(q)
        return super().embed_query(q)


def test_tone_normalize_moves_tone_marks_to_catalog_style(party):
    q = "thuỷ cung hoà bình"
    spy_on, spy_off = _SpyEmbedder(), _SpyEmbedder()
    on = _engine(party, embedder=spy_on, tone_normalize=True)(q, limit=5)
    off = _engine(party, embedder=spy_off)(q, limit=5)
    assert on["diagnostics"]["normalizedQuery"] == "thủy cung hòa bình" and spy_on.seen == ["thủy cung hòa bình"]
    assert "normalizedQuery" not in off["diagnostics"] and spy_off.seen == [q]
    e = _engine(party, tone_normalize=True)
    assert e.query_text(q) == "thủy cung hòa bình"                        # prewarm nạp đúng khoá cache


# ------------------------------------------------------------------ mặc định ≡ 1.15.0
def test_extended_plan_keys_appear_only_with_their_knob(services):
    off = _engine(services, negation_filter=False)("không lấy combo, vé lẻ Nha Trang", limit=50)
    assert "queryPlan" not in off["diagnostics"]          # chỉ parse ra loại bị phủ định → khoá 1.16.0, cờ tắt thì như 1.15.0
    assert "C1" in _ids(off)
    on = _engine(services, negation_filter=True)("không lấy combo, vé lẻ Nha Trang", limit=50)
    assert on["diagnostics"]["queryPlan"]["mustNot"] == {"amenities": [], "brands": [], "taxonomies": ["combo"]}
    assert "C1" not in _ids(on) and on["appliedFilters"]["hard"]["mustNotTaxonomies"] == ["combo"]


def test_fuzzy_index_is_built_once_and_only_when_on(services):
    off = _engine(services, lexical=services["vectors"], hybrid=HybridConfig())
    assert off.fuzzy_on is False and off._fuzzy is None
    on = _engine(services, lexical=services["vectors"], hybrid=HybridConfig(fuzzy_k=3))
    assert on.fuzzy_on and len(on._fuzzy) == len(services["index"].units)
    first = on._fuzzy
    on("Vinwondrs Nha Trang")
    assert on._fuzzy is first
    nd_only = _engine(services, lexical=services["vectors"], hybrid=HybridConfig(), no_diacritics=HybridConfig(fuzzy_k=2))
    assert nd_only.fuzzy_on and not _engine(services, hybrid=HybridConfig(fuzzy_k=3)).fuzzy_on   # không lexical → không hybrid
    assert np.all(np.isfinite(on._fuzzy.sizes))
