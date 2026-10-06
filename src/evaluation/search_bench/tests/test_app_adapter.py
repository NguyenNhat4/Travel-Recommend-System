"""Cổng APP (app_adapter.py): UnitIndex từ snapshot + text T3+R, tham số arm, bọc SearchProducts — không cần Weaviate
(engine giả). Nạp ProductBench và parity với B0 là test integration (`pytest -m integration`)."""
from __future__ import annotations

import zlib
from types import SimpleNamespace

import numpy as np
import pytest

from evaluation.search_bench import app_adapter as A, catalog, paths, runner as R
from evaluation.search_bench.arms import load_arm
from evaluation.search_bench.rerank import RerankCache, Reranker, rerank_params
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


def test_build_app_catalog_attrs_flags_occupancy_children(cfg, sample_home, monkeypatch):
    """06/10 (kiến trúc §6): cờ combo lấy từ `item_kind` của `combo_enrichment` (= catalog.combo_items của production);
    sức chứa / danh sách con dựng kèm phòng/chuyến con. Sample không có combo bay/ở → bọc combo_enrichment để thêm kind."""
    real = catalog.combo_enrichment
    picked = {}

    def with_flight_hotel(records, manual):
        items, attrs, info = real(records, manual)
        cid = sorted(items)[0]
        picked["cid"] = cid
        return {**items, cid: [*items[cid], {"item_kind": "flight"}, {"item_kind": "hotel"}]}, attrs, info

    monkeypatch.setattr(catalog, "combo_enrichment", with_flight_hotel)
    cat = A.build_app_catalog(cfg, "sample")
    ix, a = cat.index, cat.index.attrs
    records = catalog.reload_records(cfg, "sample")
    by_id = {r["productId"]: r for r in records}
    _, children, _, _ = catalog.group_children(records, cfg.catalog.search_unit_variants)

    def occ(r):
        v = (r.get("attributes") or {}).get("maxOccupancy")
        return float(v) if isinstance(v, (int, float)) and v >= 1 else None

    for i, p in enumerate(ix.units):
        rec = by_id[p.product_id]
        want = {"includesFlight", "includesHotel"} if p.product_id == picked["cid"] else set()
        if p.taxonomy == "attraction" and (rec.get("attributes") or {}).get("ticketed") is True:
            want.add("ticketed")
        assert a.flags[i] == want, p.product_id
        kids = children.get(p.product_id, [])
        assert sorted(c[0] for c in a.children[i]) == sorted(k["productId"] for k in kids)
        occs = [o for o in (occ(rec), *(occ(k) for k in kids)) if o is not None]
        assert (a.max_occupancy[i] == max(occs)) if occs else np.isnan(a.max_occupancy[i])
    assert ix.attrs.flags[ix.idx[picked["cid"]]] == {"includesFlight", "includesHotel"}
    assert not ix.mask(exclude_flags=["includesFlight"], only_available=False)[ix.idx[picked["cid"]]]
    assert any(len(c) for c in a.children) and not np.isnan(a.max_occupancy).all()   # sample có phòng khai sức chứa


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


# ------------------------------------------------------------------ 06/10: ma trận ablation (núm mới, lexical-only, rerank)
NEW_KNOBS = A.ENGINE_FLAG_KEYS + A.HYBRID_CHANNEL_KEYS + ("retrieval_mode",)
A_BASE = "APP.e5s.hybrid_norm_nocut"
ALL = "APP.e5s.hybrid_norm_nocut_all"
# arm mới của ma trận → (cha, các khoá app đổi so với cha)
MATRIX = {
    f"{A_BASE}_tax_strong": (A_BASE, {"taxonomy_filter", "taxonomy_strong_only"}),
    f"{A_BASE}_party": (A_BASE, {"party_filter"}),
    f"{A_BASE}_tone": (A_BASE, {"tone_normalize"}),
    f"{A_BASE}_fuzzy": (A_BASE, {"fuzzy_k"}),
    f"{A_BASE}_fuzzy60": (A_BASE, {"fuzzy_k", "fuzzy_min_sim"}),
    f"{A_BASE}_wrrf": (A_BASE, {"lexical_weight"}),
    f"{A_BASE}_wrrf_d": (A_BASE, {"dense_weight"}),
    f"{A_BASE}_lexonly": (A_BASE, {"retrieval_mode"}),
    ALL: (A_BASE, {"dest_filter", "no_diacritics_mode", *A.QUERY_PLAN_KEYS, "taxonomy_strong_only", "party_filter",
                   "tone_normalize", "fuzzy_k"}),
    **{f"{ALL}_minus_{s}": (ALL, {k}) for s, k in (("dest", "dest_filter"), ("nodia", "no_diacritics_mode"),
                                                   ("neg", "negation_filter"), ("tax", "taxonomy_filter"),
                                                   ("route", "route_filter"), ("num", "numeric_filter"),
                                                   ("party", "party_filter"), ("tone", "tone_normalize"), ("fuzzy", "fuzzy_k"))},
    f"{ALL}_c84": (ALL, {"cutoff", "no_diacritics"}),
    f"{ALL}_rr": (ALL, set()),
    f"{A_BASE}_rr": (A_BASE, set()),
}


