"""Adversarial answer checks: fresh data, intent-specific repetition, ambiguous numbers and fare blocks."""
from copy import deepcopy
import unittest

from src.backend.app.domain.itinerary import gatekeeper as gate
from src.backend.tests.unit.agents.test_orchestrator_jobs import product


def row(number=1, products=None, refs=None, status="ok", intent="new", kind="explore", **extra):
    products = products or [product("a", "flight" if kind == "fare" else "hotel")]
    return {"job": number, "kind": kind, "intent": intent, "status": status,
            "spec": {"kind": kind, "intent": intent, "destination": "Hà Nội", "taxonomy": "hotel", "refers_to": refs or ["#1"]},
            "products": products, "listed": refs or ["#1"], "reasons": {"#1": ["cheapest"]}, **extra}


def inspect(turn, rows=None, codes=None):
    return gate.inspect(turn, rows if rows is not None else [row()], codes or {"#1": "a"})


def render(turn, rows=None, codes=None, **extra):
    return gate.render(turn, rows or [row()], codes or {"#1": "a"}, seen={"items": []}, language="vi", **extra)


class GatekeeperTests(unittest.TestCase):
    def test_requested_count_replaces_default_and_continuation_does_not_double_it(self):
        cards = [product(f"s{i}", "attraction") for i in range(12)]
        codes = {f"#{i + 1}": p["productId"] for i, p in enumerate(cards)}
        spec = {"taxonomy": "attraction", "requested_count": 10}
        rows = [row(products=cards, refs=list(codes), spec=spec),
                row(2, products=cards, refs=list(codes), spec=spec, source_job=1)]
        # Even when the model lists fewer, remaining cards must still be grounded in the current brief.
        result = render({"cards": ["#1"]}, rows, codes)
        self.assertEqual(len(result["searchResults"]["attraction"]), 10)
        self.assertFalse(result["shortfalls"])
        spec["requested_count"] = 1
        self.assertEqual(len(render({"cards": list(codes)}, rows, codes)["searchResults"]["attraction"]), 1)

    def test_requested_counts_still_obey_total_twenty_and_report_missing(self):
        cards = [product(f"s{i}", "attraction") for i in range(20)] + [product(f"h{i}") for i in range(20)]
        codes = {f"#{i + 1}": p["productId"] for i, p in enumerate(cards)}
        rows = [row(products=cards[:20], refs=list(codes)[:20], spec={"taxonomy": "attraction", "requested_count": 20}),
                row(2, products=cards[20:], refs=list(codes)[20:], spec={"taxonomy": "hotel", "requested_count": 20})]
        result = render({"cards": list(codes)}, rows, codes)
        self.assertEqual(sum(map(len, result["searchResults"].values())), 20)
        self.assertEqual(result["shortfalls"][0]["selected"], 0)
        self.assertEqual(result["shortfalls"][0]["requested"], 20)

    def test_explicit_count_keeps_fare_cards_within_the_shared_twenty_slots(self):
        cards = [product(f"s{i}", "attraction") for i in range(20)] + [product("flight", "flight")]
        codes = {f"#{i + 1}": p["productId"] for i, p in enumerate(cards)}
        rows = [row(products=cards[:20], refs=list(codes)[:20], spec={"taxonomy": "attraction", "requested_count": 20}),
                row(2, products=cards[20:], refs=["#21"], kind="fare", status="answered",
                    fare_block="[Chuyến bay](product:flight)")]
        result = render({"cards": list(codes)[:20]}, rows, codes)
        self.assertEqual(sum(map(len, result["searchResults"].values())), 20)
        self.assertEqual(len(result["searchResults"]["flight"]), 1)
        self.assertEqual(len(result["searchResults"]["attraction"]), 19)
        self.assertEqual(result["shortfalls"][0]["selected"], 19)

    def test_requested_count_cannot_include_seen_or_unlisted_products(self):
        cards = [product(f"s{i}", "attraction") for i in range(5)]
        codes = {f"#{i + 1}": p["productId"] for i, p in enumerate(cards)}
        jobs = [row(products=cards, refs=["#1", "#2", "#3"], intent="more",
                    spec={"taxonomy": "attraction", "requested_count": 10})]
        result = gate.render({"cards": list(codes)}, jobs, codes, language="vi",
                             seen={"items": [{"productId": "s0", "taxonomy": "attraction", "place": "Hà Nội"}]})
        self.assertEqual([p["productId"] for p in result["searchResults"]["attraction"]], ["s1", "s2"])
        self.assertEqual(result["shortfalls"][0]["selected"], 2)

    def test_per_job_destination_exclusion_is_checked_again_before_render(self):
        cards = [product("a", "attraction"), product("b", "attraction", "Đà Nẵng")]
        job = row(products=cards, refs=["#1", "#2"], spec={"taxonomy": "attraction",
                  "destination": None, "excluded_destinations": ["ha noi"]})
        result = render({"cards": ["#1", "#2"], "message": "[Nơi a](#1)\n[Nơi b](#2)"},
                        [job], {"#1": "a", "#2": "b"})
        self.assertEqual([p["productId"] for p in result["searchResults"]["attraction"]], ["b"])
        self.assertNotIn("product:a", result["body"])

    def test_a_fare_lookup_does_not_authorize_raw_old_hotel_price(self):
        turn = {"action": "answer", "message": "Khách sạn lúc nãy 1.200.000 ₫, [[fare_block:1]]"}
        self.assertIn("raw_product_number", inspect(turn, [row(kind="fare", status="answered")])["violations"])

    def test_raw_numbers_are_blocked_in_every_turn_including_user_supplied_budget(self):
        for text in ("20:00", "9.4 điểm", "4 sao", "120 đánh giá", "3 km", "2 triệu", "17/10/2026", "50%"):
            with self.subTest(text=text):
                self.assertTrue(inspect({"message": text})["violations"])
        self.assertFalse(inspect({"message": "Trong mức bạn muốn, [[price:#1]]"})["violations"])

    def test_code_fare_block_is_inserted_after_raw_scan(self):
        fare = row(kind="fare", status="answered", fare_block="Vé 2.000.000 ₫ lúc 08:00.")
        turn = {"action": "answer", "message": "[[fare_block:1]]"}
        self.assertFalse(inspect(turn, [fare])["violations"])
        self.assertEqual(render(turn, [fare])["body"], fare["fare_block"])

    def test_missing_card_and_link_refs_are_dropped_but_remembered_name_is_allowed(self):
        turn = {"message": "Lúc nãy mình gợi ý Nơi b. [Nơi b](#99)", "cards": ["#99"]}
        result = render(turn)
        self.assertFalse(result["searchResults"])
        self.assertNotIn("(#99)", result["body"])
        self.assertIn("Lúc nãy", result["body"])

    def test_unlisted_product_cannot_be_selected_or_used_as_placeholder(self):
        rows = [row(products=[product("a"), product("b")])]
        turn = {"message": "[[price:#2]]", "cards": ["#2"]}
        self.assertEqual(inspect(turn, rows, {"#1": "a", "#2": "b"})["unknown_refs"], ["#2"])
        self.assertFalse(render(turn, rows, {"#1": "a", "#2": "b"})["searchResults"])

    def test_same_ref_two_prices_needs_job_qualification(self):
        rows = [row(1), row(2, products=[product("a", price=2_000_000)])]
        self.assertIn("ambiguous_placeholder", inspect({"message": "[[price:#1]]"}, rows)["violations"])
        self.assertFalse(inspect({"message": "[[price:job2:#1]]"}, rows)["violations"])
        self.assertIn("2.000.000 ₫/đêm", render({"message": "[[price:job2:#1]]"}, rows)["body"])

    def test_distance_and_difference_need_exact_job_anchor(self):
        rows = [row(1, anchor_product=product("x", price=2_000_000)),
                row(2, anchor_product=product("y", attributes={"latitude": 21.035, "longitude": 105.85}))]
        self.assertIn("comparison_missing_job", inspect({"message": "[[distance:#1]]"}, rows)["violations"])
        self.assertFalse(inspect({"message": "[[distance:job2:#1]] [[price_diff:job1:#1]]"}, rows)["violations"])
        body = render({"message": "[[distance:job2:#1]] [[price_diff:job1:#1]]"}, rows)["body"]
        self.assertIn("0.6 km", body)
        self.assertIn("1.000.000 ₫", body)
        self.assertTrue(inspect({"message": "[[distance:job3:#1]]"}, rows)["violations"])
        self.assertTrue(inspect({"message": "[[distance:job1:#1]]"}, [row()])["violations"])

    def test_missing_attributes_are_omitted_without_inventing_values(self):
        turn = {"message": "[[hours:#1]] [[rating:#1]] [[reviews:#1]] [[stars:#1]]"}
        self.assertEqual(render(turn)["body"], "")
        rich = product("a", rating=4.5, reviewCount=20, attributes={"starRating": 4, "openingHours": "08:00–17:00"})
        body = render(turn, [row(products=[rich])])["body"]
        self.assertIn("4.5 điểm", body)
        self.assertIn("20 đánh giá", body)
        self.assertIn("4 sao", body)
        self.assertIn("08:00–17:00", body)

    def test_free_product_has_no_fabricated_zero_price(self):
        result = render({"message": "[[price:#1]]"}, [row(products=[product("a", "attraction", price=0)])])
        self.assertIn("tham quan tự do", result["body"])
        self.assertNotIn("0 ₫", result["body"])

    def test_scope_checks_depend_on_intent(self):
        card = product("a")
        seen = {"items": [{"productId": "a", "place": "Hà Nội", "taxonomy": "hotel"}]}
        self.assertTrue(gate.in_scope("#1", row(), card, seen, []))
        self.assertFalse(gate.in_scope("#1", row(intent="more"), card, seen, []))
        self.assertTrue(gate.in_scope("#1", row(intent="about_shown"), card, seen, []))
        self.assertFalse(gate.in_scope("#2", row(intent="about_shown"), card, seen, []))
        self.assertFalse(gate.in_scope("#1", row(), card, seen, ["#1"]))
        self.assertFalse(gate.in_scope("#1", row(), product("a", destination="Đà Nẵng"), seen, []))
        self.assertFalse(gate.in_scope("#1", row(), product("a", "attraction"), seen, []))
        self.assertTrue(gate.in_scope("#1", row(intent="cheaper", anchor_product=product("x", price=2_000_000)), card, seen, []))
        self.assertFalse(gate.in_scope("#1", row(intent="dearer", anchor_product=product("x", price=2_000_000)), card, seen, []))
        self.assertFalse(gate.in_scope("#1", row(intent="cheaper", anchor_product=product("x", price=1_000_000)), card, seen, []))
        self.assertFalse(gate.in_scope("#1", row(intent="cheaper"), card, seen, []))

    def test_card_limits_are_three_sights_and_two_hotels_or_four_for_hotel_only(self):
        cards = [product(f"h{i}") for i in range(5)] + [product(f"s{i}", "attraction") for i in range(5)]
        codes = {f"#{i + 1}": p["productId"] for i, p in enumerate(cards)}
        rows = [row(products=cards, refs=list(codes))]
        rows[0]["spec"]["taxonomy"] = None
        result = render({"cards": list(codes)}, rows, codes)
        self.assertEqual(len(result["searchResults"]["hotel"]), 2)
        self.assertEqual(len(result["searchResults"]["attraction"]), 3)
        self.assertEqual(len(render({"cards": list(codes)}, rows, codes, hotel_only=True)["searchResults"]["hotel"]), 4)
        self.assertTrue(all(f"product:{p['productId']}" in result["body"] for group in result["searchResults"].values() for p in group))

    def test_comparative_label_is_neutralized_for_wrong_product(self):
        result = render({"message": "[Nơi a](#1) có nhiều đánh giá nhất.", "cards": ["#1"]})
        self.assertNotIn("nhiều đánh giá nhất", result["body"])
        self.assertIn("rẻ nhất", render({"message": "[Nơi a](#1) rẻ nhất.", "cards": ["#1"]})["body"])

    def test_superseded_blocks_and_products_are_not_rendered(self):
        rows = [row(status="superseded", kind="fare", fare_block="Câu hỏi cũ?"),
                row(2, status="answered", kind="fare", fare_block="Đây là câu vé mới.")]
        result = render({"message": "[[fare_block:1]] [[fare_block:2]] [[fare_block:2]]"}, rows)
        self.assertNotIn("Câu hỏi cũ", result["body"])
        self.assertEqual(result["body"].count("Đây là câu vé mới"), 1)

    def test_all_independent_answers_are_inserted_even_when_model_omits_a_block(self):
        rows = [row(1, kind="fare", status="answered", fare_block="Tuyến từ Sài Gòn."),
                row(2, kind="fare", status="answered", fare_block="Tuyến từ Đà Nẵng.")]
        result = render({"message": "[[fare_block:1]]"}, rows)
        self.assertIn("Tuyến từ Sài Gòn.", result["body"])
        self.assertIn("Tuyến từ Đà Nẵng.", result["body"])

    def test_only_earliest_fare_question_survives_and_other_jobs_wait(self):
        rows = [row(2, kind="fare", status="asked", fare_block="Bạn bay đi từ đâu tới Đà Nẵng?", suggestions=["Từ Huế"]),
                row(1, kind="fare", status="asked", fare_block="Bạn bay đi từ đâu tới Hà Nội?", suggestions=["Từ Hà Nội"],
                    pending_fare={"destination": "Hà Nội"})]
        result = render({"message": "Bạn có muốn đi không?", "suggestions": ["Khách sạn"]}, rows)
        self.assertEqual(result["body"].count("?"), 1)
        self.assertNotIn("tới Đà Nẵng", result["body"])
        self.assertEqual(len(result["waiting_jobs"]), 1)
        self.assertEqual(result["suggestions"][0], "Từ Hà Nội")
        self.assertEqual(result["pending_fare"], {"destination": "Hà Nội"})

    def test_ask_requires_structured_question(self):
        self.assertIn("ask_missing_question", inspect({"action": "ask", "message": "Đi đâu?"})["violations"])
        self.assertFalse(inspect({"action": "ask", "message": "Đi đâu?", "question": {"about": "destination"}})["violations"])

    def test_raw_url_and_unknown_placeholder_are_rejected(self):
        self.assertTrue(inspect({"message": "https://example.com [[budget]]"})["violations"])

    def test_fallback_uses_current_results_and_keeps_fare_text(self):
        result = render({"message": "Giá 999 triệu", "cards": ["#1"]}, fallback=True)
        self.assertNotIn("999", result["body"])
        self.assertIn("product:a", result["body"])


