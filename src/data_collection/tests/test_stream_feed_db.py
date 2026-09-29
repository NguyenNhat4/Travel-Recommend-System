"""L4 với Postgres thật: nạp DB theo phần nhiều lô rồi nạp chính thức, không dòng trùng, không conflict.

Chỉ chạy khi có `STREAM_TEST_ADMIN_URL` (superuser, vd. Postgres docker local). Test tạo database tạm
`vota_stream_test_<pid>`, dựng schema từ `db/vota_schema.sql`, chạy, rồi xoá database đó; không chạm database `vota`.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import stream_feed as sf
from fresh_catalog_db import load_into_db, validate_catalog
from normalise import product_id
from tests.test_stream_feed import item

ADMIN = os.environ.get('STREAM_TEST_ADMIN_URL')
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT.parents[1] / 'db' / 'vota_schema.sql'


@unittest.skipUnless(ADMIN, 'cần STREAM_TEST_ADMIN_URL (Postgres superuser) để chạy với DB thật')
class StreamLoadRealDbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.psycopg = psycopg
        cls.name = f'vota_stream_test_{os.getpid()}'
        with psycopg.connect(ADMIN, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS {cls.name}')
            conn.execute(f'CREATE DATABASE {cls.name} TEMPLATE template0')  # template1 có thể lệch collation
        parsed = urlparse(ADMIN)
        cls.url = urlunparse(parsed._replace(path=f'/{cls.name}'))
        with psycopg.connect(cls.url, autocommit=True) as conn:
            conn.execute(SCHEMA.read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        with cls.psycopg.connect(ADMIN, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS {cls.name} WITH (FORCE)')

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run = Path(tmp.name)
        (self.run / 'normalised').mkdir()
        for stem in ('agoda_hotels', 'booking_hotels'):
            (self.run / 'normalised' / f'{stem}.meta.json').write_text(json.dumps({'records': 30, 'errors': 0}),
                                                                       encoding='utf-8')
        with self.psycopg.connect(self.url, autocommit=True) as conn:
            conn.execute('TRUNCATE cdp.products CASCADE')

    def draft(self, rows):
        (self.run / 'preview').mkdir(exist_ok=True)
        (self.run / 'preview' / 'products.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                                                            encoding='utf-8')

    def products(self):
        with self.psycopg.connect(self.url) as conn:
            rows = conn.execute('SELECT product_id::text, source_ref, available, attributes FROM cdp.products '
                                'ORDER BY source_ref').fetchall()
        return {r[1]: {'id': r[0], 'available': r[2], 'attributes': r[3]} for r in rows}

    def feeder(self):
        return sf.DbFeeder(self.run, self.url, ROOT, load_into_db,
                           lambda rows: validate_catalog(rows, allow_external_parents=True),
                           min_records=20, max_error_percent=5, log=lambda m: None)

    def test_batches_then_official_load_keep_one_row_per_hotel(self):
        feeder = self.feeder()
        agoda_room = item('agoda:hotel:1:room:a', level='room', parent='agoda:hotel:1')
        self.draft([item('agoda:hotel:1'), agoda_room])  # agoda về trước
        self.assertEqual(feeder()['written'], 2)
        booking = item('booking:hotel:9', same_as=['agoda:hotel:1'])  # booking về sau, thành dòng giữ
        booking_room = item('booking:hotel:9:room:b', level='room', parent='booking:hotel:9')
        agoda_room_now = item('agoda:hotel:1:room:a', level='room', parent='booking:hotel:9')
        self.draft([booking, booking_room, agoda_room_now])
        entry = feeder()  # lô 2: dòng booking khớp dòng agoda đã nạp qua sameAs
        self.assertEqual((entry['rows'], entry['counts']['new']), (3, 1))  # chỉ phòng booking là dòng mới
        self.assertIsNone(feeder())  # không đổi nữa → không nạp
        rows = self.products()
        self.assertEqual(sorted(rows), ['agoda:hotel:1', 'agoda:hotel:1:room:a', 'booking:hotel:9:room:b'])
        hotel = rows['agoda:hotel:1']
        self.assertEqual(hotel['attributes']['sameAs'], ['booking:hotel:9'])
        self.assertEqual(rows['booking:hotel:9:room:b']['attributes']['parentProductId'], hotel['id'])
        self.assertEqual(rows['agoda:hotel:1:room:a']['attributes']['parentProductId'], hotel['id'])
        # bước nạp chính thức cuối lượt trên cùng catalog: không lỗi conflict, không thêm dòng
        official = self.run / 'official'
        official.mkdir()
        (official / 'products.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n'
                                                         for r in (booking, booking_room, agoda_room_now)), encoding='utf-8')
        counts = load_into_db(official / 'products.jsonl', None, self.url, ROOT)
        self.assertEqual((counts['new'], counts['mergedAway']), (0, 0))
        self.assertEqual(len(self.products()), 3)

    def test_rows_loaded_separately_then_merged_leave_one_visible(self):
        feeder = self.feeder()
        self.draft([item('booking:hotel:9'), item('agoda:hotel:1')])
        feeder()
        self.draft([item('booking:hotel:9', same_as=['agoda:hotel:1'])])
        entry = feeder()
        self.assertEqual(entry['counts']['mergedAway'], 1)
        rows = self.products()
        self.assertEqual((rows['agoda:hotel:1']['available'], rows['agoda:hotel:1']['attributes']['mergedInto']),
                         (False, product_id('booking:hotel:9')))
        self.assertTrue(rows['booking:hotel:9']['available'])
        # lượt sau (nạp lại cả catalog) không lỗi "sourceRef/sameAs conflict"
        again = self.run / 'again'
        again.mkdir()
        (again / 'products.jsonl').write_text(json.dumps(item('booking:hotel:9', same_as=['agoda:hotel:1'])) + '\n',
                                              encoding='utf-8')
        load_into_db(again / 'products.jsonl', None, self.url, ROOT)
        self.assertEqual(len(self.products()), 2)


if __name__ == '__main__':
    unittest.main()
