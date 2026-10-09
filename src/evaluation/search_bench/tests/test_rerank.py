"""Reranker offline (rerank.py, Phase D): kiểm tham số arm, cache sqlite, thứ tự sau rerank — scorer giả, không nạp model."""
from __future__ import annotations

import numpy as np
import pytest

from evaluation.search_bench import rerank as RR

GOOD = {"model": "BAAI/bge-reranker-v2-m3", "top_n": 30, "parent_engine": "app", "query": "raw", "batch_size": 16, "max_length": 512}


@pytest.mark.parametrize("key", RR.RERANK_KEYS)
def test_rerank_params_requires_every_key(key):
    with pytest.raises(RR.RerankError, match=f"rerank.{key}"):
        RR.rerank_params({k: v for k, v in GOOD.items() if k != key}, k=10)


@pytest.mark.parametrize("patch, match", [
    ({"parent_engine": "bench"}, "parent_engine"),
    ({"query": "lower"}, "rerank.query"),
    ({"top_n": 5}, "top_n"),                     # < k
    ({"top_n": 51}, "top_n"),                    # > max_limit của /search
    ({"batch_size": 0}, "batch_size"),
])
def test_rerank_params_rejects(patch, match):
    with pytest.raises(RR.RerankError, match=match):
        RR.rerank_params({**GOOD, **patch}, k=10)


def test_rerank_params_ok():
    p = RR.rerank_params({**GOOD, "top_n": "30"}, k=10)
    assert p["top_n"] == 30 and p["batch_size"] == 16 and p["max_length"] == 512


def test_pair_key_depends_on_every_part():
    base = RR.pair_key("m", "q", "p1", "text", 512)
    assert base == RR.pair_key("m", "q", "p1", "text", 512)
    assert len({base, RR.pair_key("m2", "q", "p1", "text", 512), RR.pair_key("m", "q2", "p1", "text", 512),
                RR.pair_key("m", "q", "p2", "text", 512), RR.pair_key("m", "q", "p1", "text 2", 512),
                RR.pair_key("m", "q", "p1", "text", 256)}) == 6


def test_cache_roundtrip(tmp_path):
    c = RR.RerankCache(tmp_path / "rr.sqlite")
    c.put_many([("k1", "m", "q", "p1", 1.5, 10.0), ("k2", "m", "q", "p2", -0.5, 12.0)])
    assert c.get_many(["k1", "k2", "k3"]) == {"k1": (1.5, 10.0), "k2": (-0.5, 12.0)}
    assert c.count() == 2 and c.count("m") == 2 and c.count("x") == 0
    c.close()
    c2 = RR.RerankCache(tmp_path / "rr.sqlite")                        # bền qua lần mở sau
    assert c2.get_many(["k1"]) == {"k1": (1.5, 10.0)}
    c2.close()


def _scorer(scores: dict[str, float], calls: list):
    def fn(pairs):
        calls.append([t for _, t in pairs])
        return np.array([scores[t] for _, t in pairs], dtype="float32"), sum(1 for _, t in pairs if t.startswith("long"))
    return fn


def test_reranker_orders_by_score_ties_keep_engine_order_and_batches(tmp_path):
    calls: list = []
    sc = {"a": 0.1, "b": 0.9, "c": 0.5, "d": 0.5, "long e": 0.2}
    r = RR.Reranker("m", batch_size=2, max_length=512, cache=RR.RerankCache(tmp_path / "rr.sqlite"), score_fn=_scorer(sc, calls))
    res = r.rerank("q", ["A", "B", "C", "D", "E"], ["a", "b", "c", "d", "long e"])
    assert res.order == [1, 2, 3, 4, 0]                                  # b, rồi c / d hoà → giữ thứ tự engine, rồi e, a
    assert res.scores == pytest.approx([0.9, 0.5, 0.5, 0.2, 0.1])
    assert [len(c) for c in calls] == [2, 2, 1] and res.n_truncated == 1
    assert (res.n_scored, res.n_cached) == (5, 0) and res.model_ms >= 0
    calls.clear()
    res2 = r.rerank("q", ["A", "B", "C", "D", "E"], ["a", "b", "c", "d", "long e"])
    assert calls == [] and (res2.n_scored, res2.n_cached) == (0, 5) and res2.order == res.order
    assert res2.model_ms == pytest.approx(res.model_ms)                # thời gian model đọc lại từ cache
    res3 = r.rerank("q other", ["A", "B"], ["a", "b"])                   # câu khác → chấm lại
    assert res3.n_scored == 2 and (r.n_scored, r.n_cached) == (7, 5)
    r.close()


def test_reranker_without_cache_and_length_mismatch():
    calls: list = []
    r = RR.Reranker("m", batch_size=8, max_length=512, cache=None, score_fn=_scorer({"x": 1.0, "y": 2.0}, calls))
    assert r.rerank("q", ["X", "Y"], ["x", "y"]).order == [1, 0]
    assert r.rerank("q", ["X", "Y"], ["x", "y"]).n_scored == 2           # không cache → chấm lại
    with pytest.raises(RR.RerankError):
        r.rerank("q", ["X"], ["x", "y"])


def test_open_reranker_shares_scorer_per_model(tmp_path, monkeypatch):
    monkeypatch.setattr(RR, "_SCORERS", {})
    a = RR.open_reranker(GOOD, cache_path=tmp_path / "a.sqlite")
    b = RR.open_reranker({**GOOD, "batch_size": 4}, cache_path=tmp_path / "b.sqlite")
    c = RR.open_reranker({**GOOD, "max_length": 256}, cache_path=tmp_path / "c.sqlite")
    assert a.score_fn is b.score_fn and a.score_fn is not c.score_fn and b.batch_size == 4
    assert isinstance(a.score_fn, RR.CrossEncoderScorer) and a.score_fn._model is None   # nạp lười
    for x in (a, b, c):
        x.close()


def test_reranker_loads_model_outside_timing_and_only_when_needed(tmp_path):
    """Nạp model (`load`) trước khi bấm giờ chấm, và không nạp khi mọi cặp đã có trong cache."""
    import time

    class Slow:
        def __init__(self):
            self.loads = 0

        def load(self):
            self.loads += 1
            time.sleep(0.2)

        def __call__(self, pairs):
            return np.ones(len(pairs), dtype="float32"), 0

    fn = Slow()
    r = RR.Reranker("m", batch_size=4, max_length=512, cache=RR.RerankCache(tmp_path / "rr.sqlite"), score_fn=fn)
    res = r.rerank("q", ["A", "B"], ["a", "b"])
    assert fn.loads == 1 and res.ms < 150 and res.model_ms < 150
    r.rerank("q", ["A", "B"], ["a", "b"])
    assert fn.loads == 1
    r.close()
