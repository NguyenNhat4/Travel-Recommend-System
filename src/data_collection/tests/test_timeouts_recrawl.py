"""P4 (docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md): hạn giờ của từng bước cào / cả phần cào, và cào lại một nguồn."""
import asyncio
import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import alerts
import fresh_catalog
import monitor
import pipeline_errors as perr
import pipeline_graph as graph


def alive(pid: int) -> bool:
    try:
        stat = Path(f'/proc/{pid}/stat').read_text()
    except OSError:
        return False
    return stat[stat.rindex(')') + 2] != 'Z'


class Quiet:
    def __enter__(self):
        self.stack = contextlib.ExitStack()
        self.out = self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        return self

    def __exit__(self, *exc):
        self.stack.close()


# ---------------------------------------------------------------------------------------------------- P4a hạn giờ


class RunSourceTimeoutTests(unittest.TestCase):
    CHILD = ("import subprocess, sys, time; "
             "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
             "print('child', c.pid, flush=True); time.sleep(60)")

    def run_source(self, script, deadline):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(fresh_catalog, 'source_command', lambda *a: [sys.executable, '-c', script]), Quiet():
            started = time.monotonic()
            code = fresh_catalog.run_source(Path(tmp), 'booking-hotels', '@x', 'booking', deadline=deadline)
            return code, time.monotonic() - started, list(fresh_catalog.SOURCE_TAIL['booking-hotels'])

    def test_deadline_stops_the_source_and_its_children(self):
        code, seconds, tail = self.run_source(self.CHILD, time.monotonic() + 1.0)
        self.assertEqual(code, perr.EXIT_TIMEOUT)
        self.assertLess(seconds, 15)
        child = int(next(line for line in tail if line.startswith('child')).split()[1])
        deadline = time.monotonic() + 5
        while alive(child) and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertFalse(alive(child), 'tiến trình con của nguồn (vd. Chromium) phải bị dừng cùng')

    def test_finishing_before_the_deadline_keeps_the_exit_code(self):
        code, _, _ = self.run_source('import sys; sys.exit(3)', time.monotonic() + 30)
        self.assertEqual(code, 3)
        code, _, _ = self.run_source('print(1)', None)
        self.assertEqual(code, 0)


class DeadlineHelpersTests(unittest.TestCase):
    def test_step_deadline_takes_the_earlier_of_own_timeout_and_crawl_deadline(self):
        values = {f.key: f.default for f in fresh_catalog.fresh_settings.FIELDS}
        with patch.object(fresh_catalog, 'CFG', {**values, 'timeout.booking': 10}):
            now = time.monotonic()
            self.assertAlmostEqual(fresh_catalog.step_deadline('booking-hotels', None) - now, 600, delta=2)
            self.assertAlmostEqual(fresh_catalog.step_deadline('booking-hotels', now + 60) - now, 60, delta=2)
        with patch.object(fresh_catalog, 'CFG', {**values, 'timeout.booking': 0}):
            self.assertIsNone(fresh_catalog.step_deadline('booking-hotels', None))  # 0 = không giới hạn
            self.assertEqual(fresh_catalog.step_deadline('booking-hotels', 123.0), 123.0)
        self.assertIsNone(fresh_catalog.deadline_after(0))

    def test_run_cancellable_raises_step_timeout_and_cancels_the_work(self):
        cancelled = []

        async def slow():
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.append(True)
                raise
        with self.assertRaises(perr.StepTimeout):
            asyncio.run(fresh_catalog.run_cancellable(slow(), time.monotonic() + 0.3))
        self.assertEqual(cancelled, [True])

    def test_error_kind(self):
        self.assertEqual(perr.classify_exit(perr.EXIT_TIMEOUT, []), perr.TIMEOUT)
        self.assertEqual(perr.strategy(perr.TIMEOUT, {})['action'], 'skip')
        self.assertEqual(perr.StepTimeout('x').step_status, 'timeout')


class SealInterimTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run = Path(tmp.name)
        (self.run / 'interim').mkdir()

    def file(self, name, text):
        (self.run / 'interim' / name).write_bytes(text.encode())

    def text(self, name):
        return (self.run / 'interim' / name).read_text()

    def test_temporary_file_is_trimmed_and_renamed(self):
        self.file('vinpearl.jsonl.tmp', '{"a": 1}\n{"b": 2}\n{"c": ')
        self.assertEqual(fresh_catalog.seal_interim(self.run, ('vinpearl', 'vinpearl_bundles')), ['vinpearl'])
        self.assertEqual(self.text('vinpearl.jsonl'), '{"a": 1}\n{"b": 2}\n')
        self.assertFalse((self.run / 'interim' / 'vinpearl.jsonl.tmp').exists())

    def test_appended_file_loses_only_its_partial_last_line(self):
        self.file('booking_hotels.jsonl', '{"a": 1}\n{"b": 2')
        self.file('booking_hotels.jsonl.tmp', '{"x": ')  # lần ghi lại cuối nguồn đang dở: giữ file chính
        self.assertEqual(fresh_catalog.seal_interim(self.run, ('booking_hotels',)), ['booking_hotels'])
        self.assertEqual(self.text('booking_hotels.jsonl'), '{"a": 1}\n')
        self.file('agoda_hotels.jsonl', '{"a": 1}\n')
        fresh_catalog.seal_interim(self.run, ('agoda_hotels',))
        self.assertEqual(self.text('agoda_hotels.jsonl'), '{"a": 1}\n')  # đủ dòng: không đổi
        self.assertEqual(fresh_catalog.seal_interim(self.run, ('trip_flights',)), [])


class Recorder:
    def __init__(self):
        self.sources, self.groups = [], []

    def source_done(self, group, stems, merge=True):
        self.sources.append((group, tuple(stems)))

    def group_done(self, name, status, merge=True):
        self.groups.append((name, status))

    def finish(self, keep):
        pass


class CrawlSitesTimeoutTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run = Path(tmp.name)
        (self.run / 'interim').mkdir()
        self.calls, self.deadlines = [], {}

    def crawl(self, groups, codes, deadline=None, delays=None):
        recorder = Recorder()

        def fake(run_dir, source, destinations, group, deadline=None):
            self.calls.append(source)
            self.deadlines[source] = deadline
            time.sleep((delays or {}).get(source, 0))
            return codes.get(source, 0)
        with patch.object(fresh_catalog, 'run_source', fake), Quiet() as quiet:
            statuses = fresh_catalog.crawl_sites(self.run, '@x', groups, 4, recorder, deadline)
        return statuses, recorder, quiet.out.getvalue()

    def test_timed_out_source_is_sealed_normalised_and_others_continue(self):
        (self.run / 'interim' / 'vinpearl.jsonl.tmp').write_text('{"a": 1}\n{"b"', encoding='utf-8')
        statuses, recorder, log = self.crawl([('vinpearl', ('vinpearl',)), ('booking', ('booking-hotels',))],
                                             {'vinpearl': perr.EXIT_TIMEOUT})
        self.assertEqual(statuses, {'vinpearl': perr.EXIT_TIMEOUT, 'booking-hotels': 0})
        self.assertEqual((self.run / 'interim' / 'vinpearl.jsonl').read_text(), '{"a": 1}\n')
        self.assertIn(('vinpearl', ('vinpearl', 'vinpearl_bundles')), recorder.sources)  # vẫn chuẩn hoá phần đã cào
        self.assertEqual(self.calls.count('vinpearl'), 1)  # không thử lại
        self.assertIn('catalog.group.done name=booking status=ok', log)

    def test_each_step_gets_its_own_deadline_capped_by_the_crawl_deadline(self):
        crawl_deadline = time.monotonic() + 30
        self.crawl([('booking', ('booking-hotels',))], {}, deadline=crawl_deadline)
        self.assertLessEqual(self.deadlines['booking-hotels'], crawl_deadline)  # timeout.booking 60 phút > 30 s
        self.crawl([('agoda', ('agoda-hotels',))], {})
        self.assertAlmostEqual(self.deadlines['agoda-hotels'] - time.monotonic(), 3600, delta=5)

    def test_expired_crawl_deadline_skips_steps_not_started(self):
        statuses, recorder, log = self.crawl([('trip', ('trip-flights', 'trip-attractions')), ('agoda', ('agoda-hotels',))],
                                             {}, deadline=time.monotonic() + 0.3, delays={'trip-flights': 0.6})
        self.assertEqual(self.calls, ['trip-flights', 'agoda-hotels'])  # agoda đã bắt đầu trước hạn
        self.assertEqual(statuses['trip-attractions'], perr.EXIT_TIMEOUT)
        self.assertIn('catalog.crawl.deadline group=trip', log)
        self.assertIn(('trip', 'timeout'), recorder.groups)
        statuses, _, _ = self.crawl([('booking', ('booking-hotels',))], {}, deadline=time.monotonic() - 1)
        self.assertEqual(statuses, {'booking-hotels': perr.EXIT_TIMEOUT})
        self.assertNotIn('booking-hotels', self.calls)

    def test_in_process_step_timeout_skips_the_dependent_step(self):
        ran = []

        def discover():
            raise perr.StepTimeout('quá giờ')

        def prices():
            ran.append('prices')
        discover.step = 'trip-hotels.discover'
        prices.step = 'trip-hotels.prices'
        _, recorder, log = self.crawl([('trip', (discover, 'trip-flights', prices))], {})
        self.assertEqual(ran, [])
        self.assertEqual(self.calls, ['trip-flights'])
        self.assertIn(('trip', 'timeout'), recorder.groups)


