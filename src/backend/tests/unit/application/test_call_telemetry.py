"""Đo lần gọi web / agent (docs/prd/deployment-plan.md §5): wrapper use case, bộ đệm, middleware, endpoint vận hành."""
import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import APIRouter, FastAPI, HTTPException

from src.backend.app.api.middleware import install_call_telemetry
from src.backend.app.api.ops import ops_router
from src.backend.app.application.itinerary.engine_tools import InProcessItineraryTools
from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.application.telemetry import Traced, summarize, traced
from src.backend.app.core.call_context import call_scope, current_source, note
from src.backend.app.infrastructure.telemetry.memory import InMemoryCallTelemetry


def run(coro):
    return asyncio.run(coro)


# -- summarize / Traced

def test_summarize_reads_ids_counts_and_stage_ms_only():
    out = summarize({"results": [{"productId": "a"}, {"productId": "b"}, {"x": 1}],
                     "diagnostics": {"stageMs": {"embed": 3}}, "query": "bí mật"})
    assert out == {"resultCount": 3, "productIds": ["a", "b"], "stageMs": {"embed": 3}}
    assert summarize([{"productId": f"p{i}"} for i in range(30)])["productIds"][-1] == "p19"  # tối đa 20 id
    assert summarize({"productId": "one", "name": "x"}) == {"resultCount": 1, "productIds": ["one"]}
    assert summarize(SimpleNamespace(results=({"productId": "s"},))) == {"resultCount": 1, "productIds": ["s"]}
    assert summarize(None) == {}


def test_traced_sync_async_and_passthrough():
    class Engine:
        units = [1, 2]

        def __call__(self, q):
            return {"results": [{"productId": "p1"}]}

        def lookup(self, pid):
            return SimpleNamespace(results=[{"productId": pid}])

    class AsyncCase:
        async def __call__(self, pid):
            return {"productId": pid}

    engine = traced(Engine(), "search")
    assert traced(engine, "search") is engine and traced(None, "x") is None
    assert engine.units == [1, 2]  # thuộc tính khác đi thẳng tới engine gốc
    with call_scope("web") as detail:
        engine("hạ long")
    assert detail["useCase"] == "search" and detail["productIds"] == ["p1"] and "useCaseMs" in detail
    with call_scope("agent") as detail:
        engine.lookup("p9")
    assert detail["productIds"] == ["p9"] and current_source() is None  # scope đóng thì nguồn trở về None
    case = Traced(AsyncCase(), "get_product_detail")
    with call_scope("web") as detail:
        assert run(case("p5")) == {"productId": "p5"}
    assert detail["useCase"] == "get_product_detail" and detail["productIds"] == ["p5"]
    note(ignored=True)  # ngoài lần gọi: không lỗi, không ghi đâu cả


# -- InMemoryCallTelemetry

def test_buffer_sequence_summary_errors_and_prometheus():
    t = InMemoryCallTelemetry(capacity=3)
    for i, status in enumerate([200, 500, 404, "ok", "error:SEARCH_UNAVAILABLE"]):
        t.record({"source": "web" if i < 3 else "agent", "kind": "http" if i < 3 else "tool",
                  "name": "GET /api/v1/search" if i < 3 else "search_products", "status": status, "ms": 10 * (i + 1)})
    t.set_catalog(1234)
    snap = t.snapshot()
    assert snap["lastSeq"] == 5 and [e["seq"] for e in snap["events"]] == [3, 4, 5]  # vòng đệm giữ 3 cái mới nhất
    assert [e["seq"] for e in t.snapshot(after=4)["events"]] == [5]
    rows = {(r["source"], r["name"]): r for r in snap["summary"]}
    web, agent = rows[("web", "GET /api/v1/search")], rows[("agent", "search_products")]
    assert (web["count"], web["errors"]) == (3, 1)  # chỉ 5xx là lỗi; 404 thì không
    assert (agent["count"], agent["errors"]) == (2, 1)
    assert web["p50Ms"] == 20.0 and web["p95Ms"] == 30.0
    assert snap["catalog"]["products"] == 1234 and snap["catalog"]["reloads"] == 1
    text = t.prometheus()
    assert 'vota_calls_total{source="web",kind="http",name="GET /api/v1/search"} 3' in text
    assert 'vota_call_errors_total{source="agent",kind="tool",name="search_products"} 1' in text
    assert "vota_catalog_products 1234" in text


