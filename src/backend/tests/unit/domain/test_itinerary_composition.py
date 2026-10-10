"""The itinerary layout is decided by rules alone, so the rules themselves need coverage."""
import unittest

from src.backend.app.domain.itinerary.planning import (compose_plan, free_to_visit, render_proposal, room_guests,
                                                       stay_rooms, summary, totals, validate_plan)


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


#: Cửa sổ giờ của chuyến 3 ngày có chặng đi hạ cánh 21:05 ngày 1 và chặng về cất cánh 19:45 ngày 3 (AC-AGT-02).
LATE_ARRIVAL = {1: {'times': [], 'full_day': False, 'transfers': [('EVENING', 'ARRIVAL')]},
                3: {'times': ['MORNING', 'AFTERNOON'], 'full_day': False, 'transfers': [('EVENING', 'DEPARTURE')]}}


class FlightWindowComposeTests(unittest.TestCase):
    """Xếp lịch theo giờ bay: `compose_plan` nhận cửa sổ từ `day_windows` (AC-AGT-02, chốt 2026-10-07)."""

    def slots(self, proposal):
        return [(s['day'], s['time'], s['product_id'] or s['activity_type']) for s in proposal['slots']]

    def test_nothing_is_scheduled_before_a_late_landing_and_the_day_gets_a_transfer(self):
        candidates = catalog(product('a'), product('b'))
        proposal = compose_plan(candidates, sources_for(candidates), intent(days=3), LATE_ARRIVAL)
        self.assertEqual(self.slots(proposal), [(1, 'EVENING', 'TRANSFER'), (2, 'MORNING', 'a'), (3, 'MORNING', 'b'),
                                                (3, 'EVENING', 'TRANSFER')])
        self.assertEqual([s['note_kind'] for s in proposal['slots'] if s['product_id'] is None], ['ARRIVAL', 'DEPARTURE'])

    def test_a_full_day_visit_never_lands_on_a_limited_day(self):
        candidates = catalog(product('ba-na', attributes={'durationMinutes': 480}), product('short'))
        proposal = compose_plan(candidates, sources_for(candidates), intent(days=3), LATE_ARRIVAL)
        self.assertIn((2, 'MORNING', 'ba-na'), self.slots(proposal))
        self.assertIn((3, 'MORNING', 'short'), self.slots(proposal))

    def test_a_full_day_visit_without_a_free_day_is_left_out(self):
        windows = {1: LATE_ARRIVAL[1], 2: LATE_ARRIVAL[3]}
        candidates = catalog(product('ba-na', attributes={'durationMinutes': 480}))
        proposal = compose_plan(candidates, sources_for(candidates), intent(days=2), windows)
        self.assertEqual([s for s in proposal['slots'] if s['product_id']], [])

    def test_a_day_with_one_open_period_holds_one_activity_at_that_period(self):
        windows = {1: {'times': ['AFTERNOON'], 'full_day': False, 'transfers': [('MORNING', 'ARRIVAL')]}}
        candidates = catalog(product('a'), product('b'), product('c'))
        proposal = compose_plan(candidates, sources_for(candidates), intent(days=2), windows)
        self.assertEqual(self.slots(proposal), [(1, 'MORNING', 'TRANSFER'), (1, 'AFTERNOON', 'a'),
                                                (2, 'MORNING', 'b'), (2, 'AFTERNOON', 'c')])

    def test_the_transfer_comes_after_an_activity_of_the_same_period(self):
        windows = {1: {'times': ['MORNING', 'AFTERNOON'], 'full_day': False, 'transfers': [('AFTERNOON', 'DEPARTURE')]}}
        candidates = catalog(product('a'), product('b'))
        proposal = compose_plan(candidates, sources_for(candidates), intent(days=1), windows)
        self.assertEqual(self.slots(proposal), [(1, 'MORNING', 'a'), (1, 'AFTERNOON', 'b'), (1, 'AFTERNOON', 'TRANSFER')])

    def test_the_windowed_proposal_survives_the_renderer_and_the_validator(self):
        candidates = catalog(product('a'), product('b'), product('long', attributes={'durationMinutes': 480}))
        trip, sources = intent(days=3), sources_for(candidates)
        plan = render_proposal(compose_plan(candidates, sources, trip, LATE_ARRIVAL), candidates, sources, trip)
        transfer = plan['days'][0]['slots']
        self.assertEqual([(s['time'], s['activityType'], s['product']) for s in transfer], [('EVENING', 'TRANSFER', None)])
        self.assertEqual(validate_plan(plan, candidates, sources, trip, {}), [])


    def test_a_full_day_tour_after_a_pre_dawn_arrival_renders_instead_of_failing(self):
        # Chat thử 10/10: chuyến bay đêm hạ cánh rạng sáng ngày 2 vẫn để lại trọn ngày (`full_day`), tour cả ngày được
        # xếp sau dòng "đến nơi" và `render_proposal` từng ném "full-day overlap" (cả lịch thành FALLBACK).
        windows = {1: {'times': [], 'full_day': False, 'transfers': []},
                   2: {'times': ['MORNING', 'AFTERNOON', 'EVENING'], 'full_day': True,
                       'transfers': [('MORNING', 'ARRIVAL')]}}
        candidates = catalog(product('tour', attributes={'durationMinutes': 600}))
        trip, sources = intent(days=2), sources_for(candidates)
        plan = render_proposal(compose_plan(candidates, sources, trip, windows), candidates, sources, trip)
        day_two = [(s['activityType'], (s['product'] or {}).get('productId')) for s in plan['days'][1]['slots']]
        self.assertEqual(day_two, [('TRANSFER', None), (None, 'tour')])
        self.assertEqual(validate_plan(plan, candidates, sources, trip, {}), [])

    def test_a_full_day_tour_still_cannot_share_its_day_with_another_activity(self):
        candidates = catalog(product('tour', attributes={'durationMinutes': 600}), product('b'))
        trip, sources = intent(days=1), sources_for(candidates)
        proposal = {'stay_id': None, 'stays': [], 'slots': [
            {'day': 1, 'note_kind': 'VISIT', 'activity_type': None, 'product_id': 'b', 'time': 'MORNING'},
            {'day': 1, 'note_kind': 'VISIT', 'activity_type': None, 'product_id': 'tour', 'time': 'MORNING'}]}
        with self.assertRaises(ValueError):
            render_proposal(proposal, candidates, sources, trip)


