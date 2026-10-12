import unittest
import uuid
from datetime import date, timedelta

from data_collection.seed import simulated_fill as sf
from data_collection.seed.simulated_business import NAMESPACE

AS_OF = date(2026, 10, 9)
HI = AS_OF + timedelta(days=29)


def route(ref, origin='Hà Nội', dest='TP. Hồ Chí Minh', *, extra=None, price=1_200_000, available=True):
    attrs = {'level': 'route', 'originCity': origin, 'destinationCity': dest, 'roundTripFrom': 2_500_000, **(extra or {})}
    return {'product_id': str(uuid.uuid5(NAMESPACE, ref)), 'name': f'Vé máy bay {origin} - {dest}', 'taxonomy': 'flight',
            'destination': dest, 'description': '', 'attributes': attrs, 'unit_price': price, 'currency': 'VND',
            'available': available, 'available_from': AS_OF, 'available_to': AS_OF, 'image_url': 'img', 'source_ref': ref}


def flight(ref, parent, *, day=AS_OF, number='VN205', price=1_494_000, trip=None, cabin=None, available=True,
           origin='HAN', dest='SGN', simulated=False):
    attrs = {'level': 'flight', 'parentProductId': parent['product_id'], 'flightNumber': number, 'airline': 'Vietnam Airlines',
             'originAirport': origin, 'destinationAirport': dest, 'departureAt': f'{day}T08:00:00+07:00',
             'arrivalAt': f'{day}T10:10:00+07:00'}
    if trip:
        attrs['tripType'] = trip
    if cabin:
        attrs['cabinClass'] = cabin
    if simulated:
        attrs['simulated'] = True
    return {'product_id': str(uuid.uuid5(NAMESPACE, ref)), 'name': ref, 'taxonomy': 'flight', 'destination': parent['destination'],
            'description': '', 'attributes': attrs, 'unit_price': price, 'currency': 'VND', 'available': available,
            'available_from': day, 'available_to': day, 'image_url': None, 'source_ref': ref}


