"""docs/spec/agent/field-review.md §2.2: backend bắt đầu trả `suggestedValues`/`suggestions`."""
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
