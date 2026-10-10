"""Đoàn đông ở nhiều phòng (AC-AGT-04, chốt 2026-10-09): tiền khách sạn × số phòng, thiếu `priceAdults` thì cảnh báo."""
import unittest

from src.backend.app.agents.steps import composition


def hotel(pid='h', **attributes):
    return {'productId': pid, 'name': f'Catalog {pid}', 'taxonomy': 'hotel',
            'destination': 'Phú Quốc', 'unitPrice': 1_000_000, 'currency': 'VND', 'available': True,
            'description': '', 'attributes': attributes, 'availableFrom': None, 'availableTo': None,
            'priceUnit': 'PER_NIGHT'}


def state(candidates, adults=10):
    return {'conversation_id': 'c1', 'decision': 'compose', 'candidates': candidates,
            'sources': {pid: 'search' for pid in candidates}, 'warnings': [], 'constraints': {},
            'intent': {'destination': 'Phú Quốc', 'startDate': None, 'days': 3,
                       'party': {'type': 'FRIENDS', 'adults': adults, 'children': 0}, 'budget': None,
                       'interests': [], 'pace': None}}


class StayRoomsCompositionTests(unittest.TestCase):
    def test_ten_adults_pay_for_five_rooms(self):
        result = composition.composed(state({'h': hotel(priceAdults=2)}))
        itinerary = result['response']['itinerary']
        self.assertEqual(itinerary['stays'][0]['rooms'], 5)
        self.assertEqual(itinerary['estimatedTotal'], 1_000_000 * 2 * 5)
        codes = [warning['code'] for warning in result['response']['warnings']]
        self.assertNotIn('STAY_ROOMS_UNKNOWN', codes)

    def test_a_hotel_without_price_adults_is_one_room_with_a_warning(self):
        result = composition.composed(state({'h': hotel()}))
        self.assertEqual(result['response']['itinerary']['stays'][0]['rooms'], 1)
        warnings = [w for w in result['response']['warnings'] if w['code'] == 'STAY_ROOMS_UNKNOWN']
        self.assertEqual([w['productId'] for w in warnings], ['h'])


if __name__ == '__main__':
    unittest.main()
