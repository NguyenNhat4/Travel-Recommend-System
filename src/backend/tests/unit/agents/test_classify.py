import unittest
from src.backend.app.agents.nodes import _classify_result, intake_node
from src.backend.app.agents.models import Extraction


class ClassifyRouteTests(unittest.TestCase):
    def test_scope_precedes_missing_information(self):
        state = intake_node({'query': 'request'})
        result = _classify_result(state, Extraction(domain='side_effect'))
        self.assertEqual(result['route'], 'simple')
        self.assertTrue(result['refusal'])

    def test_missing_information_precedes_product_retrieval(self):
        state = intake_node({'query': 'request'})
        result = _classify_result(state, Extraction(domain='travel', patch={'days': 3}))
        self.assertEqual(result['route'], 'missing_info')
        self.assertEqual(result['missing_fields'], ['destination'])

    def test_complete_intent_uses_tools_without_keyword_override(self):
        state = intake_node({'query': 'timeout search status'})
        result = _classify_result(state, Extraction(domain='travel', patch={'destination': 'Nha Trang', 'days': 3}))
        self.assertEqual(result['route'], 'tool')

    def test_clear_constraints_and_explicit_false_are_preserved(self):
        state = intake_node({'query': 'request', 'constraints': {'specific_hotel': 'old', 'hotel_attributes': {'oceanView': True}}})
        result = _classify_result(state, Extraction(domain='travel', patch={'destination': 'Nha Trang', 'days': 2},
                                constraints={'clear_fields': ['specific_hotel'], 'hotel_attributes': {'oceanView': False}}))
        self.assertNotIn('specific_hotel', result['constraints'])
        self.assertFalse(result['constraints']['hotel_attributes']['oceanView'])

    def test_unknown_party_type_remains_null_when_counts_are_explicit(self):
        result = _classify_result(intake_node({'query': 'request'}), Extraction(domain='travel',
                  patch={'destination': 'Nha Trang', 'days': 2, 'party': {'type': None, 'adults': 4, 'children': 0}}))
        self.assertEqual(result['route'], 'tool')
        self.assertIsNone(result['intent']['party']['type'])

    def test_exclude_products_keeps_only_ids_from_previous_selection(self):
        state = intake_node({'query': 'request', 'previous_selection': [{'productId': 'shown-1', 'name': 'Vinpearl', 'taxonomy': 'attraction'}]})
        result = _classify_result(state, Extraction(domain='travel', patch={'destination': 'Nha Trang', 'days': 2},
                  constraints={'exclude_products': ['shown-1', 'invented-id']}))
        self.assertEqual(result['constraints']['exclude_products'], ['shown-1'])

    def test_exclude_products_accumulates_across_turns(self):
        state = intake_node({'query': 'request', 'constraints': {'exclude_products': ['old-1']},
                             'previous_selection': [{'productId': 'old-1', 'name': 'A', 'taxonomy': 'attraction'},
                                                    {'productId': 'new-1', 'name': 'B', 'taxonomy': 'attraction'}]})
        result = _classify_result(state, Extraction(domain='travel', patch={'destination': 'Nha Trang', 'days': 2},
                  constraints={'exclude_products': ['new-1']}))
        self.assertEqual(sorted(result['constraints']['exclude_products']), ['new-1', 'old-1'])
