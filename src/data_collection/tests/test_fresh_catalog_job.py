"""Job cào mới: cửa sổ 30 ngày như seed, hết hạn giá Trip, thứ tự nạp DB → index và cặp đích DB/Weaviate."""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import threading
import time
import unittest
import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import fresh_catalog
import normalise
from fresh_catalog_db import apply_window, maintain_catalog, prepare_rows

AS_OF = date(2026, 9, 24)
HI = AS_OF + timedelta(days=29)


def row(pid, *, taxonomy='hotel', attributes=None, available=True, start=None, end=None, **extra):
    return {'product_id': pid, 'taxonomy': taxonomy, 'attributes': attributes or {'level': 'property'},
            'available': available, 'available_from': start, 'available_to': end,
            'unit_price': 1000000, 'source_ref': f'test:{pid}', **extra}


class ApplyWindowTests(unittest.TestCase):
    """DATABASE_SCHEMA.md #13 và MOCK_DATA_SPEC.md §2 bước 1, dùng lại đúng hàm của seed."""

    def test_source_window_is_clipped_and_missing_source_takes_whole_window(self):
        changed = apply_window([
            row('clipped', attributes={'level': 'property', 'sourceAvailableFrom': '2026-09-01',
                                       'sourceAvailableTo': '2026-10-05'}),
            row('no-source'),
        ], AS_OF)
        self.assertEqual((changed['clipped']['available_from'], changed['clipped']['available_to']),
                         (AS_OF, date(2026, 10, 5)))
        self.assertEqual((changed['no-source']['available_from'], changed['no-source']['available_to']), (AS_OF, HI))

    def test_empty_intersection_marks_unavailable_and_never_reopens(self):
        changed = apply_window([
            row('past', attributes={'level': 'property', 'sourceAvailableFrom': '2026-09-01',
                                    'sourceAvailableTo': '2026-09-10'}, start=date(2026, 9, 5), end=date(2026, 9, 10)),
            row('sold', available=False),
        ], AS_OF)
        self.assertEqual({k: changed['past'][k] for k in ('available', 'available_from', 'available_to')},
                         {'available': False, 'available_from': None, 'available_to': None})
        # Cửa sổ chỉ tắt, không bật lại dòng loader đã đặt chưa khả dụng (hết phòng, giá quá hạn…).
        self.assertFalse(changed['sold']['available'])

    def test_rows_already_inside_the_window_are_not_rewritten(self):
        current = row('same', start=AS_OF.isoformat(), end=HI.isoformat())
        self.assertEqual(apply_window([current], AS_OF), {})
        # Hôm sau cửa sổ cuộn thêm một ngày.
        rolled = apply_window([current], AS_OF + timedelta(days=1))['same']
        self.assertEqual((rolled['available_from'], rolled['available_to']),
                         (AS_OF + timedelta(days=1), HI + timedelta(days=1)))

    def test_flight_takes_a_seen_date_or_moves_into_the_window_and_route_spans_its_flights(self):
        seen = {'level': 'flight', 'parentProductId': 'route', 'datesSeen': ['2026-09-20', '2026-10-02'],
                'departureAt': '2026-09-20T08:30:00+07:00', 'arrivalAt': '2026-09-20T09:45:00+07:00'}
        unseen = {'level': 'flight', 'parentProductId': 'route', 'datesSeen': ['2026-12-01']}
        changed = apply_window([
            row('seen', taxonomy='flight', attributes=seen),
            row('unseen', taxonomy='flight', attributes=unseen),
            row('route', taxonomy='flight', attributes={'level': 'route'}),
        ], AS_OF)
        self.assertEqual(changed['seen']['available_from'], date(2026, 10, 2))
        self.assertEqual(changed['seen']['attributes']['departureAt'], '2026-10-02T08:30:00+07:00')
        self.assertEqual(changed['seen']['attributes']['arrivalAt'], '2026-10-02T09:45:00+07:00')
        self.assertEqual(seen['departureAt'], '2026-09-20T08:30:00+07:00')  # không sửa dict đầu vào
        mock_day = AS_OF + timedelta(days=zlib.crc32(b'unseen') % 30)
        self.assertEqual((changed['unseen']['available_from'], changed['unseen']['available_to']), (mock_day, mock_day))
        self.assertEqual((changed['route']['available_from'], changed['route']['available_to']),
                         (min(date(2026, 10, 2), mock_day), max(date(2026, 10, 2), mock_day)))


