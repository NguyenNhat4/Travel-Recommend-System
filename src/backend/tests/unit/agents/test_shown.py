"""Trí nhớ "đã cho xem" (`steps/shown.py`): lỗi 2026-10-12 "hà nội" → "ngoài ra còn gì nữa" trả lại đúng 4 thẻ cũ vì không
lượt nào nhớ đã hiện gì (`docs/plan/2026-10-12-nho-ket-qua-da-xem.md`, B2)."""
import unittest

import yaml

from src.backend.app.agents.nodes import finalize_node, intake_node
from src.backend.app.agents.steps import phase, shown
from src.backend.app.agents.steps.classification import extraction_input
from src.backend.app.agents.steps.orchestration import payload as orchestrator_input
from src.backend.app.agents.steps.conversation import conversation_input
from src.backend.app.agents.steps.history import llm_context
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore

from . import test_itinerary_runtime as runtime
from .test_fares import fare_llm
from .test_fares_followups import MoreFlights


def hotel(pid, **extra):
    return {"productId": pid, "name": f"Khách sạn {pid} – Hoàn Kiếm", "taxonomy": "hotel", "destination": "Hà Nội",
            "unitPrice": 1_200_000, "rating": 8.9, "reviewCount": 4712,
            "attributes": {"starRating": 4, "amenities": ["Hồ bơi ngoài trời", "Wi-Fi miễn phí", "Bữa sáng"],
                           "address": "12 Hàng Bạc, Phường Hàng Bạc, Quận Hoàn Kiếm, Hà Nội"}, **extra}


def sight(pid, **extra):
    return {"productId": pid, "name": f"Điểm {pid}", "taxonomy": "attraction", "destination": "Hà Nội",
            "unitPrice": 0, "attributes": {"ticketed": False, "openingHours": "08:00–17:00", "durationMinutes": 90,
                                           "tags": ["di tích", "văn hoá", "chụp ảnh", "thừa"]}, **extra}


def explored(*products):
    groups: dict = {}
    for product in products:
        groups.setdefault(product["taxonomy"], []).append(product)
    return {"status": "NEEDS_CLARIFICATION", "searchResults": groups}


