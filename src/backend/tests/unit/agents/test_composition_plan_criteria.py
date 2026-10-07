"""`compose` nói cho người dùng tiêu chí xếp lịch theo khoảng cách (AC-AGT-04, chốt 2026-10-07)."""
import unittest

from src.backend.app.agents.steps import composition


def product(pid, lat=None, lng=None, **updates):
    attributes = {'latitude': lat, 'longitude': lng} if lat is not None else {}
    return {'productId': pid, 'name': f'Catalog {pid}', 'taxonomy': 'attraction',
            'destination': 'Phú Quốc', 'unitPrice': 100_000, 'currency': 'VND', 'available': True,
            'description': '', 'attributes': attributes, 'availableFrom': None, 'availableTo': None,
            'priceUnit': 'PER_PERSON', **updates}


def state(*products, language='vi'):
    candidates = {p['productId']: p for p in products}
    return {'conversation_id': 'c1', 'decision': 'compose', 'candidates': candidates,
            'sources': {pid: 'search' for pid in candidates}, 'warnings': [], 'constraints': {},
            'language': language,
            'intent': {'destination': 'Phú Quốc', 'startDate': None, 'days': 2,
                       'party': {'type': 'SOLO', 'adults': 1, 'children': 0}, 'budget': None,
                       'interests': [], 'pace': None}}


def criteria(result):
    return [w['message'] for w in result['response']['warnings'] if w['code'] == 'PLAN_CRITERIA']


class PlanCriteriaTests(unittest.TestCase):
    def test_a_plan_arranged_by_distance_says_so(self):
        result = composition.composed(state(product('a', 10.40, 103.95), product('b', 10.05, 103.98),
                                            product('h', 10.20, 103.96, taxonomy='hotel', priceUnit='PER_NIGHT')))
        self.assertEqual(len(criteria(result)), 1)
        self.assertIn('gần nhau', criteria(result)[0])

    def test_english_wording(self):
        result = composition.composed(state(product('a', 10.40, 103.95), language='en'))
        self.assertIn('nearby places', criteria(result)[0])

    def test_no_criteria_is_claimed_when_no_place_has_a_known_position(self):
        result = composition.composed(state(product('a'), product('b')))
        self.assertEqual(criteria(result), [])


if __name__ == '__main__':
    unittest.main()
