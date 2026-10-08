import copy
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from collectors.common import Paths
from collectors.trip_business import _save_state, parse_days, plan_tasks, state_path
from collectors.trip_roundtrip_search import parse_roundtrip
from fresh_catalog_db import validate_catalog
from normalise import trip_roundtrip_search_products, trip_route_history, trip_route_products

# Fare modal read from vn.trip.com on 2026-09-30 (HAN-SGN, out 10/10, back 13/10), trimmed URL.
CAPTURE = {
    'legs': [
        'Chặng 1 Chuyến bay khởi hành từ Cảng hàng không quốc tế Nội Bài T1 lúc 22:55, 10 tháng 10, 2026 và hạ cánh tại '
        'Cảng hàng không quốc tế Tân Sơn Nhất T3 lúc 01:10, 11 tháng 10, 2026 Thời lượng chuyến bay là 2g 15p '
        'Thông tin máy bay: Vietnam Airlines, VN6025, 321',
        'Chặng 2 Chuyến bay khởi hành từ Cảng hàng không quốc tế Tân Sơn Nhất T3 lúc 06:30, 13 tháng 10, 2026 và hạ cánh '
        'tại Cảng hàng không quốc tế Nội Bài T1 lúc 08:40, 13 tháng 10, 2026 Thời lượng chuyến bay là 2g 10p '
        'Thông tin máy bay: Sun PhuQuoc Airways, 9G808, 321'],
    'cards': [
        {'cabin': 'Hạng Phổ Thông', 'payment': 'MoMo', 'price': 2083000, 'roundTrip': True},
        {'cabin': 'Hạng Phổ Thông', 'payment': 'MoMo', 'price': 2653000, 'roundTrip': True},
        {'cabin': 'Thương Gia', 'payment': 'MoMo', 'price': 21621000, 'roundTrip': True}],
    'separateTickets': True,
    'url': 'https://vn.trip.com/flights/ShowFareNext?pagesource=list&triptype=RT&class=Y&quantity=1&dcity=han&acity=sgn'
           '&ddate=2026-10-10&rdate=2026-10-13&currentseqno=2&locale=vi-VN&curr=VND&midpolicyid=1%3ASGN-HAN%3A9G808',
    'observedAt': '2026-09-30T05:40:00Z',
}
ROUTE_RECORD = {'key': 'han-sgn', 'crawledAt': '2026-09-30T03:00:00Z', 'fromCity': 'Hà Nội', 'toCity': 'TP. Hồ Chí Minh',
                'fromCode': 'han', 'toCode': 'sgn', 'fromAirports': ['HAN'], 'toAirports': ['SGN'], 'flights': []}


def route_product():
    return trip_route_products(dict(ROUTE_RECORD), 0)[0]


class ParseRoundTripTests(unittest.TestCase):
    def test_real_modal_gives_cheapest_total_per_cabin(self):
        quotes = {q['cabinClass']: q for q in parse_roundtrip(CAPTURE, 'HAN', 'SGN')}
        self.assertEqual(set(quotes), {'ECONOMY', 'BUSINESS'})
        self.assertEqual(quotes['ECONOMY']['price'], 2083000)
        self.assertEqual(quotes['BUSINESS']['price'], 21621000)
        eco = quotes['ECONOMY']
        self.assertEqual((eco['outbound']['flightNumber'], eco['inbound']['flightNumber']), ('VN6025', '9G808'))
        self.assertEqual(eco['outbound']['departureAt'], '2026-10-10T22:55:00+07:00')
        self.assertEqual(eco['inbound']['arrivalAt'], '2026-10-13T08:40:00+07:00')
        self.assertTrue(eco['separateTickets'])

    def test_fails_closed_on_mismatched_or_unverified_evidence(self):
        bad_urls = [CAPTURE['url'].replace('triptype=RT', 'triptype=OW'),
                    CAPTURE['url'].replace('quantity=1', 'quantity=2'),
                    CAPTURE['url'].replace('ddate=2026-10-10', 'ddate=2026-10-11'),
                    CAPTURE['url'].replace('rdate=2026-10-13', 'rdate=2026-10-14'),
                    CAPTURE['url'].replace('9G808', 'VN123'),
                    CAPTURE['url'].replace('acity=sgn', 'acity=dad'),
                    CAPTURE['url'].replace('vn.trip.com', 'example.com')]
        for url in bad_urls:
            self.assertEqual(parse_roundtrip({**CAPTURE, 'url': url}, 'HAN', 'SGN'), [], url)
        three_legs = CAPTURE['legs'] + [CAPTURE['legs'][1].replace('Chặng 2', 'Chặng 3')]
        for change in ({'legs': three_legs}, {'legs': CAPTURE['legs'][::-1]}, {'observedAt': 'invalid'},
                       {'legs': [CAPTURE['legs'][0], CAPTURE['legs'][1].replace('13 tháng 10', '10 tháng 10')]}):
            self.assertEqual(parse_roundtrip({**CAPTURE, **change}, 'HAN', 'SGN'), [], change)
        self.assertEqual(parse_roundtrip(CAPTURE, 'HAN', 'DAD'), [])

    def test_unverified_cards_are_dropped_not_guessed(self):
        cards = [{'cabin': 'Thương Gia (chiều đi)', 'price': 9000000, 'roundTrip': True},
                 {'cabin': 'Thương Gia', 'price': 9000000, 'roundTrip': False},
                 {'cabin': 'Thương Gia', 'price': '9000000', 'roundTrip': True},
                 {'cabin': 'Hạng Phổ Thông', 'price': 2083000, 'roundTrip': True}]
        quotes = parse_roundtrip({**CAPTURE, 'cards': cards}, 'HAN', 'SGN')
        self.assertEqual([q['cabinClass'] for q in quotes], ['ECONOMY'])

    def test_cam_ranh_airport_matches_trip_city_code(self):
        capture = copy.deepcopy(CAPTURE)
        capture['url'] = (capture['url'].replace('acity=sgn', 'acity=nha')
                          .replace('SGN-HAN', 'NHA-HAN'))
        self.assertTrue(parse_roundtrip(capture, 'HAN', 'CXR'))


