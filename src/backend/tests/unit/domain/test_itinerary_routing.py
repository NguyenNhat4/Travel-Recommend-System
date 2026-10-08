"""Tối ưu tổng quãng đường của chuyến và đổi khách sạn giữa chuyến (AC-AGT-04, chốt 2026-10-07)."""
from itertools import permutations
import math
import random
import time
import unittest

from src.backend.app.domain.itinerary.geo import haversine_km
from src.backend.app.domain.itinerary.planning import compose_plan, render_proposal, validate_plan
from src.backend.app.domain.itinerary.routing import route_cost

LAT0, LNG0 = 10.0, 104.0


def at(x_km, y_km):
    """Toạ độ cách gốc x km về phía Đông, y km về phía Bắc (đủ chính xác cho vài chục km)."""
    return {'latitude': round(LAT0 + y_km / 111.195, 6),
            'longitude': round(LNG0 + x_km / (111.195 * math.cos(math.radians(LAT0))), 6)}


def place(pid, x, y, price=100_000, **attributes):
    return {'productId': pid, 'name': f'Catalog {pid}', 'taxonomy': 'attraction', 'destination': 'Phú Quốc',
            'unitPrice': price, 'currency': 'VND', 'available': True, 'description': '',
            'attributes': {**at(x, y), **attributes}, 'availableFrom': None, 'availableTo': None,
            'priceUnit': 'PER_PERSON'}


def hotel(pid, x, y, price=1_000_000, stars=3):
    return {**place(pid, x, y, price, starRating=stars), 'taxonomy': 'hotel', 'priceUnit': 'PER_NIGHT'}


def catalog(*products):
    return {p['productId']: p for p in products}


def trip(days, budget=None):
    return {'destination': 'Phú Quốc', 'startDate': None, 'days': days,
            'party': {'type': 'COUPLE', 'adults': 2, 'children': 0}, 'budget': budget,
            'interests': [], 'pace': None}


def compose(products, days, windows=None, budget=None, fixed_cost=0):
    candidates = catalog(*products)
    sources = {pid: 'search' for pid in candidates}
    return compose_plan(candidates, sources, trip(days, budget), windows, fixed_cost), candidates, sources


def point(product):
    return product['attributes']['latitude'], product['attributes']['longitude']


def visits(proposal):
    """productId theo từng ngày, theo thứ tự buổi."""
    days = {}
    for slot in proposal['slots']:
        if slot['product_id']:
            days.setdefault(slot['day'], []).append(slot['product_id'])
    return days


def cost_of(proposal, candidates, days):
    nights = []
    for stay in proposal.get('stays') or ([{'stay_id': proposal['stay_id'], 'from_night': 1,
                                             'nights': max(1, days - 1)}] if proposal['stay_id'] else []):
        nights += [point(candidates[stay['stay_id']])] * stay['nights']
    by_day = visits(proposal)
    return route_cost([[point(candidates[pid]) for pid in by_day.get(day, [])] for day in range(1, days + 1)], nights)


class RouteCostTests(unittest.TestCase):
    """Quãng đường: ngày 1 A → B → H₁; ngày d H(d−1) → A → B → H_d; ngày cuối H(n−1) → A → B."""

    def test_the_first_day_has_no_leg_in_and_the_last_day_no_leg_out(self):
        h, a, b = (10.0, 104.0), (10.0, 104.1), (10.1, 104.1)
        cost = route_cost([[a, b], [a, b]], [h])
        expected = (haversine_km(a, b) + haversine_km(b, h)) + (haversine_km(h, a) + haversine_km(a, b))
        self.assertAlmostEqual(cost, expected)

    def test_a_day_without_places_still_pays_the_hotel_change(self):
        h1, h2 = (10.0, 104.0), (10.2, 104.0)
        self.assertAlmostEqual(route_cost([[], [], []], [h1, h2]), haversine_km(h1, h2))

    def test_unknown_positions_are_skipped_not_counted(self):
        h, a = (10.0, 104.0), (10.0, 104.1)
        self.assertAlmostEqual(route_cost([[a, None], [None]], [h]), haversine_km(a, h))


