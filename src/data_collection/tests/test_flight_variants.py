"""Synthetic edge cases for dated quotes; amounts here are test data, never catalog evidence."""
import copy
from datetime import date, datetime, timedelta, timezone

import pytest
import normalise as n
from collectors import booking_flights as bf
from data_collection.seed.load_products import convert, shift_fixed_flight
from fresh_catalog_db import apply_window, price_attributes
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


def test_seed_keeps_real_date_in_window_else_shifts_both_legs_and_ignores_quote_expiry():
    """PRD data-model §3: seed demo dời vé ngày cố định ngoài cửa sổ như vé không cố định ngày; giá và priceValidUntil giữ nguyên."""
    route, raw = roundtrip()
    p, = n.trip_roundtrip_products(raw, route)
    p['name'] = 'Khứ hồi VN100 / VN101: SGN - HAN (2026-10-10 – 2026-10-13)'
    p['description'] = 'Vé khứ hồi SGN - HAN, đi 2026-10-10, về 2026-10-13.'
    # Ngày đi trong cửa sổ: giữ ngày thật, kể cả khi báo giá (30/09) đã hết hạn.
    for as_of in (date(2026, 9, 29), date(2026, 10, 1)):
        rows, stats = convert([route, p], {}, as_of)
        loaded = next(x for x in rows if x['product_id'] == p['productId'])
        assert loaded['available'] is True
        assert loaded['available_from'] == loaded['available_to'] == '2026-10-10'
        assert loaded['attributes'] == {**p['attributes'], 'sourceAvailableFrom': '2026-10-10', 'sourceAvailableTo': '2026-10-10'}
        assert loaded['name'] == p['name']
        assert stats['chuyến bay: báo giá ngày cố định (ngày thật)'] == 1
    # Ngày đi đã qua: dời vào cửa sổ, hai chặng cùng số ngày, giữ giờ; tên/mô tả đổi theo; giá và hạn báo giá giữ nguyên.
    as_of = date(2026, 11, 1)
    rows, stats = convert([route, p], {}, as_of)
    loaded = next(x for x in rows if x['product_id'] == p['productId'])
    day = date.fromisoformat(loaded['available_from'])
    assert as_of <= day <= date(2026, 11, 30) and loaded['available_to'] == loaded['available_from']
    assert loaded['available'] is True and loaded['unit_price'] == p['unitPrice']
    back = (day + (date(2026, 10, 13) - date(2026, 10, 10))).isoformat()
    a = loaded['attributes']
    assert a['departureAt'] == f'{day.isoformat()}T08:00:00+07:00' and a['arrivalAt'] == f'{day.isoformat()}T10:00:00+07:00'
    assert a['returnFlight']['departureAt'] == f'{back}T08:00:00+07:00' and a['returnFlight']['arrivalAt'] == f'{back}T10:00:00+07:00'
    assert a['returnDate'] == back and a['stayDays'] == p['attributes']['stayDays']
    assert a['priceValidUntil'] == '2026-09-30' and a['fixedDepartureDate'] is True
    assert set(a) == set(p['attributes']) | {'sourceAvailableFrom', 'sourceAvailableTo'}  # không gắn thêm khoá nào
    assert loaded['name'] == f'Khứ hồi VN100 / VN101: SGN - HAN ({day.isoformat()} – {back})'
    assert loaded['description'] == f'Vé khứ hồi SGN - HAN, đi {day.isoformat()}, về {back}.'
    assert p['attributes']['departureAt'].startswith('2026-10-10')  # đầu vào không bị sửa
    assert stats['chuyến bay: báo giá ngày cố định (dời vào cửa sổ)'] == 1
    tuyen = next(x for x in rows if x['product_id'] == route['productId'])
    assert tuyen['available_from'] == tuyen['available_to'] == day.isoformat()


def test_shift_when_new_return_equals_old_departure():
    attrs = {'departureAt': '2026-10-10T08:00:00+07:00', 'arrivalAt': '2026-10-10T10:00:00+07:00', 'returnDate': '2026-10-13',
             'returnFlight': {'departureAt': '2026-10-13T08:00:00+07:00', 'arrivalAt': '2026-10-13T10:00:00+07:00'}}
    name, _ = shift_fixed_flight(attrs, date(2026, 10, 7), '(2026-10-10 – 2026-10-13)', '')
    assert name == '(2026-10-07 – 2026-10-10)' and attrs['returnDate'] == '2026-10-10'


def test_seed_never_puts_two_itineraries_of_the_same_flights_on_one_day_and_moves_cabins_together():
    """Hai hành trình cùng chuyến khác ngày gốc không bị dời vào cùng ngày; các hạng của một hành trình dời cùng ngày."""
    route, raw = roundtrip()
    p, = n.trip_roundtrip_products(raw, route)
    for leg in raw['roundTripLegs']:
        leg['cabinClass'] = 'BUSINESS'
    business, = n.trip_roundtrip_products(raw, route)
    as_of = date(2026, 11, 1)
    rows = [route, p, business]
    for i in range(1, 40):  # cùng cặp chuyến, ngày gốc khác nhau: nhiều hơn 30 ô để ép trùng
        other = copy.deepcopy(p)
        other['productId'] = f"{p['productId']}-{i}"
        other['sourceRef'] = f"{p['sourceRef']}-{i}"
        for key, leg in (('departureAt', other['attributes']), ('arrivalAt', other['attributes']),
                         ('departureAt', other['attributes']['returnFlight']), ('arrivalAt', other['attributes']['returnFlight'])):
            leg[key] = (datetime.fromisoformat(leg[key]) - timedelta(days=i)).isoformat()
        other['attributes']['returnDate'] = other['attributes']['returnFlight']['departureAt'][:10]
        rows.append(other)
    loaded, _ = convert(rows, {}, as_of)
    by_id = {x['product_id']: x for x in loaded}
    assert by_id[p['productId']]['available_from'] == by_id[business['productId']]['available_from']
    economy_days = [x['available_from'] for x in loaded
                    if x['attributes'].get('tripType') == 'roundTrip' and x['attributes'].get('cabinClass') != 'BUSINESS']
    assert len(economy_days) == 40 and len(set(economy_days)) == 30  # 30 ô trong cửa sổ đều dùng trước khi phải trùng


def test_job_window_keeps_real_date_and_blocks_expired_quotes():
    """Job cào (dữ liệu thật) không dời ngày vé ngày cố định; hết hạn báo giá thì không đặt được."""
    route, raw = roundtrip()
    p, = n.trip_roundtrip_products(raw, route)
    attrs = {**p['attributes'], 'sourceAvailableFrom': '2026-10-10', 'sourceAvailableTo': '2026-10-10'}
    db_row = {'product_id': p['productId'], 'taxonomy': 'flight', 'attributes': attrs, 'available': True,
              'available_from': None, 'available_to': None, 'unit_price': p['unitPrice'], 'source_ref': p['sourceRef']}
    fresh = apply_window([db_row], date(2026, 9, 29))[p['productId']]
    assert (fresh['available_from'], fresh['available_to']) == (date(2026, 10, 10), date(2026, 10, 10))
    assert fresh['attributes']['departureAt'] == p['attributes']['departureAt']
    for as_of in (date(2026, 10, 1), date(2026, 11, 1)):
        blocked = apply_window([db_row], as_of)[p['productId']]
        assert (blocked['available'], blocked['available_from']) == (False, None)
        assert blocked['attributes']['departureAt'] == p['attributes']['departureAt']


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
