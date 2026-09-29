"""Cảnh báo (CP7) và SLA (CP8) của docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import alerts
import fresh_settings

VN = timezone(timedelta(hours=7))


def values(**overrides):
    return {f.key: f.default for f in fresh_settings.FIELDS} | overrides


class Workspace(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.state, self.runs = root / 'state', root / 'runs'
        self.state.mkdir()
        self.runs.mkdir()

    def make_run(self, run_id, status='ok', steps=(), started=None, **extra):
        path = self.runs / run_id
        path.mkdir(exist_ok=True)
        data = {'id': run_id, 'mode': run_id.split('-')[0], 'status': status, 'steps': list(steps),
                'startedAt': started or datetime.now(timezone.utc).isoformat(timespec='seconds'), **extra}
        (path / 'run.json').write_text(json.dumps(data), encoding='utf-8')
        return path, data


class RunAlertTests(Workspace):
    def test_failed_quality_blocked_record_and_batch_alerts(self):
        path, data = self.make_run('full-20260928T010000Z-1', 'failed', errorKind='infra',
                              error='InfraError: postgresql://seed:hunter22@db/vota refused',
                              steps=[{'name': 'booking-hotels', 'status': 'blocked', 'group': 'booking', 'error': 'captcha'},
                                     {'name': 'db', 'status': 'error', 'error': 'InfraError'}])
        (path / 'normalised').mkdir()
        (path / 'normalised' / 'agoda_hotels.meta.json').write_text(json.dumps({'status': 'ok', 'records': 50, 'errors': 2}))
        (path / 'db_batches.jsonl').write_text(json.dumps({'n': 1, 'error': 'OperationalError: timeout'}) + '\n')
        items = alerts.run_alerts(data, path)
        self.assertEqual([(a['level'], a['kind'], a['step']) for a in items],
                         [('error', 'infra', 'db'), ('warning', 'blocked', 'booking-hotels'),
                          ('warning', 'record', 'normalise'), ('warning', 'infra', 'stream.db')])
        self.assertNotIn('hunter22', items[0]['message'])  # không lộ mật khẩu DSN
        quality = alerts.run_alerts({'id': 'x', 'status': 'failed', 'errorKind': 'quality', 'error': 'Không nạp DB'}, path)
        self.assertEqual(quality[0]['kind'], 'quality')
        self.assertEqual(alerts.run_alerts(dict(data, status='failed'), path, include_warnings=False)[1:], [])

    def test_successful_or_stopped_run_has_no_error_alert(self):
        for status in ('ok', 'stopped'):
            path, data = self.make_run(f'daily-2026092{status == "ok"}T010000Z-1', status)
            self.assertEqual(alerts.run_alerts(data, path), [])

    def test_env_secret_values_are_redacted(self):
        with patch.dict(os.environ, {'COHERE_API_KEY': 'sk-secret-123456'}):
            self.assertEqual(alerts.redact('Cohere 401 key=sk-secret-123456'), 'Cohere 401 key=***')

    def test_same_alert_is_written_but_not_shown_again_within_cooldown(self):
        path, data = self.make_run('full-20260928T010000Z-1', 'failed', errorKind='code', error='KeyError',
                              steps=[{'name': 'normalise', 'status': 'error'}])
        first = alerts.on_run_finished(data, path, self.state, values())
        second = alerts.on_run_finished(data, path, self.state, values())
        self.assertEqual((len(first), len(second)), (1, 0))
        feed = alerts.read_alerts(self.state / alerts.ALERTS)
        self.assertEqual([a['suppressed'] for a in feed], [False, True])
        self.assertEqual(len(alerts.read_alerts(path / alerts.ALERTS)), 2)
        self.assertEqual(alerts.on_run_finished(data, path, self.state, values(**{'alert.enabled': False})), [])

    def test_slow_step_against_median_of_kept_runs(self):
        for n, seconds in enumerate((10, 12, 11), 1):
            self.make_run(f'full-2026092{n}T010000Z-1', steps=[{'name': 'normalise', 'status': 'ok', 'seconds': seconds}])
        _, data = self.make_run('full-20260928T010000Z-9', steps=[{'name': 'normalise', 'status': 'ok', 'seconds': 50},
                                                              {'name': 'db', 'status': 'ok', 'seconds': 500}])
        items = alerts.slow_step_alerts(data, self.runs, values())
        self.assertEqual([(a['kind'], a['step']) for a in items], [('sla', 'normalise')])  # db: chưa đủ 3 lượt để so
        self.assertEqual(alerts.slow_step_alerts(data, self.runs, values(**{'sla.slowFactor': 0})), [])


class SlaTests(Workspace):
    NOW = datetime(2026, 9, 28, 20, 0, tzinfo=VN)

    def status(self, **overrides):
        return {r['rule']: r['state'] for r in alerts.sla_status(self.state, self.runs, values(**overrides), self.NOW)['rules']}

    def test_finish_by(self):
        self.assertEqual(self.status()['finishBy'], 'late')  # có lịch (daily bật), 20:00 > 19:00, chưa có lượt xong
        self.assertEqual(self.status(**{'sla.finishBy': '21:00'})['finishBy'], 'pending')
        self.assertEqual(self.status(**{'schedule.enabled': False})['finishBy'], 'none')
        self.make_run('daily-20260928T010000Z-1', 'ok', started='2026-09-28T01:00:00+00:00')
        self.assertEqual(self.status()['finishBy'], 'ok')

    def test_catalog_age(self):
        self.assertEqual(self.status()['catalogAge'], 'none')
        old = (self.NOW - timedelta(hours=50)).isoformat()
        self.make_run('full-20260926T010000Z-1', 'ok', started=old, steps=[{'name': 'db', 'status': 'ok', 'finishedAt': old}])
        self.assertEqual(self.status()['catalogAge'], 'late')
        self.assertEqual(self.status(**{'sla.maxCatalogAgeHours': 72})['catalogAge'], 'ok')

    def test_check_sla_alerts_once_per_rule_per_day(self):
        first = alerts.check_sla(self.state, self.runs, values(), self.NOW)
        self.assertEqual([(a['kind'], a['step']) for a in first], [('sla', 'finishBy')])
        self.assertEqual(alerts.check_sla(self.state, self.runs, values(), self.NOW + timedelta(minutes=15)), [])
        with patch.object(alerts, 'now_utc', return_value=(self.NOW + timedelta(days=1)).astimezone(timezone.utc)):
            again = alerts.check_sla(self.state, self.runs, values(), self.NOW + timedelta(days=1))
        self.assertEqual(len(again), 1)  # ngày mới: báo lại
        self.assertEqual(alerts.check_sla(self.state, self.runs, values(**{'sla.enabled': False}), self.NOW), [])


if __name__ == '__main__':
    unittest.main()