@pytest.mark.parametrize("key", NEW_KNOBS)
def test_app_params_requires_new_knobs(key):
    """06/10: núm mới bắt buộc như các khoá trước (spec §1.5) — thiếu thì lỗi nêu đúng tên khoá; mặc định = production (tắt)."""
    with pytest.raises(A.AppAdapterError, match=f"app.{key}"):
        A.app_params({k: v for k, v in A.APP_DEFAULTS.items() if k != key})
    assert A.APP_DEFAULTS[key] == {**A.NEUTRAL, "fuzzy_candidate_k": 50, "fuzzy_min_sim": 0.75, "retrieval_mode": "hybrid"}[key]


@pytest.mark.parametrize("patch, match", [
    ({"retrieval_mode": "bm25"}, "retrieval_mode"),
    ({"hybrid": False}, "mâu thuẫn"),                                       # hybrid false phải đi với dense
    ({"retrieval_mode": "dense"}, "mâu thuẫn"),                             # dense phải đi với hybrid false
    ({"hybrid": False, "retrieval_mode": "dense", "fuzzy_k": 5}, "dense"),
    ({"hybrid": False, "retrieval_mode": "dense", "lexical_weight": 0.5}, "dense"),
    ({"retrieval_mode": "lexical", "lexical_weight": 0.0}, "lexical_weight"),
    ({"fuzzy_k": -1}, "fuzzy_k"),
    ({"fuzzy_min_sim": 1.5}, "fuzzy_min_sim"),
    ({"dense_weight": -0.1}, "weight"),
])
def test_app_params_rejects_inconsistent_knobs(patch, match):
    with pytest.raises(A.AppAdapterError, match=match):
        A.app_params({**A.APP_DEFAULTS, **patch})


def test_app_params_accepts_modes():
    assert A.app_params({**A.APP_DEFAULTS, "retrieval_mode": "lexical"})["retrieval_mode"] == "lexical"
    assert A.app_params({**A.APP_DEFAULTS, "hybrid": False, "retrieval_mode": "dense"})["hybrid"] is False


def _all_app_arm_ids() -> list[str]:
    return sorted(p.stem for p in paths.ARMS_DIR.glob("APP.*.yaml"))


def test_every_app_arm_yaml_loads_with_valid_params_and_distinct_hash():
    ids = _all_app_arm_ids()
    assert set(ALL_APP_ARMS) | set(MATRIX) <= set(ids)
    arms = {a: load_arm(a) for a in ids}
    for a, arm in arms.items():
        assert arm.engine == "app" and arm.text_variant == "T3+R", a
        A.app_params(arm.app)                                              # đủ khoá + nhất quán hybrid ⇔ retrieval_mode
        if arm.rerank is not None:
            rerank_params(arm.rerank, k=10)
        if arm.parent and arm.parent.startswith("APP."):
            assert arm.parent in arms, (a, arm.parent)                   # cha là arm APP có thật (vs_parent so được)
    assert len({R.config_hash(x) for x in arms.values()}) == len(arms)   # mỗi arm một cấu hình


