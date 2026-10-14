"""Five tools: physical source budget, paging, nested rooms and partial failures."""

import asyncio
from time import monotonic

from src.backend.app.application.itinerary.orc_dispatch import (
    OrcToolDispatcher,
    SourceBudget,
)
from src.backend.app.application.itinerary.product_registry import ProductRegistry
from src.backend.tests.fakes.orc_tools import FakeTools, call, product


def dispatcher(tools, limit=10, known=None):
    return OrcToolDispatcher(
        tools,
        ProductRegistry(known),
        SourceBudget(deadline=monotonic() + 30, limit=limit),
        timeout_seconds=1,
    )


def test_find_paging_and_cursor_scope():
    tools = FakeTools([product(str(i)) for i in range(3)], total=5)
    d = dispatcher(tools)
    first = asyncio.run(
        d.run(call("find_products", query="lịch sử", taxonomy="attraction", limit=3))
    )
    cursor = first["coverage"]["next_cursor"]
    second = asyncio.run(
        d.run(
            call(
                "find_products",
                "c2",
                query="lịch sử",
                taxonomy="attraction",
                limit=3,
                cursor=cursor,
            )
        )
    )
    assert tools.calls[-1][1]["offset"] == 3 and second["refs"] == []
    wrong = asyncio.run(
        d.run(call("find_products", query="biển", taxonomy="attraction", cursor=cursor))
    )
    assert wrong["error"]["code"] == "CURSOR_MISMATCH"
    assert wrong["error"]["reason"] == "parameters_changed:query"


def test_free_only_and_exclusion_are_grounded():
    tools = FakeTools(
        [
            product("free", price=0),
            product("paid"),
            product("unknown", price=None, ticketed=True),
            product("no-ticket", price=None, ticketed=False),
        ]
    )
    d = dispatcher(tools, known={"p1": "free"})
    result = asyncio.run(
        d.run(
            call(
                "find_products",
                query="điểm",
                taxonomy="attraction",
                free_only=True,
                exclude_refs=["p1"],
            )
        )
    )
    assert len(result["refs"]) == 1
    assert result["data"]["dropped_not_free"] == {"paid": 1, "unknown_price": 1}


def test_free_only_is_forwarded_to_catalog_before_paging():
    tools = FakeTools([product("public-place", price=None)])
    d = dispatcher(tools)
    result = asyncio.run(d.run(call("find_products", taxonomy="attraction", free_only=True, limit=1)))
    assert tools.calls == [("list", {"taxonomy": "attraction", "availableOnly": True, "sort": "popular",
                                      "limit": 1, "offset": 0, "freeOnly": True})]
    assert result["refs"] == ["p1"] and d.budget.used == 1
    assert d.registry.view("p1")["entryPolicy"] == "assumed_free"


def test_hotels_include_room_refs_and_date_filter_with_one_business_call():
    hotel = product("h", "hotel", price=800_000, unit="PER_NIGHT")
    good = product(
        "r",
        "hotel",
        price=900_000,
        unit="PER_NIGHT",
        parentProductId="h",
        priceAdults=2,
    )
    closed = product(
        "x",
        "hotel",
        parentProductId="h",
        availability={"from": "2026-10-25", "calendar": "10"},
    )
    tools = FakeTools([hotel], listing={"h": [good, closed]})
    d = dispatcher(tools)
    result = asyncio.run(
        d.run(
            call(
                "find_products",
                taxonomy="hotel",
                destination="Huế",
                check_in="2026-10-25",
                check_out="2026-10-27",
            )
        )
    )
    assert result["refs"] == ["p1"] and result["data"]["rooms"] == {"p1": ["p2"]}
    assert d.registry.product("p2")["productId"] == "r" and d.budget.used == 2


def test_room_request_failure_preserves_hotels_as_partial():
    d = dispatcher(FakeTools([product("h", "hotel")]), limit=1)
    result = asyncio.run(d.run(call("find_products", taxonomy="hotel")))
    assert result["status"] == "partial" and result["refs"] == ["p1"]
    assert result["data"]["room_errors"] == {"p1": "TOOL_LIMIT"}


def test_unexpected_room_adapter_failure_preserves_hotels_as_partial():
    class BrokenRoomTools(FakeTools):
        async def list_products(self, params):
            if params.get("parentProductId"):
                raise RuntimeError("room adapter unavailable")
            return await super().list_products(params)

    d = dispatcher(BrokenRoomTools([product("h", "hotel")]))
    result = asyncio.run(d.run(call("find_products", taxonomy="hotel")))
    assert result["status"] == "partial" and result["refs"] == ["p1"]
    assert result["data"]["room_errors"] == {"p1": "TOOL_FAILED"}


def test_plan_feedback_requires_consent_without_granting_it():
    d = dispatcher(FakeTools([]))
    d.registry.add(product("a"))
    planning = call(
        "plan_itinerary",
        destination="Huế",
        start_date="2026-10-25",
        days=1,
        adults=1,
        schedule=[{"day": 1, "morning": "p1"}],
    )
    trip = {"destination": "Huế", "start_date": "2026-10-25", "days": 1, "adults": 1}
    denied = asyncio.run(d.run(planning, context=trip))
    assert denied["data"]["commit_allowed"] is False
    assert denied["data"]["needs_update_trip"] == ["planning_consent"]
    accepted = asyncio.run(d.run(planning, context={"planning_consent": True, **trip}))
    assert accepted["data"]["commit_allowed"] is True
    assert accepted["data"]["needs_update_trip"] == []
    # Số người lớn orc tự điền, khách chưa nói: chưa được lưu lịch (AC-AGT-01).
    guessed = asyncio.run(d.run(planning, context={"planning_consent": True, **trip, "adults": None}))
    assert guessed["data"]["commit_allowed"] is False
    assert guessed["data"]["needs_update_trip"] == ["adults"]
    stopped = asyncio.run(
        d.run(planning, context={"planning_consent": True, "stopped": True, **trip})
    )
    assert stopped["data"]["commit_allowed"] is False


