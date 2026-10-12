"""Đồ thị bước (pipeline_graph.py, P3 của docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md): tự nhất quán, và job chạy các
bước đúng thứ tự `deps` khai báo."""
import contextlib
import inspect
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import fresh_catalog
import fresh_settings
import pipeline_graph as graph
from collectors import live_control


class GraphDeclarationTests(unittest.TestCase):
    def test_every_dep_exists_and_there_is_no_cycle(self):
        known = set(graph.CRAWL_STEPS) | set(graph.BY_ID)
        for name in known:
            for dep in graph.deps_of(name):
                self.assertIn(dep, known, f'{name} phụ thuộc bước lạ {dep}')
        state: dict[str, int] = {}

        def visit(name, path=()):
            self.assertNotIn(name, path, f'vòng: {" → ".join((*path, name))}')
            if state.get(name) == 2:
                return
            for dep in graph.deps_of(name):
                visit(dep, (*path, name))
            state[name] = 2
        for name in known:
            visit(name)

    def test_steps_are_declared_after_their_deps(self):
        seen = {'maintain'} | set(graph.CRAWL_STEPS)
        for step in graph.STEPS[1:]:
            self.assertTrue(set(graph.deps_of(step.id)) <= seen, step.id)
            seen.add(step.id)

    def test_sources_are_complete_and_unique(self):
        keys = [src.key for src in graph.SOURCES]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(graph.CRAWL_STEPS), sum(len(src.steps) for src in graph.SOURCES))  # tên bước không trùng
        switches = {f.key for f in fresh_settings.FIELDS}
        for src in graph.SOURCES:
            self.assertTrue(src.steps and src.interim, src.key)
            self.assertEqual(len(src.step_labels), len(src.steps), src.key)
            self.assertIn(src.setting, switches, src.key)
            self.assertIn(src.site, graph.SITE_ORDER, src.key)
            self.assertIn(src.live, live_control.LIMITS, src.key)
            if src.in_process:
                self.assertEqual(len(src.step_titles), len(src.steps), src.key)
        interim = [stem for src in graph.SOURCES for stem in src.interim]
        self.assertEqual(len(interim), len(set(interim)), 'một file interim chỉ thuộc một nguồn')

    def test_columns_and_streams_point_to_known_nodes(self):
        columns = {col for col, _ in graph.COLUMNS}
        self.assertTrue({step.column for step in graph.STEPS} <= columns)
        self.assertTrue({s.node for s in graph.STREAMS if s.node} <= set(graph.BY_ID))
        self.assertEqual({s.id for s in graph.STREAMS}, set(live_control.STREAM))  # khoá chỉnh sống = tên bước

    def test_resume_plan_follows_deps(self):
        self.assertEqual(graph.RESUME_STEPS, ('crawl', 'normalise', 'merge', 'validate', 'db', 'index'))
        self.assertEqual(graph.resume_plan('crawl'), ('crawl', 'normalise', 'validate', 'db', 'index'))  # P4
        self.assertEqual(graph.resume_plan('merge'), ('normalise', 'validate', 'db', 'index'))
        self.assertEqual(graph.resume_plan('validate'), ('validate', 'db', 'index'))
        self.assertEqual(graph.resume_plan('index'), ('index',))
        with self.assertRaises(ValueError):
            graph.resume_plan('maintain')
        self.assertEqual({n: graph.resume_options(n) for n in ('normalise', graph.NORMALISE_ALL, 'validate', 'db', 'index',
                                                                'maintain', 'vinpearl')},
                         {'normalise': ('normalise', 'merge'), graph.NORMALISE_ALL: ('normalise',),
                          'validate': ('validate',), 'db': ('db',), 'index': ('index',), 'maintain': (),
                          'vinpearl': ('crawl',)})

    def test_derived_tables_keep_the_job_behaviour(self):
        # giá trị trước P3 (khai báo tay trong fresh_catalog.py); đổi ở đây là đổi hành vi của job. Booking đứng cuối từ
        # 08/10/2026 (làm mới cả catalog: Booking nhiều giờ nhất, không được ăn giờ của Agoda)
        self.assertEqual(graph.SITE_GROUPS, (('trip', ('trip-flights', 'trip-attractions')), ('vinpearl', ('vinpearl',)),
                                             ('agoda', ('agoda-hotels',)), ('booking', ('booking-hotels',))))
        self.assertEqual(graph.SITE_INTERIM, {'trip': ('trip_flights', 'trip_attractions', 'trip_hotels', 'trip_combos'),
                                              'vinpearl': ('vinpearl', 'vinpearl_bundles'),
                                              'booking': ('booking_hotels', 'booking_attractions', 'booking_flights'),
                                              'agoda': ('agoda_api', 'agoda_hotels')})
        self.assertEqual(graph.STEP_INTERIM['trip-hotels.prices'], ('trip_hotels',))
        self.assertNotIn('trip-hotels.discover', graph.STEP_INTERIM)
        self.assertEqual(graph.LIVE_KEYS, {'trip-flights': 'trip', 'trip-attractions': 'trip', 'vinpearl': 'vinpearl',
                                           'booking-hotels': 'booking', 'agoda-hotels': 'agoda'})


