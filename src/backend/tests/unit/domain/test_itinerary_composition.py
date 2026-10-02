"""The itinerary layout is decided by rules alone, so the rules themselves need coverage."""
import unittest

from src.backend.app.domain.itinerary.planning import (compose_plan, free_to_visit, render_proposal, summary, totals,
                                                       validate_plan)


def product(pid, **updates):
    return {'productId': pid, 'name': f'Catalog {pid}', 'taxonomy': 'attraction',
            'destination': 'Nha Trang', 'unitPrice': 100000, 'currency': 'VND', 'available': True,
            'description': '', 'attributes': {}, 'availableFrom': None, 'availableTo': None,
            'priceUnit': 'PER_PERSON', **updates}


def catalog(*products):
    return {p['productId']: p for p in products}


def sources_for(candidates, **overrides):
    """All-'search' sources map by default; `overrides` sets specific productIds to another source."""
    return {pid: overrides.get(pid, 'search') for pid in candidates}


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
        self.assertEqual(compose_plan(candidates, sources_for(candidates), intent())['stay_id'], 'cheap_five')

    def test_a_stay_without_a_price_is_used_only_when_nothing_priced_exists(self):
        priced = product('priced', taxonomy='hotel', unitPrice=9_000_000)
        unpriced = product('unpriced', taxonomy='hotel', unitPrice=None)
        self.assertEqual(compose_plan(catalog(priced, unpriced), sources_for(catalog(priced, unpriced)), intent())['stay_id'], 'priced')
        self.assertEqual(compose_plan(catalog(unpriced), sources_for(catalog(unpriced)), intent())['stay_id'], 'unpriced')

    def test_an_unavailable_product_is_never_proposed(self):
        candidates = catalog(product('gone', available=False), product('ok'))
        proposal = compose_plan(candidates, sources_for(candidates), intent())
        self.assertEqual([slot['product_id'] for slot in proposal['slots']], ['ok'])

    def test_a_room_and_its_parent_property_are_never_both_selected(self):
        candidates = catalog(
            product('property', taxonomy='hotel', unitPrice=2_000_000),
            product('room', taxonomy='hotel', unitPrice=1_000_000, attributes={'parentProductId': 'property'}),
            product('sibling', taxonomy='hotel', unitPrice=1_500_000, attributes={'parentProductId': 'property'}),
        )
        proposal = compose_plan(candidates, sources_for(candidates), intent())
        self.assertEqual(proposal['stay_id'], 'room')
        self.assertEqual(proposal['slots'], [])

    def test_activities_spread_across_days_before_doubling_up(self):
        candidates = catalog(product('a'), product('b'))
        proposal = compose_plan(candidates, sources_for(candidates), intent(days=2))
        self.assertEqual([(s['day'], s['time']) for s in proposal['slots']],
                         [(1, 'MORNING'), (2, 'MORNING')])

    def test_a_second_activity_on_a_day_moves_to_the_afternoon(self):
        candidates = catalog(product('a'), product('b'), product('c'))
        proposal = compose_plan(candidates, sources_for(candidates), intent(days=1))
        self.assertEqual([(s['day'], s['time']) for s in proposal['slots']],
                         [(1, 'MORNING'), (1, 'AFTERNOON')])

    def test_a_full_day_visit_takes_a_day_alone_and_is_placed_first(self):
        candidates = catalog(product('short'), product('long', attributes={'durationMinutes': 480}))
        proposal = compose_plan(candidates, sources_for(candidates), intent(days=2))
        self.assertEqual([(s['day'], s['time'], s['product_id']) for s in proposal['slots']],
                         [(1, 'MORNING', 'long'), (2, 'MORNING', 'short')])

    def test_activities_beyond_the_trip_capacity_are_left_out_rather_than_squeezed_in(self):
        candidates = catalog(*(product(f'p{index}') for index in range(6)))
        proposal = compose_plan(candidates, sources_for(candidates), intent(days=1))
        self.assertEqual(len(proposal['slots']), 2)

    def test_the_same_candidates_always_produce_the_same_proposal(self):
        products = [product('a'), product('b', unitPrice=50_000), product('h', taxonomy='hotel')]
        forward = compose_plan(catalog(*products), sources_for(catalog(*products)), intent())
        backward = compose_plan(catalog(*reversed(products)), sources_for(catalog(*reversed(products))), intent())
        self.assertEqual(forward, backward)

    def test_a_trip_without_a_duration_is_rejected_instead_of_guessed(self):
        with self.assertRaises(ValueError):
            compose_plan(catalog(product('a')), sources_for(catalog(product('a'))), intent(days=None))

    def test_a_search_stay_wins_over_a_cheaper_recommended_one(self):
        candidates = catalog(
            product('recommended', taxonomy='hotel', unitPrice=500_000),
            product('searched', taxonomy='hotel', unitPrice=2_000_000),
        )
        sources = sources_for(candidates, recommended='recommendation')
        self.assertEqual(compose_plan(candidates, sources, intent())['stay_id'], 'searched')

    def test_a_recommended_stay_is_used_only_when_search_has_no_candidate(self):
        candidates = catalog(product('recommended', taxonomy='hotel', unitPrice=500_000))
        sources = sources_for(candidates, recommended='recommendation')
        self.assertEqual(compose_plan(candidates, sources, intent())['stay_id'], 'recommended')

    def test_a_search_activity_wins_over_a_cheaper_recommended_one(self):
        candidates = catalog(
            product('recommended', unitPrice=10_000),
            product('searched', unitPrice=200_000),
        )
        sources = sources_for(candidates, recommended='recommendation')
        proposal = compose_plan(candidates, sources, intent(days=1))
        self.assertEqual([slot['product_id'] for slot in proposal['slots']], ['searched', 'recommended'])

    def test_the_proposal_always_survives_the_renderer_and_the_validator(self):
        candidates = catalog(
            product('h', taxonomy='hotel', unitPrice=1_000_000, priceUnit='PER_NIGHT'),
            product('room', taxonomy='hotel', unitPrice=800_000, attributes={'parentProductId': 'h'}),
            product('long', attributes={'durationMinutes': 480}), product('a'), product('g', taxonomy='golf'),
        )
        trip = intent(days=3)
        sources = {pid: 'search' for pid in candidates}
        plan = render_proposal(compose_plan(candidates, sources, trip), candidates, sources, trip)
        self.assertEqual(validate_plan(plan, candidates, sources, trip, {'require_hotel': True}), [])


