import unittest
import uuid
from datetime import date, timedelta

from data_collection.seed import simulated_rooms as sr
from data_collection.seed.simulated_business import NAMESPACE

AS_OF = date(2026, 10, 9)
HI = AS_OF + timedelta(days=29)


def hotel(ref, *, price=850_000, available=False, attrs=None, level='property', parent=None):
    a = {'level': level, 'address': '1 Trần Phú', 'latitude': 16.0, 'longitude': 108.2, 'starRating': 4,
         'images': [f'img{i}' for i in range(8)], **(attrs or {})}
    if level == 'property' and not available:
        a.setdefault('noBookableRoom', True)
    if parent:
        a['parentProductId'] = parent['product_id']
    return {'product_id': str(uuid.uuid5(NAMESPACE, ref)), 'name': f'Khách sạn {ref}', 'taxonomy': 'hotel', 'destination': 'Đà Nẵng',
            'description': '', 'attributes': a, 'unit_price': price, 'currency': 'VND', 'available': available,
            'available_from': AS_OF, 'available_to': HI, 'image_url': f'img:{ref}', 'source_ref': ref}


class PlanTests(unittest.TestCase):
    def test_priced_hotel_without_rooms_gets_a_standard_room_and_is_reopened(self):
        prop = hotel('agoda:hotel:a')
        [room], [opened] = sr.plan([prop], AS_OF, True)
        a = room['attributes']
        self.assertEqual(room['name'], 'Khách sạn agoda:hotel:a - Phòng tiêu chuẩn (giá minh hoạ)')
        self.assertEqual((room['unit_price'], room['source_ref'], room['image_url']), (850_000, 'demo:room:agoda:hotel:a', prop['image_url']))
        self.assertEqual((a['level'], a['parentProductId'], a['maxOccupancy'], a['simulated']), ('room', prop['product_id'], 2, True))
        self.assertEqual(a['availability'], {'from': '2026-10-09', 'days': 30, 'calendar': '1' * 30})
        self.assertEqual(len(a['images']), 5)
        self.assertEqual((room['available_from'], room['available_to']), (AS_OF, HI))
        self.assertTrue(opened['available'])
        self.assertNotIn('noBookableRoom', opened['attributes'])

    def test_skips_hotels_with_real_rooms_without_price_merged_or_closed_for_other_reasons(self):
        with_room = hotel('booking:hotel:b', available=True)
        real_room = hotel('booking:room:b1', level='room', parent=with_room, available=True)
        no_price = hotel('agoda:hotel:c', price=None)
        merged = hotel('agoda:hotel:d', attrs={'mergedInto': 'x'})
        stale = hotel('agoda:hotel:e', attrs={'priceFreshness': 'stale'})
        rooms, reopened = sr.plan([with_room, real_room, no_price, merged, stale], AS_OF, True)
        self.assertEqual([r['source_ref'] for r in rooms], ['demo:room:agoda:hotel:e'])  # có phòng nhưng không bật lại
        self.assertEqual(reopened, [])

    def test_real_rooms_appearing_or_disable_close_the_mock_room(self):
        prop = hotel('agoda:hotel:a')
        [room], [opened] = sr.plan([prop], AS_OF, True)
        real = hotel('agoda:room:a1', level='room', parent=opened, available=True)
        rooms, reopened = sr.plan([opened, room, real], AS_OF, True)
        self.assertEqual([(r['source_ref'], r['available']) for r in rooms], [(room['source_ref'], False)])
        self.assertEqual(reopened, [])  # khách sạn đã có phòng thật: giữ nguyên
        rooms, reopened = sr.plan([opened, room], AS_OF, False)
        self.assertEqual([r['available'] for r in rooms], [False])
        self.assertEqual([(r['available'], r['attributes']['noBookableRoom']) for r in reopened], [(False, True)])

    def test_plan_is_stable_after_apply(self):
        prop = hotel('agoda:hotel:a')
        [room], [opened] = sr.plan([prop], AS_OF, True)
        rooms, reopened = sr.plan([opened, room], AS_OF, True)
        self.assertEqual(rooms, [room])
        self.assertEqual(reopened, [])


if __name__ == '__main__':
    unittest.main()
