import unittest
from src.backend.app.domain.itinerary.normalization import clean_interests, fold, match_destination, normalize_intent
from src.backend.app.domain.itinerary.planning import normalized

CATALOG = ['Hội An', 'Nha Trang', 'Phú Quốc', 'Hà Nội', 'Hạ Long', 'Đà Nẵng', 'TP. Hồ Chí Minh', 'Hà Tĩnh']


class NormalizationTests(unittest.TestCase):
    def test_fold_and_normalized_ignore_accents_case_and_punctuation(self):
        self.assertEqual(fold('  TP. Hồ  Chí Minh '), 'tp ho chi minh')
        self.assertEqual(normalized('Đà Nẵng'), normalized('da nang'))

    def test_destination_matches_catalog_names_ignoring_accents_case_and_punctuation(self):
        for text, expected in (('nha trang', 'Nha Trang'), ('DA NANG', 'Đà Nẵng'), ('tp ho chi minh', 'TP. Hồ Chí Minh'),
                               ('Hạ  Long', 'Hạ Long')):
            with self.subTest(text=text):
                self.assertEqual(match_destination(text, CATALOG), expected)

    def test_no_hardcoded_aliases_abbreviations_are_left_to_the_llm_step(self):
        for text in ('tphcm', 'sài gòn', 'pq', 'Paris', '', '  '):
            with self.subTest(text=text):
                self.assertIsNone(match_destination(text, CATALOG))

    def test_names_that_fold_to_the_same_key_are_not_guessed(self):
        self.assertIsNone(match_destination('ha noi', ['Hà Nội', 'Hả Nội']))

    def test_interests_are_trimmed_deduplicated_and_capped(self):
        self.assertEqual(clean_interests([' Biển ', 'biển', '', 'Ẩm thực']), ['Biển', 'Ẩm thực'])
        self.assertEqual(len(clean_interests([f'i{n}' for n in range(30)])), 20)

    def test_party_and_constraints_are_normalized_without_mutating_input(self):
        intent = {'party': {'type': 'FAMILY_WITH_KIDS', 'adults': 1, 'children': 0}, 'interests': []}
        constraints = {'exclude_taxonomies': ['golf', 'flight', 'golf'], 'specific_hotel': ' Vinpearl   Resort '}
        new_intent, new_constraints, changed = normalize_intent(intent, constraints)
        self.assertIsNone(new_intent['party'])
        self.assertEqual(new_constraints['party_type_hint'], 'FAMILY_WITH_KIDS')
        self.assertEqual(new_constraints['exclude_taxonomies'], ['flight', 'golf'])
        self.assertEqual(new_constraints['specific_hotel'], 'Vinpearl Resort')
        self.assertEqual(set(changed), {'party', 'exclude_taxonomies', 'specific_hotel'})
        self.assertEqual(intent['party']['children'], 0)
        self.assertNotIn('party_type_hint', constraints)

    def test_real_family_party_is_kept(self):
        intent = {'party': {'type': 'FAMILY_WITH_KIDS', 'adults': 2, 'children': 1}, 'interests': []}
        new_intent, _, changed = normalize_intent(intent, {})
        self.assertEqual(new_intent['party']['children'], 1)
        self.assertEqual(changed, [])
