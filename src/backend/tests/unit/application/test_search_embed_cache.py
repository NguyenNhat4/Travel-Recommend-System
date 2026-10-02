"""Cache vector truy vấn (contract 1.12.0 `diagnostics.embedCache`, NFR-PERF-03): khoá = câu sau chuẩn hoá + gộp khoảng
trắng, LRU, single-flight thread-safe; kết quả /search không đổi khi bật/tắt cache."""
import logging
import threading
import time

import numpy as np
import pytest
from jsonschema import Draft202012Validator

from src.backend.app.application.itinerary.tool_contracts import contracts
from src.backend.app.application.search import SearchProducts
from src.backend.app.application.search.query_cache import CachingQueryEmbedder, QueryEmbeddingCache
from src.backend.app.application.search.use_cases import canonical_query
from src.backend.tests.conftest import FakeEmbedder


class CountingEmbedder(FakeEmbedder):
    def __init__(self, name="fake"):
        self.name = name
        self.queries = []
        self.batches = []

    def embed_query(self, q):
        self.queries.append(q)
        return super().embed_query(q)

    def embed_queries(self, texts):
        self.batches.append(list(texts))
        return np.stack([FakeEmbedder.embed_query(self, t) for t in texts])


def _cached(inner=None, size=100, **kw):
    inner = inner or CountingEmbedder()
    return inner, CachingQueryEmbedder(inner, QueryEmbeddingCache(size), **kw)


def test_alias_and_full_form_share_one_cohere_call(services):
    inner, emb = _cached()
    s = SearchProducts(services["index"], services["vectors"], emb, cutoff=-1.0)
    a = s("KS ở NT", limit=3)
    b = s("khách sạn ở Nha Trang", limit=3)
    c = s("khách  sạn   ở Nha Trang ", limit=3)
    assert inner.queries == ["khách sạn ở Nha Trang"]
    assert a["diagnostics"]["embedCache"] == "miss"
    assert b["diagnostics"]["embedCache"] == c["diagnostics"]["embedCache"] == "hit"
    assert [x["productId"] for x in a["results"]] == [x["productId"] for x in b["results"]]
    assert s.query_text("KS  ở NT") == "khách sạn ở Nha Trang" and canonical_query("  a \t b  ") == "a b"


def test_embedder_without_cache_adds_no_field(services):
    r = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0)("resort", limit=3)
    assert "embedCache" not in r["diagnostics"]


def test_results_identical_with_and_without_cache(services):
    plain = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0)
    _, emb = _cached()
    cached = SearchProducts(services["index"], services["vectors"], emb, cutoff=-1.0)
    for q in ("resort Nha Trang", "KS ở NT", "vé máy bay", "resort Nha Trang", "golf"):
        assert [x["productId"] for x in plain(q, limit=10)["results"]] == [x["productId"] for x in cached(q, limit=10)["results"]]


def test_response_matches_contract_and_rejects_unknown_value(services):
    _, emb = _cached()
    s = SearchProducts(services["index"], services["vectors"], emb, cutoff=0.0)   # cutoff âm cho score < 0, contract từ chối
    validator = Draft202012Validator(contracts()["search_products"]["response"])
    for q in ("resort", "resort"):
        r = s(q, limit=3)
        r["diagnostics"]["latencyMs"] = 0
        assert [e.message for e in validator.iter_errors(r)] == []
    r["diagnostics"]["embedCache"] = "stale"
    assert list(validator.iter_errors(r)), "embedCache chỉ nhận hit | miss"


def test_key_includes_model_name_so_two_models_never_share_vectors():
    cache = QueryEmbeddingCache(10)
    a, b = CountingEmbedder("m-a"), CountingEmbedder("m-b")
    CachingQueryEmbedder(a, cache).embed_query("x")
    CachingQueryEmbedder(b, cache).embed_query("x")
    assert a.queries == ["x"] and b.queries == ["x"] and len(cache) == 2


