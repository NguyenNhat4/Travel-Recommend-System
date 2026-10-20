"""Normalize ổn định theo từng bước (docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md).

Mẫu `tests/fixtures/normalise_sample/interim/` là vài chục bản ghi interim thật của 7 nguồn (đã bỏ review/tên người),
chọn sao cho có khách sạn Vinpearl/booking/agoda gộp trùng ở Nha Trang, vé Vinpearl trùng điểm tham quan trip.com,
tuyến bay, combo và biến thể giá thành viên.
"""
import contextlib
import datetime as dt
import gzip
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fresh_catalog
import monitor
import normalise

SAMPLE = Path(__file__).resolve().parent / 'fixtures' / 'normalise_sample' / 'interim'
# products.jsonl do normalise.py ở HEAD (trước CP1–CP5) sinh ngày 2026-09-28 trên mẫu này: khoá output khi tách bước
EXPECTED = SAMPLE.parent / 'expected_products.jsonl'
TODAY = '2026-09-28'
ARGS = ['--rooms-per-hotel', '0', '--flights-per-route', '0', '--keep-unsellable', '--keep-missing-coordinates',
        '--keep-location-warnings', '--keep-price-outliers', '--destinations', '@deep', '--today', TODAY]
RUN_ID = 'full-20260928T010000Z-1'


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding='utf-8').splitlines()


class SampleRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def data_dir(self, name='run') -> Path:
        path = self.root / name
        shutil.copytree(SAMPLE, path / 'interim')
        return path

    def run_normalise(self, path: Path, *extra) -> int:
        return normalise.main(['--data-dir', str(path), '--stage-dir', str(path / 'normalise_stages'), *ARGS, *extra])

    def steps(self, path: Path) -> list[dict]:
        return json.loads((path / 'normalise_stages' / 'steps.json').read_text(encoding='utf-8'))['steps']


# ---------------------------------------------------------------------------------------------------- CP1


class StepClockTests(SampleRun):
    def test_every_step_has_time_rows_and_ram(self):
        path = self.data_dir()
        self.assertEqual(self.run_normalise(path), 0)
        steps = self.steps(path)
        self.assertEqual([s['name'] for s in steps], [
            'đọc interim', 'ánh xạ nguồn', 'đọc checkpoint', 'sửa điểm đến, toạ độ', 'gộp trùng khách sạn', 'vé và điểm tham quan',
            'vé máy bay, combo', 'lọc', 'làm giàu', 'kiểm vị trí, giá', 'ghi output'])
        self.assertTrue(all(s['status'] == 'ok' and s['seconds'] >= 0 and s['peakRssMb'] > 0 for s in steps))
        self.assertEqual(steps[-1]['rowsOut'], len(read_lines(path / 'products.jsonl')))
        self.assertEqual(steps[0]['rowsOut'], steps[1]['rowsIn'])
        self.assertGreater(len(read_lines(path / 'dedup_report.csv')), 1)  # mẫu có gộp trùng giữa các nguồn

    def test_failure_names_the_step_and_keeps_traceback(self):
        path = self.data_dir()
        with patch.object(normalise, 'cluster_hotels', side_effect=KeyError('latitude')), \
                self.assertRaises(KeyError), self.assertLogs('normalise', 'ERROR') as logs:
            self.run_normalise(path)
        last = self.steps(path)[-1]
        self.assertEqual((last['name'], last['status']), ('gộp trùng khách sạn', 'error'))
        self.assertIn("KeyError", last['error'])
        self.assertIn('cluster_hotels', last['traceback'])  # dòng code gọi bước hỏng nằm trong traceback
        self.assertTrue(any('normalise.step.failed name=gộp trùng khách sạn' in line for line in logs.output))

    def test_job_error_message_and_monitor_show_the_failed_step(self):
        runs = self.root / 'runs'
        path = runs / RUN_ID
        shutil.copytree(SAMPLE, path / 'interim')
        with patch.object(normalise, 'merge_pois', side_effect=TypeError('bad ticket')), \
                self.assertRaises(RuntimeError) as ctx, self.assertLogs('normalise', 'ERROR'):
            fresh_catalog.normalize(path, '@deep')
        self.assertIn("bước 'vé và điểm tham quan'", str(ctx.exception))
        (path / 'run.json').write_text(json.dumps({'id': RUN_ID, 'status': 'failed', 'steps': []}), encoding='utf-8')
        view = monitor.FreshMonitor(self.root / 'state', runs).normalise(RUN_ID)
        self.assertTrue(view['incomplete'])
        self.assertEqual(view['steps'][-1]['status'], 'error')

    def test_today_option_pins_date_dependent_output(self):
        a, b = self.data_dir('a'), self.data_dir('b')
        self.assertEqual(self.run_normalise(a), 0)
        with patch.object(normalise, 'date') as fake_date:  # ngày máy khác: --today vẫn cho cùng kết quả
            fake_date.today.return_value = dt.date(2030, 1, 1)
            fake_date.fromisoformat = dt.date.fromisoformat
            self.assertEqual(self.run_normalise(b), 0)
        self.assertEqual(read_lines(a / 'products.jsonl'), read_lines(b / 'products.jsonl'))



