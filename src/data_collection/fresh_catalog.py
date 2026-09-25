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
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import fresh_settings
from collectors.common import Paths
from collectors.plan import select_destinations
from collectors.trip_live import LiveOptions, crawl, discover
from fresh_catalog_db import checked_trip_hotels, load_into_db, maintain_catalog
from fresh_catalog_schedule import read_state, read_targets, record_batch, select_batch, write_state
from fresh_run_log import RunRecorder, StopRequested, prune_runs, read_json
from normalise import PRODUCT_FIELDS, main as normalise_main

ROOT = Path(__file__).resolve().parent
EXIT_PARTIAL = 3   # lỗi, hoặc còn ngày Trip chưa có giá / có nguồn bị chặn
EXIT_STOPPED = 5   # người vận hành bấm Dừng
# Lượt full: mỗi site một nhóm. Các nhóm chạy song song (crawl.parallelSites), trong một nhóm vẫn tuần tự như trước
# nên số request đồng thời tới từng site không đổi. Nhóm trip còn tìm ID khách sạn trước và hỏi giá phòng sau.
SITE_GROUPS = (('trip', ('trip-flights', 'trip-attractions')), ('vinpearl', ('vinpearl',)),
               ('booking', ('booking-hotels',)), ('agoda', ('agoda-hotels',)))
SOURCE_SWITCH = {'trip-flights': 'sources.tripFlights', 'trip-attractions': 'sources.tripAttractions',
                 'vinpearl': 'sources.vinpearl', 'booking-hotels': 'sources.booking', 'agoda-hotels': 'sources.agoda'}
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
    command = [sys.executable, str(ROOT / 'crawl.py')]
    if values['log.verbose']:
        command.append('-v')
    command += ['--data-dir', str(run_dir), source, '--max-blocks', str(values['crawl.maxBlocks'])]
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
    elif source == 'booking-hotels':
        command += ['--delay', _num(values['booking.delay']), '--concurrency', str(values['booking.tabs']),
                    '--checkin-offset-days', str(values['booking.checkinOffsetDays']),
                    '--budget', f"booking_hotels={values['booking.hotelsPerDestination']}"]
        if values['booking.fast']:
            command.append('--fast')
        if not values['booking.vinpearlBrand']:
            command.append('--no-brand-sitemap')
    elif source == 'agoda-hotels':
        command += ['--delay', _num(values['agoda.delay']), '--concurrency', str(values['agoda.tabs']),
                    '--checkin-offset-days', str(values['agoda.checkinOffsetDays']),
                    '--budget', f"agoda_hotels={values['agoda.hotelsPerDestination']}"]
    return command


def run_source(run_dir: Path, source: str, destinations: str, group: str) -> int:
    command = source_command(run_dir, source, destinations, settings_values())
    say(f'[{group}] $ ' + ' '.join(command))
    with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors='replace') as proc:
        for line in proc.stdout:
            say(f'[{group}] {line.rstrip()}')
    return proc.returncode


def step(name: str, group: str | None = None, label: str | None = None):
    """Bước có ghi vào run.json khi đang có lượt; không có lượt (test gọi hàm trực tiếp) thì không làm gì."""
    return REC.step(name, group, label) if REC is not None else contextlib.nullcontext({})