class MappingTests(unittest.TestCase):
    def test_products_use_seo_ref_format_and_validate(self):
        route = route_product()
        products = trip_roundtrip_search_products({**ROUTE_RECORD, 'roundTripQuotes': [CAPTURE]}, route)
        refs = sorted(p['sourceRef'] for p in products)
        self.assertEqual(refs, ['trip:roundtrip:HAN-SGN:VN6025:2026-10-10:9G808:2026-10-13:BUSINESS',
                                'trip:roundtrip:HAN-SGN:VN6025:2026-10-10:9G808:2026-10-13:ECONOMY'])
        business = next(p for p in products if p['attributes']['cabinClass'] == 'BUSINESS')
        attrs = business['attributes']
        self.assertEqual((business['unitPrice'], business['availableFrom'], business['availableTo']),
                         (21621000, '2026-10-10', '2026-10-10'))
        self.assertEqual((attrs['tripType'], attrs['stayDays'], attrs['returnDate']), ('roundTrip', 3, '2026-10-13'))
        self.assertNotIn('priceValidUntil', attrs)  # the search shows no validity; none is invented
        self.assertEqual(attrs['returnFlight']['originAirport'], 'SGN')
        for product in products:
            product.pop('_meta', None)
        validate_catalog(products, allow_external_parents=True)

    def test_newest_capture_wins_and_history_keeps_all_captures(self):
        newer = {**CAPTURE, 'observedAt': '2026-10-01T05:40:00Z',
                 'cards': [{'cabin': 'Hạng Phổ Thông', 'price': 1990000, 'roundTrip': True}]}
        records = [{**ROUTE_RECORD, 'roundTripQuotes': [CAPTURE]},
                   {**ROUTE_RECORD, 'crawledAt': '2026-10-01T00:00:00Z'},
                   {**ROUTE_RECORD, 'crawledAt': '2026-10-01T00:00:00Z', 'roundTripQuotes': [newer]}]
        merged = trip_route_history(records)[0]
        self.assertEqual(len(merged['roundTripQuotes']), 2)
        products = {p['attributes']['cabinClass']: p['unitPrice']
                    for p in trip_roundtrip_search_products(merged, route_product())}
        self.assertEqual(products, {'ECONOMY': 1990000, 'BUSINESS': 21621000})

    def test_search_quote_replaces_seo_card_of_same_itinerary(self):
        def leg(kind, frm, to, number, dep, arr):
            return {'leg': kind, 'from': frm, 'to': to, 'flightNumber': number, 'airline': 'X',
                    'departureTime': dep, 'arrivalTime': arr, 'price': 1500000, 'currency': 'VND',
                    'cabinClass': 'ECONOMY'}
        seo = [leg('out', 'HAN', 'SGN', 'VN6025', '2026-10-10T15:55:00Z', '2026-10-10T18:10:00Z'),
               leg('in', 'SGN', 'HAN', '9G808', '2026-10-12T23:30:00Z', '2026-10-13T01:40:00Z')]
        products = trip_route_products({**ROUTE_RECORD, 'roundTripLegs': seo, 'roundTripQuotes': [CAPTURE]}, 0)
        economy = [p for p in products if p['sourceRef'].endswith(':ECONOMY')]
        self.assertEqual([p['unitPrice'] for p in economy], [2083000])
        self.assertEqual(len({p['sourceRef'] for p in products}), len(products))


    def test_refresh_clears_expiry_inherited_from_seo_card(self):
        from fresh_catalog_db import price_attributes
        fresh = next(p for p in trip_roundtrip_search_products({**ROUTE_RECORD, 'roundTripQuotes': [CAPTURE]},
                                                               route_product())
                     if p['attributes']['cabinClass'] == 'ECONOMY')
        previous = {**fresh['attributes'], 'priceValidUntil': '2026-10-01', 'priceObservedAt': '2026-09-29T00:00:00Z'}
        attrs = price_attributes(fresh, previous, '2026-09-30T05:40:00Z')
        self.assertNotIn('priceValidUntil', attrs)
        self.assertEqual(attrs['priceObservedAt'], '2026-09-30T05:40:00Z')


