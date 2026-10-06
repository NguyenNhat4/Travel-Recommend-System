"""Bộ đọc ngày tất định (`domain/itinerary/dates.py`) và lưới an toàn ngày của `extract`."""
import unittest
from datetime import date
from unittest import mock

from src.backend.app.agents.models import Extraction
from src.backend.app.agents.nodes import intake_node
from src.backend.app.agents.steps.classification import extract_result
from src.backend.app.domain.itinerary.dates import explicit_dates, this_year
from src.backend.app.domain.itinerary.planning import empty_intent

TODAY = date(2026, 10, 1)


class ExplicitDatesTests(unittest.TestCase):
    def test_reads_every_supported_form(self):
        cases = {
            'à nhầm Ngày 15 tháng 10': date(2026, 10, 15),
            'ngay 15 thang 10 nam 2027': date(2027, 10, 15),
            '15 thg 10': date(2026, 10, 15),
            'đổi sang 5/10': date(2026, 10, 5),
            '15-10': date(2026, 10, 15),
            '15.10.2026': date(2026, 10, 15),
            '15/10/26': date(2026, 10, 15),
            'bắt đầu từ ngày 2026-10-02, cho 2 người lớn, ngân sách khoảng 1 triệu': date(2026, 10, 2),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(explicit_dates(text, TODAY), [expected])

    def test_ignores_numbers_that_are_not_dates(self):
        for text in ('1410', 'đi 3-4 người', 'ngân sách 2.5 triệu', 'giá 1.000.000đ', '1/2 ngày', '32/10',
                     'tuần sau', '2 người lớn, 3 ngày'):
            with self.subTest(text=text):
                self.assertEqual(explicit_dates(text, TODAY), [])

    def test_keeps_order_and_drops_duplicates(self):
        self.assertEqual(explicit_dates('từ 14/10 đến 16/10, nhắc lại 14/10', TODAY),
                         [date(2026, 10, 14), date(2026, 10, 16)])

    def test_a_date_without_a_year_uses_the_current_year_even_if_it_has_passed(self):
        self.assertEqual(explicit_dates('20/9', TODAY), [date(2026, 9, 20)])

    def test_an_older_year_becomes_the_current_year(self):
        self.assertEqual(this_year(date(2023, 9, 20), TODAY), date(2026, 9, 20))
        self.assertEqual(this_year(date(2024, 2, 29), date(2027, 1, 1)), date(2027, 2, 28))


@mock.patch('src.backend.app.agents.steps.classification.vietnam_today', return_value=TODAY)
class DateSafetyNetTests(unittest.TestCase):
    """LLM chép lại ngày cũ hoặc bỏ sót ngày dù câu chat viết rõ: backend dùng ngày đọc được."""
    INTENT = {**empty_intent(), 'destination': 'Hà Nội', 'days': 1, 'startDate': '2026-10-14',
              'party': {'type': 'COUPLE', 'adults': 2, 'children': 0}, 'budget': 1000000}

    def planned(self, query):
        return {**intake_node({'query': query}), 'intent': dict(self.INTENT), 'start_date_asked': True,
                'previous_selection': [{'productId': 'p1', 'name': 'Tour', 'taxonomy': 'attraction'}]}

    def test_the_traced_copy_of_the_old_date_is_replaced_by_the_stated_one(self, _today):
        # Output thật của gpt-4o-mini (LangSmith, project nhat-10-1) cho "à nhầm Ngày 15 tháng 10".
        copied = {key: self.INTENT[key] for key in ('destination', 'startDate', 'days', 'party', 'budget')}
        result = extract_result(self.planned('à nhầm Ngày 15 tháng 10'),
                                Extraction(patch=copied, change_without_value=['startDate']))
        self.assertEqual(result['decision'], 'tool')
        self.assertEqual(result['intent']['startDate'], '2026-10-15')

    def test_a_date_the_model_missed_is_read_from_the_message(self, _today):
        result = extract_result(self.planned('Ngày 20 tháng 10'), Extraction(change_without_value=['startDate']))
        self.assertEqual(result['decision'], 'tool')
        self.assertEqual(result['intent']['startDate'], '2026-10-20')

    def test_the_model_date_wins_when_it_is_a_new_value(self, _today):
        result = extract_result(self.planned('đi từ 20/10 nhé'), Extraction(patch={'startDate': '2026-10-21'}))
        self.assertEqual(result['intent']['startDate'], '2026-10-21')

    def test_two_dates_are_left_to_the_model(self, _today):
        result = extract_result(self.planned('từ 15/10 đến 16/10'), Extraction(change_without_value=['startDate']))
        self.assertEqual(result['decision'], 'missing_info')

    def test_an_end_date_is_not_taken_as_the_start(self, _today):
        result = extract_result(self.planned('về ngày 16/10'), Extraction(end_date='2026-10-16'))
        self.assertEqual(result['intent']['startDate'], '2026-10-14')

    def test_no_date_in_the_message_still_asks(self, _today):
        result = extract_result(self.planned('đổi ngày'), Extraction(change_without_value=['startDate']))
        self.assertEqual(result['clarification_reason'], 'change_without_value')

    def test_a_past_stated_date_is_still_rejected(self, _today):
        result = extract_result(self.planned('đổi sang 20/9'), Extraction(change_without_value=['startDate']))
        self.assertEqual(result['clarification_reason'], 'invalid_input')
        self.assertEqual(result['invalid_inputs'][0]['reason'], 'past_date')


if __name__ == '__main__':
    unittest.main()