def test_existing_app_arms_keep_new_knobs_neutral():
    """Arm có từ trước: núm mới = production hôm nay (hành vi không đổi; hash đổi vì thêm khoá — dự kiến)."""
    for a in ALL_APP_ARMS:
        app = load_arm(a).app
        assert all(app[k] == A.NEUTRAL[k] for k in A.NEUTRAL), a
        assert (app["fuzzy_candidate_k"], app["fuzzy_min_sim"]) == (50, 0.75), a
        assert app["retrieval_mode"] == ("hybrid" if app["hybrid"] else "dense"), a
        assert load_arm(a).rerank is None


@pytest.mark.parametrize("arm_id", sorted(MATRIX))
def test_matrix_arm_changes_exactly_listed_knobs(arm_id):
    parent, changed = MATRIX[arm_id]
    arm, par = load_arm(arm_id), load_arm(parent)
    assert arm.parent == parent and arm.composite and arm.model == "e5-small" and arm.retrieval == "hybrid"
    assert {k for k in arm.app if arm.app[k] != par.app[k]} == changed
    hard = any(arm.app[k] for k in ("dest_filter", *A.QUERY_PLAN_KEYS, "party_filter"))
    assert arm.filters["qu"] is hard                                      # quy ước cũ: qu = có hard filter suy từ câu


def test_matrix_arm_values():
    a = {x: load_arm(x).app for x in MATRIX}
    assert a[f"{A_BASE}_fuzzy"]["fuzzy_k"] == 10 and a[f"{A_BASE}_fuzzy"]["fuzzy_min_sim"] == 0.75
    assert a[f"{A_BASE}_fuzzy60"]["fuzzy_min_sim"] == 0.6
    assert (a[f"{A_BASE}_wrrf"]["dense_weight"], a[f"{A_BASE}_wrrf"]["lexical_weight"]) == (1.0, 0.5)
    assert (a[f"{A_BASE}_wrrf_d"]["dense_weight"], a[f"{A_BASE}_wrrf_d"]["lexical_weight"]) == (0.5, 1.0)
    assert a[f"{A_BASE}_lexonly"]["retrieval_mode"] == "lexical" and a[f"{A_BASE}_lexonly"]["hybrid"] is True
    full = a[ALL]
    assert full["cutoff"] == -1.0 and full["no_diacritics_mode"] == "relax" and full["no_diacritics"]["cutoff"] is None
    assert all(full[k] is True for k in ("dest_filter", *A.QUERY_PLAN_KEYS, *A.ENGINE_FLAG_KEYS))
    assert (full["fuzzy_k"], full["fuzzy_min_sim"], full["dense_weight"], full["lexical_weight"]) == (10, 0.75, 1.0, 1.0)
    qp = load_arm("APP.e5s.hybrid_norm_c84_dest_nodia_nc80_qp").app
    assert {k: v for k, v in full["no_diacritics"].items() if k != "cutoff"} == {k: v for k, v in qp["no_diacritics"].items() if k != "cutoff"}
    assert a[f"{ALL}_c84"]["cutoff"] == 0.84 and a[f"{ALL}_c84"]["no_diacritics"]["cutoff"] == 0.80
    assert a[f"{ALL}_minus_tax"]["taxonomy_strong_only"] is True and a[f"{ALL}_minus_fuzzy"]["fuzzy_k"] == 0
    for rr in (f"{ALL}_rr", f"{A_BASE}_rr"):
        r = load_arm(rr).rerank
        assert r == {"model": "BAAI/bge-reranker-v2-m3", "top_n": 30, "parent_engine": "app", "query": "raw",
                     "batch_size": 16, "max_length": 512}


class _Spy:
    """SearchProducts / HybridConfig giả nhận mọi kwargs (như test cũ)."""

    seen: list

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs
        type(self).seen.append(self)


def _spy_ctx(monkeypatch, search_cls=None, hybrid_cls=None):
    class SP(_Spy):
        seen = []

    class HC(_Spy):
        seen = []

    sp, hc = search_cls or SP, hybrid_cls or HC
    monkeypatch.setattr(A, "_backend", lambda: (None, sp, None, hc, None))
    ctx = A.AppContext(cfg=None, dataset="x", cat=SimpleNamespace(index=None))
    ctx._vs = object()
    return ctx, sp, hc