# ---------------------------------------------------------------------------------------------------- CP2


def failing_for(original, bad_keys):
    """Hàm ánh xạ giả: ném lỗi với bản ghi có `key` trong `bad_keys`, còn lại gọi hàm thật."""
    def mapper(record, *args):
        if record.get('key') in bad_keys:
            raise ValueError(f"giá phòng hỏng ở {record.get('key')}")
        return original(record, *args)
    return mapper


def sample_keys(stem: str) -> list[str]:
    return [json.loads(line)['key'] for line in read_lines(SAMPLE / f'{stem}.jsonl')]


class RecordGuardTests(SampleRun):
    def errors(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in read_lines(path / 'normalise_stages' / 'errors.jsonl')]

    def test_one_bad_record_is_skipped_and_logged_others_still_mapped(self):
        clean, bad = self.data_dir('clean'), self.data_dir('bad')
        self.assertEqual(self.run_normalise(clean), 0)
        self.assertEqual(self.errors(clean), [])
        broken = sample_keys('booking_hotels')[:1]
        with patch.object(normalise, 'booking_hotel', failing_for(normalise.booking_hotel, broken)), \
                self.assertLogs('normalise', 'WARNING') as logs:
            self.assertEqual(self.run_normalise(bad), 0)
        errors = self.errors(bad)
        self.assertEqual([(e['source'], e['input']['key'], e['function']) for e in errors],
                         [('booking_hotels', broken[0], 'mapper')])
        self.assertIn('ValueError: giá phòng hỏng', errors[0]['error'])
        self.assertTrue(any('normalise.record.failed source=booking_hotels' in line for line in logs.output))
        report = json.loads((bad / 'normalise_stages' / 'steps.json').read_text(encoding='utf-8'))
        self.assertEqual(report['steps'][-1]['status'], 'ok')
        clean_refs = {json.loads(line)['sourceRef'] for line in read_lines(clean / 'products.jsonl')}
        bad_refs = {json.loads(line)['sourceRef'] for line in read_lines(bad / 'products.jsonl')}
        self.assertTrue(bad_refs < clean_refs or bad_refs == clean_refs)  # chỉ có thể mất phần của bản ghi hỏng
        self.assertGreater(len(bad_refs & {r for r in clean_refs if r.startswith('booking:')}), 0)

    def test_widespread_errors_stop_normalise_with_the_source_named(self):
        path = self.data_dir()
        with patch.object(normalise, 'booking_hotel', failing_for(normalise.booking_hotel, sample_keys('booking_hotels')[:3])), \
                self.assertRaises(normalise.RecordErrorRateExceeded) as ctx, self.assertLogs('normalise', 'WARNING'):
            self.run_normalise(path)
        self.assertIn('booking_hotels: 3/5', str(ctx.exception))  # 8 dòng, 5 bản ghi sau latest_by_key
        self.assertEqual(len(self.errors(path)), 3)
        self.assertEqual(self.steps(path)[-1]['status'], 'error')

    def test_few_errors_below_minimum_do_not_stop_but_a_fully_broken_source_does(self):
        path = self.data_dir('few')
        with patch.object(normalise, 'agoda_hotel', failing_for(normalise.agoda_hotel, sample_keys('agoda_hotels')[:2])), \
                self.assertLogs('normalise', 'WARNING'):
            self.assertEqual(self.run_normalise(path), 0)  # 2/6 = 33% nhưng chưa tới 3 bản ghi lỗi
        path = self.data_dir('all')
        with patch.object(normalise, 'trip_combo_product', side_effect=AttributeError('price')), \
                self.assertRaises(normalise.RecordErrorRateExceeded), self.assertLogs('normalise', 'WARNING'):
            self.run_normalise(path)  # 2/2 bản ghi combo lỗi: toàn bộ nguồn hỏng

    def test_monitor_lists_record_errors(self):
        runs = self.root / 'runs'
        path = runs / RUN_ID
        shutil.copytree(SAMPLE, path / 'interim')
        with patch.object(normalise, 'booking_hotel', failing_for(normalise.booking_hotel, sample_keys('booking_hotels')[:1])), \
                self.assertLogs('normalise', 'WARNING'):
            self.assertEqual(self.run_normalise(path), 0)
        (path / 'run.json').write_text(json.dumps({'id': RUN_ID, 'status': 'ok', 'steps': []}), encoding='utf-8')
        mon = monitor.FreshMonitor(self.root / 'state', runs)
        self.assertEqual(mon.normalise(RUN_ID)['recordErrors'], {'booking_hotels': 1})
        rows = mon.normalise_rows(RUN_ID, 'errors')
        self.assertEqual((rows['total'], rows['rows'][0]['source']), (1, 'booking_hotels'))
        self.assertIn('Traceback', mon.normalise_row(RUN_ID, 'errors', 0)['entry']['traceback'])


