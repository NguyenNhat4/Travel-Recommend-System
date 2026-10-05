"""Cổng APP (app_adapter.py): UnitIndex từ snapshot + text T3+R, tham số arm, bọc SearchProducts — không cần Weaviate
(engine giả). Nạp ProductBench và parity với B0 là test integration (`pytest -m integration`)."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from evaluation.search_bench import app_adapter as A, catalog, runner as R
from evaluation.search_bench.arms import load_arm
from evaluation.search_bench.store import filters as F
from evaluation.search_bench.textbuild import load_texts

APP_ARMS = ("APP.dense", "APP.dense_nocut", "APP.hybrid", "APP.hybrid_nocut", "APP.hybrid_norm", "APP.hybrid_norm_nocut")
# 05/10 (fix/search): cổng APP trên e5-small (collection riêng) + biến thể F1 (dest) / F2 (nodia)
E5_ARMS = ("APP.e5s.dense_nocut", "APP.e5s.hybrid_nocut", "APP.e5s.hybrid_norm_nocut", "APP.e5s.hybrid_norm_nocut_dest",
           "APP.e5s.hybrid_norm_nocut_nodia", "APP.e5s.hybrid_norm_nocut_dest_nodia")
# 06/10: query plan F3 (neg) / F4 (tax) / F5 (route) / F6 (num) và tổ hợp (qp) trên mốc không cutoff + trên arm đầy đủ có cutoff
QP_ARMS = ("APP.e5s.hybrid_norm_nocut_neg", "APP.e5s.hybrid_norm_nocut_tax", "APP.e5s.hybrid_norm_nocut_route",
           "APP.e5s.hybrid_norm_nocut_num", "APP.e5s.hybrid_norm_nocut_qp", "APP.e5s.hybrid_norm_c84_dest_nodia_nc80_qp")
# mọi arm APP có trong arms/ (dùng để kiểm hash phân biệt và khoá bắt buộc)
ALL_APP_ARMS = APP_ARMS + E5_ARMS + ("APP.e5s.dense", "APP.e5s.hybrid", "APP.e5s.hybrid_norm", "APP.e5s.hybrid_norm_c84", "APP.e5s.hybrid_norm_c84_dest", "APP.e5s.hybrid_norm_c84_nodia",
                                     "APP.e5s.hybrid_norm_c84_dest_nodia", "APP.e5s.hybrid_norm_c84_nodia_nc80",
                                     "APP.e5s.hybrid_norm_c84_dest_nodia_nc80") + QP_ARMS


@pytest.fixture()
def sample_home(cfg, home):
    catalog.build_catalog(cfg, "sample")
    return home


def test_app_arms_load_and_hash_by_params():
    arms = {a: load_arm(a) for a in APP_ARMS}
    assert all(x.engine == "app" and x.composite and x.model == "cohere-v3" and x.text_variant == "T3+R" for x in arms.values())
    assert arms["APP.dense"].app["hybrid"] is False and arms["APP.hybrid_norm"].app["normalize"] is True
    assert arms["APP.dense"].app["cutoff"] == 0.62 and arms["APP.dense_nocut"].app["cutoff"] == -1.0
    assert len({R.config_hash(x) for x in arms.values()}) == len(arms)      # mỗi arm một cấu hình khác nhau
    assert arms["APP.hybrid"].parent == "APP.dense" and arms["APP.hybrid_norm"].parent == "APP.hybrid"
    for a in APP_ARMS:
        A.app_params(arms[a].app)
    with pytest.raises(A.AppAdapterError, match="app.cutoff"):
        A.app_params({"hybrid": True})
    # khoá F1/F2 (05/10) bắt buộc và đúng giá trị production hôm nay (tắt) ở mọi arm Cohere
    for a in APP_ARMS:
        assert arms[a].app["dest_filter"] is False and arms[a].app["no_diacritics_mode"] == "off"
        assert set(arms[a].app["no_diacritics"]) == set(A.NO_DIACRITICS_KEYS)
    with pytest.raises(A.AppAdapterError, match="no_diacritics"):
        A.app_params({**A.APP_DEFAULTS, "no_diacritics": {"lexical_k": 20}})
    with pytest.raises(A.AppAdapterError, match="no_diacritics_mode"):
        A.app_params({**A.APP_DEFAULTS, "no_diacritics_mode": "on"})


@pytest.mark.parametrize("key", A.QUERY_PLAN_KEYS)
def test_app_params_requires_query_plan_keys(key):
    """06/10: bốn cờ query plan bắt buộc như dest_filter — arm thiếu một khoá thì lỗi nêu đúng tên khoá."""
    assert A.APP_DEFAULTS[key] is False
    with pytest.raises(A.AppAdapterError, match=f"app.{key}"):
        A.app_params({k: v for k, v in A.APP_DEFAULTS.items() if k != key})
    assert A.app_params(A.APP_DEFAULTS)[key] is False


def test_existing_app_arms_have_query_plan_off():
    """Mọi arm APP có từ trước (Cohere + e5s) giữ production hôm nay: bốn cờ query plan đều false (bool thật, không phải chuỗi)."""
    for a in ALL_APP_ARMS:
        if a in QP_ARMS:
            continue
        app = load_arm(a).app
        assert all(app[k] is False for k in A.QUERY_PLAN_KEYS), a


def test_qp_arms_toggle_f3_f6_and_hash_distinct():
    arms = {a: load_arm(a) for a in QP_ARMS}
    assert all(x.engine == "app" and x.model == "e5-small" and x.text_variant == "T3+R" and x.composite for x in arms.values())
    on = {a: {k for k in A.QUERY_PLAN_KEYS if arms[a].app[k] is True} for a in QP_ARMS}
    assert on["APP.e5s.hybrid_norm_nocut_neg"] == {"negation_filter"} and on["APP.e5s.hybrid_norm_nocut_tax"] == {"taxonomy_filter"}
    assert on["APP.e5s.hybrid_norm_nocut_route"] == {"route_filter"} and on["APP.e5s.hybrid_norm_nocut_num"] == {"numeric_filter"}
    assert on["APP.e5s.hybrid_norm_nocut_qp"] == set(A.QUERY_PLAN_KEYS) == on["APP.e5s.hybrid_norm_c84_dest_nodia_nc80_qp"]
    # năm arm trên mốc không cutoff kế thừa đúng mốc (parent + knob F1/F2 tắt); arm cuối trên arm đầy đủ có cutoff
    base = load_arm("APP.e5s.hybrid_norm_nocut").app
    for a in QP_ARMS[:5]:
        assert arms[a].parent == "APP.e5s.hybrid_norm_nocut"
        assert {k: v for k, v in arms[a].app.items() if k not in A.QUERY_PLAN_KEYS} == {k: v for k, v in base.items() if k not in A.QUERY_PLAN_KEYS}
    full = arms["APP.e5s.hybrid_norm_c84_dest_nodia_nc80_qp"]
    nc80 = load_arm("APP.e5s.hybrid_norm_c84_dest_nodia_nc80").app
    assert full.parent == "APP.e5s.hybrid_norm_c84_dest_nodia_nc80"
    assert (full.app["cutoff"], full.app["dest_filter"], full.app["no_diacritics_mode"], full.app["no_diacritics"]["cutoff"]) == (0.84, True, "relax", 0.80)
    assert {k: v for k, v in full.app.items() if k not in A.QUERY_PLAN_KEYS} == {k: v for k, v in nc80.items() if k not in A.QUERY_PLAN_KEYS}
    for a in QP_ARMS:
        A.app_params(arms[a].app)
    # mỗi arm QP một cấu hình khác nhau và khác mọi arm APP có từ trước
    assert len({R.config_hash(load_arm(a)) for a in ALL_APP_ARMS}) == len(ALL_APP_ARMS) == len(set(ALL_APP_ARMS))


def test_e5_app_arms_toggle_f1_f2_and_hash_distinct():
    arms = {a: load_arm(a) for a in E5_ARMS}
    assert all(x.engine == "app" and x.model == "e5-small" and x.app["cutoff"] == -1.0 for x in arms.values())
    assert arms["APP.e5s.hybrid_norm_nocut"].app["dest_filter"] is False and arms["APP.e5s.hybrid_norm_nocut_dest"].app["dest_filter"] is True
    assert arms["APP.e5s.hybrid_norm_nocut_nodia"].app["no_diacritics_mode"] == "relax"
    assert arms["APP.e5s.hybrid_norm_nocut_dest_nodia"].app["dest_filter"] is True and         arms["APP.e5s.hybrid_norm_nocut_dest_nodia"].app["no_diacritics_mode"] == "relax"
    assert len({R.config_hash(x) for x in arms.values()}) == len(arms)
    assert len({R.config_hash(load_arm(a)) for a in APP_ARMS + E5_ARMS}) == len(APP_ARMS) + len(E5_ARMS)
    for a in E5_ARMS:
        A.app_params(arms[a].app)


def test_applied_filter_of_reads_hard_destination():
    assert A.applied_filter_of({"appliedFilters": {"hard": {"destination": "Nha Trang", "destinationSource": "query"}, "soft": {}}}) ==         {"eq": ["destination", "Nha Trang"]}
    assert A.applied_filter_of({}) is None and A.applied_filter_of({"appliedFilters": None}) is None
    assert A.applied_filter_of({"appliedFilters": {"hard": {}, "soft": {"starRatingMin": 4}}}) is None


@pytest.mark.parametrize("hard, expected", [
    ({"taxonomy": "hotel", "taxonomySource": "query"}, {"eq": ["taxonomy", "hotel"]}),
    ({"origin": "Hà Nội", "originSource": "query", "destinationCity": "Đà Nẵng"}, {"eq": ["origin_city", "Hà Nội"]}),
    ({"mustNotAmenities": ["pool", "golf"]}, {"not": {"contains_any": ["features", ["pool", "golf"]]}}),
    ({"mustNotBrands": ["Vinpearl"]}, {"not": {"eq": ["brand", "Vinpearl"]}}),
    ({"mustNotBrands": ["Vinpearl", "Mường Thanh"]},                             # mỗi thương hiệu một node not(eq)
     {"and": [{"not": {"eq": ["brand", "Vinpearl"]}}, {"not": {"eq": ["brand", "Mường Thanh"]}}]}),
    ({"priceMax": 3_000_000, "priceSource": "query"}, {"lte": ["unit_price_min", 3_000_000]}),
    ({"priceMin": 500_000}, {"gte": ["unit_price_min", 500_000]}),
    ({"priceMin": 0}, {"gte": ["unit_price_min", 0]}),                        # 0 là giá trị hợp lệ, không phải "không có"
    # chỉ các khoá bị bỏ qua → không lọc
    ({"destinationSource": "query", "destinationCity": "Đà Nẵng", "availableOnly": True, "mustNotAmenities": [],
      "mustNotBrands": []}, None),
])
def test_applied_filter_of_maps_each_hard_key(hard, expected):
    """06/10: từng khoá `appliedFilters.hard` của query plan → một node filter của bench (tên trường theo items / store/filters.py)."""
    got = A.applied_filter_of({"appliedFilters": {"hard": hard, "soft": {}}})
    assert got == expected
    if got is not None:
        F.validate(got)          # evaluator pandas phải nhận được node (not(eq brand) cần brand trong NOT_EQ_NULLABLE)


def test_applied_filter_of_combines_hard_keys_with_and():
    hard = {"destination": "Nha Trang", "destinationSource": "query", "taxonomy": "hotel", "taxonomySource": "query",
            "origin": "Hà Nội", "originSource": "query", "destinationCity": "Nha Trang", "mustNotAmenities": ["pool"],
            "mustNotBrands": ["Vinpearl"], "priceMin": 500_000, "priceMax": 3_000_000, "priceSource": "query",
            "availableOnly": True}
    got = A.applied_filter_of({"appliedFilters": {"hard": hard, "soft": {"starRatingMin": 4, "starRatingSource": "query"}}})
    assert got == {"and": [{"eq": ["destination", "Nha Trang"]}, {"eq": ["taxonomy", "hotel"]}, {"eq": ["origin_city", "Hà Nội"]},
                           {"not": {"contains_any": ["features", ["pool"]]}}, {"not": {"eq": ["brand", "Vinpearl"]}},
                           {"gte": ["unit_price_min", 500_000]}, {"lte": ["unit_price_min", 3_000_000]}]}
    F.validate(got)
    # hai khoá → and hai phần tử, không lồng
    two = A.applied_filter_of({"appliedFilters": {"hard": {"destination": "Nha Trang", "priceMax": 1_000_000}}})
    assert two == {"and": [{"eq": ["destination", "Nha Trang"]}, {"lte": ["unit_price_min", 1_000_000]}]}


def test_build_app_catalog_matches_bench_text(cfg, sample_home):
    cat = A.build_app_catalog(cfg, "sample")
    items = catalog.read_items("sample")
    assert len(cat.index.units) == len(items) == 26 and set(cat.texts) == set(items["product_id"])
    tdf, _ = load_texts(cfg, "sample", "T3+R")
    assert dict(zip(tdf["product_id"], tdf["text"])) == cat.texts           # text = T3+R của bench = production
    assert cat.index.model_version == A.MODEL_VERSION
    assert cat.index.available.dtype == bool and cat.index.taxonomy.shape == (26,)
    p = cat.index.units[0]
    assert p.product_id == items["product_id"].iloc[0] and p.taxonomy in ("hotel", "flight", "attraction", "combo", "golf")
    assert all(cat.index.idx[parent] is not None for parent in cat.index.parent_of.values())
    assert all(len(h) == 64 for h in cat.text_hash.values())


class _Engine:
    """Giả SearchProducts: trả 3 kết quả cố định, nhớ câu đã nhận."""

    def __init__(self):
        self.calls = []

    def __call__(self, q, *, limit):
        self.calls.append((q, limit))
        return {"results": [{"productId": f"p{i}", "score": 0.9 - i * 0.1} for i in range(3)], "total": 3, "topScore": 0.9,
                "cutoff": 0.62, "appliedFilters": {"hard": {"destination": "Nha Trang", "destinationSource": "query"}, "soft": {}},
                "diagnostics": {"normalizedQuery": q.upper(), "lexicalCount": 1, "lexicalCandidates": 5,
                                "derivedDestinations": ["Nha Trang"], "destinationFilter": {"source": "query", "value": "Nha Trang"},
                                "queryProfile": "no_diacritics",
                                # 06/10: query plan F3–F6 (contract EngineDiagnostics.queryPlan)
                                "queryPlan": {"taxonomy": {"value": "hotel", "source": "query", "skipped": None, "candidates": ["hotel"]},
                                              "route": None, "mustNot": {"amenities": ["pool"], "brands": []}, "softDropped": [],
                                              "unresolved": [], "price": None, "star": None, "lexicalText": q,
                                              "applied": ["destination"], "revalidatedDrops": 0, "emptyReason": None, "ignored": []}}}


def test_app_search_and_retrieve_app(cfg, sample_home):
    eng = _Engine()
    s = A.AppSearch(engine=eng, params=A.APP_DEFAULTS)
    ids, scores, diag = s.search("resort", limit=10)
    assert ids == ["p0", "p1", "p2"] and scores[0] == pytest.approx(0.9) and diag["normalizedQuery"] == "RESORT" and diag["lexicalCount"] == 1
    env = R.load_env(cfg, "sample", __import__("pathlib").Path(__file__).parent / "fixtures" / "gold_small.jsonl", run_id="t")
    ctx = SimpleNamespace(make_search=lambda arm_app, emb: s)
    got = A.retrieve_app(load_arm("APP.hybrid_norm"), env, ctx, embedder=None)
    assert [g.qid for g in got] == [g.qid for g in env.gold] and got[0].top_ids == ["p0", "p1", "p2"]
    assert got[0].extra["normalizedQuery"] == env.gold[0].text.upper() and got[0].latency_ms >= 0
    # 05/10: diagnostics F1/F2 vào extra; hard filter điểm đến → applied_filter cho filter_recall_loss
    assert diag["derivedDestinations"] == ["Nha Trang"] and diag["destinationFilter"]["source"] == "query"
    assert diag["queryProfile"] == "no_diacritics" and diag["cutoff"] == 0.62
    assert got[0].applied_filter == {"eq": ["destination", "Nha Trang"]}
    assert eng.calls[1] == (env.gold[0].text, 10)                            # calls[0] là lượt s.search("resort") ở trên
    # 06/10: queryPlan vào extra nguyên khối, appliedFilters vẫn giữ
    assert diag["queryPlan"]["mustNot"] == {"amenities": ["pool"], "brands": []} and diag["queryPlan"]["taxonomy"]["value"] == "hotel"
    assert got[0].extra["queryPlan"]["applied"] == ["destination"] and got[0].extra["appliedFilters"]["hard"]["destination"] == "Nha Trang"


def test_app_search_extra_has_query_plan_without_gold():
    """Engine giả không có queryPlan (backend cũ) → extra.queryPlan = None, không lỗi; có thì giữ nguyên khối."""
    class Eng:
        def __call__(self, q, *, limit):
            return {"results": [], "total": 0, "topScore": None, "appliedFilters": {"hard": {}, "soft": {}}, "diagnostics": {}}
    ids, scores, diag = A.AppSearch(engine=Eng(), params=A.APP_DEFAULTS).search("x", limit=3)
    assert ids == [] and scores == [] and diag["queryPlan"] is None and diag["appliedFilters"] == {"hard": {}, "soft": {}}
    assert A.applied_filter_of(diag) is None
    eng = _Engine()
    _, _, diag = A.AppSearch(engine=eng, params=A.APP_DEFAULTS).search("khách sạn không có hồ bơi", limit=3)
    assert set(diag["queryPlan"]) >= {"taxonomy", "route", "mustNot", "softDropped", "unresolved", "price", "star", "lexicalText",
                                      "applied", "revalidatedDrops", "emptyReason", "ignored"}
    assert diag["queryPlan"]["lexicalText"] == "khách sạn không có hồ bơi"


def test_make_search_passes_query_plan_flags(monkeypatch):
    """`make_search` chuyển bốn cờ query plan thành kwargs cùng tên của SearchProducts (giả backend, không Weaviate)."""
    seen = {}

    class FakeSearchProducts:
        def __init__(self, *args, **kwargs):
            seen.update(kwargs)

    class FakeHybridConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(A, "_backend", lambda: (None, FakeSearchProducts, None, FakeHybridConfig, None))
    ctx = A.AppContext(cfg=None, dataset="x", cat=SimpleNamespace(index=None))
    ctx._vs = object()
    for flags in ({}, {"negation_filter": True, "route_filter": True}, dict.fromkeys(A.QUERY_PLAN_KEYS, True)):
        seen.clear()
        s = ctx.make_search({**A.APP_DEFAULTS, **flags}, embedder=None)
        assert isinstance(s, A.AppSearch)
        assert {k: seen[k] for k in A.QUERY_PLAN_KEYS} == {k: bool(flags.get(k, False)) for k in A.QUERY_PLAN_KEYS}
        assert seen["dest_filter"] is False and seen["normalize"] is True


def test_bench_query_embedder_wraps_cached_embedder():
    class Emb:
        def embed(self, texts, input_type):
            assert input_type == "query"
            return np.ones((len(texts), 4), dtype="float32")
    v = A.BenchQueryEmbedder(Emb()).embed_query("x")
    assert v.shape == (4,) and v.dtype == np.float32
    with pytest.raises(A.AppAdapterError):
        A.BenchQueryEmbedder(Emb()).embed_docs(["x"])


def test_runner_requires_app_ctx_for_app_arm(cfg, sample_home):
    env = R.load_env(cfg, "sample", __import__("pathlib").Path(__file__).parent / "fixtures" / "gold_small.jsonl", run_id="t")
    with pytest.raises(R.RunnerError, match="AppContext"):
        R.retrieve(load_arm("APP.dense"), env, store=None, embedder=None, physical="P", fold_mode="shadow")


@pytest.mark.integration
def test_product_bench_loads_and_dense_nocut_matches_b0(cfg):
    """Cần Weaviate bench + vector B0 của dataset jsonl: ProductBench đủ object, APP.dense_nocut ≈ B0 (khác chỉ do hnsw)."""
    cat = A.build_app_catalog(cfg, "jsonl")
    s = A.load_product_bench(cfg, "jsonl", cat)
    assert s["n"] == len(cat.texts) and s["missing"] == 0 and s["stale"] == 0


# ------------------------------------------------------------------ model khác Cohere v3 (05/10, Day 5 Search: e5-small)
def test_app_collection_keeps_productbench_for_production_model():
    assert A.app_collection("cohere-v3") == A.PRODUCT_BENCH == "ProductBench"
    assert A.app_collection("e5-small") == "ProductBench__e5_small"


def _fake_read(meta):
    def read(dataset, variant, model, input_type):
        assert (variant, input_type) == ("T3+R", "document")
        return ["a", "b"], np.ones((2, 384), dtype=np.float32), meta
    return read


def test_model_vectors_model_version_from_meta(monkeypatch):
    monkeypatch.setattr(A.vectors, "read", _fake_read({"cache_model": "intfloat/multilingual-e5-small",
                                                       "text_builder_version": "catalog-text-v2"}))
    ids, vecs, meta, mv = A.model_vectors("sample", "e5-small")
    assert ids == ["a", "b"] and vecs.shape == (2, 384) and mv == "intfloat/multilingual-e5-small:catalog-text-v2"


@pytest.mark.parametrize("model, meta, match", [
    ("e5-small", {"cache_model": "intfloat/multilingual-e5-small", "text_builder_version": "catalog-text-v1"}, "text"),
    ("e5-small", {"cache_model": "", "text_builder_version": "catalog-text-v2"}, "cache_model"),
    ("cohere-v3", {"cache_model": "embed-multilingual-v4.0", "text_builder_version": "catalog-text-v2"}, "production"),
])
def test_model_vectors_rejects_wrong_vectors(monkeypatch, model, meta, match):
    monkeypatch.setattr(A.vectors, "read", _fake_read(meta))
    with pytest.raises(A.AppAdapterError, match=match):
        A.model_vectors("sample", model)


def test_model_vectors_production_keeps_model_version(monkeypatch):
    monkeypatch.setattr(A.vectors, "read", _fake_read({"cache_model": "embed-multilingual-v3.0",
                                                       "text_builder_version": "catalog-text-v2"}))
    assert A.model_vectors("sample", "cohere-v3")[3] == A.MODEL_VERSION


# ------------------------------------------------------------------ guard BM25 sau khi nạp (05/10)
class _FakeBm25Http:
    """Trả điểm BM25 "cũ" cho `stale` lượt gọi snapshot đầu, sau đó điểm "mới" (như Weaviate cập nhật thống kê độ dài)."""

    def __init__(self, stale: int, n_probes: int = len(A.BM25_PROBES)):
        self.calls, self.stale, self.n = 0, stale, n_probes

    def post(self, path, json):
        assert path == "/v1/graphql" and "bm25" in json["query"]
        snap = self.calls // self.n
        self.calls += 1
        score = 1.0 if snap < self.stale else 5.0
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {"data": {"Get": {"C": [{"productId": "p1", "_additional": {"score": str(score)}}]}}})


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def test_wait_bm25_settled_waits_for_change_then_stability():
    clock = _Clock()
    out = A.wait_bm25_settled(_FakeBm25Http(stale=4), "C", poll_s=3, stable_polls=2, sleep=clock.sleep, clock=clock)
    assert out["changed"] is True and out["waited_s"] == 18.0           # đổi ở lần chụp 5 (t=12), giữ 2 lần → t=18


def test_wait_bm25_settled_gives_up_when_nothing_changes():
    clock = _Clock()
    out = A.wait_bm25_settled(_FakeBm25Http(stale=10**6), "C", max_wait_s=9, poll_s=3, sleep=clock.sleep, clock=clock)
    assert out == {"changed": False, "waited_s": 9.0}


def test_bm25_snapshot_raises_on_graphql_error():
    http = SimpleNamespace(post=lambda path, json: SimpleNamespace(raise_for_status=lambda: None,
                                                                   json=lambda: {"errors": [{"message": "no class"}]}))
    with pytest.raises(A.AppAdapterError, match="BM25"):
        A.bm25_snapshot(http, "C")
