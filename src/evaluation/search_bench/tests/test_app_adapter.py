"""Cổng APP (app_adapter.py): UnitIndex từ snapshot + text T3+R, tham số arm, bọc SearchProducts — không cần Weaviate
(engine giả). Nạp ProductBench và parity với B0 là test integration (`pytest -m integration`)."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from evaluation.search_bench import app_adapter as A, catalog, runner as R
from evaluation.search_bench.arms import load_arm
from evaluation.search_bench.textbuild import load_texts

APP_ARMS = ("APP.dense", "APP.dense_nocut", "APP.hybrid", "APP.hybrid_nocut", "APP.hybrid_norm", "APP.hybrid_norm_nocut")


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
                "diagnostics": {"normalizedQuery": q.upper(), "lexicalCount": 1, "lexicalCandidates": 5}}


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
    assert eng.calls[1] == (env.gold[0].text, 10)                            # calls[0] là lượt s.search("resort") ở trên


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