class JobTimeoutTests(unittest.TestCase):
    """Lượt full với một nguồn quá giờ: lượt vẫn gộp, nạp, index; kết thúc "chưa đủ dữ liệu" và có cảnh báo."""

    def run_job(self, codes, settings=None, prices_timeout=False):
        target = {'trip_hotel_id': '1', 'city_id': '1777', 'destination': 'Nha Trang'}
        coverage = {'stays': [{'checkin': '2026-10-08'}], 'requestedHotels': 1, 'partialAllowed': True,
                    'results': [{'hotelId': '1', 'checkin': '2026-10-08', 'status': 'priced'}],
                    'completedHotels': ['1'], 'unpricedHotelDates': []}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / 'state').mkdir()
        (root / 'state' / 'settings.json').write_text(json.dumps({'values': {'normalise.preview': False, **(settings or {})}}),
                                                      encoding='utf-8')
        env = {'CATALOG_STATE_DIR': f'{tmp.name}/state', 'CATALOG_RUN_ROOT': f'{tmp.name}/runs', 'DB_TARGET': 'local',
               'SEED_DATABASE_URL': 'postgresql://seed', 'CATALOG_DESTINATIONS': 'Nha Trang', 'CRAWL_PARALLEL': '4'}
        calls = []
        fake = lambda name, value=None: (lambda *a, **k: calls.append(name) or value)

        async def slow_crawl(*args, **kwargs):
            await asyncio.sleep(30)
        crawl = slow_crawl if prices_timeout else AsyncMock(return_value=([{'hotelId': '1'}], coverage))
        with patch.dict(os.environ, env, clear=True), \
                patch.object(fresh_catalog, 'index_settings', lambda *a: 'S'), \
                patch.object(fresh_catalog, 'check_local_only', lambda *a: None), \
                patch.object(fresh_catalog, 'maintain_catalog', lambda *a: {}), \
                patch.object(fresh_catalog, 'discover', AsyncMock(return_value=([target], []))), \
                patch.object(fresh_catalog, 'crawl', crawl), \
                patch.object(fresh_catalog, 'run_source', lambda run_dir, source, *a, **k: codes.get(source, 0)), \
                patch.object(fresh_catalog, 'normalize', fake('normalize', Path('products.jsonl'))), \
                patch.object(fresh_catalog, 'validate_run', fake('validate', {})), \
                patch.object(fresh_catalog, 'load_into_db', fake('load', {})), \
                patch.object(fresh_catalog, 'index_catalog', fake('index', {})), \
                patch.object(fresh_catalog, 'notify_finished', lambda *a: None), Quiet():
            code = fresh_catalog.run_job('full')
        run = next((root / 'runs').iterdir())
        return code, json.loads((run / 'run.json').read_text(encoding='utf-8')), run, calls

    def test_source_timeout_makes_a_partial_run_that_still_loads(self):
        code, data, run, calls = self.run_job({'vinpearl': perr.EXIT_TIMEOUT})
        self.assertEqual(code, 0)
        self.assertEqual(data['status'], 'partial')
        self.assertEqual(calls, ['normalize', 'validate', 'load', 'index'])
        step = next(s for s in data['steps'] if s['name'] == 'vinpearl')
        self.assertEqual((step['status'], step['detail']['errorKind']), ('timeout', 'timeout'))
        kinds = [a['kind'] for a in alerts.run_alerts(data, run)]
        self.assertIn('timeout', kinds)
        self.assertEqual(json.loads((run / 'trip_targets.run.json').read_text())['hotels'][0]['trip_hotel_id'], '1')

    def test_trip_price_timeout_drops_trip_hotels_but_not_the_run(self):
        code, data, _, calls = self.run_job({}, settings={'timeout.tripHotelsPrices': 0, 'crawl.maxHours': 0.0003},
                                            prices_timeout=True)  # ~1 s cho cả phần cào
        step = next(s for s in data['steps'] if s['name'] == 'trip-hotels.prices')
        self.assertEqual(step['status'], 'timeout')
        self.assertEqual(code, 0)
        self.assertEqual(data['status'], 'partial')
        self.assertEqual(calls, ['normalize', 'validate', 'load', 'index'])  # không lỗi "Không có khách sạn Trip đủ JSON giá"