class RoutingComposeTests(unittest.TestCase):
    def test_the_morning_and_afternoon_follow_the_way_to_and_from_the_hotel(self):
        # Ngày 1 kết thúc ở khách sạn: điểm gần khách sạn đi sau. Ngày cuối xuất phát từ khách sạn: điểm gần đi trước.
        proposal, _, _ = compose([hotel('h', 0, 0), place('e-near', 8, 0), place('e-far', 10, 0),
                                  place('w-near', -8, 0), place('w-far', -10, 0)], days=2)
        first, last = visits(proposal)[1], visits(proposal)[2]
        self.assertTrue(first[1].endswith('near') and first[0].endswith('far'))
        self.assertTrue(last[0].endswith('near') and last[1].endswith('far'))

    def test_two_far_clusters_on_a_five_day_trip_change_the_hotel_once(self):
        north = [place(f'n{i}', i * 0.5, 20) for i in range(4)]
        south = [place(f's{i}', i * 0.5, -20) for i in range(4)]
        hotels = [hotel('h-north', 0.7, 20.5), hotel('h-south', 0.7, -20.5), hotel('h-middle', 0.7, 0, price=500_000)]
        proposal, candidates, sources = compose(north + south + hotels, days=5)
        stays = proposal['stays']
        self.assertEqual(len(stays), 2)
        self.assertEqual({s['stay_id'] for s in stays}, {'h-north', 'h-south'})
        self.assertEqual([s['from_night'] for s in stays], [1, 1 + stays[0]['nights']])
        self.assertEqual(sum(s['nights'] for s in stays), 4)
        self.assertTrue(all(s['nights'] >= 2 for s in stays))
        changes = [s for s in proposal['slots'] if s['note_kind'] == 'CHANGE_STAY']
        self.assertEqual([s['day'] for s in changes], [stays[1]['from_night']])
        plan = render_proposal(proposal, candidates, sources, trip(5))
        self.assertEqual(validate_plan(plan, candidates, sources, trip(5), {}), [])
        self.assertEqual(plan['stay'], plan['stays'][0])

    def test_a_four_day_trip_keeps_one_hotel(self):
        north = [place(f'n{i}', i * 0.5, 20) for i in range(4)]
        south = [place(f's{i}', i * 0.5, -20) for i in range(4)]
        proposal, _, _ = compose(north + south + [hotel('h-north', 0.7, 20.5), hotel('h-south', 0.7, -20.5)], days=4)
        self.assertEqual(len(proposal['stays']), 1)

    def test_no_change_when_it_saves_less_than_the_penalty(self):
        north = [place(f'n{i}', i * 0.5, 2) for i in range(4)]
        south = [place(f's{i}', i * 0.5, -2) for i in range(4)]
        proposal, _, _ = compose(north + south + [hotel('h-north', 0.7, 2.5), hotel('h-south', 0.7, -2.5)], days=5)
        self.assertEqual(len(proposal['stays']), 1)

    def test_hotels_about_as_close_are_decided_by_price(self):
        places = [place('a', 0, 0), place('b', 1, 0), place('c', 0, 1), place('d', 1, 1)]
        proposal, _, _ = compose(places + [hotel('h-close', 0.5, 0.5, price=2_000_000),
                                           hotel('h-cheap', 0.6, 0.7, price=900_000)], days=3)
        self.assertEqual(proposal['stay_id'], 'h-cheap')

    def test_a_far_hotel_loses_even_when_much_cheaper(self):
        places = [place('a', 0, 0), place('b', 1, 0), place('c', 0, 1), place('d', 1, 1)]
        proposal, _, _ = compose(places + [hotel('h-close', 0.5, 0.5, price=2_000_000),
                                           hotel('h-far', 15, 15, price=300_000)], days=3)
        self.assertEqual(proposal['stay_id'], 'h-close')

    def test_the_result_is_the_true_minimum_on_small_trips(self):
        rng = random.Random(7)
        for _ in range(5):
            places = [place(f'p{i}', rng.uniform(-15, 15), rng.uniform(-15, 15)) for i in range(6)]
            only = hotel('h', rng.uniform(-5, 5), rng.uniform(-5, 5))
            proposal, candidates, _ = compose(places + [only], days=3)
            points = {p['productId']: point(p) for p in places}
            best = min(route_cost([[points[x] for x in order[0:2]], [points[x] for x in order[2:4]],
                                   [points[x] for x in order[4:6]]], [point(only)] * 2)
                       for order in permutations(points))
            self.assertAlmostEqual(cost_of(proposal, candidates, 3), best, places=6)

    def test_a_flight_limited_day_still_follows_the_hotel(self):
        windows = {1: {'times': ['AFTERNOON'], 'full_day': False, 'transfers': [('MORNING', 'ARRIVAL')]}}
        places = [place('near', 0.5, 0), place('far1', 12, 0), place('far2', 12.5, 0)]
        proposal, _, _ = compose(places + [hotel('h', 0, 0)], days=2, windows=windows)
        self.assertEqual(visits(proposal)[1], ['near'])

    def test_full_day_visits_stay_alone_on_unlimited_days(self):
        places = [place('long', 10, 0, durationMinutes=480), place('a', 0, 1), place('b', 0, 2), place('c', 1, 1)]
        proposal, candidates, sources = compose(places + [hotel('h', 0, 0)], days=3)
        long_day = next(day for day, ids in visits(proposal).items() if 'long' in ids)
        self.assertEqual(visits(proposal)[long_day], ['long'])
        plan = render_proposal(proposal, candidates, sources, trip(3))
        self.assertEqual(validate_plan(plan, candidates, sources, trip(3), {}), [])

    def test_the_same_candidates_give_the_same_plan_in_any_order(self):
        products = [place(f'p{i}', (i * 37) % 23 - 11, (i * 17) % 19 - 9) for i in range(9)]
        products += [hotel('h1', 0, 0), hotel('h2', 3, -2, price=800_000)]
        forward, _, _ = compose(products, days=5)
        backward, _, _ = compose(list(reversed(products)), days=5)
        self.assertEqual(forward, backward)

    def test_a_long_full_trip_stays_valid_and_fast(self):
        rng = random.Random(11)
        products = [place(f'p{i:02d}', rng.uniform(-25, 25), rng.uniform(-25, 25)) for i in range(16)]
        products += [hotel(f'h{i}', rng.uniform(-20, 20), rng.uniform(-20, 20), price=rng.randrange(5, 30) * 100_000)
                     for i in range(10)]
        started = time.perf_counter()
        proposal, candidates, sources = compose(products, days=7)
        elapsed = time.perf_counter() - started
        plan = render_proposal(proposal, candidates, sources, trip(7))
        self.assertEqual(validate_plan(plan, candidates, sources, trip(7), {}), [])
        self.assertEqual(sum(len(ids) for ids in visits(proposal).values()), 14)
        self.assertLess(elapsed, 1.0)


