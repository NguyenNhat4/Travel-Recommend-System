"""Chạy liên tục sau chuẩn hoá (L3–L5, docs/plan/2026-09-28-pipeline-chay-lien-tuc.md): gộp nháp định kỳ, nạp DB theo
phần, index theo phần; và sửa prepare_rows để nạp nhiều lần không tạo dòng trùng khi dòng giữ lúc gộp trùng đổi."""
import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

import stream_feed as sf
from fresh_catalog_db import prepare_rows, validate_catalog
from normalise import PRODUCT_FIELDS, product_id

NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)


def item(ref, *, taxonomy='hotel', level='property', parent=None, same_as=None, price=1000000, name=None):
    attrs = {'level': level} if level else {}
    if parent:
        attrs['parentProductId'] = product_id(parent)
    if same_as:
        attrs['sameAs'] = list(same_as)
    values = {'productId': product_id(ref), 'name': name or ref, 'taxonomy': taxonomy, 'destination': 'Nha Trang',
              'description': 'mô tả', 'attributes': attrs, 'unitPrice': price, 'currency': 'VND', 'available': True,
              'availableFrom': None, 'availableTo': None, 'imageUrl': None, 'sourceRef': ref}
    return {k: values[k] for k in PRODUCT_FIELDS}


def db_rows(prepared):
    """Trạng thái DB sau một lần nạp (upsert theo product_id)."""
    return {str(r['product_id']): r for r in prepared}


def load(state, fresh):
    rows, counts = prepare_rows(fresh, list(state.values()), set(), '2026-09-28', now=NOW)
    state.update(db_rows(rows))
    return counts


class PrepareRowsAcrossBatchesTests(unittest.TestCase):
    def test_keeper_switches_after_first_load_keeps_one_product(self):
        """agoda về trước và được nạp; booking về sau thành dòng giữ, sameAs chứa ref agoda → vẫn một product_id."""
        state = {}
        load(state, [item('agoda:hotel:1')])
        counts = load(state, [item('booking:hotel:9', same_as=['agoda:hotel:1'])])
        self.assertEqual(list(state), [product_id('agoda:hotel:1')])
        row = state[product_id('agoda:hotel:1')]
        self.assertEqual(row['source_ref'], 'agoda:hotel:1')  # cột tĩnh giữ nguyên
        self.assertEqual(row['attributes']['sameAs'], ['booking:hotel:9'])
        self.assertEqual((counts['new'], counts['refreshed']), (0, 1))
        # lần nạp sau (và lượt sau) không lỗi "sourceRef/sameAs conflict"
        load(state, [item('booking:hotel:9', same_as=['agoda:hotel:1'])])
        load(state, [item('agoda:hotel:1')])
        self.assertEqual(len(state), 1)

    def test_two_existing_rows_merged_later_leave_one_visible(self):
        """booking và agoda cùng khách sạn đã nạp riêng; lô sau gộp chúng → dòng agoda ẩn, trỏ mergedInto dòng booking."""
        state = {}
        load(state, [item('booking:hotel:9'), item('agoda:hotel:1')])
        counts = load(state, [item('booking:hotel:9', same_as=['agoda:hotel:1'])])
        self.assertEqual(counts['mergedAway'], 1)
        away = state[product_id('agoda:hotel:1')]
        self.assertEqual((away['available'], away['attributes']['mergedInto']), (False, product_id('booking:hotel:9')))
        self.assertTrue(state[product_id('booking:hotel:9')]['available'])
        # dòng đã gộp không còn giữ ref: lần sau không conflict, không gộp lại lần nữa
        again = load(state, [item('booking:hotel:9', same_as=['agoda:hotel:1'])])
        self.assertEqual(again['mergedAway'], 0)
        self.assertEqual(len(state), 2)

    def test_room_is_reparented_to_the_kept_row(self):
        state = {}
        load(state, [item('agoda:hotel:1')])
        load(state, [item('booking:hotel:9', same_as=['agoda:hotel:1']),
                     item('booking:hotel:9:room:a', level='room', parent='booking:hotel:9')])
        room = state[product_id('booking:hotel:9:room:a')]
        self.assertEqual(room['attributes']['parentProductId'], product_id('agoda:hotel:1'))

    def test_single_load_is_unchanged(self):
        """Một lần nạp như lượt theo lô: kết quả như trước khi sửa (không sameAs mới, không mergedAway)."""
        state = {}
        counts = load(state, [item('booking:hotel:9', same_as=['agoda:hotel:1']), item('vinpearl:tour:1', taxonomy='attraction', level=None)])
        self.assertEqual((counts['new'], counts['mergedAway']), (2, 0))
        self.assertEqual(state[product_id('booking:hotel:9')]['attributes']['sameAs'], ['agoda:hotel:1'])


