#!/usr/bin/env python3
"""One-repository fresh catalog job for the console VM.

Full runs crawl Travel's existing sources plus a bounded new Trip hotel batch.
Daily runs rotate known Trip IDs. Only ID/timestamp state survives each run;
all prices and product rows are read from this run's fresh source responses.
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from collectors.common import Paths
from collectors.plan import select_destinations
from collectors.trip_live import LiveOptions, crawl, discover
from fresh_catalog_db import checked_trip_hotels, load_into_db, maintain_catalog
from fresh_catalog_schedule import read_state, read_targets, record_batch, select_batch, write_state
from normalise import PRODUCT_FIELDS, main as normalise_main

ROOT = Path(__file__).resolve().parent
# Lượt full: mỗi site một nhóm. Các nhóm chạy song song (CRAWL_PARALLEL), trong một nhóm vẫn tuần tự như trước
# nên số request đồng thời tới từng site không đổi. Nhóm trip còn tìm ID khách sạn trước và hỏi giá phòng sau.
SITE_GROUPS = (('trip', ('trip-flights', 'trip-attractions')), ('vinpearl', ('vinpearl',)),
               ('booking', ('booking-hotels',)), ('agoda', ('agoda-hotels',)))
REQUIRED = {('hotel', 'property'), ('hotel', 'room'), ('flight', 'route'),
            ('flight', 'flight'), ('attraction', None), ('combo', None)}


def positive_env(name: str, default: int) -> int:
    value = int(os.environ.get(name, default))
    if value < 1:
        raise ValueError(f'{name} phải >= 1')
    return value


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


_print_lock = threading.Lock()


def say(line: str) -> None:
    """Một dòng log nguyên vẹn khi nhiều nhóm cùng in."""
    with _print_lock:
        print(line, flush=True)


def run_source(run_dir: Path, source: str, destinations: str, group: str) -> int:
    command = [sys.executable, str(ROOT / 'crawl.py'), '--data-dir', str(run_dir), source]
    if source == 'vinpearl':
        command.append('--refresh')
    else:
        command.extend(['--destinations', destinations])
        if source == 'booking-hotels':
            command.append('--fast')
    say(f'[{group}] $ ' + ' '.join(command))
    with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, errors='replace') as proc:
        for line in proc.stdout:
            say(f'[{group}] {line.rstrip()}')
    return proc.returncode


def crawl_sites(run_dir: Path, destinations: str, groups, parallel: int) -> dict[str, int]:
    """Chạy các nhóm site song song, tối đa `parallel` nhóm; mỗi bước là tên nguồn crawl.py hoặc một hàm.

    Một bước lỗi thì nhóm đó dừng và các nhóm chưa bắt đầu bị bỏ; nhóm đang chạy được chạy xong rồi mới raise,
    giống lượt tuần tự cũ dừng ở nguồn lỗi đầu tiên. Mã 75 (bị chặn, đã lưu tiến độ) vẫn được coi là chạy xong.
    """
    statuses: dict[str, int] = {}
    errors: list[Exception] = []
    stop = threading.Event()

    def run_group(name: str, steps) -> None:
        if stop.is_set():
            say(f'catalog.group.skip name={name}')
            return
        started, status = time.monotonic(), 'ok'
        say(f'catalog.group.start name={name}')
        try:
            for step in steps:
                if stop.is_set():
                    status = 'stopped'
                    break
                if callable(step):
                    step()
                    continue
                statuses[step] = code = run_source(run_dir, step, destinations, name)
                if code not in (0, 75):
                    raise RuntimeError(f'Nguồn {step} dừng với mã {code}')
        except Exception as exc:
            status = 'error'
            errors.append(exc)
            stop.set()
            say(f'[{name}] {type(exc).__name__}: {exc}')
        finally:
            say(f'catalog.group.done name={name} status={status} seconds={round(time.monotonic() - started)}')

    with ThreadPoolExecutor(max_workers=parallel, thread_name_prefix='site') as pool:
        for name, steps in groups:
            pool.submit(run_group, name, steps)
    if errors:
        raise errors[0]
    return statuses


def normalize(run_dir: Path, destinations: str | None) -> Path:
    args = ['--data-dir', str(run_dir), '--rooms-per-hotel', '0',
            '--keep-unsellable', '--keep-missing-coordinates',
            '--keep-location-warnings', '--keep-price-outliers']
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


def validate_run(products_path: Path, coverage_path: Path, *, full: bool) -> dict:
    checked = checked_trip_hotels(coverage_path)
    if not checked:
        raise ValueError('Chưa có khách sạn Trip hoàn tất 3 mốc ngày')
    with products_path.open(encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    if not rows or any(tuple(row) != PRODUCT_FIELDS for row in rows):
        raise ValueError('Catalog thiếu 13 trường đúng thứ tự')
    variants = {(row['taxonomy'], row['attributes'].get('level')) for row in rows}
    if full and not REQUIRED <= variants:
        raise ValueError(f'Thiếu nhóm sản phẩm: {REQUIRED - variants}')
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


def run_job(mode: str) -> int:
    state_dir = Path(os.environ.get('CATALOG_STATE_DIR', ROOT / 'data' / 'state')).resolve()
    run_root = Path(os.environ.get('CATALOG_RUN_ROOT', ROOT / 'data' / 'fresh_runs')).resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)
    targets_file = state_dir / 'trip_targets.json'
    schedule_file = state_dir / 'trip_schedule.json'
    marker = state_dir / 'full.last_success'
    if state_dir == run_root or run_root in state_dir.parents:
        raise ValueError('CATALOG_STATE_DIR phải nằm ngoài CATALOG_RUN_ROOT')
    full_days = positive_env('FULL_REFRESH_DAYS', 7)
    if mode in ('auto', 'status'):
        if not targets_file.exists() or not marker.exists():
            selected = 'full'
        else:
            elapsed = datetime.now(timezone.utc).timestamp() - marker.stat().st_mtime
            selected = 'full' if elapsed >= full_days * 86400 else 'daily'
    else:
        selected = mode
    if mode == 'status':
        print(f'Next run: {selected}; known Trip IDs: {len(saved_targets(targets_file))}; '
              f'daily batch: {positive_env("TRIP_DAILY_HOTELS", 60)}; '
              f'initial/city: {positive_env("TRIP_INITIAL_PER_CITY", 10)}; '
              f'new/city: {positive_env("TRIP_NEW_PER_CITY", 3)}; '
              f'parallel sites (full): {positive_env("CRAWL_PARALLEL", 2)}')
        return 0
    db_target = os.environ.get('DB_TARGET', 'local')
    key = 'SEED_DATABASE_URL' if db_target == 'local' else 'CLOUD_SEED_DATABASE_URL'
    if db_target not in ('local', 'cloud') or not os.environ.get(key):
        raise ValueError(f'Cần DB_TARGET=local/cloud và {key}')
    index_config = index_settings(db_target)
    options = LiveOptions(
        http_workers=positive_env('FAST_WORKERS', 4),
        price_workers=positive_env('PRICE_WORKERS', 2),
        delay_min=float(os.environ.get('MIN_DELAY', '0.5')),
        delay_max=float(os.environ.get('MAX_DELAY', '1.0')),
        offsets=tuple(int(value.strip()) for value in os.environ.get('TRIP_PRICE_DATES', '14,30,60').split(',')))
    lock_path = state_dir / 'fresh_catalog.lock'
    with lock_path.open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Đã có job catalog khác đang chạy') from None
        maintenance = maintain_catalog(os.environ[key])
        print("catalog.maintain.complete " + json.dumps(maintenance), flush=True)
        if mode == 'index':
            index_catalog(index_config)
            return 0
        # A killed process can leave temporary captures. They never become inputs.
        if os.environ.get('KEEP_FAILED_RUNS') != '1' and os.environ.get('KEEP_SUCCESS_RUNS') != '1':
            for old in run_root.iterdir():
                if old.is_dir() and old.name.startswith(('full-', 'daily-')):
                    shutil.rmtree(old)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        run_dir = run_root / f'{selected}-{stamp}-{os.getpid()}'
        run_dir.mkdir()
        print(f'Run {selected}: {run_dir}', flush=True)
        try:
            if selected == 'full':
                destinations = os.environ.get('CATALOG_DESTINATIONS', '@deep')
                cities = select_destinations(destinations)
                known = {row['trip_hotel_id'] for row in saved_targets(targets_file)}
                new_per_city = (positive_env('TRIP_NEW_PER_CITY', 3) if known else
                                positive_env('TRIP_INITIAL_PER_CITY', 10))
                trip: dict = {}

                def find_hotels() -> None:
                    trip['targets'], trip['discovery'] = asyncio.run(discover(
                        Paths(run_dir).ensure(), cities,
                        positive_env('TRIP_DISCOVERY_SCAN_PER_CITY', 300),
                        new_per_city, known))
                    if not trip['targets']:
                        raise RuntimeError('Trip không trả ID khách sạn mới hoặc cũ để kiểm tra')

                def price_rooms() -> None:
                    trip['records'], trip['coverage'] = asyncio.run(
                        crawl(Paths(run_dir).ensure(), trip['targets'], options))

                groups = [(name, (find_hotels, *sources, price_rooms) if name == 'trip' else sources)
                          for name, sources in SITE_GROUPS]
                statuses = crawl_sites(run_dir, destinations, groups, positive_env('CRAWL_PARALLEL', 2))
                targets, discovery = trip['targets'], trip['discovery']
                records, coverage = trip['records'], trip['coverage']
            else:
                destinations = None
                known = saved_targets(targets_file)
                if not known:
                    raise RuntimeError('Chưa có ID Trip; chạy --full trước')
                targets = select_batch(known, read_state(schedule_file),
                                       positive_env('TRIP_DAILY_HOTELS', 60))
                discovery, statuses = [], {}
                records, coverage = asyncio.run(crawl(Paths(run_dir).ensure(), targets, options))
            print(f'Trip complete: {len(records)}/{len(targets)}', flush=True)
            if not records:
                state = record_batch(targets, coverage, read_state(schedule_file),
                                     datetime.now(timezone.utc).isoformat())
                write_state(schedule_file, state)
                raise RuntimeError('Không có khách sạn Trip đủ JSON giá ở mọi mốc ngày')
            products = normalize(run_dir, destinations)
            summary = validate_run(products, run_dir / 'trip_price_coverage.json', full=selected == 'full')
            counts = load_into_db(products, run_dir / 'trip_price_coverage.json', os.environ[key], ROOT)
            if selected == 'full':
                merge_targets(targets_file, targets)
                marker.write_text(datetime.now(timezone.utc).isoformat() + '\n', encoding='utf-8')
            state = record_batch(targets, coverage, read_state(schedule_file),
                                 datetime.now(timezone.utc).isoformat())
            write_state(schedule_file, state)
            print(json.dumps({'mode': selected, 'discovery': discovery, 'sources': statuses,
                              'catalog': summary, 'database': counts}, ensure_ascii=False), flush=True)
            return 3 if coverage['unpricedHotelDates'] or any(status != 0 for status in statuses.values()) else 0
        finally:
            crawl_failed = sys.exc_info()[0] is not None
            try:
                index_catalog(index_config)
            except Exception as exc:
                print(f"catalog.index.failed {type(exc).__name__}: {exc}; retry mode=index", file=sys.stderr, flush=True)
                if not crawl_failed:
                    raise RuntimeError("Index thất bại; DB đã giữ dữ liệu mới. Chạy lại mode=index") from exc
            finally:
                cleanup_run(run_dir, crawl_failed)


def cleanup_run(run_dir: Path, failed: bool) -> None:
    if os.environ.get('KEEP_FAILED_RUNS') == '1' and failed:
        print(f'Kept failed run: {run_dir}', flush=True)
    elif os.environ.get('KEEP_SUCCESS_RUNS') == '1' and not failed:
        print(f'Kept run: {run_dir}', flush=True)
    else:
        shutil.rmtree(run_dir, ignore_errors=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', nargs='?', choices=('auto', 'full', 'daily', 'status', 'index'), default='auto')
    args = ap.parse_args(argv)
    try:
        return run_job(args.mode)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f'Fresh catalog failed: {exc}', file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