#: Một km theo vĩ độ, đủ chính xác cho test (haversine: 1° ≈ 111,19 km).
KM = 1 / 111.19


def at(pid, km_north, km_east=0.0, **updates):
    """Sản phẩm đặt cách gốc (10.3, 103.95) — Phú Quốc — `km_north` km về Bắc và `km_east` km về Đông."""
    attributes = {'latitude': round(10.3 + km_north * KM, 6), 'longitude': round(103.95 + km_east * KM, 6),
                  **updates.pop('attributes', {})}
    return product(pid, destination='Phú Quốc', attributes=attributes, **updates)


class DistanceComposeTests(unittest.TestCase):
    """Lịch trình ít di chuyển: gom điểm gần nhau theo ngày, khách sạn gần các điểm (AC-AGT-04, chốt 2026-10-07)."""

    def trip(self, days):
        return intent(days=days, destination='Phú Quốc')

    def days_of(self, proposal):
        days = {}
        for slot in proposal['slots']:
            if slot['product_id']:
                days.setdefault(slot['day'], set()).add(slot['product_id'])
        return days

    def test_nearby_places_share_a_day_instead_of_crossing_the_island(self):
        # Theo luật cũ (giá, rồi productId, rải ngày ít việc nhất) thì ngày 1 = {a1, b1}: một Bắc một Nam, cách 40 km.
        candidates = catalog(at('a1', 40), at('a2', 41), at('b1', 0), at('b2', 1))
        proposal = compose_plan(candidates, sources_for(candidates), self.trip(2))
        self.assertEqual(sorted(self.days_of(proposal).values(), key=sorted), [{'a1', 'a2'}, {'b1', 'b2'}])
        self.assertEqual(proposal['criteria'], 'DISTANCE')

    def test_a_far_place_is_left_out_before_a_nearby_one_even_when_cheaper(self):
        candidates = catalog(at('near1', 0, unitPrice=200_000), at('near2', 0.5, unitPrice=200_000),
                             at('far', 40, unitPrice=10_000))
        proposal = compose_plan(candidates, sources_for(candidates), self.trip(1))
        self.assertEqual(self.days_of(proposal), {1: {'near1', 'near2'}})

    def test_within_two_km_the_cheaper_place_wins_over_the_closer_one(self):
        # Một buổi trống: chỉ một hoạt động. Mốc ở km 0; `cheap` cách 1,5 km (cùng mức), `far` cách 5 km.
        window = {1: {'times': ['AFTERNOON'], 'full_day': False, 'transfers': [('MORNING', 'ARRIVAL')]}}
        candidates = catalog(at('m1', 0, unitPrice=400_000), at('m2', 0, unitPrice=400_000),
                             at('pricey', 0, unitPrice=300_000), at('cheap', 1.5, unitPrice=100_000),
                             at('far', 5, unitPrice=10_000))
        proposal = compose_plan(candidates, sources_for(candidates), self.trip(1), window)
        self.assertEqual(self.days_of(proposal), {1: {'cheap'}})

    def test_the_stay_is_the_one_near_the_places_not_the_cheapest(self):
        candidates = catalog(at('a1', 40), at('a2', 41),
                             at('near', 40.5, 0.5, taxonomy='hotel', unitPrice=1_500_000),
                             at('cheap_far', 10, taxonomy='hotel', unitPrice=500_000))
        self.assertEqual(compose_plan(candidates, sources_for(candidates), self.trip(1))['stay_id'], 'near')

    def test_among_equally_near_stays_the_cheapest_wins(self):
        candidates = catalog(at('a1', 0), at('a2', 1),
                             at('pricey', 0.5, taxonomy='hotel', unitPrice=2_000_000),
                             at('cheap', 1.0, 0.5, taxonomy='hotel', unitPrice=900_000))
        self.assertEqual(compose_plan(candidates, sources_for(candidates), self.trip(1))['stay_id'], 'cheap')

    def test_a_search_stay_still_wins_over_a_nearer_recommended_one(self):
        candidates = catalog(at('a1', 0), at('rec', 0, taxonomy='hotel'), at('searched', 20, taxonomy='hotel'))
        sources = sources_for(candidates, rec='recommendation')
        self.assertEqual(compose_plan(candidates, sources, self.trip(1))['stay_id'], 'searched')

    def test_a_flight_limited_day_gets_the_single_place_nearest_the_stay(self):
        # Ngày 1 chỉ còn buổi chiều. Theo luật cũ ngày 1 nhận `a` (productId nhỏ nhất); `a`, `b` ở xa khách sạn.
        window = {1: {'times': ['AFTERNOON'], 'full_day': False, 'transfers': [('MORNING', 'ARRIVAL')]}}
        candidates = catalog(at('a', 10), at('b', 11), at('c', 0.2), at('h', 0, taxonomy='hotel'))
        proposal = compose_plan(candidates, sources_for(candidates), self.trip(2), window)
        self.assertEqual(self.days_of(proposal), {1: {'c'}, 2: {'a', 'b'}})
        self.assertEqual(proposal['stay_id'], 'h')

    def test_a_place_without_a_known_position_comes_after_located_ones(self):
        candidates = catalog(at('a', 0, unitPrice=300_000), at('b', 1, unitPrice=300_000),
                             product('unknown', destination='Phú Quốc', unitPrice=10_000))
        proposal = compose_plan(candidates, sources_for(candidates), self.trip(1))
        self.assertEqual(self.days_of(proposal), {1: {'a', 'b'}})

    def test_a_city_centre_point_counts_as_unknown(self):
        # Năm tour chung toạ độ 4 chữ số thập phân: tâm thành phố, không phải vị trí thật (AC-AGT-04).
        tours = [product(f'tour{index}', destination='Phú Quốc', unitPrice=10_000,
                         attributes={'latitude': 10.3, 'longitude': 103.95}) for index in range(5)]
        candidates = catalog(*tours, at('a', 30, unitPrice=300_000), at('b', 31, unitPrice=300_000))
        proposal = compose_plan(candidates, sources_for(candidates), self.trip(1))
        self.assertEqual(self.days_of(proposal), {1: {'a', 'b'}})

    def test_without_any_position_the_old_rules_apply_and_no_criteria_is_claimed(self):
        candidates = catalog(product('a'), product('b'), product('c'))
        proposal = compose_plan(candidates, sources_for(candidates), intent(days=2))
        self.assertEqual(self.days_of(proposal), {1: {'a', 'c'}, 2: {'b'}})
        self.assertNotIn('criteria', proposal)

    def test_a_full_day_visit_still_takes_a_day_alone(self):
        candidates = catalog(at('long', 0, attributes={'durationMinutes': 480}), at('a', 30), at('b', 31))
        proposal = compose_plan(candidates, sources_for(candidates), self.trip(2))
        self.assertEqual(sorted(self.days_of(proposal).values(), key=sorted), [{'a', 'b'}, {'long'}])

    def test_the_same_candidates_in_any_order_give_the_same_proposal(self):
        products = [at('a1', 40), at('a2', 41), at('b1', 0), at('b2', 1), at('h', 20, taxonomy='hotel')]
        forward = compose_plan(catalog(*products), sources_for(catalog(*products)), self.trip(2))
        backward = compose_plan(catalog(*reversed(products)), sources_for(catalog(*reversed(products))), self.trip(2))
        self.assertEqual(forward, backward)

    def test_the_distance_proposal_survives_the_renderer_and_the_validator(self):
        candidates = catalog(at('a1', 40), at('a2', 41), at('b1', 0), at('b2', 1),
                             at('long', 20, attributes={'durationMinutes': 480}),
                             at('h', 20, taxonomy='hotel', unitPrice=1_000_000, priceUnit='PER_NIGHT'))
        trip, sources = self.trip(3), sources_for(candidates)
        plan = render_proposal(compose_plan(candidates, sources, trip, LATE_ARRIVAL), candidates, sources, trip)
        self.assertEqual(validate_plan(plan, candidates, sources, trip, {'require_hotel': True}), [])


