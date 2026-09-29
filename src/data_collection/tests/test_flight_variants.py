"""Synthetic edge cases for dated quotes; amounts here are test data, never catalog evidence."""
import copy
from datetime import date, datetime, timezone

import pytest
import normalise as n
from collectors import booking_flights as bf
from data_collection.seed.load_products import convert
from fresh_catalog_db import price_attributes
from tests.test_booking_flights import payload


def roundtrip():
    route = n.make_product(name='SGN–HAN', taxonomy='flight', destination='Hà Nội',
                           description='', sourceRef='trip:route:sgn-han',
                           attributes={'level': 'route', 'originCity': 'Hồ Chí Minh'})
    go = dict(leg='out', flightNumber='VN100', airline='Test', **{'from': 'SGN', 'to': 'HAN'},
              departureTime='2026-10-10T08:00:00+07:00', arrivalTime='2026-10-10T10:00:00+07:00',
              price=2400000, currency='VND', priceValidUntil='2026-09-30')
    back = dict(leg='in', flightNumber='VN101', airline='Test', **{'from': 'HAN', 'to': 'SGN'},
                departureTime='2026-10-13T08:00:00+07:00', arrivalTime='2026-10-13T10:00:00+07:00')
    return route, {'roundTripLegs': [go, back], 'crawledAt': '2026-09-29T08:00:00Z'}


def test_roundtrip_price_dates_and_stable_identity():
    route, raw = roundtrip()
    p, = n.trip_roundtrip_products(raw, route)
    assert p['unitPrice'] == 2400000
    assert p['availableFrom'] == p['availableTo'] == '2026-10-10'
    assert p['attributes']['returnDate'] == '2026-10-13'
    assert p['attributes']['parentProductId'] == route['productId']
    assert not p['attributes'].get('cabinClass')
    raw['roundTripLegs'][0]['price'] = 2600000
    assert n.trip_roundtrip_products(raw, route)[0]['productId'] == p['productId']
    for leg in raw['roundTripLegs']:
        leg['cabinClass'] = 'BUSINESS'
    business, = n.trip_roundtrip_products(raw, route)
    assert business['productId'] != p['productId']
    assert business['attributes']['cabinClass'] == 'BUSINESS'


@pytest.mark.parametrize('change', ['missing', 'wrong_airports', 'return_before_departure', 'price_mismatch', 'bad_price'])
def test_incomplete_or_ambiguous_pairs_are_not_bookable(change):
    route, raw = roundtrip()
    if change == 'missing': raw['roundTripLegs'].pop()
    elif change == 'wrong_airports': raw['roundTripLegs'][1]['to'] = 'DAD'
    elif change == 'return_before_departure': raw['roundTripLegs'][1]['departureTime'] = '2026-10-09T08:00:00+07:00'
    elif change == 'price_mismatch': raw['roundTripLegs'][1]['price'] = 500000
    else: raw['roundTripLegs'][0]['price'] = float('nan')
    assert n.trip_roundtrip_products(raw, route) == []


def test_loader_keeps_both_legs_and_expires_old_quotes():
    route, raw = roundtrip()
    p, = n.trip_roundtrip_products(raw, route)
    for as_of, expected in [(date(2026, 9, 29), True), (date(2026, 10, 1), False), (date(2026, 11, 1), False)]:
        rows, _ = convert([route, p], {}, as_of)
        loaded = next(x for x in rows if x['product_id'] == p['productId'])
        assert loaded['available'] is expected
        assert loaded['attributes']['departureAt'] == p['attributes']['departureAt']
        assert loaded['attributes']['returnFlight'] == p['attributes']['returnFlight']
        if expected: assert loaded['available_from'] == loaded['available_to'] == '2026-10-10'


def test_cabins_are_separate_and_party_price_is_not_divided():
    eco = bf.parse_detail(payload())
    business = copy.deepcopy(eco)
    business['context']['cabinClass'] = 'BUSINESS'
    business['totalPrice'] = 3200000
    party = copy.deepcopy(eco)
    party['context']['adults'] = 2
    party['totalPrice'] = 10
    rows = n.merge_booking_flight_products([], [{'key': 'test', 'offers': [eco, business, party]}],
                                           now=datetime(2026, 9, 18, 10, tzinfo=timezone.utc))
    flights = [p for p in rows if p['attributes']['level'] == 'flight']
    assert len(flights) == 2
    assert len({p['productId'] for p in flights}) == 2
    assert {p['unitPrice'] for p in flights} == {1223323, 3200000}
    assert {p['attributes']['cabinClass'] for p in flights} == {'ECONOMY', 'BUSINESS'}


def test_requested_business_cannot_relabel_rendered_economy():
    p = payload()
    p['context']['cabinClass'] = 'BUSINESS'
    with pytest.raises(ValueError): bf.parse_detail(p)
    p['html'] = p['html'].replace('Economy', 'Business')
    assert bf.parse_detail(p)['context']['cabinClass'] == 'BUSINESS'


def test_price_refresh_preserves_static_fields_and_updates_fixed_quote():
    route, raw = roundtrip()
    p, = n.trip_roundtrip_products(raw, route)
    previous = {**copy.deepcopy(p['attributes']), 'priceValidUntil': '2026-09-20', 'customStatic': 'keep'}
    attrs = price_attributes(p, previous, '2026-09-29T08:00:00Z')
    assert attrs['customStatic'] == 'keep'
    assert attrs['priceValidUntil'] == '2026-09-30'
    assert attrs['returnFlight'] == p['attributes']['returnFlight']
