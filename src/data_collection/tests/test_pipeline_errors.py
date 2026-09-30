"""CP3: phân loại lỗi và chiến thuật cho từng loại (pipeline_errors.py + fresh_catalog)."""
import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import psycopg

import fresh_catalog
import fresh_run_log as run_log
import fresh_settings
import pipeline_errors as perr


def settings(**overrides) -> dict:
    values = {f.key: f.default for f in fresh_settings.FIELDS}
    values.update({'retry.transientDelay': 0.01, 'retry.infraDelay': 0.01})
    values.update(overrides)
    return values


class ClassifyTests(unittest.TestCase):
    def test_exit_codes_and_log_tails(self):
        cases = [
            (0, [], 'ok'),
            (75, [], perr.BLOCKED),
            (1, ['Traceback (most recent call last):', '  File "common.py", line 253, in __init__',
                 'sqlite3.OperationalError: database is locked'], perr.TRANSIENT),
            (1, ['httpx.ReadTimeout: timed out'], perr.TRANSIENT),
            (1, ["TypeError: BrowserSession.fetch_json() takes 3 positional arguments but 4 were given"], perr.CODE),
            (1, ['09:00:01 ERROR   [booking_hotels] Bị chặn 8 lần liên tiếp – dừng. Chạy lại sau vài giờ.'], perr.BLOCKED),
            (1, ['09:00:01 WARNING https://x trả 503 – chờ 5s rồi thử lại'], perr.TRANSIENT),
            (1, ['RuntimeError: something odd'], perr.CODE),
            (2, ['usage: crawl.py'], perr.UNKNOWN),
        ]
        for code, tail, kind in cases:
            with self.subTest(code=code, tail=tail):
                self.assertEqual(perr.classify_exit(code, tail), kind)

    def test_exceptions(self):
        request = httpx.Request('GET', 'https://api.cohere.test')
        cases = [
            (perr.BlockedError('x'), perr.BLOCKED),
            (sqlite3.OperationalError('database is locked'), perr.TRANSIENT),
            (psycopg.OperationalError('connection refused'), perr.INFRA),
            (httpx.ConnectError('down', request=request), perr.INFRA),
            (httpx.HTTPStatusError('429', request=request, response=httpx.Response(429, request=request)), perr.INFRA),
            (httpx.HTTPStatusError('400', request=request, response=httpx.Response(400, request=request)), perr.CODE),
            (ConnectionResetError(), perr.INFRA),
            (KeyError('x'), perr.CODE),
            (RuntimeError('odd'), perr.UNKNOWN),
        ]
        for exc, kind in cases:
            with self.subTest(exc=exc):
                self.assertEqual(perr.classify_exception(exc), kind)

    def test_strategy_follows_settings(self):
        values = settings(**{'retry.transientAttempts': 4, 'retry.infraAttempts': 1})
        self.assertEqual(perr.strategy(perr.TRANSIENT, values)['retries'], 4)
        self.assertEqual(perr.strategy(perr.INFRA, values)['retries'], 1)
        self.assertEqual(perr.strategy(perr.BLOCKED, values)['action'], 'skip')
        for kind in (perr.CODE, perr.QUALITY, perr.UNKNOWN):
            self.assertEqual(perr.strategy(kind, values)['action'], 'fail')


class RunnerStrategyTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(fresh_catalog, 'CFG', settings())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = []

    def fake_sources(self, script):
        """script: nguồn → danh sách (mã thoát, các dòng log) cho từng lần chạy."""
        def run(run_dir, source, destinations, group, deadline=None):
            code, tail = script[source][len([c for c in self.calls if c == source])]
            self.calls.append(source)
            fresh_catalog.SOURCE_TAIL[source] = list(tail)
            return code
        return run

    def crawl(self, groups, script):
        with patch.object(fresh_catalog, 'run_source', self.fake_sources(script)), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            try:
                return fresh_catalog.crawl_sites(Path('/tmp/unused'), '@deep', groups, 4), out.getvalue()
            except perr.PipelineError as exc:
                return exc, out.getvalue()

    def test_transient_failure_is_retried_then_succeeds(self):
        locked = (1, ['sqlite3.OperationalError: database is locked'])
        result, log = self.crawl([('trip', ('trip-flights',))], {'trip-flights': [locked, (0, [])]})
        self.assertEqual((result, self.calls), ({'trip-flights': 0}, ['trip-flights', 'trip-flights']))
        self.assertIn('catalog.retry step=trip-flights attempt=1/2 kind=transient', log)

    def test_transient_failure_gives_up_after_the_configured_attempts(self):
        locked = (1, ['sqlite3.OperationalError: database is locked'])
        result, _ = self.crawl([('trip', ('trip-flights',))], {'trip-flights': [locked] * 3})
        self.assertEqual(result, {'trip-flights': 1})
        self.assertEqual(len(self.calls), 3)

    def test_code_error_fails_fast_and_blocked_source_does_not_stop_others(self):
        bug = (1, ['TypeError: fetch_json() takes 3 positional arguments but 4 were given'])
        result, _ = self.crawl([('vinpearl', ('vinpearl',))], {'vinpearl': [bug]})
        self.assertEqual(result, {'vinpearl': 1})
        self.assertEqual(self.calls, ['vinpearl'])
        self.calls.clear()
        blocked = (1, ['Bị chặn 8 lần liên tiếp – dừng'])
        result, _ = self.crawl([('booking', ('booking-hotels',)), ('agoda', ('agoda-hotels',))],
                               {'booking-hotels': [blocked], 'agoda-hotels': [(0, [])]})
        self.assertEqual(result, {'booking-hotels': 75, 'agoda-hotels': 0})
        self.assertEqual(sorted(self.calls), ['agoda-hotels', 'booking-hotels'])

    def test_blocked_discovery_skips_prices_but_keeps_flights_and_attractions(self):
        priced = []

        def discover():
            raise perr.BlockedError('Trip trả 0 khách sạn')

        def prices():
            priced.append(True)
        discover.step = 'trip-hotels.discover'
        prices.step = 'trip-hotels.prices'
        groups = [('trip', (discover, 'trip-flights', 'trip-attractions', prices))]
        result, log = self.crawl(groups, {'trip-flights': [(0, [])], 'trip-attractions': [(0, [])]})
        self.assertEqual(result, {'trip-hotels.discover': 75, 'trip-hotels.prices': 75, 'trip-flights': 0, 'trip-attractions': 0})
        self.assertEqual(priced, [])
        self.assertIn('catalog.group.done name=trip status=blocked', log)

    def test_infra_errors_are_retried_with_detail(self):
        detail, attempts = {}, []

        def load():
            attempts.append(1)
            if len(attempts) < 3:
                raise psycopg.OperationalError('server closed the connection')
            return {'dbRowsWritten': 3}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fresh_catalog.with_retry('db', load, detail), {'dbRowsWritten': 3})
        self.assertEqual([a['kind'] for a in detail['attempts']], ['infra', 'infra'])
        with self.assertRaises(KeyError) as ctx:
            fresh_catalog.with_retry('db', lambda: {}['x'], detail)
        self.assertEqual((ctx.exception.pipeline_kind, detail['errorKind']), ('code', 'code'))


class QualityGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runs = Path(self.tmp.name)

    def previous(self, name, products, status='ok', **overrides):
        path = self.runs / name
        path.mkdir()
        values = settings(**overrides)
        run_log.write_json(path / 'run.json', {'id': name, 'status': status, 'settings': values,
                                               'counts': {'catalog': {'products': products}}})

    def test_large_drop_against_comparable_previous_run_blocks_loading(self):
        self.previous('full-20260927T010000Z-1', 1000)
        current = self.runs / 'full-20260928T010000Z-2'
        current.mkdir()
        with self.assertRaises(perr.QualityGateError) as ctx:
            fresh_catalog.quality_drop_check(400, 'full', settings(), current)
        self.assertIn('giảm 60% > 50%', str(ctx.exception))
        self.assertEqual(fresh_catalog.quality_drop_check(700, 'full', settings(), current)['dropPercent'], 30)
        self.assertEqual(fresh_catalog.quality_drop_check(10, 'full', settings(**{'quality.maxDropPercent': 0}), current), {})

    def test_different_scope_or_failed_previous_run_is_not_compared(self):
        self.previous('full-20260926T010000Z-1', 1000, status='failed')
        self.previous('full-20260927T010000Z-1', 1000, **{'scope.destinations': 'Nha Trang'})
        current = self.runs / 'full-20260928T010000Z-2'
        current.mkdir()
        self.assertEqual(fresh_catalog.quality_drop_check(10, 'full', settings(), current), {})

    def test_step_records_blocked_status_and_error_kind(self):
        state = self.runs / 'state'
        state.mkdir()
        recorder = run_log.RunRecorder(self.runs / 'full-20260928T010000Z-3', state, run_id='full-20260928T010000Z-3',
                                       mode='full', trigger='test', settings={}).start()
        try:
            with self.assertRaises(perr.BlockedError), recorder.step('trip-hotels.discover'):
                raise perr.BlockedError('0 nơi lưu trú')
        finally:
            recorder.finish('partial', 3)
        entry = json.loads((recorder.run_dir / 'run.json').read_text(encoding='utf-8'))['steps'][0]
        self.assertEqual((entry['status'], entry['errorKind']), ('blocked', 'blocked'))


if __name__ == '__main__':
    unittest.main()