def test_lru_evicts_oldest_and_vectors_are_read_only():
    inner, emb = _cached(size=2)
    for q in ("a", "b", "c"):
        emb.embed_query(q)
    assert emb.cache.evictions == 1 and emb.key("a") not in emb.cache and emb.key("c") in emb.cache
    emb.embed_query("b")                       # hit → "b" thành mới nhất
    emb.embed_query("d")                       # đẩy "c"
    assert emb.key("b") in emb.cache and emb.key("c") not in emb.cache
    vec, status = emb.embed_query_status("b")
    assert status == "hit" and vec.dtype == np.float32 and not vec.flags.writeable
    with pytest.raises(ValueError):
        vec[0] = 1.0


def test_single_flight_coalesces_concurrent_misses():
    class Slow(CountingEmbedder):
        def embed_query(self, q):
            time.sleep(0.05)
            return super().embed_query(q)
    inner, emb = _cached(Slow())
    n = 8
    barrier = threading.Barrier(n)
    statuses = []

    def worker():
        barrier.wait()
        statuses.append(emb.embed_query_status("cùng một câu")[1])
    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert inner.queries == ["cùng một câu"]
    assert sorted(statuses) == ["hit"] * (n - 1) + ["miss"]
    st = emb.cache.stats()
    assert (st["misses"], st["coalesced"], st["size"]) == (1, n - 1, 1)


def test_leader_failure_wakes_followers_who_then_compute_themselves():
    go = threading.Event()

    class Flaky(CountingEmbedder):
        def embed_query(self, q):
            first = not self.queries
            self.queries.append(q)
            if first:
                go.wait(2)
                raise RuntimeError("Cohere 503")
            return FakeEmbedder.embed_query(self, q)
    inner, emb = _cached(Flaky())
    results, errors = [], []

    def leader():
        try:
            emb.embed_query_status("q")
        except RuntimeError as e:
            errors.append(str(e))

    def follower():
        results.append(emb.embed_query_status("q"))
    a = threading.Thread(target=leader)
    a.start()
    time.sleep(0.05)                           # follower vào sau khi leader đã giữ inflight
    b = threading.Thread(target=follower)
    b.start()
    time.sleep(0.05)
    go.set()
    a.join(2)
    b.join(2)
    assert errors == ["Cohere 503"] and results and results[0][1] == "miss"
    assert inner.queries == ["q", "q"] and emb.key("q") in emb.cache and not emb.cache._inflight


def test_embed_queries_fills_only_missing_keys_in_one_batch():
    inner, emb = _cached()
    emb.embed_query("a")
    assert emb.embed_queries(["a", "b", "c", "b"]) == 2
    assert inner.batches == [["b", "c"]] and inner.queries == ["a"]
    assert emb.embed_queries(["a", "b", "c"]) == 0
    assert emb.embed_query_status("c")[1] == "hit"


def test_embed_queries_falls_back_to_single_calls_without_batch_api():
    inner = FakeEmbedder()
    emb = CachingQueryEmbedder(inner, QueryEmbeddingCache(10))
    assert emb.embed_queries(["x", "y"]) == 2 and emb.embed_query_status("y")[1] == "hit"


def test_stats_are_logged_every_n_lookups_without_query_text(caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    _, emb = _cached(log_every=2)
    emb.embed_query("bí mật của khách")
    assert not [r for r in caplog.records if "search.embed_cache" in r.getMessage()]
    emb.embed_query("bí mật của khách")
    lines = [r.getMessage() for r in caplog.records if "search.embed_cache" in r.getMessage()]
    assert lines and "hits=1" in lines[0] and "misses=1" in lines[0] and "bí mật" not in lines[0]
    assert emb.cache.stats() == {"hits": 1, "misses": 1, "coalesced": 0, "evictions": 0, "size": 1, "ratio": 0.5}


def test_embed_docs_passes_through_and_close_closes_inner():
    class Inner(CountingEmbedder):
        closed = False

        def close(self):
            self.closed = True
    inner, emb = _cached(Inner())
    assert emb.embed_docs(["t"]).shape == (1, 64) and emb.name == "fake"
    emb.close()
    assert inner.closed
