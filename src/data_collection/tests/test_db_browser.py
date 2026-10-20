import datetime as dt
import decimal
import os
import re
import time
import unicodedata
import unittest
import uuid

from db_browser import COUNT_CAP, MASK, DbBrowser, accent_regex, fold, is_secret, jsonable, masked
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

    def test_fold_drops_case_and_vietnamese_marks_even_in_nfd(self):
        self.assertEqual(fold('Bà Nà HILLS Đà Lạt Ỷ'), 'ba na hills da lat y')
        self.assertEqual(fold(unicodedata.normalize('NFD', 'Hà Nội Ước')), 'ha noi uoc')

    def test_accent_regex_matches_every_case_and_accent_and_escapes_symbols(self):
        pattern = re.compile(accent_regex('da  nang'))  # lớp ký tự + \s+ dùng được cho cả PostgreSQL ARE
        for text in ('Đà Nẵng', 'DA NANG', 'đá   nặng', 'Dà Nang'):
            self.assertTrue(pattern.search(text), text)
        self.assertFalse(pattern.search('dan ang'))
        symbols = re.compile(accent_regex('a.b+c(1)'))
        self.assertTrue(symbols.search('x a.b+c(1) y'))
        self.assertFalse(symbols.search('axb+c(1)'))


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

    def test_graph_has_every_table_with_full_columns_and_both_edge_kinds(self):
        g = self.db.graph()
        tables = {t['name']: t for t in g['tables']}
        self.assertEqual(set(tables), {t['name'] for t in self.db.tables()['tables']})
        products = {c['name']: c for c in tables['cdp.products']['columns']}
        self.assertEqual(len(products), 13)  # đủ 13 cột, không tóm tắt
        self.assertTrue(products['product_id']['pk'])
        users = {c['name']: c for c in tables['app.users']['columns']}
        self.assertTrue(users['password_hash']['secret'])
        self.assertEqual(users['cdp_user_id']['fk'], 'cdp.profiles')
        edges = {(e['from'], e['to'], tuple(e['columns']), e['kind']) for e in g['edges']}
        self.assertIn(('app.booking_items', 'cdp.products', ('product_id',), 'fk'), edges)
        self.assertIn(('catalog.combo_items', 'cdp.products', ('combo_product_id', 'combo_taxonomy'), 'fk'), edges)
        self.assertIn(('catalog.product_meta', 'cdp.products', ('product_id',), 'convention'), edges)
        self.assertIn(('cdp.products', 'cdp.products', ('attributes.parentProductId',), 'convention'), edges)
        for e in g['edges']:  # mọi cạnh trỏ tới bảng / cột có thật (để vẽ được)
            self.assertIn(e['to'], tables)
            if e['kind'] == 'fk':
                cols = {c['name'] for c in tables[e['from']]['columns']}
                self.assertTrue(set(e['columns']) <= cols, e)

    def test_row_key_must_identify_one_row(self):
        with self.assertRaises(ValueError):
            self.db.row('cdp.products', {})
        with self.assertRaises(ValueError):
            self.db.row('cdp.products', {'taxonomy': 'flight'})

    # -- tìm nhanh cả database (chốt 2026-10-13)
    def test_quick_search_ignores_case_and_accents_and_ranks_the_whole_phrase_first(self):
        out = self.db.search('ba na')
        products = next(g for g in out['groups'] if g['table'] == 'cdp.products')
        self.assertEqual(out['groups'][0]['table'], 'cdp.products')  # bảng hay tìm nhất đứng đầu
        self.assertIn('Bà Nà', products['rows'][0]['values']['name'])
        self.assertIn('name', products['rows'][0]['matched'])
        self.assertEqual(self.db.search('BÀ NÀ')['groups'][0]['rows'], products['rows'])
        self.assertEqual(self.db.search('Sun World Bà Nà Hills')['groups'][0]['rows'][0]['values']['name'],
                         'Sun World Bà Nà Hills')
        self.assertEqual(self.db.search('x'), {'q': 'x', 'groups': [], 'tables': 0, 'ms': 0})  # dưới 2 ký tự: không tìm

    def test_quick_search_needs_every_word_in_any_short_text_column(self):
        rows = next(g for g in self.db.search('vinpearl phu quoc', limit=50)['groups']
                    if g['table'] == 'cdp.products')['rows']
        self.assertTrue(rows)
        for row in rows:
            text = fold(' '.join(str(v) for v in row['values'].values()))
            self.assertIn('vinpearl', text)
            self.assertIn('phu quoc', text)

    def test_quick_search_by_uuid_email_and_reference_code(self):
        item = self.db.rows('app.booking_items', limit=1)['rows'][0]
        tables = {g['table']: g for g in self.db.search(item['product_id'])['groups']}
        self.assertEqual(tables['cdp.products']['rows'][0]['key'], {'product_id': item['product_id']})
        self.assertIn('app.booking_items', tables)
        user = self.db.rows('app.users', limit=1)['rows'][0]
        hit = next(g for g in self.db.search(user['email'].upper())['groups'] if g['table'] == 'app.users')
        self.assertEqual(hit['rows'][0]['key'], {'user_id': user['user_id']})
        booking = self.db.rows('app.bookings', limit=1)['rows'][0]
        hit = next(g for g in self.db.search(booking['reference_code'])['groups'] if g['table'] == 'app.bookings')
        self.assertEqual(hit['rows'][0]['key'], {'booking_id': booking['booking_id']})

    def test_quick_search_never_reads_secret_columns(self):
        out = self.db.search('$argon2')
        self.assertFalse([g for g in out['groups'] if g['table'] in ('app.users', 'app.refresh_tokens')])
        for group in self.db.search('test')['groups']:
            self.assertFalse([c for c in group['columns'] if is_secret(c)], group['table'])

    def test_a_table_that_times_out_is_reported_and_the_others_still_answer(self):
        import psycopg
        from psycopg.rows import dict_row

        slow = DbBrowser(self.url, connect=lambda: psycopg.connect(
            self.url, row_factory=dict_row, options='-c default_transaction_read_only=on -c statement_timeout=1'))
        slow._meta, slow._meta_at = self.db.metadata(), time.monotonic()  # chỉ câu lệnh tìm bị quá giờ
        out = slow.search('ba na')
        self.assertGreater(out['tables'], 5)
        self.assertTrue(any(g.get('error') == 'quá giờ' for g in out['groups']), out['groups'])

    def test_table_filter_ignores_accents_needs_every_word_and_caps_the_count(self):
        plain, accented = self.db.rows('cdp.products', q='da nang', limit=1), self.db.rows('cdp.products', q='Đà Nẵng', limit=1)
        self.assertGreater(plain['total'], 0)
        self.assertEqual(plain['total'], accented['total'])
        both = self.db.rows('cdp.products', q='vinpearl phu quoc', limit=1)['total']
        self.assertLessEqual(both, self.db.rows('cdp.products', q='vinpearl', limit=1)['total'])
        deep = self.db.rows('cdp.products', q='vinpearl phu quoc', limit=1, deep=True)['total']
        self.assertGreater(deep, 11)  # các từ không cần đứng liền nhau (cụm liền chỉ có 11 dòng)
        self.assertGreaterEqual(deep, both)  # tìm sâu = thêm mô tả, JSON
        rows = self.db.rows('cdp.products', q='Đà Nẵng', limit=200)['rows']
        light = [fold(' '.join(str(r[c]) for c in ('name', 'destination', 'source_ref', 'taxonomy'))) for r in rows]
        self.assertTrue(all('da' in t and 'nang' in t for t in light))  # mặc định không khớp nhờ mô tả / attributes
        common = self.db.rows('cdp.products', q='a', limit=1)
        self.assertEqual((common['total'], common['totalCapped']), (COUNT_CAP, True))
        self.assertFalse(self.db.rows('cdp.products', limit=1)['totalCapped'])  # không tìm: đếm đủ


if __name__ == '__main__':
    unittest.main()
