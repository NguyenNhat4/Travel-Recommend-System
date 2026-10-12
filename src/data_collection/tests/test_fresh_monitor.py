"""Offline regression coverage for the fresh runner and its shared-volume monitor."""
import asyncio
import contextlib
import io
import fcntl
import gzip
import http.client
import json
import os
import subprocess
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import fresh_catalog
import fresh_run_log as run_log
import fresh_settings as settings
import monitor
from collectors import trip_live
from fresh_catalog_db import write_load_report

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = 'full-20260925T010000Z-123'
VN = timezone(timedelta(hours=7))


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / 'state'
        self.runs = self.root / 'runs'
        self.state.mkdir()
        self.runs.mkdir()
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.monitor = monitor.FreshMonitor(self.state, self.runs)

    def run_dir(self, name=RUN_ID, status='running'):
        path = self.runs / name
        path.mkdir(exist_ok=True)
        run_log.write_json(path / 'run.json', {'id': name, 'mode': 'full', 'status': status,
                                             'startedAt': '2026-09-25T01:00:00+00:00'})
        return path

    def lock(self):
        handle = (self.state / 'fresh_catalog.lock').open('a')
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(handle.close)
        return handle


class SettingsTests(Workspace):
    def test_priority_and_reset(self):
        env = {'TRIP_DAILY_HOTELS': '80'}
        self.assertEqual(settings.load(self.state, env)['tripHotels.dailyHotels'], 80)
        settings.save(self.state, {'tripHotels.dailyHotels': 250}, env)
        self.assertEqual(settings.resolve(self.state, env)['tripHotels.dailyHotels']['source'], 'file')
        settings.save(self.state, {'tripHotels.dailyHotels': None}, env)
        self.assertEqual(settings.load(self.state, env)['tripHotels.dailyHotels'], 80)
        self.assertEqual(settings.load(self.state, {})['tripHotels.dailyHotels'], 180)

    def test_invalid_changes_are_atomic(self):
        settings.save(self.state, {'runs.keep': 4}, {})
        before = (self.state / 'settings.json').read_bytes()
        for change in ({'unknown': 1}, {'runs.keep': 0}, {'tripHotels.delayMin': 20},
                       {'trip.delay': float('nan')}, {'trip.delay': float('inf')},
                       {'tripHotels.initialPerCity': 501}):
            with self.subTest(change=change), self.assertRaises(settings.SettingsError):
                settings.save(self.state, change, {})
            self.assertEqual((self.state / 'settings.json').read_bytes(), before)

    def test_settings_do_not_expose_connection_secrets(self):
        data = settings.describe(self.state, {'COHERE_API_KEY': 'secret-test-123',
                                             'CLOUD_SEED_DATABASE_URL': 'postgresql://private'})
        self.assertNotIn('secret-test-123', json.dumps(data))
        self.assertNotIn('postgresql://private', json.dumps(data))
        self.assertTrue(data['env']['COHERE_API_KEY'])

    def test_schedule_once_per_vietnam_day(self):
        cfg = settings.load(self.state, {})
        now = datetime(2026, 9, 25, 8, 45, tzinfo=VN)  # sau giờ mặc định 08:35
        self.assertIsNone(settings.scheduled_mode(cfg, self.state, now.replace(hour=1))[0])
        self.assertEqual(settings.scheduled_mode(cfg, self.state, now)[0], 'full')
        settings.mark_scheduled(self.state, RUN_ID, now.date())
        self.assertIsNone(settings.scheduled_mode(cfg, self.state, now)[0])
        self.assertTrue(settings.next_run(cfg, self.state, now)['at'].startswith('2026-09-26'))
        (self.state / settings.FULL_MARKER).write_text('2026-09-24T18:30:00+00:00')
        self.assertEqual(settings.last_full_date(self.state).isoformat(), '2026-09-25')

    def test_disabled_tick_never_needs_database_credentials(self):
        settings.save(self.state, {'schedule.enabled': False}, {})
        with patch.dict(os.environ, {'CATALOG_STATE_DIR': str(self.state), 'CATALOG_RUN_ROOT': str(self.runs)}), \
                patch.object(fresh_catalog, 'index_settings') as index:
            self.assertEqual(fresh_catalog.run_job('tick'), 0)
            index.assert_not_called()

    def test_tick_rechecks_schedule_under_lock_and_records_only_one_run(self):
        env = {'CATALOG_STATE_DIR': str(self.state), 'CATALOG_RUN_ROOT': str(self.runs),
               'CATALOG_DB_RUN_LOCK': 'off', 'DB_TARGET': 'local', 'SEED_DATABASE_URL': 'postgresql://unused'}
        settings.save(self.state, {'schedule.time': '00:00'}, {})
        with patch.dict(os.environ, env), patch.object(fresh_catalog, 'index_settings'), \
                patch.object(fresh_catalog, 'execute', return_value=0) as execute:
            self.assertEqual(fresh_catalog.run_job('tick'), 0)
            self.assertEqual(fresh_catalog.run_job('tick'), 0)
            execute.assert_called_once()
        history = list(monitor.iter_jsonl(self.state / run_log.HISTORY_FILE))
        self.assertEqual(history[0][1]['trigger'], 'schedule')
        self.assertEqual(history[0][1]['status'], 'ok')


    def test_stop_during_final_database_step_is_not_reported_as_success(self):
        env = {'CATALOG_STATE_DIR': str(self.state), 'CATALOG_RUN_ROOT': str(self.runs),
               'CATALOG_DB_RUN_LOCK': 'off', 'DB_TARGET': 'local', 'SEED_DATABASE_URL': 'postgresql://unused'}

        def finish_after_stop(selected, recorder, *args):
            recorder.stop_event.set()
            return 0

        with patch.dict(os.environ, env), patch.object(fresh_catalog, 'index_settings'), \
                patch.object(fresh_catalog, 'execute', side_effect=finish_after_stop):
            with self.assertRaises(run_log.StopRequested):
                fresh_catalog.run_job('daily')
        history = list(monitor.iter_jsonl(self.state / run_log.HISTORY_FILE))
        self.assertEqual(history[0][1]['status'], 'stopped')


