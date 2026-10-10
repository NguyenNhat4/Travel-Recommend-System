"""Đổi khách sạn, chuyến bay khi người dùng chưa nói đổi thế nào (kịch bản bản 5; góp ý người dùng 09/10/2026)."""
from datetime import date
import unittest

from src.backend.app.agents.nodes import intake_node
from src.backend.app.agents.steps import changes
from src.backend.app.domain.itinerary.flights import choose_flights, flight_choices
from src.backend.app.domain.itinerary.planning import empty_intent
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore

from . import test_itinerary_runtime as runtime
from .test_itinerary_runtime import FlightClients, ScriptedLlm, extracted, flight_product


def option(index, hotel, money_delta, km_delta):
    return {"index": index, "stays": [{"productId": f"h{index}", "name": hotel, "fromNight": 1, "nights": 2}],
            "moneyDelta": money_delta, "kmDelta": km_delta, "distanceKm": 10.0, "itinerary": {"days": []}}


RETURN_CHOICE = {"direction": "RETURN", "date": "2999-10-12",
                 "chosen": {"productId": "vn", "flightNumber": "VN6025", "departure": "21:55", "unitPrice": 648_000},
                 "alternatives": [{"productId": "vu", "flightNumber": "VU779", "airline": "Vietravel Airlines",
                                   "departure": "20:55", "unitPrice": 814_000},
                                  {"productId": "vj", "flightNumber": "VJ167", "airline": "VietJet Air",
                                   "departure": "21:45", "unitPrice": 700_000}]}
OUTBOUND_CHOICE = {"direction": "OUTBOUND", "date": "2999-10-10",
                   "chosen": {"productId": "o", "flightNumber": "9G886", "departure": "22:15", "unitPrice": 900_000},
                   "alternatives": []}


def turn(query, **fields):
    return {**intake_node({"query": query}), "conversation_id": "c1", "plan_consent": True,
            "intent": {**empty_intent(), "destination": "Hà Nội", "days": 3}, **fields}


class StayChangeTests(unittest.TestCase):
    def planned(self, query):
        return turn(query, previous_plan={"itinerary": {"days": []}},
                    previous_options=[option(1, "Little Charm Hostel Hà Nội", -1_491_384, -0.6),
                                      option(2, "Khách sạn Home Town Cha", -1_275_675, -0.6)])

    def test_a_bare_hotel_change_asks_with_the_ready_options_as_buttons(self):
        state = self.planned("đổi khách sạn")
        update = changes.detected(state)
        self.assertEqual((update["decision"], update["clarification_reason"]), ("missing_info", changes.CHOOSE_STAY))
        response = changes.question({**state, **update})["response"]
        self.assertIn("Phương án 1: Little Charm Hostel Hà Nội — bớt 1.491.384 ₫", response["question"])
        self.assertEqual(response["suggestions"][0], "Lấy phương án 1: Little Charm Hostel Hà Nội")
        self.assertEqual(response["suggestions"][-1], "Bạn chọn giúp mình khách sạn khác")
        # Nút đi vào luồng đổi tức thì đã có: "lấy phương án N" (`option_swap.chosen_option`).
        from src.backend.app.agents.steps.classification import picked_option
        self.assertEqual(picked_option({**state, "query": response["suggestions"][0]})["index"], 1)

    def test_a_change_with_a_direction_or_left_to_the_assistant_is_not_asked(self):
        for query in ("đổi khách sạn rẻ hơn", "đổi khách sạn gần biển hơn", "bạn chọn giúp mình khách sạn khác"):
            with self.subTest(query=query):
                self.assertIsNone(changes.detected(self.planned(query)))
        self.assertIsNone(changes.detected(turn("đổi khách sạn")))  # không có phương án sẵn: luồng cũ