# ---------------------------------------------------------------------------------------------------- P4b cào lại một nguồn


class FakeRec:
    def save(self):
        pass

    def __init__(self, mode='full'):
        self.data = {'mode': mode, 'id': 'full-x', 'startedAt': 's'}
        self.stop_event = type('E', (), {'is_set': staticmethod(lambda: False)})()

    def check_stop(self):
        pass


class RecrawlTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run = Path(tmp.name)
        self.values = {**{f.key: f.default for f in fresh_catalog.fresh_settings.FIELDS}, 'scope.destinations': 'Nha Trang'}
        self.calls = []

    def resume(self, source, mode='full', crawl_sites=None):
        (self.run / 'products.jsonl').write_text('', encoding='utf-8')

        def sites(run_dir, destinations, groups, parallel, previewer=None, deadline=None):
            self.calls.append(('crawl', groups, parallel, previewer, destinations))
            for _, steps in groups:
                for item in steps:
                    if callable(item):
                        item()
            return {'booking-hotels': 0}
        with patch.object(fresh_catalog, 'crawl_sites', crawl_sites or sites), \
                patch.object(fresh_catalog, 'normalise_step', lambda *a, **k: self.calls.append('normalise') or self.run / 'products.jsonl'), \
                patch.object(fresh_catalog, 'validate_step', lambda *a, **k: self.calls.append('validate')), \
                patch.object(fresh_catalog, 'db_step', lambda *a, **k: self.calls.append('db')), \
                patch.object(fresh_catalog, 'run_index', lambda *a, **k: self.calls.append('index')), Quiet():
            return fresh_catalog.resume_run(FakeRec(mode), self.values, self.run, self.run, 'crawl', 'db', None, source=source)

    def test_recrawl_runs_only_that_source_then_every_later_step(self):
        self.assertEqual(self.resume('booking'), 0)
        crawl, *rest = self.calls
        self.assertEqual(crawl, ('crawl', [('booking', ('booking-hotels',))], 1, None, 'Nha Trang'))
        self.assertEqual(rest, ['normalise', 'validate', 'db', 'index'])

    def test_recrawl_that_is_blocked_again_is_partial(self):
        blocked = lambda *a, **k: self.calls.append('crawl') or {'booking-hotels': perr.EXIT_BLOCKED}
        self.assertEqual(self.resume('booking', crawl_sites=blocked), fresh_catalog.EXIT_PARTIAL)
        self.assertEqual(self.calls, ['crawl', 'normalise', 'validate', 'db', 'index'])

    def test_trip_hotels_need_the_saved_targets_and_only_reprice(self):
        with self.assertRaisesRegex(ValueError, 'trip_targets.run.json'):
            self.resume('tripHotels')
        fresh_catalog.save_run_targets(self.run, [{'trip_hotel_id': '1'}])
        priced = []
        with patch.object(fresh_catalog, 'crawl_trip_prices', lambda run_dir, targets, *a: priced.append(targets) or ([], {})):
            self.resume('tripHotels')
        self.assertEqual(priced, [[{'trip_hotel_id': '1'}]])
        groups = self.calls[-5][1]
        self.assertEqual([getattr(s, 'step', s) for s in groups[0][1]], ['trip-hotels.prices'])

    def test_invalid_requests(self):
        with self.assertRaisesRegex(ValueError, 'không cào nguồn booking'):
            self.resume('booking', mode='daily')
        with self.assertRaisesRegex(ValueError, 'Nguồn phải là'):
            self.resume('nope')
        with self.assertRaisesRegex(ValueError, '--source'), Quiet():
            fresh_catalog.resume_run(FakeRec(), self.values, self.run, self.run, 'crawl', 'db', None)
        with self.assertRaises(SystemExit), Quiet():
            fresh_catalog.main(['resume', 'full-20260929T000000Z-1', '--from', 'crawl'])
        with self.assertRaises(SystemExit), Quiet():
            fresh_catalog.main(['resume', 'full-20260929T000000Z-1', '--from', 'db', '--source', 'booking'])


