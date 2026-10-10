"""Hỏi gộp số ngày cùng ngày đi, số người, ngân sách, nơi đi trong một câu (AC-AGT-01, kịch bản bản 5 cảnh 7).

Chat thử / golden 10/10: "Ok, lên lịch Hà Nội luôn" sau lượt khám phá chỉ được hỏi "Bạn muốn đi Hà Nội mấy ngày?", rồi
lượt sau mới hỏi tiếp ngày đi, số người.
"""
import unittest

from src.backend.app.agents.models import Extraction
from src.backend.app.agents.nodes import intake_node
from src.backend.app.agents.steps.classification import _extract_update
from src.backend.app.agents.steps.conversation import clarification_fallback
from src.backend.app.domain.itinerary.planning import empty_intent


def _state(query, **extra):
    return {**intake_node({'query': query}), 'intent': empty_intent(), 'conversation_id': 'c1', 'plan_consent': True,
            **extra}


class AskDaysWithDetailsTests(unittest.TestCase):
    def test_a_known_destination_without_days_asks_everything_in_one_question(self):
        update = _extract_update(_state('Ok, lên lịch Hà Nội luôn'), Extraction(patch={'destination': 'Hà Nội'}))
        self.assertEqual(update['decision'], 'missing_info')
        self.assertEqual(update['missing_fields'], ['days', 'startDate', 'party', 'budget', 'origin'])
        self.assertTrue(update['start_date_asked'])
        self.assertIsNone(update['clarification_reason'])
        question = clarification_fallback({**_state('Ok, lên lịch Hà Nội luôn'), **update})['response']['question']
        self.assertIn('Thêm vài thông tin để lập lịch', question)
        self.assertIn('mấy ngày', question)
        self.assertIn('ngày khởi hành', question)
        self.assertIn('số người lớn và trẻ em', question)

    def test_the_next_partial_answer_gets_the_form_not_another_question(self):
        first = _extract_update(_state('Ok, lên lịch Hà Nội luôn'), Extraction(patch={'destination': 'Hà Nội'}))
        state = _state('3 ngày, 2 vợ chồng với 1 bé, chưa biết ngày', intent=first['intent'],
                       start_date_asked=first['start_date_asked'], clarification_rounds=first['clarification_rounds'])
        second = _extract_update(state, Extraction(patch={'days': 3, 'party': {'type': 'FAMILY_WITH_KIDS', 'adults': 2,
                                                                                'children': 1}}))
        self.assertEqual(second['decision'], 'missing_info')
        self.assertEqual(second['clarification_reason'], 'suggest_form')
        self.assertIn('startDate', second['missing_fields'])

    def test_missing_destination_is_still_asked_first(self):
        update = _extract_update(_state('lên lịch cho mình'), Extraction(patch={}))
        self.assertEqual(update['missing_fields'], ['destination', 'days'])

    def test_details_already_asked_keep_the_old_question(self):
        update = _extract_update(_state('Hà Nội', start_date_asked=True), Extraction(patch={'destination': 'Hà Nội'}))
        self.assertEqual(update['missing_fields'], ['days'])


if __name__ == '__main__':
    unittest.main()
