import datetime as dt
import decimal
import os
import unittest
import uuid

from db_browser import MASK, DbBrowser, is_secret, jsonable, masked
from monitor import prefixed


class PureTests(unittest.TestCase):
    def test_secret_columns(self):
        for name in ('password_hash', 'token_hash', 'request_token', 'client_secret', 'PASSWORD'):
            self.assertTrue(is_secret(name), name)
        for name in ('email', 'product_id', 'contact_phone', 'source_ref'):
            self.assertFalse(is_secret(name), name)

    def test_masked_values_and_json(self):
        row = {'password_hash': '$argon2id$abc', 'token_hash': None, 'price': decimal.Decimal('1494000.00'),
               'rate': decimal.Decimal('2.5'), 'id': uuid.UUID(int=1), 'day': dt.date(2026, 10, 1),
               'attrs': {'nested': decimal.Decimal('3')}}
        out = masked(row)
        self.assertEqual(out['password_hash'], MASK)
        self.assertIsNone(out['token_hash'])  # NULL stays visible as NULL, not a hidden value
        self.assertEqual((out['price'], out['rate'], out['day']), (1494000, 2.5, '2026-10-01'))
        self.assertEqual(out['id'], str(uuid.UUID(int=1)))
        self.assertEqual(out['attrs'], {'nested': 3})
        self.assertEqual(jsonable([decimal.Decimal('1')]), [1])

    def test_prefixed_query_params(self):
        self.assertEqual(prefixed({'f.email': 'a@b', 'f.phone': '\\N', 'table': 'app.users', 'k.id': '1'}, 'f.'),
                         {'email': 'a@b', 'phone': None})


@unittest.skipUnless(os.environ.get('DBX_TEST_DATABASE_URL'), 'isolated seeded PostgreSQL required')
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.url = os.environ['DBX_TEST_DATABASE_URL']
        with psycopg.connect(cls.url) as c:
            if not c.execute('select current_database()').fetchone()[0].startswith('vota_dbx_test_'):
                raise RuntimeError('requires a disposable, seeded vota_dbx_test_* database')
        cls.db = DbBrowser(cls.url)

    def test_every_table_of_the_three_schemas_is_listed_with_counts(self):
        tables = {t['name']: t for t in self.db.tables()['tables']}
        for name in ('cdp.products', 'cdp.profiles', 'cdp.events', 'catalog.combo_items', 'catalog.product_meta',
                     'app.users', 'app.bookings', 'app.booking_items', 'app.payments', 'app.refresh_tokens'):
            self.assertIn(name, tables)
        self.assertEqual(tables['app.users']['rows'], 54)
        self.assertTrue(tables['catalog.product_meta']['view'])
        self.assertGreater(tables['cdp.products']['links'], 3)

    def test_secret_columns_are_masked_and_cannot_be_probed(self):
        page = self.db.rows('app.users', limit=5)
        self.assertIn('password_hash', page['secret'])
        self.assertTrue(all(r['password_hash'] == MASK for r in page['rows']))
        self.assertIn('@', page['rows'][0]['email'])  # everything else is shown
        with self.assertRaises(ValueError):
            self.db.rows('app.users', {'password_hash': MASK})
        with self.assertRaises(ValueError):
            self.db.rows('app.users', sort='password_hash')
        self.assertEqual(self.db.rows('app.users', q='$argon2')['total'], 0)  # search skips secret columns
        self.assertEqual(self.db.rows('app.users', q='$2b$')['total'], 0)

    def test_unknown_names_are_rejected(self):
        for table in ('cdp.products; DROP TABLE cdp.products', 'pg_catalog.pg_authid', 'insider.partners', ''):
            with self.assertRaises(ValueError):
                self.db.rows(table)
        with self.assertRaises(ValueError):
            self.db.rows('cdp.products', {'name; --': 'x'})
        with self.assertRaises(ValueError):
            self.db.rows('cdp.products', sort='nope')

    def test_connection_is_read_only(self):
        import psycopg
        with self.assertRaises(psycopg.errors.ReadOnlySqlTransaction):
            with self.db.connection() as conn:
                conn.execute("UPDATE cdp.products SET name = name WHERE false")

    def test_filters_search_sort_and_paging(self):
        page = self.db.rows('cdp.products', {'taxonomy': 'flight'}, q='giá minh hoạ', sort='unit_price', desc=True,
                            offset=0, limit=3)
        self.assertEqual(len(page['rows']), 3)
        self.assertGreaterEqual(page['total'], 797)
        prices = [r['unit_price'] for r in page['rows']]
        self.assertEqual(prices, sorted(prices, reverse=True))
        self.assertEqual(self.db.rows('cdp.products', limit=10_000)['limit'], 200)
        nulls = self.db.rows('cdp.products', {'image_url': None}, limit=1)
        self.assertGreater(nulls['total'], 0)

    def test_links_both_ways_for_a_booking_item(self):
        item = self.db.rows('app.booking_items', limit=1)['rows'][0]
        detail = self.db.row('app.booking_items', {'booking_item_id': item['booking_item_id']})
        targets = {(o['table'], tuple(o['via'])) for o in detail['outgoing']}
        self.assertIn(('app.bookings', ('booking_id',)), targets)
        self.assertIn(('cdp.products', ('product_id',)), targets)
        product = self.db.row('cdp.products', {'product_id': item['product_id']})
        incoming = {i['table']: i for i in product['incoming'] if i['kind'] == 'fk'}
        self.assertGreaterEqual(incoming['app.booking_items']['count'], 1)
        booking = self.db.row('app.bookings', {'booking_id': item['booking_id']})
        self.assertIn('cdp.profiles', {o['table'] for o in booking['outgoing']})
        profile = self.db.row('cdp.profiles', {'cdp_user_id': booking['row']['cdp_user_id']})
        counts = {i['table']: i['count'] for i in profile['incoming']}
        self.assertGreaterEqual(counts['app.bookings'], 1)
        self.assertGreaterEqual(counts['app.users'], 1)

    def test_convention_links_parent_children_and_simulated_copy(self):
        sim = self.db.rows('cdp.products', q='demo:business:trip:roundtrip', limit=1)['rows'][0]
        detail = self.db.row('cdp.products', {'product_id': sim['product_id']})
        via = {o['via'][0]: o for o in detail['outgoing']}
        self.assertIn('attributes.parentProductId', via)
        original = self.db.row('cdp.products', via['source_ref (vé gốc)']['key'])
        self.assertEqual('demo:business:' + original['row']['source_ref'], sim['source_ref'])
        self.assertIn('source_ref (vé mô phỏng)', {i['via'][0] for i in original['incoming']})
        parent = via['attributes.parentProductId']['key']['product_id']
        route = self.db.row('cdp.products', {'product_id': parent})
        kids = next(i for i in route['incoming'] if i['via'] == ['attributes.parentProductId'])
        self.assertEqual(self.db.children(parent)['total'], kids['count'])
        meta = self.db.row('catalog.product_meta', {'product_id': sim['product_id']})
        self.assertIn('cdp.products', {o['table'] for o in meta['outgoing']})

    def test_row_key_must_identify_one_row(self):
        with self.assertRaises(ValueError):
            self.db.row('cdp.products', {})
        with self.assertRaises(ValueError):
            self.db.row('cdp.products', {'taxonomy': 'flight'})


if __name__ == '__main__':
    unittest.main()
