"""Sơ đồ monitor: % hoàn thành của từng ô (tô màu) và bước con của ô lớn (bấm để bung) — UI6, 08/10/2026."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fresh_catalog
import monitor
import pipeline_graph as graph
from fresh_run_log import write_json
from stage_log import Stages

RUN_ID = 'full-20261008T040337Z-1'


class StagesTests(unittest.TestCase):
    def test_stage_records_counts_status_and_errors(self):
        sink, saves = [], []
        stages = Stages(sink, lambda: saves.append(len(sink)))
        with stages.stage('đọc', inp=3) as stage:
            stage.update(out=2, ok=2, total=3)
        with self.assertRaises(ValueError), stages.stage('hỏng'):
            raise ValueError('xấu')
        stages.add('suy ra', changed=4)
        self.assertEqual([(e['name'], e['status']) for e in sink], [('đọc', 'ok'), ('hỏng', 'error'), ('suy ra', 'ok')])
        self.assertEqual((sink[0]['in'], sink[0]['out'], sink[0]['ok'], sink[0]['total']), (3, 2, 2, 3))
        self.assertIn('ValueError: xấu', sink[1]['error'])
        self.assertIsNotNone(sink[0]['seconds'])
        self.assertTrue(saves)  # mỗi lần đổi đều gọi lưu run.json (monitor thấy bước con đang chạy)

    def test_each_substep_logs_when_it_starts_and_when_it_ends(self):
        lines = []
        stages = Stages([], step='db', emit=lines.append)
        with stages.stage('ghép với DB', inp=10) as stage:
            self.assertEqual(lines, ['catalog.substep name=db:ghép với DB status=running in=10'])  # tab Log thấy ngay
            stage.update(out=11, ok=9, total=10, note='mới 1')
        stages.add('cửa sổ 30 ngày', changed=4)
        self.assertEqual(lines[1].split(' seconds=')[0], 'catalog.substep name=db:ghép với DB status=ok in=10 out=11 ok=9/10')
        self.assertTrue(lines[1].endswith('— mới 1'))
        self.assertEqual(lines[2], 'catalog.substep name=db:cửa sổ 30 ngày status=ok changed=4')  # bước suy ra: một dòng
        from stage_log import substep_line
        self.assertEqual(substep_line('normalise', {'name': 'lọc', 'status': 'ok', 'rowsIn': 96, 'rowsOut': 95, 'seconds': 0.1}),
                         'catalog.substep name=normalise:lọc status=ok in=96 out=95 seconds=0.1')

    def test_without_sink_it_just_runs(self):
        with Stages().stage('x') as stage:
            stage['out'] = 1


class ValidateRulesTests(unittest.TestCase):
    def products(self, root, rows):
        path = Path(root) / 'products.jsonl'
        path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return path

    def row(self, ref, taxonomy='attraction', level=None):
        from normalise import PRODUCT_FIELDS, product_id
        values = {'productId': product_id(ref), 'name': 'x', 'taxonomy': taxonomy, 'destination': 'Huế',
                  'description': 'x', 'attributes': {'level': level} if level else {}, 'unitPrice': 1, 'currency': 'VND',
                  'available': True, 'availableFrom': None, 'availableTo': None, 'imageUrl': 'https://x/a.jpg',
                  'sourceRef': ref}
        return {k: values[k] for k in PRODUCT_FIELDS}

    def test_each_rule_is_a_substep_and_a_failing_rule_is_marked(self):
        with tempfile.TemporaryDirectory() as root:
            products = self.products(root, [self.row('a:1'), self.row('a:2')])
            sink = []
            fresh_catalog.validate_run(products, None, full=True, required={('attraction', None)}, trip=False,
                                       stages=Stages(sink))
            self.assertEqual([(s['name'], s['status']) for s in sink],
                             [('khách sạn Trip đủ mốc ngày giá', 'skipped'), ('13 trường đúng thứ tự', 'ok'),
                              ('id, sourceRef, thông tin hiển thị', 'ok'), ('đủ nhóm sản phẩm', 'ok')])
            self.assertEqual((sink[1]['ok'], sink[1]['total'], sink[3]['ok'], sink[3]['total']), (2, 2, 1, 1))
            sink = []
            with self.assertRaisesRegex(ValueError, 'Thiếu nhóm'):
                fresh_catalog.validate_run(products, None, full=True, required={('attraction', None), ('combo', None)},
                                           trip=False, stages=Stages(sink))
            self.assertEqual((sink[-1]['status'], sink[-1]['ok'], sink[-1]['total'], sink[-1]['note']),
                             ('error', 1, 2, 'thiếu combo/-'))

    def test_index_substeps_from_report(self):
        sink = []
        fresh_catalog.index_substeps(Stages(sink), {'searchUnits': 530, 'unchanged': 500, 'embedded': 28,
                                                    'deletedOrphans': 3, 'missingLexical': 2, 'backfilledLexical': 1})
        embed = next(s for s in sink if s['name'].startswith('embed'))
        self.assertEqual((embed['in'], embed['out'], embed['ok'], embed['total']), (30, 28, 28, 30))
        lexical = sink[-1]
        self.assertEqual((lexical['status'], lexical['ok'], lexical['total']), ('partial', 528, 530))
        sink = []
        fresh_catalog.index_substeps(Stages(sink), {'searchUnits': 5, 'unchanged': 5, 'embedded': 0})
        embed = next(s for s in sink if s['name'].startswith('embed'))
        self.assertNotIn('total', embed)  # không có gì để embed: không hiện "0/0 đạt"
        sink = []
        fresh_catalog.index_substeps(Stages(sink), {'deferred': True, 'reason': 'quota'})
        self.assertEqual(sink[0]['status'], 'partial')


class ProgressRulesTests(unittest.TestCase):
    def node(self, status):
        return {'status': status}

    def test_percent_rules(self):
        cases = [(dict(done=117, total=125), 'ok', 93.6, 'result'), (dict(), 'ok', 100.0, 'result'),
                 (dict(), 'error', 0.0, 'result'), (dict(done=30, total=120, running=True), 'running', 25.0, 'progress'),
                 (dict(running=True), 'running', None, 'progress'), (dict(done=1, total=0), 'ok', 100.0, 'result')]
        for kwargs, status, pct, kind in cases:
            node = self.node(status)
            monitor.node_progress(node, **kwargs)
            self.assertEqual((node['progress']['percent'], node['progress']['kind']), (pct, kind), (kwargs, status))

    def test_substep_view_maps_both_formats(self):
        normalise_step = monitor.substep_view({'name': 'lọc', 'status': 'ok', 'rowsIn': 96, 'rowsOut': 95, 'peakRssMb': 198})
        self.assertEqual((normalise_step['in'], normalise_step['out'], normalise_step['ramMb'], normalise_step['percent']),
                         (96, 95, 198, 100.0))  # lọc bớt dòng là bình thường: tô đủ
        self.assertTrue(normalise_step['description'])
        rule = monitor.substep_view({'name': 'ghép với DB', 'status': 'ok', 'ok': 9, 'total': 10})
        self.assertEqual(rule['percent'], 90.0)
        self.assertIsNone(monitor.substep_view({'name': 'x', 'status': 'running'})['percent'])


LOG = '''02:00:01 catalog.step.start name=booking-hotels group=booking
03:22:08 [booking] 03:22:08 INFO    [booking_hotels] 4/24 xong · 0 lỗi · 0 bỏ qua · 7.68 trang/phút · còn ~2m
03:29:46 [booking] 03:29:46 INFO    [booking_hotels] 120/135 xong · 1 lỗi · 7 bỏ qua · 7.56 trang/phút · còn ~0m
03:29:52 [booking] 03:29:52 INFO    [booking_hotels] Trạng thái: {'done': 120, 'gone': 7}
03:41:12 [agoda] 03:41:12 INFO    Agoda: 160 khách sạn có hotel_id, 160 lượt hỏi giá cần làm (ngân sách không giới hạn request)
03:44:01 [agoda] 03:44:01 INFO    Agoda giá: 50/160 (0.30 req/s, ok 48, lỗi 1)
03:49:52 [agoda] 03:49:52 INFO    Agoda API: {'sitemapFiles': 41, 'hotelsInSitemap': 61461, 'idResolved': 7, 'priceOk': 150, 'priceNone': 6, 'failed': 4, 'scope': 160, 'tasks': 160, 'requests': 200}
02:30:00 [vinpearl] 02:30:00 INFO    Vinpearl 15/16: Vinpearl Resort Nha Trang – 10 hạng phòng
'''


class GraphProgressTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'state').mkdir()
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.monitor = monitor.FreshMonitor(self.root / 'state', self.root / 'runs')
        self.run = self.root / 'runs' / RUN_ID
        self.run.mkdir(parents=True)
        (self.run / monitor.LOG_FILE).write_text(LOG, encoding='utf-8')

    def write(self, steps, status='ok', counts=None):
        write_json(self.run / 'run.json', {'id': RUN_ID, 'mode': 'full', 'status': status, 'steps': steps,
                                          'counts': counts or {}, 'settings': {}})

    def nodes(self):
        return {n['id']: n for n in self.monitor.graph(RUN_ID)['nodes']}

    def test_crawl_nodes_use_final_state_and_refresh_coverage(self):
        self.write([{'name': 'booking-hotels', 'status': 'ok', 'detail': {}},
                    {'name': 'agoda-hotels', 'status': 'ok', 'detail': {}},
                    {'name': 'trip-hotels.prices', 'status': 'ok', 'detail': {'requested': 21, 'completed': 20}}],
                   counts={'refresh': {'booking-hotels': {'requested': 105, 'refreshed': 98, 'percent': 93.3}}})
        nodes = self.nodes()
        booking = nodes['booking-hotels']['progress']
        self.assertEqual((booking['done'], booking['total'], booking['percent']), (120, 127, 94.5))  # không đếm lượt thử lại
        agoda = nodes['agoda-hotels']['progress']
        self.assertEqual((agoda['done'], agoda['total']), (156, 160))  # hết phòng (priceNone) không phải lỗi
        self.assertEqual(nodes['trip-hotels.prices']['progress']['percent'], 95.2)
        self.assertEqual(nodes['booking-hotels']['refresh'], {'requested': 105, 'refreshed': 98, 'percent': 93.3})

    def test_agoda_plan_line_gives_total_before_first_progress_line(self):
        scan = monitor.LogScan(self.run / 'x.log')
        scan._line('03:41:12 [agoda] 03:41:12 INFO    Agoda: 24 khách sạn có hotel_id, 24 lượt hỏi giá cần làm (ngân sách x)')
        self.assertEqual((scan.stats['agoda']['progress']['processed'], scan.stats['agoda']['progress']['total']), (0, 24))

    def test_running_crawl_and_big_steps_show_work_done(self):
        self.write([{'name': 'vinpearl', 'status': 'running', 'detail': {}},
                    {'name': 'validate', 'status': 'running',
                     'detail': {'substeps': [{'name': name, 'status': status} for name, status in
                                             zip(graph.SUBSTEPS['validate'], ('ok', 'ok', 'running'))]}}],
                   status='running')
        with patch.object(self.monitor, '_is_running', lambda run_id: True):
            nodes = self.nodes()
        vinpearl = nodes['vinpearl']
        self.assertEqual((vinpearl['progress']['done'], vinpearl['progress']['total'], vinpearl['progress']['kind']),
                         (15, 16, 'progress'))
        self.assertEqual(vinpearl['substep'], 'khách sạn')
        validate = nodes['validate']['progress']
        self.assertEqual((validate['done'], validate['total'], validate['kind']), (2, 6, 'progress'))
        chain = nodes['validate']['substeps']
        self.assertEqual([s['status'] for s in chain], ['ok', 'ok', 'running', 'waiting', 'waiting', 'waiting'])
        self.assertEqual([bool(s.get('planned')) for s in chain], [False] * 3 + [True] * 3)

    def test_finished_big_steps_use_their_main_rule(self):
        rules = [{'name': 'khách sạn Trip đủ mốc ngày giá', 'status': 'skipped'},
                 {'name': '13 trường đúng thứ tự', 'status': 'ok', 'ok': 10, 'total': 10},
                 {'name': 'độ phủ làm mới khách sạn đang có', 'status': 'partial', 'ok': 80, 'total': 100}]
        self.write([{'name': 'validate', 'status': 'ok', 'detail': {'substeps': rules}},
                    {'name': 'db', 'status': 'ok', 'detail': {'substeps': [
                        {'name': 'ghép với DB', 'status': 'ok', 'ok': 99, 'total': 100}]}},
                    {'name': 'normalise', 'status': 'ok', 'detail': {}}])
        (self.run / 'normalise_stages').mkdir()
        write_json(self.run / 'normalise_stages' / 'steps.json',
                   {'steps': [{'name': 'lọc', 'status': 'ok', 'rowsIn': 96, 'rowsOut': 95}]})
        nodes = self.nodes()
        self.assertEqual((nodes['validate']['progress']['done'], nodes['validate']['progress']['total']), (1, 2))
        self.assertEqual(nodes['db']['progress']['percent'], 99.0)
        merge = {s['name']: s for s in nodes['normalise']['substeps']}
        self.assertEqual(merge['lọc']['in'], 96)
        self.assertEqual(merge['ghi output']['status'], 'notRun')  # bước đã xong: bước con không có số liệu là Không chạy
        self.assertEqual(nodes['normalise']['progress']['percent'], 100.0)
        self.assertEqual(len(nodes['validate']['substeps']), len(graph.SUBSTEPS['validate']))

    def test_steps_not_run_yet_still_show_their_substeps(self):
        self.write([{'name': 'maintain', 'status': 'ok', 'detail': {'substeps': [
            {'name': 'đọc catalog', 'status': 'ok', 'out': 5}, {'name': 'hết hạn giá Trip', 'status': 'ok'}]}}],
            status='running')
        with patch.object(self.monitor, '_is_running', lambda run_id: True):
            nodes = self.nodes()
        for step in ('normalise', 'validate', 'db', 'index'):
            chain = nodes[step]['substeps']
            self.assertEqual(nodes[step]['status'], 'waiting')
            self.assertEqual([s['name'] for s in chain], list(graph.SUBSTEPS[step]), step)
            self.assertTrue(all(s['planned'] and s['status'] == 'waiting' and s['percent'] is None for s in chain), step)
            self.assertIsNone(nodes[step]['progress']['percent'], step)  # chưa chạy: không tô
        maintain = {s['name']: s for s in nodes['maintain']['substeps']}
        self.assertEqual(list(maintain), list(graph.SUBSTEPS['maintain']))
        self.assertEqual((maintain['đọc catalog']['out'], maintain['đọc catalog'].get('planned')), (5, None))
        self.assertEqual(maintain['danh sách làm mới']['status'], 'notRun')  # lượt này không chạy bước con này
        self.assertEqual(nodes['maintain']['progress']['percent'], 100.0)  # % chỉ tính bước con có số liệu

    def test_draft_merge_shows_the_merge_only_chain(self):
        self.write([{'name': 'normalise.preview', 'status': 'running', 'detail': {}}], status='running')
        (self.run / 'preview.next' / 'normalise_stages').mkdir(parents=True)
        write_json(self.run / 'preview.next' / 'normalise_stages' / 'steps.json',
                   {'steps': [{'name': 'đọc checkpoint', 'status': 'ok'},
                              {'name': 'sửa điểm đến, toạ độ', 'status': 'running'}]})
        with patch.object(self.monitor, '_is_running', lambda run_id: True):
            merge = self.nodes()['normalise']
        self.assertEqual(merge['status'], 'draft')
        self.assertEqual([s['name'] for s in merge['substeps']], list(graph.planned_substeps('normalise', merge_only=True)))
        self.assertEqual([s['status'] for s in merge['substeps']][:3], ['ok', 'running', 'waiting'])

    def test_finished_run_marks_missing_substeps_not_run_and_keeps_extras(self):
        self.write([{'name': 'index', 'status': 'partial', 'detail': {'substeps': [
            {'name': 'embed + ghi Weaviate', 'status': 'partial', 'note': 'hoãn: quota'}]}}], status='partial')
        nodes = self.nodes()
        chain = nodes['index']['substeps']
        self.assertEqual([s['status'] for s in chain[:-1]], ['notRun'] * len(graph.SUBSTEPS['index']))
        self.assertEqual((chain[-1]['name'], chain[-1]['status']), ('embed + ghi Weaviate', 'partial'))
        self.assertEqual(nodes['validate']['status'], 'notRun')  # lượt kết thúc trước khi tới bước Kiểm tra
        self.assertEqual({s['status'] for s in nodes['validate']['substeps']}, {'notRun'})

    def test_finished_step_without_recorded_substeps_says_no_data_not_not_run(self):
        # lượt trước 08/10: Kiểm tra chạy xong nhưng job chưa ghi bước con → "Chưa ghi số liệu", không phải "Không chạy"
        self.write([{'name': 'validate', 'status': 'ok', 'detail': {'products': 3578}}], status='ok')
        chain = self.nodes()['validate']['substeps']
        self.assertEqual([s['name'] for s in chain], list(graph.SUBSTEPS['validate']))
        self.assertEqual({(s['status'], s['planned']) for s in chain}, {('noData', True)})

    def test_merge_tab_lists_the_planned_substeps_before_the_first_merge(self):
        self.write([], status='running')
        steps = self.monitor.substeps(RUN_ID, 'normalise')['steps']
        self.assertEqual([s['name'] for s in steps], list(graph.SUBSTEPS['normalise']))
        self.assertTrue(all(s['planned'] and s['status'] == 'waiting' for s in steps))
        self.assertTrue(steps[0]['description'])
        self.write([], status='ok')
        self.assertEqual({s['status'] for s in self.monitor.substeps(RUN_ID, 'normalise')['steps']}, {'notRun'})


if __name__ == '__main__':
    unittest.main()