def test_make_search_passes_new_knobs(monkeypatch):
    ctx, SP, HC = _spy_ctx(monkeypatch)
    knobs = {"tone_normalize": True, "taxonomy_strong_only": True, "party_filter": True, "fuzzy_k": 10, "fuzzy_candidate_k": 40,
             "fuzzy_min_sim": 0.6, "dense_weight": 0.5, "lexical_weight": 0.25, "fuzzy_weight": 2.0}
    s = ctx.make_search({**A.APP_DEFAULTS, **knobs, "no_diacritics_mode": "relax"}, embedder=None)
    kw = SP.seen[-1].kwargs
    assert {k: kw[k] for k in A.ENGINE_FLAG_KEYS} == dict.fromkeys(A.ENGINE_FLAG_KEYS, True)
    assert kw["candidate_k"] == 200 and kw["lexical"] is ctx._vs and s.params["fuzzy_k"] == 10
    main, nd = HC.seen[-2].kwargs, HC.seen[-1].kwargs                     # hybrid chung, rồi bộ câu không dấu
    assert kw["hybrid"] is HC.seen[-2] and kw["no_diacritics"] is HC.seen[-1]
    for cfg_kw in (main, nd):                                             # núm của kênh đi vào CẢ hai bộ ngưỡng
        assert {k: cfg_kw[k] for k in A.HYBRID_CHANNEL_KEYS} == {k: knobs[k] for k in A.HYBRID_CHANNEL_KEYS}
        assert isinstance(cfg_kw["fuzzy_k"], int) and isinstance(cfg_kw["dense_weight"], float)
    assert (main["lexical_k"], nd["lexical_k"]) == (10, 20)


def test_make_search_lexical_mode_empties_dense_channel(monkeypatch):
    ctx, SP, HC = _spy_ctx(monkeypatch)
    ctx.make_search({**A.APP_DEFAULTS, "retrieval_mode": "lexical"}, embedder=None)
    kw = SP.seen[-1].kwargs
    assert kw["candidate_k"] == 0 and kw["hybrid"] is HC.seen[-1] and kw["lexical"] is ctx._vs
    assert kw["lexical_candidate_k"] == 50 and kw["cutoff"] == A.APP_DEFAULTS["cutoff"]


def test_make_search_dense_mode_has_no_channel(monkeypatch):
    ctx, SP, HC = _spy_ctx(monkeypatch)
    ctx.make_search({**A.APP_DEFAULTS, "hybrid": False, "retrieval_mode": "dense"}, embedder=None)
    kw = SP.seen[-1].kwargs
    assert kw["hybrid"] is None and kw["lexical"] is None and kw["candidate_k"] == 200 and HC.seen == []


def test_make_search_guards_fields_backend_lacks(monkeypatch):
    """Backend cũ (dataclass không có field mới): giá trị tắt → không truyền; giá trị bật → lỗi 'backend chưa có field'."""
    import dataclasses as dc

    @dc.dataclass
    class OldSP:
        index: object
        vectors: object
        embedder: object
        cutoff: float
        candidate_k: int = 200
        lexical: object = None
        hybrid: object = None
        lexical_candidate_k: int = 50
        normalize: bool = True
        dest_filter: bool = False
        dest_filter_fallback: bool = True
        no_diacritics: object = None
        no_diacritics_cutoff: object = None
        no_diacritics_min_tokens: int = 3
        negation_filter: bool = False
        taxonomy_filter: bool = False
        route_filter: bool = False
        numeric_filter: bool = False

    @dc.dataclass(frozen=True)
    class OldHC:
        rrf_k: int = 60
        lexical_k: int = 10
        lexical_cutoff: float = 0.5
        min_coverage: float = 0.6

    ctx, _, _ = _spy_ctx(monkeypatch, search_cls=OldSP, hybrid_cls=OldHC)
    s = ctx.make_search(dict(A.APP_DEFAULTS), embedder=None)              # mọi núm mới tắt → chạy được trên backend cũ
    assert isinstance(s.engine, OldSP) and s.engine.hybrid == OldHC(60, 10, 0.5, 0.6)
    with pytest.raises(A.AppAdapterError, match="backend chưa có field SearchProducts.party_filter"):
        ctx.make_search({**A.APP_DEFAULTS, "party_filter": True}, embedder=None)
    with pytest.raises(A.AppAdapterError, match="backend chưa có field HybridConfig.fuzzy_k"):
        ctx.make_search({**A.APP_DEFAULTS, "fuzzy_k": 10}, embedder=None)
    with pytest.raises(A.AppAdapterError, match="backend chưa có field HybridConfig.lexical_weight"):
        ctx.make_search({**A.APP_DEFAULTS, "lexical_weight": 0.5}, embedder=None)
    # fuzzy_min_sim / fuzzy_candidate_k chỉ có nghĩa khi fuzzy bật → đổi mà fuzzy_k 0 thì vẫn chạy
    ctx.make_search({**A.APP_DEFAULTS, "fuzzy_min_sim": 0.6}, embedder=None)


