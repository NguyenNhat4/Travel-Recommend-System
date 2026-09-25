import json
import unittest
from src.backend.app.agents.steps.classification import extract_result, route_input, route_result
from src.backend.app.agents.nodes import intake_node
from src.backend.app.agents.models import Extraction, TurnRoute


class RouteTests(unittest.TestCase):
    """`classify` chỉ phân luồng: du lịch → extract; trò chuyện và ngoài phạm vi → converse."""

    def test_travel_goes_to_extract_without_touching_intent(self):
        state = intake_node({'query': 'request'})
        result = route_result(state, TurnRoute(route='travel'))
        self.assertEqual(result['route'], 'travel')
        self.assertFalse(result['refusal'])
        self.assertNotIn('intent', result)

    def test_out_of_scope_is_a_refusal_through_converse(self):
        result = route_result(intake_node({'query': 'request'}), TurnRoute(route='out_of_scope'))
        self.assertEqual(result['route'], 'simple')
        self.assertTrue(result['refusal'])

    def test_conversation_is_not_a_refusal_and_knows_what_the_trip_lacks(self):
        state = {**intake_node({'query': 'cảm ơn'}), 'intent': {'destination': 'Huế', 'days': None}}
        result = route_result(state, TurnRoute(route='conversation'))
        self.assertEqual(result['route'], 'simple')
        self.assertFalse(result['refusal'])
        self.assertEqual(result['missing_fields'], ['days'])

    def test_classify_sees_the_whole_conversation_context(self):
        state = {**intake_node({'query': 'chưa chốt ngày đi'}),
                 'conversation_history': [{'role': 'user', 'content': 'Huế 2 ngày'},
                                          {'role': 'assistant', 'content': 'Bạn dự định khởi hành ngày nào?'}],
                 'intent': {'destination': 'Huế', 'days': 2},
                 'previous_selection': [{'productId': 'p1', 'name': 'A', 'taxonomy': 'hotel'}]}
        payload = json.loads(route_input(state)[1][1])
        self.assertEqual(payload['last_assistant_message'], 'Bạn dự định khởi hành ngày nào?')
        self.assertEqual(payload['known_intent']['destination'], 'Huế')
        self.assertEqual(len(payload['conversation_history']), 2)
        self.assertEqual(payload['previous_selection'][0]['productId'], 'p1')


class ClassifyRouteTests(unittest.TestCase):
    def test_missing_information_precedes_product_retrieval(self):
        state = intake_node({'query': 'request'})
        result = extract_result(state, Extraction(start_date_undecided=True, patch={'budget': 5000000, 'party': {'type': 'SOLO', 'adults': 1, 'children': 0}} | {'days': 3}))
        self.assertEqual(result['route'], 'missing_info')
        self.assertEqual(result['missing_fields'], ['destination'])

    def test_complete_intent_uses_tools_without_keyword_override(self):
        state = intake_node({'query': 'timeout search status'})
        result = extract_result(state, Extraction(start_date_undecided=True, patch={'budget': 5000000, 'party': {'type': 'SOLO', 'adults': 1, 'children': 0}} | {'destination': 'Nha Trang', 'days': 3}))
        self.assertEqual(result['route'], 'tool')

    def test_clear_constraints_and_explicit_false_are_preserved(self):
        state = intake_node({'query': 'request', 'constraints': {'specific_hotel': 'old', 'hotel_attributes': {'oceanView': True}}})
        result = extract_result(state, Extraction(start_date_undecided=True, patch={'budget': 5000000, 'party': {'type': 'SOLO', 'adults': 1, 'children': 0}} | {'destination': 'Nha Trang', 'days': 2},
                                constraints={'clear_fields': ['specific_hotel'], 'hotel_attributes': {'oceanView': False}}))
        self.assertNotIn('specific_hotel', result['constraints'])
        self.assertFalse(result['constraints']['hotel_attributes']['oceanView'])

    def test_unknown_party_type_remains_null_when_counts_are_explicit(self):
        result = extract_result(intake_node({'query': 'request'}), Extraction(start_date_undecided=True,
                  patch={'destination': 'Nha Trang', 'days': 2, 'budget': 5000000,
                         'party': {'type': None, 'adults': 4, 'children': 0}}))
        self.assertEqual(result['route'], 'tool')
        self.assertIsNone(result['intent']['party']['type'])

    def test_exclude_products_keeps_only_ids_from_previous_selection(self):
        state = intake_node({'query': 'request', 'previous_selection': [{'productId': 'shown-1', 'name': 'Vinpearl', 'taxonomy': 'attraction'}]})
        result = extract_result(state, Extraction(start_date_undecided=True, patch={'budget': 5000000, 'party': {'type': 'SOLO', 'adults': 1, 'children': 0}} | {'destination': 'Nha Trang', 'days': 2},
                  constraints={'exclude_products': ['shown-1', 'invented-id']}))
        self.assertEqual(result['constraints']['exclude_products'], ['shown-1'])

    def test_exclude_products_accumulates_across_turns(self):
        state = intake_node({'query': 'request', 'constraints': {'exclude_products': ['old-1']},
                             'previous_selection': [{'productId': 'old-1', 'name': 'A', 'taxonomy': 'attraction'},
                                                    {'productId': 'new-1', 'name': 'B', 'taxonomy': 'attraction'}]})
        result = extract_result(state, Extraction(start_date_undecided=True, patch={'budget': 5000000, 'party': {'type': 'SOLO', 'adults': 1, 'children': 0}} | {'destination': 'Nha Trang', 'days': 2},
                  constraints={'exclude_products': ['new-1']}))
        self.assertEqual(sorted(result['constraints']['exclude_products']), ['new-1', 'old-1'])


