"""Unit test cho bộ chấm golden (src/evaluation/agent/golden.py). Không cần LLM/Postgres/backend:
chỉ nạp dataset thật và chạy từng hàm chấm với state/response giả lập."""

import unittest
from pathlib import Path
from types import SimpleNamespace

from src.backend.app.application.itinerary.contracts import enum_values
from src.evaluation.agent.golden import (
    conversation_of, dataset_findings, expected_tool_call, gate_no_booking_claim, gate_no_tool_before_info,
    gate_schema, gate_secrets, load_dataset, schedule_findings,
)

DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "itinerary_agent_golden.yaml"

FAKE_SETTINGS = SimpleNamespace(
    openai_api_key="sk-fake-test-key-0123456789", gemini_api_key="", anthropic_api_key="", langsmith_api_key="",
)


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.cases = load_dataset(DATASET_PATH)

    def test_has_fifty_cases_with_unique_ids(self):
        self.assertEqual(len(self.cases), 50)
        self.assertEqual(len({c.id for c in self.cases}), 50)

    def test_every_case_has_fr_codes_and_turns(self):
        for case in self.cases:
            self.assertTrue(case.turns, f"{case.id}: không có turn")
            self.assertTrue(case.fr, f"{case.id}: thiếu fr")
            for code in case.fr:
                self.assertRegex(code, r"^(FR|NFR)-[A-Z]+-\d+$", f"{case.id}: mã {code!r} sai định dạng")

    def test_status_values_are_real_contract_statuses(self):
        # ItineraryResponse là oneOf không có "status" phẳng; lấy trực tiếp bốn giá trị discriminator.
        allowed_status = {"COMPLETED", "NEEDS_CLARIFICATION", "NO_RESULTS", "FALLBACK"}
        allowed_error = set(enum_values("ErrorResponse", "error", "code"))
        for case in self.cases:
            for turn in case.turns:
                for value in turn.expect.get("status", []):
                    self.assertIn(value, allowed_status, f"{case.id}: status {value!r} không có trong contract")
                if "errorCode" in turn.expect:
                    self.assertIn(turn.expect["errorCode"], allowed_error,
                                 f"{case.id}: errorCode {turn.expect['errorCode']!r} không có trong contract")

    def test_load_dataset_rejects_duplicate_ids(self, tmp_path=None):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dup.yaml"
            path.write_text(
                "- id: X-1\n  category: c\n  fr: [FR-AGT-01]\n  turns: [{message: a, expect: {}}]\n"
                "- id: X-1\n  category: c\n  fr: [FR-AGT-01]\n  turns: [{message: b, expect: {}}]\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_dataset(path)


class GateSchemaTests(unittest.TestCase):
    def test_valid_completed_response_passes(self):
        response = {
            "status": "COMPLETED", "conversationId": "c1",
            "itinerary": {"days": [{"day": 1, "slots": []}], "estimatedTotal": None,
                         "currency": "VND", "budgetStatus": "UNKNOWN"},
            "warnings": [],
        }
        self.assertEqual(gate_schema(response), [])

    def test_missing_required_field_fails(self):
        response = {"status": "COMPLETED", "conversationId": "c1"}  # thiếu itinerary, warnings
        self.assertTrue(gate_schema(response))

    def test_error_response_uses_error_schema(self):
        response = {"error": {"code": "UNSUPPORTED_DESTINATION", "message": "x",
                              "retryable": False, "requestId": "r1"}}
        self.assertEqual(gate_schema(response), [])


class GateSecretsTests(unittest.TestCase):
    def test_no_secret_passes(self):
        self.assertEqual(gate_secrets({"status": "COMPLETED"}, FAKE_SETTINGS), [])

    def test_configured_api_key_flagged(self):
        response = {"message": f"key of provider: {FAKE_SETTINGS.openai_api_key}"}
        self.assertTrue(gate_secrets(response, FAKE_SETTINGS))

    def test_generic_secret_pattern_flagged(self):
        response = {"message": "here is bearer abcdefghij1234567890"}
        self.assertTrue(gate_secrets(response, FAKE_SETTINGS))


class GateBookingClaimTests(unittest.TestCase):
    def test_no_claim_passes(self):
        self.assertEqual(gate_no_booking_claim({"message": "tôi không thể đặt giúp bạn"}), [])

    def test_past_tense_claim_flagged(self):
        self.assertTrue(gate_no_booking_claim({"message": "Đơn của bạn đã đặt thành công"}))


class GateNoToolBeforeInfoTests(unittest.TestCase):
    def test_missing_fields_with_tool_node_flagged(self):
        response = {"status": "NEEDS_CLARIFICATION", "missingFields": ["destination"]}
        events = [{"node": "intake"}, {"node": "classify"}, {"node": "tool"}]
        self.assertTrue(gate_no_tool_before_info(response, events))

    def test_missing_fields_without_tool_node_ok(self):
        response = {"status": "NEEDS_CLARIFICATION", "missingFields": ["destination"]}
        events = [{"node": "intake"}, {"node": "classify"}, {"node": "clarify"}]
        self.assertEqual(gate_no_tool_before_info(response, events), [])

    def test_constraint_clarification_without_missing_fields_ignored(self):
        response = {"status": "NEEDS_CLARIFICATION", "missingFields": []}
        events = [{"node": "tool"}]
        self.assertEqual(gate_no_tool_before_info(response, events), [])


class ConversationOfTests(unittest.TestCase):
    def test_success_response_top_level(self):
        self.assertEqual(conversation_of({"status": "COMPLETED", "conversationId": "c1"}), "c1")

    def test_resumable_error_uses_details(self):
        response = {"error": {"code": "UNSUPPORTED_DESTINATION", "details": {"conversationId": "c2"}}}
        self.assertEqual(conversation_of(response), "c2")

    def test_error_without_details(self):
        self.assertIsNone(conversation_of({"error": {"code": "VALIDATION_ERROR"}}))


class ExpectedToolCallTests(unittest.TestCase):
    def test_missing_info_expects_no_tool(self):
        self.assertFalse(expected_tool_call({"status": "NEEDS_CLARIFICATION", "missingFields": ["destination"]}))

    def test_constraint_clarification_is_unscored(self):
        self.assertIsNone(expected_tool_call({"status": "NEEDS_CLARIFICATION", "missingFields": []}))

    def test_completed_expects_tool(self):
        self.assertTrue(expected_tool_call({"status": "COMPLETED"}))

    def test_unsupported_destination_expects_tool(self):
        self.assertTrue(expected_tool_call({"error": {"code": "UNSUPPORTED_DESTINATION"}}))

    def test_validation_error_expects_no_tool(self):
        self.assertFalse(expected_tool_call({"error": {"code": "VALIDATION_ERROR"}}))


def _product(product_id, taxonomy="attraction", price=100000, duration=60):
    return {"productId": product_id, "taxonomy": taxonomy, "unitPrice": price,
            "attributes": {"durationMinutes": duration}}


class ScheduleFindingsTests(unittest.TestCase):
    def test_non_completed_status_skipped(self):
        self.assertEqual(schedule_findings({"status": "FALLBACK"}, {}), [])

    def test_day_count_mismatch_flagged(self):
        response = {"status": "COMPLETED", "intent": {"days": 3},
                    "itinerary": {"days": [{"day": 1, "slots": []}]}, "warnings": [
                        {"code": "DAY_WITHOUT_PRODUCTS"}]}
        findings = schedule_findings(response, {})
        self.assertTrue(any("khác intent.days" in f for f in findings))

    def test_empty_day_without_warning_flagged(self):
        response = {"status": "COMPLETED", "intent": {"days": 1},
                    "itinerary": {"days": [{"day": 1, "slots": []}]}, "warnings": []}
        findings = schedule_findings(response, {})
        self.assertTrue(any("DAY_WITHOUT_PRODUCTS" in f for f in findings))

    def test_too_many_activities_flagged(self):
        slots = [{"time": "MORNING", "product": _product("p1")},
                 {"time": "AFTERNOON", "product": _product("p2")},
                 {"time": "EVENING", "product": _product("p3")}]
        response = {"status": "COMPLETED", "intent": {"days": 1},
                    "itinerary": {"days": [{"day": 1, "slots": slots}]}, "warnings": []}
        findings = schedule_findings(response, {})
        self.assertTrue(any("vượt trần" in f for f in findings))

    def test_duplicate_product_id_flagged(self):
        slots = [{"time": "MORNING", "product": _product("p1")},
                 {"time": "AFTERNOON", "product": _product("p1")}]
        response = {"status": "COMPLETED", "intent": {"days": 1},
                    "itinerary": {"days": [{"day": 1, "slots": slots}]}, "warnings": []}
        findings = schedule_findings(response, {})
        self.assertTrue(any("lặp lại" in f for f in findings))

    def test_cheapest_hotel_not_selected_flagged(self):
        expensive = _product("hotel-expensive", taxonomy="hotel", price=2_000_000)
        cheap = _product("hotel-cheap", taxonomy="hotel", price=500_000)
        response = {"status": "COMPLETED", "intent": {"days": 1},
                    "itinerary": {"stay": {"product": expensive}, "days": []}, "warnings": []}
        findings = schedule_findings(response, {"hotel-expensive": expensive, "hotel-cheap": cheap})
        self.assertTrue(any("hotel rẻ nhất" in f for f in findings))

    def test_cheapest_hotel_selected_passes(self):
        cheap = _product("hotel-cheap", taxonomy="hotel", price=500_000)
        expensive = _product("hotel-expensive", taxonomy="hotel", price=2_000_000)
        response = {"status": "COMPLETED", "intent": {"days": 1},
                    "itinerary": {"stay": {"product": cheap}, "days": []}, "warnings": []}
        findings = schedule_findings(response, {"hotel-expensive": expensive, "hotel-cheap": cheap})
        self.assertFalse(any("hotel rẻ nhất" in f for f in findings))


class DatasetFindingsTests(unittest.TestCase):
    def test_intent_path_mismatch_flagged(self):
        response = {"status": "COMPLETED", "intent": {"destination": "Đà Nẵng", "days": 2,
                                                       "party": {"adults": 2, "children": 0}}}
        findings = dataset_findings(response, 200, [], {"intent": {"destination": "Huế", "party.adults": 4}}, {})
        self.assertEqual(len(findings), 2)

    def test_missing_fields_include_satisfied(self):
        response = {"status": "NEEDS_CLARIFICATION", "missingFields": ["destination", "days"]}
        findings = dataset_findings(response, 200, [], {"missingFieldsInclude": ["destination"]}, {})
        self.assertEqual(findings, [])

    def test_nodes_exclude_violation(self):
        events = [{"node": "intake"}, {"node": "classify"}, {"node": "tool"}]
        findings = dataset_findings({}, 200, events, {"nodesExclude": ["tool"]}, {})
        self.assertTrue(findings)

    def test_forbidden_text_case_insensitive(self):
        response = {"message": "Đã thêm Ritz Carlton Nha Trang vào lịch"}
        findings = dataset_findings(response, 200, [], {"forbiddenText": ["ritz carlton"]}, {})
        self.assertTrue(findings)

    def test_exclude_products_from_turn_overlap_flagged(self):
        response = {"itinerary": {"stay": {"product": {"productId": "p1"}}, "days": []}}
        previous = {1: {"stay": {"p1"}, "any": {"p1"}}}
        findings = dataset_findings(response, 200, [], {"excludeProductsFromTurn": {"turn": 1, "role": "stay"}},
                                    previous)
        self.assertTrue(findings)

    def test_exclude_products_from_turn_no_overlap_passes(self):
        response = {"itinerary": {"stay": {"product": {"productId": "p2"}}, "days": []}}
        previous = {1: {"stay": {"p1"}, "any": {"p1"}}}
        findings = dataset_findings(response, 200, [], {"excludeProductsFromTurn": {"turn": 1, "role": "stay"}},
                                    previous)
        self.assertEqual(findings, [])

    def test_http_status_and_error_code(self):
        response = {"error": {"code": "UNSUPPORTED_DESTINATION"}}
        findings = dataset_findings(response, 422, [], {"httpStatus": 422, "errorCode": "UNSUPPORTED_DESTINATION"}, {})
        self.assertEqual(findings, [])
        findings = dataset_findings(response, 422, [], {"httpStatus": 200, "errorCode": "VALIDATION_ERROR"}, {})
        self.assertEqual(len(findings), 2)


if __name__ == "__main__":
    unittest.main()
