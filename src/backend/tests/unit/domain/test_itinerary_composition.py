"""The itinerary layout is decided by rules alone, so the rules themselves need coverage."""
import unittest

from src.backend.app.domain.itinerary.planning import compose_plan, render_proposal, validate_plan


def product(pid, **updates):
    return {'productId': pid, 'name': f'Catalog {pid}', 'taxonomy': 'attraction',
            'destination': 'Nha Trang', 'unitPrice': 100000, 'currency': 'VND', 'available': True,
            'description': '', 'attributes': {}, 'availableFrom': None, 'availableTo': None,
            'priceUnit': 'PER_PERSON', **updates}


def catalog(*products):
    return {p['productId']: p for p in products}


def intent(days=2, **updates):
    return {'destination': 'Nha Trang', 'startDate': None, 'days': days,
            'party': {'type': 'SOLO', 'adults': 1, 'children': 0}, 'budget': None,
            'interests': [], 'pace': None, **updates}


class ComposePlanTests(unittest.TestCase):
    def test_the_cheapest_stay_wins_and_a_higher_rating_breaks_the_tie(self):
        candidates = catalog(
            product('expensive', taxonomy='hotel', unitPrice=3_000_000, attributes={'starRating': 5}),
            product('cheap_three', taxonomy='hotel', unitPrice=1_000_000, attributes={'starRating': 3}),
            product('cheap_five', taxonomy='hotel', unitPrice=1_000_000, attributes={'starRating': 5}),
        )
        self.assertEqual(compose_plan(candidates, intent())['stay_id'], 'cheap_five')

    def test_a_stay_without_a_price_is_used_only_when_nothing_priced_exists(self):
        priced = product('priced', taxonomy='hotel', unitPrice=9_000_000)
        unpriced = product('unpriced', taxonomy='hotel', unitPrice=None)
        self.assertEqual(compose_plan(catalog(priced, unpriced), intent())['stay_id'], 'priced')
        self.assertEqual(compose_plan(catalog(unpriced), intent())['stay_id'], 'unpriced')

    def test_an_unavailable_product_is_never_proposed(self):
        candidates = catalog(product('gone', available=False), product('ok'))
        proposal = compose_plan(candidates, intent())
        self.assertEqual([slot['product_id'] for slot in proposal['slots']], ['ok'])

    def test_a_room_and_its_parent_property_are_never_both_selected(self):
        candidates = catalog(
            product('property', taxonomy='hotel', unitPrice=2_000_000),
            product('room', taxonomy='hotel', unitPrice=1_000_000, attributes={'parentProductId': 'property'}),
            product('sibling', taxonomy='hotel', unitPrice=1_500_000, attributes={'parentProductId': 'property'}),
        )
        proposal = compose_plan(candidates, intent())
        self.assertEqual(proposal['stay_id'], 'room')
        self.assertEqual(proposal['slots'], [])

    def test_activities_spread_across_days_before_doubling_up(self):
        candidates = catalog(product('a'), product('b'))
        proposal = compose_plan(candidates, intent(days=2))
        self.assertEqual([(s['day'], s['time']) for s in proposal['slots']],
                         [(1, 'MORNING'), (2, 'MORNING')])

    def test_a_second_activity_on_a_day_moves_to_the_afternoon(self):
        candidates = catalog(product('a'), product('b'), product('c'))
        proposal = compose_plan(candidates, intent(days=1))
        self.assertEqual([(s['day'], s['time']) for s in proposal['slots']],
                         [(1, 'MORNING'), (1, 'AFTERNOON')])

    def test_a_full_day_visit_takes_a_day_alone_and_is_placed_first(self):
        candidates = catalog(product('short'), product('long', attributes={'durationMinutes': 480}))
        proposal = compose_plan(candidates, intent(days=2))
        self.assertEqual([(s['day'], s['time'], s['product_id']) for s in proposal['slots']],
                         [(1, 'MORNING', 'long'), (2, 'MORNING', 'short')])

    def test_activities_beyond_the_trip_capacity_are_left_out_rather_than_squeezed_in(self):
        candidates = catalog(*(product(f'p{index}') for index in range(6)))
        proposal = compose_plan(candidates, intent(days=1))
        self.assertEqual(len(proposal['slots']), 2)

    def test_the_same_candidates_always_produce_the_same_proposal(self):
        products = [product('a'), product('b', unitPrice=50_000), product('h', taxonomy='hotel')]
        forward = compose_plan(catalog(*products), intent())
        backward = compose_plan(catalog(*reversed(products)), intent())
        self.assertEqual(forward, backward)

    def test_a_trip_without_a_duration_is_rejected_instead_of_guessed(self):
        with self.assertRaises(ValueError):
            compose_plan(catalog(product('a')), intent(days=None))

    def test_the_proposal_always_survives_the_renderer_and_the_validator(self):
        candidates = catalog(
            product('h', taxonomy='hotel', unitPrice=1_000_000, priceUnit='PER_NIGHT'),
            product('room', taxonomy='hotel', unitPrice=800_000, attributes={'parentProductId': 'h'}),
            product('long', attributes={'durationMinutes': 480}), product('a'), product('g', taxonomy='golf'),
        )
        trip = intent(days=3)
        sources = {pid: 'search' for pid in candidates}
        plan = render_proposal(compose_plan(candidates, trip), candidates, sources, trip)
        self.assertEqual(validate_plan(plan, candidates, sources, trip, {'require_hotel': True}), [])


if __name__ == '__main__':
    unittest.main()