def meta(records, errors=0, status='streaming'):
    return {'records': records, 'errors': errors, 'status': status}


class SelectReadyTests(unittest.TestCase):
    def select(self, products, metas, loaded=()):
        return sf.select_ready(products, metas, set(loaded), min_records=20, max_error_percent=5,
                               validate=lambda rows: validate_catalog(rows, allow_external_parents=True))

    def test_rules(self):
        hotel = item('booking:hotel:1')
        room = item('booking:hotel:1:room:a', level='room', parent='booking:hotel:1')
        orphan = item('booking:hotel:2:room:a', level='room', parent='booking:hotel:2')
        trip = item('trip:hotel:5')
        combo = item('trip:combo:1', taxonomy='combo', level=None)
        few = item('agoda:hotel:3')
        broken = dict(item('booking:hotel:4'), description='')
        ready, held = self.select([hotel, room, orphan, trip, combo, few, broken],
                                  {'booking_hotels': meta(30, 1), 'agoda_hotels': meta(5), 'trip_hotels': meta(50)})
        self.assertEqual([r['sourceRef'] for r in ready], ['booking:hotel:1', 'booking:hotel:1:room:a'])
        self.assertEqual(sum(held.values()), 5)
        self.assertTrue(any('khách sạn Trip' in k for k in held))
        self.assertTrue(any('combo' in k for k in held))
        self.assertTrue(any('agoda' in k for k in held))
        self.assertTrue(any('kiểm tra dòng' in k for k in held))
        self.assertTrue(any('cha chưa nạp' in k for k in held))

    def test_error_rate_or_failed_checkpoint_holds_the_site(self):
        hotel = item('booking:hotel:1')
        self.assertEqual(self.select([hotel], {'booking_hotels': meta(30, 5)})[0], [])
        self.assertEqual(self.select([hotel], {'booking_hotels': meta(30, 0, 'failed')})[0], [])

    def test_finished_site_below_minimum_is_ready_but_a_streaming_one_is_not(self):
        # 2026-09-29 (P2): nguồn cào xong (mọi checkpoint của site đã chốt ok) không cần đủ min_records
        hotel = item('agoda:hotel:3')
        self.assertEqual(self.select([hotel], {'agoda_hotels': meta(5, status='ok')})[0], [hotel])
        _, held = self.select([hotel], {'agoda_hotels': meta(5)})
        self.assertTrue(any('đang cào' in k for k in held))
        # site có một checkpoint đã chốt, một checkpoint còn đang cào: chưa đủ → vẫn chờ
        flight = item('trip:route:HAN-CXR', taxonomy='flight', level='route')
        partial = {'trip_flights': meta(2, status='ok'), 'trip_attractions': meta(5)}
        self.assertEqual(self.select([flight], partial)[0], [])
        done = {'trip_flights': meta(2, status='ok'), 'trip_attractions': meta(5, status='ok')}
        self.assertEqual(self.select([flight], done)[0], [flight])
        # đã chốt nhưng tỉ lệ lỗi vượt ngưỡng: vẫn giữ
        self.assertEqual(self.select([hotel], {'agoda_hotels': meta(5, 1, status='ok')})[0], [])

    def test_child_with_parent_loaded_earlier_is_ready(self):
        room = item('booking:hotel:1:room:a', level='room', parent='booking:hotel:1')
        ready, _ = self.select([room], {'booking_hotels': meta(30)}, loaded={product_id('booking:hotel:1')})
        self.assertEqual(len(ready), 1)


class FeederTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run = Path(tmp.name)
        (self.run / 'normalised').mkdir()
        (self.run / 'normalised' / 'booking_hotels.meta.json').write_text(json.dumps(meta(30)), encoding='utf-8')
        self.calls = []

    def draft(self, rows):
        (self.run / 'preview').mkdir(exist_ok=True)
        (self.run / 'preview' / 'products.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')

    def fake_load(self, path, coverage, url, root, report_path=None):
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        self.calls.append((rows, coverage, url))
        return {'dbRowsWritten': len(rows)}

    def feeder(self, load=None):
        return sf.DbFeeder(self.run, 'postgresql://local', Path('.'), load or self.fake_load,
                           lambda rows: validate_catalog(rows, allow_external_parents=True),
                           min_records=20, max_error_percent=5, log=lambda m: None)

    def test_only_new_or_changed_rows_are_loaded(self):
        feeder = self.feeder()
        self.assertIsNone(feeder())  # chưa có catalog đang gộp
        self.draft([item('booking:hotel:1'), item('booking:hotel:2')])
        self.assertEqual(feeder()['rows'], 2)
        self.assertIsNone(feeder())  # không đổi → không nạp
        self.draft([item('booking:hotel:1', price=900000), item('booking:hotel:2'), item('booking:hotel:3')])
        entry = feeder()
        self.assertEqual(sorted(r['sourceRef'] for r in self.calls[-1][0]), ['booking:hotel:1', 'booking:hotel:3'])
        self.assertEqual((entry['n'], feeder.written, self.calls[-1][1], self.calls[-1][2]), (2, 4, None, 'postgresql://local'))
        batches = [json.loads(line) for line in (self.run / 'db_batches.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([b['rows'] for b in batches], [2, 2])
        self.assertTrue((self.run / 'db_batches' / '0002' / 'products.jsonl').is_file())

    def test_failed_load_is_retried_next_cycle(self):
        attempts = []

        def flaky(*args, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise ConnectionError('db down')
            return self.fake_load(*args, **kwargs)
        feeder = self.feeder(flaky)
        self.draft([item('booking:hotel:1')])
        ticker = sf.Ticker('db', feeder, 60, log=lambda m: None)
        self.assertIsNone(ticker.run_once())  # lỗi: ghi log, không làm hỏng lượt
        self.assertEqual(ticker.run_once()['rows'], 1)  # lần sau nạp lại đủ
        lines = (self.run / 'db_batches.jsonl').read_text(encoding='utf-8').splitlines()
        self.assertIn('ConnectionError', json.loads(lines[0])['error'])

    def test_index_runs_only_after_new_db_rows(self):
        feeder = self.feeder()
        reports = []
        index = sf.IndexFeeder(self.run, feeder, lambda path: reports.append(path) or {'embedded': 1}, log=lambda m: None)
        self.assertIsNone(index())
        self.draft([item('booking:hotel:1')])
        feeder()
        self.assertEqual(index()['newDbRows'], 1)
        self.assertIsNone(index())  # không có dòng ghi mới → không gọi Cohere
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].name, 'index_detail.stream.jsonl')


class TickerTests(unittest.TestCase):
    def test_interval_pause_and_kick_are_read_live(self):
        calls, control = [], {'interval': 3600}
        ticker = sf.Ticker('t', lambda: calls.append(1) or {}, 3600, control=lambda: control, log=lambda m: None)
        ticker.start()
        self.addCleanup(ticker.close)
        time.sleep(0.8)
        self.assertEqual(calls, [])  # chưa tới chu kỳ
        control['interval'] = 0.1  # chỉnh sống: áp ở lần kiểm kế tiếp
        deadline = time.monotonic() + 3
        while not calls and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertTrue(calls)
        control['paused'] = True
        time.sleep(0.7)
        paused_at = len(calls)
        time.sleep(1.2)
        self.assertEqual(len(calls), paused_at)  # tạm dừng: không chạy
        control.update(paused=False, interval=3600)
        ticker.kick()  # "chạy ngay"
        deadline = time.monotonic() + 3
        while len(calls) == paused_at and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertEqual(len(calls), paused_at + 1)

    def test_close_waits_for_running_batch(self):
        started, done = threading.Event(), threading.Event()

        def work():
            started.set()
            time.sleep(0.5)
            done.set()
            return {}
        ticker = sf.Ticker('t', work, 0.1, log=lambda m: None).start()
        started.wait(3)
        ticker.close()
        self.assertTrue(done.is_set())


class DraftMergerTests(unittest.TestCase):
    def test_requests_merge_only_when_checkpoints_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            requests = []
            merger = sf.DraftMerger(folder, lambda: requests.append(1))
            self.assertIsNone(merger())
            (folder / 'a.meta.json').write_text('{}', encoding='utf-8')
            self.assertIsNotNone(merger())
            self.assertIsNone(merger())
            time.sleep(0.01)
            (folder / 'a.meta.json').write_text('{"x": 1}', encoding='utf-8')
            self.assertIsNotNone(merger())
            self.assertEqual(len(requests), 2)



class StreamSettingsTests(unittest.TestCase):
    def test_stream_settings_have_their_own_group_and_are_off_by_default(self):
        import fresh_settings as fs
        fields = {f.key: f for f in fs.FIELDS if f.key.startswith('stream.')}
        self.assertEqual({f.group for f in fields.values()}, {'stream'})
        self.assertIn('stream', dict(fs.GROUPS))
        self.assertEqual([fields[k].default for k in ('stream.enabled', 'stream.db', 'stream.index')], [False] * 3)


class StreamLiveControlTests(unittest.TestCase):
    def test_stream_keys_validate_interval_pause_and_kick(self):
        from collectors import live_control as lc
        self.assertEqual(lc.validate('stream.db', {'interval': 20, 'paused': True}), {'interval': 20.0, 'paused': True})
        self.assertIn('kickAt', lc.validate('stream.index', {'kick': True}))
        self.assertEqual(lc.validate('stream.merge', {'interval': None}), {'interval': None})
        for key, changes in (('stream.db', {'interval': 5}), ('stream.index', {'interval': 9000}),
                             ('stream.db', {'delay': 3}), ('stream.db', {'kick': False}), ('stream.db', {}),
                             ('stream.db', {'interval': True}), ('stream.normalise', {'paused': 'yes'})):
            with self.subTest(key=key, changes=changes), self.assertRaises(lc.LiveControlError):
                lc.validate(key, changes)

    def test_monitor_write_reaches_the_ticker_through_the_file(self):
        """Nút trên monitor ghi live_control.json; Ticker của job đọc lại file đó (chu kỳ, tạm dừng, chạy ngay)."""
        from collectors import live_control as lc
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / lc.FILE_NAME
            reader = lc.Reader(path, 'run-1')
            calls = []
            ticker = sf.Ticker('db', lambda: calls.append(1) or {}, 3600, lambda: reader.get('stream.db'), log=lambda m: None)
            ticker.start()
            self.addCleanup(ticker.close)
            time.sleep(0.8)
            self.assertEqual(calls, [])
            lc.write(path, 'run-1', 'stream.db', {'kick': True})
            deadline = time.monotonic() + 3
            while not calls and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertEqual(len(calls), 1)  # chạy ngay dù chu kỳ 3600 s
            lc.write(path, 'run-1', 'stream.db', {'paused': True, 'interval': 10})
            time.sleep(1.2)
            self.assertEqual(ticker.settings(), (10.0, True))
            lc.write(path, 'other-run', 'stream.db', {'interval': 20})  # file của lượt khác: không áp
            time.sleep(1.2)
            self.assertEqual(ticker.settings(), (3600, False))

    def test_crawl_keys_are_unchanged(self):
        from collectors import live_control as lc
        self.assertEqual(lc.validate('booking', {'delay': 3}), {'delay': 3.0})
        with self.assertRaises(lc.LiveControlError):
            lc.validate('booking', {'interval': 30})


if __name__ == '__main__':
    unittest.main()
