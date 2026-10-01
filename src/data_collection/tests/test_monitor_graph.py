"""Sơ đồ luồng của monitor (UI1, docs/plan/2026-09-28-monitor-so-do-luong.md): /api/graph và dải bước của /api/runs."""
import fcntl
import json
import tempfile
import unittest
from pathlib import Path

import fresh_run_log as run_log
import monitor

RUN_ID = 'full-20260928T010000Z-1'


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    run_log.write_json(path, data)


def step(name, status='ok', group=None, **detail):
    return {'name': name, 'group': group, 'label': name, 'status': status, 'seconds': 1.0,
            'startedAt': '2026-09-28T01:00:00+00:00', 'finishedAt': '2026-09-28T01:00:01+00:00', 'detail': detail}


FULL_STEPS = [
    step('maintain', windowRows=7),
    step('vinpearl', group='vinpearl'), step('trip-flights', group='trip'), step('trip-attractions', group='trip'),
    step('booking-hotels', group='booking'), step('agoda-hotels', group='agoda'),
    step('normalise.source:vinpearl', group='vinpearl', records=10, rows=8, errors=1),
    step('normalise.preview', group='preview'),
    step('normalise.source:vinpearl_bundles', group='vinpearl', records=2, rows=2, errors=0),
    step('normalise.preview', group='preview'), step('normalise.preview', group='preview'),
    step('normalise', recordsRead={'vinpearl': 60, 'vinpearl_bundles': 40}, rowsFinal=90),
    step('validate', products=90), step('db', dbRowsWritten=90), step('index', searchUnits=50, embedded=5),
]


class GraphTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.state, self.runs = root / 'state', root / 'runs'
        self.state.mkdir()
        self.runs.mkdir()
        self.monitor = monitor.FreshMonitor(self.state, self.runs)

    def write_run(self, steps, run_id=RUN_ID, mode='full', status='ok', settings=None, counts=None):
        path = self.runs / run_id
        path.mkdir(exist_ok=True)
        run_log.write_json(path / 'run.json', {
            'id': run_id, 'mode': mode, 'status': status, 'startedAt': '2026-09-28T01:00:00+00:00',
            'settings': {'sources.tripHotels': False} if settings is None else settings,
            'steps': steps, 'counts': counts or {}})
        return path

    def graph(self, run_id=RUN_ID):
        data = self.monitor.graph(run_id)
        return data, {n['id']: n for n in data['nodes']}

    def test_full_run_has_source_nodes_and_edges(self):
        path = self.write_run(FULL_STEPS)
        (path / 'interim').mkdir()
        (path / 'interim' / 'vinpearl.jsonl').write_text('{}\n{}\n', encoding='utf-8')
        (path / 'interim' / 'vinpearl_bundles.jsonl').write_text('{}\n', encoding='utf-8')
        data, nodes = self.graph()
        for stem in ('vinpearl', 'vinpearl_bundles'):
            self.assertIn(['vinpearl', f'normalise.source:{stem}'], data['edges'])
            self.assertIn([f'normalise.source:{stem}', 'normalise'], data['edges'])
        self.assertNotIn('normalise.preview', nodes)
        self.assertNotIn(monitor.NORMALISE_ALL, nodes)
        self.assertEqual(nodes['normalise']['drafts'], 3)
        self.assertEqual((nodes['vinpearl']['out'], nodes['maintain']['out']), (3, 7))
        source = nodes['normalise.source:vinpearl']
        self.assertEqual((source['lane'], source['in'], source['out'], source['errors']), ('vinpearl', 10, 8, 1))
        self.assertEqual((nodes['normalise']['in'], nodes['normalise']['out']), (100, 90))
        self.assertEqual((nodes['index']['in'], nodes['index']['out'], nodes['db']['out']), (50, 5, 90))
        self.assertEqual(nodes['trip-hotels.prices']['status'], 'disabled')
        self.assertEqual(set(data['strip'].values()), {'ok'})
        self.assertNotIn('other', [c['id'] for c in data['columns']])
        # mọi đường nối trỏ tới ô có thật
        self.assertTrue(all(a in nodes and b in nodes for a, b in data['edges']))

    def test_run_without_source_steps_gets_one_normalise_node(self):
        self.write_run([step('maintain'), step('vinpearl', group='vinpearl'), step('normalise')])
        data, nodes = self.graph()
        self.assertEqual(nodes[monitor.NORMALISE_ALL]['status'], 'ok')
        self.assertEqual([n['id'] for n in data['nodes'] if n['col'] == 'normalise'], [monitor.NORMALISE_ALL])
        tails = {'vinpearl', 'trip-flights', 'trip-attractions', 'booking-hotels', 'agoda-hotels', 'trip-hotels.prices'}
        self.assertEqual({a for a, b in data['edges'] if b == monitor.NORMALISE_ALL}, tails)

    def test_index_run_marks_other_columns_not_in_mode(self):
        self.write_run([step('maintain'), step('index')], run_id='index-20260928T010000Z-1', mode='index')
        data, nodes = self.graph('index-20260928T010000Z-1')
        self.assertEqual(nodes['booking-hotels']['status'], 'notInMode')
        self.assertEqual(data['strip'], {'prepare': 'ok', 'crawl': 'notInMode', 'normalise': 'notInMode',
                                         'merge': 'notInMode', 'validate': 'notInMode', 'db': 'notInMode',
                                         'index': 'ok'})

    def test_error_step_carries_kind_retries_and_worst_status(self):
        attempts = [{'attempt': 1, 'kind': 'transient'}, {'attempt': 2, 'kind': 'transient'}]
        self.write_run([step('maintain'), step('vinpearl', group='vinpearl'),
                        {**step('trip-flights', 'error', 'trip', errorKind='transient', attempts=attempts),
                         'error': 'TransientError: Nguồn trip-flights dừng với mã 1'},
                        step('booking-hotels', 'blocked', 'booking', errorKind='blocked')], status='failed')
        data, nodes = self.graph()
        failed = nodes['trip-flights']
        self.assertEqual((failed['status'], failed['errorKind'], failed['retries']), ('error', 'transient', 2))
        self.assertIn('mã 1', failed['error'])
        self.assertEqual(data['strip']['crawl'], 'error')
        self.assertEqual(nodes['validate']['status'], 'notRun')

    def test_blocked_source_is_worst_when_others_ok(self):
        self.write_run([step('maintain'), step('vinpearl', group='vinpearl'),
                        step('booking-hotels', 'blocked', 'booking', errorKind='blocked')])
        self.assertEqual(self.graph()[0]['strip']['crawl'], 'blocked')

    def test_running_run_waits_and_lost_run_is_dead(self):
        self.write_run([step('maintain'), step('vinpearl', 'running', 'vinpearl')], status='running')
        data, nodes = self.graph()  # không có khoá: tiến trình đã mất
        self.assertEqual((data['status'], nodes['vinpearl']['status'], nodes['db']['status']), ('dead', 'dead', 'notRun'))
        handle = (self.state / 'fresh_catalog.lock').open('a')
        self.addCleanup(handle.close)
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        (self.state / monitor.RUNNING_FILE).write_text(json.dumps({'runId': RUN_ID}), encoding='utf-8')
        data, nodes = self.graph()
        self.assertEqual((data['status'], nodes['vinpearl']['status'], nodes['db']['status']),
                         ('running', 'running', 'waiting'))
        self.assertEqual(data['strip']['crawl'], 'running')

    def test_unknown_step_is_shown_in_other_column(self):
        self.write_run([step('maintain'), step('resume.check', 'error')])
        data, nodes = self.graph()
        self.assertEqual((nodes['resume.check']['col'], nodes['resume.check']['status']), ('other', 'error'))
        self.assertEqual(data['columns'][-1], {'id': 'other', 'label': 'Bước khác'})
        self.assertNotIn('other', data['strip'])

    def test_checkpoint_without_step_still_becomes_a_node(self):
        path = self.write_run([step('maintain'), step('normalise', 'error')], status='failed')
        (path / 'normalised').mkdir()
        run_log.write_json(path / 'normalised' / 'booking_hotels.meta.json',
                           {'source': 'booking_hotels', 'status': 'failed', 'records': 5, 'rows': 0, 'errors': 5,
                            'error': 'RecordErrorRateExceeded'})
        _, nodes = self.graph()
        node = nodes['normalise.source:booking_hotels']
        self.assertEqual((node['status'], node['lane'], node['errors']), ('error', 'booking', 5))

    def test_streaming_checkpoint_runs_while_run_is_live(self):
        """L1 pipeline liên tục: checkpoint `streaming` (đang chuẩn hoá dần) là "Đang chạy"; lượt đã dừng thì "Đã dừng"."""
        path = self.write_run([step('maintain'), step('booking-hotels', 'running', 'booking')], status='running')
        (path / 'normalised').mkdir()
        run_log.write_json(path / 'normalised' / 'booking_hotels.meta.json',
                           {'source': 'booking_hotels', 'status': 'streaming', 'records': 4, 'rows': 12, 'errors': 0,
                            'batches': 3})
        handle = (self.state / 'fresh_catalog.lock').open('a')
        self.addCleanup(handle.close)
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        (self.state / monitor.RUNNING_FILE).write_text(json.dumps({'runId': RUN_ID}), encoding='utf-8')
        node = self.graph()[1]['normalise.source:booking_hotels']
        self.assertEqual((node['status'], node['in'], node['out']), ('running', 4, 12))
        handle.close()
        self.write_run([step('maintain'), step('booking-hotels', 'stopped', 'booking')], status='stopped')
        self.assertEqual(self.graph()[1]['normalise.source:booking_hotels']['status'], 'stopped')

    def lock_running(self):
        handle = (self.state / 'fresh_catalog.lock').open('a')
        self.addCleanup(handle.close)
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        (self.state / monitor.RUNNING_FILE).write_text(json.dumps({'runId': RUN_ID}), encoding='utf-8')
        return handle

    def test_merge_shows_drafts_and_running_substep_before_official(self):
        """UI2b: gộp nháp đã chạy 2 lần, bản chính thức chưa có → ô Gộp "Đang gộp nháp", hiện bước con của nháp đang chạy."""
        path = self.write_run([step('maintain'), step('booking-hotels', group='booking'),
                               step('normalise.preview', group='preview', rows=59, groups={'trip': 'ok', 'booking': 'ok'},
                                    sources=['booking_hotels']),
                               step('normalise.preview', 'running', 'preview')], status='running')
        put(path / 'preview.next' / 'normalise_stages' / 'steps.json',
                           {'steps': [{'name': 'đọc checkpoint', 'status': 'ok'},
                                      {'name': 'gộp trùng khách sạn', 'status': 'running'}]})
        self.lock_running()
        merge = self.graph()[1]['normalise']
        self.assertEqual((merge['status'], merge['draft']['n'], merge['draft']['groups']), ('draft', 2, []))
        self.assertEqual(merge['substep'], 'gộp trùng khách sạn')
        self.assertEqual(self.monitor.graph(RUN_ID)['strip']['merge'], 'draft')

    def test_merge_substeps_official_and_draft_with_descriptions(self):
        path = self.write_run([step('normalise.preview', group='preview', rows=45, groups={'trip': 'ok'},
                                    sources=['trip_flights']), step('normalise')])
        steps = [{'name': 'đọc checkpoint', 'status': 'ok', 'seconds': 0.01, 'rowsIn': None, 'rowsOut': 45},
                 {'name': 'gộp trùng khách sạn', 'status': 'ok', 'seconds': 0.02, 'rowsIn': 12, 'rowsOut': 10}]
        put(path / 'normalise_stages' / 'steps.json', {'steps': steps + [{'name': 'ghi output', 'status': 'ok'}]})
        put(path / 'preview' / 'normalise_stages' / 'steps.json', {'steps': steps})
        official = self.monitor.substeps(RUN_ID, 'normalise')
        self.assertEqual((official['variant'], official['variants'], len(official['steps'])), ('official', ['official', 'draft'], 3))
        self.assertIn('sameAs', official['steps'][1]['description'])
        draft = self.monitor.substeps(RUN_ID, 'normalise', 'draft')
        self.assertEqual((draft['variant'], len(draft['steps'])), ('draft', 2))
        self.assertEqual((draft['drafts'][0]['n'], draft['drafts'][0]['rows'], draft['drafts'][0]['sources']),
                         (1, 45, ['trip_flights']))

    def test_source_substeps_process_and_stream(self):
        path = self.write_run([step('normalise.source:booking_hotels', group='booking')])
        put(path / 'normalised' / 'steps' / 'booking_hotels' / 'steps.json',
                           {'steps': [{'name': 'đọc interim', 'status': 'ok', 'rowsOut': 6},
                                      {'name': 'ánh xạ nguồn', 'status': 'ok', 'rowsIn': 6, 'rowsOut': 29}]})
        put(path / 'normalised' / 'booking_hotels.meta.json', {'status': 'ok'})
        process = self.monitor.substeps(RUN_ID, 'normalise.source:booking_hotels')
        self.assertEqual((process['variant'], [s['name'] for s in process['steps']]), ('process', ['đọc interim', 'ánh xạ nguồn']))
        self.assertTrue(all(s['description'] for s in process['steps']))
        put(path / 'normalised' / 'booking_hotels.meta.json',
                           {'status': 'streaming', 'batches': 2,
                            'steps': [{'name': 'đọc phần mới', 'status': 'ok'}, {'name': 'ghi checkpoint', 'status': 'ok'}],
                            'history': [{'n': 1, 'newRecords': 4}, {'n': 2, 'newRecords': 2}]})
        stream = self.monitor.substeps(RUN_ID, 'normalise.source:booking_hotels')
        self.assertEqual((stream['variant'], len(stream['batches'])), ('stream', 2))
        with self.assertRaises(ValueError):
            self.monitor.substeps(RUN_ID, 'db')
        with self.assertRaises(ValueError):
            self.monitor.substeps(RUN_ID, 'normalise.source:../x')

    def test_stream_steps_attach_to_their_nodes_not_other_column(self):
        """L6: bước chạy liên tục (stream.*) gắn vào ô Gộp / Nạp DB / Index, không thành "Bước khác"."""
        path = self.write_run([step('maintain'), step('booking-hotels', 'running', 'booking'),
                               step('stream.normalise', 'running', 'stream', batches=4),
                               step('stream.merge', 'running', 'stream', batches=2),
                               step('stream.db', 'running', 'stream', batches=3, dbRowsWritten=120),
                               step('stream.index', 'running', 'stream', batches=1, dbRowsWritten=120)], status='running')
        self.lock_running()
        data, nodes = self.graph()
        self.assertNotIn('other', [c['id'] for c in data['columns']])
        self.assertEqual((nodes['db']['status'], nodes['db']['stream']['batches'], nodes['db']['stream']['dbRowsWritten']),
                         ('running', 3, 120))
        self.assertEqual((nodes['index']['status'], nodes['normalise']['status']), ('running', 'draft'))
        self.assertEqual(data['strip']['db'], 'running')
        (path / 'db_batches.jsonl').write_text(''.join(json.dumps({'n': n, 'rows': n}) + '\n' for n in (1, 2, 3)),
                                               encoding='utf-8')
        feed = self.monitor.feed(RUN_ID, 'db')
        self.assertEqual((feed['total'], [r['n'] for r in feed['rows']]), (3, [3, 2, 1]))
        with self.assertRaises(ValueError):
            self.monitor.feed(RUN_ID, 'x')

    def test_validate_runs_row_checks_while_db_streams(self):
        """Nạp DB theo phần đang chạy → ô Kiểm tra "Đang chạy" (kiểm từng dòng theo lô), không "Chờ tới lượt"."""
        self.write_run([step('maintain'), step('vinpearl', 'running', 'vinpearl'),
                        step('stream.db', 'running', 'stream', batches=2)], status='running')
        self.lock_running()
        node = self.graph()[1]['validate']
        self.assertEqual(node['status'], 'running')
        self.assertIn('kiểm từng dòng', node['note'])

    def test_final_db_step_wins_over_stream_step(self):
        self.write_run([step('stream.db', 'ok', 'stream', batches=5), step('db', dbRowsWritten=7)])
        node = self.graph()[1]['db']
        self.assertEqual((node['status'], node['out'], node['stream']['batches']), ('ok', 7, 5))

    def test_live_lists_stream_controls_of_the_running_run(self):
        self.write_run([step('maintain')], status='running',
                       settings={'stream.enabled': True, 'stream.db': True, 'stream.index': False,
                                 'stream.dbSeconds': 60, 'stream.mergeSeconds': 30, 'stream.normaliseSeconds': 15,
                                 'stream.indexSeconds': 300})
        self.lock_running()
        code, live = self.monitor.set_live('stream.db', {'interval': 20, 'paused': True})
        self.assertEqual(code, 200)
        rows = {r['key']: r for r in live['stream']}
        self.assertEqual((rows['stream.db']['value'], rows['stream.db']['base'], rows['stream.db']['paused']), (20, 60, True))
        self.assertEqual((rows['stream.index']['enabled'], rows['stream.merge']['enabled']), (False, True))
        _, live = self.monitor.set_live('stream.db', {'kick': True})
        self.assertTrue([r for r in live['stream'] if r['key'] == 'stream.db'][0]['kickAt'])

    def test_finished_run_offers_resume_from_steps_after_crawl(self):
        """CP6: lượt đã kết thúc → ô Gộp chạy lại từ normalise hoặc chỉ gộp; Kiểm tra / Nạp DB / Index từ chính nó."""
        self.write_run([step('maintain'), {**step('db', 'error'), 'error': 'InfraError'}], status='failed')
        data, nodes = self.graph()
        self.assertEqual(nodes['normalise']['resume'], ['normalise', 'merge'])
        self.assertEqual((nodes['db']['resume'], nodes['index']['resume']), (['db'], ['index']))
        self.assertNotIn('resume', nodes['booking-hotels'])
        self.write_run([step('maintain'), step('index')], run_id='index-20260928T010000Z-1', mode='index')
        nodes = self.graph('index-20260928T010000Z-1')[1]
        self.assertEqual((nodes['index']['resume'], 'resume' in nodes['db']), (['index'], False))

    def test_running_run_has_no_resume_and_api_refuses(self):
        self.write_run([step('maintain')], status='running')
        self.lock_running()
        self.assertNotIn('resume', self.graph()[1]['db'])
        code, out = self.monitor.resume(RUN_ID, 'db')
        self.assertEqual(code, 409)
        with self.assertRaises(ValueError):
            self.monitor.resume(RUN_ID, 'crawl')

    def test_resume_spawns_the_job_with_the_run_and_step(self):
        from unittest.mock import patch
        self.write_run([step('db', 'error')], status='failed')
        with patch.object(monitor.subprocess, 'Popen') as popen:
            popen.return_value.pid = 4321
            popen.return_value.wait.return_value = 0
            code, out = self.monitor.resume(RUN_ID, 'db')
        self.assertEqual((code, out['from'], out['pid']), (202, 'db', 4321))
        cmd = popen.call_args[0][0]
        self.assertEqual(cmd[-6:], ['resume', RUN_ID, '--from', 'db', '--trigger', 'monitor'])
        self.assertEqual(popen.call_args[1]['env']['CATALOG_RUN_ROOT'], str(self.runs))

    def test_focus_and_problem_for_failed_running_and_finished_runs(self):
        """UI3: lượt lỗi → ô lỗi đầu tiên + dải báo; đang chạy → ô đang chạy xa nhất; xong → ô cuối đã chạy."""
        self.write_run([step('maintain'), step('vinpearl', group='vinpearl'),
                        step('booking-hotels', 'blocked', 'booking', errorKind='blocked'),
                        {**step('trip-flights', 'error', 'trip', errorKind='transient'), 'error': 'TransientError: mã 1'}],
                       status='failed')
        data = self.graph()[0]
        self.assertEqual(data['focus'], 'trip-flights')  # lỗi xếp trước bị chặn
        self.assertEqual((data['problem']['label'], data['problem']['errorKind']), ('Trip vé máy bay', 'transient'))
        self.write_run([step('maintain'), step('vinpearl', 'ok', 'vinpearl'), step('normalise'), step('validate'),
                        step('db'), step('index')])
        data = self.graph()[0]
        self.assertEqual((data['focus'], data['problem']), ('index', None))
        self.write_run([step('maintain'), step('booking-hotels', 'running', 'booking'),
                        step('stream.db', 'running', 'stream', batches=1)], status='running')
        self.lock_running()
        self.assertEqual(self.graph()[0]['focus'], 'db')  # ô đang chạy xa nhất
        self.write_run([step('maintain')], run_id='daily-20260928T010000Z-1', mode='daily', status='failed')
        path = self.runs / 'daily-20260928T010000Z-1' / 'run.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        path.write_text(json.dumps(dict(data, error='RuntimeError: Không có ID Trip')), encoding='utf-8')
        problem = self.graph('daily-20260928T010000Z-1')[0]['problem']
        self.assertEqual((problem['id'], problem['label']), (None, 'Cả lượt'))

    def test_runs_have_strip_detail_per_column(self):
        self.write_run([step('maintain'), step('vinpearl', group='vinpearl'),
                        step('booking-hotels', 'blocked', 'booking')])
        row = self.monitor.runs()[0]
        crawl = dict(row['stripDetail']['crawl'])
        self.assertEqual((crawl['Vinpearl'], crawl['booking.com']), ('ok', 'blocked'))
        self.assertNotIn('Trip KS: tìm ID', crawl)  # nguồn tắt không hiện

    def test_stem_lanes(self):
        self.assertEqual(monitor.stem_lanes('agoda_hotels'), ['agoda'])
        self.assertEqual(monitor.stem_lanes('trip_combos'), ['tripFlights', 'tripAttractions', 'tripHotels'])
        self.assertEqual(monitor.stem_lanes('unknown_source'), [])

    def test_runs_have_strip_and_product_delta_per_mode(self):
        catalog = lambda n: {'catalog': {'products': n}}  # noqa: E731
        self.write_run(FULL_STEPS, run_id='full-20260926T010000Z-1', counts=catalog(100))
        self.write_run([step('maintain')], run_id='daily-20260927T010000Z-1', mode='daily', counts=catalog(40))
        self.write_run(FULL_STEPS, run_id='full-20260928T010000Z-1', counts=catalog(120))
        for run_id, started in (('full-20260926T010000Z-1', '2026-09-26'), ('daily-20260927T010000Z-1', '2026-09-27')):
            data = json.loads((self.runs / run_id / 'run.json').read_text(encoding='utf-8'))
            run_log.write_json(self.runs / run_id / 'run.json', dict(data, startedAt=f'{started}T01:00:00+00:00'))
        rows = {r['id']: r for r in self.monitor.runs()}
        newest, daily, oldest = rows['full-20260928T010000Z-1'], rows['daily-20260927T010000Z-1'], rows['full-20260926T010000Z-1']
        self.assertEqual((newest['products'], newest['productsDelta']), (120, 20))
        self.assertIsNone(daily['productsDelta'])
        self.assertIsNone(oldest['productsDelta'])
        self.assertEqual(newest['strip']['db'], 'ok')
        self.assertEqual(daily['strip']['db'], 'notRun')

    def test_lanes_carry_source_dirs_for_panel_filter(self):
        self.write_run([step('maintain')])
        lanes = {lane['id']: lane for lane in self.graph()[0]['lanes']}
        self.assertEqual(lanes['vinpearl']['dirs'], ['vinpearl', 'vinpearl_bundles'])

    def test_record_errors_by_source_before_merge_step(self):
        """Panel "Bản ghi lỗi" của ô chuẩn hoá theo nguồn: chưa có errors.jsonl gộp thì đọc checkpoint từng nguồn."""
        path = self.write_run([step('maintain'), step('normalise.source:booking_hotels', group='booking', errors=2)],
                              status='running')
        (path / 'normalised').mkdir()
        for stem, n in (('booking_hotels', 2), ('agoda_hotels', 1)):
            (path / 'normalised' / f'{stem}.errors.jsonl').write_text(
                ''.join(json.dumps({'source': stem, 'function': 'map', 'input': {'i': i}, 'error': 'KeyError'}) + '\n'
                        for i in range(n)), encoding='utf-8')
        rows = self.monitor.normalise_rows(RUN_ID, 'errors', source='booking_hotels')
        self.assertEqual((rows['total'], {r['source'] for r in rows['rows']}), (2, {'booking_hotels'}))
        self.assertEqual(rows['facets']['source'], {'booking_hotels': 2, 'agoda_hotels': 1})
        # đã có bản gộp thì chỉ dùng bản gộp
        (path / 'normalise_stages').mkdir()
        (path / 'normalise_stages' / 'errors.jsonl').write_text(
            json.dumps({'source': 'agoda_hotels', 'function': 'map', 'input': {}, 'error': 'KeyError'}) + '\n',
            encoding='utf-8')
        self.assertEqual(self.monitor.normalise_rows(RUN_ID, 'errors')['total'], 1)

    def test_graph_rejects_bad_run_id(self):
        with self.assertRaises(ValueError):
            self.monitor.graph('../etc')


if __name__ == '__main__':
    unittest.main()