class RecordTests(unittest.TestCase):
    def test_cards_of_a_turn_get_short_codes_and_a_line_of_facts(self):
        seen = shown.record({}, explored(sight("s1"), sight("s2"), hotel("h1")))
        self.assertEqual(seen["turn"], 1)
        self.assertEqual([item["ref"] for item in seen["items"]], ["#1", "#2", "#3"])
        line = shown.by_ref(seen)["#3"]["facts"]
        self.assertIn("1.200.000 ₫/đêm", line)
        self.assertIn("4 sao", line)
        self.assertIn("8.9 điểm (4,7k đánh giá)", line)
        self.assertIn("pool", line)
        self.assertIn("Quận Hoàn Kiếm", line)
        self.assertNotIn("Hàng Bạc,", line)  # không đưa địa chỉ đầy đủ
        sight_line = shown.by_ref(seen)["#1"]["facts"]
        self.assertIn("tham quan tự do", sight_line)
        self.assertIn("mở 08:00–17:00", sight_line)
        self.assertIn("khoảng 1 giờ 30 phút", sight_line)
        self.assertNotIn("thừa", sight_line)  # tối đa 3 nhãn
        all_day = sight("s9")
        all_day["attributes"]["openingHours"] = "Mở cửa cả ngày"
        self.assertIn("; Mở cửa cả ngày;", shown.facts(all_day))

    def test_the_price_unit_follows_the_catalog_so_per_person_or_per_package_is_known(self):
        tour = sight("t1", unitPrice=900_000, priceUnit="PER_PERSON", attributes={"ticketed": True})
        combo = sight("c1", taxonomy="combo", unitPrice=5_000_000, priceUnit="PER_PACKAGE", attributes={})
        unknown = sight("u1", unitPrice=300_000, priceUnit="UNKNOWN", attributes={"ticketed": True})
        self.assertIn("900.000 ₫/khách", shown.facts(tour))
        self.assertIn("5.000.000 ₫/gói", shown.facts(combo))
        self.assertIn("300.000 ₫;", shown.facts(unknown) + ";")
        self.assertIn("1.200.000 ₫/đêm", shown.facts(hotel("h1")))  # thiếu priceUnit: khách sạn tính theo đêm

    def test_the_full_tool_product_is_preferred_over_the_summary_in_the_response(self):
        summary = {"productId": "h1", "name": "Khách sạn h1", "taxonomy": "hotel", "destination": "Hà Nội",
                   "unitPrice": 1_200_000}
        seen = shown.record({"candidates": {"h1": hotel("h1")}}, explored(summary))
        self.assertIn("4 sao", seen["items"][0]["facts"])

    def test_a_product_shown_again_keeps_its_code_and_codes_are_never_reused(self):
        first = shown.record({}, explored(sight("s1"), sight("s2")))
        second = shown.record({"shown": first}, explored(sight("s2"), sight("s3")))
        refs = {item["productId"]: item["ref"] for item in second["items"]}
        self.assertEqual(refs, {"s1": "#1", "s2": "#2", "s3": "#3"})
        self.assertEqual([item["productId"] for item in second["items"]], ["s1", "s2", "s3"])
        self.assertEqual(shown.by_ref(second)["#2"]["turn"], 2)

    def test_at_most_forty_items_per_place_dropping_the_oldest(self):
        seen = shown.record({}, explored(*[sight(f"s{index}") for index in range(45)]))
        seen = shown.record({"shown": seen}, explored(hotel("other", destination="Đà Nẵng")))
        hanoi = [item for item in seen["items"] if item["place"] == "Hà Nội"]
        self.assertEqual(len(hanoi), shown.MAX_PER_PLACE)
        self.assertEqual(hanoi[0]["productId"], "s5")
        self.assertEqual(shown.by_ref(seen)["#46"]["place"], "Đà Nẵng")

    def test_an_itinerary_records_its_flights_stay_and_activities_with_where_they_are(self):
        flight = {"productId": "f1", "name": "VJ1", "taxonomy": "flight", "destination": "Hà Nội", "unitPrice": 900_000,
                  "attributes": {"airline": "VietJet Air", "flightNumber": "VJ1", "originCity": "TP. Hồ Chí Minh",
                                 "destinationCity": "Hà Nội", "departureAt": "2999-10-10T06:00:00+07:00",
                                 "departureTimeLocal": "06:00"}}
        response = {"status": "COMPLETED", "itinerary": {
            "flights": [{"product": flight, "direction": "OUTBOUND"}],
            "stays": [{"product": hotel("h1")}],
            "days": [{"day": 1, "slots": [{"time": "MORNING", "product": sight("s1")}]},
                     {"day": 2, "slots": [{"time": "AFTERNOON", "product": sight("s2")}, {"time": "EVENING",
                                                                                         "product": None}]}]}}
        seen = shown.record({}, response)
        where = {item["productId"]: (item["where"], item["place"]) for item in seen["items"]}
        self.assertEqual(where["f1"], ("lịch, chặng đi", "TP. Hồ Chí Minh→Hà Nội"))
        self.assertEqual(where["h1"][0], "lịch, khách sạn")
        self.assertEqual(where["s2"][0], "lịch, ngày 2 chiều")
        self.assertEqual(shown.by_ref(seen)["#1"]["name"], "VietJet Air VJ1")
        self.assertEqual(shown.by_ref(seen)["#1"]["facts"],
                         "flight; TP. Hồ Chí Minh→Hà Nội; 10/10; cất cánh 06:00; 900.000 ₫/khách")

    def test_a_conversation_saved_before_this_field_reads_as_empty(self):
        self.assertEqual(phase.carried({})["shown"], shown.EMPTY)
        self.assertEqual(shown.current({"shown": None}), shown.EMPTY)


def plan_response():
    return {"status": "COMPLETED", "itinerary": {
        "estimatedTotal": 9_999_000,
        "stays": [{"product": hotel("h1"), "fromNight": 1, "nights": 2}],
        "days": [{"day": 1, "slots": [{"time": "MORNING", "product": sight("s1")},
                                      {"time": "AFTERNOON", "product": sight("s2")}]},
                 {"day": 2, "slots": [{"time": "MORNING", "product": sight("s3")}]}]}}


