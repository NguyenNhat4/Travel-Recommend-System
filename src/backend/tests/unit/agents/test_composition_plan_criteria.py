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
        self.assertIn('tổng quãng đường', criteria(result)[0])

    def test_english_wording(self):
        result = composition.composed(state(product('a', 10.40, 103.95), language='en'))
        self.assertIn('total travel', criteria(result)[0])

    def test_a_hotel_change_is_explained_with_the_night_and_both_hotels(self):
        north = [product(f'n{i}', 10.40, 103.90 + i * 0.005) for i in range(4)]
        south = [product(f's{i}', 10.04, 103.90 + i * 0.005) for i in range(4)]
        hotels = [product('h-north', 10.405, 103.905, taxonomy='hotel', priceUnit='PER_NIGHT', unitPrice=1_000_000),
                  product('h-south', 10.035, 103.905, taxonomy='hotel', priceUnit='PER_NIGHT', unitPrice=1_000_000)]
        current = state(*north, *south, *hotels)
        current['intent']['days'] = 5
        result = composition.composed(current)
        stays = result['response']['itinerary']['stays']
        self.assertEqual(len(stays), 2)
        self.assertIn(f"từ đêm {stays[1]['fromNight']}", criteria(result)[0])
        self.assertIn('Catalog h-north', criteria(result)[0])
        self.assertIn('Catalog h-south', criteria(result)[0])

    def test_no_criteria_is_claimed_when_no_place_has_a_known_position(self):
        result = composition.composed(state(product('a'), product('b')))
        self.assertEqual(criteria(result), [])


def options_text(result):
    return [w['message'] for w in result['response']['warnings'] if w['code'] == 'STAY_OPTIONS']


def square_trip(budget=None, language='vi'):
    """4 điểm trong 1 km quanh khách sạn gần (3 triệu/đêm); khách sạn rẻ (500k/đêm) cách khoảng 8 km. 3 ngày, 2 đêm,
    1 khách: lịch ở khách sạn gần 6.400.000 ₫, ở khách sạn rẻ 1.400.000 ₫."""
    places = [product(pid, lat, lng) for pid, lat, lng in
              (('a', 10.200, 103.960), ('b', 10.209, 103.960), ('c', 10.200, 103.969), ('d', 10.209, 103.969))]
    hotels = [product('h-close', 10.2045, 103.9645, taxonomy='hotel', priceUnit='PER_NIGHT', unitPrice=3_000_000),
              product('h-far', 10.2600, 104.0100, taxonomy='hotel', priceUnit='PER_NIGHT', unitPrice=500_000)]
    current = state(*places, *hotels, language=language)
    current['intent'].update(days=3, budget=budget)
    return current


class StayOptionsTests(unittest.TestCase):
    """Chọn theo ngân sách và mục "Phương án khác" (AC-AGT-04, chốt 2026-10-08)."""

    def test_without_a_budget_the_cheaper_hotel_is_offered_with_the_extra_travel(self):
        result = composition.composed(square_trip())
        self.assertEqual(result['response']['itinerary']['stay']['product']['productId'], 'h-close')
        [text] = options_text(result)
        self.assertTrue(text.startswith('Lịch trên: đi lại khoảng '))
        self.assertIn('• Phương án 1: bớt 5.000.000 ₫ — ở Catalog h-far: đi thêm khoảng ', text)
        self.assertNotIn('vượt ngân sách', text)
        self.assertTrue(text.endswith('Bấm một thẻ khách sạn để đổi ngay, hoặc nhắn "lấy phương án 1".'))
        [option] = result['stay_options']
        self.assertEqual((option['index'], option['stays'][0]['productId']), (1, 'h-far'))

    def test_a_tight_budget_takes_the_hotel_that_fits_and_offers_the_closer_one_over_budget(self):
        result = composition.composed(square_trip(budget=3_000_000))
        self.assertEqual(result['response']['itinerary']['stay']['product']['productId'], 'h-far')
        self.assertEqual(result['response']['itinerary']['budgetStatus'], 'WITHIN_BUDGET')
        self.assertIn('ngân sách của bạn', criteria(result)[0])
        [text] = options_text(result)
        self.assertIn('• Phương án 1: thêm 5.000.000 ₫ — ở Catalog h-close: bớt khoảng ', text)
        self.assertIn(' km đi lại (vượt ngân sách 3.400.000 ₫).\n', text)

    def test_english_wording(self):
        [text] = options_text(composition.composed(square_trip(budget=3_000_000, language='en')))
        self.assertIn('• Option 1: 5,000,000 VND more — stay at Catalog h-close: about ', text)
        self.assertIn('(3,400,000 VND over budget)', text)

    def test_no_section_when_there_is_no_other_hotel(self):
        current = square_trip()
        del current['candidates']['h-far']
        result = composition.composed(current)
        self.assertEqual(options_text(result), [])
        self.assertEqual(result['stay_options'], [])


if __name__ == '__main__':
    unittest.main()