def test_batch_detail_refreshes_once_and_reports_individual_error():
    d = dispatcher(FakeTools([product("a")]), known={"p1": "a", "p2": "missing"})
    result = asyncio.run(d.run(call("get_products", refs=["p1", "p9"])))
    assert result["status"] == "partial" and result["refs"] == ["p1"]
    assert result["data"]["errors"]["p9"] == "UNKNOWN_REF"
    again = asyncio.run(d.run(call("get_products", refs=["p1"])))
    assert again["refs"] == ["p1"] and d.budget.used == 1


def test_transient_retry_and_parallel_budget():
    d = dispatcher(FakeTools([product("a")], failures=1))
    result = asyncio.run(
        d.run(call("find_products", query="biển", taxonomy="attraction"))
    )
    assert result["status"] == "ok" and d.budget.used == 2
    d = dispatcher(FakeTools([product("a")]), limit=1)

    async def both():
        return await asyncio.gather(
            d.run(call("find_products", query="biển", taxonomy="attraction")),
            d.run(call("find_products", "c2", query="núi", taxonomy="attraction")),
        )

    results = asyncio.run(both())
    assert (
        sorted(row["status"] for row in results) == ["error", "ok"]
        and d.budget.used == 1
    )


def test_recommend_filters_without_claiming_personalisation():
    d = dispatcher(FakeTools([product("a"), product("h", "hotel")]), known={"p1": "a"})
    result = asyncio.run(
        d.run(call("recommend", taxonomy="hotel", exclude_refs=["p1"]))
    )
    assert result["data"]["strategy"] == "popular" and len(result["refs"]) == 1
    similar = asyncio.run(d.run(call("recommend", like_ref="p1", taxonomy="hotel")))
    assert similar["data"]["strategy"] == "similar"


def test_only_new_tools_are_available_and_stale_plan_ref_is_rejected():
    d = dispatcher(FakeTools([product("a")]), known={"p1": "a"})
    assert set(d.allowed) == {
        "find_products",
        "get_products",
        "recommend",
        "lookup_flights",
        "plan_itinerary",
    }
    result = asyncio.run(
        d.run(
            call(
                "plan_itinerary",
                destination="Huế",
                start_date="2026-10-24",
                days=1,
                adults=1,
                schedule=[{"day": 1, "morning": "p1"}],
            )
        )
    )
    assert result["error"]["code"] == "STALE_REF"


def test_named_hotel_outside_previous_destination_filters_before_registering():
    # Search can return semantic near matches; none may masquerade as the requested name.
    rows = [
        {**product('wrong-name', 'hotel', destination='Phan Thiết'), 'name': 'Le Aqua Resort'},
        {**product('old-city', 'hotel', destination='Phan Thiết'), 'name': 'Khách sạn Lê Phan'},
        {**product('right', 'hotel', destination='Đà Lạt'), 'name': 'Khách sạn Lê Phan'},
        {**product('substring', 'hotel', destination='Đà Lạt'), 'name': 'Le Phanorama Hotel'},
    ]
    tools = FakeTools(rows)
    d = dispatcher(tools)
    result = asyncio.run(d.run(call('find_products', taxonomy='hotel', query='Le Phan',
                                   name_contains='Le Phan', excluded_destinations=['phan thiet']),
                              context={'destination': 'Phan Thiết'}))
    assert result['status'] == 'ok'
    assert [d.registry.product(r)['productId'] for r in result['refs']] == ['right']
    assert result['coverage']['filtered'] == 3
    assert 'destination' not in tools.calls[0][1]
    assert [params['parentProductId'] for name, params in tools.calls if name == 'list'] == ['right']


def test_filtered_name_page_keeps_cursor_and_does_not_claim_exhaustion():
    rows = [{**product('wrong', 'hotel'), 'name': 'Le Aqua'},
            {**product('right', 'hotel'), 'name': 'Lê Phan'}]
    d = dispatcher(FakeTools(rows))
    args = {'taxonomy': 'hotel', 'query': 'Le Phan', 'name_contains': 'Le Phan', 'limit': 1}
    first = asyncio.run(d.run(call('find_products', **args)))
    assert first['status'] == 'empty' and first['refs'] == []
    cursor = first['coverage']['next_cursor']
    assert cursor and first['coverage']['checked'] == 1
    second = asyncio.run(d.run(call('find_products', 'c2', **args, cursor=cursor)))
    assert [d.registry.product(r)['productId'] for r in second['refs']] == ['right']
    wrong = asyncio.run(d.run(call('find_products', 'c3', **args, cursor=cursor,
                                  excluded_destinations=['Huế'])))
    assert wrong['error']['code'] == 'CURSOR_MISMATCH'


def test_hotel_name_filter_does_not_remove_its_differently_named_rooms():
    hotel = {**product('h', 'hotel'), 'name': 'Lê Phan'}
    room = {**product('r', 'hotel', level='room'), 'name': 'Deluxe', 'parentProductId': 'h'}
    d = dispatcher(FakeTools([hotel], listing={'h': [room]}))
    result = asyncio.run(d.run(call('find_products', taxonomy='hotel', query='Le Phan', name_contains='Le Phan')))
    assert result['data']['rooms']['p1']
