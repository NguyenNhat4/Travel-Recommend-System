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