async def run_cancellable(coroutine):
    """Cancel in-process HTTP/browser work too when the monitor requests a stop."""
    task = asyncio.create_task(coroutine)
    try:
        while not task.done():
            if REC is not None:
                REC.check_stop()
            await asyncio.wait({task}, timeout=0.25)
        return await task
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def crawl_sites(run_dir: Path, destinations: str, groups, parallel: int) -> dict[str, int]:
    """Chạy các nhóm site song song, tối đa `parallel` nhóm; mỗi bước là tên nguồn crawl.py hoặc một hàm.

    Một bước lỗi thì nhóm đó dừng và các nhóm chưa bắt đầu bị bỏ; nhóm đang chạy được chạy xong rồi mới raise,
    giống lượt tuần tự cũ dừng ở nguồn lỗi đầu tiên. Mã 75 (bị chặn, đã lưu tiến độ) vẫn được coi là chạy xong.
    """
    statuses: dict[str, int] = {}
    errors: list[Exception] = []
    stop = threading.Event()

    def run_group(name: str, steps) -> None:
        if stop.is_set() or (REC is not None and REC.stop_event.is_set()):
            say(f'catalog.group.skip name={name}')
            return
        started, status = time.monotonic(), 'ok'
        say(f'catalog.group.start name={name}')
        try:
            for item in steps:
                if stop.is_set():
                    status = 'stopped'
                    break
                if callable(item):
                    item()
                    continue
                with step(item, group=name) as detail:
                    statuses[item] = code = run_source(run_dir, item, destinations, name)
                    detail['exitCode'] = code
                    if code == 75:
                        detail['_status'] = 'blocked'
                    if code not in (0, 75):
                        raise RuntimeError(f'Nguồn {item} dừng với mã {code}')
        except Exception as exc:
            status = 'error'
            errors.append(exc)
            stop.set()
            say(f'[{name}] {type(exc).__name__}: {exc}')
        finally:
            say(f'catalog.group.done name={name} status={status} seconds={round(time.monotonic() - started)}')

    with ThreadPoolExecutor(max_workers=parallel, thread_name_prefix='site') as pool:
        for name, steps in groups:
            if steps:
                pool.submit(run_group, name, steps)
    if errors:
        raise errors[0]
    return statuses


def normalize(run_dir: Path, destinations: str | None) -> Path:
    values = settings_values()
    args = ['--data-dir', str(run_dir), '--rooms-per-hotel', str(values['normalise.roomsPerHotel']),
            '--flights-per-route', str(values['tripFlights.flightsPerRoute']),
            '--keep-unsellable', '--keep-missing-coordinates',
            '--keep-location-warnings', '--keep-price-outliers',
            '--report-json', str(run_dir / 'normalise_report.json')]
    if destinations:
        args += ['--destinations', destinations]
    else:
        args += ['--no-plan']
    if normalise_main(args):
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
    variants = {(row['taxonomy'], row['attributes'].get('level')) for row in rows}
    need = REQUIRED if required is None else required
    if full and not need <= variants:
        raise ValueError(f'Thiếu nhóm sản phẩm: {need - variants}')
    return {'products': len(rows), 'completedHotels': len(checked),
            'variants': sorted(f'{a}/{b or "-"}' for a, b in variants)}


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
    required['COHERE_API_KEY'] = settings.cohere_api_key
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f'Thiếu biến cho bước index: {", ".join(missing)}')
    normalize_weaviate_url(settings.weaviate_url)
    return settings


def index_catalog(settings) -> dict:
    # Đọc lại đúng DB vừa ghi, ghi vào Weaviate của cùng đích; runtime API vẫn dùng role chỉ đọc của nó.
    from src.backend.jobs.embed_products import run
    print("catalog.index.start", flush=True)
    report = run(settings=settings)
    print("catalog.index.complete " + json.dumps(report, ensure_ascii=False), flush=True)
    return report


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
    running = read_json(state_dir / 'running.json')
    if running and lock_busy(state_dir):
        print(f'Running: {running.get("runId")} since {running.get("startedAt")} steps={running.get("steps")}')