# -- web: middleware + endpoint vận hành

def web_app(telemetry):
    app = FastAPI()
    app.state.call_telemetry = telemetry
    install_call_telemetry(app)
    app.include_router(ops_router)
    detail = traced(lambda pid: {"productId": pid}, "get_product_detail")

    @app.get("/api/v1/products/{product_id}")
    async def product(product_id: str):
        return detail(product_id)

    @app.get("/api/v1/boom")
    async def boom():
        raise HTTPException(503)

    @app.get("/health")
    async def health():
        return {"ok": True}

    router = APIRouter()  # như app thật: router gắn qua include_router(prefix="/api/v1")

    @router.get("/search")
    async def search():
        return {"results": []}

    app.include_router(router, prefix="/api/v1")

    return app


def test_web_calls_are_recorded_with_route_template_not_values():
    t = InMemoryCallTelemetry()

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=web_app(t)), base_url="http://t") as c:
            assert (await c.get("/api/v1/products/p-42?utm=secret")).status_code == 200
            assert (await c.get("/api/v1/boom")).status_code == 503
            await c.get("/health")
            await c.get("/api/v1/nope")
            await c.get("/api/v1/search")
            metrics = await c.get("/metrics")
            calls = await c.get("/internal/calls", params={"after": 0})
            return metrics, calls

    metrics, calls = run(scenario())
    events = calls.json()["events"]
    assert [e["name"] for e in events] == ["GET /api/v1/products/{product_id}", "GET /api/v1/boom",
                                           "GET (không khớp route)", "GET /api/v1/search"]  # /health, /metrics: không đo
    first = events[0]
    assert (first["source"], first["kind"], first["status"]) == ("web", "http", 200)
    assert first["productIds"] == ["p-42"] and first["useCase"] == "get_product_detail"
    assert "secret" not in str(events) and "utm" not in str(events)
    assert events[1]["status"] == 503
    assert metrics.status_code == 200 and "vota_calls_total" in metrics.text


def test_ops_endpoints_report_503_without_telemetry():
    app = FastAPI()
    app.include_router(ops_router)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return (await c.get("/metrics")).status_code, (await c.get("/internal/calls")).status_code

    assert run(scenario()) == (503, 503)


# -- agent: công cụ trong tiến trình

def tools(t, **providers):
    return InProcessItineraryTools(
        search=lambda: providers.get("search"), recommend=lambda: None, index=lambda: None,
        product_detail=lambda: providers.get("detail"), similar_products=lambda: None,
        token_verifier=lambda: None, revoked_tokens=lambda: None, telemetry=t)


def test_agent_tool_calls_are_recorded_with_engine_detail(services):
    t = InMemoryCallTelemetry()
    engine = traced(services["search"], "search")
    run(tools(t, search=engine).search_products({"query": "nghỉ dưỡng biển", "limit": 5, "offset": 0}))
    [event] = t.snapshot()["events"]
    assert (event["source"], event["kind"], event["name"], event["status"]) == ("agent", "tool", "search_products", "ok")
    assert event["useCase"] == "search" and event["resultCount"] >= 1 and event["productIds"]
    assert set(event["stageMs"]) >= {"embed", "dense", "hydrate"}  # đo bằng StageTimer của /search
    assert "nghỉ dưỡng" not in str(event)


def test_agent_errors_are_recorded_and_still_raised():
    t = InMemoryCallTelemetry()
    with pytest.raises(ToolError):
        run(tools(t).search_products({"query": "x"}))  # engine chưa nạp → SEARCH_UNAVAILABLE
    [event] = t.snapshot()["events"]
    assert event["status"].startswith("error:") and event["source"] == "agent"


def test_agent_inside_web_request_keeps_sources_apart(services):
    t = InMemoryCallTelemetry()
    engine = traced(services["search"], "search")

    async def scenario():
        with call_scope("web") as web_detail:
            await tools(t, search=engine).search_products({"query": "biển", "limit": 3, "offset": 0})
            return web_detail, current_source()

    web_detail, source_after = run(scenario())
    assert source_after == "web" and web_detail == {}  # chi tiết của công cụ agent không lẫn vào request web
    assert t.snapshot()["events"][0]["source"] == "agent"
