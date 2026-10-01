import copy
import gzip
import json
import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

import psycopg

from data_collection.seed.database import PRODUCT, copy_rows
from data_collection.seed.load_products import convert
from data_collection.seed.release_flights import BUNDLE, import_flights, load_bundle

TODAY = date(2026, 9, 30)
ROOT = Path(__file__).resolve().parents[3]


class BundleTests(unittest.TestCase):
    def test_real_quotes_are_grounded_and_unique(self):
        rows = load_bundle()
        self.assertEqual(len(rows), 43)
        self.assertEqual(len({r['attributes']['parentProductId'] for r in rows}), 6)
        self.assertTrue(all(len(r) == 13 for r in rows))
        self.assertTrue(all('MoMo' in r['description'] for r in rows))

    def test_expired_quotes_never_shift_to_future_dates(self):
        rows, _ = convert(load_bundle(), {}, date(2026, 10, 16), real_flight_dates=True)
        self.assertTrue(all(not r['available'] for r in rows))
        self.assertTrue(all(r['attributes']['departureAt'].startswith('2026-10-15') for r in rows))

    def test_tampering_fails_before_database_access(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'bundle'
            shutil.copytree(BUNDLE.parent, root)
            (root / 'evidence.json.gz').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                load_bundle(root / BUNDLE.name)


@unittest.skipUnless(os.environ.get('RELEASE_TEST_DATABASE_URL'), 'isolated PostgreSQL required')
class ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = os.environ['RELEASE_TEST_DATABASE_URL']
        with psycopg.connect(cls.url) as c:
            if not c.execute('select current_database()').fetchone()[0].startswith('vota_business_test_'):
                raise RuntimeError('integration tests require a disposable vota_business_test_* database')
            ddl = (ROOT / 'db/vota_schema.sql').read_text()
            c.execute(ddl[:ddl.index('-- cdp.profiles')])
        cls.rows = load_bundle()
        wanted = {r['attributes']['parentProductId'] for r in cls.rows}
        with gzip.open(BUNDLE.parent.parent / '2026-09-30/products.jsonl.gz', 'rt') as stream:
            parents = [r for line in stream if (r := json.loads(line))['productId'] in wanted]
        cls.parents, _ = convert(parents, {}, TODAY, real_flight_dates=True)

    def setUp(self):
        with psycopg.connect(self.url) as c:
            c.execute('TRUNCATE cdp.products')
            copy_rows(c, 'cdp.products', PRODUCT, self.parents)

    def test_insert_replay_and_keep_newer_price(self):
        self.assertEqual(import_flights(self.url, self.rows, TODAY)['inserted'], 43)
        pid = self.rows[0]['productId']
        with psycopg.connect(self.url) as c:
            c.execute('UPDATE cdp.products SET unit_price=9999999 WHERE product_id=%s', (pid,))
        self.assertEqual(import_flights(self.url, self.rows, TODAY)['inserted'], 0)
        with psycopg.connect(self.url) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM cdp.products').fetchone()[0], 49)
            self.assertEqual(c.execute('SELECT unit_price FROM cdp.products WHERE product_id=%s', (pid,)).fetchone()[0], 9999999)

    def test_missing_parent_aborts_whole_import(self):
        rows = copy.deepcopy(self.rows)
        rows[-1]['attributes']['parentProductId'] = '00000000-0000-0000-0000-000000000000'
        with self.assertRaisesRegex(ValueError, 'parent'):
            import_flights(self.url, rows, TODAY)
        with psycopg.connect(self.url) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM cdp.products').fetchone()[0], 6)

    def test_constraint_error_rolls_back_all_insertions(self):
        rows = copy.deepcopy(self.rows)
        rows[-1]['sourceRef'] = rows[0]['sourceRef']
        with self.assertRaises(psycopg.errors.UniqueViolation):
            import_flights(self.url, rows, TODAY)
        with psycopg.connect(self.url) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM cdp.products').fetchone()[0], 6)
