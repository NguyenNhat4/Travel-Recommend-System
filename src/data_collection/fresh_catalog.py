#!/usr/bin/env python3
"""One-repository fresh catalog job for the console VM.

Full runs crawl Travel's existing sources plus a bounded new Trip hotel batch.
Daily runs rotate known Trip IDs. Only ID/timestamp state survives between runs as
job input; all prices and product rows are read from this run's fresh source responses.

Modes: auto (full/daily by date) · full · daily · index (maintain + index only) · status ·
due (print the mode a cron tick should run now, or nothing). Settings come from
`fresh_settings.py` (monitor → env → defaults). Each run keeps its data and log in
`<CATALOG_RUN_ROOT>/<run>/` for the monitor (`runs.keep` newest runs are retained).
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import alerts
import fresh_settings
import index_backlog
import pipeline_errors as perr
import pipeline_graph as graph
from collectors import live_control
from collectors.common import Paths
from collectors.plan import select_destinations
from collectors.trip_live import LiveOptions, crawl, discover
from fresh_catalog_db import checked_trip_hotels, load_into_db, maintain_catalog, validate_catalog
from fresh_catalog_schedule import read_state, read_targets, record_batch, select_batch, write_state
from fresh_run_log import RunRecorder, StopRequested, prune_runs, read_json, run_dirs, terminate_tree, write_json
from normalise import PRODUCT_FIELDS, main as normalise_main
from normalise_stream import StreamNormaliser
from stream_feed import DbFeeder, DraftMerger, IndexFeeder, Ticker

ROOT = Path(__file__).resolve().parent
EXIT_PARTIAL = 3   # lỗi, hoặc còn ngày Trip chưa có giá / có nguồn bị chặn
EXIT_STOPPED = 5   # người vận hành bấm Dừng
# Nguồn, nhóm site, file interim, bước sau cào và quan hệ giữa chúng khai báo ở pipeline_graph.py (P3,
# docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md). Lượt full: mỗi site một nhóm, các nhóm chạy song song
# (crawl.parallelSites), trong một nhóm vẫn tuần tự nên số request đồng thời tới từng site không đổi.
SITE_GROUPS = graph.SITE_GROUPS
SOURCE_SWITCH = graph.SOURCE_SWITCH
LIVE_KEYS = graph.LIVE_KEYS       # khoá chỉnh tốc độ live của từng bước crawl.py; khách sạn Trip chạy trong tiến trình này
GROUP_INTERIM = graph.SITE_INTERIM  # nhóm site → file interim; bước lỗi / file không khai báo được chuẩn hoá khi nhóm xong
STEP_INTERIM = graph.STEP_INTERIM  # bước cào → file nó ghi: bước xong thì chuẩn hoá ngay (P1); hàm khai báo thuộc tính `step`
LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1'}
PREVIEW_DIR = 'preview'
REQUIRED = {('hotel', 'property'), ('hotel', 'room'), ('flight', 'route'),
            ('flight', 'flight'), ('attraction', None), ('combo', None)}

CFG: dict | None = None            # cấu hình của lượt đang chạy (fresh_settings.load)
REC: RunRecorder | None = None     # nhật ký của lượt đang chạy


def settings_values() -> dict:
    return CFG if CFG is not None else {f.key: f.default for f in fresh_settings.FIELDS}


def dirs() -> tuple[Path, Path]:
    state_dir = Path(os.environ.get('CATALOG_STATE_DIR', ROOT / 'data' / 'state')).resolve()
    run_root = Path(os.environ.get('CATALOG_RUN_ROOT', ROOT / 'data' / 'fresh_runs')).resolve()
    if state_dir == run_root or run_root in state_dir.parents:
        raise ValueError('CATALOG_STATE_DIR phải nằm ngoài CATALOG_RUN_ROOT')
    return state_dir, run_root


def saved_targets(path: Path) -> list[dict]:
    return read_targets(path) if path.is_file() else []


def merge_targets(path: Path, fresh: list[dict]) -> list[dict]:
    by_id = {row['trip_hotel_id']: row for row in saved_targets(path)}
    for row in fresh:
        by_id[row['trip_hotel_id']] = {'trip_hotel_id': row['trip_hotel_id'],
                                       'city_id': row['city_id'],
                                       'destination': row['destination']}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'hotels': list(by_id.values())}, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)
    return list(by_id.values())


def trip_cities(values: dict):
    """Thành phố khách sạn Trip: lựa chọn trên monitor, hoặc phạm vi điểm đến; luôn trong 7 thành phố hiện có."""
    allowed = set(fresh_settings.TRIP_HOTEL_CITIES)
    chosen = values.get('tripHotels.cities')
    pool = select_destinations('@all' if chosen else values['scope.destinations'])
    wanted = set(chosen) if chosen else {d.name for d in pool}
    return tuple(d for d in pool if d.name in wanted & allowed and d.trip_hotel_city_id)


_print_lock = threading.Lock()


def say(line: str) -> None:
    """Một dòng log nguyên vẹn khi nhiều nhóm cùng in."""
    with _print_lock:
        print(line, flush=True)


def _num(value: float) -> str:
    return f'{value:g}'


def source_command(run_dir: Path, source: str, destinations: str, values: dict) -> list[str]:
    """Lệnh crawl.py của một nguồn theo cấu hình."""
    # Giữ id bước agoda-hotels để tương thích run.json/monitor cũ, nhưng dùng collector HTTP đã có khả năng
    # xuất hotel_room + giá thật. Collector trình duyệt cũ chỉ tạo property nên FE không có phòng để bán.
    cli_source = 'agoda-api' if source == 'agoda-hotels' else source
    command = [sys.executable, str(ROOT / 'crawl.py')]
    if values['log.verbose']:
        command.append('-v')
    command += ['--data-dir', str(run_dir), cli_source, '--max-blocks', str(values['crawl.maxBlocks'])]
    if source == 'vinpearl':
        command += ['--refresh', '--delay', _num(values['vinpearl.delay']),
                    '--price-dates', ','.join(str(d) for d in values['vinpearl.priceOffsets'])]
        if not values['vinpearl.tours']:
            command.append('--skip-tours')
        return command
    command += ['--destinations', destinations]
    if source in ('trip-flights', 'trip-attractions'):
        command += ['--delay', _num(values['trip.delay'])]
        if source == 'trip-attractions':
            command += ['--budget', f"trip_attractions={values['tripAttractions.perDestination']}"]
        if source == 'trip-flights':
            command += ['--fares-minutes', str(values['tripFlights.fareMinutes'])]
            if values['timeout.tripFlights']:
                command += ['--source-deadline-minutes', str(values['timeout.tripFlights'])]
    elif source == 'booking-hotels':
        command += ['--delay', _num(values['booking.delay']), '--concurrency', str(values['booking.tabs']),
                    '--checkin-offset-days', str(values['booking.checkinOffsetDays']),
                    '--budget', f"booking_hotels={values['booking.hotelsPerDestination']}"]
        if values['booking.fast']:
            command.append('--fast')
        if not values['booking.vinpearlBrand']:
            command.append('--no-brand-sitemap')
    elif source == 'agoda-hotels':
        # Một ngày giá thật đủ để xác nhận phòng bán được; fresh_catalog_db mở rộng availability thành cửa sổ 30 ngày.
        # State SQLite của collector giúp lượt sau tiếp tục thay vì cào lại từ đầu.
        command += ['--delay', _num(values['agoda.delay']),
                    '--per-city', str(values['agoda.hotelsPerDestination']), '--days', '1']
    return command


SOURCE_TAIL: dict[str, deque] = {}  # nguồn → các dòng log cuối của lần chạy gần nhất, để phân loại lỗi


def run_source(run_dir: Path, source: str, destinations: str, group: str, deadline: float | None = None) -> int:
    """Chạy `crawl.py <source>`. `deadline` (time.monotonic): quá hạn thì dừng cả cây tiến trình của nguồn này (crawl.py,
    Chromium) và trả perr.EXIT_TIMEOUT (P4); các nguồn khác không bị đụng."""
    command = source_command(run_dir, source, destinations, settings_values())
    say(f'[{group}] $ ' + ' '.join(command))
    env = dict(os.environ, CRAWL_LIVE_KEY=LIVE_KEYS.get(source, ''), PYTHONUNBUFFERED='1')
    tail = SOURCE_TAIL[source] = deque(maxlen=80)
    timed_out = threading.Event()
    with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors='replace', env=env) as proc:
        if deadline is not None:
            def watch() -> None:
                while proc.poll() is None:
                    if time.monotonic() >= deadline:
                        timed_out.set()
                        say(f'[{group}] catalog.source.timeout name={source}: quá hạn giờ, dừng nguồn này')
                        terminate_tree(proc.pid)
                        return
                    time.sleep(0.5)
            threading.Thread(target=watch, name=f'timeout-{source}', daemon=True).start()
        for line in proc.stdout:
            tail.append(line.rstrip())
            say(f'[{group}] {line.rstrip()}')
    return perr.EXIT_TIMEOUT if timed_out.is_set() else proc.returncode


def deadline_after(seconds: float) -> float | None:
    """Hạn chót (time.monotonic) sau `seconds` giây; 0 = không giới hạn."""
    return time.monotonic() + seconds if seconds and seconds > 0 else None


def step_deadline(name: str, crawl_deadline: float | None) -> float | None:
    """Hạn chót của một bước cào: hạn giờ riêng của bước (`timeout.*`, phút) hoặc hạn của cả phần cào, lấy cái sớm hơn."""
    key = graph.STEP_TIMEOUT.get(name)
    own = deadline_after(float(settings_values()[key]) * 60) if key else None
    return min((d for d in (own, crawl_deadline) if d is not None), default=None)


def seal_interim(run_dir: Path, stems) -> list[str]:
    """Nguồn bị dừng giữa chừng (quá giờ): bỏ dòng ghi dở ở cuối file interim; collector chỉ ghi file tạm (Vinpearl
    `<nguồn>.jsonl.tmp`, đổi tên khi cào xong) thì đổi tên luôn để phần đã cào được chuẩn hoá. Trả các file đã sửa."""
    sealed = []
    for stem in stems:
        final = run_dir / 'interim' / f'{stem}.jsonl'
        partial = final.with_name(final.name + '.tmp')
        target = partial if partial.is_file() and not final.exists() else final
        if not target.is_file():
            continue
        with target.open('rb+') as fh:
            data = fh.read()
            keep = data.rfind(b'\n') + 1
            if keep < len(data):
                fh.truncate(keep)
        if target is partial:
            partial.rename(final)
        sealed.append(stem)
    return sealed


def wait_or_stop(seconds: float) -> None:
    """Chờ trước lần thử lại; người vận hành bấm Dừng thì dừng ngay."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if REC is not None:
            REC.check_stop()
        time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))