def test_real_backend_has_every_knob():
    """Backend hiện tại có đủ field cho mọi núm của arm (nếu hỏng: backend đổi tên field → sửa APP_DEFAULTS / arm)."""
    _, SearchProducts, _, HybridConfig, _ = A._backend()
    assert set(A.ENGINE_FLAG_KEYS) | set(A.QUERY_PLAN_KEYS) <= A._init_names(SearchProducts)
    assert set(A.HYBRID_CHANNEL_KEYS) <= A._init_names(HybridConfig)


class _QEmb:
    """Embedder truy vấn giả (CachedEmbedder.embed) — vector tất định theo câu."""

    def __init__(self, dim):
        self.dim = dim

    def embed(self, texts, input_type):
        rng = np.random.default_rng(zlib.crc32(texts[0].encode("utf-8")))
        v = rng.normal(size=(len(texts), self.dim)).astype("float32")
        return v / np.linalg.norm(v, axis=1, keepdims=True)


def _numpy_ctx(cfg):
    from src.backend.app.infrastructure.vectors.numpy_search import NumpyVectorSearch
    cat = A.build_app_catalog(cfg, "sample")
    ids = [p.product_id for p in cat.index.units]
    rng = np.random.default_rng(7)
    E = rng.normal(size=(len(ids), 16)).astype("float32")
    E /= np.linalg.norm(E, axis=1, keepdims=True)
    vs = NumpyVectorSearch(ids, E, texts=[f"{p.name} {p.name} {cat.texts[p.product_id]}" for p in cat.index.units])
    ctx = A.AppContext(cfg=cfg, dataset="sample", cat=cat, dimension=16)
    ctx._vs = vs
    return ctx, vs


def test_lexical_mode_real_use_case_ranks_by_bm25_only(cfg, sample_home):
    """SearchProducts thật + kho numpy: lexical = đúng thứ tự BM25 trong mask (không unit nào chỉ có ở dense); hybrid thì có."""
    ctx, vs = _numpy_ctx(cfg)
    base = {**A.APP_DEFAULTS, "cutoff": -1.0, "normalize": False}
    lex = ctx.make_search({**base, "retrieval_mode": "lexical"}, _QEmb(16))
    hyb = ctx.make_search(base, _QEmb(16))
    ix = ctx.cat.index
    allowed = ix.allowed_ids(ix.mask(only_available=True))
    checked = 0
    for q in ("resort", "khách sạn", "vé máy bay", "golf"):
        bm = [h.product_id for h in vs.bm25(q, allowed, 50)]
        ids, scores, extra = lex.search(q, limit=10)
        assert ids == bm[:10], q
        assert extra["retrievalMode"] == "lexical"
        h_ids, _, h_extra = hyb.search(q, limit=10)
        assert "retrievalMode" not in h_extra
        if 0 < len(bm) < 10:
            assert len(h_ids) == 10 and set(h_ids) - set(bm)                # hybrid lấp bằng hit dense; lexical thì không
            checked += 1
    assert checked >= 1


class _Engine30:
    def __init__(self):
        self.calls = []

    def __call__(self, q, *, limit):
        self.calls.append((q, limit))
        return {"results": [{"productId": f"p{i}", "score": round(0.9 - i * 0.01, 4)} for i in range(limit)],
                "total": limit, "topScore": 0.9, "cutoff": -1.0, "diagnostics": {"normalizedQuery": q.upper(), "fuzzyCount": 1,
                                                                                  "stageMs": {"dense": 1}, "searchMode": "X"}}