class RotationTests(unittest.TestCase):
    routes = [{'fromAirports': ['HAN'], 'toAirports': ['SGN']}, {'fromAirports': ['SGN'], 'toAirports': ['PQC']}]

    def test_parse_days(self):
        self.assertEqual(parse_days('1-3,7'), (1, 2, 3, 7))
        for bad in ('', '0-30', '-1'):
            with self.assertRaises(ValueError):
                parse_days(bad)

    def test_untried_nearest_first_then_least_recently_tried(self):
        today = date(2026, 9, 30)
        tasks = plan_tasks(self.routes, today, (1, 2), (3, 5, 7), {})
        self.assertEqual(len(tasks), 2 * 2 * 4)
        self.assertEqual([t['key'] for t in tasks[:5]],
                         ['ow-business:HAN-SGN:2026-10-01', 'rt:HAN-SGN:2026-10-01:3', 'rt:HAN-SGN:2026-10-01:5',
                          'rt:HAN-SGN:2026-10-01:7', 'ow-business:SGN-PQC:2026-10-01'])
        state = {t['key']: {'lastAttemptAt': '2026-09-30T01:00:00Z'} for t in tasks[:8]}
        state['rt:HAN-SGN:2026-10-01:3'] = {'lastAttemptAt': '2026-09-29T01:00:00Z'}
        again = plan_tasks(self.routes, today, (1, 2), (3, 5, 7), state)
        self.assertEqual(again[0]['day'], date(2026, 10, 2))  # never tried
        self.assertEqual(again[8]['key'], 'rt:HAN-SGN:2026-10-01:3')  # oldest attempt among tried ones

    def test_state_survives_run_dirs_and_drops_past_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {'CATALOG_STATE_DIR': tmp}):
                path = state_path(Paths(Path(tmp) / 'run-1'))
            self.assertEqual(path, Path(tmp) / 'trip_fares_rotation.json')
            _save_state(path, {'rt:HAN-SGN:2026-09-29:3': {}, 'ow-business:HAN-SGN:2026-09-30': {}},
                        date(2026, 9, 30))
            self.assertEqual(list(json.loads(path.read_text())), ['ow-business:HAN-SGN:2026-09-30'])


class BlockRetryTests(unittest.TestCase):
    class Page:
        def __init__(self, statuses):
            self.statuses, self.calls = list(statuses), 0

        async def goto(self, url, **kw):
            self.calls += 1
            return mock.Mock(status=self.statuses.pop(0))

    def run_open(self, statuses):
        import asyncio
        from collectors import trip_roundtrip_search as rt
        page = self.Page(statuses)
        sleep = mock.AsyncMock()
        with mock.patch.object(rt.asyncio, 'sleep', sleep):
            try:
                asyncio.run(rt.open_search(page, 'https://vn.trip.com/x', 'search'))
                error = None
            except RuntimeError as exc:
                error = str(exc)
        return page.calls, sleep.await_args_list, error

    def test_432_waits_45_seconds_then_retries_once(self):
        calls, sleeps, error = self.run_open([432, 200])
        self.assertEqual((calls, error), (2, None))
        self.assertEqual([c.args for c in sleeps], [(45,)])
        calls, sleeps, error = self.run_open([432, 432])
        self.assertEqual((calls, error), (2, 'search denied: HTTP 432'))

    def test_other_denials_fail_without_waiting(self):
        for status in (403, 429):
            calls, sleeps, error = self.run_open([status])
            self.assertEqual((calls, len(sleeps), error), (1, 0, f'search denied: HTTP {status}'))


class FreshCommandTests(unittest.TestCase):
    def test_trip_flights_gets_fare_budget_and_source_deadline(self):
        import fresh_catalog
        import fresh_settings
        with tempfile.TemporaryDirectory() as tmp:
            values = fresh_settings.load(Path(tmp), env={})
        command = fresh_catalog.source_command(Path('/tmp/run'), 'trip-flights', 'Hà Nội', values)
        self.assertIn('--fares-minutes', command)
        self.assertEqual(command[command.index('--fares-minutes') + 1], '30')
        self.assertEqual(command[command.index('--source-deadline-minutes') + 1], str(values['timeout.tripFlights']))

    def test_agoda_fresh_step_uses_api_room_collector_for_one_real_price_day(self):
        import fresh_catalog
        import fresh_settings
        with tempfile.TemporaryDirectory() as tmp:
            values = fresh_settings.load(Path(tmp), env={})
        command = fresh_catalog.source_command(Path('/tmp/run'), 'agoda-hotels', '@core', values)
        self.assertIn('agoda-api', command)
        self.assertNotIn('agoda-hotels', command)
        self.assertEqual(command[command.index('--per-city') + 1], str(values['agoda.hotelsPerDestination']))
        self.assertEqual(command[command.index('--days') + 1], '1')
        self.assertNotIn('--concurrency', command)


if __name__ == '__main__':
    unittest.main()