class MonitorTests(Workspace):
    def test_lost_process_is_dead_even_when_stale_file_claims_running(self):
        self.run_dir()
        run_log.write_json(self.state / run_log.RUNNING_FILE, {'runId': RUN_ID, 'pid': os.getpid()})
        self.assertIsNone(self.monitor.running())
        self.assertEqual(self.monitor.runs()[0]['status'], 'dead')
        self.assertEqual(self.monitor.run(RUN_ID)['status'], 'dead')

    def test_shared_lock_detects_other_container_and_stop_is_scoped_to_run(self):
        self.run_dir()
        self.lock()
        run_log.write_json(self.state / run_log.RUNNING_FILE,
                           {'runId': RUN_ID, 'pid': 999999999, 'host': 'other-container',
                            'heartbeatAt': datetime.now(timezone.utc).isoformat()})
        self.assertEqual(self.monitor.running()['runId'], RUN_ID)
        self.assertEqual(self.monitor.stop()[0], 202)
        self.assertEqual(run_log.read_json(self.state / run_log.STOP_FILE)['runId'], RUN_ID)
        self.assertEqual(self.monitor.start('full')[0], 409)

    def test_start_builds_safe_command_and_passes_shared_paths(self):
        done = threading.Event()
        proc = Mock(pid=123)
        proc.wait.side_effect = lambda: (done.wait(1), 0)[1]
        with patch.object(monitor.subprocess, 'Popen', return_value=proc) as popen, \
                patch.object(monitor.shutil, 'which', return_value=None):
            code, _ = self.monitor.start('daily')
            self.assertEqual(code, 202)
            args, opts = popen.call_args
            self.assertEqual(args[0][-3:], ['daily', '--trigger', 'monitor'])
            self.assertEqual(opts['env']['CATALOG_STATE_DIR'], str(self.state))
            self.assertEqual(opts['env']['CATALOG_RUN_ROOT'], str(self.runs))
            self.assertNotIn('shell', opts)
            done.set()
        with self.assertRaises(ValueError):
            self.monitor.start('daily; touch /tmp/no')

    def test_raw_gzip_and_path_escape(self):
        path = self.run_dir()
        raw = path / 'raw' / 'trip_hotels' / '1'
        raw.mkdir(parents=True)
        with gzip.open(raw / 'rooms.json.gz', 'wt') as f:
            json.dump({'price': 900000}, f)
        data = self.monitor.raw_file(RUN_ID, 'trip_hotels', '1/rooms.json.gz')
        self.assertIn('900000', data['json'])
        for bad in ('../../outside', '/etc/passwd'):
            with self.assertRaises(ValueError):
                self.monitor.raw_file(RUN_ID, 'trip_hotels', bad)
        with self.assertRaises(ValueError):
            self.monitor.run_path('../state')
        secret = path / 'trip_price_profile' / 'Cookies'
        secret.parent.mkdir()
        secret.write_text('private')
        with self.assertRaises(ValueError):
            self.monitor.artifact(RUN_ID, 'trip_price_profile/Cookies')

    def test_product_trace_and_database_report(self):
        path = self.run_dir(status='ok')
        (path / 'interim').mkdir()
        (path / 'interim' / 'trip_hotels.jsonl').write_text(json.dumps({'hotelId': '99', 'name': 'Hotel'})+'\n')
        product = {'productId': 'p1', 'sourceRef': 'trip:hotel:99:room:7', 'name': 'Room',
                   'taxonomy': 'hotel', 'attributes': {'level': 'room'}, 'unitPrice': 1200000}
        (path / 'products.jsonl').write_text(json.dumps(product)+'\n')
        (path / 'db_load.jsonl').write_text(json.dumps({'productId': 'p1', 'action': 'refresh', 'written': True})+'\n')
        trace = self.monitor.product(RUN_ID, 'p1')
        self.assertEqual(trace['trace'][0]['interim']['id'], '99')
        self.assertTrue(trace['db']['written'])
        self.assertEqual(self.monitor.products(RUN_ID, q='Room')['total'], 1)
        self.assertEqual(self.monitor.db_rows(RUN_ID, action='refresh')['written'], 1)

    def test_retention_preserves_summary_and_unrelated_directories(self):
        old = self.run_dir('daily-20260924T010000Z-1', 'ok')
        new = self.run_dir()
        other = self.runs / 'notes'
        other.mkdir()
        (self.state / run_log.HISTORY_FILE).write_text(json.dumps({'id': old.name, 'status': 'ok', 'startedAt': '2026-09-24'}) + '\n')
        self.assertEqual(run_log.prune_runs(self.runs, 1, protect=new), [old.name])
        self.assertTrue(other.is_dir())
        self.assertFalse(next(r for r in self.monitor.runs() if r['id'] == old.name)['retained'])

    def test_recorder_finishes_without_resurrecting_running_marker(self):
        rec = run_log.RunRecorder(self.runs / RUN_ID, self.state, run_id=RUN_ID, mode='full', trigger='test', settings={})
        with patch.object(run_log, 'HEARTBEAT_SECONDS', 0.01):
            rec.start()
            with rec.step('normalise'):
                print('hello monitor')
            rec.finish('ok', 0)
        self.assertFalse(rec._thread.is_alive())
        self.assertFalse((self.state / run_log.RUNNING_FILE).exists())
        data = run_log.read_json(self.runs / RUN_ID / run_log.RUN_FILE)
        self.assertEqual(data['steps'][0]['status'], 'ok')
        self.assertIn('hello monitor', (self.runs / RUN_ID / run_log.LOG_FILE).read_text())