class FlightChangeTests(unittest.TestCase):
    def state(self, query):
        return turn(query, previous_flights=[OUTBOUND_CHOICE, RETURN_CHOICE])

    def test_a_bare_flight_change_lists_the_other_flights_of_each_leg(self):
        state = self.state("đổi chuyến bay")
        update = changes.detected(state)
        self.assertEqual(update["clarification_reason"], changes.CHOOSE_FLIGHT)
        response = changes.question({**state, **update})["response"]
        self.assertIn("Chặng đi ngày 10/10/2999: không còn chuyến nào khác trong ngày.", response["question"])
        self.assertIn("• VU779 Vietravel Airlines, bay 20:55, 814.000 ₫/khách (đắt hơn 166.000 ₫)", response["question"])
        self.assertEqual(response["suggestions"],
                         ["Về chuyến VU779 lúc 20:55", "Về chuyến VJ167 lúc 21:45", "Đổi ngày đi"])

    def test_tapping_a_flight_button_picks_it_and_replans(self):
        update = changes.detected(self.state("Về chuyến VJ167 lúc 21:45"))
        self.assertEqual(update["decision"], "tool")
        self.assertEqual(update["constraints"]["chosen_flights"], {"RETURN": "vj"})

    def test_a_stated_wish_picks_the_matching_flight_without_asking(self):
        earlier = changes.detected(self.state("đổi chuyến về sớm hơn"))
        self.assertEqual(earlier["constraints"]["chosen_flights"], {"RETURN": "vj"})  # gần giờ cũ nhất
        anyone = changes.detected(self.state("đổi chuyến về, bạn chọn giúp mình"))
        self.assertEqual(anyone["constraints"]["chosen_flights"], {"RETURN": "vu"})

    def test_a_wish_nothing_matches_says_so_and_still_offers_the_flights(self):
        state = self.state("đổi chuyến về rẻ hơn")
        update = changes.detected(state)
        self.assertEqual(update["change_request"]["unmatched"], "cheaper")
        question = changes.question({**state, **update})["response"]["question"]
        self.assertIn("không có chuyến nào rẻ hơn chuyến đang chọn", question)
        self.assertNotIn("Chặng đi", question)

    def test_a_bare_ticket_change_is_a_flight_change_but_an_attraction_ticket_is_not(self):
        self.assertEqual(changes.detected(self.state("đổi vé"))["clarification_reason"], changes.CHOOSE_FLIGHT)
        self.assertIsNone(changes.detected(self.state("đổi vé VinWonders sang ngày khác")))

    def test_other_messages_are_not_flight_changes(self):
        for query in ("Hà Nội có gì vui?", "đổi ngày đi", "ok"):
            with self.subTest(query=query):
                self.assertIsNone(changes.detected(self.state(query)))


class ChosenFlightRuleTests(unittest.TestCase):
    def test_the_chosen_flight_wins_over_a_cheaper_one_and_over_a_round_trip(self):
        day, back = "2999-10-10", "2999-10-12"
        cheap = flight_product("VJ2", "Hà Nội", back, 600_000, parent="r-back")
        late = flight_product("VJ3", "Hà Nội", back, 950_000, parent="r-back", clock="21:00")
        out = flight_product("VJ1", "Nha Trang", day, 1_000_000, parent="r-out")
        round_trip = flight_product("RT", "Nha Trang", day, 1_500_000, parent="r-out")
        round_trip["attributes"].update({"tripType": "roundTrip", "returnDate": back})
        options = {"status": None, "outbound": [out, round_trip], "return": [cheap, late]}
        intent = {**empty_intent(), "startDate": day, "days": 3, "party": {"type": "SOLO", "adults": 1, "children": 0}}
        self.assertEqual([leg["direction"] for leg in choose_flights(options, intent)[0]], ["ROUND_TRIP"])
        legs, _ = choose_flights(options, intent, {"RETURN": "VJ3"})
        self.assertEqual([(leg["direction"], leg["product"]["productId"]) for leg in legs],
                         [("OUTBOUND", "VJ1"), ("RETURN", "VJ3")])
        choices = flight_choices(options, legs)
        self.assertEqual([alt["productId"] for alt in choices[1]["alternatives"]], ["VJ2"])


class RoundTripChangeTests(unittest.TestCase):
    def test_a_round_trip_can_be_swapped_for_another_round_trip_of_the_same_dates(self):
        # Golden TC-14 với LLM thật (10/10): lịch có vé khứ hồi thì "đổi chuyến bay" lập lại đúng vé cũ.
        day, back = "2999-10-10", "2999-10-12"

        def round_trip(pid, price, return_date=back, back_number="VJ522"):
            item = flight_product(pid, "Đà Nẵng", day, price, parent="r-out")
            item["attributes"].update({"tripType": "roundTrip", "returnDate": return_date, "flightNumber": "VJ507",
                                       "returnFlight": {"flightNumber": back_number,
                                                        "departureAt": f"{return_date}T19:30:00+07:00"}})
            return item
        # Hai vé khứ hồi chung chuyến đi VJ507, khác chuyến về: phải nêu chuyến về mới phân biệt được.
        options = {"status": None, "outbound": [round_trip("RT1", 753_000), round_trip("RT2", 900_000, back_number="VJ530"),
                                                round_trip("RT3", 600_000, "2999-10-13")], "return": []}
        intent = {**empty_intent(), "startDate": day, "days": 3, "party": {"type": "SOLO", "adults": 1, "children": 0}}
        legs, _ = choose_flights(options, intent)
        choices = flight_choices(options, legs)
        self.assertEqual((choices[0]["direction"], [a["productId"] for a in choices[0]["alternatives"]]),
                         ("ROUND_TRIP", ["RT2"]))  # RT3 về ngày khác: không phải lựa chọn
        state = turn("đổi chuyến bay", previous_flights=choices)
        question = changes.question({**state, **changes.detected(state)})["response"]
        self.assertIn("• VJ507 / VJ530 VietJet Air, đi 08:00, về 19:30, 900.000 ₫/khách (đắt hơn 147.000 ₫)",
                      question["question"])
        self.assertIn("Khứ hồi VJ507 / VJ530", question["suggestions"])
        self.assertIsNone(changes._picked_by_number("khu hoi vj507", choices))  # thiếu chuyến về: chưa chọn được
        picked = changes.detected(turn("Khứ hồi VJ507 / VJ530", previous_flights=choices))
        self.assertEqual(picked["constraints"]["chosen_flights"], {"ROUND_TRIP": "RT2"})
        legs, _ = choose_flights(options, intent, picked["constraints"]["chosen_flights"])
        self.assertEqual([leg["product"]["productId"] for leg in legs], ["RT2"])