class CalendarTests(unittest.TestCase):
    """Lịch 30 ngày như seed (MOCK_DATA_SPEC.md §2 bước 2) cho dòng job cào ghi và mỗi lần cuộn."""

    def setUp(self):
        from data_collection.seed.catalog_meta import room_calendar, ticket_calendar
        self.room_calendar, self.ticket_calendar = room_calendar, ticket_calendar
        self.parent = row('hotel', attributes={'level': 'property', 'brand': 'Vinpearl'})

    def calendar(self, changed, pid):
        availability = changed[pid]['attributes']['availability']
        self.assertEqual((availability['from'], availability['days']), (AS_OF.isoformat(), 30))
        return availability['calendar']

    def test_sparse_trip_samples_keep_the_seed_calendar_and_mark_observed_days(self):
        sampled = {'level': 'room', 'parentProductId': 'hotel',
                   'pricesByDateQueried': ['2026-10-08', '2026-10-24', '2026-11-23'],
                   'pricesByDate': {'2026-10-08': 700000}}
        sold_out = dict(sampled, pricesByDate={})
        changed = apply_window([self.parent, row('open', attributes=sampled), row('closed', attributes=sold_out)], AS_OF)
        view = {'productId': 'open', 'sourceRef': 'test:open', 'attributes': sampled}
        views = {'hotel': {'productId': 'hotel', 'sourceRef': 'test:hotel', 'attributes': self.parent['attributes']}}
        expected = list(self.room_calendar(view, AS_OF, views))
        expected[14] = '1'  # 2026-10-08 có giá; 24/10 và 23/11 nằm ngoài cửa sổ 30 ngày
        self.assertEqual(self.calendar(changed, 'open'), ''.join(expected))
        self.assertEqual(self.calendar(changed, 'closed')[14], '0')  # nguồn xác nhận hết phòng ngày mẫu
        self.assertNotIn('availability', changed['hotel']['attributes'])  # property không có lịch

    def test_dense_real_sweep_uses_the_real_calendar(self):
        days = [(AS_OF + timedelta(days=i)).isoformat() for i in range(30)]
        prices = {day: 900000 for day in days if day != days[3]}
        changed = apply_window([row('dense', attributes={'level': 'room', 'pricesByDateQueried': days,
                                                         'pricesByDate': prices})], AS_OF)
        self.assertEqual(self.calendar(changed, 'dense'), '111' + '0' + '1' * 26)

    def test_unavailable_rows_are_closed_and_tickets_are_cut_to_the_sale_window(self):
        changed = apply_window([
            row('sold', attributes={'level': 'room'}, available=False),
            row('ticket', taxonomy='attraction', attributes={'sourceAvailableTo': '2026-10-03'}),
        ], AS_OF)
        self.assertEqual(self.calendar(changed, 'sold'), '0' * 30)
        self.assertEqual(self.calendar(changed, 'ticket'), self.ticket_calendar('ticket', AS_OF)[:10] + '0' * 20)

    def test_calendar_rolls_with_the_window(self):
        current = apply_window([row('room', attributes={'level': 'room'})], AS_OF)['room']
        self.assertEqual(apply_window([current], AS_OF), {})
        rolled = apply_window([current], AS_OF + timedelta(days=1))['room']['attributes']['availability']
        self.assertEqual(rolled['from'], (AS_OF + timedelta(days=1)).isoformat())