class StartDateQuestionTests(unittest.TestCase):
    """Ngày đi, số người, ngân sách: hỏi gộp một câu, một lần, chỉ trước lần lập lịch đầu tiên."""

    trip = {'destination': 'Nha Trang', 'days': 2}
    complete = {'startDate': '2026-10-10', 'budget': 5_000_000, 'party': {'type': 'COUPLE', 'adults': 2, 'children': 0}}

    def classify(self, state=None, **fields):
        state = state or intake_node({'query': 'request'})
        patch = {**self.trip, **fields.pop('patch', {})}
        return extract_result(state, Extraction(patch=patch, **fields))

    def test_asks_every_missing_detail_in_one_question(self):
        result = self.classify()
        self.assertEqual(result['route'], 'missing_info')
        self.assertEqual(result['missing_fields'], ['startDate', 'party', 'budget'])
        self.assertTrue(result['start_date_asked'])

    def test_asks_only_what_is_still_missing(self):
        result = self.classify(patch={'startDate': '2026-10-10', 'party': self.complete['party']})
        self.assertEqual(result['missing_fields'], ['budget'])

    def test_does_not_ask_again_after_it_has_asked(self):
        state = intake_node({'query': 'request', 'start_date_asked': True})
        result = self.classify(state)
        self.assertEqual(result['route'], 'tool')
        self.assertIsNone(result['intent']['startDate'])
        self.assertIsNone(result['intent']['budget'])

    def test_complete_details_need_no_question_and_close_the_question_for_later_turns(self):
        result = self.classify(patch=self.complete)
        self.assertEqual(result['route'], 'tool')
        self.assertTrue(result['start_date_asked'])

    def test_an_undecided_date_is_not_counted_as_missing(self):
        result = self.classify(start_date_undecided=True, patch={'budget': 5_000_000, 'party': self.complete['party']})
        self.assertEqual(result['route'], 'tool')

    def test_missing_destination_or_days_come_before_the_details(self):
        result = self.classify(patch={'destination': None})
        self.assertEqual(result['route'], 'missing_info')
        self.assertEqual(result['missing_fields'], ['destination'])
        self.assertFalse(result['start_date_asked'])

    def test_a_chip_override_is_not_asked_for_details(self):
        state = {**intake_node({'query': ''}), 'intent_override': {'days': 3}}
        result = self.classify(state)
        self.assertEqual(result['route'], 'tool')


