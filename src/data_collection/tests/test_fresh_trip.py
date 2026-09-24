"""Trip room JSON must map to fresh, dated room products without old prices."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import normalise
from collectors.trip_live import assemble, price_packet
from fresh_catalog_db import prepare_rows
from fresh_catalog_schedule import record_batch, select_batch


class FreshTripTests(unittest.TestCase):
    def test_room_json_joins_physical_room_and_filters_invalid_offers(self):
        payload = {'data': {'physicRoomMap': {'7': {'name': 'Deluxe'}},
                            'saleRoomMap': {'offer-1': {'physicalRoomId': 7,
                                                       'priceInfo': {'price': 900000, 'currency': 'VND'}},
                                            'offer-2': {'physicalRoomId': 7,
                                                       'priceInfo': {'price': 700000, 'currency': 'VND'}},
                                            'bad': {'physicalRoomId': 7,
                                                    'priceInfo': {'price': 1, 'currency': 'USD'}}}}}
        status, data, offers = price_packet(payload)
        self.assertEqual((status, offers), ('priced', 3))
        self.assertEqual(data['best']['7']['price'], 700000)
        self.assertEqual(price_packet({'data': {'physicRoomMap': {}, 'saleRoomMap': {},
                                                    'isRoomListSoldOut': True}})[0], 'sold_out')
        self.assertEqual(price_packet({'data': {'saleRoomMap': {}}})[0], 'missing')

    def test_assemble_and_normalise_three_dates_and_new_room(self):
        target = {'trip_hotel_id': '999', 'city_id': '1777', 'destination': 'Nha Trang'}
        dates = [('2026-10-08', '2026-10-09'), ('2026-10-24', '2026-10-25'),
                 ('2026-11-23', '2026-11-24')]
        base = {'hotelId': '999', 'name': 'Khách sạn thử nghiệm', 'city': 'Nha Trang',
                'description': 'Khách sạn có nhiều phòng tại Nha Trang.',
                'rooms': [{'roomId': '7', 'name': 'Deluxe'}], 'images': [],
                'currency': 'VND', 'crawledAt': '2026-09-24T00:00:00Z'}
        captures = {
            ('999', dates[0][0]): ('priced', {'physical': {'7': {'name': 'Deluxe'},
                                                          '8': {'name': 'Suite'}},
                                           'best': {'7': {'price': 700000, 'occupancy': 2},
                                                    '8': {'price': 900000, 'occupancy': 3}}}, 2, None),
            ('999', dates[1][0]): ('sold_out', {'physical': {}, 'best': {}}, 0, None),
            ('999', dates[2][0]): ('priced', {'physical': {'7': {'name': 'Deluxe'},
                                                         '8': {'name': 'Suite'}},
                                           'best': {'7': {'price': 800000, 'occupancy': 2}}}, 1, None),
        }
        with tempfile.TemporaryDirectory() as tmp:
            records, coverage = assemble([target], dates, {'999': base}, captures, Path(tmp))
            self.assertEqual(coverage['completedHotels'], ['999'])
            prop, rooms = normalise.trip_hotel(records[0], {})
            self.assertEqual(prop['unitPrice'], 700000)
            self.assertEqual(len(rooms), 2)
            suite = next(row for row in rooms if row['attributes']['roomId'] == '8')
            self.assertEqual(suite['attributes']['pricesByDate'], {'2026-10-08': 900000})
            self.assertEqual(suite['attributes']['availabilityByDate']['2026-10-24'], False)
            self.assertEqual(tuple(suite)[:13], normalise.PRODUCT_FIELDS)

    def test_current_run_normalise_keeps_all_trip_room_ids(self):
        record = {'recordType': 'trip_hotel', 'key': 'hotel:999', 'hotelId': '999',
                  'name': 'Khách sạn thử nghiệm', 'city': 'Nha Trang',
                  'description': 'Khách sạn thử nghiệm tại Nha Trang.',
                  'rooms': [{'roomId': '7', 'name': 'Deluxe', 'currency': 'VND',
                             'pricesByDate': {'2026-10-08': 700000}},
                            {'roomId': '8', 'name': 'Suite', 'currency': 'VND',
                             'pricesByDate': {'2026-10-08': 900000}}],
                  'priceDatesQueried': ['2026-10-08', '2026-10-24', '2026-11-23'],
                  'currency': 'VND', 'crawledAt': '2026-09-24T00:00:00Z',
                  'plan': {'destination': 'Nha Trang'}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'interim').mkdir()
            (root / 'interim' / 'trip_hotels.jsonl').write_text(
                json.dumps(record, ensure_ascii=False) + '\n', encoding='utf-8')
            self.assertEqual(normalise.main([
                '--data-dir', tmp, '--no-plan', '--rooms-per-hotel', '0',
                '--keep-unsellable', '--keep-missing-coordinates',
                '--keep-location-warnings', '--keep-price-outliers']), 0)
            rows = [json.loads(line) for line in (root / 'products.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual({row['sourceRef'] for row in rows},
                             {'trip:hotel:999', 'trip:hotel:999:room:7', 'trip:hotel:999:room:8'})
            self.assertEqual({row['attributes'].get('parentProductId') for row in rows[1:]},
                             {rows[0]['productId']})

    def test_failed_hotel_does_not_publish_or_retire_its_rooms(self):
        target = {'trip_hotel_id': '999', 'city_id': '1777', 'destination': 'Nha Trang'}
        dates = [('2026-10-08', '2026-10-09'), ('2026-10-24', '2026-10-25')]
        captures = {('999', dates[0][0]): ('priced', {'physical': {'7': {'name': 'Deluxe'}},
                                                         'best': {'7': {'price': 700000}}}, 1, None)}
        with tempfile.TemporaryDirectory() as tmp:
            records, coverage = assemble([target], dates, {}, captures, Path(tmp))
            self.assertEqual(records, [])
            self.assertEqual(coverage['completedHotels'], [])
            self.assertEqual(len(coverage['unpricedHotelDates']), 1)

    def test_new_trip_room_attaches_to_existing_merged_hotel(self):
        record = {'hotelId': '999', 'name': 'Khách sạn thử nghiệm', 'city': 'Nha Trang',
                  'priceDatesQueried': ['2026-10-08'], 'crawledAt': '2026-09-24T00:00:00Z',
                  'rooms': [{'roomId': '8', 'name': 'Suite', 'currency': 'VND',
                             'pricesByDate': {'2026-10-08': 900000}}]}
        prop, rooms = normalise.trip_hotel(record, {})
        canonical_id = 'aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa'
        old = {'product_id': canonical_id, 'source_ref': 'booking:hotel:999',
               'attributes': {'level': 'property', 'sameAs': ['trip:hotel:999']},
               'unit_price': None, 'available': False}
        fresh = [{key: item[key] for key in normalise.PRODUCT_FIELDS} for item in [prop, *rooms]]
        prepared, counts = prepare_rows(fresh, [old], {'999'}, '2026-09-24')
        self.assertEqual(counts['newRooms'], 1)
        self.assertEqual(prepared[0]['product_id'], canonical_id)
        self.assertEqual(prepared[1]['attributes']['parentProductId'], canonical_id)
        self.assertEqual(prepared[1]['source_ref'], 'trip:hotel:999:room:8')

    def test_scheduler_rotates_and_db_expires_native_trip_prices(self):
        targets = [{'trip_hotel_id': value, 'city_id': '1777', 'destination': 'Nha Trang'}
                   for value in ('1', '2', '3')]
        selected = select_batch(targets, {}, 2)
        self.assertEqual([row['trip_hotel_id'] for row in selected], ['1', '2'])
        coverage = {'stays': [{'checkin': '2026-10-08'}],
                    'results': [{'hotelId': value, 'checkin': '2026-10-08', 'status': 'priced'}
                                for value in ('1', '2')]}
        state = record_batch(selected, coverage, {}, '2026-09-24T00:00:00Z')
        self.assertEqual(select_batch(targets, state, 1)[0]['trip_hotel_id'], '3')
        old = {'product_id': 'old', 'source_ref': 'trip:hotel:1:room:7',
               'attributes': {'level': 'room', 'priceRefreshedAt': '2026-09-01T00:00:00Z',
                              'pricesByDate': {'2026-10-08': 700000}},
               'unit_price': 700000, 'available': True}
        rows, counts = prepare_rows([], [old], set(), '2026-09-24',
                                    now=datetime(2026, 9, 24, tzinfo=timezone.utc))
        self.assertEqual(counts['staleTrip'], 1)
        self.assertFalse(rows[0]['available'])
        self.assertIsNone(rows[0]['unit_price'])


if __name__ == '__main__':
    unittest.main()
