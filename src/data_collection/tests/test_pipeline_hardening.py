"""Failure injection at the isolation, transaction and process boundaries."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import fresh_catalog as job
import normalise as n
from pipeline_runtime import supervise
from tests.test_normalise_steps import SAMPLE, ARGS


def test_bad_source_is_excluded_and_healthy_sources_survive(tmp_path):
    shutil.copytree(SAMPLE, tmp_path / 'interim')
    with patch.object(n, 'trip_combo_product', side_effect=TypeError('changed source shape')):
        assert n.main(['--data-dir', str(tmp_path), *ARGS, '--allow-partial-sources',
                       '--report-json', str(tmp_path / 'report.json')]) == 0
    report = json.loads((tmp_path / 'report.json').read_text())
    assert 'trip_combos' in report['excludedSources']
    rows = [json.loads(x) for x in (tmp_path / 'products.jsonl').read_text().splitlines()]
    assert any(p['taxonomy'] == 'hotel' for p in rows)
    assert not any(p['sourceRef'].startswith('trip:combo:') for p in rows)
    # Existing failed checkpoints cannot silently re-enter a merge-only retry.
    with pytest.raises(ValueError, match='Checkpoint nguồn lỗi'):
        n.main(['--data-dir', str(tmp_path), *ARGS, '--merge-only'])


def test_per_source_drop_gate_keeps_other_sources(tmp_path):
    shutil.copytree(SAMPLE, tmp_path / 'interim')
    assert n.main(['--data-dir', str(tmp_path), *ARGS, '--allow-partial-sources',
                   '--source-minimums', '{"trip_flights": 100}', '--report-json', str(tmp_path / 'report.json')]) == 0
    report = json.loads((tmp_path / 'report.json').read_text())
    assert 'trip_flights' in report['excludedSources']
    assert 'booking_hotels' not in report['excludedSources']


def test_resume_does_not_hide_another_sources_timeout(tmp_path):
    rec = type('R', (), {'data': {'steps': [{'name': 'vinpearl', 'status': 'timeout'},
                                         {'name': 'agoda-hotels', 'status': 'ok'}]}})()
    assert job.incomplete_sources(rec, tmp_path) == {'vinpearl': 'timeout'}
    rec.data['steps'].append({'name': 'vinpearl', 'status': 'ok'})
    assert job.incomplete_sources(rec, tmp_path) == {}


def test_dependency_failure_only_skips_its_own_downstream(tmp_path):
    called = []
    def discover():
        raise ValueError('malformed hotel list')
    discover.step = 'trip-hotels.discover'
    def prices():
        called.append('prices')
    prices.step = 'trip-hotels.prices'
    with patch.object(job, 'run_source', lambda *a, **kw: called.append(a[1]) or 0):
        status = job.crawl_sites(tmp_path, '@deep', [('trip', (discover, 'trip-flights', prices)),
                                                   ('booking', ('booking-hotels',))], 1)
    assert called == ['trip-flights', 'booking-hotels']
    assert status['trip-hotels.discover'] != 0
    assert status['trip-hotels.prices'] != 0


def test_supervisor_reaps_hung_worker_and_child_releases_lock(tmp_path):
    state, runs = tmp_path / 'state', tmp_path / 'runs'
    state.mkdir(); runs.mkdir()
    code = '''
import fcntl,json,os,subprocess,sys,time
from pathlib import Path
state,runs=map(Path,sys.argv[1:])
lock=(state/'fresh_catalog.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX)
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])
(state/'child').write_text(str(child.pid))
run=runs/'full-test';run.mkdir()
(run/'run.json').write_text(json.dumps({'id':'full-test','status':'running','steps':[{'name':'db','status':'running'}]}))
(state/'running.json').write_text(json.dumps({'pid':os.getpid(),'runId':'full-test'}))
time.sleep(120)
'''
    started = time.monotonic()
    assert supervise([sys.executable, '-c', code, str(state), str(runs)], state, runs,
                     max_seconds=1, step_seconds={}, poll=.02) == 3
    assert time.monotonic() - started < 5
    data = json.loads((runs / 'full-test' / 'run.json').read_text())
    assert data['status'] == 'failed' and data['steps'][0]['status'] == 'timeout'
    assert not job.lock_busy(state)
    from fresh_run_log import _alive
    assert not _alive(int((state / 'child').read_text()))
    assert not (state / 'running.json').exists()


def test_empty_source_remains_partial_even_if_fetch_step_returned_ok(tmp_path):
    rec = type('R', (), {'data': {'steps': [{'name': 'trip-hotels.prices', 'status': 'ok'}],
                                 'sourceStatuses': {'trip-hotels.prices': 1}}})()
    assert job.incomplete_sources(rec, tmp_path) == {'trip-hotels.prices': 1}
    rec.data['sourceStatuses']['trip-hotels.prices'] = 0
    assert job.incomplete_sources(rec, tmp_path) == {}


def test_supervisor_finalizes_before_releasing_worker_lock(tmp_path):
    import fcntl
    from pipeline_runtime import kill_worker
    lock_path = tmp_path / 'worker.lock'
    code = "import fcntl,sys,time; f=open(sys.argv[1],'w'); fcntl.flock(f,fcntl.LOCK_EX); print('ready',flush=True); time.sleep(60)"
    proc = subprocess.Popen([sys.executable, '-c', code, str(lock_path)], stdout=subprocess.PIPE,
                            text=True, start_new_session=True)
    assert proc.stdout.readline().strip() == 'ready'
    callbacks = []
    def before_release():
        with lock_path.open('a') as lock:
            with pytest.raises(BlockingIOError):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        callbacks.append(True)
    try:
        kill_worker(proc, grace=.01, before_release=before_release)
        assert callbacks == [True]
        with lock_path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()


def test_resume_excludes_failed_trip_coverage_but_loads_other_sources(tmp_path):
    import threading
    from types import SimpleNamespace
    state = tmp_path / 'state'; state.mkdir()
    (tmp_path / 'products.jsonl').write_text('{}\n')
    (tmp_path / 'trip_price_coverage.json').write_text('{"requestedHotels":0}')
    rec = SimpleNamespace(data={'id': 'full-test', 'mode': 'full', 'startedAt': '2026-09-29T00:00:00Z',
                                'sourceStatuses': {'trip-hotels.prices': 1}},
                          stop_event=threading.Event(), check_stop=lambda: None)
    with patch.object(job, 'validate_step') as validate, patch.object(job, 'db_step') as db, patch.object(job, 'run_index'):
        result = job.resume_run(rec, {}, state, tmp_path, 'validate', 'test-db', None)
    assert result == job.EXIT_PARTIAL
    assert validate.call_args.args[-1] is None
    assert db.call_args.args[-2] is None