class DuplicateFlightProductTests(unittest.TestCase):
    def test_another_product_of_the_same_flight_is_not_an_alternative(self):
        # Golden TC-14 với LLM thật (10/10): VJ507/VJ522 giá 753.000 ₫ và một sản phẩm khác cùng VJ507/VJ522 giá 1.995.000 ₫.
        day, back = "2999-10-10", "2999-10-12"

        def round_trip(pid, price):
            item = flight_product(pid, "Đà Nẵng", day, price, parent="r-out")
            item["attributes"].update({"tripType": "roundTrip", "returnDate": back, "flightNumber": "VJ507",
                                       "returnFlight": {"flightNumber": "VJ522", "departureAt": f"{back}T19:30:00+07:00"}})
            return item
        options = {"status": None, "outbound": [round_trip("A", 753_000), round_trip("B", 1_995_000)], "return": []}
        intent = {**empty_intent(), "startDate": day, "days": 3, "party": {"type": "SOLO", "adults": 1, "children": 0}}
        legs, _ = choose_flights(options, intent)
        choices = flight_choices(options, legs)
        self.assertEqual(choices[0]["alternatives"], [])
        state = turn("đổi chuyến bay", previous_flights=choices)
        question = changes.question({**state, **changes.detected(state)})["response"]
        self.assertIn("Ngày bay này không còn chuyến nào khác", question["question"])
        self.assertEqual(question["suggestions"], ["Đổi ngày đi"])


class TwoReturnFlights(FlightClients):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.flights.append(flight_product("VJ3", "Hà Nội", "2999-10-12", 950_000, parent="r-back", clock="21:00"))


class FlightChangeFlowTests(unittest.IsolatedAsyncioTestCase):
    run_graph = runtime.RuntimeTests.run_graph

    async def test_change_flight_then_tap_another_flight_replans_with_it(self):
        store, clients = InMemoryConversationStore(), TwoReturnFlights()

        def trip():
            return ScriptedLlm(extraction=extracted(destination="Nha Trang", days=3, origin="Hà Nội",
                                                    party={"type": "COUPLE", "adults": 2, "children": 0}))
        first = await self.run_graph(trip(), clients, store=store, owner="u")
        self.assertEqual([f["product"]["productId"] for f in first["response"]["itinerary"]["flights"]], ["VJ1", "VJ2"])
        cid = first["conversation_id"]

        llm = trip()
        asked = await self.run_graph(llm, clients, store=store, owner="u",
                                     state={"query": "đổi chuyến bay", "conversation_id": cid})
        self.assertEqual(asked["response"]["status"], "NEEDS_CLARIFICATION")
        self.assertIn("Về chuyến VJ3 lúc 21:00", asked["response"]["suggestions"])
        self.assertEqual(llm.calls, [])  # luật tất định: không gọi LLM để phân luồng hay viết câu hỏi

        picked = await self.run_graph(trip(), clients, store=store, owner="u",
                                      state={"query": "Về chuyến VJ3 lúc 21:00", "conversation_id": cid})
        self.assertEqual(picked["response"]["status"], "COMPLETED")
        self.assertEqual([f["product"]["productId"] for f in picked["response"]["itinerary"]["flights"]],
                         ["VJ1", "VJ3"])
        self.assertEqual(picked["validation_issues"], [])



class DateChipTests(unittest.TestCase):
    def test_the_form_offers_quick_start_dates_on_coming_saturdays(self):
        # Kịch bản bản 5, cảnh 8: nút chọn nhanh ngày đi dưới form; 10/10/2026 là thứ 7 nên "thứ 7 này" là 17/10.
        from unittest.mock import patch
        from src.backend.app.agents.steps import conversation
        with patch.object(conversation, "vietnam_today", return_value=date(2026, 10, 10)):
            self.assertEqual(conversation.date_suggestions({"language": "vi"}),
                             ["Thứ 7 này (17/10)", "Thứ 7 tuần sau (24/10)"])
        with patch.object(conversation, "vietnam_today", return_value=date(2026, 10, 8)):
            self.assertEqual(conversation.date_suggestions({"language": "vi"})[0], "Thứ 7 này (10/10)")


if __name__ == "__main__":
    unittest.main()