def by_kind_day(rows):
    return {(r['attributes']['tripType'], r['available_from']): r for r in rows if r['available']}


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.go = route('trip:route:HAN-SGN')
        self.back = route('trip:route:SGN-HAN', 'TP. Hồ Chí Minh', 'Hà Nội')
        self.real = flight('trip:flight:VN205', self.go, day=AS_OF + timedelta(days=3))
        self.real_back = flight('trip:flight:VN220', self.back, number='VN220', price=1_300_000, origin='SGN', dest='HAN')

    def plan(self, *rows, on=True):
        return sf.plan([self.go, self.back, self.real, self.real_back, *rows], AS_OF, on)

    def test_every_day_of_the_window_gets_one_way_and_round_trip(self):
        fills, _ = self.plan()
        mine = by_kind_day(r for r in fills if r['attributes']['parentProductId'] == self.go['product_id'])
        days = {AS_OF + timedelta(days=i) for i in range(30)}
        self.assertEqual({d for k, d in mine if k == 'oneWay'}, days - {self.real['available_from']})  # vé thật thắng
        self.assertEqual({d for k, d in mine if k == 'roundTrip'}, days)

    def test_copy_is_marked_priced_and_scheduled_from_the_real_flight(self):
        fills, _ = self.plan()
        day = AS_OF + timedelta(days=5)
        one = next(r for r in fills if r['available_from'] == day and r['attributes']['tripType'] == 'oneWay'
                   and r['attributes']['parentProductId'] == self.go['product_id'])
        a = one['attributes']
        self.assertEqual(one['unit_price'], 1_494_000)
        self.assertEqual((a['flightNumber'], a['departureAt'], a['arrivalAt']),
                         ('VN205', f'{day}T08:00:00+07:00', f'{day}T10:10:00+07:00'))
        self.assertEqual(a['durationMinutes'], 130)  # suy từ giờ bay của vé mẫu
        self.assertEqual((a['simulated'], a['cabinClass'], a['fieldSources']['unitPrice']), (True, 'ECONOMY', 'mô phỏng'))
        self.assertTrue(one['name'].endswith('(giá minh hoạ)'))
        self.assertEqual(one['source_ref'], f'demo:fill:trip:route:HAN-SGN:oneWay:{day}')
        self.assertEqual(one['product_id'], str(uuid.uuid5(NAMESPACE, one['source_ref'])))
        self.assertEqual(a['simulatedFrom'], [self.real['product_id']])

    def test_round_trip_return_leg_comes_from_the_reverse_route(self):
        fills, _ = self.plan()
        rt = next(r for r in fills if r['attributes']['tripType'] == 'roundTrip'
                  and r['attributes']['parentProductId'] == self.go['product_id'])
        a = rt['attributes']
        self.assertIn(a['stayDays'], (2, 3, 4, 5))
        back_day = rt['available_from'] + timedelta(days=a['stayDays'])
        self.assertEqual(a['returnDate'], back_day.isoformat())
        self.assertEqual((a['returnFlight']['flightNumber'], a['returnFlight']['departureAt']),
                         ('VN220', f'{back_day}T08:00:00+07:00'))
        self.assertEqual(rt['unit_price'], 2_500_000)  # không có vé khứ hồi thật → roundTripFrom của tuyến

    def test_real_round_trip_price_wins_over_route_price(self):
        real_rt = flight('trip:rt:VN205', self.go, trip='roundTrip', price=2_900_000, day=AS_OF + timedelta(days=1))
        fills, _ = self.plan(real_rt)
        rts = [r for r in fills if r['attributes']['tripType'] == 'roundTrip' and r['attributes']['parentProductId']
               == self.go['product_id']]
        self.assertNotIn(AS_OF + timedelta(days=1), {r['available_from'] for r in rts})
        self.assertEqual({r['unit_price'] for r in rts}, {2_900_000})

    def test_business_and_simulated_rows_do_not_cover_a_day(self):
        biz = flight('trip:biz', self.go, cabin='BUSINESS', day=AS_OF)
        sim = flight('demo:business:x', self.go, simulated=True, day=AS_OF)
        fills, _ = self.plan(biz, sim)
        self.assertIn(('oneWay', AS_OF), {(r['attributes']['tripType'], r['available_from']) for r in fills
                                          if r['attributes']['parentProductId'] == self.go['product_id']})

    def test_existing_fill_is_closed_when_a_real_flight_appears_or_day_passes(self):
        first, _ = self.plan()
        old = next(r for r in first if r['available_from'] == AS_OF and r['attributes']['tripType'] == 'oneWay'
                   and r['attributes']['parentProductId'] == self.go['product_id'])
        stale = {**old, 'available_from': AS_OF - timedelta(days=1), 'available_to': AS_OF - timedelta(days=1),
                 'source_ref': old['source_ref'].replace(str(AS_OF), str(AS_OF - timedelta(days=1))),
                 'product_id': 'stale'}
        real_today = flight('trip:flight:VN207', self.go, number='VN207', day=AS_OF)
        second, _ = self.plan(old, stale, real_today)
        closed = {r['product_id']: r for r in second if not r['available']}
        self.assertIn(old['product_id'], closed)
        self.assertIn('stale', closed)

    def test_disabled_closes_every_fill(self):
        first, _ = self.plan()
        again, _ = self.plan(*first, on=False)
        self.assertEqual(len(again), len(first))
        self.assertFalse(any(r['available'] for r in again))

    def test_plan_is_stable(self):
        a, _ = self.plan()
        b, _ = self.plan()
        self.assertEqual(a, b)

    def test_route_window_widens_to_children(self):
        _, widened = self.plan()
        go = next(r for r in widened if r['product_id'] == self.go['product_id'])
        self.assertEqual((go['available_from'], go['available_to']), (AS_OF, HI))

    def test_mock_route_uses_template_from_combo(self):
        mock = route('demo:combo:trip:combo:X:1', 'Hà Nội', 'Hạ Long', extra={
            'comboOnly': True, 'templateFlight': {'airline': 'VietJet Air', 'airlineCode': 'VJ', 'originAirport': 'HAN',
                                                  'destinationAirport': 'VDO', 'departureTimeLocal': '19:25',
                                                  'arrivalTimeLocal': '20:45', 'durationMinutes': 80},
            'templateReturnFlight': {'airline': 'VietJet Air', 'originAirport': 'VDO', 'destinationAirport': 'HAN',
                                     'departureTimeLocal': '20:45', 'durationMinutes': 80}}, price=700_000, available=False)
        mock['attributes']['roundTripFrom'] = 1_400_000
        fills, _ = self.plan(mock)
        mine = [r for r in fills if r['attributes']['parentProductId'] == mock['product_id']]
        self.assertEqual(len(mine), 60)
        rt = next(r for r in mine if r['attributes']['tripType'] == 'roundTrip')
        self.assertEqual(rt['unit_price'], 1_400_000)
        self.assertTrue(rt['attributes']['departureAt'].endswith('T19:25:00+07:00'))
        self.assertEqual(rt['attributes']['returnFlight']['originAirport'], 'VDO')
        self.assertNotIn('flightNumber', rt['attributes'])

    def test_round_trip_without_reverse_route_swaps_airports_and_names_cleanly(self):
        lone = route('trip:route:HAN-TBB', 'Hà Nội', 'Phú Yên')
        out = flight('trip:flight:VN1661', lone, number='VN1661', dest='TBB')
        fills, _ = self.plan(lone, out)
        rt = next(r for r in fills if r['attributes']['parentProductId'] == lone['product_id']
                  and r['attributes']['tripType'] == 'roundTrip')
        back = rt['attributes']['returnFlight']
        self.assertEqual((back['originAirport'], back['destinationAirport']), ('TBB', 'HAN'))
        self.assertNotIn('flightNumber', back)
        self.assertTrue(rt['name'].startswith('Khứ hồi VN1661: HAN - TBB ('), rt['name'])
        self.assertNotIn('?', rt['name'])

    def test_route_without_any_template_gets_nothing(self):
        lonely = route('trip:route:CAH-HAN', 'Cà Mau', 'Hà Nội')
        fills, _ = self.plan(lonely)
        self.assertFalse([r for r in fills if r['attributes']['parentProductId'] == lonely['product_id']])