class PrepareRowsTests(unittest.TestCase):
    def test_fresh_rows_record_the_source_window_of_this_run(self):
        record = {'hotelId': '999', 'name': 'Khách sạn thử nghiệm', 'city': 'Nha Trang',
                  'priceDatesQueried': ['2026-10-08'], 'crawledAt': '2026-09-24T00:00:00Z',
                  'rooms': [{'roomId': '8', 'name': 'Suite', 'currency': 'VND',
                             'pricesByDate': {'2026-10-08': 900000}}]}
        prop, rooms = normalise.trip_hotel(record, {})
        fresh = [{key: item[key] for key in normalise.PRODUCT_FIELDS} for item in [prop, *rooms]]
        fresh[0]['availableFrom'], fresh[0]['availableTo'] = '2026-10-08', '2026-10-09'
        old = {'product_id': fresh[1]['productId'], 'source_ref': fresh[1]['sourceRef'], 'unit_price': 1,
               'available': True, 'attributes': {'level': 'room', 'sourceAvailableFrom': '2026-01-01'}}
        prepared, _ = prepare_rows(fresh, [old], {'999'}, '2026-09-24')
        self.assertEqual((prepared[0]['attributes']['sourceAvailableFrom'],
                          prepared[0]['attributes']['sourceAvailableTo']), ('2026-10-08', '2026-10-09'))
        # Nguồn của lượt này không có khoảng ngày: bỏ khoảng cũ để cửa sổ lấy trọn 30 ngày.
        self.assertNotIn('sourceAvailableFrom', prepared[1]['attributes'])

    def test_trip_price_on_a_merged_booking_row_expires_but_other_sources_do_not(self):
        old = datetime(2026, 9, 1, tzinfo=timezone.utc).isoformat()
        merged = {'product_id': 'merged', 'source_ref': 'booking:hotel:1', 'unit_price': 1, 'available': True,
                  'attributes': {'level': 'property', 'sameAs': ['trip:hotel:999'], 'priceRefreshedAt': old,
                                 'fieldSources': {'unitPrice': 'trip.com'}, 'pricesByDate': {'2026-10-08': 1}}}
        booking = {**merged, 'product_id': 'booking', 'source_ref': 'booking:hotel:2',
                   'attributes': {**merged['attributes'], 'sameAs': ['trip:hotel:998'],
                                  'fieldSources': {'unitPrice': 'booking.com'}}}
        rows, counts = prepare_rows([], [merged, booking], set(), '2026-09-24',
                                    now=datetime(2026, 9, 24, tzinfo=timezone.utc))
        self.assertEqual(counts['staleTrip'], 1)
        self.assertEqual([r['product_id'] for r in rows], ['merged'])
        self.assertNotIn('pricesByDate', rows[0]['attributes'])
        self.assertNotIn('unitPrice', rows[0]['attributes']['fieldSources'])


class _Conn:
    def __init__(self, rows):
        self.rows, self.updates = rows, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        return SimpleNamespace(fetchall=lambda: self.rows)

    def cursor(self):
        conn = self

        class _Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def executemany(self, sql, params):
                conn.updates.extend(params)

        return _Cursor()


class MaintainCatalogTests(unittest.TestCase):
    def test_expires_stale_trip_prices_and_rolls_windows_in_one_pass(self):
        stale = row('stale', source_ref='trip:hotel:1', start=AS_OF, end=HI,
                    attributes={'level': 'property', 'priceRefreshedAt': '2026-09-01T00:00:00+00:00'})
        seeded = row('seeded', start=date(2026, 9, 20), end=date(2026, 10, 19))
        current = row('current', start=AS_OF, end=HI)
        conn = _Conn([stale, seeded, current])
        sync = Mock(return_value={'simulatedBusiness': 0})
        with patch('psycopg.connect', return_value=conn), \
                patch('data_collection.seed.simulated_business.sync', sync):
            counts = maintain_catalog('postgresql://unused', today=AS_OF,
                                      now=datetime(2026, 9, 24, tzinfo=timezone.utc))
        updates = {params[-1]: params for params in conn.updates}
        self.assertEqual(counts, {'staleTrip': 1, 'windowRows': 1, 'simulatedBusiness': 0})
        sync.assert_called_once_with(conn)  # simulated business fares follow the rolled window (data-model.md §3)
        self.assertEqual(set(updates), {'stale', 'seeded'})
        self.assertEqual(updates['stale'][1:3], (None, False))  # unit_price, available
        self.assertEqual(updates['seeded'][3:5], (AS_OF, HI))  # available_from, available_to


class RunJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / 'state').mkdir()
        (root / 'state' / 'trip_targets.json').write_text(json.dumps(
            {'hotels': [{'trip_hotel_id': '1', 'city_id': '1777', 'destination': 'Nha Trang'}]}), encoding='utf-8')
        (root / 'state' / 'full.last_success').write_text('x', encoding='utf-8')
        self.env = {'CATALOG_STATE_DIR': str(root / 'state'), 'CATALOG_RUN_ROOT': str(root / 'runs'),
                    'DB_TARGET': 'cloud', 'CLOUD_SEED_DATABASE_URL': 'postgresql://seed',
                    'CLOUD_WEAVIATE_URL': 'https://abc.weaviate.cloud', 'COHERE_API_KEY': 'k'}
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def patches(self, **overrides):
        record = lambda name, value=None: (lambda *args, **kwargs: self.calls.append(name) or value)
        mocks = {'index_settings': record('settings', 'SETTINGS'),
                 'maintain_catalog': record('maintain', {'staleTrip': 0, 'windowRows': 0}),
                 'index_catalog': record('index', {}),
                 'load_into_db': record('load', {}),
                 'normalize': record('normalize', Path('products.jsonl')),
                 'validate_run': record('validate', {})}
        mocks.update(overrides)
        return [patch.object(fresh_catalog, name, value) for name, value in mocks.items()]

    def run_job(self, mode, **overrides):
        coverage = {'stays': [{'checkin': '2026-10-08'}], 'requestedHotels': 1, 'partialAllowed': True,
                    'results': [{'hotelId': '1', 'checkin': '2026-10-08', 'status': 'priced'}],
                    'completedHotels': ['1'], 'unpricedHotelDates': []}
        crawl = overrides.pop('crawl', AsyncMock(return_value=([{'hotelId': '1'}], coverage)))
        with patch.dict(os.environ, self.env, clear=True), patch.object(fresh_catalog, 'crawl', crawl):
            stack = self.patches(**overrides)
            for item in stack:
                item.start()
            try:
                return fresh_catalog.run_job(mode)
            finally:
                for item in stack:
                    item.stop()

    def test_daily_run_maintains_then_loads_then_indexes_the_same_target(self):
        self.assertEqual(self.run_job('daily'), 0)
        self.assertEqual(self.calls, ['settings', 'maintain', 'normalize', 'validate', 'load', 'index'])

    def test_failed_crawl_still_maintains_and_indexes_but_never_loads(self):
        failed = {'stays': [{'checkin': '2026-10-08'}], 'requestedHotels': 1, 'partialAllowed': True,
                  'results': [{'hotelId': '1', 'checkin': '2026-10-08', 'status': 'missing'}],
                  'completedHotels': [], 'unpricedHotelDates': ['1@2026-10-08']}
        with self.assertRaisesRegex(RuntimeError, 'Không có khách sạn Trip'):
            self.run_job('daily', crawl=AsyncMock(return_value=([], failed)))
        self.assertEqual(self.calls, ['settings', 'maintain', 'index'])

    def test_index_mode_only_maintains_and_indexes(self):
        crawl = AsyncMock()
        self.assertEqual(self.run_job('index', crawl=crawl), 0)
        self.assertEqual(self.calls, ['settings', 'maintain', 'index'])
        crawl.assert_not_called()

    def test_index_quota_after_successful_load_defers_without_fatal_exit(self):
        def broken_index(*args, **kwargs):
            raise RuntimeError('Cohere 429')
        self.assertEqual(self.run_job('daily', index_catalog=broken_index), 0)
        self.assertIn('load', self.calls)
        state = Path(self.env['CATALOG_STATE_DIR']) / 'index_pending.json'
        self.assertTrue(json.loads(state.read_text())['pending'])
        run_dir = next(Path(self.env['CATALOG_RUN_ROOT']).iterdir())
        data = json.loads((run_dir / 'run.json').read_text())
        self.assertEqual(data['status'], 'partial')
        self.assertTrue(data['counts']['index']['deferred'])

    def test_due_entrypoint_and_tick_retry_only_index_after_cooldown(self):
        state = Path(self.env['CATALOG_STATE_DIR'])
        (state / 'index_pending.json').write_text(json.dumps({
            'pending': True, 'retryAfter': '2000-01-01T00:00:00+00:00'}))
        with patch.dict(os.environ, self.env, clear=True), \
                patch.object(fresh_catalog.fresh_settings, 'scheduled_mode', return_value=(None, 'already ran')):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(fresh_catalog.run_job('due'), 0)
            self.assertEqual(output.getvalue().strip(), 'index')
            crawl = AsyncMock()
            self.assertEqual(self.run_job('tick', crawl=crawl), 0)
            crawl.assert_not_called()
        self.assertEqual(self.calls, ['settings', 'maintain', 'index'])
        self.assertFalse((state / 'index_pending.json').exists())

    def test_failed_run_writes_an_alert_for_the_monitor(self):
        """CP7: lượt lỗi → cảnh báo trong <state>/alerts.jsonl và <lượt>/alerts.jsonl (chưa gửi ra ngoài)."""
        failed = {'stays': [{'checkin': '2026-10-08'}], 'requestedHotels': 1, 'partialAllowed': True,
                  'results': [{'hotelId': '1', 'checkin': '2026-10-08', 'status': 'missing'}],
                  'completedHotels': [], 'unpricedHotelDates': ['1@2026-10-08']}
        with self.assertRaises(RuntimeError), contextlib.redirect_stdout(io.StringIO()):
            self.run_job('daily', crawl=AsyncMock(return_value=([], failed)))
        feed = [json.loads(line) for line in (Path(self.env['CATALOG_STATE_DIR']) / 'alerts.jsonl').read_text(
            encoding='utf-8').splitlines()]
        self.assertEqual((feed[0]['level'], feed[0]['run'].split('-')[0]), ('error', 'daily'))
        self.assertIn('Không có khách sạn Trip', feed[0]['message'])
        run_dir = next(Path(self.env['CATALOG_RUN_ROOT']).iterdir())
        self.assertTrue((run_dir / 'alerts.jsonl').is_file())

    def test_idle_tick_checks_sla_without_database_settings(self):
        """CP8: tick rảnh (lịch tắt) vẫn kiểm SLA và không cần biến kết nối DB."""
        checked = []
        env = {k: v for k, v in self.env.items() if k.startswith('CATALOG_')}
        (Path(env['CATALOG_STATE_DIR']) / 'settings.json').write_text(json.dumps({'values': {'schedule.enabled': False}}),
                                                                       encoding='utf-8')
        with patch.dict(os.environ, env, clear=True), \
                patch.object(fresh_catalog.alerts, 'check_sla', lambda *a: checked.append(a)):
            self.assertEqual(fresh_catalog.run_job('tick'), 0)
        self.assertEqual(len(checked), 1)

    def test_missing_index_configuration_keeps_crawl_and_load_then_reports_index_failure(self):
        del self.env['CLOUD_WEAVIATE_URL']
        with self.assertRaisesRegex(RuntimeError, 'Index thất bại'):
            self.run_job('daily', index_settings=fresh_catalog.index_settings)
        self.assertIn('maintain', self.calls)
        self.assertIn('load', self.calls)