def run_job(mode: str, trigger: str | None = None) -> int:
    global CFG, REC
    state_dir, run_root = dirs()
    state_dir.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)
    values = fresh_settings.load(state_dir)
    if mode == 'status':
        print_status(values, state_dir)
        return 0
    if mode == 'due':
        chosen, reason = (None, 'đang có lượt chạy') if lock_busy(state_dir) else \
            fresh_settings.scheduled_mode(values, state_dir)
        print(chosen or '', flush=True)
        print(f'catalog.due {chosen or "-"}: {reason}', file=sys.stderr, flush=True)
        return 0
    # An idle cron tick needs neither DB credentials nor an index connection.
    if mode == 'tick' and (lock_busy(state_dir) or fresh_settings.scheduled_mode(values, state_dir)[0] is None):
        return 0
    trigger = trigger or os.environ.get('CATALOG_TRIGGER') or 'manual'
    db_target = os.environ.get('DB_TARGET', 'local')
    key = 'SEED_DATABASE_URL' if db_target == 'local' else 'CLOUD_SEED_DATABASE_URL'
    if db_target not in ('local', 'cloud') or not os.environ.get(key):
        raise ValueError(f'Cần DB_TARGET=local/cloud và {key}')
    index_config = index_settings(db_target)
    lock_path = state_dir / 'fresh_catalog.lock'
    with lock_path.open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if mode == 'tick':
                return 0
            raise RuntimeError('Đã có job catalog khác đang chạy') from None
        if mode == 'tick':
            selected, reason = fresh_settings.scheduled_mode(values, state_dir)
            if selected is None:
                print(f'catalog.schedule.skip: {reason}', flush=True)
                return 0
            trigger = 'schedule'
        else:
            selected = fresh_settings.auto_mode(values, state_dir) if mode == 'auto' else mode
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        run_id = f'{selected}-{stamp}-{os.getpid()}'
        run_dir = run_root / run_id
        if trigger == 'schedule':
            fresh_settings.mark_scheduled(state_dir, run_id)
        recorder = RunRecorder(run_dir, state_dir, run_id=run_id, mode=selected, trigger=trigger, settings=values)
        CFG, REC = values, recorder.start()
        status, code, error = 'failed', EXIT_PARTIAL, None
        try:
            removed = prune_runs(run_root, values['runs.keep'], protect=run_dir)
            print(f'Run {selected}: {run_dir}' + (f' (xoá lượt cũ: {", ".join(removed)})' if removed else ''), flush=True)
            code = execute(selected, recorder, values, state_dir, run_dir, os.environ[key], index_config)
            recorder.check_stop()
            status = 'ok' if code == 0 else 'partial'
            return code
        except BaseException as exc:
            error = f'{type(exc).__name__}: {exc}'
            if isinstance(exc, StopRequested) or recorder.stop_event.is_set():
                status, code = 'stopped', EXIT_STOPPED
                if not isinstance(exc, StopRequested):
                    raise StopRequested(str(exc)) from exc
            raise
        finally:
            recorder.finish(status, code, error)
            CFG = REC = None


def execute(selected: str, rec: RunRecorder, values: dict, state_dir: Path, run_dir: Path,
            db_url: str, index_config) -> int:
    with step('maintain', label='Bảo trì DB: hết hạn giá Trip cũ, cuộn cửa sổ 30 ngày') as detail:
        maintenance = maintain_catalog(db_url)
        detail.update(maintenance)
    print("catalog.maintain.complete " + json.dumps(maintenance), flush=True)
    rec.set_counts(maintain=maintenance)
    if selected == 'index':
        run_index(rec, index_config)
        return 0
    try:
        return crawl_and_load(selected, rec, values, state_dir, run_dir, db_url)
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
    with step('index', label='Index vector vào Weaviate') as detail:
        report = index_catalog(index_config)
        detail.update(report or {})
    rec.set_counts(index=report)
    (rec.run_dir / 'index_report.json').write_text(json.dumps(report or {}, ensure_ascii=False, indent=1),
                                                   encoding='utf-8')