def _fake_score_fn(calls):
    def score(pairs):
        calls.append(len(pairs))
        return np.array([float(t.split()[-1]) for _, t in pairs], dtype="float32"), 0     # text "unit i" → điểm i
    return score


def test_retrieve_app_rerank_reorders_and_caches(cfg, sample_home, tmp_path):
    env = R.load_env(cfg, "sample", __import__("pathlib").Path(__file__).parent / "fixtures" / "gold_small.jsonl", run_id="t")
    arm = load_arm(f"{A_BASE}_rr")
    eng = _Engine30()
    s = A.AppSearch(engine=eng, params=dict(arm.app))
    ctx = SimpleNamespace(make_search=lambda app, emb: s, cat=SimpleNamespace(texts={f"p{i}": f"unit {i}" for i in range(50)}))
    calls = []
    rr = Reranker("m", batch_size=16, max_length=512, cache=RerankCache(tmp_path / "rr.sqlite"), score_fn=_fake_score_fn(calls))
    got = A.retrieve_app(arm, env, ctx, embedder=None, reranker=rr)
    assert all(c[1] == 30 for c in eng.calls)                            # engine trả top-30 (rerank.top_n)
    first = got[0]
    assert first.top_ids == [f"p{i}" for i in range(29, 19, -1)]           # điểm giả = i → đảo thứ tự, cắt top-10
    assert first.top_scores == [round(0.9 - i * 0.01, 4) for i in range(29, 19, -1)]   # cosine đi theo unit
    info = first.extra["rerank"]
    assert (info["topN"], info["inputN"], info["scored"], info["cached"], info["movedIn"]) == (30, 30, 30, 0, 10)
    assert info["scores"][0] == 29.0 and info["modelMs"] >= 0 and info["ms"] >= 0
    assert first.extra["fuzzyCount"] == 1 and first.extra["stageMs"] == {"dense": 1} and "searchMode" not in first.extra
    n_model = sum(calls)
    assert n_model == 30 * len({g.text for g in env.gold})
    again = A.retrieve_app(arm, env, ctx, embedder=None, reranker=rr)     # lần 2: toàn bộ từ cache, 0 lượt model
    assert sum(calls) == n_model and [g.top_ids for g in again] == [g.top_ids for g in got]
    assert again[0].extra["rerank"]["cached"] == 30 and again[0].extra["rerank"]["scored"] == 0
    rr.close()


def test_retrieve_app_rerank_rejects_bad_block(cfg, sample_home):
    env = R.load_env(cfg, "sample", __import__("pathlib").Path(__file__).parent / "fixtures" / "gold_small.jsonl", run_id="t")
    arm = load_arm(f"{A_BASE}_rr")
    bad = arm.model_copy(update={"rerank": {**arm.rerank, "top_n": 5}})
    with pytest.raises(A.AppAdapterError, match="top_n"):
        A.retrieve_app(bad, env, SimpleNamespace(), embedder=None, reranker=object())


# ------------------------------------------------------------------ 06/10: LLM fallback phát lại cache (contract 1.17.0)
def test_llm_block_optional_and_replays_cache_only(tmp_path):
    from evaluation.search_bench import app_adapter as AA
    ctx = AA.AppContext.__new__(AA.AppContext)
    assert ctx.llm_kwargs({}) == {}                                             # vắng khối = off, không đổi arm cũ
    with pytest.raises(AA.AppAdapterError):
        ctx.llm_kwargs({"llm": {"mode": "always", "cache_path": "x.jsonl"}})
    with pytest.raises(AA.AppAdapterError):
        ctx.llm_kwargs({"llm": {"mode": "on", "cache_path": str(tmp_path / "missing.jsonl")}})
    cache = tmp_path / "h.jsonl"
    cache.write_text("", encoding="utf-8")
    kw = ctx.llm_kwargs({"llm": {"mode": "on", "min_confidence": 0.6, "cache_path": str(cache)}})
    assert kw["llm_fallback"] == "on" and kw["llm_min_confidence"] == 0.6 and kw["hypothesizer"].inner is None
    assert ctx.llm_kwargs({"llm": {"mode": "on", "cache_path": str(cache)}})["hypothesizer"] is kw["hypothesizer"]   # dựng một lần