class ContextTests(unittest.TestCase):
    """Khối "đã gợi ý" trong ngữ cảnh chung của mọi lời gọi LLM (plan 2026-10-12 B3)."""

    def planned(self, query="ngoài ra còn gì nữa"):
        response = plan_response()
        seen = shown.record({}, response)
        seen = shown.record({"shown": seen}, explored(sight("s4"), sight("s5"), hotel("h2"), hotel("h3")))
        return {**intake_node({"query": query}), "shown": seen, "previous_plan": {"itinerary": response["itinerary"]},
                "conversation_history": [{"role": "user", "content": "hà nội"},
                                         {"role": "assistant", "content": "Hà Nội có…", "note": "giới thiệu 4 nơi"}]}

    def test_every_card_of_the_last_turn_and_every_product_of_the_plan_reach_the_model(self):
        block = llm_context(self.planned())["already_shown"]
        text = "\n".join(block["items"])
        for ref in ("#1", "#2", "#3", "#4", "#5", "#6", "#7", "#8"):
            self.assertIn(f"{ref} ", text)
        self.assertEqual(block["current_plan"],
                         "khách sạn #1 (đêm 1–2); ngày 1: sáng #2, chiều #3; ngày 2: sáng #4")
        self.assertNotIn("9.999.000", yaml.safe_dump(block, allow_unicode=True))  # không có tổng tiền lịch

    def test_the_block_stays_short_after_many_turns_and_keeps_the_last_turn(self):
        seen = shown.EMPTY
        for turn in range(20):
            seen = shown.record({"shown": seen}, explored(*[hotel(f"t{turn}-{index}", destination=f"Nơi {turn}")
                                                             for index in range(4)]))
        block = shown.context({"shown": seen})
        self.assertLessEqual(sum(len(line) for line in block["items"]), shown.MAX_CONTEXT_CHARS)
        last = [item["ref"] for item in seen["items"] if item["turn"] == 20]
        self.assertTrue(all(any(line.startswith(f"{ref} ") for line in block["items"]) for ref in last))
        self.assertFalse(any(line.startswith("#1 ") for line in block["items"]))  # lượt cũ nhất bị bỏ trước

    def test_every_node_gets_the_block_and_the_message_stays_first(self):
        # Đo lặp 2026-10-12: đưa tin nhắn xuống cuối payload làm câu hỏi vé hiểu sai nhiều hơn; giữ thứ tự cũ.
        state = {**self.planned(), "missing_fields": [], "interaction_type": "conversation"}
        for name, build in (("orchestrate", orchestrator_input), ("extract", extraction_input),
                            ("clarify", conversation_input)):
            with self.subTest(node=name):
                payload = yaml.safe_load(build(state)[1][1])
                keys = list(payload)
                self.assertEqual(keys[0], "message")
                self.assertEqual(payload["message"], "ngoài ra còn gì nữa")
                self.assertEqual(keys.index("already_shown"), keys.index("known_constraints") + 1)
                self.assertEqual(len(payload["already_shown"]["items"]), 8)

    def test_a_conversation_without_anything_shown_has_no_block(self):
        self.assertNotIn("already_shown", llm_context(intake_node({"query": "hà nội"})))


class FinalizeTests(unittest.TestCase):
    def test_a_response_that_fails_validation_shows_nothing(self):
        before = shown.record({}, explored(sight("s1")))
        state = {"response": {"status": "BOGUS"}, "http_status": 200, "shown": before, "conversation_id": "c",
                 "request_id": "r", "intent": {}}
        update = finalize_node(state)
        self.assertEqual(update["http_status"], 500)
        self.assertEqual(update["shown"], before)


class SavedTests(unittest.IsolatedAsyncioTestCase):
    run_graph = runtime.RuntimeTests.run_graph

    async def test_fare_cards_are_remembered_for_the_next_turn(self):
        clients, store = MoreFlights(), InMemoryConversationStore()
        result = await self.run_graph(fare_llm(origin='hn', destination='nt'), clients, store=store, owner='u',
                                      state={'query': 'vé hn ra nt bao nhiu'})
        saved = await store.load(result['conversation_id'], 'u')
        cards = [card['productId'] for card in result['response']['searchResults']['flight']]
        self.assertEqual([item['productId'] for item in saved['shown']['items']], cards)
        self.assertTrue(all(item['where'] == 'vé máy bay' for item in saved['shown']['items']))
        self.assertEqual(saved['shown']['turn'], 1)


if __name__ == "__main__":
    unittest.main()
