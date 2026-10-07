"""history/2026-09-28-ap-dung-de-xuat-field-review-agent.md: backend bắt đầu trả `suggestedValues`/`suggestions`."""
import unittest

from src.backend.app.agents.steps import composition, conversation


class NoResultsSuggestionsTests(unittest.TestCase):
    def test_generic_suggestion_when_no_constraint_is_active(self):
        self.assertEqual(composition._no_results_suggestions({'constraints': {}}),
                         [composition.messages.message({}, 'suggestion_generic')])

    def test_one_suggestion_per_active_constraint_up_to_three(self):
        state = {'constraints': {'require_hotel': True, 'hotel_price_max': 1_000_000,
                                  'star_rating_min': 4, 'specific_activity': 'lặn biển'}}
        result = composition._no_results_suggestions(state)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], composition.messages.message(state, 'suggestion_hotel'))

    def test_nearest_open_date_comes_first_then_other_catalog_destinations(self):
        state = {'constraints': {}, 'intent': {'destination': 'Hà Nội', 'days': 3, 'startDate': '2026-12-01'},
                 'nearest_open_date': '2026-10-24', 'supported_destinations': ['Hà Nội', 'Huế', 'Nha Trang', 'Đà Nẵng']}
        self.assertEqual(composition._no_results_suggestions(state),
                         ['Đi Hà Nội 3 ngày từ ngày 24/10/2026', 'Đi Huế 3 ngày', 'Đi Nha Trang 3 ngày'])

    def test_current_destination_is_never_offered_as_an_alternative(self):
        state = {'constraints': {}, 'intent': {'destination': 'huế', 'days': 2},
                 'supported_destinations': ['Huế', 'Nha Trang']}
        self.assertEqual(composition._no_results_suggestions(state), ['Đi Nha Trang 2 ngày'])

    def test_suggestions_follow_the_conversation_language(self):
        state = {'constraints': {}, 'language': 'en', 'intent': {'destination': 'Hue', 'days': 2},
                 'supported_destinations': ['Hue', 'Nha Trang']}
        self.assertEqual(composition._no_results_suggestions(state), ['A 2-day trip to Nha Trang'])

    def test_message_names_the_date_when_it_is_the_main_drop_reason(self):
        dropped = [{'code': 'PRODUCT_DROPPED_DATE'}] * 2 + [{'code': 'PRODUCT_DROPPED_UNAVAILABLE'}]
        state = {'warnings': dropped, 'intent': {'destination': 'Hà Nội', 'days': 3, 'startDate': '2026-12-01'}}
        self.assertEqual(composition._no_results_message(state),
                         '**Chưa có sản phẩm mở bán cho ngày này**\n'
                         'Hiện chưa có sản phẩm ở Hà Nội mở bán cho ngày 01/12/2026. '
                         'Bạn có thể chọn một trong các gợi ý bên dưới.')

    def test_message_stays_generic_for_any_other_reason(self):
        state = {'warnings': [{'code': 'PRODUCT_DROPPED_UNAVAILABLE'}],
                 'intent': {'destination': 'Hà Nội', 'days': 3, 'startDate': '2026-12-01'}}
        self.assertEqual(composition._no_results_message(state), composition.messages.message(state, 'no_results'))
        self.assertEqual(composition._no_results_message({'intent': {}}), composition.messages.message({}, 'no_results'))

    def test_retrieval_outcome_attaches_suggestions_to_no_results(self):
        state = {'decision': 'no_results', 'conversation_id': 'c1', 'intent': {'destination': 'Huế'},
                 'constraints': {'specific_hotel': 'Vinpearl'}}
        response = composition.retrieval_outcome(state)['response']
        self.assertEqual(response['status'], 'NO_RESULTS')
        self.assertEqual(response['suggestions'], [composition.messages.message(state, 'suggestion_hotel')])


class SuggestedValuesTests(unittest.TestCase):
    base = {'conversation_id': 'c1', 'intent': {'destination': None, 'days': None}}

    def test_destination_and_days_suggested_when_both_missing_and_catalog_known(self):
        state = {**self.base, 'missing_fields': ['destination', 'days'],
                 'supported_destinations': ['Nha Trang', 'Phú Quốc']}
        response = conversation._question_response(state, 'question')['response']
        self.assertEqual(response['suggestedValues'],
                         {'destination': ['Nha Trang', 'Phú Quốc'], 'days': list(range(1, 8))})

    def test_destination_suggestion_absent_before_the_catalog_has_been_fetched(self):
        state = {**self.base, 'missing_fields': ['destination']}
        response = conversation._question_response(state, 'question')['response']
        self.assertNotIn('destination', response.get('suggestedValues', {}))

    def test_no_suggested_values_outside_a_missing_destination_or_days(self):
        state = {**self.base, 'missing_fields': ['startDate']}
        self.assertNotIn('suggestedValues', conversation._question_response(state, 'question')['response'])


if __name__ == '__main__':
    unittest.main()