class JobOrderTests(unittest.TestCase):
    """Job gọi bước theo thứ tự trong code; test này bắt khi thứ tự đó lệch `deps` của đồ thị."""

    def run_job(self, mode, settings=None):
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
        if mode == 'daily':
            (root / 'state' / 'trip_targets.json').write_text(json.dumps({'hotels': [target]}), encoding='utf-8')
        env = {'CATALOG_STATE_DIR': f'{tmp.name}/state', 'CATALOG_RUN_ROOT': f'{tmp.name}/runs', 'CATALOG_DB_RUN_LOCK': 'off', 'DB_TARGET': 'local',
               'SEED_DATABASE_URL': 'postgresql://seed', 'CATALOG_DESTINATIONS': 'Nha Trang', 'CRAWL_PARALLEL': '4'}
        fake = lambda value=None: (lambda *args, **kwargs: value)
        with patch.dict(os.environ, env, clear=True), \
                patch.object(fresh_catalog, 'index_settings', fake('S')), \
                patch.object(fresh_catalog, 'check_local_only', fake()), \
                patch.object(fresh_catalog, 'maintain_catalog', fake({})), \
                patch.object(fresh_catalog, 'discover', AsyncMock(return_value=([target], []))), \
                patch.object(fresh_catalog, 'crawl', AsyncMock(return_value=([{'hotelId': '1'}], coverage))), \
                patch.object(fresh_catalog, 'run_source', fake(0)), \
                patch.object(fresh_catalog, 'normalize', fake(Path('products.jsonl'))), \
                patch.object(fresh_catalog, 'validate_run', fake({})), \
                patch.object(fresh_catalog, 'load_into_db', fake({})), \
                patch.object(fresh_catalog, 'index_catalog', fake({})), \
                patch.object(fresh_catalog, 'notify_finished', fake()), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(fresh_catalog.run_job(mode), 0)
        run = next((root / 'runs').iterdir())
        return json.loads((run / 'run.json').read_text(encoding='utf-8'))['steps']

    def assert_order(self, steps):
        by_name = {st['name']: st for st in steps}
        order = [st['name'] for st in steps]
        for st in steps:
            for dep in graph.deps_of(st['name']):
                if dep in by_name:  # bước tắt / không có trong chế độ này thì bỏ qua
                    self.assertLess(order.index(dep), order.index(st['name']), f'{dep} phải trước {st["name"]}')
                    self.assertLessEqual(by_name[dep]['finishedAt'], st['startedAt'], f'{dep} phải xong trước {st["name"]}')
        return order

    def test_full_run_respects_deps(self):
        order = self.assert_order(self.run_job('full'))
        self.assertEqual(set(order) - set(graph.CRAWL_STEPS), {'maintain', 'normalise', 'validate', 'db', 'index'})
        self.assertTrue(set(graph.CRAWL_STEPS) <= set(order))  # mọi bước cào của lượt full đã chạy

    def test_daily_run_respects_deps(self):
        order = self.assert_order(self.run_job('daily'))
        self.assertEqual(order, ['maintain', 'trip-hotels.prices', 'normalise', 'validate', 'db', 'index'])

    def test_resume_runs_exactly_the_planned_steps(self):
        for from_step in graph.RESUME_STEPS:
            source = 'booking' if from_step == graph.RECRAWL else None
            with self.subTest(from_step=from_step):
                calls = []
                rec = type('Rec', (), {'data': {'mode': 'full', 'id': 'x', 'startedAt': 's'},
                                       'stop_event': type('E', (), {'is_set': staticmethod(lambda: False)})(),
                                       'check_stop': staticmethod(lambda: None), 'save': staticmethod(lambda: None)})()
                with tempfile.TemporaryDirectory() as tmp, \
                        patch.object(fresh_catalog, 'normalise_step', lambda *a, **k: calls.append('normalise') or Path(tmp) / 'products.jsonl'), \
                        patch.object(fresh_catalog, 'validate_step', lambda *a, **k: calls.append('validate')), \
                        patch.object(fresh_catalog, 'db_step', lambda *a, **k: calls.append('db')), \
                        patch.object(fresh_catalog, 'run_index', lambda *a, **k: calls.append('index')), \
                        patch.object(fresh_catalog, 'recrawl_source', lambda *a, **k: calls.append('crawl') or {}), \
                        contextlib.redirect_stdout(io.StringIO()):
                    (Path(tmp) / 'products.jsonl').write_text('', encoding='utf-8')
                    fresh_catalog.resume_run(rec, {'scope.destinations': ''}, Path(tmp), Path(tmp), from_step, 'db', None,
                                             source=source)
                self.assertEqual(tuple(calls), graph.resume_plan(from_step))


