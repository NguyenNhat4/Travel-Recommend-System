"""`compose_or_fallback` acknowledges recommendation-sourced items with a dedicated warning."""
import unittest

from src.backend.app.agents.steps import composition


def product(pid, **updates):
    return {'productId': pid, 'name': f'Catalog {pid}', 'taxonomy': 'hotel',
            'destination': 'Nha Trang', 'unitPrice': 1_000_000, 'currency': 'VND', 'available': True,
            'description': '', 'attributes': {}, 'availableFrom': None, 'availableTo': None,
            'priceUnit': 'PER_NIGHT', **updates}


def state(candidates, sources):
    return {'conversation_id': 'c1', 'decision': 'compose', 'candidates': candidates, 'sources': sources,
            'warnings': [], 'constraints': {},
            'intent': {'destination': 'Nha Trang', 'startDate': None, 'days': 1,
                       'party': {'type': 'SOLO', 'adults': 1, 'children': 0}, 'budget': None,
                       'interests': [], 'pace': None}}


class RecommendationWarningTests(unittest.TestCase):
    def test_no_warning_when_every_item_comes_from_search(self):
        candidates = {'h': product('h')}
        result = composition.composed(state(candidates, {'h': 'search'}))
        codes = [warning['code'] for warning in result['response']['warnings']]
        self.assertNotIn('RECOMMENDATION_FALLBACK', codes)

    def test_warning_appears_when_the_stay_is_a_recommendation_fallback(self):
        candidates = {'h': product('h')}
        result = composition.composed(state(candidates, {'h': 'recommendation'}))
        codes = [warning['code'] for warning in result['response']['warnings']]
        self.assertIn('RECOMMENDATION_FALLBACK', codes)


if __name__ == '__main__':
    unittest.main()