SQUARE = [place('a', 0, 0), place('b', 1, 0), place('c', 0, 1), place('d', 1, 1)]  # 4 điểm × 2 khách × 100k = 800k
CLOSE = hotel('h-close', 0.5, 0.5, price=3_000_000)  # 2 đêm: 6.000.000 → cả lịch 6.800.000
FAR = hotel('h-far', 8, 8, price=500_000)  # 2 đêm: 1.000.000 → cả lịch 1.800.000


class BudgetTests(unittest.TestCase):
    """Gần trước, trong ngân sách nếu có (AC-AGT-04, chốt 2026-10-08)."""

    def stay(self, budget, fixed_cost=0):
        proposal, _, _ = compose(SQUARE + [CLOSE, FAR], days=3, budget=budget, fixed_cost=fixed_cost)
        return proposal['stay_id']

    def test_without_a_budget_the_nearest_hotel_wins(self):
        self.assertEqual(self.stay(None), 'h-close')

    def test_a_wide_budget_keeps_the_nearest_hotel(self):
        self.assertEqual(self.stay(10_000_000), 'h-close')

    def test_a_tight_budget_takes_the_nearest_hotel_that_fits(self):
        self.assertEqual(self.stay(3_000_000), 'h-far')

    def test_the_flights_count_against_the_budget(self):
        self.assertEqual(self.stay(7_500_000), 'h-close')
        self.assertEqual(self.stay(7_500_000, fixed_cost=1_000_000), 'h-far')

    def test_nothing_fits_so_the_cheapest_plan_wins(self):
        self.assertEqual(self.stay(1_000_000), 'h-far')

    def test_an_unknown_flight_price_falls_back_to_the_rule_without_budget(self):
        self.assertEqual(self.stay(3_000_000, fixed_cost=None), 'h-close')