class PriceUnitTests(unittest.TestCase):
    def test_price_placeholder_already_includes_its_unit(self):
        for suffix in ("/đêm", " /khách", "/night"):
            body = render({"message": "Giá [[price:#1]]" + suffix})["body"]
            self.assertEqual(body, "Giá 1.000.000 ₫/đêm")

    def test_a_hotel_without_a_positive_price_is_not_called_free_entry(self):
        body = render({"message": "[[price:#1]]"}, [row(products=[product("a", price=0)])])["body"]
        self.assertEqual(body, "")

    def test_unknown_link_labels_cannot_hide_unguarded_numbers(self):
        self.assertIn("raw_product_number", inspect({"message": "[Giá 1 triệu](#99)"})["violations"])
        for raw in ("9h30", "4.5/5", "$1,000"):
            self.assertTrue(inspect({"message": raw})["violations"])

    def test_auto_refresh_of_an_old_anchor_cannot_make_it_a_cheaper_card(self):
        rows = [row(intent="about_shown", answer_only=True)]
        turn = {"message": "[Cái 5 sao](#1) giá [[price:#1]].", "cards": ["#1"]}
        result = render(turn, rows)
        self.assertEqual(result["searchResults"], {})
        self.assertNotIn("5 sao", result["body"])
        self.assertIn("Nơi a giá 1.000.000 ₫/đêm", result["body"])
