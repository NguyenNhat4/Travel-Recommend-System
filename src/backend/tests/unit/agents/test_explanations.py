"""Câu nêu lý do khi điều kiện bắt buộc không có sản phẩm, hoặc lịch trình không có chỗ ở (`drop_summary`)."""
import unittest

from src.backend.app.agents.steps import conversation, explanations, messages

HANOI = {'destination': 'Hà Nội', 'days': 3, 'startDate': '2026-10-02'}
DATE_DROP = {'count': 10, 'reason': 'PRODUCT_DROPPED_DATE', 'openFrom': '2026-10-15', 'openTo': '2026-10-16',
             'nearestOpenDate': '2026-10-15'}


def state(drop=None, constraints=None, intent=None, **extra):
    return {'conversation_id': 'c1', 'intent': intent or HANOI, 'candidates': {},
            'constraints': {'require_hotel': True} if constraints is None else constraints,
            'drop_summary': {'hotel': drop} if drop is not None else {}, **extra}


class ConstraintQuestionTests(unittest.TestCase):
    def test_hotels_outside_the_trip_dates_name_the_window_and_the_nearest_date(self):
        # Trace nhat-10-1 "không có hotel à": 10 khách sạn Hà Nội đều chỉ mở bán 15–16/10.
        response = conversation.constraint_clarification(state(DATE_DROP))['response']
        self.assertEqual(response['question'],
                         '**Khách sạn ở Hà Nội chưa mở bán cho ngày đi**\n'
                         'Mình tìm thấy 10 khách sạn ở Hà Nội, nhưng dữ liệu hiện chỉ nhận đặt trong khoảng '
                         '15/10/2026–16/10/2026, không khớp chuyến của bạn từ 02/10/2026 đến 04/10/2026. '
                         'Bạn muốn dời ngày khởi hành sang 15/10/2026, hay giữ ngày và lập lịch không kèm khách sạn?')
        self.assertEqual(response['suggestions'],
                         ['Đổi ngày khởi hành sang 15/10/2026', 'Đi Hà Nội 3 ngày, không cần khách sạn'])

    def test_no_nearest_date_asks_to_plan_without_a_hotel_or_go_elsewhere(self):
        question, suggestions = explanations.constraint_question(state({**DATE_DROP, 'nearestOpenDate': None}))
        self.assertTrue(question.endswith('Bạn muốn lập lịch không kèm khách sạn, hay chọn điểm đến khác?'))
        self.assertEqual(suggestions, ['Đi Hà Nội 3 ngày, không cần khách sạn'])

    def test_price_limit_names_the_users_maximum(self):
        drop = {'count': 4, 'reason': 'PRODUCT_DROPPED_PRICE_BASIS', 'openFrom': None, 'openTo': None,
                'nearestOpenDate': None}
        question, suggestions = explanations.constraint_question(
            state(drop, constraints={'require_hotel': True, 'hotel_price_max': 1200000}))
        self.assertTrue(question.startswith('**Chưa có khách sạn trong mức giá bạn đặt**\n'))
        self.assertIn('mức tối đa 1.200.000 ₫', question)
        self.assertEqual(suggestions[0], messages.message({}, 'suggestion_price'))

    def test_named_hotel_that_is_not_in_the_data_is_quoted(self):
        drop = {'count': 6, 'reason': 'PRODUCT_DROPPED_NAMED_REQUIREMENT', 'openFrom': None, 'openTo': None,
                'nearestOpenDate': None}
        question, _ = explanations.constraint_question(state(drop, constraints={'specific_hotel': 'Sofitel Metropole'}))
        self.assertTrue(question.startswith('**Chưa tìm thấy "Sofitel Metropole"**\n'))

    def test_a_search_that_found_nothing_says_so(self):
        drop = {'count': 0, 'reason': None, 'openFrom': None, 'openTo': None, 'nearestOpenDate': None}
        question, _ = explanations.constraint_question(state(drop))
        self.assertEqual(question, '**Chưa có khách sạn ở Hà Nội**\nMình chưa tìm thấy khách sạn nào ở Hà Nội trong '
                                   'dữ liệu hiện có. Bạn muốn lập lịch không kèm khách sạn, hay chọn điểm đến khác?')

    def test_specific_activity_uses_the_slot_taxonomy_with_the_most_drops(self):
        drop = {'count': 3, 'reason': 'PRODUCT_DROPPED_NAMED_REQUIREMENT', 'openFrom': None, 'openTo': None,
                'nearestOpenDate': None}
        current = state(constraints={'specific_activity': 'Lặn biển'})
        current['drop_summary'] = {'attraction': drop, 'golf': {**drop, 'count': 1}}
        question, suggestions = explanations.constraint_question(current)
        self.assertIn('Mình tìm thấy 3 điểm tham quan ở Hà Nội, nhưng không có "Lặn biển"', question)
        self.assertEqual(suggestions, [messages.message({}, 'suggestion_activity')])

    def test_unknown_reason_keeps_the_generic_question_without_chips(self):
        response = conversation.constraint_clarification(state())['response']
        self.assertEqual(response['question'], messages.CLARIFY_CONSTRAINT)
        self.assertNotIn('suggestions', response)

    def test_english_conversation_gets_english_reason(self):
        question, suggestions = explanations.constraint_question(state(DATE_DROP, language='en'))
        self.assertTrue(question.startswith('**Hotels in Hà Nội are not on sale for your dates**\n'))
        self.assertEqual(suggestions[-1], 'A 3-day trip to Hà Nội without a hotel')


class MissingStayNoteTests(unittest.TestCase):
    def test_plan_without_stay_explains_the_dates(self):
        note = explanations.missing_stay_note(state(DATE_DROP, constraints={}), {'days': []})
        self.assertEqual(note, 'Khách sạn ở Hà Nội trong dữ liệu hiện chỉ nhận đặt từ 15/10/2026 đến 16/10/2026, nên '
                               'lịch này chưa kèm chỗ ở cho chuyến từ 02/10/2026. Muốn có khách sạn, bạn có thể dời '
                               'ngày khởi hành sang 15/10/2026.')

    def test_no_note_when_there_is_a_stay_a_single_day_or_no_hotel_was_sought(self):
        self.assertIsNone(explanations.missing_stay_note(state(DATE_DROP), {'stay': {'product': {'productId': 'h'}}}))
        self.assertIsNone(explanations.missing_stay_note(state(DATE_DROP, intent={**HANOI, 'days': 1}), {}))
        self.assertIsNone(explanations.missing_stay_note(state(), {}))


if __name__ == '__main__':
    unittest.main()