def retry_note(detail: dict | None, name: str, attempt: int, plan: dict, kind: str, reason: str) -> float:
    """Ghi một lần thử lại vào log + chi tiết bước; trả số giây phải chờ (tăng gấp `factor` mỗi lần)."""
    wait = plan['delay'] * plan['factor'] ** (attempt - 1)
    say(f'catalog.retry step={name} attempt={attempt}/{plan["retries"]} kind={kind} wait={wait:g}s reason={reason[:200]}')
    if detail is not None:
        detail.setdefault('attempts', []).append({'attempt': attempt, 'kind': kind, 'reason': reason[:300],
                                                  'waitSeconds': wait})
    return wait


def with_retry(name: str, fn, detail: dict | None = None):
    """Chạy `fn()`; lỗi tạm thời / hạ tầng thì thử lại theo Cấu hình (pipeline_errors.strategy), loại khác thì raise
    ngay. Exception thoát ra được gắn `pipeline_kind` để run.json và monitor biết loại lỗi."""
    attempt = 0
    while True:
        try:
            return fn()
        except perr.PipelineError:
            raise
        except Exception as exc:
            if name == 'index' and index_backlog.rate_limit(exc)[0]:
                raise  # persistent cooldown owns quota retries, not the outer retry loop
            kind = perr.classify_exception(exc)
            plan = perr.strategy(kind, settings_values())
            if plan['action'] != 'retry' or attempt >= plan['retries']:
                exc.pipeline_kind = kind
                if detail is not None:
                    detail['errorKind'] = kind
                raise
            attempt += 1
            wait_or_stop(retry_note(detail, name, attempt, plan, kind, f'{type(exc).__name__}: {exc}'))


