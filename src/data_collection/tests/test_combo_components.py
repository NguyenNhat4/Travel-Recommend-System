import unittest
import uuid
from datetime import date, timedelta
from decimal import Decimal

from data_collection.seed import combo_components as cc
from data_collection.seed.simulated_business import NAMESPACE

AS_OF = date(2026, 10, 9)
HI = AS_OF + timedelta(days=29)


def row(ref, taxonomy, name, attrs, *, price=None, dest='Huế', available=True):
    return {'product_id': str(uuid.uuid5(NAMESPACE, ref)), 'name': name, 'taxonomy': taxonomy, 'destination': dest,
            'description': '', 'attributes': attrs, 'unit_price': None if price is None else Decimal(price), 'currency': 'VND',
            'available': available, 'available_from': AS_OF, 'available_to': HI, 'image_url': f'img:{ref}', 'source_ref': ref}


def item(combo, position, kind, label, target=None, quantity=1):
    return {'combo_product_id': combo['product_id'], 'position': position, 'label': label, 'item_kind': kind,
            'item_product_id': target and target['product_id'], 'quantity': Decimal(quantity), 'price_share': None}


class Fixture:
    def __init__(self):
        self.hotel = row('booking:hotel:melia', 'hotel', 'Meliá Vinpearl Hue', {'level': 'property', 'address': '50A Hùng Vương',
                                                                               'starRating': 5}, price=1_500_000)
        self.room = row('booking:room:melia:deluxe', 'hotel', 'Meliá Vinpearl Hue - Phòng Deluxe',
                        {'level': 'room', 'parentProductId': self.hotel['product_id'], 'roomName': 'Phòng Deluxe'}, price=1_800_000)
        self.route = row('trip:route:SGN-HUI', 'flight', 'Vé máy bay TP. Hồ Chí Minh - Huế',
                         {'level': 'route', 'originAirports': ['SGN'], 'destinationAirports': ['HUI'], 'originCity': 'TP. Hồ Chí Minh',
                          'roundTripFrom': 2_000_000}, price=900_000)
        self.ticket = row('vinpearl:tour:T1', 'attraction', 'Vé VinWonders', {'venue': 'VinWonders'}, price=600_000)
        self.poi = row('trip:poi:dainoi', 'attraction', 'Đại Nội Huế', {'latitude': 16.4, 'longitude': 107.6})
        self.flight_hotel = row('trip:combo:SGN-HUI:1', 'combo', 'Vé máy bay khứ hồi + Phòng Deluxe tại Melia',
                                {'hotelName': 'Khách sạn Melia Vipearl Huế', 'roomType': 'Phòng Deluxe', 'fromCode': 'SGN',
                                 'toCode': 'HUI', 'priceAdults': 2}, price=6_000_500)
        self.fun = row('vinpearl:tour:C1', 'combo', 'Combo VinWonders + Buffet 350K + Xe điện + Đại Nội',
                       {'venue': 'VinWonders'}, price=1_000_000)
        self.rows = [self.hotel, self.room, self.route, self.ticket, self.poi, self.flight_hotel, self.fun]
        self.items = [item(self.flight_hotel, 1, 'flight', 'Vé máy bay khứ hồi', self.route, quantity=2),
                      item(self.flight_hotel, 2, 'hotel', 'Phòng Deluxe tại Melia', self.hotel),
                      item(self.fun, 1, 'attraction', 'VinWonders', self.ticket),
                      item(self.fun, 2, 'meal', 'Buffet 350K'),
                      item(self.fun, 3, 'transfer', 'Xe điện'),
                      item(self.fun, 4, 'attraction', 'Đại Nội', self.poi)]


def run(rows, items, on=True):
    return cc.plan(rows, items, AS_OF, on)