class MonitorRecrawlTests(unittest.TestCase):
    RUN = 'full-20260929T010000Z-1'

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / 'state').mkdir()
        self.run_dir = root / 'runs' / self.RUN
        self.run_dir.mkdir(parents=True)
        self.monitor = monitor.FreshMonitor(root / 'state', root / 'runs')

    def write_run(self, statuses, mode='full'):
        steps = [{'name': name, 'group': graph.SOURCE_BY_STEP[name].site, 'status': status,
                  'startedAt': '2026-09-29T01:00:00+00:00', 'finishedAt': '2026-09-29T01:01:00+00:00'}
                 for name, status in statuses.items()]
        (self.run_dir / 'run.json').write_text(json.dumps({'id': self.RUN, 'mode': mode, 'status': 'partial',
                                                           'steps': steps, 'settings': {}}), encoding='utf-8')

    def resume_of(self):
        return {n['id']: n.get('resume') for n in self.monitor.graph(self.RUN)['nodes']
                if n['id'] in graph.SOURCE_BY_STEP}

    def test_recrawl_button_only_on_failed_crawl_steps(self):
        self.write_run({'vinpearl': 'timeout', 'booking-hotels': 'ok', 'agoda-hotels': 'blocked',
                        'trip-flights': 'error', 'trip-hotels.discover': 'ok', 'trip-hotels.prices': 'timeout'})
        found = self.resume_of()
        self.assertEqual(found['vinpearl'], ['crawl'])
        self.assertEqual(found['agoda-hotels'], ['crawl'])
        self.assertEqual(found['trip-flights'], ['crawl'])
        self.assertIsNone(found['booking-hotels'])
        self.assertIsNone(found['trip-hotels.prices'])  # chưa lưu ID khách sạn Trip của lượt
        (self.run_dir / 'trip_targets.run.json').write_text('{"hotels": []}', encoding='utf-8')
        self.assertEqual(self.resume_of()['trip-hotels.prices'], ['crawl'])
        self.assertEqual(monitor.SEVERITY['timeout'], monitor.SEVERITY['blocked'])

    def test_resume_api_passes_the_source(self):
        self.write_run({'booking-hotels': 'timeout'})
        launched = []

        class Proc:
            pid = 42

            def wait(self):
                return 0
        with patch.object(monitor.subprocess, 'Popen', lambda cmd, **k: launched.append(cmd) or Proc()), \
                patch.dict(os.environ, {'DISPLAY': ':0'}):
            code, out = self.monitor.resume(self.RUN, 'crawl', 'booking')
        self.assertEqual((code, out['source']), (202, 'booking'))
        self.assertEqual(launched[0][-6:], ['--from', 'crawl', '--trigger', 'monitor', '--source', 'booking'])
        for bad in (('crawl', None), ('crawl', 'nope'), ('db', 'booking')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.monitor.resume(self.RUN, *bad)