class SummaryTests(unittest.TestCase):
    """history/2026-09-28-ap-dung-de-xuat-field-review-agent.md: ProductSummary trong lịch trình bỏ `description`,
    `attributes` chỉ giữ khoá FE đọc."""

    def test_description_is_dropped(self):
        item = product('h', description='Mô tả rất dài về khách sạn.')
        self.assertNotIn('description', summary(item))

    def test_attributes_keep_only_the_fields_the_frontend_reads(self):
        place = {'latitude': 12.2451, 'longitude': 109.1943, 'address': 'Đường Trần Phú, Nha Trang'}
        item = product('h', attributes={
            'oceanView': True, 'privateBeach': True, 'pool': True, 'ticketed': True, 'starRating': 5, **place,
            'durationMinutes': 480, 'parentProductId': 'p', 'images': ['https://example.vn/1.jpg'],
        })
        self.assertEqual(summary(item)['attributes'],
                         {'oceanView': True, 'privateBeach': True, 'pool': True, 'ticketed': True, 'starRating': 5,
                          **place})

    def test_attributes_key_is_dropped_entirely_when_nothing_survives_the_cut(self):
        item = product('h', attributes={'durationMinutes': 480, 'parentProductId': 'p'})
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

    def test_a_free_to_visit_place_counts_as_zero_not_as_an_unknown_price(self):
        # Trace 2026-10-08 (TP.HCM): Chợ Bến Thành, Bưu điện… không có giá bị xếp sau mọi vé có giá; spec tính 0 đ.
        candidates = catalog(product('ticket_a', unitPrice=300_000), product('ticket_b', unitPrice=200_000),
                             product('market', unitPrice=None), product('pagoda', attributes={'ticketed': False}))
        proposal = compose_plan(candidates, sources_for(candidates), intent(days=1))
        self.assertEqual({slot['product_id'] for slot in proposal['slots']}, {'market', 'pagoda'})
        # Khách sạn thiếu giá vẫn là giá chưa biết, xếp sau khách sạn có giá.
        stays = catalog(product('priced', taxonomy='hotel', unitPrice=9_000_000),
                        product('unpriced', taxonomy='hotel', unitPrice=None))
        self.assertEqual(compose_plan(stays, sources_for(stays), intent())['stay_id'], 'priced')

    def test_free_to_visit_covers_only_attractions_and_golf(self):
        self.assertTrue(free_to_visit(product('a', unitPrice=None)))
        self.assertTrue(free_to_visit(product('g', taxonomy='golf', unitPrice=None)))
        self.assertFalse(free_to_visit(product('h', taxonomy='hotel', unitPrice=None)))
        self.assertFalse(free_to_visit(product('c', taxonomy='combo', unitPrice=None)))
        self.assertFalse(free_to_visit(product('priced')))


