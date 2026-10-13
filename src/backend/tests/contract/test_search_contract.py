"""/search ở biên HTTP thật với mọi núm bật (contract 1.16.0 + ba cờ 1.18.0 duration / poi / entity): response phải khớp
`SearchResponse` (queryPlan `additionalProperties: false`), cả ở use case (`contracts()["search_products"]["response"]`) lẫn
qua route của `main.app`. Kèm kiểm contract khai đủ hằng số của domain (lý do confidence, họ filter, cờ combo).

Fixture chỉ có điểm đến Nha Trang / Phú Quốc (conftest ROWS) và Nha Trang (PARTY_ROWS): địa danh Hà Nội bị `place_table`
bỏ lúc nạp, nên câu POI dùng Hòn Tằm (venue, Nha Trang) và Bãi Sao (landmark, Phú Quốc)."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from src.backend.app.application.itinerary.tool_contracts import contracts
from src.backend.app.application.search import SearchProducts
from src.backend.app.domain.catalog import unit_attributes
from src.backend.app.domain.search import HybridConfig, query_plan
from src.backend.app.main import app
from src.backend.tests.conftest import FakeEmbedder
from src.backend.tests.contract.test_booking_contract import DOC, assert_contract
from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore
from src.backend.tests.unit.application.test_search_v116_knobs import PARTY_ROWS

ALL_ON = dict(negation_filter=True, taxonomy_filter=True, route_filter=True, numeric_filter=True, dest_filter=True,
              tone_normalize=True, taxonomy_strong_only=True, party_filter=True,
              duration_filter=True, poi_resolve=True, entity_filter=True)
HYBRID_ON = HybridConfig(lexical_cutoff=0.0, fuzzy_k=5, fuzzy_min_sim=0.5, dense_weight=1.0, lexical_weight=0.8,
                         fuzzy_weight=0.5)
CASES = (
    ("khách sạn Nha Trang không có hồ bơi", {}),
    ("resort 5 sao Phú Quốc dưới 2 triệu", {}),
    ("vé máy bay từ Hà Nội đến Nha Trang", {}),
    ("khách sạn, vé máy bay và vé tham quan ở Nha Trang", {}),
    ("nghỉ dưỡng ở Nha Trang", {}),
    ("khách sạn cho 3 người ở Nha Trang dưới 4 triệu", {}),
    ("2 người lớn 1 trẻ em ở Nha Trang", {}),
    ("combo không gồm vé máy bay", {}),
    ("không lấy combo, vé lẻ Nha Trang", {}),
    ("Vinwondrs Nha Trang", {}),
    ("thuỷ cung hoà bình", {}),
    ("khách sạn Nha Trang", {"adults": 4, "price_max": 4000000}),
    ("khách sạn Nha Trang", {"adults": 30, "taxonomy": "hotel"}),
    ("Nha Trang", {"taxonomy": "flight", "origin": "Hà Nội", "children": 2}),
    ("resort Nha Trang", {"origin": "Hà Nội", "price_max": 4000000, "star_min": 4, "available_only": False}),
    ("Đà Nẵng", {"destination": "Nha Trang"}),
    ("khách sạn Nha Trang", {"check_in": date.today() + timedelta(days=3), "check_out": date.today() + timedelta(days=5)}),
    ("vé tham quan Nha Trang", {"check_in": date.today() + timedelta(days=3), "adults": 2}),
    ("khách sạn Nha Trang", {"check_in": date.today() - timedelta(days=30)}),   # quá khứ → F rỗng, emptyReason = date
    ("zzzz không khớp gì", {}),
    # 1.18.0: duration + entity gate · venue → location (vai trò location, hard.destinationSource = poi) · landmark → F1 ·
    # gate với tab hotel → total 0, emptyReason = entity
    ("vé VinWonders 3 ngày 2 đêm", {}),
    ("khách sạn gần Hòn Tằm", {}),
    ("resort gần Bãi Sao", {}),
    ("VinWonders Nha Trang", {"taxonomy": "hotel"}),
)


@pytest.fixture(scope="module")
def party_catalog(tmp_path_factory):
    d = tmp_path_factory.mktemp("party_contract")
    (d / "products.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in PARTY_ROWS), encoding="utf-8")
    return InMemoryVectorStore(str(d / "products.jsonl"), FakeEmbedder(), str(d / ".emb")).load()


@pytest.fixture
def engines(services, party_catalog):
    out = []
    for index, vectors in ((services["index"], services["vectors"]), party_catalog):
        out.append(SearchProducts(index, vectors, FakeEmbedder(), cutoff=0.0, lexical=vectors, hybrid=HYBRID_ON, **ALL_ON))
        out.append(SearchProducts(index, vectors, FakeEmbedder(), cutoff=0.0, **ALL_ON))   # ANN: không có kênh fuzzy
    return out


def test_engine_responses_with_every_knob_on_match_contract(engines):
    schema = Draft202012Validator(contracts()["search_products"]["response"])
    seen: set[str] = set()
    for engine in engines:
        for q, kw in CASES:
            r = engine(q, limit=5, **kw)
            r["diagnostics"]["latencyMs"] = 0   # route gắn trường này
            errors = [e.message for e in schema.iter_errors(r)]
            assert errors == [], (q, kw, errors)
            json.dumps(r)
            qp = r["diagnostics"].get("queryPlan", {})
            seen |= set(qp) | {f"taxonomy.{k}" for k in qp.get("taxonomy", {})} | {f"mustNot.{k}" for k in qp.get("mustNot", {})}
            seen |= {"matchedChildren" for x in r["results"] if "matchedChildren" in x}
            seen |= {"fuzzyCount"} & set(r["diagnostics"])
            hard = (r.get("appliedFilters") or {}).get("hard") or {}
            seen |= {f"hard.{k}" for k in hard} | {f"applied.{a}" for a in qp.get("applied", [])}
            if "destinationSource" in hard:
                seen.add(f"hard.destinationSource.{hard['destinationSource']}")
            if "emptyReason" in qp:
                seen.add(f"emptyReason.{qp['emptyReason']}")
    # các khoá 1.16.0 / 1.18.0 thực sự được phát ít nhất một lần trong bộ câu trên (không chỉ hợp lệ khi vắng)
    assert {"party", "confidence", "fallbackReasons", "taxonomy.strength", "mustNot.taxonomies", "mustNot.flags",
            "matchedChildren", "fuzzyCount", "date"} <= seen, seen
    assert {"duration", "entity", "location", "hard.entity", "hard.destinationSource.poi", "emptyReason.entity",
            "applied.duration", "applied.entity"} <= seen, seen


@pytest.fixture
def client(services):
    saved = {name: getattr(app.state, name, None) for name in ("search", "search_log")}
    app.state.search = SearchProducts(services["index"], services["vectors"], FakeEmbedder(), cutoff=0.0,
                                      lexical=services["vectors"], hybrid=HYBRID_ON, **ALL_ON)
    app.state.search_log = None
    try:
        yield TestClient(app)
    finally:
        for name, value in saved.items():
            setattr(app.state, name, value)


def test_http_get_and_post_match_contract(client):
    get = assert_contract(client.get("/api/v1/search", params={"q": "khách sạn cho 3 người ở Nha Trang dưới 4 triệu"}),
                          "/search", "get")
    assert get["diagnostics"]["queryPlan"]["party"]["source"] == "query"
    post = assert_contract(client.post("/api/v1/search", json={
        "query": "resort Nha Trang", "priceMax": 4000000,
        "travelContext": {"checkIn": "2026-10-10", "checkOut": "2026-10-12", "guests": {"adults": 2, "children": 1}}}),
        "/search", "post")
    assert post["appliedFilters"]["hard"]["minOccupancy"] == 3 and post["appliedFilters"]["hard"]["partySource"] == "param"
    bad = client.post("/api/v1/search", json={"query": "resort", "priceMin": 9, "priceMax": 1})
    assert assert_contract(bad, "/search", "post")["error"]["code"] == "VALIDATION_ERROR"


def _query_plan_schema() -> dict:
    return DOC["components"]["schemas"]["EngineDiagnostics"]["properties"]["queryPlan"]["properties"]


def test_contract_declares_every_domain_constant():
    qp = _query_plan_schema()
    reasons = {v for k, v in vars(query_plan).items() if k.startswith("REASON_") and isinstance(v, str)}
    assert reasons and all(r in qp["fallbackReasons"]["description"] for r in reasons), reasons
    families = {v for k, v in vars(query_plan).items() if k.startswith("APPLIED_") and isinstance(v, str)}
    assert families <= set(qp["applied"]["items"]["enum"]) and families <= set(qp["emptyReason"]["enum"])
    combo_flags = {unit_attributes.FLAG_INCLUDES_FLIGHT, unit_attributes.FLAG_INCLUDES_HOTEL}
    assert combo_flags == set(qp["mustNot"]["properties"]["flags"]["items"]["enum"])
    scored = DOC["components"]["schemas"]["ScoredProduct"]["allOf"][1]["properties"]
    assert scored["matchedChildren"]["maxItems"] == 5
    assert DOC["info"]["version"] == app.version == "1.27.0"
