"""Contract 1.17.0: `diagnostics.queryPlan.llm` + `stageMs.llm` (LLM fallback của query plan) — response của use case và của
route `main.app` với model giả phải khớp `SearchResponse`; contract khai đủ hằng số của domain / application."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from src.backend.app.application.itinerary.tool_contracts import contracts
from src.backend.app.application.search import SearchProducts
from src.backend.app.application.search import query_plan_llm
from src.backend.app.application.search.query_plan_llm import CachedQueryHypothesizer, HypothesisCache
from src.backend.app.domain.search import hypothesis
from src.backend.app.domain.search.hypothesis import QueryHypothesis
from src.backend.app.main import app
from src.backend.tests.conftest import FakeEmbedder
from src.backend.tests.contract.test_booking_contract import DOC, assert_contract

Q = "đi chơi Nha Trang cuối tuần cho cả nhà 4 người giá rẻ dưới 5 triệu"
MULTI = "khách sạn, vé máy bay và vé tham quan ở Nha Trang"
RICH = QueryHypothesis(confidence=0.9, taxonomy="attraction", destination="Đà Lạt", star_min=9, party_total=4,
                       must_not_amenities=("pool", "nope"), origin="Hà Nội", soft_preferences=("view biển",))
ALL_ON = dict(negation_filter=True, taxonomy_filter=True, route_filter=True, numeric_filter=True, dest_filter=True,
              party_filter=True)


class Fake:
    version = "fake|contract"

    def __init__(self, result=RICH, exc=None):
        self.result, self.exc = result, exc

    def hypothesize(self, query, context):
        if self.exc:
            raise self.exc
        return self.result


def _engines(services):
    kw = dict(cutoff=0.0, llm_min_confidence=1.0, **ALL_ON)
    idx, vec = services["index"], services["vectors"]
    return [
        SearchProducts(idx, vec, FakeEmbedder(), llm_fallback="on", hypothesizer=Fake(), **kw),
        SearchProducts(idx, vec, FakeEmbedder(), llm_fallback="on", hypothesizer=Fake(exc=RuntimeError("x")), **kw),
        SearchProducts(idx, vec, FakeEmbedder(), llm_fallback="on", **kw),                         # unavailable
        SearchProducts(idx, vec, FakeEmbedder(), llm_fallback="on",
                       hypothesizer=CachedQueryHypothesizer(None, cache=HypothesisCache(), cache_only=True), **kw),
        SearchProducts(idx, vec, FakeEmbedder(), llm_fallback="shadow",
                       hypothesizer=CachedQueryHypothesizer(Fake(None)), **kw),
    ]


def test_engine_responses_with_llm_block_match_contract(services):
    schema = Draft202012Validator(contracts()["search_products"]["response"])
    statuses: set[str] = set()
    reasons: set[str] = set()
    for engine in _engines(services):
        for q, kw in ((Q, {}), (MULTI, {}), (Q, {"taxonomy": "hotel"}), ("vé máy bay giá tốt cuối tuần", {})):
            r = engine(q, limit=5, **kw)
            r["diagnostics"]["latencyMs"] = 0
            errors = [e.message for e in schema.iter_errors(r)]
            assert errors == [], (q, kw, errors)
            json.dumps(r)
            llm = r["diagnostics"].get("queryPlan", {}).get("llm")
            if llm:
                statuses.add(llm["status"])
                reasons |= {x["reason"] for x in llm["rejected"]}
                assert "llm" in r["diagnostics"]["stageMs"]
    assert {"ok", "failed", "unavailable", "cache_miss", "pending"} <= statuses, statuses
    assert {"not_in_catalog", "out_of_range", "invalid_value", "param_set"} <= reasons, reasons


def test_http_route_with_llm_on_matches_contract(services):
    saved = {name: getattr(app.state, name, None) for name in ("search", "search_log")}
    app.state.search = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=0.0,
                                      llm_fallback="on", llm_min_confidence=1.0, hypothesizer=Fake(), **ALL_ON)
    app.state.search_log = None
    try:
        client = TestClient(app)
        body = assert_contract(client.get("/api/v1/search", params={"q": Q}), "/search", "get")
        assert body["diagnostics"]["queryPlan"]["llm"]["used"] is True
        assert body["appliedFilters"]["hard"]["taxonomy"] == "attraction"
        post = assert_contract(client.post("/api/v1/search", json={"query": Q, "taxonomy": "hotel"}), "/search", "post")
        assert {"field": "taxonomy", "reason": "param_set"} in post["diagnostics"]["queryPlan"]["llm"]["rejected"]
    finally:
        for name, value in saved.items():
            setattr(app.state, name, value)


def _llm_schema() -> dict:
    return DOC["components"]["schemas"]["EngineDiagnostics"]["properties"]["queryPlan"]["properties"]["llm"]


def test_contract_declares_every_llm_constant():
    s = _llm_schema()["properties"]
    assert set(s["mode"]["enum"]) == set(query_plan_llm.MODES) - {query_plan_llm.MODE_OFF}
    assert set(s["status"]["enum"]) == set(query_plan_llm.STATUSES)
    fields = {v for k, v in vars(hypothesis).items() if k.startswith("F_") and isinstance(v, str)}
    reasons = {v for k, v in vars(hypothesis).items() if k.startswith("R_") and isinstance(v, str)}
    rejected = s["rejected"]["items"]["properties"]
    assert set(rejected["field"]["enum"]) == fields
    assert set(s["accepted"]["items"]["enum"]) == fields - {hypothesis.F_HYPOTHESIS}
    assert set(rejected["reason"]["enum"]) == reasons
    stage = DOC["components"]["schemas"]["EngineDiagnostics"]["properties"]["stageMs"]["properties"]
    assert "llm" in stage
    assert set(hypothesis.CONTRACT_TAXONOMIES) == set(DOC["components"]["schemas"]["Taxonomy"]["enum"])
    assert DOC["info"]["version"] == "1.23.0"


@pytest.mark.parametrize("mode", ["off", "shadow", "on"])
def test_modes_are_the_settings_values(mode, services):
    SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=0.0, llm_fallback=mode)