class StayRoomsTests(unittest.TestCase):
    """Đoàn đông ở nhiều phòng (AC-AGT-04, chốt 2026-10-09): số phòng = ceil(người lớn / priceAdults), tiền × số phòng."""

    def hotel(self, pid='h', price=1_000_000, **attributes):
        return product(pid, taxonomy='hotel', unitPrice=price, priceUnit='PER_NIGHT', attributes=attributes)

    def party(self, adults, children=0):
        return {'type': 'FRIENDS', 'adults': adults, 'children': children}

    def render(self, candidates, trip):
        sources = sources_for(candidates)
        return render_proposal(compose_plan(candidates, sources, trip), candidates, sources, trip), sources

    def test_rooms_come_from_the_adults_the_price_already_covers(self):
        self.assertEqual(stay_rooms(self.hotel(priceAdults=2), self.party(10)), 5)
        self.assertEqual(stay_rooms(self.hotel(priceAdults=2), self.party(3)), 2)
        self.assertEqual(stay_rooms(self.hotel(priceAdults=3), self.party(3)), 1)

    def test_children_share_a_room_with_the_adults(self):
        self.assertEqual(stay_rooms(self.hotel(priceAdults=2), self.party(2, children=2)), 1)

    def test_a_hotel_without_price_adults_has_unknown_rooms(self):
        self.assertIsNone(stay_rooms(self.hotel(), self.party(10)))

    def test_the_stay_cost_is_price_times_nights_times_rooms(self):
        trip = intent(days=3, party=self.party(10))
        plan, _ = self.render(catalog(self.hotel(priceAdults=2)), trip)
        self.assertEqual(plan['stays'][0]['rooms'], 5)
        self.assertEqual(plan['costBreakdown']['stays'], 1_000_000 * 2 * 5)
        self.assertEqual(plan['estimatedTotal'], 10_000_000)

    def test_a_hotel_without_price_adults_counts_one_room(self):
        trip = intent(days=3, party=self.party(10))
        plan, _ = self.render(catalog(self.hotel()), trip)
        self.assertEqual(plan['stays'][0]['rooms'], 1)
        self.assertEqual(plan['costBreakdown']['stays'], 2_000_000)

    def test_a_hotel_needing_more_than_nine_rooms_is_not_chosen(self):
        trip = intent(days=2, party=self.party(20))
        candidates = catalog(self.hotel('pairs', price=500_000, priceAdults=2),
                             self.hotel('quads', price=3_000_000, priceAdults=4))
        self.assertEqual(compose_plan(candidates, sources_for(candidates), trip)['stay_id'], 'quads')
        only_pairs = catalog(self.hotel('pairs', price=500_000, priceAdults=2))
        self.assertIsNone(compose_plan(only_pairs, sources_for(only_pairs), trip)['stay_id'])

    def test_the_validator_rejects_a_tampered_room_count(self):
        trip = intent(days=3, party=self.party(10))
        candidates = catalog(self.hotel(priceAdults=2))
        plan, sources = self.render(candidates, trip)
        self.assertEqual(validate_plan(plan, candidates, sources, trip, {}), [])
        plan['stays'][0]['rooms'] = plan['stay']['rooms'] = 1
        self.assertIn('stays', validate_plan(plan, candidates, sources, trip, {}))

    def test_search_guests_are_the_fewest_per_room_that_fit_nine_rooms(self):
        self.assertEqual(room_guests(self.party(10)), {'adults': 2, 'children': 0})
        self.assertEqual(room_guests(self.party(2, children=1)), {'adults': 1, 'children': 0})
        self.assertEqual(room_guests(self.party(9, children=9)), {'adults': 1, 'children': 1})
        self.assertIsNone(room_guests(None))


if __name__ == '__main__':
    unittest.main()
