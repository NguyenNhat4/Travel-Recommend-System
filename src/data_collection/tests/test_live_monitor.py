"""Monitor theo dõi cào local: chỉnh tốc độ live, tình trạng từng nguồn, log real-time, các bước normalize và embedding."""
import asyncio
import contextlib
import fcntl
import io
import sys
import gzip
import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import fresh_catalog
import fresh_run_log as run_log
import monitor
import normalise
from collectors import live_control, trip_live
from collectors.common import HostRateLimiter

RUN_ID = 'full-20260925T010000Z-123'
OLD_RUN = 'full-20260924T010000Z-99'


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

    def run_dir(self, name=RUN_ID, status='running', steps=(), settings=None):
        path = self.runs / name
        path.mkdir(exist_ok=True)
        run_log.write_json(path / 'run.json', {'id': name, 'mode': name.split('-')[0], 'status': status,
                                             'startedAt': '2026-09-25T01:00:00+00:00', 'steps': list(steps),
                                             'settings': settings or {}})
        return path

    def hold_lock(self, run_id=RUN_ID):
        handle = (self.state / 'fresh_catalog.lock').open('a')
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(handle.close)
        run_log.write_json(self.state / 'running.json', {'runId': run_id})
        return handle


# ---------------------------------------------------------------------------------------------------- điều khiển live


class LiveControlTests(Workspace):
    def test_validate_keeps_speed_floors_and_consistency(self):
        for key, changes in (('booking', {'delay': 1.9}), ('booking', {'delay': float('nan')}),
                             ('booking', {'delayMin': 1}), ('tripHotels', {'delayMin': 0.4}),
                             ('tripHotels', {'delayMin': 3, 'delayMax': 2}), ('nope', {'paused': True}),
                             ('trip', {'paused': 'yes'}), ('trip', {'delay': 301}), ('trip', {})):
            with self.subTest(key=key, changes=changes), self.assertRaises(live_control.LiveControlError):
                live_control.validate(key, changes)
        self.assertEqual(live_control.validate('booking', {'delay': '5', 'paused': True}), {'delay': 5.0, 'paused': True})

    def test_floors_match_settings_minimums(self):
        import fresh_settings
        for key, fields in live_control.LIMITS.items():
            for name, floor in fields.items():
                self.assertEqual(fresh_settings.BY_KEY[live_control.SETTING_KEYS[key][name]].minimum, floor)

    def test_write_merges_resets_other_run_and_clears_override(self):
        path = self.state / live_control.FILE_NAME
        live_control.write(path, 'old-run', 'booking', {'delay': 9})
        data = live_control.write(path, RUN_ID, 'booking', {'delay': 4, 'paused': True})
        self.assertEqual((data['runId'], data['sources']['booking']['delay']), (RUN_ID, 4.0))
        data = live_control.write(path, RUN_ID, 'booking', {'delay': None})
        self.assertNotIn('delay', data['sources']['booking'])
        self.assertTrue(data['sources']['booking']['paused'])

    def test_reader_follows_file_changes_and_ignores_other_runs(self):
        path = self.state / live_control.FILE_NAME
        reader = live_control.Reader(path, RUN_ID)
        with patch.object(live_control, 'CHECK_EVERY', 0):
            self.assertEqual(reader.get('agoda'), {})
            live_control.write(path, RUN_ID, 'agoda', {'delay': 6})
            self.assertEqual(reader.get('agoda'), {'delay': 6.0})
            path.write_text(json.dumps({'runId': 'other', 'sources': {'agoda': {'delay': 99}}}), encoding='utf-8')
            self.assertEqual(reader.get('agoda'), {})

    def test_recorder_clears_live_file_of_previous_run(self):
        path = self.state / live_control.FILE_NAME
        live_control.write(path, 'old-run', 'booking', {'paused': True})
        recorder = run_log.RunRecorder(self.runs / RUN_ID, self.state, run_id=RUN_ID, mode='full', trigger='test',
                                       settings={}).start()
        self.assertFalse(path.exists())
        live_control.write(path, RUN_ID, 'booking', {'paused': True})
        recorder.finish('ok', 0)
        self.assertFalse(path.exists())


class LimiterLiveTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / live_control.FILE_NAME
        env = patch.dict(os.environ, {'CRAWL_LIVE_FILE': str(self.path), 'CRAWL_RUN_ID': RUN_ID,
                                      'CRAWL_LIVE_KEY': 'booking'})
        env.start()
        self.addCleanup(env.stop)
        for name, value in (('CHECK_EVERY', 0), ('PAUSE_POLL', 0.02)):
            patcher = patch.object(live_control, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def control(self, key, **values):  # ghi thẳng file: test dùng khoảng chờ nhỏ hơn mức tối thiểu của monitor
        data = live_control.read(self.path) or {'runId': RUN_ID, 'sources': {}}
        data['sources'][key] = values
        self.path.write_text(json.dumps(data), encoding='utf-8')

    async def test_live_delay_replaces_configured_interval_immediately(self):
        limiter = HostRateLimiter(30, jitter=0)
        await limiter.wait('https://www.booking.com/a')
        self.control('booking', delay=0.05)
        started = time.monotonic()
        await asyncio.wait_for(limiter.wait('https://www.booking.com/b'), 2)
        self.assertLess(time.monotonic() - started, 1.5)

    async def test_pause_holds_requests_until_resumed(self):
        limiter = HostRateLimiter(0, jitter=0)
        self.control('booking', paused=True)
        task = asyncio.create_task(limiter.wait('https://www.booking.com/a'))
        await asyncio.sleep(0.15)
        self.assertFalse(task.done())
        self.control('booking', paused=False)
        await asyncio.wait_for(task, 1)

    async def test_other_source_is_not_paused(self):
        self.control('agoda', paused=True)
        await asyncio.wait_for(HostRateLimiter(0).wait('https://www.booking.com/a'), 1)

    async def test_trip_hotel_pacing_uses_live_delays_and_pause(self):
        options = trip_live.LiveOptions(delay_min=30, delay_max=30)
        clock = {'last': asyncio.get_running_loop().time()}
        self.control('tripHotels', delayMin=0.01, delayMax=0.02)
        await asyncio.wait_for(trip_live.next_start(clock, options), 1)
        self.control('tripHotels', paused=True, delayMin=0.01, delayMax=0.02)
        task = asyncio.create_task(trip_live.next_start(clock, options))
        await asyncio.sleep(0.1)
        self.assertFalse(task.done())
        self.control('tripHotels', delayMin=0.01, delayMax=0.02)
        await asyncio.wait_for(task, 1)


# ---------------------------------------------------------------------------------------------------- tình trạng nguồn


LOG = """01:00:00 catalog.step.start name=maintain
01:00:01 catalog.group.start name=trip
01:00:01 catalog.step.start name=trip-flights group=trip
01:00:02 [trip] 01:00:02 INFO    [trip_flights] 3/10 xong · 0 lỗi · 0 bỏ qua · 12.00 trang/phút · còn ~1m
01:00:03 [trip] 01:00:03 WARNING https://www.trip.com/x trả 429 – chờ 5s rồi thử lại
01:00:04 catalog.step.start name=trip-attractions group=trip
01:00:05 [trip] 01:00:05 INFO    Bắt đầu 5 URL
01:00:06 [booking] 01:00:06 WARNING [booking_hotels] Bị chặn (2 liên tiếp) – nghỉ 60s
01:00:07 Trip meta 123 lần 1: HTTP 200 · 100 ms · 10 B
01:00:08 Trip 123@2026-10-09: priced, 4 offers
01:00:09 catalog.group.skip name=agoda
"""
STEPS = [{'name': 'maintain', 'status': 'ok'},
         {'name': 'trip-flights', 'group': 'trip', 'status': 'ok', 'seconds': 3},
         {'name': 'trip-attractions', 'group': 'trip', 'status': 'running'},
         {'name': 'booking-hotels', 'group': 'booking', 'status': 'blocked', 'detail': {'exitCode': 75}},
         {'name': 'vinpearl', 'group': 'vinpearl', 'status': 'error', 'error': 'RuntimeError: Nguồn vinpearl dừng với mã 1'}]


class HealthTests(Workspace):
    def write_interim(self, run, name, n):
        (run / 'interim').mkdir(exist_ok=True)
        (run / 'interim' / f'{name}.jsonl').write_text(''.join(json.dumps({'key': str(i)}) + '\n' for i in range(n)),
                                                      encoding='utf-8')

    def test_sources_report_progress_errors_blocks_skips_and_drops(self):
        old = self.run_dir(OLD_RUN, status='ok')
        self.write_interim(old, 'trip_flights', 10)
        run = self.run_dir(steps=STEPS, settings={'sources.agoda': True, 'sources.tripHotels': True})
        (run / 'job.log').write_text(LOG, encoding='utf-8')
        self.write_interim(run, 'trip_flights', 2)
        (run / 'raw' / 'trip_flights' / 'json').mkdir(parents=True)
        (run / 'raw' / 'trip_flights' / 'json' / 'a.json').write_text('{}', encoding='utf-8')
        self.hold_lock()
        health = self.monitor.health(RUN_ID)
        rows = {row['key']: row for row in health['sources']}
        self.assertTrue(health['running'])
        self.assertEqual(health['previousRun'], OLD_RUN)
        flights = rows['tripFlights']
        self.assertEqual((flights['state'], flights['interim'], flights['prevInterim'], flights['rawFiles']), ('ok', 2, 10, 1))
        self.assertEqual(flights['log']['progress']['done'], 3)
        self.assertEqual(flights['log']['http'], {'429': 1})
        self.assertTrue(any('giảm mạnh' in note for note in flights['notes']))
        self.assertEqual((rows['tripAttractions']['state'], rows['tripAttractions']['log']['lines']), ('running', 1))
        self.assertEqual((rows['booking']['state'], rows['booking']['lost'], rows['booking']['log']['blocks']),
                         ('blocked', True, 1))
        self.assertEqual((rows['vinpearl']['state'], rows['vinpearl']['lost']), ('error', True))
        self.assertIn('mã 1', ' '.join(rows['vinpearl']['notes']))
        self.assertEqual((rows['agoda']['state'], rows['agoda']['lost']), ('skipped', True))
        hotels = rows['tripHotels']
        self.assertEqual((hotels['state'], hotels['log']['tripPrices'], hotels['log']['tripMeta']),
                         ('waiting', {'priced': 1}, {'ok': 1}))
        with (run / 'job.log').open('a', encoding='utf-8') as fh:
            fh.write('01:00:10 [trip] 01:00:10 ERROR   [trip_attractions] Không mở được trang\n')
        rows = {row['key']: row for row in self.monitor.health(RUN_ID)['sources']}
        self.assertEqual((rows['tripAttractions']['log']['lines'], rows['tripAttractions']['log']['errors']), (2, 1))

    def test_finished_source_without_records_is_lost_and_daily_skips_site_sources(self):
        self.run_dir(status='ok', steps=[{'name': 'trip-flights', 'status': 'ok'}],
                     settings={'sources.booking': False})
        rows = {row['key']: row for row in self.monitor.health(RUN_ID)['sources']}
        self.assertEqual((rows['tripFlights']['state'], rows['tripFlights']['lost']), ('empty', True))
        self.assertEqual(rows['booking']['state'], 'disabled')
        self.assertEqual(rows['agoda']['state'], 'notRun')
        daily = 'daily-20260925T010000Z-5'
        self.run_dir(daily, status='ok', steps=[{'name': 'trip-hotels.prices', 'status': 'ok'}])
        rows = {row['key']: row for row in self.monitor.health(daily)['sources']}
        self.assertEqual(rows['vinpearl']['state'], 'notInMode')


class LiveApiTests(Workspace):
    def test_live_changes_need_running_run_and_report_run_settings(self):
        self.assertEqual(self.monitor.set_live('booking', {'delay': 5})[0], 409)
        self.run_dir(settings={'booking.delay': 3.0, 'tripHotels.delayMin': 0.5, 'tripHotels.delayMax': 1.0})
        self.hold_lock()
        code, data = self.monitor.set_live('booking', {'delay': 5, 'paused': True})
        self.assertEqual(code, 200)
        booking = next(row for row in data['sources'] if row['key'] == 'booking')
        self.assertEqual((booking['paused'], booking['fields'][0]['base'], booking['fields'][0]['value']), (True, 3.0, 5.0))
        self.assertEqual({f['key'] for f in data['nextRun']}, set(monitor.NEXT_RUN_KEYS))
        with self.assertRaises(live_control.LiveControlError):
            self.monitor.set_live('booking', {'delay': 0.5})


# ---------------------------------------------------------------------------------------------------- log real-time


class StreamTests(Workspace):
    def setUp(self):
        super().setUp()
        handler = type('TestHandler', (monitor.Handler,), {'monitor': self.monitor})
        self.server = monitor.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        for name, value in (('STREAM_POLL', 0.05), ('STREAM_END_IDLE', 0.2)):
            patcher = patch.object(monitor, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def events(response, count):
        out, event = [], None
        while len(out) < count:
            line = response.fp.readline().decode('utf-8')
            if not line:
                break
            if line.startswith('event: '):
                event = line[7:].strip()
            elif line.startswith('data: '):
                out.append((event, json.loads(line[6:])))
        return out

    def test_stream_sends_tail_then_new_lines_then_end(self):
        run = self.run_dir()
        (run / 'job.log').write_text('01:00:00 a\n01:00:01 b\n', encoding='utf-8')
        lock = self.hold_lock()
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request('GET', f'/api/log/stream?run={RUN_ID}&lines=10')
        response = conn.getresponse()
        self.assertEqual(response.getheader('Content-Type'), 'text/event-stream; charset=utf-8')
        self.assertEqual(self.events(response, 1), [('init', {'lines': ['01:00:00 a', '01:00:01 b']})])
        with (run / 'job.log').open('a', encoding='utf-8') as fh:
            fh.write('01:00:02 c\n01:00:03 d')
            fh.flush()
            self.assertEqual(self.events(response, 1), [('lines', {'lines': ['01:00:02 c']})])
            fh.write('\n')
        self.assertEqual(self.events(response, 1), [('lines', {'lines': ['01:00:03 d']})])
        lock.close()
        self.assertEqual(self.events(response, 1)[0][0], 'end')
        conn.close()

    def test_stream_rejects_unknown_run_and_foreign_host(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        conn.request('GET', '/api/log/stream?run=../../etc')
        self.assertEqual(conn.getresponse().status, 400)
        conn.close()
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        conn.request('GET', f'/api/log/stream?run={RUN_ID}', headers={'Host': 'evil.example'})
        self.assertEqual(conn.getresponse().status, 403)
        conn.close()


# ---------------------------------------------------------------------------------------------------- các bước normalize


TRIP_RECORD = {'recordType': 'trip_hotel', 'key': 'hotel:999', 'hotelId': '999', 'name': 'Khách sạn thử nghiệm',
               'city': 'Nha Trang', 'description': 'Khách sạn thử nghiệm tại Nha Trang.',
               'rooms': [{'roomId': '7', 'name': 'Deluxe', 'currency': 'VND', 'pricesByDate': {'2026-10-08': 700000}},
                         {'roomId': '8', 'name': 'Suite', 'currency': 'VND', 'pricesByDate': {'2026-10-08': 900000}}],
               'priceDatesQueried': ['2026-10-08'], 'currency': 'VND', 'crawledAt': '2026-09-24T00:00:00Z',
               'plan': {'destination': 'Nha Trang'}}


class NormaliseStageTests(Workspace):
    def normalise(self, *extra):
        run = self.run_dir(status='ok')
        (run / 'interim').mkdir()
        (run / 'interim' / 'trip_hotels.jsonl').write_text(json.dumps(TRIP_RECORD, ensure_ascii=False) + '\n',
                                                          encoding='utf-8')
        args = ['--data-dir', str(run), '--no-plan', '--rooms-per-hotel', '0', '--keep-unsellable',
                '--keep-location-warnings', '--keep-price-outliers', '--stage-dir', str(run / 'normalise_stages'), *extra]
        self.assertEqual(normalise.main(args), 0)
        return run

    def test_stages_record_rows_and_dropped_reasons_without_changing_output(self):
        run = self.normalise()  # khách sạn thử không có toạ độ → bước kiểm vị trí xoá cả 3 dòng
        self.assertEqual((run / 'products.jsonl').read_text(encoding='utf-8'), '')
        summary = self.monitor.normalise(RUN_ID)
        self.assertEqual([(s['id'], s['rows']) for s in summary['stages']],
                         [('mapped', 3), ('merged', 3), ('filtered', 3), ('enriched', 3), ('final', 0)])
        self.assertEqual([s['bySource'] for s in summary['stages']], [{'trip': 3}] * 4 + [{}])
        self.assertEqual(summary['dropped'], {'location': 3})
        self.assertEqual([(r['step'], r['reason'], r['rows']) for r in summary['dropReasons']], [('location', 'thiếu toạ độ', 3)])
        mapped = self.monitor.normalise_rows(RUN_ID, 'mapped')
        self.assertEqual(mapped['rows'][0]['input'], {'key': 'hotel:999', 'hotelId': '999', 'recordType': 'trip_hotel'})
        self.assertEqual(self.monitor.normalise_row(RUN_ID, 'mapped', 0)['entry']['interim'], 'trip_hotels')
        dropped = self.monitor.normalise_rows(RUN_ID, 'dropped', step='location', q='deluxe')
        self.assertEqual(dropped['total'], 1)
        trace = self.monitor.normalise_trace(RUN_ID, 'trip:hotel:999')
        self.assertEqual([len(s['rows']) for s in trace['stages']], [1, 1, 1, 1, 0])
        self.assertEqual(len(trace['dropped']), 1)
        with self.assertRaises(ValueError):
            self.monitor.normalise_rows(RUN_ID, '../x')

    def test_trace_shows_fields_changed_between_stages(self):
        self.normalise('--keep-missing-coordinates')
        rows = [json.loads(x) for x in (self.runs / RUN_ID / 'products.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(rows), 3)
        hotel = rows[0]['productId']
        trace = self.monitor.normalise_trace(RUN_ID, hotel)
        self.assertEqual([len(s['rows']) for s in trace['stages']], [1, 1, 1, 1, 1])
        final = trace['stages'][-1]
        self.assertIsInstance(final['diff'], dict)
        self.assertIn('_meta', final['diff'])  # products.jsonl bỏ khoá nội bộ _meta của các bước trước
        self.assertEqual(self.monitor.normalise(RUN_ID)['stages'][-1]['bySource'], {'trip': 3})
        self.assertEqual(self.monitor.normalise_rows(RUN_ID, 'final')['facets']['source'], {'trip': 3})

    def test_without_stage_dir_nothing_is_written(self):
        dump = normalise.StageDump(None)
        dump.add('mapped', [{'x': 1}], 'trip_hotels')
        dump.close([], 0)
        self.assertEqual(list(self.root.rglob('stages.json')), [])


# ---------------------------------------------------------------------------------------------------- chuẩn hoá nháp


class PreviewTests(Workspace):
    def trip_run(self):
        run = self.run_dir(status='running')
        (run / 'interim').mkdir()
        (run / 'interim' / 'trip_hotels.jsonl').write_text(json.dumps(TRIP_RECORD, ensure_ascii=False) + '\n',
                                                          encoding='utf-8')
        (run / 'interim' / 'booking_hotels.jsonl').write_text('{}\n', encoding='utf-8')  # site chưa xong: không lấy
        return run

    def test_finished_site_is_normalised_into_preview_and_monitor_reads_it(self):
        run = self.trip_run()
        previewer = fresh_catalog.Previewer(run, None)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            previewer.group_done('trip', 'ok')
            previewer.finish(keep=True)
        info = json.loads((run / 'preview' / 'preview.json').read_text(encoding='utf-8'))
        self.assertEqual((info['status'], info['rows'], info['sources'], info['groups']),
                         ('ok', 3, ['trip_hotels'], {'trip': 'ok'}))
        meta = json.loads((run / 'normalised' / 'trip_hotels.meta.json').read_text(encoding='utf-8'))
        self.assertEqual((meta['status'], meta['records'], meta['rows']), ('ok', 1, 3))  # checkpoint thật của lượt
        self.assertFalse((run / 'normalised' / 'booking_hotels.meta.json').exists())  # site chưa xong: chưa chuẩn hoá
        self.assertFalse((run / 'products.jsonl').exists())  # bản chính thức không bị đụng
        self.assertIn('catalog.preview.done groups=trip sources=trip_hotels rows=3', out.getvalue())
        self.assertEqual(self.monitor.run(RUN_ID)['preview']['rows'], 3)
        self.assertEqual(self.monitor.products(RUN_ID, preview=True)['total'], 3)
        self.assertEqual([s['rows'] for s in self.monitor.normalise(RUN_ID, preview=True)['stages']], [3, 3, 3, 3, 3])
        hotel = self.monitor.products(RUN_ID, preview=True, level='property')['rows'][0]['productId']
        self.assertIsNone(self.monitor.product(RUN_ID, hotel, preview=True)['db'])
        self.assertEqual(len(self.monitor.normalise_trace(RUN_ID, hotel, preview=True)['stages']), 5)
        self.monitor.health(RUN_ID)  # bảng nguồn đếm dòng interim: không được làm hỏng bản ghi interim đã cache
        self.assertEqual(self.monitor.product(RUN_ID, hotel, preview=True)['product']['productId'], hotel)
        with self.assertRaises(ValueError):
            self.monitor.products(RUN_ID)  # chưa có bản chính thức

    def test_sites_finishing_during_a_preview_are_coalesced_into_one_more_run(self):
        previewer = fresh_catalog.Previewer(self.root, None)
        seen, gate = [], threading.Event()

        def build(groups):
            seen.append(sorted(groups))
            gate.wait(2)
        with patch.object(previewer, '_build', build):
            previewer.group_done('trip', 'ok')
            time.sleep(0.05)
            previewer.group_done('vinpearl', 'ok')
            previewer.group_done('booking', 'error')
            gate.set()
            previewer.finish(keep=True)
        self.assertEqual(seen, [['trip'], ['booking', 'trip', 'vinpearl']])

    def test_official_normalise_stops_a_running_preview(self):
        run = self.trip_run()
        previewer = fresh_catalog.Previewer(run, None)
        real_popen = fresh_catalog.subprocess.Popen

        def slow(command, **kwargs):  # chỉ bước gộp nháp chạy lâu; chuẩn hoá theo nguồn chạy thật
            if '--merge-only' in command:
                command = [sys.executable, '-c', 'import time; time.sleep(30)']
            return real_popen(command, **kwargs)
        with patch.object(fresh_catalog.subprocess, 'Popen', slow), contextlib.redirect_stdout(io.StringIO()):
            previewer.group_done('trip', 'ok')
            deadline = time.monotonic() + 5
            while previewer.proc is None and time.monotonic() < deadline:
                time.sleep(0.02)
            started = time.monotonic()
            previewer.finish(keep=False)
        self.assertLess(time.monotonic() - started, 5)
        self.assertFalse((run / 'preview').exists())
        self.assertFalse((run / 'preview.next').exists())
        self.assertTrue((run / 'normalised' / 'trip_hotels.meta.json').exists())  # checkpoint vẫn giữ cho bản chính thức

    def test_last_site_is_normalised_per_source_without_a_preview_and_official_run_reuses_it(self):
        run = self.trip_run()
        previewer = fresh_catalog.Previewer(run, None)
        with contextlib.redirect_stdout(io.StringIO()):
            previewer.group_done('trip', 'ok', merge=False)
            previewer.finish(keep=False)
        self.assertTrue((run / 'normalised' / 'trip_hotels.meta.json').exists())
        self.assertFalse((run / 'preview').exists())
        (run / 'interim' / 'booking_hotels.jsonl').unlink()
        with self.assertLogs('normalise', 'INFO') as logs:
            products = fresh_catalog.normalize(run, None)
        self.assertTrue(any('normalise.source.reuse name=trip_hotels' in line for line in logs.output))
        self.assertEqual(len(products.read_text(encoding='utf-8').splitlines()), 3)

    # P1 (docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md)
    def counting(self, previewer):
        calls, real = [], previewer._normalise_source

        def normalise_source(group, stem, merge=True):
            calls.append((group, stem, merge))
            real(group, stem, merge)
        return calls, patch.object(previewer, '_normalise_source', normalise_source)

    def test_source_done_normalises_its_file_now_and_group_done_only_the_rest(self):
        run = self.trip_run()
        (run / 'interim' / 'trip_flights.jsonl').write_text('', encoding='utf-8')
        previewer = fresh_catalog.Previewer(run, None)
        calls, patcher = self.counting(previewer)
        merges = []
        with patcher, patch.object(previewer, '_request_merge', lambda: merges.append(1)), \
                contextlib.redirect_stdout(io.StringIO()):
            previewer.source_done('trip', ('trip_hotels',), merge=True)
            for job in list(previewer.jobs):
                job.result()
            # checkpoint thật có ngay, trước khi nhóm xong
            self.assertTrue((run / 'normalised' / 'trip_hotels.meta.json').exists())
            previewer.source_done('trip', ('trip_hotels', 'trip_combos'))  # giao lại / file không có: bỏ qua
            previewer.group_done('trip', 'ok')
            previewer.finish(keep=False)
        self.assertEqual(calls, [('trip', 'trip_hotels', True), ('trip', 'trip_flights', True)])
        self.assertEqual(len(merges), 2)  # mỗi file một lần gộp nháp; group_done không gộp thêm
        self.assertEqual(previewer.done, {'trip': 'ok'})

    def test_group_done_still_merges_a_group_that_produced_no_file(self):
        previewer = fresh_catalog.Previewer(self.run_dir(), None)
        merges = []
        with patch.object(previewer, '_request_merge', lambda: merges.append(1)):
            previewer.group_done('trip', 'blocked')
            previewer.group_done('vinpearl', 'ok', merge=False)
            previewer.finish(keep=False)
        self.assertEqual(len(merges), 1)

    def test_group_done_does_not_merge_again_when_its_sources_already_did(self):
        run = self.trip_run()
        previewer = fresh_catalog.Previewer(run, None)
        calls, patcher = self.counting(previewer)
        merges = []
        with patcher, patch.object(previewer, '_request_merge', lambda: merges.append(1)), \
                contextlib.redirect_stdout(io.StringIO()):
            previewer.source_done('trip', ('trip_hotels',), merge=False)  # bước cuối của lượt
            previewer.group_done('trip', 'ok', merge=False)
            previewer.finish(keep=False)
        self.assertEqual((calls, merges), ([('trip', 'trip_hotels', False)], []))

    def test_source_done_after_close_is_ignored(self):
        run = self.trip_run()
        previewer = fresh_catalog.Previewer(run, None)
        previewer.finish(keep=False)
        previewer.source_done('trip', ('trip_hotels',))
        self.assertEqual(previewer.jobs, [])
        self.assertFalse((run / 'normalised').exists())

    def test_stream_mode_closes_a_source_when_its_step_finishes(self):
        run = self.trip_run()
        previewer = fresh_catalog.Previewer(run, None)
        closed = []
        previewer.stream = SimpleNamespace(finish_source=lambda stem: closed.append(stem) or {'status': 'ok'},
                                           close=lambda: closed.append('close'))
        with patch.object(previewer, '_request_merge', lambda: None):
            previewer.source_done('trip', ('trip_hotels',))
            for job in list(previewer.jobs):
                job.result()
            self.assertEqual(closed, ['trip_hotels'])  # chốt ngay, trước khi nhóm xong
            previewer.group_done('trip', 'ok')
            previewer.finish(keep=False)
        self.assertEqual(closed, ['trip_hotels', 'close'])


class PreviewTriggerTests(unittest.TestCase):
    class Recorder:
        def __init__(self):
            self.done, self.sources, self.events, self.finished = [], [], [], None

        def group_done(self, name, status, merge=True):
            self.done.append((name, status, merge))
            self.events.append(('group', name))

        def source_done(self, group, stems, merge=True):
            self.sources.append((group, tuple(stems), merge))
            self.events.append(('source', tuple(stems)))

        def finish(self, keep):
            self.finished = keep

    def run_sites(self, codes, delays, groups=None, recorder=None):
        recorder = recorder or self.Recorder()

        def fake_source(run_dir, source, destinations, group, deadline=None, on_start=None):
            recorder.events.append(('crawl.start', source))
            time.sleep(delays.get(source, 0))
            recorder.events.append(('crawl.end', source))
            code = codes.get(source, 0)
            return code(source) if callable(code) else code
        groups = groups or [('trip', ('trip-flights',)), ('vinpearl', ('vinpearl',)), ('booking', ('booking-hotels',)),
                            ('agoda', ('agoda-hotels',)), ('empty', ())]
        # Thứ tự xong do độ trễ giả lập quyết định: bỏ khoá một Chromium (BROWSER_STEPS) để các site chạy song song thật.
        with patch.object(fresh_catalog, 'run_source', fake_source), \
                patch.object(fresh_catalog, 'wait_or_stop', lambda seconds: None), \
                patch.object(fresh_catalog, 'BROWSER_STEPS', set()), \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                fresh_catalog.crawl_sites(Path('/tmp/unused'), '@deep', groups, 4, recorder)
            except RuntimeError:
                pass
        return recorder

    def test_every_site_is_normalised_but_the_last_of_a_clean_run_gets_no_preview(self):
        delays = {'trip-flights': 0.01, 'vinpearl': 0.1, 'booking-hotels': 0.2, 'agoda-hotels': 0.3}
        recorder = self.run_sites({}, delays)
        self.assertEqual(recorder.done, [('trip', 'ok', True), ('vinpearl', 'ok', True), ('booking', 'ok', True),
                                         ('agoda', 'ok', False)])
        self.assertEqual(recorder.sources, [('trip', ('trip_flights',), True),
                                            ('vinpearl', ('vinpearl', 'vinpearl_bundles'), True),
                                            ('booking', ('booking_hotels',), True), ('agoda', ('agoda_api',), False)])
        self.assertFalse(recorder.finished)

    def test_partial_run_finishes_previews_before_building_the_official_catalog(self):
        delays = {'trip-flights': 0.01, 'vinpearl': 0.1, 'booking-hotels': 0.2, 'agoda-hotels': 0.3}
        recorder = self.run_sites({'vinpearl': 1}, delays)
        self.assertEqual(recorder.done, [('trip', 'ok', True), ('vinpearl', 'error', True), ('booking', 'ok', True),
                                         ('agoda', 'ok', False)])
        self.assertEqual(len(recorder.sources), 4)
        self.assertFalse(recorder.finished)

    # P1 (docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md): chuẩn hoá theo bước cào, không đợi cả nhóm site
    def test_source_is_normalised_while_the_next_step_of_its_group_still_crawls(self):
        recorder = self.run_sites({}, {'trip-flights': 0.01, 'trip-attractions': 0.3},
                                  groups=[('trip', ('trip-flights', 'trip-attractions'))])
        events = recorder.events
        self.assertLess(events.index(('source', ('trip_flights',))), events.index(('crawl.end', 'trip-attractions')))
        self.assertLess(events.index(('crawl.end', 'trip-attractions')), events.index(('group', 'trip')))
        # bước cuối của lượt không lỗi: không gộp nháp; bước trước đó thì có
        self.assertEqual(recorder.sources, [('trip', ('trip_flights',), True), ('trip', ('trip_attractions',), False)])
        self.assertEqual(recorder.done, [('trip', 'ok', False)])

    def test_only_the_final_step_of_the_last_group_skips_the_preview(self):
        # nhóm trip xong sau: bước cuối của nó là bước cuối của lượt; bước đầu của nó thì không (vinpearl còn chạy)
        recorder = self.run_sites({}, {'trip-flights': 0.01, 'trip-attractions': 0.4, 'vinpearl': 0.2},
                                  groups=[('trip', ('trip-flights', 'trip-attractions')), ('vinpearl', ('vinpearl',))])
        self.assertEqual(recorder.sources, [('trip', ('trip_flights',), True),
                                            ('vinpearl', ('vinpearl', 'vinpearl_bundles'), True),
                                            ('trip', ('trip_attractions',), False)])

    def test_blocked_step_is_normalised_once_right_after_it_stops(self):
        recorder = self.run_sites({'trip-flights': 75}, {'trip-attractions': 0.2},
                                  groups=[('trip', ('trip-flights', 'trip-attractions'))])
        self.assertEqual([s for s in recorder.sources if s[1] == ('trip_flights',)], [('trip', ('trip_flights',), True)])
        self.assertLess(recorder.events.index(('source', ('trip_flights',))),
                        recorder.events.index(('crawl.end', 'trip-attractions')))
        self.assertEqual(recorder.done, [('trip', 'ok', False)])  # mã 75 vẫn tính là nhóm chạy xong

    def test_retried_step_is_normalised_only_after_its_last_attempt(self):
        attempts = []

        self.addCleanup(fresh_catalog.SOURCE_TAIL.pop, 'trip-flights', None)

        def flaky(source):  # lần đầu lỗi tạm thời, lần thử lại thành công
            attempts.append(source)
            if len(attempts) == 1:
                fresh_catalog.SOURCE_TAIL[source] = deque(['TimeoutError: timed out'])
                return 1
            return 0
        recorder = self.run_sites({'trip-flights': flaky}, {}, groups=[('trip', ('trip-flights',))])
        self.assertEqual(len(attempts), 2)
        self.assertEqual(recorder.sources, [('trip', ('trip_flights',), False)])
        crawls = [i for i, e in enumerate(recorder.events) if e == ('crawl.end', 'trip-flights')]
        self.assertGreater(recorder.events.index(('source', ('trip_flights',))), crawls[-1])

    def test_failed_step_is_sealed_and_independent_steps_still_normalise(self):
        recorder = self.run_sites({'trip-attractions': 2}, {},
                                  groups=[('trip', ('trip-flights', 'trip-attractions', 'booking-hotels'))])
        self.assertEqual(recorder.sources, [('trip', ('trip_flights',), True),
                         ('trip', ('trip_attractions',), True), ('trip', ('booking_hotels',), False)])
        self.assertEqual(recorder.done, [('trip', 'error', False)])

    def test_in_process_steps_declare_their_interim_and_skipped_steps_are_not_normalised(self):
        def prices():
            pass
        prices.step = 'trip-hotels.prices'

        def discover():
            pass
        recorder = self.run_sites({}, {}, groups=[('trip', (discover, 'trip-flights', prices))])
        self.assertEqual(recorder.sources, [('trip', ('trip_flights',), True), ('trip', ('trip_hotels',), False)])

        def blocked():
            raise fresh_catalog.perr.BlockedError('0 nơi lưu trú')
        blocked.step = 'trip-hotels.discover'
        recorder = self.run_sites({}, {}, groups=[('trip', (blocked, 'trip-flights', prices))])
        self.assertEqual(recorder.sources, [('trip', ('trip_flights',), True)])  # bước giá phòng bị bỏ: không có file
        self.assertEqual(recorder.done, [('trip', 'blocked', False)])


# ---------------------------------------------------------------------------------------------------- theo thành phố


def product(ref, taxonomy, level, city, same_as=()):
    attrs = {'level': level} if level else {}
    if same_as:
        attrs['sameAs'] = list(same_as)
    return {'productId': ref, 'name': ref, 'taxonomy': taxonomy, 'destination': city, 'sourceRef': ref, 'attributes': attrs}


class CitiesTests(Workspace):
    def write(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')

    def test_catalog_matrix_and_live_interim_counts_per_city(self):
        run = self.run_dir(status='ok')
        self.write(run / 'products.jsonl', [
            product('vinpearl:hotel:1', 'hotel', 'property', 'Nha Trang'),
            product('vinpearl:hotel:1:room:a', 'hotel', 'room', 'Nha Trang'),
            product('booking:hotel:2', 'hotel', 'property', 'Hà Nội', same_as=['agoda:hotel:9']),
            product('trip:attraction:3', 'attraction', None, 'Nha Trang'),
            product('trip:route:HAN-CXR', 'flight', 'route', 'Nha Trang')])
        interim = run / 'interim'
        self.write(interim / 'booking_hotels.jsonl', [{'key': 'a', 'plan': {'destination': 'Hà Nội'}}] * 2)
        self.write(interim / 'vinpearl.jsonl', [{'recordType': 'vinpearl_hotel', 'name': 'Vinpearl X'}])
        self.write(interim / 'trip_flights.jsonl', [{'fromCity': 'Hanoi', 'toCity': 'Nha Trang'}])
        data = self.monitor.cities(RUN_ID)
        catalog = {e['destination']: e for e in data['catalog']['destinations']}
        self.assertEqual(data['catalog']['types'], ['Khách sạn', 'Hạng phòng', 'Điểm tham quan / vé', 'Tuyến bay'])
        self.assertEqual((catalog['Nha Trang']['total'], catalog['Nha Trang']['bySource']), (4, {'vinpearl': 2, 'trip': 2}))
        self.assertEqual((catalog['Hà Nội']['byType'], catalog['Hà Nội']['merged']), ({'Khách sạn': 1}, 1))
        live = {e['destination']: e for e in data['interim']['destinations']}
        self.assertEqual(live['Hà Nội']['bySource'], {'booking_hotels': 2})
        self.assertEqual(live['Nha Trang']['bySource'], {'trip_flights': 1})
        self.assertEqual(live[monitor.UNKNOWN_CITY]['bySource'], {'vinpearl': 1})
        self.assertEqual(data['interim']['destinations'][-1]['destination'], monitor.UNKNOWN_CITY)
        with (interim / 'booking_hotels.jsonl').open('a', encoding='utf-8') as fh:  # site đang cào ghi thêm
            fh.write(json.dumps({'key': 'b', 'plan': {'destination': 'Đà Nẵng'}}) + '\n{"key": "c", "pl')
        live = {e['destination']: e for e in self.monitor.cities(RUN_ID)['interim']['destinations']}
        self.assertEqual((live['Hà Nội']['total'], live['Đà Nẵng']['total']), (2, 1))
        self.write(interim / 'booking_hotels.jsonl', [{'key': 'a', 'plan': {'destination': 'Huế'}}])  # site ghi lại file
        live = {e['destination']: e for e in self.monitor.cities(RUN_ID)['interim']['destinations']}
        self.assertEqual((live.get('Hà Nội'), live['Huế']['total']), (None, 1))

    def test_without_catalog_reports_reason_and_preview_is_used_when_asked(self):
        run = self.run_dir()
        data = self.monitor.cities(RUN_ID)
        self.assertIsNone(data['catalog'])
        self.assertIn('chuẩn hoá', data['catalogError'])
        self.write(run / 'preview' / 'products.jsonl', [product('booking:hotel:2', 'hotel', 'property', 'Huế')])
        (run / 'preview' / 'preview.json').write_text('{"status": "ok"}', encoding='utf-8')
        self.assertEqual(self.monitor.cities(RUN_ID, preview=True)['catalog']['destinations'][0]['destination'], 'Huế')


# ---------------------------------------------------------------------------------------------------- embedding


DETAIL = [
    {'productId': 'P1', 'action': 'embedded', 'reason': 'new', 'name': 'Resort biển', 'taxonomy': 'hotel',
     'destination': 'Nha Trang', 'textHash': 'h1', 'chars': 40, 'words': 8, 'text': 'Resort biển Nha Trang có hồ bơi',
     'vector': {'dims': 3, 'norm': 1.0, 'head': [1.0, 0.0, 0.0]}},
    {'productId': 'P2', 'action': 'unchanged', 'reason': None, 'name': 'Vé cáp treo', 'taxonomy': 'attraction',
     'destination': 'Nha Trang', 'textHash': 'h2', 'chars': 20, 'words': 4, 'text': 'Vé cáp treo'},
    {'productId': 'GONE', 'action': 'deleted'},
]


class EmbedTests(Workspace):
    def setUp(self):
        super().setUp()
        run = self.run_dir(status='ok')
        (run / 'index_detail.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in DETAIL),
                                                encoding='utf-8')
        (run / 'index_report.json').write_text(json.dumps({'modelVersion': 'm:v2', 'searchUnits': 2}), encoding='utf-8')

    def test_embed_summary_filters_and_row(self):
        data = self.monitor.embed(RUN_ID)
        self.assertEqual(data['actions'], {'embedded': 1, 'unchanged': 1, 'deleted': 1})
        self.assertEqual((data['reasons'], data['report']['modelVersion']), ({'new': 1}, 'm:v2'))
        self.assertEqual(self.monitor.embed(RUN_ID, action='embedded')['rows'][0]['norm'], 1.0)
        self.assertEqual(self.monitor.embed(RUN_ID, q='cáp treo')['total'], 1)
        self.assertEqual(self.monitor.embed_row(RUN_ID, 'P2')['text'], 'Vé cáp treo')
        with self.assertRaises(ValueError):
            self.monitor.embed_row(RUN_ID, 'nope')

    def test_query_ranks_collection_vectors_by_cosine(self):
        class Embedder:
            def __init__(self, *args, **kwargs):
                pass

            def embed_query(self, q):
                return np.array([0.9, 0.1, 0.0], dtype=np.float32)

            def close(self):
                pass

        vectors = {'ids': ['P2', 'P1', 'X'], 'matrix': np.array([[0, 1, 0], [1, 0, 0], [0.7, 0.7, 0]], np.float32),
                   'models': {'m:v2': 3}}
        vectors['norms'] = np.linalg.norm(vectors['matrix'], axis=1)
        monitor.ensure_backend_path()
        settings = SimpleNamespace(embed_model='intfloat/multilingual-e5-small', embed_dimension=3,
                                   vector_collection='ProductCrawl')
        with patch('src.backend.app.infrastructure.embeddings.factory.build_embedder', lambda settings: Embedder()), \
                patch.object(self.monitor, '_index_settings', return_value=settings), \
                patch.object(self.monitor, '_collection_vectors', return_value=vectors):
            result = self.monitor.embed_query(RUN_ID, 'resort gần biển', 2)
        self.assertEqual([hit['productId'] for hit in result['hits']], ['P1', 'X'])
        self.assertEqual((result['hits'][0]['name'], result['hits'][1]['inRun']), ('Resort biển', False))
        with self.assertRaises(ValueError):
            self.monitor.embed_query(RUN_ID, ' ')


# ---------------------------------------------------------------------------------------------------- chặn đích local


class LocalOnlyGuardTests(unittest.TestCase):
    def config(self, **values):
        base = {'database_url': 'postgresql://u:p@localhost:5432/vota_crawl', 'weaviate_url': 'http://localhost:8080',
                'vector_collection': 'ProductCrawl'}
        return SimpleNamespace(**(base | values))

    def test_local_only_accepts_private_sandbox_and_blocks_shared_targets(self):
        url = 'postgresql://u:p@127.0.0.1:5432/vota_crawl'
        with patch.dict(os.environ, {'CATALOG_LOCAL_ONLY': '1'}):
            fresh_catalog.check_local_only('local', url, self.config())
            for target, db_url, config in (
                    ('cloud', url, self.config()),
                    ('local', 'postgresql://u:p@10.0.0.5:5432/vota_crawl', self.config()),
                    ('local', 'postgresql://u:p@localhost:5432/vota', self.config()),
                    ('local', url, self.config(weaviate_url='abc.weaviate.cloud')),
                    ('local', url, self.config(vector_collection='Product'))):
                with self.subTest(target=target, db=db_url, config=config), self.assertRaises(ValueError):
                    fresh_catalog.check_local_only(target, db_url, config)
        with patch.dict(os.environ, {}, clear=True):  # VM: không bật chế độ local thì không chặn
            fresh_catalog.check_local_only('cloud', 'postgresql://u:p@10.0.0.5/vota', self.config(vector_collection='Product'))


if __name__ == '__main__':
    unittest.main()