# ---------------------------------------------------------------------------------------------------- CP4


class CheckpointTests(SampleRun):
    def test_default_run_matches_output_before_the_split(self):
        path = self.data_dir()
        self.assertEqual(self.run_normalise(path), 0)
        self.assertEqual(read_lines(path / 'products.jsonl'), read_lines(EXPECTED))
        metas = {p.name[:-len('.meta.json')]: json.loads(p.read_text(encoding='utf-8'))
                 for p in (path / 'normalised').glob('*.meta.json')}
        self.assertEqual(sorted(metas), sorted(f.stem for f in SAMPLE.glob('*.jsonl')))
        self.assertEqual(metas['booking_hotels']['records'], 5)  # 8 dòng, 5 bản ghi sau latest_by_key

    def test_each_source_alone_then_merge_only_gives_the_same_catalog(self):
        path = self.data_dir()
        for stem in sorted(f.stem for f in SAMPLE.glob('*.jsonl')):
            self.assertEqual(normalise.main(['--data-dir', str(path), *ARGS, '--only-source', stem,
                                             '--stage-dir', str(path / 'stages' / stem)]), 0)
            self.assertTrue((path / 'normalised' / f'{stem}.jsonl').is_file())
        self.assertFalse((path / 'products.jsonl').exists())  # --only-source không gộp
        self.assertEqual(self.run_normalise(path, '--merge-only'), 0)
        self.assertEqual(read_lines(path / 'products.jsonl'), read_lines(EXPECTED))

    def test_merge_only_rebuilds_from_checkpoints_without_interim(self):
        path = self.data_dir()
        self.assertEqual(self.run_normalise(path), 0)
        shutil.rmtree(path / 'interim')
        (path / 'products.jsonl').unlink()
        self.assertEqual(self.run_normalise(path, '--merge-only'), 0)
        self.assertEqual(read_lines(path / 'products.jsonl'), read_lines(EXPECTED))
        self.assertEqual(self.steps(path)[0]['name'], 'đọc checkpoint')

    def test_missing_inputs_and_broken_source_in_isolation(self):
        empty = self.root / 'empty'
        with self.assertLogs('normalise', 'ERROR'):
            self.assertEqual(normalise.main(['--data-dir', str(empty), *ARGS, '--merge-only']), 1)
        path = self.data_dir()
        with self.assertLogs('normalise', 'ERROR'):
            self.assertEqual(normalise.main(['--data-dir', str(path), *ARGS, '--only-source', 'agoda_api']), 1)
        with patch.object(normalise, 'trip_combo_product', side_effect=AttributeError('price')), \
                self.assertRaises(normalise.RecordErrorRateExceeded), self.assertLogs('normalise', 'WARNING'):
            normalise.main(['--data-dir', str(path), *ARGS, '--only-source', 'trip_combos'])
        errors = read_lines(path / 'normalised' / 'trip_combos.errors.jsonl')
        self.assertEqual(len(errors), 2)  # nguồn hỏng dừng riêng nguồn đó, lỗi vẫn được ghi


# ---------------------------------------------------------------------------------------------------- CP5


