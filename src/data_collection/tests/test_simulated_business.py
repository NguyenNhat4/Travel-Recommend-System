import copy
import os
import unittest
import uuid
from datetime import date

from data_collection.seed import simulated_business as sb


def flight(ref, *, price=1_494_000, cabin=None, trip='oneWay', available=True, day=date(2026, 10, 10), number='VN205',
           back=None, simulated=None, level='flight'):
    attrs = {'level': level, 'tripType': trip, 'flightNumber': number, 'originAirport': 'HAN', 'destinationAirport': 'SGN',
             'departureAt': f'{day}T08:00:00+07:00', 'parentProductId': 'route-1', 'priceValidUntil': '2026-10-01',
             'fieldSources': {'unitPrice': 'trip.com'}}
    if cabin:
        attrs['cabinClass'] = cabin
    if back:
        attrs.update(returnFlight={'flightNumber': back, 'departureAt': '2026-10-13T06:30:00+07:00'},
                     returnDate='2026-10-13')
    if simulated:
        attrs['simulated'] = True
    return {'product_id': str(uuid.uuid5(sb.NAMESPACE, ref)), 'name': f'Vé {ref}', 'taxonomy': 'flight',
            'destination': 'TP. Hồ Chí Minh', 'description': 'Mô tả gốc.', 'attributes': attrs, 'unit_price': price,
            'currency': 'VND', 'available': available, 'available_from': day, 'available_to': day, 'image_url': None,
            'source_ref': ref}


class PlanTests(unittest.TestCase):
    def test_namespace_and_ids_match_normalise(self):
        from normalise import NAMESPACE, product_id
        self.assertEqual(sb.NAMESPACE, NAMESPACE)
        [sim] = sb.plan([flight('trip:flight:HAN-SGN:VN205')], True)
        self.assertEqual(sim['product_id'], product_id('demo:business:trip:flight:HAN-SGN:VN205'))

    def test_business_copy_is_priced_marked_and_copies_journey(self):
        source = flight('trip:roundtrip:HAN-SGN:VN6025:2026-10-10:9G808:2026-10-13:ECONOMY', price=2_083_000,
                        cabin='ECONOMY', trip='roundTrip', number='VN6025', back='9G808')
        [sim] = sb.plan([source], True)
        a = sim['attributes']
        self.assertEqual(sim['unit_price'], 5_520_000)  # 2.083.000 × 2,65 = 5.519.950 → nghìn đồng
        self.assertEqual(sim['source_ref'], 'demo:business:' + source['source_ref'])
        self.assertTrue(sim['name'].endswith('(giá minh hoạ)'))
        self.assertIn('không phải giá nguồn báo', sim['description'])
        self.assertEqual((a['cabinClass'], a['simulated'], a['fieldSources']['unitPrice']), ('BUSINESS', True, 'mô phỏng'))
        for key in ('returnFlight', 'returnDate', 'priceValidUntil', 'departureAt', 'parentProductId', 'tripType'):
            self.assertEqual(a[key], source['attributes'][key])
        self.assertEqual((sim['available'], sim['available_from'], sim['available_to']),
                         (True, source['available_from'], source['available_to']))
        self.assertNotIn('simulated', source['attributes'])  # source row untouched

    def test_only_real_non_business_flight_instances_are_sources(self):
        rows = [flight('route', level='route'), flight('biz', cabin='BUSINESS', number='VN1'),
                flight('first', cabin='FIRST', number='VN2'), flight('noprice', price=None, number='VN3'),
                flight('nonumber', number=None), flight('eco', cabin='ECONOMY', number='VN4'),
                flight('unknown', number='VN5')]
        self.assertEqual(sorted(r['source_ref'] for r in sb.plan(rows, True)),
                         ['demo:business:eco', 'demo:business:unknown'])

    def test_real_business_of_same_journey_and_day_wins(self):
        eco = flight('eco', cabin='ECONOMY')
        real = flight('real-biz', cabin='BUSINESS')
        other_day = flight('real-biz-other-day', cabin='BUSINESS', day=date(2026, 10, 11))
        [sim] = sb.plan([eco, real], True)
        self.assertFalse(sim['available'])
        [sim] = sb.plan([eco, other_day], True)
        self.assertTrue(sim['available'])
        [sim] = sb.plan([eco, {**real, 'available': False}], True)
        self.assertTrue(sim['available'])

    def test_closed_when_source_closes_disappears_or_feature_off(self):
        eco = flight('eco', cabin='ECONOMY')
        [sim] = sb.plan([eco], True)
        existing = {**sim, 'attributes': copy.deepcopy(sim['attributes'])}
        [closed] = sb.plan([{**eco, 'available': False}, existing], True)
        self.assertFalse(closed['available'])
        [closed] = sb.plan([existing], True)  # source row gone
        self.assertFalse(closed['available'])
        [closed] = sb.plan([eco, existing], False)
        self.assertFalse(closed['available'])
        self.assertEqual(sb.plan([eco, {**existing, 'available': False}], False), [])  # already closed: no write
        self.assertEqual(sb.plan([eco], False), [])

    def test_simulated_rows_never_seed_more_simulated_rows(self):
        [sim] = sb.plan([flight('eco')], True)
        refs = [r['source_ref'] for r in sb.plan([flight('eco'), sim], True)]
        self.assertEqual(refs, ['demo:business:eco'])

    def test_enabled_flag(self):
        for value, expected in (('1', True), ('true', True), ('on', True), ('', True), ('0', False), ('false', False),
                                ('no', False), (' OFF ', False)):
            self.assertEqual(sb.enabled({sb.ENV: value}), expected, value)
        self.assertTrue(sb.enabled({}))  # mặc định bật (data-model.md §3)