class ResumeTests(RunJobTests):
    """CP6 (docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md): chạy lại lượt đã kết thúc từ một bước, không cào lại."""
    RUN = 'full-20260928T010000Z-77'

    def failed_run(self, status='failed', products=True):
        run = Path(self.env['CATALOG_RUN_ROOT']) / self.RUN
        run.mkdir(parents=True)
        (run / 'run.json').write_text(json.dumps({
            'id': self.RUN, 'mode': 'full', 'trigger': 'monitor', 'status': status, 'startedAt': '2026-09-28T01:00:00+00:00',
            'seconds': 100, 'error': 'InfraError: Postgres không kết nối được', 'settings': {'scope.destinations': 'Nha Trang'},
            'steps': [{'name': 'vinpearl', 'status': 'ok'}, {'name': 'db', 'status': 'error'}], 'counts': {}}),
            encoding='utf-8')
        if products:
            (run / 'products.jsonl').write_text('{}\n', encoding='utf-8')
        return run

    def resume(self, from_step, **overrides):
        crawl = AsyncMock()
        self.calls.clear()
        with patch.dict(os.environ, self.env, clear=True), patch.object(fresh_catalog, 'crawl', crawl):
            stack = self.patches(**overrides)
            for item in stack:
                item.start()
            try:
                return fresh_catalog.run_job('resume', run_id=self.RUN, from_step=from_step)
            finally:
                for item in stack:
                    item.stop()
                crawl.assert_not_called()

    def test_resume_from_each_step_runs_only_the_steps_after_it(self):
        run = self.failed_run()
        for from_step, expected in (('db', ['settings', 'load', 'index']),
                                    ('validate', ['settings', 'validate', 'load', 'index']),
                                    ('normalise', ['settings', 'normalize', 'validate', 'load', 'index']),
                                    ('index', ['settings', 'index'])):
            with self.subTest(from_step=from_step):
                self.assertEqual(self.resume(from_step), 0)
                self.assertEqual(self.calls, expected)  # không bảo trì DB, không cào lại
        data = json.loads((run / 'run.json').read_text(encoding='utf-8'))
        self.assertEqual(data['status'], 'ok')
        self.assertEqual([r['from'] for r in data['resumes']], ['db', 'validate', 'normalise', 'index'])
        self.assertEqual(data['resumes'][0]['previousStatus'], 'failed')
        self.assertIn('Postgres', data['resumes'][0]['previousError'])
        self.assertEqual(data['steps'][:2], [{'name': 'vinpearl', 'status': 'ok'}, {'name': 'db', 'status': 'error'}])
        self.assertEqual([s['name'] for s in data['steps'][2:5]], ['db', 'index', 'validate'])
        self.assertGreaterEqual(data['seconds'], 100)  # cộng dồn thời gian lượt gốc

    def test_merge_only_uses_checkpoints(self):
        self.failed_run()
        seen = []
        self.assertEqual(self.resume('merge', normalize=lambda run_dir, dest, merge_only=False: seen.append((dest, merge_only))
                                     or Path('products.jsonl')), 0)
        self.assertEqual(seen, [('Nha Trang', True)])

    def test_db_without_catalog_asks_for_normalise_but_still_indexes(self):
        self.failed_run(products=False)
        with self.assertRaisesRegex(ValueError, 'chạy lại từ normalise'):
            self.resume('db')
        self.assertEqual(self.calls, ['settings', 'index'])

    def test_running_run_or_second_resume_is_refused(self):
        self.failed_run(status='running')
        with self.assertRaisesRegex(ValueError, 'đang chạy'):
            self.resume('db')
        state = Path(self.env['CATALOG_STATE_DIR'])
        (Path(self.env['CATALOG_RUN_ROOT']) / self.RUN / 'run.json').unlink()
        run = Path(self.env['CATALOG_RUN_ROOT']) / self.RUN
        (run / 'run.json').write_text(json.dumps({'id': self.RUN, 'mode': 'full', 'status': 'failed', 'steps': []}),
                                      encoding='utf-8')
        import fcntl
        with (state / 'fresh_catalog.lock').open('w') as lock:  # một lượt / lần chạy lại khác đang giữ khoá
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, 'job catalog khác'):
                self.resume('db')

    def test_unknown_run_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Không có lượt'):
            self.resume('db')

    def test_cli_requires_run_and_step(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            fresh_catalog.main(['resume'])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            fresh_catalog.main(['resume', self.RUN, '--from', 'crawl'])



for _name in [n for n in vars(RunJobTests) if n.startswith('test_')]:  # ResumeTests chỉ dùng lại khung, không chạy lại test cũ
    setattr(ResumeTests, _name, None)


class CrawlSitesTests(unittest.TestCase):
    """Lượt full: các site chạy song song, tối đa CRAWL_PARALLEL; trong một site vẫn tuần tự."""

    def setUp(self):
        self.lock = threading.Lock()
        self.active = self.peak = 0
        self.order = []

    def step(self, name, code=0, seconds=0.05):
        def run(*args):
            with self.lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
                self.order.append(name)
            time.sleep(seconds)
            with self.lock:
                self.active -= 1
            return code
        return run

    def run_sites(self, groups, parallel, codes=None):
        codes = codes or {}
        def fake_source(run_dir, source, destinations, group, deadline=None):
            return self.step(source, codes.get(source, 0))()
        with patch.object(fresh_catalog, 'run_source', fake_source), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            try:
                return fresh_catalog.crawl_sites(Path('/tmp/unused'), '@deep', groups, parallel), out.getvalue()
            except RuntimeError as exc:
                return exc, out.getvalue()

    def test_runs_at_most_parallel_sites_and_keeps_order_inside_a_site(self):
        groups = [('trip', (self.step('discover'), 'trip-flights', 'trip-attractions', self.step('prices'))),
                  ('vinpearl', ('vinpearl',)), ('booking', ('booking-hotels',)), ('agoda', ('agoda-hotels',))]
        statuses, log = self.run_sites(groups, 2)
        self.assertEqual(self.peak, 2)
        trip = [name for name in self.order if name in {'discover', 'trip-flights', 'trip-attractions', 'prices'}]
        self.assertEqual(trip, ['discover', 'trip-flights', 'trip-attractions', 'prices'])
        self.assertEqual(statuses, {'trip-flights': 0, 'trip-attractions': 0, 'vinpearl': 0,
                                    'booking-hotels': 0, 'agoda-hotels': 0})
        self.assertEqual(log.count('"event": "catalog.group.done"'), 4)  # log.py: một dòng JSON mỗi sự kiện

    def test_one_site_at_a_time_is_the_old_sequential_run(self):
        groups = [('vinpearl', ('vinpearl',)), ('booking', ('booking-hotels',))]
        self.run_sites(groups, 1)
        self.assertEqual((self.peak, self.order), (1, ['vinpearl', 'booking-hotels']))

    def test_blocked_and_failed_sources_do_not_skip_queued_sites(self):
        groups = [('vinpearl', ('vinpearl',)), ('booking', ('booking-hotels',)), ('agoda', ('agoda-hotels',))]
        statuses, log = self.run_sites(groups, 1, codes={'vinpearl': 75, 'booking-hotels': 2})
        self.assertEqual(statuses, {'vinpearl': 75, 'booking-hotels': 2, 'agoda-hotels': 0})
        self.assertIn('agoda-hotels', self.order)

    def test_full_run_crawls_trip_inside_its_site_group(self):
        target = {'trip_hotel_id': '1', 'city_id': '1777', 'destination': 'Nha Trang'}
        coverage = {'stays': [{'checkin': '2026-10-08'}], 'requestedHotels': 1, 'partialAllowed': True,
                    'results': [{'hotelId': '1', 'checkin': '2026-10-08', 'status': 'priced'}],
                    'completedHotels': ['1'], 'unpricedHotelDates': []}
        with tempfile.TemporaryDirectory() as tmp:
            env = {'CATALOG_STATE_DIR': f'{tmp}/state', 'CATALOG_RUN_ROOT': f'{tmp}/runs', 'DB_TARGET': 'local',
                   'SEED_DATABASE_URL': 'postgresql://seed', 'CATALOG_DESTINATIONS': 'Nha Trang', 'CRAWL_PARALLEL': '2'}
            calls = []
            fake = lambda name, value=None: (lambda *args, **kwargs: calls.append(name) or value)
            with patch.dict(os.environ, env, clear=True), \
                    patch.object(fresh_catalog, 'index_settings', fake('settings', 'S')), \
                    patch.object(fresh_catalog, 'maintain_catalog', fake('maintain', {})), \
                    patch.object(fresh_catalog, 'discover', AsyncMock(return_value=([target], []))), \
                    patch.object(fresh_catalog, 'crawl', AsyncMock(return_value=([{'hotelId': '1'}], coverage))), \
                    patch.object(fresh_catalog, 'run_source', lambda *args, **kwargs: calls.append(args[1]) or 0), \
                    patch.object(fresh_catalog, 'normalize', fake('normalize', Path('products.jsonl'))), \
                    patch.object(fresh_catalog, 'validate_run', fake('validate', {})), \
                    patch.object(fresh_catalog, 'load_into_db', fake('load', {})), \
                    patch.object(fresh_catalog, 'index_catalog', fake('index', {})), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(fresh_catalog.run_job('full'), 0)
        self.assertEqual(calls[:2], ['settings', 'maintain'])
        self.assertEqual(calls[-4:], ['normalize', 'validate', 'load', 'index'])
        self.assertLess(calls.index('trip-flights'), calls.index('trip-attractions'))
        self.assertEqual(set(calls[2:-4]), {'trip-flights', 'trip-attractions', 'vinpearl', 'booking-hotels',
                                            'agoda-hotels'})


class IndexSettingsTests(unittest.TestCase):
    """Bước index dùng cùng cặp đích với bước nạp, theo quy ước TARGETS của daily.py."""

    def settings(self, **env):
        with patch.dict(os.environ, env, clear=True):
            return fresh_catalog.index_settings(env['DB_TARGET'])

    def test_cloud_target_reads_the_cloud_catalog_and_writes_the_cloud_collection(self):
        settings = self.settings(DB_TARGET='cloud', CLOUD_SEED_DATABASE_URL='postgresql://seed',
                                 CLOUD_DATABASE_URL='postgresql://reader', CLOUD_WEAVIATE_URL='abc.weaviate.cloud',
                                 CLOUD_WEAVIATE_API_KEY='wk', COHERE_API_KEY='k', WEAVIATE_URL='http://localhost:8080')
        self.assertEqual((settings.database_url, settings.weaviate_url, settings.weaviate_api_key),
                         ('postgresql://reader', 'abc.weaviate.cloud', 'wk'))
        fallback = self.settings(DB_TARGET='cloud', CLOUD_SEED_DATABASE_URL='postgresql://seed',
                                 CLOUD_WEAVIATE_URL='https://abc.weaviate.cloud', COHERE_API_KEY='k')
        self.assertEqual(fallback.database_url, 'postgresql://seed')

    def test_local_target_uses_the_backend_variables(self):
        settings = self.settings(DB_TARGET='local', SEED_DATABASE_URL='postgresql://seed',
                                 WEAVIATE_URL='http://localhost:8080', WEAVIATE_API_KEY='', COHERE_API_KEY='k')
        self.assertEqual((settings.database_url, settings.weaviate_url), ('postgresql://seed', 'http://localhost:8080'))

    def test_missing_key_or_invalid_url_is_reported_by_name(self):
        with self.assertRaisesRegex(ValueError, 'COHERE_API_KEY'):
            self.settings(DB_TARGET='cloud', CLOUD_SEED_DATABASE_URL='postgresql://seed',
                          CLOUD_WEAVIATE_URL='https://abc.weaviate.cloud', COHERE_API_KEY='')
        with self.assertRaises(ValueError):
            self.settings(DB_TARGET='local', SEED_DATABASE_URL='postgresql://seed',
                          WEAVIATE_URL='ftp://weaviate', COHERE_API_KEY='k')


if __name__ == '__main__':
    unittest.main()
