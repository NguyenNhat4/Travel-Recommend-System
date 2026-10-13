"""Read-only job execution: pagination, exact shown scope and fresh comparative anchors."""
import asyncio
from copy import deepcopy
from time import time
import unittest

from src.backend.app.agents.models import FareQuestion, Job
from src.backend.app.agents.steps import jobs, shown
from src.backend.app.agents.nodes import intake_node


def product(pid, taxonomy="hotel", destination="Hà Nội", price=1_000_000, **extra):
    return {"productId": pid, "name": f"Nơi {pid}", "taxonomy": taxonomy, "destination": destination,
            "unitPrice": price, "priceUnit": "PER_NIGHT" if taxonomy == "hotel" else "PER_PERSON", "currency": "VND",
            "available": True, "attributes": {"latitude": 21.03, "longitude": 105.85, "pool": True}, **extra}


class Tools:
    supports_catalog = True

    def __init__(self, products, page_size=None):
        self.products = deepcopy(products)
        self.calls = []
        self.page_size = page_size

    async def list_destinations(self):
        self.calls.append(("destinations", {}))
        return {"destinations": [{"destination": name, "productCount": 20} for name in ("Hà Nội", "Đà Nẵng")]}

    def definitions(self):
        return []

    async def get_product_detail(self, pid):
        self.calls.append(("detail", pid))
        return deepcopy(next(item for item in self.products if item["productId"] == pid))

    def _page(self, params):
        pool = [p for p in self.products if (not params.get("destination") or p["destination"] == params["destination"])
                and (not params.get("taxonomy") or p["taxonomy"] == params["taxonomy"])]
        if params.get("sort") in ("price_asc", "price_desc"):
            pool.sort(key=lambda item: item["unitPrice"], reverse=params["sort"] == "price_desc")
        offset = params.get("offset", 0)
        limit = self.page_size or params.get("limit", 50)
        return {"results": deepcopy(pool[offset:offset + limit]), "total": len(pool)}

    async def execute(self, call):
        self.calls.append(("search", deepcopy(call["args"])))
        return {"data": self._page(call["args"])}

    async def list_products(self, params):
        self.calls.append(("list", deepcopy(params)))
        return self._page(params)


def initial(**extra):
    return {**intake_node({"query": "hà nội"}),
            "supported_destinations": ["Hà Nội", "Đà Nẵng"], **extra}


async def run(state, tools, *specs):
    return await jobs.execute(state, list(specs), tools=tools, timeout_seconds=1, budget_seconds=30)