def notify_finished(data: dict, run_dir: Path, state_dir: Path, values: dict) -> None:
    """CP7: cảnh báo của lượt vừa kết thúc (ghi file, monitor hiện). Best effort: không đổi kết quả lượt."""
    try:
        alerts.on_run_finished(data, run_dir, state_dir, values)
    except Exception as exc:
        print(f'alert.failed {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)


def check_sla(state_dir: Path, run_root: Path, values: dict) -> None:
    """CP8: kiểm SLA ở mỗi cron tick (kể cả tick rảnh; không cần DB). Best effort."""
    try:
        alerts.check_sla(state_dir, run_root, values)
    except Exception as exc:
        print(f'alert.sla.failed {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)


def save_run() -> None:
    """Ghi run.json ngay (detail của bước đang chạy đổi giữa chừng, vd. các việc chạy liên tục)."""
    if REC is not None:
        with REC.lock:
            REC.save()


def step(name: str, group: str | None = None, label: str | None = None):
    """Bước có ghi vào run.json khi đang có lượt; không có lượt (test gọi hàm trực tiếp) thì không làm gì."""
    return REC.step(name, group, label) if REC is not None else contextlib.nullcontext({})


async def run_cancellable(coroutine, deadline: float | None = None):
    """Cancel in-process HTTP/browser work too when the monitor requests a stop, or when `deadline` (time.monotonic)
    passes (P4: raises perr.StepTimeout)."""
    task = asyncio.create_task(coroutine)
    try:
        while not task.done():
            if REC is not None:
                REC.check_stop()
            if deadline is not None and time.monotonic() >= deadline:
                raise perr.StepTimeout('quá hạn giờ của bước, đã dừng')
            await asyncio.wait({task}, timeout=0.25)
        return await task
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


class Previewer:
    """Chuẩn hoá theo nguồn ngay khi một bước cào xong (lượt full), song song với các bước còn đang cào.

    1. Mỗi file interim của bước vừa xong (`source_done`; file còn lại của nhóm khi cả nhóm xong: `group_done`):
       `normalise.py --only-source` trong tiến trình con (tối đa
       `SOURCE_WORKERS` cùng lúc) → checkpoint thật ở `<lượt>/normalised/` (ánh xạ 13 trường, lỗi bản ghi, meta).
    2. Sau mỗi nguồn: bản nháp = `normalise.py --merge-only` trên các checkpoint đang có → `<lượt>/preview.next/` rồi đổi
       tên thành `<lượt>/preview/` (kèm preview.json) cho monitor. Mỗi lúc một bản nháp; nguồn xong trong lúc đang gộp nháp
       thì gộp lại một lần với tập mới nhất.
    3. Cuối lượt, bước normalize chính thức (`normalize`) dùng lại các checkpoint còn mới và chỉ ánh xạ nguồn còn thiếu,
       nên khi bước cào cuối xong chỉ còn phần của bước đó + bước gộp.
    Không validate, không nạp DB, không index ở đây. Lỗi ở đây không làm hỏng lượt: nguồn lỗi sẽ được ánh xạ lại (và báo
    lỗi đúng chỗ) ở bước normalize chính thức.
    """

    SOURCE_WORKERS = 1 if (os.cpu_count() or 2) <= 2 else 2

    STREAM_LABELS = {stream.name: stream.title for stream in graph.STREAMS}

    def __init__(self, run_dir: Path, destinations: str | None, db_url: str | None = None, index_config=None):
        self.run_dir = run_dir
        self.destinations = destinations
        self.done: dict[str, str] = {}
        self.lock = threading.RLock()  # group_done giữ khoá rồi gọi _request_merge (cũng lấy khoá)
        self.pending = False
        self.closed = False
        self.thread: threading.Thread | None = None
        self.proc: subprocess.Popen | None = None
        self.sources = ThreadPoolExecutor(max_workers=self.SOURCE_WORKERS, thread_name_prefix='normalise-source')
        self.jobs: list = []
        self.submitted: set[str] = set()  # file interim đã giao chuẩn hoá (mỗi file đúng một lần)
        values = settings_values()
        # docs/plan/2026-09-28-pipeline-chay-lien-tuc.md — L1: chuẩn hoá từng phần trong lúc cào (bước cào xong chỉ còn
        # chốt nguồn); L3: gộp khi checkpoint đổi; L4: nạp DB theo phần; L5: index theo phần. Monitor chỉnh chu kỳ / tạm dừng /
        # chạy ngay qua live_control (L6). Tắt `stream.enabled` thì như trước.
        self.stream: StreamNormaliser | None = None
        self.tickers: list[Ticker] = []
        self.db_feeder: DbFeeder | None = None
        if values['stream.enabled']:
            self.stream = StreamNormaliser(run_dir, normalise_args(run_dir, destinations, values, stage=False),
                                           values['stream.normaliseSeconds'], say)
            self.stream.start(lambda: live_control.current('stream.normalise'), self._in_step)
            self.tickers.append(Ticker('merge', DraftMerger(run_dir / 'normalised', self._request_merge),
                                       values['stream.mergeSeconds'], lambda: live_control.current('stream.merge'), say))
            if values['stream.db'] and db_url:
                self.db_feeder = DbFeeder(run_dir, db_url, ROOT, load_into_db,
                                          lambda rows: validate_catalog(rows, allow_external_parents=True),
                                          min_records=values['stream.minRecords'],
                                          max_error_percent=values['normalise.maxErrorPercent'], log=say)
                self.tickers.append(Ticker('db', self.db_feeder, values['stream.dbSeconds'],
                                           lambda: live_control.current('stream.db'), say))
                if values['stream.index'] and index_config is not None:
                    feeder = IndexFeeder(run_dir, self.db_feeder, lambda path: index_backlog.guarded_index(
                        (REC.state_dir if REC is not None else dirs()[0]) / 'index_pending.json',
                        lambda: index_catalog(index_config, path)), log=say)
                    self.tickers.append(Ticker('index', feeder, values['stream.indexSeconds'],
                                               lambda: live_control.current('stream.index'), say))
            for ticker in self.tickers:
                ticker.start(self._in_step(ticker))

    def _in_step(self, ticker: Ticker):
        """Vòng lặp của một việc chạy liên tục nằm trong bước `stream.<việc>` của run.json (đang chạy suốt phần cào);
        mỗi lô cập nhật detail (số lô, lô gần nhất, số dòng đã ghi DB) cho monitor."""
        def run() -> None:
            try:
                with step(f'stream.{ticker.name}', group='stream', label=self.STREAM_LABELS[ticker.name]) as detail:
                    def record(result: dict) -> None:
                        detail.update(batches=ticker.runs, last=result, at=datetime.now(timezone.utc).isoformat(timespec='seconds'))
                        if ticker.name in ('db', 'index') and self.db_feeder is not None:
                            detail['dbRowsWritten'] = self.db_feeder.written
                        save_run()
                    ticker.on_result = record
                    original_work = ticker.work
                    def bounded_batch():
                        with step(f'stream.{ticker.name}.batch', group='stream'):
                            return original_work()
                    ticker.work = bounded_batch
                    ticker.loop()
            except Exception as exc:  # StopRequested khi mở bước (lượt đang dừng) hoặc lỗi ghi run.json
                say(f'[stream-{ticker.name}] {type(exc).__name__}: {exc}')
        return run

    # -- 1. chuẩn hoá theo nguồn
    def source_done(self, group: str, stems, merge: bool = True) -> None:
        """Một bước cào của nhóm `group` đã xong hẳn (ok, bị chặn, hoặc đã hết lượt thử): chuẩn hoá ngay các file interim
        của nó. `merge=False`: bước cuối của lượt không lỗi — không gộp nháp vì bản chính thức chạy ngay sau đó."""
        with self.lock:
            if not self.closed:
                self._submit(group, stems, merge)

    def group_done(self, name: str, status: str, merge: bool = True) -> None:
        """Cả nhóm xong: chuẩn hoá các file interim của nhóm chưa được `source_done` giao (bước lỗi làm nhóm dừng, file
        không khai báo trong STEP_INTERIM). `merge=False`: site cuối của lượt không lỗi — không gộp nháp."""
        with self.lock:
            self.done[name] = status
            if self.closed:
                return
            started = any(stem in self.submitted for stem in GROUP_INTERIM.get(name, ()))
            if not self._submit(name, GROUP_INTERIM.get(name, ()), merge) and merge and not started:
                self._request_merge()

    def _submit(self, group: str, stems, merge: bool) -> int:
        """Giao chuẩn hoá các file có trên đĩa và chưa giao; trả số file vừa giao. Gọi khi đang giữ `self.lock`."""
        todo = [stem for stem in stems
                if stem not in self.submitted and (self.run_dir / 'interim' / f'{stem}.jsonl').is_file()]
        for stem in todo:
            self.submitted.add(stem)
            self.jobs.append(self.sources.submit(self._normalise_source, group, stem, merge))
        return len(todo)

    def _normalise_source(self, group: str, stem: str, merge: bool = True) -> None:
        if self.stream is not None:
            self._finish_stream(group, stem)
            if merge:
                self._request_merge()
            return
        with step(graph.NORMALISE_SOURCE + stem, group=group, label=f'Chuẩn hoá nguồn {stem}') as detail:
            command = [sys.executable, str(ROOT / 'normalise.py'),
                       *normalise_args(self.run_dir, self.destinations, settings_values(), stage=False),
                       '--only-source', stem, '--stage-dir', str(self.run_dir / 'normalised' / 'steps' / stem)]
            code = self._run(command, f'[normalise:{stem}]')
            meta = read_json(self.run_dir / 'normalised' / f'{stem}.meta.json', {}) or {}
            detail.update({k: meta.get(k) for k in ('records', 'rows', 'errors', 'seconds', 'status', 'error')},
                          exitCode=code)
            if code:
                detail['_status'] = 'error'
                detail['errorKind'] = perr.CODE if meta.get('status') == 'failed' else perr.UNKNOWN
                say(f'catalog.normalise.source.failed name={stem} exit={code}: sẽ ánh xạ lại ở bước normalize chính thức')
        if merge:
            self._request_merge()

    def _finish_stream(self, group: str, stem: str) -> None:
        """Site đã cào xong: đọc phần còn lại của interim và chốt checkpoint (phần lớn đã ánh xạ trong lúc cào)."""
        with step(graph.NORMALISE_SOURCE + stem, group=group, label=f'Chuẩn hoá nguồn {stem} (chốt, chạy liên tục)') as detail:
            try:
                meta = self.stream.finish_source(stem) or {}
            except Exception as exc:  # như tiến trình con lỗi: không hỏng lượt, bản chính thức ánh xạ lại nguồn này
                detail.update(_status='error', errorKind=perr.classify_exception(exc), error=f'{type(exc).__name__}: {exc}')
                say(f'catalog.normalise.source.failed name={stem} {type(exc).__name__}: {exc}: sẽ ánh xạ lại ở bước normalize chính thức')
                return
            detail.update({k: meta.get(k) for k in ('records', 'rows', 'errors', 'seconds', 'status', 'error', 'batches')},
                          stream=True)
            if meta.get('status') == 'failed':
                detail['_status'] = 'error'
                detail['errorKind'] = perr.CODE
                say(f'catalog.normalise.source.failed name={stem}: {meta.get("error")}; sẽ ánh xạ lại ở bước normalize chính thức')

    def _run(self, command: list[str], prefix: str, track: bool = False) -> int:
        proc = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                errors='replace', env=dict(os.environ, PYTHONUNBUFFERED='1'))
        if track:
            with self.lock:
                self.proc = proc
        ended = threading.Event()
        expired = threading.Event()
        def watch():
            if not ended.wait(float(settings_values()['timeout.processing']) * 60):
                expired.set()
                terminate_tree(proc.pid, grace=2)
        threading.Thread(target=watch, daemon=True).start()
        try:
            for line in proc.stdout:
                say(f'{prefix} {line.rstrip()}')
            code = proc.wait()
            return perr.EXIT_TIMEOUT if expired.is_set() else code
        finally:
            ended.set()

    # -- 2. bản nháp gộp từ checkpoint
    def _request_merge(self) -> None:
        with self.lock:
            if self.closed:
                return
            if self.thread is not None and self.thread.is_alive():
                self.pending = True
                return
            self.thread = threading.Thread(target=self._loop, name='preview', daemon=True)
            self.thread.start()

    def finish(self, keep: bool) -> None:
        """Đợi các job chuẩn hoá theo nguồn (checkpoint dùng cho bản chính thức). `keep=True`: đợi cả bản nháp đang gộp
        (lượt lỗi, sẽ không có bản chính thức); False: dừng bản nháp ngay."""
        for job in list(self.jobs):
            job.result()
        self.sources.shutdown(wait=True)
        if self.stream is not None:
            self.stream.close()
        for ticker in self.tickers:  # lô đang chạy dở (nạp DB, index) chạy xong rồi mới dừng
            ticker.close()
        with self.lock:
            if not keep:
                self.closed = True
                if self.proc is not None and self.proc.poll() is None:
                    self.proc.terminate()
            thread = self.thread
        if thread is not None:
            thread.join()

    def _loop(self) -> None:
        while True:
            with self.lock:
                if self.closed:
                    return
                groups, self.pending = dict(self.done), False
            try:
                self._build(groups)
            except Exception as exc:
                say(f'[preview] {type(exc).__name__}: {exc}')
            with self.lock:
                if not self.pending or self.closed:
                    return

    def _build(self, groups: dict[str, str]) -> None:
        checkpoints = self.run_dir / 'normalised'
        stems = sorted(p.name[:-len('.meta.json')] for p in checkpoints.glob('*.meta.json')) if checkpoints.is_dir() else []
        names = sorted(groups)
        target = self.run_dir / f'{PREVIEW_DIR}.next'
        with step('normalise.preview', group='preview', label='Bản nháp gộp từ nguồn đã chuẩn hoá: ' + ', '.join(stems)) as detail:
            detail.update(groups=groups, sources=stems)
            if not stems:
                detail['_status'] = 'skipped'
                return
            shutil.rmtree(target, ignore_errors=True)
            target.mkdir(parents=True)
            command = [sys.executable, str(ROOT / 'normalise.py'),
                       *normalise_args(target, self.destinations, settings_values()),
                       '--merge-only', '--allow-partial-sources', '--checkpoint-dir', str(checkpoints)]
            started = time.monotonic()
            with self.lock:
                if self.closed:
                    detail['_status'] = 'stopped'
                    shutil.rmtree(target, ignore_errors=True)
                    return
            code = self._run(command, '[preview]', track=True)
            if code < 0 or self.closed:  # bị dừng: bản chính thức sắp chạy, hoặc người vận hành bấm Dừng
                detail['_status'] = 'stopped'
                shutil.rmtree(target, ignore_errors=True)
                return
            products = target / 'products.jsonl'
            rows = sum(1 for line in products.open(encoding='utf-8') if line.strip()) if products.is_file() else 0
            info = {'status': 'ok' if code == 0 else 'failed', 'exitCode': code, 'groups': groups, 'sources': stems,
                    'rows': rows, 'finishedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                    'seconds': round(time.monotonic() - started, 1)}
            write_json(target / 'preview.json', info)
            final, old = self.run_dir / PREVIEW_DIR, self.run_dir / f'{PREVIEW_DIR}.old'
            shutil.rmtree(old, ignore_errors=True)
            if final.exists():
                final.rename(old)
            target.rename(final)
            shutil.rmtree(old, ignore_errors=True)
            detail.update(rows=rows, exitCode=code)
            if code:
                detail['_status'] = 'error'
            say(f'catalog.preview.done groups={",".join(names)} sources={",".join(stems)} rows={rows} exit={code}')


# VM 2 vCPU / 4 GB: mỗi Chromium ~0,8–1 GB, hai cái cùng lúc dễ bị OOM-killer. Các bước dùng trình duyệt chạy lần lượt
# (khoá giữ trong lúc chạy, không giữ khi chờ retry); nguồn HTTP (Vinpearl, Trip vé/điểm tham quan, Agoda API) vẫn song song.
# Bước có mở Chromium: Vinpearl (vé/tour qua trang có Cloudflare), Trip vé máy bay (báo giá thương gia), booking.com,
# Trip KS tìm ID (hàm find_hotels, không gắn .step) và giá phòng (price_rooms.step). Agoda dùng API nên không cần khoá.
BROWSER_STEPS = {'vinpearl', 'trip-flights', 'booking-hotels', 'find_hotels', 'trip-hotels.prices'}
_browser_lock = threading.Lock()


def browser_slot(key: str):
    return _browser_lock if key in BROWSER_STEPS else contextlib.nullcontext()


def crawl_sites(run_dir: Path, destinations: str, groups, parallel: int,
                previewer: Previewer | None = None, deadline: float | None = None) -> dict[str, int]:
    """Isolate failures per source; only dependent steps are skipped, not an entire site or run."""
    statuses: dict[str, int] = {}
    active = [(name, steps) for name, steps in groups if steps]
    finished: list[str] = []
    finished_lock = threading.Lock()

    def run_group(name: str, items) -> None:
        started, status = time.monotonic(), 'ok'
        say(f'catalog.group.start name={name}')
        try:
            for index, item in enumerate(items):
                if REC is not None:
                    REC.check_stop()
                key = getattr(item, 'step', getattr(item, '__name__', 'source')) if callable(item) else item
                limit = step_deadline(key, deadline)  # one budget for every retry of this source
                deps = graph.deps_of(key)
                dependency_failed = any(statuses.get(dep, 0) != 0 for dep in deps)
                expired = deadline is not None and time.monotonic() >= deadline
                if dependency_failed or expired:
                    if expired:
                        say(f'catalog.crawl.deadline group={name}: bỏ {key}')
                    status = 'timeout' if expired or status == 'timeout' else 'blocked'
                    statuses[key] = perr.EXIT_TIMEOUT if expired else perr.EXIT_BLOCKED
                    with step(key, group=name) as detail:
                        detail.update(_status='timeout' if expired else 'blocked',
                                      errorKind=perr.TIMEOUT if expired else perr.BLOCKED,
                                      reason='Hết hạn cào' if expired else 'Bước phụ thuộc chưa thành công',
                                      exitCode=statuses[key])
                    continue
                if callable(item):
                    try:
                        with browser_slot(key):
                            item()
                        if key in graph.SOURCE_BY_STEP:
                            statuses[key] = 0
                    except StopRequested:
                        raise
                    except Exception as exc:
                        statuses[key] = (perr.EXIT_TIMEOUT if isinstance(exc, perr.StepTimeout) else
                                         perr.EXIT_BLOCKED if isinstance(exc, perr.BlockedError) else 1)
                        status = getattr(exc, 'step_status', 'error')
                        say(f'[{name}] {key}: {type(exc).__name__}: {exc}; tiếp tục nguồn độc lập')
                else:
                    with step(key, group=name) as detail:
                        attempt = 0
                        while True:
                            with browser_slot(key):
                                if attempt == 0:  # ngân sách giờ tính từ lúc có slot trình duyệt, không tính lúc chờ
                                    limit = step_deadline(key, deadline)
                                code = (perr.EXIT_TIMEOUT if limit is not None and time.monotonic() >= limit else
                                        run_source(run_dir, key, destinations, name, deadline=limit))
                            kind = perr.classify_exit(code, list(SOURCE_TAIL.get(key, ())))
                            statuses[key] = code
                            detail['exitCode'] = code
                            if kind == 'ok':
                                break
                            plan = perr.strategy(kind, settings_values())
                            if plan['action'] == 'retry' and attempt < plan['retries']:
                                attempt += 1
                                delay = retry_note(detail, key, attempt, plan, kind, f'mã {code}')
                                if limit is not None:
                                    delay = min(delay, max(0, limit - time.monotonic()))
                                wait_or_stop(delay)
                                continue
                            if kind not in (perr.BLOCKED, perr.TIMEOUT):
                                status = 'error'
                            detail.update(_status='blocked' if kind == perr.BLOCKED else
                                          'timeout' if kind == perr.TIMEOUT else 'error', errorKind=kind)
                            if kind == perr.BLOCKED:
                                statuses[key] = perr.EXIT_BLOCKED
                            detail['sealed'] = seal_interim(run_dir, STEP_INTERIM.get(key, ()))
                            say(f'catalog.source.incomplete name={key} kind={kind}; tiếp tục nguồn độc lập')
                            break
                if previewer is not None and STEP_INTERIM.get(key):
                    with finished_lock:
                        last = index == len(items) - 1 and len(finished) == len(active) - 1
                    previewer.source_done(name, STEP_INTERIM.get(key, ()), merge=not last)
        finally:
            with finished_lock:
                finished.append(name)
                last = len(finished) == len(active)
            if previewer is not None:
                previewer.group_done(name, status, merge=not last)
            say(f'catalog.group.done name={name} status={status} seconds={round(time.monotonic() - started)}')

    try:
        with ThreadPoolExecutor(max_workers=parallel, thread_name_prefix='site') as pool:
            futures = [pool.submit(run_group, name, items) for name, items in active]
            for future in futures:
                future.result()  # never silently discard worker exceptions
    finally:
        if previewer is not None:
            previewer.finish(keep=False)
    return statuses


def normalise_args(data_dir: Path, destinations: str | None, values: dict, stage: bool = True) -> list[str]:
    """Tham số normalise.py của lượt (bản chính thức, bản nháp, chuẩn hoá theo nguồn dùng chung).
    `stage=False`: không kèm báo cáo/ảnh chụp của bước gộp (chuẩn hoá một nguồn tự đặt --stage-dir riêng)."""
    args = ['--data-dir', str(data_dir), '--rooms-per-hotel', str(values['normalise.roomsPerHotel']),
            '--flights-per-route', str(values['tripFlights.flightsPerRoute']),
            '--keep-unsellable', '--keep-missing-coordinates',
            '--keep-location-warnings', '--keep-price-outliers',
            *(['--report-json', str(data_dir / 'normalise_report.json'),
               '--stage-dir', str(data_dir / 'normalise_stages')] if stage else []),
            '--max-error-percent', f"{values['normalise.maxErrorPercent']:g}"]
    return args + (['--destinations', destinations] if destinations else ['--no-plan'])


def normalise_failed_step(stage_dir: Path) -> dict:
    """Bước normalize lỗi (hoặc còn "running" vì tiến trình chết) theo `<stage-dir>/steps.json` của normalise.StepClock."""
    steps = (read_json(stage_dir / 'steps.json', {}) or {}).get('steps') or []
    return next((s for s in reversed(steps) if s.get('status') in ('error', 'running')), {})


def source_minimums(run_dir: Path) -> dict[str, int]:
    values = settings_values()
    limit = values.get('quality.maxDropPercent', 0)
    if not limit:
        return {}
    mode = (REC.data.get('mode') if REC else run_dir.name.split('-')[0])
    for path in run_dirs(run_dir.parent):
        if path == run_dir or path.name > run_dir.name:
            continue
        data = read_json(path / 'run.json', {}) or {}
        if data.get('mode') != mode or data.get('status') not in ('ok', 'partial'):
            continue
        if any(data.get('settings', {}).get(key) != values.get(key) for key in QUALITY_KEYS):
            continue
        report = read_json(path / 'normalise_report.json', {}) or {}
        counts = report.get('recordsRead') or {}
        return {stem: max(1, int(count * (100 - limit) / 100)) for stem, count in counts.items()
                if count and stem not in (report.get('excludedSources') or {})}
    return {}


def normalize(run_dir: Path, destinations: str | None, merge_only: bool = False) -> Path:
    try:
        # dùng lại checkpoint của nguồn đã chuẩn hoá khi bước cào xong (Previewer); chỉ ánh xạ nguồn còn thiếu/cũ/lỗi.
        # merge_only (chạy lại từ bước gộp, CP6): chỉ gộp từ checkpoint đã có, không đọc interim.
        extra = ['--allow-partial-sources', *(['--merge-only'] if merge_only else ['--reuse-checkpoints'])]
        minima = source_minimums(run_dir)
        if minima:
            extra += ['--source-minimums', json.dumps(minima)]
        code = normalise_main([*normalise_args(run_dir, destinations, settings_values()), *extra])
    except Exception as exc:
        name = normalise_failed_step(run_dir / 'normalise_stages').get('name') or '?'
        # normalize là tính toán thuần (không mạng): lỗi của nó là lỗi code/dữ liệu, không thử lại
        raise perr.CodeError(f"normalise lỗi ở bước '{name}': {type(exc).__name__}: {exc}") from exc
    if code:
        raise RuntimeError('normalise.py không tạo catalog hợp lệ')
    products = run_dir / 'products.jsonl'
    if not products.is_file():
        raise RuntimeError('Thiếu products.jsonl của lượt cào mới')
    return products


def required_variants(values: dict) -> set:
    """Nhóm sản phẩm bắt buộc có ở lượt full, theo các nguồn đang bật."""
    need = set()
    if values['sources.tripFlights']:
        need |= {('flight', 'route'), ('flight', 'flight')}
    if values['sources.tripAttractions'] or values['sources.vinpearl']:
        need.add(('attraction', None))
    if values['sources.vinpearl']:
        need.add(('combo', None))
    if values['sources.vinpearl'] or values['sources.booking'] or values['sources.tripHotels']:
        need |= {('hotel', 'property'), ('hotel', 'room')}
    return need


def validate_run(products_path: Path, coverage_path: Path | None, *, full: bool,
                 required: set | None = None, trip: bool = True) -> dict:
    checked = checked_trip_hotels(coverage_path) if trip else set()
    if trip and not checked:
        raise ValueError('Chưa có khách sạn Trip hoàn tất mọi mốc ngày')
    with products_path.open(encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    if not rows or any(tuple(row) != PRODUCT_FIELDS for row in rows):
        raise ValueError('Catalog thiếu 13 trường đúng thứ tự')
    validate_catalog(rows)
    variants = {(row['taxonomy'], row['attributes'].get('level')) for row in rows}
    need = REQUIRED if required is None else required
    if full and not need <= variants:
        raise ValueError(f'Thiếu nhóm sản phẩm: {need - variants}')
    return {'products': len(rows), 'completedHotels': len(checked),
            'variants': sorted(f'{a}/{b or "-"}' for a, b in variants)}


QUALITY_KEYS = ('scope.destinations', 'sources.vinpearl', 'sources.tripFlights', 'sources.tripAttractions',
                'sources.booking', 'sources.agoda', 'sources.tripHotels')


def quality_drop_check(products: int, mode: str, values: dict, run_dir: Path) -> dict:
    """Chặn nạp DB khi catalog giảm quá `quality.maxDropPercent` so với lượt thành công gần nhất cùng chế độ, cùng phạm vi
    điểm đến và cùng bộ nguồn (khác phạm vi thì số dòng khác là bình thường, không so)."""
    limit = values.get('quality.maxDropPercent', 0)
    if not limit:
        return {}
    for path in run_dirs(run_dir.parent):
        if path == run_dir or not path.name.startswith(f'{mode}-') or path.name > run_dir.name:
            continue
        data = read_json(path / 'run.json', {}) or {}
        previous = ((data.get('counts') or {}).get('catalog') or {}).get('products')
        if data.get('status') not in ('ok', 'partial') or not previous:
            continue
        if any((data.get('settings') or {}).get(key) != values.get(key) for key in QUALITY_KEYS):
            continue
        dropped = round(100 * (previous - products) / previous)
        if dropped > limit:
            raise perr.QualityGateError(f'Không nạp DB: catalog {products} dòng, lượt {path.name} có {previous} '
                                        f'(giảm {dropped}% > {limit}%). Kiểm nguồn bị chặn/lỗi, hoặc tăng ngưỡng ở Cấu hình.')
        return {'comparedWith': path.name, 'previousProducts': previous, 'dropPercent': max(dropped, 0)}
    return {}


def index_settings(db_target: str):
    """Cấu hình bước index: cùng cặp Postgres/Weaviate với đích nạp, theo quy ước `TARGETS` của daily.py.

    Đích cloud đọc catalog bằng CLOUD_DATABASE_URL (thiếu thì CLOUD_SEED_DATABASE_URL) và ghi vào CLOUD_WEAVIATE_URL
    với CLOUD_WEAVIATE_API_KEY; đích local dùng DATABASE_URL (thiếu thì SEED_DATABASE_URL) và WEAVIATE_URL như backend.
    Kiểm trước khi cào để VM cấu hình thiếu không cào hàng giờ rồi mới lỗi ở bước cuối.
    """
    repo_root = str(ROOT.parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from src.backend.app.core.config import Settings
    from src.backend.app.infrastructure.vectors.weaviate_store import normalize_weaviate_url
    if db_target == 'cloud':
        values = {'database_url': os.environ.get('CLOUD_DATABASE_URL') or os.environ['CLOUD_SEED_DATABASE_URL'],
                  'weaviate_url': os.environ.get('CLOUD_WEAVIATE_URL', ''),
                  'weaviate_api_key': os.environ.get('CLOUD_WEAVIATE_API_KEY', '')}
        required = {'CLOUD_WEAVIATE_URL': values['weaviate_url']}
    else:
        values = {'database_url': os.environ.get('DATABASE_URL') or os.environ['SEED_DATABASE_URL']}
        required = {}
    settings = Settings(**values)
    # e5-small chạy trong image (PRD FR-SRC-02): bước index không cần khoá embedding nào.
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f'Thiếu biến cho bước index: {", ".join(missing)}')
    normalize_weaviate_url(settings.weaviate_url)
    return settings


def index_catalog(settings, detail_path: Path | None = None) -> dict:
    # Đọc lại đúng DB vừa ghi, ghi vào Weaviate của cùng đích; runtime API vẫn dùng role chỉ đọc của nó.
    # detail_path: text đem embed, hash, hành động và vài chiều đầu của vector từng sản phẩm, cho monitor.
    from src.backend.jobs.embed_products import run
    print("catalog.index.start", flush=True)
    report = run(settings=settings, detail_path=detail_path)
    print("catalog.index.complete " + json.dumps(report, ensure_ascii=False), flush=True)
    return report


def check_local_only(db_target: str, db_url: str, index_config) -> None:
    """`CATALOG_LOCAL_ONLY=1` (local_crawl.sh): chỉ cho ghi vào Postgres/Weaviate trên máy này và không đụng database
    `vota` hay collection `Product` mà backend local đang dùng. Kiểm trước khi cào để lượt thử không ghi nhầm lên staging."""
    if os.environ.get('CATALOG_LOCAL_ONLY') != '1':
        return
    problems = []
    if db_target != 'local':
        problems.append(f'DB_TARGET={db_target} (cần local)')
    targets = [('SEED_DATABASE_URL', db_url)]
    if index_config is not None:
        targets += [('database đọc cho index', index_config.database_url), ('WEAVIATE_URL', index_config.weaviate_url)]
    for name, url in targets:
        parsed = urlparse(url if '://' in url else f'http://{url}')
        if parsed.hostname not in LOCAL_HOSTS:
            problems.append(f'{name} trỏ tới {parsed.hostname or "?"} (không phải localhost)')
        if name != 'WEAVIATE_URL' and parsed.path.lstrip('/') in ('', 'vota'):
            problems.append(f'{name} dùng database "{parsed.path.lstrip("/") or "mặc định"}" của backend local')
    if index_config is not None and index_config.weaviate_collection in ('Product', 'ProductE5Small'):
        problems.append(f'WEAVIATE_COLLECTION={index_config.weaviate_collection} là collection của backend local')
    if problems:
        raise ValueError('Chế độ local chặn lượt này: ' + '; '.join(problems))


def lock_busy(state_dir: Path) -> bool:
    path = state_dir / 'fresh_catalog.lock'
    if not path.exists():
        return False
    with path.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(handle, fcntl.LOCK_UN)
    return False


def print_status(values: dict, state_dir: Path) -> None:
    targets_file = state_dir / 'trip_targets.json'
    upcoming = fresh_settings.next_run(values, state_dir)
    print(f'Next run: {fresh_settings.auto_mode(values, state_dir)}; known Trip IDs: {len(saved_targets(targets_file))}; '
          f'daily batch: {values["tripHotels.dailyHotels"]}; '
          f'initial/city: {values["tripHotels.initialPerCity"]}; '
          f'new/city: {values["tripHotels.newPerCity"]}; '
          f'parallel sites (full): {values["crawl.parallelSites"]}')
    print('Schedule: ' + (f'{upcoming["mode"]} at {upcoming["at"]}' if upcoming else 'off'))
    backlog = index_backlog.pending(state_dir / 'index_pending.json')
    if backlog:
        print('Index backlog: ' + json.dumps(backlog), flush=True)
    running = read_json(state_dir / 'running.json')
    if running and lock_busy(state_dir):
        print(f'Running: {running.get("runId")} since {running.get("startedAt")} steps={running.get("steps")}')


def run_job(mode: str, trigger: str | None = None, run_id: str | None = None, from_step: str | None = None,
            source: str | None = None) -> int:
    global CFG, REC
    state_dir, run_root = dirs()
    state_dir.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)
    values = fresh_settings.load(state_dir)
    if mode == 'status':
        print_status(values, state_dir)
        return 0
    def scheduled():
        selected, reason = fresh_settings.scheduled_mode(values, state_dir)
        if selected is None and values['schedule.enabled'] and index_backlog.due(state_dir / 'index_pending.json'):
            return 'index', 'index backlog retry is due'
        return selected, reason

    if mode == 'due':
        chosen, reason = (None, 'đang có lượt chạy') if lock_busy(state_dir) else scheduled()
        print(chosen or '', flush=True)
        print(f'catalog.due {chosen or "-"}: {reason}', file=sys.stderr, flush=True)
        return 0
    # An idle cron tick needs neither DB credentials nor an index connection.
    if mode == 'tick' and (lock_busy(state_dir) or scheduled()[0] is None):
        check_sla(state_dir, run_root, values)
        return 0
    trigger = trigger or os.environ.get('CATALOG_TRIGGER') or 'manual'
    db_target = os.environ.get('DB_TARGET', 'local')
    key = 'SEED_DATABASE_URL' if db_target == 'local' else 'CLOUD_SEED_DATABASE_URL'
    if db_target not in ('local', 'cloud') or not os.environ.get(key):
        raise ValueError(f'Cần DB_TARGET=local/cloud và {key}')
    try:
        index_config = index_settings(db_target)
    except ValueError as exc:
        index_config = None
        say(f'catalog.index.deferred: {exc}; cào và nạp DB vẫn tiếp tục')
    check_local_only(db_target, os.environ[key], index_config)
    lock_path = state_dir / 'fresh_catalog.lock'
    with lock_path.open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if mode == 'tick':
                return 0
            raise RuntimeError('Đã có job catalog khác đang chạy') from None
        if mode == 'tick':
            selected, reason = scheduled()
            if selected is None:
                print(f'catalog.schedule.skip: {reason}', flush=True)
                return 0
            trigger = 'schedule'
        elif mode != 'resume':
            selected = fresh_settings.auto_mode(values, state_dir) if mode == 'auto' else mode
        if mode == 'resume':
            if not run_id or not re.match(r'^(full|daily|index)-\d{8}T\d{6}Z-\d+$', run_id) or not (run_root / run_id).is_dir():
                raise ValueError(f'Không có lượt {run_id} trong {run_root}')
            run_dir = run_root / run_id
            label = f'{from_step}:{source}' if from_step == graph.RECRAWL else from_step  # vd. crawl:booking
            recorder = RunRecorder.resume(run_dir, state_dir, from_step=label, trigger=trigger)
            selected = recorder.data['mode']
            values = {**values, **recorder.data.get('settings', {})}  # cấu hình của chính lượt đó
        else:
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            run_id = f'{selected}-{stamp}-{os.getpid()}'
            run_dir = run_root / run_id
            if trigger == 'schedule' and selected != 'index':
                fresh_settings.mark_scheduled(state_dir, run_id)
            recorder = RunRecorder(run_dir, state_dir, run_id=run_id, mode=selected, trigger=trigger, settings=values)
        # Monitor chỉnh tốc độ/tạm dừng qua file này; tiến trình con crawl.py nhận thêm CRAWL_LIVE_KEY của nguồn.
        os.environ.update(CRAWL_LIVE_FILE=str(state_dir / live_control.FILE_NAME), CRAWL_RUN_ID=run_id,
                          CRAWL_LIVE_KEY='tripHotels')
        CFG, REC = values, recorder.start()
        status, code, error = 'failed', EXIT_PARTIAL, None
        try:
            if mode == 'resume':
                print(f'Resume {run_id} from {from_step}' + (f' source={source}' if source else '') + f': {run_dir}',
                      flush=True)
                code = resume_run(recorder, values, state_dir, run_dir, from_step, os.environ[key], index_config,
                                  source=source)
            else:
                removed = prune_runs(run_root, values['runs.keep'], protect=run_dir)
                print(f'Run {selected}: {run_dir}' + (f' (xoá lượt cũ: {", ".join(removed)})' if removed else ''), flush=True)
                code = execute(selected, recorder, values, state_dir, run_dir, os.environ[key], index_config)
            recorder.check_stop()
            incomplete = recorder.data.get('incompleteSources') or recorder.data['counts'].get('index', {}).get('deferred')
            status = 'ok' if code == 0 and not incomplete else 'partial'
            return code
        except BaseException as exc:
            error = f'{type(exc).__name__}: {exc}'
            if not isinstance(exc, (StopRequested, KeyboardInterrupt)):
                recorder.data['errorKind'] = perr.classify_exception(exc)
                # vào job.log: sau recorder.finish() stdout/stderr đã trả về luồng gốc nên traceback ở ngoài sẽ mất
                print('catalog.failed traceback:\n' + traceback.format_exc(), file=sys.stderr, flush=True)
            if isinstance(exc, StopRequested) or recorder.stop_event.is_set():
                status, code = 'stopped', EXIT_STOPPED
                if not isinstance(exc, StopRequested):
                    raise StopRequested(str(exc)) from exc
            raise
        finally:
            recorder.finish(status, code, error)
            CFG = REC = None
            notify_finished(recorder.data, run_dir, state_dir, values)
            for name in ('CRAWL_LIVE_FILE', 'CRAWL_RUN_ID', 'CRAWL_LIVE_KEY'):
                os.environ.pop(name, None)


def execute(selected: str, rec: RunRecorder, values: dict, state_dir: Path, run_dir: Path,
            db_url: str, index_config) -> int:
    maintenance_error = False
    try:
        with step('maintain', label=graph.BY_ID['maintain'].title) as detail:
            maintenance = with_retry('maintain', lambda: maintain_catalog(db_url), detail)
            detail.update(maintenance)
        rec.set_counts(maintain=maintenance)
    except StopRequested:
        raise
    except Exception as exc:
        maintenance_error = True
        say(f'catalog.maintain.failed {type(exc).__name__}: {exc}; vẫn lưu dữ liệu cào để chạy lại')
    if selected == 'index':
        run_index(rec, index_config)
        return EXIT_PARTIAL if maintenance_error else 0
    try:
        result = crawl_and_load(selected, rec, values, state_dir, run_dir, db_url, index_config)
        return EXIT_PARTIAL if maintenance_error else result
    finally:
        failed = sys.exc_info()[0] is not None
        if not rec.stop_event.is_set():  # dừng tay thì bỏ index; lượt sau index lại
            try:
                run_index(rec, index_config)
            except Exception as exc:
                print(f"catalog.index.failed {type(exc).__name__}: {exc}; retry mode=index", file=sys.stderr, flush=True)
                if not failed:
                    raise RuntimeError("Index thất bại; DB đã giữ dữ liệu mới. Chạy lại mode=index") from exc


def run_index(rec: RunRecorder, index_config) -> None:
    with step('index', label=graph.BY_ID['index'].title) as detail:
        if index_config is None:
            target = os.environ.get('DB_TARGET', 'local')
            index_config = index_settings(target)
            key = 'SEED_DATABASE_URL' if target == 'local' else 'CLOUD_SEED_DATABASE_URL'
            check_local_only(target, os.environ[key], index_config)
        report = index_backlog.guarded_index(rec.state_dir / 'index_pending.json',
            lambda: with_retry('index', lambda: index_catalog(index_config, rec.run_dir / 'index_detail.jsonl'), detail))
        if report.get('deferred'):
            detail['_status'] = 'partial'
            say(f"catalog.index.deferred reason={report['reason']} retryAfter={report['retryAfter']}; DB retained")
        detail.update(report or {})
    rec.set_counts(index=report)
    (rec.run_dir / 'index_report.json').write_text(json.dumps(report or {}, ensure_ascii=False, indent=1),
                                                   encoding='utf-8')


RUN_TARGETS = 'trip_targets.run.json'  # ID khách sạn Trip của lượt: cào lại riêng bước giá phòng cần danh sách này (P4)


def save_run_targets(run_dir: Path, targets: list[dict]) -> None:
    write_json(run_dir / RUN_TARGETS, {'hotels': targets})


def crawl_trip_prices(run_dir: Path, targets: list[dict], values: dict, deadline: float | None) -> tuple[list, dict]:
    """Bước `trip-hotels.prices`: thông tin + giá phòng khách sạn Trip. Giá chỉ ghi khi cả bước xong: quá hạn giờ thì
    ném perr.StepTimeout và lượt không có khách sạn Trip mới."""
    options = LiveOptions(
        http_workers=values['tripHotels.httpWorkers'], price_workers=values['tripHotels.priceTabs'],
        delay_min=values['tripHotels.delayMin'], delay_max=values['tripHotels.delayMax'],
        offsets=tuple(values['tripHotels.priceOffsets']))
    with step('trip-hotels.prices', group='trip', label=graph.STEP_TITLES['trip-hotels.prices']) as detail:
        records, coverage = asyncio.run(run_cancellable(crawl(Paths(run_dir).ensure(), targets, options),
                                                        step_deadline('trip-hotels.prices', deadline)))
        detail.update(requested=len(targets), completed=len(records),
                      unpricedHotelDates=len((coverage or {}).get('unpricedHotelDates') or []))
    return records, coverage


def crawl_and_load(selected: str, rec: RunRecorder, values: dict, state_dir: Path, run_dir: Path, db_url: str,
                   index_config=None) -> int:
    targets_file = state_dir / 'trip_targets.json'
    schedule_file = state_dir / 'trip_schedule.json'
    coverage_path = run_dir / 'trip_price_coverage.json'
    started_at = rec.data['startedAt']
    trip_on = values['sources.tripHotels']
    crawl_deadline = deadline_after(float(values['crawl.maxHours']) * 3600)  # hạn giờ cả phần cào (P4)
    trip: dict = {'targets': [], 'discovery': [], 'records': [], 'coverage': None, 'timedOut': False}
    statuses: dict[str, int] = {}

    def price_rooms() -> None:
        try:
            trip['records'], trip['coverage'] = crawl_trip_prices(run_dir, trip['targets'], values, crawl_deadline)
        except perr.StepTimeout:
            trip['timedOut'] = True  # lượt này không có khách sạn Trip mới; các nguồn khác vẫn nạp
            statuses['trip-hotels.prices'] = perr.EXIT_TIMEOUT
            raise
    price_rooms.step = 'trip-hotels.prices'  # crawl_sites chuẩn hoá file của bước này ngay khi nó xong (P1)

    if selected == 'full':
        destinations = values['scope.destinations']
        cities = trip_cities(values)
        known = {row['trip_hotel_id'] for row in saved_targets(targets_file)}
        new_per_city = values['tripHotels.newPerCity'] if known else values['tripHotels.initialPerCity']

        def find_hotels() -> None:
            with step('trip-hotels.discover', group='trip', label=graph.STEP_TITLES['trip-hotels.discover']) as detail:
                try:
                    trip['targets'], trip['discovery'] = asyncio.run(run_cancellable(discover(
                        Paths(run_dir).ensure(), cities, values['tripHotels.scanPerCity'], new_per_city, known),
                        step_deadline('trip-hotels.discover', crawl_deadline)))
                except perr.StepTimeout:
                    statuses['trip-hotels.discover'] = perr.EXIT_TIMEOUT
                    raise
                save_run_targets(run_dir, trip['targets'])
                detail.update(cities=[c.name for c in cities], selected=len(trip['targets']),
                              perCity=trip['discovery'])
                if not trip['targets']:
                    statuses['trip-hotels.discover'] = perr.EXIT_BLOCKED
                    raise perr.BlockedError('Trip không trả ID khách sạn nào (trang danh sách hiện 0 nơi lưu trú; '
                                            'nghi bị chặn) — bỏ bước hỏi giá khách sạn Trip')

        groups = []
        for name, sources in SITE_GROUPS:
            steps = [s for s in sources if values[SOURCE_SWITCH[s]]]
            if name == 'trip' and trip_on and cities:
                steps = [*steps, find_hotels, price_rooms]
            groups.append((name, tuple(steps)))
        previewer = Previewer(run_dir, destinations, db_url, index_config) if values['normalise.preview'] else None
        statuses.update(crawl_sites(run_dir, destinations, groups, values['crawl.parallelSites'], previewer,
                                    crawl_deadline))
        rec.check_stop()
        # tìm ID bị chặn / quá giờ, hoặc hỏi giá quá giờ: lượt này không có khách sạn Trip
        trip_used = trip_on and bool(cities) and bool(trip['targets']) and not trip['timedOut']
    else:
        destinations = None
        trip_used = trip_on
        if trip_on:
            known = saved_targets(targets_file)
            if not known:
                raise RuntimeError('Chưa có ID Trip; chạy --full trước')
            trip['targets'] = select_batch(known, read_state(schedule_file), values['tripHotels.dailyHotels'])
            save_run_targets(run_dir, trip['targets'])
            price_rooms()
        else:
            print('Khách sạn Trip đang tắt: lượt hằng ngày chỉ bảo trì DB và index.', flush=True)
            return 0
    rec.check_stop()
    records, coverage = trip['records'], trip['coverage']
    if trip_used:
        print(f'Trip complete: {len(records)}/{len(trip["targets"])}', flush=True)
        rec.set_counts(trip={'requested': len(trip['targets']), 'completed': len(records),
                             'unpricedHotelDates': len((coverage or {}).get('unpricedHotelDates') or [])})
        if not records:
            write_state(schedule_file, record_batch(trip['targets'], coverage, read_state(schedule_file),
                                                    datetime.now(timezone.utc).isoformat()))
            if selected == 'daily':
                raise RuntimeError('Không có khách sạn Trip đủ JSON giá ở mọi mốc ngày')
            statuses['trip-hotels.prices'] = 1
            trip_used = False
            say('catalog.trip.incomplete: không có khách sạn đủ giá; giữ catalog cũ, nạp các nguồn khác')
    rec.data['sourceStatuses'] = statuses
    rec.save()
    products = normalise_step(run_dir, destinations)
    summary = validate_step(rec, values, selected, run_dir, products, coverage_path if trip_used else None)
    rec.check_stop()
    counts = db_step(rec, run_dir, products, coverage_path if trip_used else None, db_url)
    if selected == 'full':
        if trip_used:
            merge_targets(targets_file, trip['targets'])
        (state_dir / fresh_settings.FULL_MARKER).write_text(started_at + '\n', encoding='utf-8')
    if trip_used:
        write_state(schedule_file, record_batch(trip['targets'], coverage, read_state(schedule_file),
                                                datetime.now(timezone.utc).isoformat()))
    print(json.dumps({'mode': selected, 'discovery': trip['discovery'], 'sources': statuses,
                      'catalog': summary, 'database': counts}, ensure_ascii=False, default=str), flush=True)
    unpriced = (coverage or {}).get('unpricedHotelDates') if trip_used else None
    # A committed partial catalog is usable. Keep warnings in run.json, not a fatal process exit.
    rec.data['incompleteSources'] = incomplete_sources(rec, run_dir)
    if unpriced:
        rec.data['incompleteSources']['trip-hotels.prices'] = 'unpriced dates'
    rec.save()
    return 0


def normalise_step(run_dir: Path, destinations: str | None, merge_only: bool = False) -> Path:
    with step('normalise', label=graph.BY_ID['normalise'].title + (' (chỉ gộp từ checkpoint)' if merge_only else '')) as detail:
        products = normalize(run_dir, destinations, merge_only)
        detail.update(read_json(run_dir / 'normalise_report.json', {}) or {})
    return products


def incomplete_sources(rec: RunRecorder, run_dir: Path) -> dict[str, object]:
    latest = {entry['name']: entry for entry in rec.data.get('steps', [])}
    bad = {name: code for name, code in rec.data.get('sourceStatuses', {}).items() if code}
    for name, entry in latest.items():
        if name in graph.SOURCE_BY_STEP:
            if entry.get('status') in ('error', 'timeout', 'blocked', 'stopped'):
                bad[name] = entry['status']
    report = read_json(run_dir / 'normalise_report.json', {}) or {}
    bad.update(report.get('excludedSources') or {})
    return bad


def available_requirements(values: dict, failures: dict) -> set:
    effective = dict(values)
    for source in graph.SOURCES:
        if any(name in failures for name in (*source.steps, *source.interim)):
            effective[source.setting] = False
    return required_variants(effective)


def validate_step(rec: RunRecorder, values: dict, selected: str, run_dir: Path, products: Path,
                  coverage: Path | None) -> dict:
    with step('validate', label=graph.BY_ID['validate'].title) as detail:
        try:
            summary = validate_run(products, coverage, full=selected == 'full', required=available_requirements(values, incomplete_sources(rec, run_dir)),
                                   trip=coverage is not None)
        except ValueError as exc:
            raise perr.QualityGateError(f'Không nạp DB: {exc}') from exc
        detail.update(summary)
        failures = incomplete_sources(rec, run_dir)
        detail['incompleteSources'] = failures
        # Different source sets have different totals; per-source gates still apply in normalize.
        if summary.get('products') is not None and not failures:
            detail.update(quality_drop_check(summary['products'], selected, values, run_dir))
    rec.set_counts(catalog=summary)
    return summary


def db_step(rec: RunRecorder, run_dir: Path, products: Path, coverage: Path | None, db_url: str) -> dict:
    with step('db', label=graph.BY_ID['db'].title) as detail:
        counts = with_retry('db', lambda: load_into_db(products, coverage, db_url, ROOT,
                                                       report_path=run_dir / 'db_load.jsonl'), detail)
        detail.update(counts or {})
    rec.set_counts(database=counts)
    return counts


# CP6 (docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md): chạy lại một lượt đã kết thúc từ một bước sau cào, dùng lại
# raw, interim, checkpoint và products.jsonl của chính lượt đó. Tương đương nút "Clear" task của Airflow. Bước chạy tiếp
# sau bước được chọn suy từ `deps` trong pipeline_graph.py (resume_plan).
RESUME_STEPS = graph.RESUME_STEPS


def recrawl_source(rec: RunRecorder, values: dict, run_dir: Path, key: str) -> dict[str, int]:
    """P4b: cào lại riêng nguồn `key` vào thư mục của chính lượt (crawl.py tiếp tục từ tiến độ đã lưu nếu có), cùng thử
    lại / bị chặn / hạn giờ như lượt thường. Khách sạn Trip: chỉ bước giá phòng, với ID đã lưu ở trip_targets.run.json."""
    src = graph.SOURCE_BY_KEY.get(key)
    if src is None:
        raise ValueError(f'Nguồn phải là một trong: {", ".join(graph.SOURCE_BY_KEY)}')
    if rec.data['mode'] not in src.modes:
        raise ValueError(f'Lượt {rec.data["mode"]} không cào nguồn {key}')
    deadline = deadline_after(float(values['crawl.maxHours']) * 3600)
    statuses: dict[str, int] = {}
    if src.in_process:
        targets = (read_json(run_dir / RUN_TARGETS, {}) or {}).get('hotels') or []
        if not targets:
            raise ValueError(f'Lượt không có {RUN_TARGETS} (danh sách ID khách sạn Trip); không cào lại được giá phòng')

        def prices() -> None:
            try:
                crawl_trip_prices(run_dir, targets, values, deadline)
            except perr.StepTimeout:
                statuses['trip-hotels.prices'] = perr.EXIT_TIMEOUT  # crawl_sites chỉ ghi mã của bước crawl.py
                raise
        prices.step = 'trip-hotels.prices'
        steps: tuple = (prices,)
    else:
        steps = src.steps
    say(f'catalog.recrawl source={key} steps={",".join(getattr(s, "step", s) for s in steps)}')
    return {**crawl_sites(run_dir, values['scope.destinations'], [(src.site, steps)], 1, None, deadline), **statuses}


def resume_run(rec: RunRecorder, values: dict, state_dir: Path, run_dir: Path, from_step: str, db_url: str,
               index_config, source: str | None = None) -> int:
    """Chạy lại từ `from_step`. Không cào lại, trừ `crawl` (P4b: cào lại riêng nguồn `source` rồi chạy tiếp mọi bước sau
    cào, dùng lại checkpoint của nguồn khác). Không cập nhật trạng thái xoay vòng khách sạn Trip. Khách sạn Trip vẫn chỉ
    nạp khi lượt có `trip_price_coverage.json`."""
    plan = graph.resume_plan(from_step)  # ValueError nếu không chạy lại được từ bước này
    selected = rec.data['mode']
    if selected == 'index' and from_step != 'index':
        raise ValueError('Lượt index chỉ chạy lại được bước index')
    if (from_step == graph.RECRAWL) != bool(source):
        raise ValueError('--source chỉ dùng và bắt buộc với --from crawl')
    say(f'catalog.resume run={rec.data["id"]} from={from_step}' + (f' source={source}' if source else ''))
    products = run_dir / 'products.jsonl'
    statuses: dict[str, int] = {}
    try:
        if graph.RECRAWL in plan:
            statuses = recrawl_source(rec, values, run_dir, source)
            rec.data.setdefault('sourceStatuses', {}).update(statuses)
            rec.save()
            rec.check_stop()
        coverage = run_dir / 'trip_price_coverage.json'  # cào lại khách sạn Trip ghi lại file này
        coverage = coverage if coverage.is_file() else None
        if 'normalise' in plan:
            destinations = values['scope.destinations'] if selected == 'full' else None
            products = normalise_step(run_dir, destinations, merge_only=from_step == 'merge')
        elif 'db' in plan and not products.is_file():
            raise ValueError('Lượt chưa có products.jsonl; chạy lại từ normalise')
        if selected == 'full' and any(name in incomplete_sources(rec, run_dir)
                                      for name in ('trip_hotels', 'trip-hotels.prices', 'trip-hotels.discover')):
            coverage = None  # exclude the failed source on resume just as on the original full run
        if 'validate' in plan:
            validate_step(rec, values, selected, run_dir, products, coverage)
            rec.check_stop()
        if 'db' in plan:
            db_step(rec, run_dir, products, coverage, db_url)
            if selected == 'full':
                (state_dir / fresh_settings.FULL_MARKER).write_text(rec.data['startedAt'] + '\n', encoding='utf-8')
    finally:
        if not rec.stop_event.is_set():
            run_index(rec, index_config)
    return EXIT_PARTIAL if incomplete_sources(rec, run_dir) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', nargs='?', choices=('auto', 'full', 'daily', 'status', 'index', 'due', 'tick', 'resume'),
                    default='auto')
    ap.add_argument('run_id', nargs='?', help='resume: mã lượt cần chạy lại (vd. full-20260928T080824Z-245196)')
    ap.add_argument('--from', dest='from_step', choices=RESUME_STEPS, default=None,
                    help='resume: chạy lại từ bước này (dùng lại dữ liệu của lượt; crawl = cào lại một nguồn)')
    ap.add_argument('--source', choices=tuple(graph.SOURCE_BY_KEY), default=None,
                    help='resume --from crawl: nguồn cần cào lại (vd. booking)')
    ap.add_argument('--trigger', choices=('manual', 'schedule', 'monitor', 'cron'), default=None,
                    help='ai khởi chạy lượt (mặc định CATALOG_TRIGGER hoặc manual)')
    ap.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.mode == 'resume' and not (args.run_id and args.from_step):
        ap.error('resume cần <mã lượt> và --from ' + '|'.join(RESUME_STEPS))
    if args.mode == 'resume' and (args.from_step == graph.RECRAWL) != bool(args.source):
        ap.error('--source chỉ dùng và bắt buộc với --from crawl')
    try:
        if not args.worker and args.mode not in ('status', 'due'):
            from pipeline_runtime import supervise
            state, runs = dirs()
            values = fresh_settings.load(state)
            seconds = values['timeout.processing'] * 60
            command = [sys.executable, str(Path(__file__).resolve()), *(argv if argv is not None else sys.argv[1:]), '--worker']
            limits = {name: seconds for name in ('maintain', 'normalise', 'normalise.source',
                       'normalise.preview', 'validate', 'db', 'index', 'stream.db.batch', 'stream.index.batch',
                       'stream.normalise.batch', 'stream.merge.batch')}
            limits.update({name: values[key] * 60 + 15 for name, key in graph.STEP_TIMEOUT.items() if values[key]})
            return supervise(command, state, runs, max_seconds=values['run.maxHours'] * 3600, step_seconds=limits)
        if args.mode == 'resume':
            return run_job('resume', args.trigger, run_id=args.run_id, from_step=args.from_step, source=args.source)
        return run_job(args.mode, args.trigger)
    except StopRequested as exc:
        print(f'Fresh catalog stopped: {exc}', file=sys.stderr)
        return EXIT_STOPPED
    except (RuntimeError, ValueError, OSError) as exc:
        print(f'Fresh catalog failed: {exc}', file=sys.stderr)
        return EXIT_PARTIAL


if __name__ == '__main__':
    raise SystemExit(main())