class VietnamTodayTests(unittest.TestCase):
    """Mốc `today` của LLM là ngày ở Việt Nam, không phụ thuộc múi giờ máy chạy backend."""

    def test_early_morning_in_vietnam_is_already_the_next_utc_date(self):
        from datetime import datetime, timezone
        from src.backend.app.agents.steps.classification import vietnam_today
        # 20:00 UTC ngày 24/09 = 03:00 sáng ngày 25/09 ở Việt Nam.
        self.assertEqual(vietnam_today(datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)).isoformat(), '2026-09-25')
        # 16:59 UTC = 23:59 cùng ngày ở Việt Nam.
        self.assertEqual(vietnam_today(datetime(2026, 9, 24, 16, 59, tzinfo=timezone.utc)).isoformat(), '2026-09-24')

    def test_extraction_input_carries_the_vietnam_date(self):
        import json
        from unittest.mock import patch
        from datetime import date
        from src.backend.app.agents.steps import classification
        with patch.object(classification, 'vietnam_today', return_value=date(2026, 9, 25)):
            payload = json.loads(classification.extraction_input({'query': 'đi Huế ngày mai'})[1][1])
        self.assertEqual(payload['today'], '2026-09-25')


class DefaultYearTests(unittest.TestCase):
    """Năm mặc định là năm hiện tại: LLM hay trích "20/9" thành 2023-09-20 (lỗi báo ngày 25/09/2026)."""

    def extract(self, start, end_date=None, state=None):
        from unittest.mock import patch
        from datetime import date
        from src.backend.app.agents.steps import classification
        state = state or intake_node({'query': 'request', 'start_date_asked': True})
        result = Extraction(patch={'destination': 'Hà Nội', 'days': 2, 'startDate': start}, end_date=end_date)
        with patch.object(classification, 'vietnam_today', return_value=date(2026, 9, 25)):
            return extract_result(state, result)

    def test_a_stale_year_from_the_model_becomes_the_current_year(self):
        for stale, fixed in (('2023-09-20', '2026-09-20'), ('2023-10-05', '2026-10-05'), ('2025-12-31', '2026-12-31')):
            with self.subTest(stale=stale):
                result = self.extract(stale)
                self.assertEqual(result['route'], 'tool')
                self.assertEqual(result['intent']['startDate'], fixed)

    def test_current_and_future_years_are_kept(self):
        self.assertEqual(self.extract('2026-09-25')['intent']['startDate'], '2026-09-25')
        self.assertEqual(self.extract('2027-01-02')['intent']['startDate'], '2027-01-02')

    def test_a_leap_day_falls_back_to_the_28th_in_a_common_year(self):
        self.assertEqual(self.extract('2024-02-29')['intent']['startDate'], '2026-02-28')

    def test_the_end_date_gets_the_same_year_fix(self):
        from datetime import date
        from unittest.mock import patch
        from src.backend.app.agents.steps import classification
        state = intake_node({'query': 'request', 'start_date_asked': True})
        result = Extraction(patch={'destination': 'Hà Nội', 'startDate': '2023-10-05'}, end_date='2023-10-07')
        with patch.object(classification, 'vietnam_today', return_value=date(2026, 9, 25)):
            update = extract_result(state, result)
        self.assertEqual(update['intent']['startDate'], '2026-10-05')
        self.assertEqual(update['intent']['days'], 3)

    def test_a_date_saved_in_an_earlier_turn_is_not_rewritten(self):
        from datetime import date
        from unittest.mock import patch
        from src.backend.app.agents.steps import classification
        state = {**intake_node({'query': 'request', 'start_date_asked': True}),
                 'intent': {'destination': 'Hà Nội', 'days': 2, 'startDate': '2025-09-01', 'party': None,
                            'budget': None, 'interests': [], 'pace': None}}
        with patch.object(classification, 'vietnam_today', return_value=date(2026, 9, 25)):
            result = extract_result(state, Extraction(patch={'days': 3}))
        self.assertEqual(result['intent']['startDate'], '2025-09-01')
