"""Dispatcher v2: chạy đúng lời gọi orc chọn, trong ngân sách request; lỗi không biến thành rỗng."""
import asyncio
from time import monotonic

from src.backend.app.application.itinerary.orc_dispatch import OrcToolDispatcher, SourceBudget
from src.backend.app.application.itinerary.product_registry import ProductRegistry
from src.backend.tests.fakes.orc_tools import FakeTools, call, product


def dispatcher(tools: FakeTools, *, limit: int = 10, known: dict | None = None) -> OrcToolDispatcher:
    return OrcToolDispatcher(tools, ProductRegistry(known), SourceBudget(deadline=monotonic() + 30, limit=limit),
                             timeout_seconds=1)


def test_search_sends_exactly_the_orc_arguments_and_reports_next_page():
    tools = FakeTools([product(f"h{i}", "hotel") for i in range(3)], total=5)
    d = dispatcher(tools)
    result = asyncio.run(d.run(call("search_products", query="khách sạn có hồ bơi", taxonomy="hotel", limit=3,
                                    guests=2)))
    assert tools.calls == [("search_products", {"query": "khách sạn có hồ bơi", "taxonomy": "hotel", "limit": 3,
                                                "offset": 0, "travelContext": {"guests": {"adults": 2}}})]
    assert result["status"] == "ok" and result["refs"] == ["p1", "p2", "p3"]
    assert result["coverage"]["checked"] == 3 and result["coverage"]["next_cursor"]
    following = asyncio.run(d.run(call("search_products", "c2", query="khách sạn có hồ bơi", taxonomy="hotel",
                                       limit=3, guests=2, cursor=result["coverage"]["next_cursor"])))
    assert tools.calls[-1][1]["offset"] == 3 and following["coverage"]["next_cursor"] is None


def test_free_only_counts_paid_and_unknown_price_separately():
    tools = FakeTools([product("free", price=0), product("paid", price=50_000), product("unknown", price=None),
                       product("ticketless", price=None, ticketed=False)])
    result = asyncio.run(dispatcher(tools).run(call("search_products", query="điểm miễn phí", free_only=True)))
    assert result["refs"] == ["p1", "p2"]
    assert result["data"] == {"dropped_not_free": {"paid": 1, "unknown_price": 1}}


def test_exclude_refs_drop_known_products_without_extra_requests():
    tools = FakeTools([product("a"), product("b")])
    result = asyncio.run(dispatcher(tools, known={"p1": "a"}).run(call("search_products", query="x",
                                                                       exclude_refs=["p1"])))
    assert result["refs"] == ["p2"] and len(tools.calls) == 1


def test_error_is_not_empty_and_transient_error_retries_once():
    flaky = FakeTools([product("a")], failures=1)
    d = dispatcher(flaky)
    assert asyncio.run(d.run(call("search_products", query="x")))["refs"] == ["p1"]
    assert len(flaky.calls) == 2 and d.budget.used == 2
    broken = FakeTools([product("a")], failures=5)
    result = asyncio.run(dispatcher(broken).run(call("search_products", query="x")))
    assert result["status"] == "error" and result["error"] == {"code": "SEARCH_UNAVAILABLE", "retryable": True}
    assert result["refs"] == []


def test_g09_parallel_calls_cannot_exceed_the_source_budget():
    tools = FakeTools([product("a")])
    d = dispatcher(tools, limit=1)

    async def both():
        return await asyncio.gather(d.run(call("search_products", "c1", query="biển")),
                                    d.run(call("search_products", "c2", query="núi")))

    results = asyncio.run(both())
    assert sorted(r["status"] for r in results) == ["error", "ok"]
    assert [r["error"]["code"] for r in results if r["error"]] == ["TOOL_LIMIT"] and d.budget.used == 1


def test_same_request_twice_uses_the_turn_cache():
    tools = FakeTools([product("a")])
    d = dispatcher(tools)
    asyncio.run(d.run(call("search_products", "c1", query="x")))
    asyncio.run(d.run(call("get_product_detail", "c2", product_ref="p1")))
    asyncio.run(d.run(call("get_product_detail", "c3", product_ref="p1")))
    assert [name for name, _ in tools.calls] == ["search_products", "detail"] and d.budget.used == 2


def test_stale_ref_and_unavailable_tool_are_errors_for_the_orc():
    d = dispatcher(FakeTools([product("a")]), known={"p1": "a"})
    stale = asyncio.run(d.run(call("build_itinerary", destination="Huế", start_date="2026-10-24", days=1, adults=1,
                                   children=0, plan_days=[{"day_index": 1, "activities": [
                                       {"product_ref": "p1", "start_minute": 480, "end_minute": 540,
                                        "timing_source": "estimate", "assumption": "1 giờ"}]}])))
    assert stale["error"]["code"] == "STALE_REF"
    no_catalog = FakeTools()
    no_catalog.supports_catalog = False
    d = dispatcher(no_catalog)
    assert "lookup_flights" not in d.allowed
    assert asyncio.run(d.run(call("list_destinations")))["error"]["code"] == "TOOL_NOT_ALLOWED"


def test_recommendations_keep_strategy_for_honest_wording():
    result = asyncio.run(dispatcher(FakeTools([product("a")])).run(call("get_recommendations", k=3)))
    assert result["data"] == {"strategy": "popular", "because": {"p1": []}}
