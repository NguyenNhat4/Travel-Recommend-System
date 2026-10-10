"""SearchProducts — LLM fallback của query plan (đề xuất đã chốt 2026-10-06; contract 1.17.0 `queryPlan.llm`, `stageMs.llm`).

Model giả (không mạng). Fixture tests/conftest.py: A1 VinWonders Nha Trang và A2 Bãi biển Trần Phú là attraction; câu Q có plan
rule confidence 0.75 (long_multi_constraint), không taxonomy, nên `llm_min_confidence=1.0` mới kích hoạt."""
import json
import threading
import time
from pathlib import Path

import pytest

from src.backend.app.application.search import SearchProducts
from src.backend.app.application.search.prewarm import read_query_file
from src.backend.app.application.search.query_plan_llm import (
    CachedQueryHypothesizer,
    HypothesisCache,
    cache_key,
    llm_log_fields,
    prewarm_hypotheses,
)
from src.backend.app.domain.search import HybridConfig
from src.backend.app.domain.search.hypothesis import QueryHypothesis
from src.backend.tests.conftest import FakeEmbedder

PREWARM = Path(__file__).resolve().parents[3] / "data" / "search_prewarm_queries.txt"
Q = "đi chơi Nha Trang cuối tuần cho cả nhà 4 người giá rẻ dưới 5 triệu"
QN = "đi chơi Nha Trang cuối tuần cho gia đình 4 người giá rẻ dưới 5 triệu"   # q' (kiểu đi về nhãn catalog)
MULTI = "khách sạn, vé máy bay và vé tham quan ở Nha Trang"     # confidence 0.5
ATTRACTION = QueryHypothesis(intent="attraction_search", confidence=0.9, taxonomy="attraction")


class FakeHypothesizer:
    version = "fake|v1"

    def __init__(self, result=ATTRACTION, *, delay: float = 0.0, exc: Exception | None = None):
        self.result, self.delay, self.exc = result, delay, exc
        self.calls: list[tuple[str, dict]] = []
        self.done = threading.Event()

    def hypothesize(self, query, context):
        self.calls.append((query, context))
        try:
            if self.delay:
                time.sleep(self.delay)
            if self.exc is not None:
                raise self.exc
            return self.result
        finally:
            self.done.set()


class Boom:
    def hypothesize(self, query, context):   # pragma: no cover — chế độ off không bao giờ được gọi
        raise AssertionError("LLM bị gọi khi fallback tắt")


def _engine(services, **kw):
    kw.setdefault("cutoff", -1.0)
    return SearchProducts(services["index"], services["vectors"], FakeEmbedder(), **kw)


def _ids(r):
    return [x["productId"] for x in r["results"]]


def _strip(r):
    return {**r, "diagnostics": {k: v for k, v in r["diagnostics"].items() if k != "stageMs"}}


def _llm(r):
    return r["diagnostics"]["queryPlan"]["llm"]