class SubstepPlanTests(unittest.TestCase):
    """pipeline_graph.SUBSTEPS (monitor hiện sẵn cả bước con chưa chạy) khớp tên và thứ tự bước con trong code."""
    STAGE = re.compile(r"""stages\.(?:stage|add)\(\s*(['"])(.+?)\1""")
    CLOCK = re.compile(r"""clock\.begin\(\s*(['"])(.+?)\1""")

    def names(self, pattern, *functions):
        found = []
        for function in functions:
            for match in pattern.finditer(inspect.getsource(function)):
                if match.group(2) not in found:
                    found.append(match.group(2))
        return found

    def test_declared_substeps_match_the_code(self):
        import fresh_catalog_db
        import normalise
        in_code = {'maintain': self.names(self.STAGE, fresh_catalog_db.maintain_catalog),
                   'db': self.names(self.STAGE, fresh_catalog_db.load_into_db),
                   'validate': self.names(self.STAGE, fresh_catalog.validate_run, fresh_catalog.validate_step),
                   'index': self.names(self.STAGE, fresh_catalog.index_substeps),
                   'normalise': self.names(self.CLOCK, normalise._normalise, normalise.merge_catalog)}
        self.assertEqual(set(in_code), set(graph.SUBSTEPS))
        for step, names in in_code.items():
            plan = graph.SUBSTEPS[step]
            self.assertEqual(set(names), set(plan) | set(graph.SUBSTEP_EXTRAS.get(step, ())), step)
            self.assertEqual([name for name in names if name in plan], list(plan), f'{step}: thứ tự chạy')

    def test_merge_only_plan_starts_at_reading_checkpoints(self):
        self.assertEqual(graph.planned_substeps('normalise', merge_only=True)[0], graph.MERGE_ONLY_FROM)
        self.assertNotIn('ánh xạ nguồn', graph.planned_substeps('normalise', merge_only=True))
        self.assertEqual(graph.planned_substeps('db', merge_only=True), graph.SUBSTEPS['db'])
        self.assertEqual(graph.planned_substeps('vinpearl'), ())