class JobTests(unittest.IsolatedAsyncioTestCase):
    async def test_more_after_multicity_search_does_not_choose_last_card_city(self):
        cards = [product("a", "attraction", "Hà Nội"), product("b", "attraction", "Đà Nẵng")]
        memory = shown.record({}, {"searchResults": {"attraction": cards}})
        for item in memory["items"]:
            item["via"] = {"destination": None, "taxonomy": "attraction", "query": "chỗ chơi"}
        tools = Tools([*cards, product("c", "attraction", "Hà Nội"), product("d", "attraction", "Đà Nẵng")])
        update = await run(initial(shown=memory), tools, Job(kind="explore", intent="more", taxonomy="attraction"))
        self.assertNotIn("destination", tools.calls[0][1])
        self.assertEqual({p["productId"] for p in update["turn_jobs"][0]["products"]}, {"c", "d"})

    async def test_more_with_legacy_multicity_cards_does_not_guess_one_city(self):
        memory = shown.record({}, {"searchResults": {"attraction": [
            product("a", "attraction", "Hà Nội"), product("b", "attraction", "Đà Nẵng")]}})
        spec = jobs.inherited(initial(shown=memory), Job(kind="explore", intent="more", taxonomy="attraction").model_dump())
        self.assertIsNone(spec["destination"])

    async def test_more_can_replace_scope_without_repeating_seen_or_excluded_cities(self):
        memory = shown.record({}, {"searchResults": {"attraction": [product("a", "attraction")]}})
        memory["items"][0]["via"] = {"destination": "Hà Nội", "taxonomy": "attraction", "query": "bảo tàng",
                                      "near": "Hồ Gươm", "sort": "price_asc"}
        tools = Tools([product("a", "attraction"), product("b", "attraction"),
                       product("c", "attraction", "Đà Nẵng")])
        update = await run(initial(shown=memory), tools, Job(kind="explore", intent="more", scope_mode="replace",
                            taxonomy="attraction", query="chỗ chơi", excluded_destinations=["ha noi"]))
        row = update["turn_jobs"][0]
        self.assertIsNone(row["spec"]["destination"])
        self.assertIsNone(row["spec"]["near"])
        self.assertEqual(row["spec"]["sort"], "relevance")
        self.assertNotIn("destination", tools.calls[0][1])
        self.assertEqual(row["spec"]["excluded_destinations"], ["Hà Nội"])
        self.assertEqual([p["productId"] for p in row["products"]], ["c"])

    async def test_thematic_search_without_city_keeps_each_result_destination_in_brief(self):
        tools = Tools([product("temple-a", "attraction", "Hà Nội", name="Chùa A"),
                       product("temple-b", "attraction", "Đà Nẵng", name="Chùa B")])
        update = await run(initial(), tools, Job(kind="explore", taxonomy="attraction", query="chùa"))
        self.assertEqual([p["productId"] for p in update["turn_jobs"][0]["products"]], ["temple-a", "temple-b"])
        self.assertEqual(len(tools.calls), 1)
        self.assertNotIn("destination", tools.calls[0][1])
        self.assertEqual(tools.calls[0][1]["query"], "chùa")
        lines = update["turn_results"][0]["items"]
        self.assertIn("điểm đến: Hà Nội", lines[0])
        self.assertIn("điểm đến: Đà Nẵng", lines[1])

    async def test_more_excludes_entire_conversation_only_for_matching_destination_and_type(self):
        cards = [product("a"), product("b"), product("c", "attraction"), product("d", destination="Đà Nẵng")]
        memory = shown.record({}, {"searchResults": {"hotel": [cards[0]]}})
        memory = shown.record({"shown": memory}, {"searchResults": {"attraction": [cards[2]], "hotel": [cards[3]]}})
        update = await run(initial(shown=memory), Tools(cards), Job(kind="explore", intent="more", destination="Hà Nội", taxonomy="hotel"))
        self.assertEqual([p["productId"] for p in update["turn_jobs"][0]["products"]], ["b"])
        self.assertNotIn("a", update["turn_codes"].values())

    async def test_about_shown_refreshes_only_requested_reference(self):
        cards = [product("a"), product("b", price=2_000_000)]
        memory = shown.record({}, {"searchResults": {"hotel": cards}})
        tools = Tools([product("a"), product("b", price=3_000_000)])
        update = await run(initial(shown=memory), tools, Job(kind="explore", intent="about_shown", refers_to=["#2"]))
        self.assertEqual(tools.calls, [("detail", "b")])
        self.assertEqual(update["turn_codes"], {"#2": "b"})
        self.assertEqual(update["turn_jobs"][0]["products"][0]["unitPrice"], 3_000_000)

    async def test_unlisted_is_consumed_before_fetching_a_new_source_page(self):
        tools = Tools([product(f"p{i}") for i in range(20)])
        state = initial()
        update = await run(state, tools, Job(kind="explore", destination="Hà Nội", taxonomy="hotel"))
        self.assertEqual(update["turn_results"][0]["unlisted"], 12)
        state.update(update)
        update = await run(state, tools, Job(kind="explore", continue_from=1))
        self.assertEqual(len(tools.calls), 1)
        self.assertEqual(update["turn_results"][-1]["unlisted"], 4)
        self.assertEqual(update["turn_jobs"][0]["cursor"], 16)
        self.assertEqual(update["turn_results"][-1]["items"][0].split()[0], "#9")

    async def test_continue_fetches_next_page_only_after_unlisted_runs_out(self):
        tools = Tools([product(f"p{i}") for i in range(10)], page_size=5)
        state = initial()
        state.update(await run(state, tools, Job(kind="explore", destination="Hà Nội", taxonomy="hotel")))
        self.assertTrue(state["turn_results"][0]["source_more"])
        update = await run(state, tools, Job(kind="explore", continue_from=1))
        self.assertEqual(tools.calls[-1][1]["offset"], 5)
        self.assertFalse(update["turn_results"][-1]["source_more"])
        state.update(update)
        update = await run(state, tools, Job(kind="explore", continue_from=1))
        self.assertEqual(update["turn_results"][-1]["status"], "empty")
        self.assertEqual(len(tools.calls), 2)

    async def test_more_skips_fully_seen_page_with_budget(self):
        cards = [product(f"p{i}") for i in range(6)]
        memory = shown.record({}, {"searchResults": {"hotel": cards[:3]}})
        tools = Tools(cards, page_size=3)
        update = await run(initial(shown=memory), tools, Job(kind="explore", intent="more", destination="Hà Nội", taxonomy="hotel"))
        self.assertEqual([p["productId"] for p in update["turn_jobs"][0]["products"]], ["p3", "p4", "p5"])
        self.assertEqual([args["offset"] for _, args in tools.calls], [0, 3])

    async def test_cheaper_uses_fresh_lowest_anchor_and_preserves_prior_conditions(self):
        memory = shown.record({}, {"searchResults": {"hotel": [product("a", price=4_000_000), product("b", price=5_000_000)]}})
        for item in memory["items"]:
            item["via"] = {"destination": "Hà Nội", "taxonomy": "hotel", "query": "khách sạn có hồ bơi", "near": None, "sort": "relevance"}
        tools = Tools([product("a", price=2_000_000), product("b", price=3_000_000), product("c", price=1_000_000),
                       product("d", price=2_000_000), product("e", price=500_000, priceUnit="PER_PACKAGE")])
        update = await run(initial(shown=memory), tools, Job(kind="explore", intent="cheaper", refers_to=["#1", "#2"]))
        row = update["turn_jobs"][0]
        self.assertEqual(row["anchor"], "#1")
        self.assertEqual(row["anchor_product"]["unitPrice"], 2_000_000)
        self.assertEqual([p["productId"] for p in row["products"]], ["c"])
        self.assertEqual(tools.calls[-1][1]["query"], "khách sạn có hồ bơi")

    async def test_near_refreshes_one_anchor_and_filters_distance(self):
        anchor = product("a", "attraction")
        memory = shown.record({}, {"searchResults": {"attraction": [anchor]}})
        tools = Tools([anchor, product("b"), product("far", attributes={"latitude": 10, "longitude": 106})])
        update = await run(initial(shown=memory), tools, Job(kind="explore", destination="Hà Nội", taxonomy="hotel", near="#1"))
        self.assertEqual([p["productId"] for p in update["turn_jobs"][0]["products"]], ["b"])
        self.assertEqual(update["turn_jobs"][0]["anchor"], "#1")

    async def test_sort_uses_catalog_listing(self):
        tools = Tools([product("a", price=3_000_000), product("b", price=1_000_000)])
        update = await run(initial(), tools, Job(kind="explore", destination="Hà Nội", taxonomy="hotel", sort="price_asc"))
        self.assertEqual(tools.calls[0][0], "list")
        self.assertEqual([p["productId"] for p in update["turn_jobs"][0]["products"]], ["b", "a"])

    async def test_duplicate_jobs_stop_but_moving_cursor_is_new_work(self):
        tools = Tools([product(f"p{i}") for i in range(20)])
        state = initial()
        spec = Job(kind="explore", destination="Hà Nội", taxonomy="hotel")
        state.update(await run(state, tools, spec))
        self.assertFalse((await run(state, tools, spec))["jobs_progress"])
        state.update(await run(state, tools, Job(kind="explore", continue_from=1)))
        self.assertTrue((await run(state, tools, Job(kind="explore", continue_from=1)))["jobs_progress"])

    async def test_tool_failure_is_safe_and_bounded(self):
        class Broken(Tools):
            async def execute(self, call):
                raise RuntimeError("secret upstream text")
        update = await run(initial(), Broken([]), Job(kind="explore", destination="Hà Nội"))
        self.assertEqual(update["turn_jobs"][0]["status"], "failed")
        self.assertNotIn("secret", str(update))

    async def test_short_codes_reserved_for_unshown_items_are_not_reused(self):
        state = initial()
        update = await run(state, Tools([product("a"), product("b")]), Job(kind="explore", destination="Hà Nội"))
        seen = shown.record({**state, **update}, {"searchResults": {"hotel": [product("a")]}})
        self.assertEqual(seen["seq"], 2)
        self.assertEqual(len(seen["items"]), 1)
        self.assertIn("via", seen["items"][0])
        self.assertEqual(shown.record({"shown": seen}, {"searchResults": {"hotel": [product("c")]}})["items"][-1]["ref"], "#3")

    async def test_per_job_and_round_brief_limits(self):
        state = initial()
        tools = Tools([product(f"p{i}", name="Nơi " + "dài " * 120) for i in range(20)])
        update = await run(state, tools, Job(kind="explore", query="khách sạn"), Job(kind="explore", query="có hồ bơi"),
                           Job(kind="explore", query="gần phố cổ"))
        self.assertLessEqual(sum(len(line) for row in update["turn_results"] for line in row["items"]), jobs.ROUND_CHARS)
        self.assertTrue(all(len(row["items"]) <= 8 for row in update["turn_results"]))
        self.assertLessEqual(jobs._size(update["turn_results"]), jobs.ROUND_CHARS)
        self.assertTrue(all(jobs._size(row) <= jobs.BRIEF_CHARS for row in update["turn_results"]))

    async def test_parallel_jobs_share_one_tool_budget(self):
        counter = jobs.BudgetTools(Tools([product("a")]), 9, time() + 10, 1)
        result = await asyncio.gather(counter.get_product_detail("a"), counter.get_product_detail("a"), return_exceptions=True)
        self.assertEqual(counter.count, 10)
        self.assertEqual(sum(isinstance(value, Exception) for value in result), 1)

    def test_replaces_requires_exactly_the_missing_field(self):
        def row(number, status="asked", **fare):
            return {"job": number, "kind": "fare", "status": status, "spec": {"fare": FareQuestion(**fare).model_dump(mode="json")},
                    "pending_fare": {"destination": "Hà Nội"}}
        before = row(1, destination="Hà Nội")
        self.assertTrue(jobs.can_replace(before, row(2, destination="Hà Nội", origin="TP. Hồ Chí Minh")))
        self.assertFalse(jobs.can_replace(before, row(2, destination="Hà Nội", origin="TP. Hồ Chí Minh", day="2026-10-20")))
        self.assertFalse(jobs.can_replace(row(1, "answered", destination="Hà Nội"), row(2, destination="Hà Nội", origin="TP. Hồ Chí Minh")))


class FullConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_more_and_codes_remember_ids_beyond_forty_fact_rows(self):
        cards = [product(f"p{i}") for i in range(45)]
        state = initial()
        memory = shown.record(state, {"searchResults": {"hotel": cards}})
        self.assertEqual(len(memory["items"]), 40)
        self.assertEqual(len(memory["seen"]), 45)
        self.assertEqual(shown.ref_of(memory, "p0"), "#1")
        tools = Tools([cards[0], product("new")])
        update = await run(initial(shown=memory), tools, Job(kind="explore", intent="more", destination="Hà Nội", taxonomy="hotel"))
        self.assertEqual([p["productId"] for p in update["turn_jobs"][0]["products"]], ["new"])
        repeated = await run(initial(shown=memory), tools, Job(kind="explore", intent="new", destination="Hà Nội", taxonomy="hotel"))
        self.assertEqual(repeated["turn_codes"]["#1"], "p0")
        detail = await run(initial(shown=memory), tools, Job(kind="explore", intent="about_shown", refers_to=["#1"]))
        self.assertEqual(detail["turn_jobs"][0]["products"][0]["productId"], "p0")

    async def test_about_shown_does_not_overwrite_original_query_scope(self):
        memory = shown.record(initial(), {"searchResults": {"hotel": [product("a")]}})
        memory["items"][0]["via"] = {"destination": "Hà Nội", "taxonomy": "hotel", "query": "khách sạn có hồ bơi", "near": "Hồ Gươm", "sort": "relevance"}
        state = initial(shown=memory)
        update = await run(state, Tools([product("a")]), Job(kind="explore", intent="about_shown", refers_to=["#1"]))
        recorded = shown.record({**state, **update}, {"searchResults": {"hotel": [product("a")]}})
        self.assertEqual(recorded["items"][-1]["via"], memory["items"][0]["via"])

    async def test_continue_aliases_share_a_single_source_cursor(self):
        tools = Tools([product(f"p{i}") for i in range(20)])
        state = initial()
        state.update(await run(state, tools, Job(kind="explore", destination="Hà Nội", taxonomy="hotel")))
        state.update(await run(state, tools, Job(kind="explore", continue_from=1)))
        state.update(await run(state, tools, Job(kind="explore", continue_from=1)))
        update = await run(state, tools, Job(kind="explore", continue_from=2))
        self.assertEqual(update["turn_results"][-1]["status"], "empty")
        self.assertEqual(update["turn_results"][-1]["items"], [])
        state.update(update)
        self.assertFalse((await run(state, tools, Job(kind="explore", continue_from=1)))["jobs_progress"])
        self.assertEqual(len(tools.calls), 1)

    async def test_cheaper_near_a_place_keeps_price_anchor_and_geographic_scope(self):
        anchor, landmark = product("a", price=2_000_000), product("landmark", "attraction", price=0)
        memory = shown.record(initial(), {"searchResults": {"hotel": [anchor], "attraction": [landmark]}})
        memory["items"][0]["via"] = {"destination": "Hà Nội", "taxonomy": "hotel", "query": "có hồ bơi", "near": "#2", "sort": "relevance"}
        tools = Tools([anchor, landmark, product("cheap", price=1_000_000),
                       product("far", price=500_000, attributes={"latitude": 10, "longitude": 106})])
        update = await run(initial(shown=memory), tools, Job(kind="explore", intent="cheaper", refers_to=["#1"]))
        row = update["turn_jobs"][0]
        self.assertEqual(row["anchor_product"]["productId"], "a")
        self.assertEqual(row["near_product"]["productId"], "landmark")
        self.assertEqual([p["productId"] for p in row["products"]], ["cheap"])

    async def test_sort_preserves_semantic_conditions_via_fresh_search_intersection(self):
        class PoolTools(Tools):
            async def execute(self, call):
                self.calls.append(("search", call["args"]))
                return {"data": {"results": [self.products[1]], "total": 1}}
        tools = PoolTools([product("no-pool", price=500_000, attributes={"pool": False}), product("pool", price=1_000_000)])
        update = await run(initial(), tools, Job(kind="explore", destination="Hà Nội", taxonomy="hotel", query="khách sạn có hồ bơi", sort="price_asc"))
        self.assertEqual([p["productId"] for p in update["turn_jobs"][0]["products"]], ["pool"])
        self.assertEqual([name for name, _ in tools.calls], ["search", "list"])

    async def test_brief_budget_includes_metadata_and_previous_rounds(self):
        tools = Tools([product(f"p{i}", name="Nơi " + "dài " * 60) for i in range(20)])
        state = initial()
        for round_number in range(3):
            state.update(await run(state, tools, *(Job(kind="explore", destination="Hà Nội", query=f"ý tìm {round_number}-{index}") for index in range(3))))
            self.assertLessEqual(jobs._size(state["turn_results"]), jobs.ROUND_CHARS)
        self.assertEqual(len(state["turn_results"]), 9)