class PerSourceRunTests(SampleRun):
    def test_sites_normalised_as_they_finish_then_official_run_reuses_all_checkpoints(self):
        runs = self.root / 'runs'
        run = runs / RUN_ID
        shutil.copytree(SAMPLE, run / 'interim')
        direct = self.data_dir('direct')  # cùng ngày, không --today: so với luồng một lần chạy
        self.assertEqual(normalise.main(['--data-dir', str(direct), *ARGS[:-2]]), 0)
        previewer = fresh_catalog.Previewer(run, '@deep')
        with contextlib.redirect_stdout(io.StringIO()) as out:
            for group, merge in (('trip', True), ('vinpearl', True), ('booking', True), ('agoda', False)):
                previewer.group_done(group, 'ok', merge=merge)
            previewer.finish(keep=False)
        metas = sorted(p.name for p in (run / 'normalised').glob('*.meta.json'))
        self.assertEqual(metas, sorted(f'{f.stem}.meta.json' for f in SAMPLE.glob('*.jsonl')))
        self.assertIn('catalog.preview.done', out.getvalue())
        with self.assertLogs('normalise', 'INFO') as logs:
            products = fresh_catalog.normalize(run, '@deep')
        reused = [line for line in logs.output if 'normalise.source.reuse' in line]
        self.assertEqual(len(reused), 7)  # bản chính thức không ánh xạ lại nguồn nào
        self.assertEqual(read_lines(products), read_lines(direct / 'products.jsonl'))
        (run / 'run.json').write_text(json.dumps({'id': RUN_ID, 'status': 'ok', 'steps': []}), encoding='utf-8')
        view = monitor.FreshMonitor(self.root / 'state', runs).normalise(RUN_ID)
        self.assertEqual({c['source']: c['status'] for c in view['checkpoints']},
                         {f.stem: 'ok' for f in SAMPLE.glob('*.jsonl')})

    def test_stale_or_failed_checkpoint_is_mapped_again(self):
        path = self.data_dir()
        self.assertEqual(self.run_normalise(path), 0)
        meta = path / 'normalised' / 'booking_hotels.meta.json'
        data = json.loads(meta.read_text(encoding='utf-8'))
        meta.write_text(json.dumps(dict(data, status='failed')), encoding='utf-8')
        interim = path / 'interim' / 'trip_flights.jsonl'
        interim.write_text(interim.read_text(encoding='utf-8'), encoding='utf-8')  # site ghi lại file: mtime đổi
        with self.assertLogs('normalise', 'INFO') as logs:
            self.assertEqual(self.run_normalise(path, '--reuse-checkpoints'), 0)
        mapped = {line.split('name=')[1].split()[0] for line in logs.output if 'normalise.source.done' in line}
        self.assertEqual(mapped, {'booking_hotels', 'trip_flights'})
        self.assertEqual(read_lines(path / 'products.jsonl'), read_lines(EXPECTED))

# ---------------------------------------------------------------------------------------------------- soát tay 13/10/2026


class ReviewedOverridesTests(SampleRun):
    """Chạy trọn normalise trên mẫu: khách sạn bị loại thì hạng phòng cũng không còn (job không bật lại khách sạn đã ẩn),
    tên trong name_overrides.csv được áp cho mọi loại sản phẩm (cả tour booking.com)."""

    def test_excluded_hotel_loses_its_rooms_and_reviewed_name_is_applied(self):
        excluded = self.root / 'excluded.csv'
        excluded.write_text('sourceRef,reason,evidence\nbooking:hotel:13399754,thử loại khách sạn,test\n', encoding='utf-8')
        names = self.root / 'names.csv'
        names.write_text('sourceRef,name,evidence\nbooking:attraction:prxty9xfoiyk,Tour văn hoá Sài Gòn buổi tối,test\n',
                         encoding='utf-8')
        path = self.data_dir()
        with patch.object(normalise, 'EXCLUDED_PRODUCTS_CSV', excluded), patch.object(normalise, 'NAME_OVERRIDES_CSV', names), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.run_normalise(path), 0)
        products = [json.loads(line) for line in read_lines(path / 'products.jsonl')]
        refs = {p['sourceRef'] for p in products}
        expected = {json.loads(line)['sourceRef'] for line in read_lines(EXPECTED)}
        dropped = {r for r in expected if r == 'booking:hotel:13399754' or r.startswith('booking:hotel:13399754:room:')}
        self.assertEqual(len(dropped), 6)  # khách sạn + 5 hạng phòng
        self.assertEqual(refs, expected - dropped)
        # hạng phòng bị loại ngay ở bước soát tay, cùng lý do với khách sạn cha (drop_orphans về sau chỉ là lưới an toàn)
        with gzip.open(path / 'normalise_stages' / 'dropped.jsonl.gz', 'rt', encoding='utf-8') as f:
            reasons = {d['product']['sourceRef']: (d['step'], d['reason']) for d in map(json.loads, f)
                       if d['product'].get('sourceRef') in dropped}
        self.assertEqual(set(reasons), dropped)
        self.assertEqual({step for step, _ in reasons.values()}, {'excluded'})
        rooms = {r for r in dropped if ':room:' in r}
        self.assertTrue(all(reasons[r][1] == 'khách sạn cha đã loại: thử loại khách sạn' for r in rooms))
        tour = next(p for p in products if p['sourceRef'] == 'booking:attraction:prxty9xfoiyk')
        self.assertEqual(tour['name'], 'Tour văn hoá Sài Gòn buổi tối')
        self.assertEqual(tour['attributes']['nameSource'], 'reviewed: collectors/name_overrides.csv')


if __name__ == '__main__':
    unittest.main()