class HttpTests(Workspace):
    def setUp(self):
        super().setUp()
        self.handler = type('TestHandler', (monitor.Handler,), {'monitor': self.monitor})
        self.server = monitor.ThreadingHTTPServer(('127.0.0.1', 0), self.handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path, method='GET', body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        code, data, location = response.status, response.read(), response.getheader('Location')
        conn.close()
        return code, data, location

    def test_dashboard_and_old_urls(self):
        self.assertIn(b'Fresh catalog', self.request('/')[1])
        for path in ('/daily', '/pipeline'):
            code, _, location = self.request(path)
            self.assertEqual((code, location), (302, '/'))
        for path in ('/api/daily/overview', '/api/pipeline/config'):
            self.assertEqual(self.request(path)[0], 404)

    def test_local_host_guard_and_post_header(self):
        self.assertEqual(self.request('/api/overview', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.request('/api/settings', 'POST', '{}')[0], 403)
        headers = {'X-Requested-With': 'vota-monitor', 'Content-Type': 'application/json'}
        code, body, _ = self.request('/api/settings', 'POST', json.dumps({'values': {'tripHotels.dailyHotels': 250}}), headers)
        self.assertEqual(code, 200, body)
        self.assertEqual(settings.load(self.state, {})['tripHotels.dailyHotels'], 250)
        self.assertEqual(self.request('/api/settings', 'POST', '[]', headers)[0], 400)


class TripSpeedTests(unittest.IsolatedAsyncioTestCase):
    async def test_ready_packet_skips_all_scroll_waits(self):
        page, ready = Mock(), asyncio.Event()
        ready.set()
        await trip_live.wait_for_prices(page, ready)
        page.evaluate.assert_not_called()

    async def test_price_arrival_during_first_scroll_finishes_early(self):
        ready = asyncio.Event()
        page = SimpleNamespace(evaluate=AsyncMock(side_effect=lambda _: ready.set()))
        await trip_live.wait_for_prices(page, ready)
        page.evaluate.assert_awaited_once()

    async def test_stop_cancels_in_process_http_work(self):
        cancelled = asyncio.Event()
        started = asyncio.Event()
        stop = threading.Event()
        async def work():
            started.set()
            try:
                await asyncio.sleep(30)
            finally:
                cancelled.set()
        def check():
            if stop.is_set():
                raise run_log.StopRequested('stop')
        with patch.object(fresh_catalog, 'REC', SimpleNamespace(check_stop=check)):
            task = asyncio.create_task(fresh_catalog.run_cancellable(work()))
            await started.wait()
            stop.set()
            with self.assertRaises(run_log.StopRequested):
                await task
        self.assertTrue(cancelled.is_set())

    async def test_metadata_reuses_session_and_closes_it(self):
        session = Mock()
        session.get = AsyncMock(return_value=SimpleNamespace(status_code=200, text='hotelDetailResponse', content=b'{}'))
        session.close = AsyncMock()
        targets = [{'trip_hotel_id': str(i), 'city_id': '1'} for i in (1, 2)]
        with tempfile.TemporaryDirectory() as t, patch.object(trip_live, 'AsyncSession', return_value=session) as factory, \
                patch.object(trip_live, 'extract_anchored_json', return_value={}), \
                patch.object(trip_live, 'parse_hotel_detail', return_value={'name': 'Hotel'}):
            results = await trip_live.fetch_metadata(targets, ('2026-10-01', '2026-10-02'), Path(t),
                                                     trip_live.LiveOptions(delay_min=0, delay_max=0))
        factory.assert_called_once()
        session.close.assert_awaited_once()
        self.assertEqual(len(results), 2)

    async def test_raw_capture_removes_people_and_reviews(self):
        with tempfile.TemporaryDirectory() as t:
            path = trip_live._write_capture(Path(t), '1', 'rooms', {'url': 'https://example.test',
                'packets': [{'reviewList': [{'userName': 'private'}], 'userInfo': {'name': 'private'}, 'price': 500000}]})
            with gzip.open(path, 'rt') as f:
                text = f.read()
            self.assertNotIn('private', text)
            self.assertIn('500000', text)

    async def test_non_finite_prices_and_invalid_packet_are_missing(self):
        self.assertEqual(trip_live.price_packet({'data': [1]})[0], 'missing')
        packet = {'data': {'physicRoomMap': {'1': {}}, 'saleRoomMap': {'s': {
            'physicalRoomId': '1', 'priceInfo': {'price': 'nan', 'currency': 'VND'}}}}}
        self.assertEqual(trip_live.price_packet(packet)[0], 'missing')


class LoadReportTests(unittest.TestCase):
    def test_reports_before_after_and_actual_written_rows(self):
        old = {'product_id': '1', 'unit_price': 10, 'available': True}
        fresh = dict(old, unit_price=20)
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / 'report.jsonl'
            write_load_report(path, [fresh], [old], {'1'}, {'1'})
            report = json.loads(path.read_text())
        self.assertEqual(report['action'], 'refresh')
        self.assertEqual((report['before']['unitPrice'], report['after']['unitPrice']), (10, 20))
        self.assertTrue(report['written'])


class DockerRunnerTests(unittest.TestCase):
    def test_monitor_command_is_the_daily_image_container_that_cd_waits_for(self):
        """CD của release-mvp-v2 chạy `run_daily_docker.sh monitor` với IMAGE daily rồi chờ container vota-daily-monitor."""
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'data' / 'interim').mkdir(parents=True)
            (root / 'env').write_text('')
            fake = root / 'docker'
            fake.write_text('#!/usr/bin/env python3\nimport os,sys,json\nopen(os.environ["CALLS"],"a").write(json.dumps(sys.argv[1:])+"\\n")\n')
            fake.chmod(0o755)
            env = dict(os.environ, PATH=f'{root}:/usr/bin:/bin', CALLS=str(root / 'calls'), DATA_DIR=str(root / 'data'),
                       ENV_FILE=str(root / 'env'), IMAGE='test:daily', CONTAINER_NAME='vota-daily', PULL='0')
            subprocess.run(['bash', str(ROOT / 'run_daily_docker.sh'), 'monitor'], check=True, env=env, capture_output=True)
            call = json.loads((root / 'calls').read_text().splitlines()[-1])
            self.assertEqual(call[call.index('--name') + 1], 'vota-daily-monitor')
            self.assertIn('test:daily', call)
            self.assertEqual(call[-4:], ['python', 'monitor.py', '--host', '127.0.0.1'])  # mặc định chỉ loopback
            self.assertIn(f'{root}/data:/data', call)
            # Link công khai tạm thời (như bản deploy 25/09): MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1.
            env.update(MONITOR_HOST='0.0.0.0', MONITOR_PUBLIC='1')
            subprocess.run(['bash', str(ROOT / 'run_daily_docker.sh'), 'monitor'], check=True, env=env, capture_output=True)
            call = json.loads((root / 'calls').read_text().splitlines()[-1])
            self.assertEqual(call[-5:], ['python', 'monitor.py', '--host', '0.0.0.0', '--allow-public-host'])

    def test_fresh_job_container_memory_is_capped(self):
        """VM 4 GB chạy chung backend: hết RAM thì chỉ tiến trình trong job cào bị giết (FRESH_MEMORY, mặc định 2500m)."""
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'data').mkdir()
            fake = root / 'docker'
            fake.write_text('#!/usr/bin/env python3\nimport os,sys,json\nopen(os.environ["CALLS"],"a").write(json.dumps(sys.argv[1:])+"\\n")\n')
            fake.chmod(0o755)
            env = dict(os.environ, PATH=f'{root}:/usr/bin:/bin', CALLS=str(root / 'calls'), FRESH_DATA_DIR=str(root / 'data'),
                       CATALOG_LOG_DIR=str(root / 'logs'), CATALOG_ENV_FILE=str(root / 'missing.env'), PULL='0')
            env.pop('FRESH_MEMORY', None)

            def memory(**extra):
                subprocess.run(['bash', str(ROOT / 'run_daily_docker.sh'), 'fresh-run', 'due'], check=True,
                               env={**env, **extra}, capture_output=True)
                call = json.loads((root / 'calls').read_text().splitlines()[-1])
                return (call[call.index('--memory') + 1], call[call.index('--memory-swap') + 1]) if '--memory' in call else None
            self.assertEqual(memory(), ('2500m', '2500m'))
            self.assertEqual(memory(FRESH_MEMORY='3g'), ('3g', '3g'))
            self.assertIsNone(memory(FRESH_MEMORY=''))

    def test_monitor_main_resolves_dirs_from_args_env_then_data_dir(self):
        seen = {}

        class Server:
            def __init__(self, address, handler):
                seen['monitor'] = handler.monitor

            def serve_forever(self):
                raise KeyboardInterrupt

            def server_close(self):
                pass
        with tempfile.TemporaryDirectory() as t, patch.object(monitor, 'ThreadingHTTPServer', Server), \
                contextlib.redirect_stdout(io.StringIO()):
            data = Path(t) / 'data'
            (data / 'logs').mkdir(parents=True)
            with patch.dict(os.environ, {'VOTA_DATA_DIR': str(data)}, clear=True):
                monitor.main([])
            m = seen['monitor']
            self.assertEqual((m.state_dir, m.run_root), (data.resolve() / 'state', data.resolve() / 'fresh_runs'))
            with patch.dict(os.environ, {'VOTA_DATA_DIR': str(data), 'CATALOG_STATE_DIR': str(Path(t) / 's')}, clear=True):
                monitor.main(['--run-root', str(Path(t) / 'r')])
            m = seen['monitor']
            self.assertEqual((m.state_dir, m.run_root), ((Path(t) / 's').resolve(), (Path(t) / 'r').resolve()))

    def test_fresh_monitor_mounts_same_volume_and_image_as_fresh_runner(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'data').mkdir()
            (root / 'logs').mkdir()
            (root / 'env').write_text('')
            fake = root / 'docker'
            fake.write_text('#!/usr/bin/env python3\nimport os,sys,json\nopen(os.environ["CALLS"],"a").write(json.dumps(sys.argv[1:])+"\\n")\n')
            fake.chmod(0o755)
            env = dict(os.environ, PATH=f'{root}:/usr/bin:/bin', CALLS=str(root / 'calls'),
                       FRESH_DATA_DIR=str(root / 'data'), CATALOG_LOG_DIR=str(root / 'logs'),
                       CATALOG_ENV_FILE=str(root / 'env'), FRESH_IMAGE='test:fresh', PULL='0')
            subprocess.run(['bash', str(ROOT / 'run_daily_docker.sh'), 'fresh-monitor', '--port', '18765'],
                           check=True, env=env, capture_output=True)
            call = json.loads((root / 'calls').read_text().splitlines()[-1])
            self.assertIn(f'{root}/data:/data', call)
            self.assertIn('test:fresh', call)
            self.assertIn('--entrypoint', call)
            self.assertIn('/app/src/data_collection/monitor.py', call)
            self.assertNotIn('/var/run/docker.sock', ' '.join(call))
            subprocess.run(['bash', str(ROOT / 'run_daily_docker.sh'), 'fresh-run', 'tick'],
                           check=True, env=env, capture_output=True)
            call = json.loads((root / 'calls').read_text().splitlines()[-1])
            self.assertEqual(call[-2:], ['test:fresh', 'tick'])