def crawl_and_load(selected: str, rec: RunRecorder, values: dict, state_dir: Path, run_dir: Path, db_url: str) -> int:
    targets_file = state_dir / 'trip_targets.json'
    schedule_file = state_dir / 'trip_schedule.json'
    coverage_path = run_dir / 'trip_price_coverage.json'
    started_at = rec.data['startedAt']
    trip_on = values['sources.tripHotels']
    options = LiveOptions(
        http_workers=values['tripHotels.httpWorkers'], price_workers=values['tripHotels.priceTabs'],
        delay_min=values['tripHotels.delayMin'], delay_max=values['tripHotels.delayMax'],
        offsets=tuple(values['tripHotels.priceOffsets']))
    trip: dict = {'targets': [], 'discovery': [], 'records': [], 'coverage': None}
    statuses: dict[str, int] = {}

    def price_rooms() -> None:
        with step('trip-hotels.prices', group='trip', label='Khách sạn Trip: thông tin + giá phòng') as detail:
            trip['records'], trip['coverage'] = asyncio.run(run_cancellable(crawl(Paths(run_dir).ensure(), trip['targets'], options)))
            coverage = trip['coverage'] or {}
            detail.update(requested=len(trip['targets']), completed=len(trip['records']),
                          unpricedHotelDates=len(coverage.get('unpricedHotelDates') or []))

    if selected == 'full':
        destinations = values['scope.destinations']
        cities = trip_cities(values)
        known = {row['trip_hotel_id'] for row in saved_targets(targets_file)}
        new_per_city = values['tripHotels.newPerCity'] if known else values['tripHotels.initialPerCity']

        def find_hotels() -> None:
            with step('trip-hotels.discover', group='trip', label='Khách sạn Trip: tìm ID mới') as detail:
                trip['targets'], trip['discovery'] = asyncio.run(run_cancellable(discover(
                    Paths(run_dir).ensure(), cities, values['tripHotels.scanPerCity'], new_per_city, known)))
                detail.update(cities=[c.name for c in cities], selected=len(trip['targets']),
                              perCity=trip['discovery'])
                if not trip['targets']:
                    raise RuntimeError('Trip không trả ID khách sạn mới hoặc cũ để kiểm tra')

        groups = []
        for name, sources in SITE_GROUPS:
            steps = [s for s in sources if values[SOURCE_SWITCH[s]]]
            if name == 'trip' and trip_on and cities:
                steps = [find_hotels, *steps, price_rooms]
            groups.append((name, tuple(steps)))
        statuses = crawl_sites(run_dir, destinations, groups, values['crawl.parallelSites'])
        rec.check_stop()
        trip_used = trip_on and bool(cities)
    else:
        destinations = None
        trip_used = trip_on
        if trip_on:
            known = saved_targets(targets_file)
            if not known:
                raise RuntimeError('Chưa có ID Trip; chạy --full trước')
            trip['targets'] = select_batch(known, read_state(schedule_file), values['tripHotels.dailyHotels'])
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
            raise RuntimeError('Không có khách sạn Trip đủ JSON giá ở mọi mốc ngày')
    with step('normalise', label='Chuẩn hoá 13 trường, gộp trùng') as detail:
        products = normalize(run_dir, destinations)
        detail.update(read_json(run_dir / 'normalise_report.json', {}) or {})
    with step('validate', label='Kiểm tra catalog trước khi nạp') as detail:
        summary = validate_run(products, coverage_path if trip_used else None, full=selected == 'full',
                               required=required_variants(values), trip=trip_used)
        detail.update(summary)
    rec.set_counts(catalog=summary)
    rec.check_stop()
    with step('db', label='Nạp cdp.products / catalog.combo_items') as detail:
        counts = load_into_db(products, coverage_path if trip_used else None, db_url, ROOT,
                              report_path=run_dir / 'db_load.jsonl')
        detail.update(counts or {})
    rec.set_counts(database=counts)
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
    return EXIT_PARTIAL if unpriced or any(status != 0 for status in statuses.values()) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', nargs='?', choices=('auto', 'full', 'daily', 'status', 'index', 'due', 'tick'), default='auto')
    ap.add_argument('--trigger', choices=('manual', 'schedule', 'monitor', 'cron'), default=None,
                    help='ai khởi chạy lượt (mặc định CATALOG_TRIGGER hoặc manual)')
    args = ap.parse_args(argv)
    try:
        return run_job(args.mode, args.trigger)
    except StopRequested as exc:
        print(f'Fresh catalog stopped: {exc}', file=sys.stderr)
        return EXIT_STOPPED
    except (RuntimeError, ValueError, OSError) as exc:
        print(f'Fresh catalog failed: {exc}', file=sys.stderr)
        return EXIT_PARTIAL


if __name__ == '__main__':
    raise SystemExit(main())