@unittest.skipUnless(os.environ.get('SIMULATED_TEST_DATABASE_URL'), 'isolated PostgreSQL required')
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.url = os.environ['SIMULATED_TEST_DATABASE_URL']
        with psycopg.connect(cls.url) as c:
            if not c.execute('select current_database()').fetchone()[0].startswith('vota_simbiz_test_'):
                raise RuntimeError('requires a disposable vota_simbiz_test_* database')

    def run_sync(self, on, rows=()):
        import psycopg
        from psycopg.types.json import Jsonb
        with psycopg.connect(self.url) as conn:
            for row in rows:
                conn.execute(f"INSERT INTO cdp.products ({', '.join(sb.COLUMNS)}) VALUES "
                             f"({', '.join(['%s'] * len(sb.COLUMNS))}) ON CONFLICT (product_id) DO UPDATE SET "
                             "available = EXCLUDED.available, unit_price = EXCLUDED.unit_price",
                             [Jsonb(row[c]) if c == 'attributes' else row[c] for c in sb.COLUMNS])
            counts = sb.sync(conn, on)
            rows = conn.execute("SELECT source_ref, available, unit_price, attributes->>'cabinClass' FROM cdp.products "
                                "WHERE source_ref LIKE 'demo:business:test:%' ORDER BY 1").fetchall()
        return counts, rows

    def tearDown(self):
        import psycopg
        with psycopg.connect(self.url) as conn:
            conn.execute("DELETE FROM cdp.products WHERE source_ref LIKE 'test:%' OR source_ref LIKE 'demo:business:test:%'")

    def test_sync_inserts_is_idempotent_follows_price_and_closes_when_off(self):
        eco = flight('test:eco', cabin='ECONOMY')
        counts, rows = self.run_sync(True, [eco])
        self.assertEqual(rows, [('demo:business:test:eco', True, 3_959_000, 'BUSINESS')])
        self.assertGreaterEqual(counts['simulatedBusinessWritten'], 1)
        counts, _ = self.run_sync(True)
        self.assertEqual(counts['simulatedBusinessWritten'], 0)  # nothing changed → nothing written
        _, rows = self.run_sync(True, [{**eco, 'unit_price': 1_000_000}])
        self.assertEqual(rows[0][2], 2_650_000)
        _, rows = self.run_sync(False)
        self.assertEqual(rows, [('demo:business:test:eco', False, 2_650_000, 'BUSINESS')])

    def test_fresh_maintenance_follows_the_env_switch(self):
        from unittest import mock
        import psycopg
        from fresh_catalog_db import maintain_catalog
        count = "SELECT count(*) FILTER (WHERE available), count(*) FROM cdp.products WHERE source_ref LIKE 'demo:business:%'"
        with mock.patch.dict(os.environ, {sb.ENV: '0'}):
            off = maintain_catalog(self.url, today=date(2026, 9, 30))
        with psycopg.connect(self.url) as conn:
            closed = conn.execute(count).fetchone()
        with mock.patch.dict(os.environ, {sb.ENV: '1'}):
            on = maintain_catalog(self.url, today=date(2026, 9, 30))
        with psycopg.connect(self.url) as conn:
            opened = conn.execute(count).fetchone()
        self.assertGreater(closed[1], 0)
        self.assertEqual(closed[0], 0)
        self.assertEqual(off['simulatedBusiness'], 0)
        self.assertEqual(opened[0], on['simulatedBusiness'])
        self.assertGreater(opened[0], 0)

    def test_fresh_load_writes_business_copy_and_real_business_wins(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest import mock
        import psycopg
        from fresh_catalog_db import load_into_db
        from tests.test_trip_roundtrip_search import CAPTURE, ROUTE_RECORD
        from normalise import trip_route_products
        products = trip_route_products({**ROUTE_RECORD, 'roundTripQuotes': [CAPTURE]}, 0)
        economy = next(p for p in products if p['sourceRef'].endswith(':ECONOMY'))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'products.jsonl'
            path.write_text(''.join(json.dumps({k: v for k, v in p.items() if k != '_meta'}, ensure_ascii=False) + '\n'
                                    for p in products))
            from stage_log import Stages
            sink, lines = [], []
            try:
                with mock.patch.dict(os.environ, {sb.ENV: '1'}):
                    counts = load_into_db(path, None, self.url, Path(__file__).resolve().parents[1],
                                          stages=Stages(sink, step='db', emit=lines.append))
                with psycopg.connect(self.url) as conn:
                    row = conn.execute("SELECT unit_price, available, attributes->>'cabinClass', attributes->>'simulated' "
                                       "FROM cdp.products WHERE source_ref = %s",
                                       ('demo:business:' + economy['sourceRef'],)).fetchone()
            finally:
                refs = [p['sourceRef'] for p in products]
                with psycopg.connect(self.url) as conn:
                    # combo_items parse trên toàn catalog: combo có sẵn trong DB cũng có thể trỏ tới tuyến vừa nạp
                    conn.execute("DELETE FROM catalog.combo_items WHERE combo_product_id IN "
                                 "(SELECT product_id FROM cdp.products WHERE source_ref = ANY(%s)) OR item_product_id IN "
                                 "(SELECT product_id FROM cdp.products WHERE source_ref = ANY(%s))", (refs, refs))
                    conn.execute("DELETE FROM cdp.products WHERE source_ref = ANY(%s)",
                                 (refs + ['demo:business:' + r for r in refs],))
        self.assertGreaterEqual(counts['simulatedBusinessWritten'], 1)
        # vé mô phỏng là dữ liệu demo: vẫn đồng bộ nhưng không hiện thành bước con / dòng log trên monitor (08/10/2026)
        self.assertTrue(sink and not any('thương gia' in e['name'] for e in sink))
        self.assertFalse([line for line in lines if 'thương gia' in line])
        self.assertEqual(row[2:], ('BUSINESS', 'true'))
        self.assertEqual(int(row[0]), 5_520_000)  # 2.083.000 × 2,65
        self.assertFalse(row[1])  # the same modal carried a real business fare for this journey: the real one wins


if __name__ == '__main__':
    unittest.main()