class SummaryTests(unittest.TestCase):
    """docs/spec/agent/field-review.md §2.1: ProductSummary trong lịch trình bỏ `description`,
    `attributes` chỉ giữ khoá FE đọc."""

    def test_description_is_dropped(self):
        item = product('h', description='Mô tả rất dài về khách sạn.')
        self.assertNotIn('description', summary(item))

    def test_attributes_keep_only_the_fields_the_frontend_reads(self):
        item = product('h', attributes={
            'oceanView': True, 'privateBeach': True, 'pool': True, 'ticketed': True,
            'starRating': 5, 'durationMinutes': 480, 'parentProductId': 'p',
        })
        self.assertEqual(summary(item)['attributes'],
                         {'oceanView': True, 'privateBeach': True, 'pool': True, 'ticketed': True})

    def test_attributes_key_is_dropped_entirely_when_nothing_survives_the_cut(self):
        item = product('h', attributes={'starRating': 5, 'parentProductId': 'p'})
        self.assertNotIn('attributes', summary(item))

    def test_a_non_dict_product_summarizes_to_an_empty_dict(self):
        self.assertEqual(summary(None), {})


class TotalsTests(unittest.TestCase):
    """Điểm tham quan tự do tính 0 đ vào tổng; mục khác thiếu giá vẫn làm tổng null (`architecture.md` §3)."""

    def plan_of(self, *products, days=2, **intent_updates):
        candidates = catalog(*products)
        sources = sources_for(candidates)
        trip = intent(days=days, **intent_updates)
        return render_proposal(compose_plan(candidates, sources, trip), candidates, sources, trip), trip

    def test_an_unpriced_beach_counts_as_free_and_the_total_is_kept(self):
        plan, trip = self.plan_of(product('show', unitPrice=700_000),
                                  product('beach', unitPrice=None, priceUnit='UNKNOWN'),
                                  party={'type': 'COUPLE', 'adults': 2, 'children': 0}, budget=5_000_000)
        self.assertEqual(plan['estimatedTotal'], 1_400_000)
        self.assertEqual(plan['budgetStatus'], 'WITHIN_BUDGET')
        self.assertEqual(totals(plan, trip), (1_400_000, 'WITHIN_BUDGET'))

    def test_a_ticketed_false_place_counts_as_free_even_with_a_source_price(self):
        plan, _ = self.plan_of(product('park', unitPrice=50_000, attributes={'ticketed': False}))
        self.assertEqual(plan['estimatedTotal'], 0)

    def test_an_unpriced_stay_still_makes_the_total_unknown(self):
        plan, _ = self.plan_of(product('hotel', taxonomy='hotel', unitPrice=None, priceUnit='UNKNOWN'),
                               product('beach', unitPrice=None, priceUnit='UNKNOWN'))
        self.assertIsNone(plan['estimatedTotal'])
        self.assertEqual(plan['budgetStatus'], 'UNKNOWN')

    def test_free_to_visit_covers_only_attractions_and_golf(self):
        self.assertTrue(free_to_visit(product('a', unitPrice=None)))
        self.assertTrue(free_to_visit(product('g', taxonomy='golf', unitPrice=None)))
        self.assertFalse(free_to_visit(product('h', taxonomy='hotel', unitPrice=None)))
        self.assertFalse(free_to_visit(product('c', taxonomy='combo', unitPrice=None)))
        self.assertFalse(free_to_visit(product('priced')))


if __name__ == '__main__':
    unittest.main()