class ReverseRouteTests(unittest.TestCase):
    def setUp(self):
        self.go = route('trip:route:PXU-HAN', 'Pleiku', 'Hà Nội', extra={
            'originAirports': ['PXU'], 'destinationAirports': ['HAN'], 'airlines': ['VietJet Air'],
            'originLatitude': 14.0, 'originLongitude': 108.0, 'latitude': 21.2, 'longitude': 105.8})
        self.flight = flight('trip:flight:VJ402', self.go, number='VJ402', origin='PXU', dest='HAN', price=1_100_000)

    def test_one_way_route_gets_a_reverse_route_with_swapped_template(self):
        [rev] = sf.reverse_routes([self.go, self.flight], AS_OF, True)
        a = rev['attributes']
        self.assertEqual((rev['name'], rev['destination']), ('Vé máy bay Hà Nội - Pleiku (giá minh hoạ)', 'Pleiku'))
        self.assertEqual((a['originCity'], a['destinationCity'], a['originAirports'], a['destinationAirports']),
                         ('Hà Nội', 'Pleiku', ['HAN'], ['PXU']))
        self.assertEqual((a['latitude'], a['originLatitude']), (14.0, 21.2))
        self.assertEqual(a['templateFlights'], [{'airline': 'Vietnam Airlines', 'originAirport': 'HAN', 'destinationAirport': 'PXU',
                                                 'departureTimeLocal': '08:00', 'durationMinutes': 130, 'price': 1_100_000.0}])
        self.assertEqual((rev['unit_price'], rev['source_ref'], a['simulated']), (1_100_000, 'demo:reverse:trip:route:PXU-HAN', True))
        self.assertEqual((rev['available_from'], rev['available_to']), (AS_OF, HI))

    def test_reverse_route_is_filled_and_feeds_round_trips_of_the_real_route(self):
        rows = [self.go, self.flight, *sf.reverse_routes([self.go, self.flight], AS_OF, True)]
        rev_id = rows[-1]['product_id']
        fills, _ = sf.plan(rows, AS_OF, True)
        on_reverse = [r for r in fills if r['attributes']['parentProductId'] == rev_id]
        self.assertEqual(len(on_reverse), 60)
        one = next(r for r in on_reverse if r['attributes']['tripType'] == 'oneWay')
        self.assertEqual((one['attributes']['originAirport'], one['attributes']['destinationAirport'], one['unit_price']),
                         ('HAN', 'PXU', 1_100_000))
        rt = next(r for r in fills if r['attributes']['parentProductId'] == self.go['product_id']
                  and r['attributes']['tripType'] == 'roundTrip')
        self.assertEqual((rt['attributes']['returnFlight']['originAirport'], rt['attributes']['returnFlight']['destinationAirport']),
                         ('HAN', 'PXU'))

    def test_no_reverse_when_real_reverse_exists_and_old_one_is_closed(self):
        [rev] = sf.reverse_routes([self.go, self.flight], AS_OF, True)
        real_back = route('trip:route:HAN-PXU', 'Hà Nội', 'Pleiku')
        again = sf.reverse_routes([self.go, self.flight, real_back, rev], AS_OF, True)
        self.assertEqual([(r['source_ref'], r['available']) for r in again], [(rev['source_ref'], False)])
        self.assertEqual(sf.reverse_routes([self.go], AS_OF, True), [])  # tuyến không có vé thật: không đảo chiều
        self.assertEqual([r['available'] for r in sf.reverse_routes([self.go, self.flight, rev], AS_OF, False)], [False])


class EnabledTests(unittest.TestCase):
    def test_default_on_and_off_values(self):
        self.assertTrue(sf.enabled({}))
        for value in ('0', 'false', 'no', 'off', 'OFF'):
            self.assertFalse(sf.enabled({sf.ENV: value}))


if __name__ == '__main__':
    unittest.main()