def apply(fx, result):
    """Ghi kết quả vào bản sao trong bộ nhớ như sync() ghi DB, để chạy lại lần hai."""
    rows = {r['product_id']: r for r in fx.rows}
    rows.update({p['product_id']: p for p in result.products.values()})
    links = {(i['combo_product_id'], i['position']): i for i in result.items}
    items = [{**i, **{k: links[(i['combo_product_id'], i['position'])][k]
                      for k in ('item_product_id', 'item_kind', 'price_share')}} for i in fx.items]
    return list(rows.values()), items


class SharesTests(unittest.TestCase):
    def test_sum_is_exactly_the_combo_price(self):
        out = cc.shares(Decimal('6000500'), [Decimal(4_000_000), Decimal(1_800_000)])
        self.assertEqual(sum(out), Decimal('6000500'))
        self.assertEqual(out, [Decimal('4138500.00'), Decimal('1862000.00')])

    def test_missing_reference_takes_the_cheapest_and_none_means_equal(self):
        out = cc.shares(Decimal(1_200_000), [Decimal(600_000), None, Decimal(300_000)])
        self.assertEqual(out, [Decimal('600000.00'), Decimal('300000.00'), Decimal('300000.00')])
        self.assertEqual(cc.shares(Decimal(1_000_000), [None, None]), [Decimal('500000.00'), Decimal('500000.00')])
        self.assertEqual(cc.shares(None, [Decimal(1)]), [None])

    def test_label_amounts(self):
        self.assertEqual(cc.label_amount('Ẩm thực Cát Thuỷ 300k'), 300_000)
        self.assertEqual(cc.label_amount('Voucher ẩm thực 150.000 VND'), 150_000)
        self.assertEqual(cc.label_amount('Voucher Quà lưu niệm 30.000 VNĐ'), 30_000)
        self.assertEqual(cc.label_amount('Buffet 350K'), 350_000)
        self.assertIsNone(cc.label_amount('10 buổi Jjimjilbang'))
        self.assertIsNone(cc.label_amount('03 Games trên Đảo'))

    def test_duration_text(self):
        self.assertEqual(cc.minutes('1g 20p'), 80)
        self.assertEqual(cc.minutes('2g'), 120)
        self.assertIsNone(cc.minutes(''))


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()
        self.result = run(self.fx.rows, self.fx.items)
        self.links = {(i['combo_product_id'], i['position']): i for i in self.result.items}
        self.by_id = {p['product_id']: p for p in self.result.products.values()}

    def link(self, combo, position):
        return self.links[(combo['product_id'], position)]

    def test_hotel_and_room_names_matching_link_the_real_room(self):
        self.assertEqual(self.link(self.fx.flight_hotel, 2)['item_product_id'], self.fx.room['product_id'])
        self.assertEqual(self.link(self.fx.flight_hotel, 1)['item_product_id'], self.fx.route['product_id'])

    def test_shares_follow_references_and_sum_to_price(self):
        fh = [self.link(self.fx.flight_hotel, p)['price_share'] for p in (1, 2)]
        self.assertEqual(sum(fh), Decimal('6000500'))  # tham khảo: khứ hồi 2.000.000 × 2 khách, phòng 1.800.000 × 1 đêm
        self.assertEqual(fh, [Decimal('4138500.00'), Decimal('1862000.00')])
        fun = [self.link(self.fx.fun, p)['price_share'] for p in (1, 2, 3, 4)]
        # vé thật 600.000 và vé mô phỏng Đại Nội (không giá tham khảo → bằng vé rẻ nhất) chia đôi; buffet, xe điện đi kèm
        self.assertEqual(fun, [Decimal('500000.00'), None, None, Decimal('500000.00')])

    def test_services_stay_included_without_product_or_share(self):
        for position, kind in ((2, 'meal'), (3, 'transfer')):
            link = self.link(self.fx.fun, position)
            self.assertEqual((link['item_kind'], link['item_product_id'], link['price_share']), (kind, None, None))
        self.assertFalse([p for p in self.result.products.values() if p['attributes'].get('serviceKind')])
        self.assertEqual({p['source_ref'] for p in self.result.products.values()
                          if p['attributes'].get('comboProductId') == self.fx.fun['product_id']}, {'demo:combo:vinpearl:tour:C1:4'})

    def test_combo_with_only_services_gets_no_shares(self):
        spa = row('vinpearl:tour:S1', 'combo', 'Combo Cano + Tắm bùn', {'venue': 'Hòn Tằm'}, price=860_000)
        self.fx.rows.append(spa)
        self.fx.items += [item(spa, 1, 'transfer', 'Cano Hòn Tằm'), item(spa, 2, 'other', 'Tắm Bùn')]
        result = run(self.fx.rows, self.fx.items)
        links = [i for i in result.items if i['combo_product_id'] == spa['product_id']]
        self.assertEqual([(i['item_product_id'], i['price_share']) for i in links], [(None, None), (None, None)])

    def test_services_linked_by_an_older_run_are_unlinked_and_their_mocks_closed(self):
        old = row('demo:combo:vinpearl:tour:C1:2', 'attraction', 'Buffet 350K — VinWonders (giá minh hoạ)',
                  {'serviceKind': 'meal', 'comboOnly': True, 'simulated': True}, price=212_000)
        self.fx.rows.append(old)
        self.fx.items[3] = {**self.fx.items[3], 'item_kind': 'attraction', 'item_product_id': old['product_id']}
        result = run(self.fx.rows, self.fx.items)
        link = next(i for i in result.items if i['combo_product_id'] == self.fx.fun['product_id'] and i['position'] == 2)
        self.assertEqual((link['item_kind'], link['item_product_id'], link['price_share']), ('meal', None, None))
        self.assertFalse(result.products[old['source_ref']]['available'])

    def test_mock_without_real_price_uses_the_combo_share(self):
        poi = self.link(self.fx.fun, 4)
        self.assertEqual(self.by_id[poi['item_product_id']]['unit_price'], poi['price_share'])

    def test_unpriced_poi_becomes_a_mock_ticket_with_its_base(self):
        poi = self.link(self.fx.fun, 4)
        mock = self.by_id[poi['item_product_id']]
        self.assertEqual(mock['attributes']['comboBaseProductId'], self.fx.poi['product_id'])
        self.assertEqual((mock['attributes']['latitude'], mock['image_url']), (16.4, self.fx.poi['image_url']))
        self.assertEqual(self.link(self.fx.fun, 1)['item_product_id'], self.fx.ticket['product_id'])  # vé thật giữ nguyên

    def test_unmatched_room_type_gets_mock_room_under_mock_property(self):
        self.fx.flight_hotel['attributes']['roomType'] = 'Garda Deluxe Twin Room'
        result = run(self.fx.rows, self.fx.items)
        link = next(i for i in result.items if i['combo_product_id'] == self.fx.flight_hotel['product_id'] and i['position'] == 2)
        products = {p['product_id']: p for p in result.products.values()}
        room = products[link['item_product_id']]
        prop = products[room['attributes']['parentProductId']]
        self.assertEqual((room['attributes']['level'], prop['attributes']['level']), ('room', 'property'))
        self.assertEqual(prop['attributes']['comboBaseProductId'], self.fx.hotel['product_id'])
        self.assertEqual(prop['attributes']['address'], '50A Hùng Vương')
        self.assertTrue(room['attributes']['comboOnly'] and prop['attributes']['comboOnly'])
        self.assertNotEqual(room['attributes']['parentProductId'], self.fx.hotel['product_id'])  # không gắn vào khách sạn thật
        self.assertEqual((room['available_from'], room['available_to']), (AS_OF, HI))
        self.assertEqual(room['unit_price'], Decimal(1_500_000))  # giá lẻ = giá thật của khách sạn đã khớp, không phải phần giá combo
        self.assertNotEqual(link['price_share'], room['unit_price'])

    def test_missing_route_becomes_mock_route_with_template(self):
        self.fx.flight_hotel['attributes'].update(fromCode='HAN', toCode='VDO', outboundFlight={
            'departTime': '19:25', 'arriveTime': '20:45', 'airlineCode': 'VJ', 'durationText': '1g 20p',
            'departAirport': 'HAN T1', 'arriveAirport': 'VDO'})
        self.fx.items[0]['item_product_id'] = None
        result = run(self.fx.rows, self.fx.items)
        link = next(i for i in result.items if i['combo_product_id'] == self.fx.flight_hotel['product_id'] and i['position'] == 1)
        products = {p['product_id']: p for p in result.products.values()}
        mock = products[link['item_product_id']]
        a = mock['attributes']
        self.assertEqual((a['level'], a['originAirports'], a['destinationAirports'], a['comboOnly']), ('route', ['HAN'], ['VDO'], True))
        self.assertEqual(a['templateFlight'], {'airline': 'VJ', 'airlineCode': 'VJ', 'originAirport': 'HAN',
                                               'destinationAirport': 'VDO', 'departureTimeLocal': '19:25',
                                               'arrivalTimeLocal': '20:45', 'durationMinutes': 80})
        self.assertEqual(a['roundTripFrom'], float(link['price_share'] / 2))

    def test_reverse_mock_route_is_used_before_a_combo_only_route(self):
        reverse = row('demo:reverse:trip:route:VDO-HAN', 'flight', 'Vé máy bay Hà Nội - Hạ Long (giá minh hoạ)',
                      {'level': 'route', 'originAirports': ['HAN'], 'destinationAirports': ['VDO'], 'roundTripFrom': 1_500_000,
                       'simulated': True}, price=700_000)
        self.fx.rows.append(reverse)
        self.fx.flight_hotel['attributes'].update(fromCode='HAN', toCode='VDO')
        self.fx.items[0]['item_product_id'] = None
        result = run(self.fx.rows, self.fx.items)
        link = next(i for i in result.items if i['combo_product_id'] == self.fx.flight_hotel['product_id'] and i['position'] == 1)
        self.assertEqual(link['item_product_id'], reverse['product_id'])
        self.assertFalse([p for p in result.products.values() if p['attributes'].get('level') == 'route'])
        again = run(*apply(self.fx, result))
        self.assertEqual(sorted(again.items, key=lambda i: (i['combo_product_id'], i['position'])),
                         sorted(result.items, key=lambda i: (i['combo_product_id'], i['position'])))

    def test_second_run_changes_nothing(self):
        rows, items = apply(self.fx, self.result)
        again = run(rows, items)
        self.assertEqual(sorted(again.items, key=lambda i: (i['combo_product_id'], i['position'])),
                         sorted(self.result.items, key=lambda i: (i['combo_product_id'], i['position'])))
        self.assertEqual(again.products, self.result.products)

    def test_unavailable_combo_or_disabled_closes_mocks(self):
        rows, items = apply(self.fx, self.result)
        off = run(rows, items, on=False)
        self.assertTrue(off.products)
        self.assertFalse(any(p['available'] for p in off.products.values()))
        self.fx.fun['available'] = False
        closed = run(self.fx.rows, self.fx.items)
        self.assertFalse(any(p['available'] for p in closed.products.values()
                             if p['attributes'].get('comboProductId') == self.fx.fun['product_id']))

    def test_merged_link_follows_to_the_kept_row(self):
        dup = row('booking:tour:T1-dup', 'attraction', 'Vé VinWonders (trùng)', {'mergedInto': self.fx.ticket['product_id']})
        self.fx.rows.append(dup)
        self.fx.items[2]['item_product_id'] = dup['product_id']
        result = run(self.fx.rows, self.fx.items)
        link = next(i for i in result.items if i['combo_product_id'] == self.fx.fun['product_id'] and i['position'] == 1)
        self.assertEqual(link['item_product_id'], self.fx.ticket['product_id'])


class EnabledTests(unittest.TestCase):
    def test_default_on_and_off_values(self):
        self.assertTrue(cc.enabled({}))
        self.assertFalse(cc.enabled({cc.ENV: '0'}))


if __name__ == '__main__':
    unittest.main()
