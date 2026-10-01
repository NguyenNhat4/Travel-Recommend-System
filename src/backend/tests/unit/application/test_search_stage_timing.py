"""`diagnostics.stageMs` của /search (contract 1.11.0): thời gian từng bước, đo trong engine, ms nguyên."""
import time

from jsonschema import Draft202012Validator

from src.backend.app.application.itinerary.tool_contracts import contracts
from src.backend.app.application.search import SearchProducts
from src.backend.app.application.search.responses import search_tool_payload
from src.backend.app.application.search.use_cases import StageTimer
from src.backend.app.domain.search import HybridConfig
from src.backend.tests.conftest import FakeEmbedder

ANN_STAGES = {"normalize", "embed", "dense", "fuse", "hydrate"}
NORMALIZATION_KEYS = {"normalizedQuery", "appliedAliases", "corrections", "party"}


class SlowEmbedder(FakeEmbedder):
    """Embed chậm có chủ đích: thời gian phải rơi vào đúng bước `embed`."""

    def embed_query(self, q):
        time.sleep(0.03)
        return super().embed_query(q)


class _BrokenLexical:
    def bm25(self, *args, **kwargs):
        raise RuntimeError("collection has no searchable property")


def _stage_ms(r):
    stage_ms = r["diagnostics"]["stageMs"]
    assert all(isinstance(v, int) and v >= 0 for v in stage_ms.values()), stage_ms
    return stage_ms


def test_dense_only_declares_every_stage_except_lexical(services):
    r = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0)("resort", limit=3)
    assert r["diagnostics"]["searchMode"] == "ANN_CANDIDATE_SCORE"
    assert set(_stage_ms(r)) == ANN_STAGES


def test_hybrid_adds_lexical_stage(services):
    s = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0,
                       lexical=services["vectors"], hybrid=HybridConfig())
    r = s("VinWonders Nha Trang", limit=3)
    assert r["diagnostics"]["searchMode"] == "HYBRID_CANDIDATE_SCORE"
    assert set(_stage_ms(r)) == ANN_STAGES | {"lexical"}


def test_normalize_off_has_no_normalize_stage(services):
    r = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0, normalize=False)("resort")
    assert set(_stage_ms(r)) == ANN_STAGES - {"normalize"}


def test_lexical_failure_still_reports_lexical_stage(services):
    s = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0,
                       lexical=_BrokenLexical(), hybrid=HybridConfig())
    r = s("resort", limit=3)
    assert r["diagnostics"]["lexicalCandidates"] == 0
    assert "lexical" in _stage_ms(r)


def test_time_lands_in_the_stage_that_spent_it(services):
    r = SearchProducts(services["index"], services["vectors"], SlowEmbedder(), cutoff=-1.0)("resort", limit=3)
    stage_ms = _stage_ms(r)
    assert stage_ms["embed"] >= 25
    assert stage_ms["embed"] > sum(v for k, v in stage_ms.items() if k != "embed")


def test_response_with_stage_ms_matches_contract(services):
    s = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=0.0,
                       lexical=services["vectors"], hybrid=HybridConfig(lexical_cutoff=0.0))
    validator = Draft202012Validator(contracts()["search_products"]["response"])
    for q in ("VinWonders Nha Trang", "KS ở PQ Vinpeal cho gd", "zzzz không khớp gì"):
        r = s(q, limit=5)
        r["diagnostics"]["latencyMs"] = 0  # route `_safe_search` gắn trường này, use case thì không
        assert [e.message for e in validator.iter_errors(r)] == [], q


def test_contract_rejects_unknown_stage(services):
    r = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0)("resort", limit=3)
    r["diagnostics"]["latencyMs"] = 0
    r["diagnostics"]["stageMs"]["rerank"] = 1
    errors = list(Draft202012Validator(contracts()["search_products"]["response"]).iter_errors(r))
    assert errors, "stageMs có additionalProperties: false"


def test_agent_payload_does_not_carry_stage_ms(services):
    r = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=-1.0)("resort", limit=3)
    assert "diagnostics" not in search_tool_payload(r)


def test_stage_ms_is_not_a_normalization_key():
    assert "stageMs" not in NORMALIZATION_KEYS


def test_stage_timer_floors_so_the_sum_never_exceeds_the_total(monkeypatch):
    # Sáu bước 0,6 ms: làm tròn từng bước sẽ ra 6 ms > tổng 3,6 ms; làm tròn xuống thì tổng 0 ≤ latencyMs.
    from src.backend.app.application.search import use_cases

    clock = iter([0.0, 0.0006, 0.0012, 0.0018, 0.0024, 0.0030, 0.0036])
    monkeypatch.setattr(use_cases, "perf_counter", lambda: next(clock))
    timer = StageTimer()
    for name in ("normalize", "embed", "dense", "lexical", "fuse", "hydrate"):
        timer.lap(name)
    assert timer.ms == dict.fromkeys(("normalize", "embed", "dense", "lexical", "fuse", "hydrate"), 0)
    assert sum(timer.ms.values()) <= round(0.0036 * 1000)


def test_route_latency_covers_the_sum_of_stages(services):
    from src.backend.app.api.v1.routes.search import _safe_search

    s = SearchProducts(services["index"], services["vectors"], SlowEmbedder(), cutoff=-1.0,
                       lexical=services["vectors"], hybrid=HybridConfig())
    for q in ("resort", "VinWonders Nha Trang", "KS ở PQ"):
        r = _safe_search(s, q, None, None, 5, 0)
        assert sum(_stage_ms(r).values()) <= r["diagnostics"]["latencyMs"], q


def test_stage_timer_accumulates_repeated_laps():
    timer = StageTimer()
    time.sleep(0.005)
    timer.lap("embed")
    time.sleep(0.005)
    timer.lap("embed")
    assert set(timer.ms) == {"embed"} and timer.ms["embed"] >= 8