def _wait_cached(hyp: CachedQueryHypothesizer, timeout: float = 5.0):
    """Chờ lượt gọi nền xong và đã ghi cache."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not hyp._inflight and len(hyp.cache):
            return
        time.sleep(0.01)
    raise AssertionError("lượt gọi nền chưa xong")


# ------------------------------------------------------------------ off ≡ 1.16.0
@pytest.mark.parametrize("hybrid", [False, True], ids=["ann", "hybrid"])
def test_off_and_untriggered_are_byte_identical_to_today(services, hybrid):
    kw = dict(cutoff=0.0, negation_filter=True, taxonomy_filter=True, dest_filter=True)
    if hybrid:
        kw.update(lexical=services["vectors"], hybrid=HybridConfig(lexical_cutoff=0.0))
    base = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), **kw)
    off = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), llm_fallback="off", hypothesizer=Boom(),
                         **kw)
    never = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), llm_fallback="on",
                           llm_min_confidence=0.0, hypothesizer=Boom(), **kw)   # bật nhưng không câu nào đủ thấp
    assert off._llm is None
    queries = [*read_query_file(PREWARM), Q, MULTI, "khách sạn Nha Trang không có hồ bơi"]
    assert len(queries) >= 130
    for q in queries:
        a = base(q, limit=50)
        for other in (off, never):
            b = other(q, limit=50)
            assert _strip(a) == _strip(b), q
            assert json.dumps(_strip(a), ensure_ascii=False) == json.dumps(_strip(b), ensure_ascii=False), q
            assert "llm" not in b["diagnostics"].get("queryPlan", {}) and "llm" not in b["diagnostics"]["stageMs"], q


def test_invalid_mode_is_rejected(services):
    with pytest.raises(ValueError):
        _engine(services, llm_fallback="maybe")


# ------------------------------------------------------------------ on
def test_on_fills_empty_taxonomy_applies_under_flag_and_caches(services):
    fake = FakeHypothesizer()
    e = _engine(services, llm_fallback="on", llm_min_confidence=1.0, taxonomy_filter=True, hypothesizer=fake)
    r = e(Q, limit=50)
    assert set(_ids(r)) <= {"A1", "A2"} and _ids(r)
    assert r["appliedFilters"]["hard"] == {"taxonomy": "attraction", "taxonomySource": "query"}
    qp = r["diagnostics"]["queryPlan"]
    assert qp["taxonomy"]["value"] == "attraction" and qp["taxonomy"]["source"] == "query" and "taxonomy" in qp["applied"]
    assert qp["confidence"] == 0.75 and qp["fallbackReasons"] == ["long_multi_constraint"]   # router giữ của rule
    llm = qp["llm"]
    assert llm["mode"] == "on" and llm["used"] is True and llm["cached"] is False and llm["status"] == "ok"
    assert llm["accepted"] == ["taxonomy"] and llm["rejected"] == [] and "error" not in llm
    assert "llm" in r["diagnostics"]["stageMs"]
    query, ctx = fake.calls[0]
    assert query == QN and ctx["rawQuery"] == Q and ctx["rule"]["fallbackReasons"] == ["long_multi_constraint"]
    assert "attraction" in ctx["vocab"]["taxonomies"] and ctx["vocab"]["destinations"] == ["Nha Trang", "Phú Quốc"]
    again = e(Q, limit=50)
    assert _llm(again)["cached"] is True and _llm(again)["used"] is True and len(fake.calls) == 1
    assert _ids(again) == _ids(r)


def test_on_family_flag_off_declares_but_does_not_filter(services):
    off = _engine(services)(Q, limit=50)
    r = _engine(services, llm_fallback="on", llm_min_confidence=1.0, hypothesizer=FakeHypothesizer())(Q, limit=50)
    assert _ids(r) == _ids(off) and "appliedFilters" not in r
    assert r["diagnostics"]["queryPlan"]["taxonomy"]["value"] == "attraction" and _llm(r)["accepted"] == ["taxonomy"]


def test_default_threshold_only_fires_below_075(services):
    fake = FakeHypothesizer(QueryHypothesis())
    e = _engine(services, llm_fallback="on", hypothesizer=fake)
    assert "llm" not in e(Q, limit=5)["diagnostics"]["queryPlan"] and fake.calls == []      # 0.75 không < 0.75
    r = e(MULTI, limit=5)
    assert _llm(r)["status"] == "ok" and _llm(r)["used"] is False and len(fake.calls) == 1


def test_params_win_and_invalid_values_never_become_filters(services):
    hyp = QueryHypothesis(taxonomy="attraction", destination="Đà Lạt", star_min=9, must_not_amenities=("pool",),
                          origin="Hà Nội")
    e = _engine(services, llm_fallback="on", llm_min_confidence=1.0, taxonomy_filter=True, negation_filter=True,
                numeric_filter=True, route_filter=True, dest_filter=True, hypothesizer=FakeHypothesizer(hyp))
    r = e(Q, taxonomy="hotel", limit=50)
    assert {x["taxonomy"] for x in r["results"]} == {"hotel"}
    llm = _llm(r)
    assert llm["used"] is False and llm["accepted"] == []
    assert {(x["field"], x["reason"]) for x in llm["rejected"]} == {
        ("destination", "not_in_catalog"), ("mustNotAmenities", "no_cue"), ("star", "out_of_range"),
        ("taxonomy", "param_set"), ("origin", "not_in_query")}
    base = _engine(services, taxonomy_filter=True, negation_filter=True, numeric_filter=True, route_filter=True,
                   dest_filter=True)(Q, taxonomy="hotel", limit=50)
    assert _ids(r) == _ids(base) and r.get("appliedFilters") == base.get("appliedFilters")


def test_timeout_keeps_rule_plan_and_late_result_fills_cache(services):
    fake = FakeHypothesizer(delay=0.3)
    hyp = CachedQueryHypothesizer(fake)
    e = _engine(services, llm_fallback="on", llm_min_confidence=1.0, llm_timeout_ms=30, taxonomy_filter=True,
                hypothesizer=hyp)
    base = _engine(services, taxonomy_filter=True)(Q, limit=50)
    r = e(Q, limit=50)
    assert _llm(r)["status"] == "timeout" and _llm(r)["used"] is False and _ids(r) == _ids(base)
    assert fake.done.wait(5)
    _wait_cached(hyp)
    later = e(Q, limit=50)
    assert _llm(later)["status"] == "ok" and _llm(later)["cached"] is True and _llm(later)["used"] is True
    assert len(fake.calls) == 1


def test_provider_error_keeps_rule_plan(services):
    r = _engine(services, llm_fallback="on", llm_min_confidence=1.0, taxonomy_filter=True,
                hypothesizer=FakeHypothesizer(exc=RuntimeError("boom")))(Q, limit=50)
    base = _engine(services, taxonomy_filter=True)(Q, limit=50)
    assert _llm(r)["status"] == "failed" and _llm(r)["error"] == "RuntimeError" and _ids(r) == _ids(base)


def test_missing_adapter_is_declared_unavailable(services):
    r = _engine(services, llm_fallback="on", llm_min_confidence=1.0)(Q, limit=5)
    assert _llm(r) == {"mode": "on", "used": False, "cached": False, "status": "unavailable",
                       "latencyMs": _llm(r)["latencyMs"], "accepted": [], "rejected": []}


def test_busy_when_max_pending_reached(services):
    slow = FakeHypothesizer(delay=0.3)
    hyp = CachedQueryHypothesizer(slow, max_pending=1)
    e = _engine(services, llm_fallback="on", llm_min_confidence=1.0, llm_timeout_ms=10, hypothesizer=hyp)
    assert _llm(e(Q, limit=5))["status"] == "timeout"
    assert _llm(e(MULTI, limit=5))["status"] == "busy"
    hyp.close(wait=True)


def test_agent_call_without_plan_derivation_skips_llm(services):
    fake = FakeHypothesizer()
    r = _engine(services, llm_fallback="on", llm_min_confidence=1.0, hypothesizer=fake)(Q, limit=5, derive_plan=False)
    assert "llm" not in r["diagnostics"].get("queryPlan", {}) and fake.calls == []


# ------------------------------------------------------------------ shadow
def test_shadow_never_changes_results_and_compares_on_cache_hit(services):
    fake = FakeHypothesizer()
    hyp = CachedQueryHypothesizer(fake)
    e = _engine(services, llm_fallback="shadow", llm_min_confidence=1.0, taxonomy_filter=True, hypothesizer=hyp)
    base = _engine(services, taxonomy_filter=True)(Q, limit=50)
    first = e(Q, limit=50)
    assert _llm(first)["status"] == "pending" and _llm(first)["used"] is False and _ids(first) == _ids(base)
    assert fake.done.wait(5)
    _wait_cached(hyp)
    second = e(Q, limit=50)
    llm = _llm(second)
    assert llm == {"mode": "shadow", "used": False, "cached": True, "status": "ok", "latencyMs": llm["latencyMs"],
                   "accepted": ["taxonomy"], "rejected": []}
    assert _ids(second) == _ids(base) and second.get("appliedFilters") == base.get("appliedFilters")
    assert second["diagnostics"]["queryPlan"].get("taxonomy") == base["diagnostics"]["queryPlan"].get("taxonomy")
    assert llm_log_fields(second) == {"llm": {"mode": "shadow", "used": False, "status": "ok", "accepted": ["taxonomy"],
                                              "rejected": []}}
    assert llm_log_fields(base) is None
    assert len(fake.calls) == 1


# ------------------------------------------------------------------ cache đĩa / bench
def test_disk_cache_persists_with_raw_alias_and_replays_cache_only(services, tmp_path):
    path = tmp_path / "hyp.jsonl"
    fake = FakeHypothesizer()
    writer = CachedQueryHypothesizer(fake, cache=HypothesisCache(path=path, tag=fake.version))
    _engine(services, llm_fallback="on", llm_min_confidence=1.0, hypothesizer=writer)("  " + Q.replace(" ", "  "), limit=5)
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1 and rows[0]["tag"] == "fake|v1" and rows[0]["hypothesis"]["taxonomy"] == "attraction"
    assert rows[0]["key"] == cache_key(QN) and rows[0]["aliases"] == [cache_key(Q)]
    assert HypothesisCache(path=path, tag="other|v2").stats()["size"] == 0                   # tag khác → không nạp

    replay = CachedQueryHypothesizer(None, cache=HypothesisCache(path=path), cache_only=True)
    e = _engine(services, llm_fallback="on", llm_min_confidence=1.0, taxonomy_filter=True, hypothesizer=replay)
    r = e(Q.upper(), limit=50)
    assert _llm(r)["cached"] is True and _llm(r)["used"] is True and set(_ids(r)) <= {"A1", "A2"}
    miss = e(MULTI, limit=5)
    assert _llm(miss)["status"] == "cache_miss" and _llm(miss)["used"] is False
    # khoá phụ (câu gốc) vẫn hit khi q' khác: cache chỉ có khoá phụ
    only_raw = HypothesisCache()
    only_raw.put(("không-trùng-q'", cache_key(Q)), ATTRACTION, persist=False)
    r2 = _engine(services, llm_fallback="on", llm_min_confidence=1.0,
                 hypothesizer=CachedQueryHypothesizer(None, cache=only_raw, cache_only=True))(Q, limit=5)
    assert _llm(r2)["cached"] is True and _llm(r2)["accepted"] == ["taxonomy"]


def test_prewarm_calls_only_low_confidence_queries_once(services, tmp_path):
    fake = FakeHypothesizer(QueryHypothesis())
    hyp = CachedQueryHypothesizer(fake, cache=HypothesisCache(path=tmp_path / "c.jsonl", tag=fake.version))
    e = _engine(services)
    queries = [Q, MULTI, "Vinpearl Resort Nha Trang", Q, "   "]
    rep = prewarm_hypotheses(e, hyp, queries)
    assert (rep.queries, rep.eligible, rep.called, rep.skipped, rep.failed) == (5, 2, 2, 0, 0)
    assert prewarm_hypotheses(e, hyp, queries).called == 0
    assert prewarm_hypotheses(e, hyp, queries, min_confidence=0.75).eligible == 1
    assert prewarm_hypotheses(e, hyp, queries, include_all=True).called == 1          # câu confidence 1.0
    req = e.llm_hypothesis_request(Q)
    assert req.keys == (cache_key(QN), cache_key(Q)) and req.confidence == 0.75 and req.query == QN
    replay = CachedQueryHypothesizer(None, cache=HypothesisCache(path=tmp_path / "c.jsonl", tag=fake.version),
                                     cache_only=True)
    r = _engine(services, llm_fallback="on", llm_min_confidence=1.0, hypothesizer=replay)(Q, limit=5)
    assert _llm(r)["cached"] is True and _llm(r)["status"] == "ok"
    failing = CachedQueryHypothesizer(FakeHypothesizer(exc=RuntimeError("x")))
    rep = prewarm_hypotheses(e, failing, [Q])
    assert rep.failed == 1 and rep.errors and not failing.cache.has(cache_key(QN), cache_key(Q))
