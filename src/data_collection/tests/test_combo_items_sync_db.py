"""catalog.combo_items parse lại từ cdp.products với Postgres thật: combo không có trong lượt cào vẫn được sửa, chạy lại không ghi.

Chỉ chạy khi có `STREAM_TEST_ADMIN_URL` (superuser, vd. Postgres docker local). Test tạo database tạm
`vota_combo_test_<pid>`, dựng schema từ `db/vota_schema.sql`, chạy, rồi xoá database đó; không chạm database `vota`.
"""
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from fresh_catalog_db import load_into_db, maintain_catalog, sync_combo_items
from normalise import PRODUCT_FIELDS, product_id

ADMIN = os.environ.get('STREAM_TEST_ADMIN_URL')
ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT.parents[1] / 'db' / 'vota_schema.sql'
TICKET_REF, COMBO_REF = 'vinpearl:attraction:ch-std', 'vinpearl:combo:ch-04'
STALE = ('Combo Phá Đảo 04 Khu', 'other')  # bản parse trước khi thêm "Vé vào cửa <địa điểm>"


def item(ref, name, taxonomy):
    values = {'productId': product_id(ref), 'name': name, 'taxonomy': taxonomy, 'destination': 'Nghệ An',
              'description': 'Vé vào cửa trực tiếp khu vui chơi VinWonders Cửa Hội sử dụng trong ngày.',
              'attributes': {'venue': 'VinWonders Cửa Hội'}, 'unitPrice': 300000, 'currency': 'VND', 'available': True,
              'availableFrom': None, 'availableTo': None, 'imageUrl': None, 'sourceRef': ref}
    return {k: values[k] for k in PRODUCT_FIELDS}


TICKET = item(TICKET_REF, '[VinWonders Cửa Hội] - Vé vào cửa tiêu chuẩn', 'attraction')
COMBO = item(COMBO_REF, '[VinWonders Cửa Hội] - Combo Phá Đảo 04 Khu', 'combo')


@unittest.skipUnless(ADMIN, 'cần STREAM_TEST_ADMIN_URL (Postgres superuser) để chạy với DB thật')
class ComboItemsSyncRealDbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.psycopg = psycopg
        cls.name = f'vota_combo_test_{os.getpid()}'
        with psycopg.connect(ADMIN, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS {cls.name}')
            conn.execute(f'CREATE DATABASE {cls.name} TEMPLATE template0')
        cls.url = urlunparse(urlparse(ADMIN)._replace(path=f'/{cls.name}'))
        with psycopg.connect(cls.url, autocommit=True) as conn:
            conn.execute(SCHEMA.read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        with cls.psycopg.connect(ADMIN, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS {cls.name} WITH (FORCE)')

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        with self.psycopg.connect(self.url, autocommit=True) as conn:
            conn.execute('TRUNCATE cdp.products CASCADE')
        self.load([TICKET, COMBO], 'first')

    def load(self, rows, name):
        run = self.tmp / name
        run.mkdir()
        (run / 'products.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return load_into_db(run / 'products.jsonl', None, self.url, ROOT)

    def items(self):
        with self.psycopg.connect(self.url) as conn:
            return conn.execute('SELECT label, item_kind, item_product_id::text, source FROM catalog.combo_items '
                                'WHERE combo_product_id = %s ORDER BY position', (product_id(COMBO_REF),)).fetchall()

    def make_stale(self):
        with self.psycopg.connect(self.url) as conn:
            conn.execute('DELETE FROM catalog.combo_items WHERE combo_product_id = %s', (product_id(COMBO_REF),))
            conn.execute('INSERT INTO catalog.combo_items (combo_product_id, position, label, item_kind) VALUES (%s, 1, %s, %s)',
                         (product_id(COMBO_REF), *STALE))

    def expected(self):
        return [('Vé vào cửa VinWonders Cửa Hội', 'attraction', product_id(TICKET_REF), 'description_parse')]

    def test_load_writes_components_mapped_on_the_db_catalog(self):
        self.assertEqual(self.items(), self.expected())

    def test_maintenance_reparses_a_combo_no_crawl_saw_then_writes_nothing(self):
        self.make_stale()
        first = maintain_catalog(self.url, today=date.today())
        self.assertEqual((first['combos'], first['combosChanged'], first['comboItemsWritten']), (1, 1, 1))
        self.assertEqual(self.items(), self.expected())
        again = maintain_catalog(self.url, today=date.today())
        self.assertEqual((again['combosChanged'], again['comboItemsWritten']), (0, 0))

    def test_load_without_any_combo_still_fixes_stored_components(self):
        self.make_stale()
        counts = self.load([TICKET], 'blocked-combo-source')  # nguồn combo bị chặn: lượt chỉ có vé
        self.assertEqual(counts['combosChanged'], 1)
        self.assertEqual(self.items(), self.expected())

    def test_dry_run_reports_without_writing(self):
        self.make_stale()
        with self.psycopg.connect(self.url) as conn:
            conn.read_only = True
            report = sync_combo_items(conn, dry_run=True)
        self.assertEqual((report['combosChanged'], report['comboItemsWritten'], report['combosLabelsChanged']), (1, 0, 1))
        self.assertEqual(report['changedCombos'], [{'productId': product_id(COMBO_REF), 'name': COMBO['name'],
                                                    'before': 1, 'after': 1, 'labelsChanged': True,
                                                    'labelsBefore': [STALE[0]],
                                                    'labelsAfter': ['Vé vào cửa VinWonders Cửa Hội']}])
        self.assertEqual(self.items(), [(*STALE, None, 'description_parse')])

    def test_reviewed_rows_are_kept_and_invalid_ones_never_break_the_foreign_key(self):
        manual = self.tmp / 'combo_items_manual.jsonl'
        good = {'combo_product_id': product_id(COMBO_REF), 'position': 2, 'label': 'Ẩm thực', 'item_kind': 'meal',
                'item_product_id': None, 'quantity': 1, 'unit': 'suất', 'is_optional': False, 'source': 'manual',
                'confidence': None, 'evidence': 'duyệt tay'}
        wrong_kind = {**good, 'position': 3, 'item_kind': 'golf', 'item_product_id': product_id(TICKET_REF), 'unit': 'lượt'}
        manual.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in (good, wrong_kind)), encoding='utf-8')
        with self.psycopg.connect(self.url) as conn:
            counts = sync_combo_items(conn, manual_path=manual)
        self.assertEqual((counts['combosChanged'], counts['manualSkipped']), (1, 1))
        self.assertEqual(self.items(), self.expected() + [('Ẩm thực', 'meal', None, 'manual')])


if __name__ == '__main__':
    unittest.main()
