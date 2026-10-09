"""Unit test cho bộ chấm golden (src/evaluation/agent/golden.py). Không cần LLM/Postgres/backend:
chỉ nạp dataset thật và chạy từng hàm chấm với state/response giả lập."""

import json
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from src.backend.app.application.itinerary.contracts import enum_values
from src.evaluation.agent.golden import (
    Case, Turn, conversation_of, dataset_findings, expected_tool_call, gate_no_booking_claim,
    gate_no_tool_before_info, gate_schema, gate_secrets, judge_findings, load_dataset, progress_writer,
    TurnResult, build_report, render_markdown, resolve_dates, run_case, schedule_findings,
)

DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "agent_test_cases_nhat.yaml"

FAKE_SETTINGS = SimpleNamespace(
    openai_api_key="sk-fake-test-key-0123456789", gemini_api_key="", anthropic_api_key="", langsmith_api_key="",
)


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.cases = load_dataset(DATASET_PATH)

    def test_case_ids_are_unique(self):
        self.assertEqual(len({c.id for c in self.cases}), len(self.cases))

    def test_every_date_placeholder_in_the_dataset_resolves(self):
        today = date(2026, 10, 2)
        for case in self.cases:
            for turn in case.turns:
                resolved = json.dumps([resolve_dates(turn.message, today), resolve_dates(turn.expect, today)],
                                      ensure_ascii=False)
                self.assertNotIn("{today", resolved, f"{case.id}: placeholder ngày không được thay")

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

    def test_load_dataset_rejects_unknown_expect_key(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "typo.yaml"
            path.write_text("- id: X-1\n  category: c\n  fr: [FR-AGT-01]\n"
                            "  turns: [{message: a, expect: {missingField: [days]}}]\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missingField"):
                load_dataset(path)

    def test_turn_language_and_conversation_id_are_loaded(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "turn.yaml"
            path.write_text("- id: X-1\n  category: c\n  fr: [FR-AGT-01]\n"
                            "  turns: [{message: a, language: en, conversationId: conv-x}]\n", encoding="utf-8")
            turn = load_dataset(path)[0].turns[0]
        self.assertEqual((turn.language, turn.conversation_id), ("en", "conv-x"))


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

    def test_title_first_line_checks_the_bold_summary_line(self):
        from src.evaluation.agent.golden import answer_text, dataset_findings, has_title_first_line
        self.assertTrue(has_title_first_line("**Bạn muốn đi đâu?**\nMình cần biết điểm đến."))
        for text in ("Bạn muốn đi đâu?", "**Chỉ tiêu đề**", "Xin chào **bạn**\nđi đâu?", "**a** và **b**\nx"):
            with self.subTest(text=text):
                self.assertFalse(has_title_first_line(text))
        self.assertEqual(answer_text({"error": {"message": "lỗi"}}), "lỗi")
        titled = {"status": "NEEDS_CLARIFICATION", "question": "**Ngoài phạm vi hỗ trợ**\nChỉ hỗ trợ du lịch."}
        self.assertEqual(dataset_findings(titled, 200, [], {"titleFirstLine": True}, {}), [])
        plain = {"status": "NEEDS_CLARIFICATION", "question": "Chào bạn!"}
        self.assertEqual(len(dataset_findings(plain, 200, [], {"titleFirstLine": True}, {})), 1)
        self.assertEqual(dataset_findings(plain, 200, [], {"titleFirstLine": False}, {}), [])

    def test_an_unsupported_destination_passing_through_tool_is_not_a_retrieval(self):
        from src.evaluation.agent.golden import retrieval_ran
        searched = [{"node": "tool", "metadata": {"calls": 2}}]
        rejected = [{"node": "tool", "metadata": {"retrieval": False}}]
        self.assertTrue(retrieval_ran(searched))
        self.assertFalse(retrieval_ran(rejected))
        self.assertFalse(retrieval_ran([{"node": "extract", "metadata": {}}]))


def _product(product_id, taxonomy="attraction", price=100000, duration=60):
    return {"productId": product_id, "taxonomy": taxonomy, "unitPrice": price, "available": True,
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

    def test_two_products_with_the_same_name_are_flagged(self):
        # Trace 08/10/2026: hai vé Water Taxi khác mã, cùng tên (AC-AGT-04, node `filter`).
        name = "[Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi)"
        slots = [{"time": "MORNING", "product": {**_product("e35d"), "name": name}},
                 {"time": "AFTERNOON", "product": {**_product("f540"), "name": name.upper()}}]
        response = {"status": "COMPLETED", "intent": {"days": 1},
                    "itinerary": {"days": [{"day": 1, "slots": slots}]}, "warnings": []}
        self.assertTrue(any("tên" in f and "lặp lại" in f for f in schedule_findings(response, {})))

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

    def test_a_searched_hotel_beats_a_cheaper_recommended_one(self):
        # compose_plan xếp Search trước Recommendation rồi mới tới giá.
        searched = _product("hotel-searched", taxonomy="hotel", price=2_000_000)
        recommended = _product("hotel-recommended", taxonomy="hotel", price=500_000)
        response = {"status": "COMPLETED", "intent": {"days": 1},
                    "itinerary": {"stay": {"product": searched}, "days": []}, "warnings": []}
        findings = schedule_findings(response, {"hotel-searched": searched, "hotel-recommended": recommended},
                                     {"hotel-searched": "search", "hotel-recommended": "recommendation"})
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


def _itinerary_response(activity_count, stay=True, warnings=()):
    slots = [{"time": "MORNING", "product": {"productId": f"a{i}"}} for i in range(activity_count)]
    itinerary = {"days": [{"day": 1, "slots": slots}]}
    if stay:
        itinerary["stay"] = {"product": {"productId": "h1"}}
    return {"status": "COMPLETED", "itinerary": itinerary, "warnings": [{"code": c} for c in warnings]}


class NewExpectKeyTests(unittest.TestCase):
    def test_min_activities(self):
        self.assertTrue(dataset_findings(_itinerary_response(1), 200, [], {"minActivities": 3}, {}))
        self.assertEqual(dataset_findings(_itinerary_response(3), 200, [], {"minActivities": 3}, {}), [])

    def test_has_stay(self):
        self.assertTrue(dataset_findings(_itinerary_response(1), 200, [], {"hasStay": False}, {}))
        self.assertEqual(dataset_findings(_itinerary_response(1, stay=False), 200, [], {"hasStay": False}, {}), [])

    def test_warnings_exclude(self):
        response = _itinerary_response(1, warnings=["SNAPSHOT_ONLY", "PRODUCT_DROPPED_EXCLUDED"])
        self.assertTrue(dataset_findings(response, 200, [], {"warningsExclude": ["PRODUCT_DROPPED_EXCLUDED"]}, {}))
        self.assertEqual(dataset_findings(response, 200, [], {"warningsExclude": ["PRODUCT_DROPPED_DATE"]}, {}), [])

    def test_tools_include_checks_the_final_tool_plan(self):
        expect = {"toolsInclude": ["get_similar_products"]}
        response = _itinerary_response(1)
        findings = dataset_findings(response, 200, [], expect, {}, {"search_products"})
        self.assertEqual(len(findings), 1)
        self.assertIn("get_similar_products", findings[0])
        self.assertTrue(dataset_findings(response, 200, [], expect, {}))  # lượt không có tool plan
        self.assertEqual(dataset_findings(response, 200, [], expect, {},
                                          {"get_similar_products", "search_products"}), [])


if __name__ == "__main__":
    unittest.main()


class ResolveDatesTests(unittest.TestCase):
    today = date(2026, 9, 25)

    def test_message_uses_vietnamese_date_and_expect_uses_iso(self):
        self.assertEqual(resolve_dates("đi Huế, khởi hành {today+7}", self.today), "đi Huế, khởi hành 02/10/2026")
        self.assertEqual(resolve_dates("{today+7:iso}", self.today), "2026-10-02")

    def test_offset_is_optional_and_may_be_negative(self):
        self.assertEqual(resolve_dates("{today}", self.today), "25/09/2026")
        self.assertEqual(resolve_dates("{today-1:iso}", self.today), "2026-09-24")

    def test_rolls_over_month_and_year(self):
        self.assertEqual(resolve_dates("{today+10}", date(2026, 12, 25)), "04/01/2027")

    def test_nested_expect_values_are_resolved_and_other_values_are_untouched(self):
        expect = {"intent": {"destination": "Huế", "days": 3, "startDate": "{today+1:iso}"},
                  "status": ["COMPLETED"], "toolCalled": True}
        self.assertEqual(resolve_dates(expect, self.today), {
            "intent": {"destination": "Huế", "days": 3, "startDate": "2026-09-26"},
            "status": ["COMPLETED"], "toolCalled": True})

    def test_text_that_is_not_a_placeholder_is_left_alone(self):
        self.assertEqual(resolve_dates("giá {100} và {today+x}", self.today), "giá {100} và {today+x}")

    def test_day_month_formats_typed_by_real_users(self):
        self.assertEqual(resolve_dates("Ngày {today+19:vi}", self.today), "Ngày 14 tháng 10")
        self.assertEqual(resolve_dates("ngày {today+20:dm}, 2 người lớn", self.today), "ngày 15/10, 2 người lớn")


AGENT_CASES_PATH = DATASET_PATH


def _form_response(question, default, suggested=("Đà Nẵng", "Nha Trang", "Phú Quốc"), form=True):
    response = {"status": "NEEDS_CLARIFICATION", "question": question, "missingFields": ["destination"],
                "suggestedValues": {"destination": list(suggested)}}
    if form:
        response["clarificationForm"] = {"defaults": {"destination": default}}
    return response


class FormMatchesAnswerTests(unittest.TestCase):
    expect = {"formMatchesAnswer": True}

    def test_a_suggested_destination_missing_from_the_form_fails(self):
        # TC-02: lời trả lời gợi ý Đà Nẵng nhưng form chưa chọn Đà Nẵng.
        findings = dataset_findings(_form_response("**Gợi ý**\nMình gợi ý Đà Nẵng nhé.", None), 200, [], self.expect, {})
        self.assertEqual(len(findings), 1)
        self.assertIn("Đà Nẵng", findings[0])
        self.assertTrue(dataset_findings(_form_response("Mình gợi ý Đà Nẵng nhé.", "Nha Trang"), 200, [],
                                         self.expect, {}))

    def test_a_matching_form_passes(self):
        self.assertEqual(dataset_findings(_form_response("Mình gợi ý Đà Nẵng nhé.", "Đà Nẵng"), 200, [],
                                          self.expect, {}), [])

    def test_an_answer_naming_no_destination_has_nothing_to_compare(self):
        self.assertEqual(dataset_findings(_form_response("Bạn chỉnh form bên dưới nhé.", "Đà Nẵng"), 200, [],
                                          self.expect, {}), [])

    def test_the_form_must_be_shown(self):
        findings = dataset_findings(_form_response("Đi đâu?", None, form=False), 200, [], self.expect, {})
        self.assertEqual(findings, ["không có clarificationForm"])


class AgentTestCasesDatasetTests(unittest.TestCase):
    def test_the_user_reported_cases_load_and_every_placeholder_resolves(self):
        cases = load_dataset(AGENT_CASES_PATH)
        self.assertEqual([case.id for case in cases], ["TC-01", "TC-02", "TC-03", "TC-04", "TC-10", "TC-11"])
        for case in cases:
            for turn in case.turns:
                resolved = json.dumps([resolve_dates(turn.message, date(2026, 10, 2)),
                                       resolve_dates(turn.expect, date(2026, 10, 2))], ensure_ascii=False)
                self.assertNotIn("{today", resolved, f"{case.id}: placeholder chưa được thay")
        tc01 = resolve_dates(cases[0].turns[2].message, date(2026, 10, 2))
        self.assertEqual(tc01, "Ngày 14 tháng 10")


class _ScriptedJudge:
    """LLM giả: trả kết luận cố định, ghi lại prompt đã nhận."""

    def __init__(self, verdicts=None, error=None):
        self.verdicts, self.error, self.prompts = verdicts or [], error, []

    def with_structured_output(self, schema):
        judge = self

        class _Runnable:
            async def ainvoke(self, messages, config=None):
                judge.prompts.append(messages)
                if judge.error:
                    raise judge.error
                return schema(verdicts=judge.verdicts)
        return _Runnable()


class JudgeFindingsTests(unittest.IsolatedAsyncioTestCase):
    response = {"status": "COMPLETED", "message": "**Hà Nội 1 ngày**\nMình đổi ngày đi sang 14/10.",
                "intent": {"destination": "Hà Nội", "startDate": "2026-10-14"}}

    async def test_only_failed_criteria_become_findings_with_the_judge_reason(self):
        judge = _ScriptedJudge([{"passed": True, "reason": "có nói ngày"}, {"passed": False, "reason": "không có lịch"}])
        findings = await judge_findings(judge, [{"user": "Đổi ngày"}], "Ngày 14 tháng 10", self.response,
                                        ["Ghi nhận ngày", "Trình bày lịch trình"], 5)
        self.assertEqual(findings, ["[judge] Trình bày lịch trình: không có lịch"])
        human = judge.prompts[0][1][1]
        self.assertIn("Mình đổi ngày đi sang 14/10.", human)
        self.assertIn("Đổi ngày", human)

    async def test_a_judge_error_or_wrong_count_never_passes_silently(self):
        failed = await judge_findings(_ScriptedJudge(error=RuntimeError("down")), [], "x", self.response, ["a"], 5)
        self.assertEqual(failed, ["[judge] không chấm được: RuntimeError"])
        short = await judge_findings(_ScriptedJudge([]), [], "x", self.response, ["a"], 5)
        self.assertEqual(short, ["[judge] trả 0 kết luận cho 1 tiêu chí"])

    def test_the_judge_key_is_accepted_by_the_loader(self):
        cases = load_dataset(AGENT_CASES_PATH)
        self.assertTrue(any(turn.expect.get("judge") for case in cases for turn in case.turns))


class ReportSlugTests(unittest.TestCase):
    def test_each_dataset_writes_its_own_report(self):
        from src.evaluation.agent.golden import DEFAULT_DATASET, report_slug
        self.assertEqual(report_slug(DEFAULT_DATASET), "agent-test-cases")
        self.assertEqual(report_slug("x/my_cases.yaml"), "my-cases")


class DroppedReportTests(unittest.TestCase):
    """Mục "Đã loại" của biên bản: mã node `filter` bỏ vì trùng (AC-AGT-04, chốt 2026-10-08)."""

    def report(self, dropped):
        result = TurnResult("TC-11", 1, "Phú Quốc 3 ngày", 200, "COMPLETED", 10, 0, True, True, [], dropped)
        settings = SimpleNamespace(itinerary_llm_model="m")
        report = build_report([result], settings, "golden", None)
        return report

    def test_dropped_products_are_listed_with_what_they_duplicate_and_who_dropped_them(self):
        report = self.report([{"productId": "fdb01f88-87d1", "name": "Cáp Treo Hòn Thơm", "duplicateOf": "76da210a-c70c",
                               "duplicateOfName": "Sun World Hòn Thơm", "by": "llm"}])
        self.assertEqual(report["turns"][0]["dropped"][0]["by"], "llm")
        markdown = render_markdown(report, "abc")
        self.assertIn("## Đã loại", markdown)
        self.assertIn("| TC-11 | 1 | Cáp Treo Hòn Thơm (`fdb01f88`) | Sun World Hòn Thơm (`76da210a`) | llm |", markdown)

    def test_no_dropped_product_says_so(self):
        markdown = render_markdown(self.report([]), "abc")
        self.assertIn("## Đã loại", markdown)
        self.assertIn("Không có.", markdown.split("## Đã loại")[1])


class _StubPlanner:
    """Graph giả: mỗi lượt trả câu hỏi lại; lượt có câu "chậm" thì treo để runner gặp timeout."""

    async def ainvoke(self, inputs, config=None):
        import asyncio
        if inputs["query"] == "chậm":
            await asyncio.sleep(1)
        return {"http_status": 200, "events": [], "candidates": {}, "response": {
            "status": "NEEDS_CLARIFICATION", "conversationId": "5f0c8a52-0b7e-4b5e-9d55-8d5b1f8e2a10",
            "question": "Bạn đi ngày nào?", "missingFields": ["startDate"], "knownIntent": {
                "destination": "Hà Nội", "startDate": None, "days": None, "party": None, "budget": None,
                "interests": [], "pace": None}}}


class ProgressEventTests(unittest.IsolatedAsyncioTestCase):
    """Event tiến độ mà eval_app.py đọc (qua --progress-file)."""

    async def test_each_turn_reports_start_then_result_and_the_case_closes(self):
        events = []
        case = Case(id="X-1", category="c", fr=["FR-AGT-01"],
                    turns=[Turn("Đi Hà Nội", {"status": ["NEEDS_CLARIFICATION"]}), Turn("2 ngày", {"status": ["COMPLETED"]})])
        await run_case(case, _StubPlanner(), None, FAKE_SETTINGS, 5, on_event=events.append, repetition=2)
        self.assertEqual([e["event"] for e in events], ["turn_start", "turn_done", "turn_start", "turn_done", "case_done"])
        first, second = events[1], events[3]
        self.assertTrue(first["passed"])
        self.assertEqual(first["reply"], "Bạn đi ngày nào?")
        self.assertEqual(first["intent"]["destination"], "Hà Nội")
        self.assertEqual((first["turn"], first["turns"], first["repetition"]), (1, 2, 2))
        self.assertFalse(second["passed"])
        self.assertTrue(any("status=" in f for f in second["findings"]))
        self.assertEqual(events[-1], {"event": "case_done", "caseId": "X-1", "repetition": 2, "turns": 2,
                                      "turnsRun": 2, "passed": False})

    async def test_a_timeout_reports_the_turn_and_the_skipped_rest(self):
        events = []
        case = Case(id="X-2", category="c", fr=["FR-AGT-01"], turns=[Turn("chậm"), Turn("không chạy tới")])
        await run_case(case, _StubPlanner(), None, FAKE_SETTINGS, 0.05, on_event=events.append)
        self.assertEqual([e["event"] for e in events], ["turn_start", "turn_done", "case_done"])
        self.assertEqual(events[1]["status"], "TIMEOUT")
        self.assertEqual((events[2]["turns"], events[2]["turnsRun"]), (2, 1))

    def test_progress_writer_appends_one_json_line_per_event(self):
        import tempfile
        self.assertIsNone(progress_writer(None))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run" / "progress.jsonl"
            write = progress_writer(path)
            write({"event": "start", "turns": 3})
            write({"event": "done", "exitCode": 0})
            lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([line["event"] for line in lines], ["start", "done"])
        self.assertIn("at", lines[0])
