"""Chuẩn hoá từng phần trong lúc cào (L1, docs/plan/2026-09-28-pipeline-chay-lien-tuc.md).

Điều kiện chính: interim lớn dần theo từng khúc, checkpoint cuối của `normalise_stream` giống hệt `normalise.py --only-source`
chạy một lần trên cả file, và bước normalize chính thức dùng lại được mọi checkpoint.
"""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fresh_catalog
import fresh_settings
import normalise
import normalise_stream as ns

SAMPLE = Path(__file__).resolve().parent / 'fixtures' / 'normalise_sample' / 'interim'
EXPECTED = SAMPLE.parent / 'expected_products.jsonl'
ARGS = ['--rooms-per-hotel', '0', '--flights-per-route', '0', '--keep-unsellable', '--keep-missing-coordinates',
        '--keep-location-warnings', '--keep-price-outliers', '--destinations', '@deep', '--today', '2026-09-28']
STEMS = sorted(p.stem for p in SAMPLE.glob('*.jsonl'))
SAME_META = ('source', 'status', 'error', 'records', 'entries', 'rows', 'errors', 'interimMtimeNs', 'interimBytes',
             'today', 'rates', 'flightsPerRoute')


def lines(stem):
    return (SAMPLE / f'{stem}.jsonl').read_text(encoding='utf-8').splitlines(keepends=True)


class StreamTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.logs = []

    def stream_dir(self, name='stream'):
        path = self.root / name
        (path / 'interim').mkdir(parents=True)
        return path

    def streamer(self, path):
        return ns.StreamNormaliser(path, ['--data-dir', str(path), *ARGS], 1, self.logs.append)

    def batch(self, stem):
        """Checkpoint của bản theo lô (--only-source) trên cùng file interim."""
        path = self.root / 'batch'
        path.mkdir(exist_ok=True)
        shutil.copytree(self.root / 'stream' / 'interim', path / 'interim', dirs_exist_ok=True)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(normalise.main(['--data-dir', str(path), *ARGS, '--only-source', stem]), 0)
        return path / 'normalised'

    def read(self, folder, stem):
        meta = json.loads((folder / f'{stem}.meta.json').read_text(encoding='utf-8'))
        return ((folder / f'{stem}.jsonl').read_bytes(), (folder / f'{stem}.errors.jsonl').read_bytes(),
                {k: meta.get(k) for k in SAME_META})

    def test_growing_interim_gives_same_checkpoint_as_batch(self):
        path = self.stream_dir()
        stream = self.streamer(path)
        for stem in STEMS:
            with self.subTest(stem=stem):
                rows, target = lines(stem), path / 'interim' / f'{stem}.jsonl'
                cuts = [len(rows) // 3, 2 * len(rows) // 3, len(rows)]
                start = 0
                for cut in cuts:  # collector nối thêm bản ghi 3 lần
                    with target.open('a', encoding='utf-8') as fh:
                        fh.write(''.join(rows[start:cut]))
                    start = cut
                    stream.follower(stem).poll()
                meta = stream.finish_source(stem)
                self.assertEqual(meta['status'], 'ok')
                self.assertGreaterEqual(meta['batches'], 2)
                self.assertEqual(self.read(path / 'normalised', stem), self.read(self.batch(stem), stem))

    def test_official_normalise_reuses_every_streamed_checkpoint(self):
        path = self.stream_dir()
        stream = self.streamer(path)
        for stem in STEMS:
            half = lines(stem)[:len(lines(stem)) // 2]
            (path / 'interim' / f'{stem}.jsonl').write_text(''.join(half), encoding='utf-8')
        stream.poll_all()
        for stem in STEMS:
            with (path / 'interim' / f'{stem}.jsonl').open('a', encoding='utf-8') as fh:
                fh.write(''.join(lines(stem)[len(lines(stem)) // 2:]))
            stream.finish_source(stem)
        with self.assertLogs('normalise', 'INFO') as logs:
            self.assertEqual(normalise.main(['--data-dir', str(path), *ARGS, '--reuse-checkpoints']), 0)
        self.assertEqual(sum('normalise.source.reuse' in line for line in logs.output), len(STEMS))
        self.assertEqual((path / 'products.jsonl').read_text(encoding='utf-8').splitlines(),
                         EXPECTED.read_text(encoding='utf-8').splitlines())

    def test_meta_keeps_substep_timings_and_batch_history(self):
        path = self.stream_dir()
        target = path / 'interim' / 'booking_hotels.jsonl'
        rows = lines('booking_hotels')
        follower = self.streamer(path).follower('booking_hotels')
        target.write_text(''.join(rows[:2]), encoding='utf-8')
        follower.poll()
        with target.open('a', encoding='utf-8') as fh:
            fh.write(''.join(rows[2:]))
        follower.poll(final=True)
        meta = json.loads((path / 'normalised' / 'booking_hotels.meta.json').read_text(encoding='utf-8'))
        self.assertEqual([s['name'] for s in meta['steps']],
                         ['đọc phần mới', 'bỏ trùng theo khoá', 'ánh xạ bản ghi mới', 'ghi checkpoint'])
        self.assertTrue(all(s['seconds'] >= 0 for s in meta['steps']))
        self.assertEqual([(h['n'], h['newRecords'], h['final']) for h in meta['history']],
                         [(1, 2, False), (2, len(rows) - 2, True)])

    def test_line_without_newline_waits_for_next_batch(self):
        path = self.stream_dir()
        rows = lines('booking_hotels')
        target = path / 'interim' / 'booking_hotels.jsonl'
        target.write_text(rows[0] + rows[1][:40], encoding='utf-8')  # dòng 2 đang ghi dở
        follower = self.streamer(path).follower('booking_hotels')
        self.assertEqual(follower.poll()['records'], 1)
        with target.open('a', encoding='utf-8') as fh:
            fh.write(rows[1][40:])
        self.assertEqual(follower.poll()['records'], 2)

    def test_nothing_new_writes_nothing(self):
        path = self.stream_dir()
        (path / 'interim' / 'trip_combos.jsonl').write_text(''.join(lines('trip_combos')), encoding='utf-8')
        follower = self.streamer(path).follower('trip_combos')
        self.assertIsNotNone(follower.poll())
        self.assertIsNone(follower.poll())

    def test_rewritten_file_is_read_again_without_mapping_again(self):
        path = self.stream_dir()
        target = path / 'interim' / 'booking_hotels.jsonl'
        target.write_text(''.join(lines('booking_hotels')), encoding='utf-8')
        follower = self.streamer(path).follower('booking_hotels')
        first = follower.poll()
        tmp = target.with_suffix('.tmp')  # collector ghi lại cả file qua file tạm rồi đổi tên (inode mới)
        tmp.write_text(''.join(lines('booking_hotels')), encoding='utf-8')
        tmp.replace(target)
        again = follower.poll(final=True)
        self.assertEqual((again['records'], again['rows'], again['mappedThisBatch']), (first['records'], first['rows'], 0))
        self.assertEqual(again['interimBytes'], target.stat().st_size)

    def test_record_errors_accumulate_across_batches(self):
        path = self.stream_dir()
        rows = lines('booking_hotels')
        target = path / 'interim' / 'booking_hotels.jsonl'
        broken = json.loads(rows[0])['key']
        real = normalise.booking_hotel

        def flaky(record, *args):
            if record.get('key') == broken:
                raise KeyError('rooms')
            return real(record, *args)
        follower = self.streamer(path).follower('booking_hotels')
        with patch.object(normalise, 'booking_hotel', flaky):
            target.write_text(rows[0], encoding='utf-8')
            self.assertEqual(follower.poll()['errors'], 1)
            with target.open('a', encoding='utf-8') as fh:
                fh.write(''.join(rows[1:]))
            meta = follower.poll(final=True)
        self.assertEqual((meta['errors'], meta['status']), (1, 'ok'))  # 1 lỗi lẻ < ngưỡng
        errors = (path / 'normalised' / 'booking_hotels.errors.jsonl').read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(errors), 1)
        self.assertIn('KeyError', json.loads(errors[0])['error'])

    def test_failing_source_does_not_stop_others(self):
        path = self.stream_dir()
        for stem in ('trip_combos', 'booking_hotels'):
            (path / 'interim' / f'{stem}.jsonl').write_text(''.join(lines(stem)), encoding='utf-8')
        stream = self.streamer(path)
        real = ns.SourceFollower.poll

        def poll(follower, final=False):
            if follower.stem == 'trip_combos':
                raise RuntimeError('hỏng')
            return real(follower, final)
        with patch.object(ns.SourceFollower, 'poll', poll):
            self.assertEqual(stream.poll_all(), 1)  # booking vẫn được chuẩn hoá
        self.assertTrue(any('normalise.stream.failed' in line and 'trip_combos' in line for line in self.logs))


class PartialFileTests(StreamTests):
    """L2: collector ghi vào `<nguồn>.jsonl.tmp` rồi đổi tên ở cuối (Vinpearl: từng khách sạn/tour flush ngay)."""

    def write_partial(self, path, stem, rows):
        with (path / 'interim' / f'{stem}.jsonl.tmp').open('a', encoding='utf-8') as fh:
            fh.write(''.join(rows))

    def test_partial_file_is_followed_then_rename_is_not_read_again(self):
        path = self.stream_dir()
        stream = self.streamer(path)
        rows = lines('vinpearl')
        self.write_partial(path, 'vinpearl', rows[:len(rows) // 2])
        self.assertEqual(stream.poll_all(), 1)  # nguồn chỉ có file tạm vẫn được nhận ra
        first = stream.follower('vinpearl').meta
        self.assertEqual((first['status'], first['records']), ('streaming', len(json_keys(rows[:len(rows) // 2]))))
        self.write_partial(path, 'vinpearl', rows[len(rows) // 2:])
        stream.poll_all()
        (path / 'interim' / 'vinpearl.jsonl.tmp').replace(path / 'interim' / 'vinpearl.jsonl')  # collector xong
        self.assertEqual(stream.poll_all(), 0)  # cùng inode, cùng nội dung: không có gì mới
        meta = stream.finish_source('vinpearl')
        self.assertEqual((meta['status'], meta['mappedThisBatch']), ('ok', 0))
        self.assertEqual(self.read(path / 'normalised', 'vinpearl'), self.read(self.batch('vinpearl'), 'vinpearl'))

    def test_source_stopped_before_rename_has_no_checkpoint_like_batch(self):
        path = self.stream_dir()
        stream = self.streamer(path)
        self.write_partial(path, 'vinpearl', lines('vinpearl'))
        stream.poll_all()
        self.assertTrue((path / 'normalised' / 'vinpearl.meta.json').is_file())  # bản nháp trong lúc cào vẫn thấy
        stream.close()  # lượt hết cào mà Vinpearl không đổi tên file tạm
        self.assertEqual(sorted(p.name for p in (path / 'normalised').iterdir() if not p.name.startswith('.')), [])
        self.assertTrue(any('normalise.stream.dropped' in line for line in self.logs))
        self.assertIsNone(stream.finish_source('vinpearl'))


def json_keys(rows):
    return {json.loads(row)['key'] for row in rows if row.strip()}


class PreviewerStreamTests(unittest.TestCase):
    def test_previewer_streams_then_official_run_reuses_checkpoints(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        run = root / 'runs' / 'full-20260928T010000Z-1'
        (run / 'interim').mkdir(parents=True)
        direct = root / 'direct'
        shutil.copytree(SAMPLE, direct / 'interim')
        cfg = {f.key: f.default for f in fresh_settings.FIELDS} | {'stream.enabled': True, 'stream.normaliseSeconds': 2,
                                                                    'normalise.roomsPerHotel': 0}
        with patch.object(fresh_catalog, 'CFG', cfg):
            direct_args = [*fresh_catalog.normalise_args(direct, '@deep', cfg, stage=False)]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(normalise.main(direct_args), 0)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                previewer = fresh_catalog.Previewer(run, '@deep')
                self.assertIsNotNone(previewer.stream)
                for stem in STEMS:  # các site ghi interim trong lúc luồng chuẩn hoá đang chạy
                    (run / 'interim' / f'{stem}.jsonl').write_text(''.join(lines(stem)), encoding='utf-8')
                previewer.stream.poll_all()
                for group, merge in (('trip', True), ('vinpearl', True), ('booking', True), ('agoda', False)):
                    previewer.group_done(group, 'ok', merge=merge)
                previewer.finish(keep=False)
            self.assertIn('normalise.stream.batch', out.getvalue())
            self.assertFalse(previewer.stream.thread.is_alive())
            metas = {p.name[:-len('.meta.json')]: json.loads(p.read_text(encoding='utf-8'))
                     for p in (run / 'normalised').glob('*.meta.json')}
            self.assertEqual({k: m['status'] for k, m in metas.items()}, {stem: 'ok' for stem in STEMS})
            with self.assertLogs('normalise', 'INFO') as logs:
                products = fresh_catalog.normalize(run, '@deep')
        self.assertEqual(sum('normalise.source.reuse' in line for line in logs.output), len(STEMS))
        self.assertEqual(products.read_text(encoding='utf-8').splitlines(),
                         (direct / 'products.jsonl').read_text(encoding='utf-8').splitlines())

    def test_stream_is_off_by_default(self):
        self.assertFalse({f.key: f.default for f in fresh_settings.FIELDS}['stream.enabled'])



class PreviewerFeedTests(unittest.TestCase):
    """L3–L5 nối trong Previewer: catalog đang gộp → nạp DB theo phần → index theo phần, rồi dừng gọn khi site xong."""

    def test_stream_feeds_db_and_index_from_the_merging_catalog(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        run = Path(tmp.name) / 'full-20260928T010000Z-1'
        (run / 'interim').mkdir(parents=True)
        cfg = {f.key: f.default for f in fresh_settings.FIELDS} | {
            'stream.enabled': True, 'stream.db': True, 'stream.index': True, 'normalise.roomsPerHotel': 0,
            'stream.minRecords': 1}
        loads, indexed = [], []

        def fake_load(path, coverage, url, root, report_path=None, **_):
            loads.append([json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()])
            return {'dbRowsWritten': len(loads[-1])}

        with patch.object(fresh_catalog, 'CFG', cfg), patch.object(fresh_catalog, 'load_into_db', fake_load), \
                patch.object(fresh_catalog, 'index_catalog', lambda config, path: indexed.append(path) or {'embedded': 3}), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            previewer = fresh_catalog.Previewer(run, '@deep', 'postgresql://local', object())
            tickers = {t.name: t for t in previewer.tickers}
            self.assertEqual(sorted(tickers), ['db', 'index', 'merge'])
            for stem in STEMS:
                (run / 'interim' / f'{stem}.jsonl').write_text(''.join(lines(stem)), encoding='utf-8')
            previewer.stream.poll_all()
            self.assertIsNotNone(tickers['merge'].run_once())  # checkpoint đổi → gộp
            previewer.thread.join(60)
            self.assertTrue((run / 'preview' / 'products.jsonl').is_file())
            self.assertIsNone(tickers['merge'].run_once())  # không đổi → không gộp lại
            batch = tickers['db'].run_once()
            self.assertGreater(batch['rows'], 0)
            loaded = {r['sourceRef'] for r in loads[0]}
            self.assertFalse(any(ref.startswith('trip:hotel:') for ref in loaded))
            self.assertFalse(any(r['taxonomy'] == 'combo' for r in loads[0]))
            self.assertIsNone(tickers['db'].run_once())  # không đổi → không nạp lại
            self.assertEqual(tickers['index'].run_once()['newDbRows'], batch['rows'])
            self.assertIsNone(tickers['index'].run_once())
            previewer.finish(keep=False)
        self.assertTrue(all(not t.thread.is_alive() for t in previewer.tickers))
        self.assertEqual(len(indexed), 1)
        self.assertIn('stream.db.batch', out.getvalue())
        self.assertTrue((run / 'db_batches.jsonl').is_file() and (run / 'index_batches.jsonl').is_file())

    def test_db_feed_needs_a_database_url(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cfg = {f.key: f.default for f in fresh_settings.FIELDS} | {'stream.enabled': True, 'stream.db': True}
        with patch.object(fresh_catalog, 'CFG', cfg), contextlib.redirect_stdout(io.StringIO()):
            previewer = fresh_catalog.Previewer(Path(tmp.name), None)
            self.assertEqual([t.name for t in previewer.tickers], ['merge'])
            previewer.finish(keep=False)


if __name__ == '__main__':
    unittest.main()