class OptionTests(unittest.TestCase):
    """Phương án khác: "thêm X ₫ → bớt Y km" và ngược lại (AC-AGT-04, chốt 2026-10-08)."""

    def test_within_a_tight_budget_the_closer_hotel_is_offered_with_how_much_it_goes_over(self):
        proposal, _, _ = compose(SQUARE + [CLOSE, FAR], days=3, budget=3_000_000)
        [option] = proposal['options']
        self.assertEqual([s['stay_id'] for s in option['stays']], ['h-close'])
        self.assertEqual(option['money_delta'], 5_000_000)
        self.assertLessEqual(option['km_delta'], -2)
        self.assertEqual(option['over_budget'], 6_800_000 - 3_000_000)
        self.assertGreater(proposal['distance_km'], 2)

    def test_without_a_budget_the_cheaper_hotel_is_offered_with_the_extra_travel(self):
        proposal, _, _ = compose(SQUARE + [CLOSE, FAR], days=3)
        [option] = proposal['options']
        self.assertEqual([s['stay_id'] for s in option['stays']], ['h-far'])
        self.assertEqual(option['money_delta'], -5_000_000)
        self.assertGreaterEqual(option['km_delta'], 2)
        self.assertIsNone(option['over_budget'])

    def test_no_option_when_the_hotels_are_about_as_close(self):
        proposal, _, _ = compose(SQUARE + [hotel('h1', 0.5, 0.5, price=2_000_000),
                                           hotel('h2', 0.6, 0.7, price=900_000)], days=3)
        self.assertEqual(proposal['options'], [])

    def test_no_option_when_a_price_is_unknown(self):
        proposal, _, _ = compose(SQUARE + [hotel('h-close', 0.5, 0.5, price=None), FAR], days=3)
        self.assertEqual(proposal['stay_id'], 'h-close')
        self.assertEqual(proposal['options'], [])

    def test_options_trade_money_for_distance_and_stay_within_the_limits(self):
        rng = random.Random(5)
        for budget in (None, 4_000_000, 8_000_000):
            places = [place(f'p{i}', rng.uniform(-6, 6), rng.uniform(-6, 6)) for i in range(6)]
            hotels = [hotel(f'h{i}', rng.uniform(-20, 20), rng.uniform(-20, 20), price=rng.randrange(3, 40) * 100_000)
                      for i in range(9)]
            proposal, _, _ = compose(places + hotels, days=3, budget=budget)
            options = proposal['options']
            self.assertLessEqual(len(options), 3)
            for option in options:
                self.assertGreaterEqual(abs(option['km_delta']), 2)
                # Gần hơn thì đắt hơn, xa hơn thì rẻ hơn: không phương án nào hơn lịch được chọn ở cả hai mặt.
                self.assertTrue((option['km_delta'] < 0) == (option['money_delta'] > 0), option)
            closer = [o['km_delta'] < 0 for o in options]
            self.assertEqual(closer, sorted(closer, reverse=True))
            self.assertLessEqual(sum(closer), 2)
            self.assertLessEqual(len(closer) - sum(closer), 2)
            ids = [tuple(s['stay_id'] for s in o['stays']) for o in options]
            self.assertNotIn((proposal['stay_id'],), ids)
            self.assertEqual(len(ids), len(set(ids)))


if __name__ == '__main__':
    unittest.main()
