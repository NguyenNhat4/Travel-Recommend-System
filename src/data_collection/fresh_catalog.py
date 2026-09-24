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
from datetime import datetime, timezone
from pathlib import Path

from collectors.common import Paths
from collectors.plan import select_destinations
from collectors.trip_live import LiveOptions, crawl, discover
from fresh_catalog_db import checked_trip_hotels, load_into_db
from fresh_catalog_schedule import read_state, read_targets, record_batch, select_batch, write_state
from normalise import PRODUCT_FIELDS, main as normalise_main

ROOT = Path(__file__).resolve().parent
SOURCES = ('vinpearl', 'trip-flights', 'trip-attractions', 'booking-hotels', 'agoda-hotels')
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


def crawl_sources(run_dir: Path, destinations: str) -> dict[str, int]:
    statuses = {}
    for source in SOURCES:
        command = [sys.executable, str(ROOT / 'crawl.py'), '--data-dir', str(run_dir), source]
        if source == 'vinpearl':
            command.append('--refresh')
        else:
            command.extend(['--destinations', destinations])
            if source == 'booking-hotels':
                command.append('--fast')
        print('$ ' + ' '.join(command), flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        statuses[source] = result.returncode
        if result.returncode not in (0, 75):
            raise RuntimeError(f'Nguồn {source} dừng với mã {result.returncode}')
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
              f'new/city: {positive_env("TRIP_NEW_PER_CITY", 3)}')
        return 0
    db_target = os.environ.get('DB_TARGET', 'local')
    key = 'SEED_DATABASE_URL' if db_target == 'local' else 'CLOUD_SEED_DATABASE_URL'
    if db_target not in ('local', 'cloud') or not os.environ.get(key):
        raise ValueError(f'Cần DB_TARGET=local/cloud và {key}')
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
                targets, discovery = asyncio.run(discover(
                    Paths(run_dir).ensure(), cities,
                    positive_env('TRIP_DISCOVERY_SCAN_PER_CITY', 300),
                    new_per_city, known))
                if not targets:
                    raise RuntimeError('Trip không trả ID khách sạn mới hoặc cũ để kiểm tra')
                statuses = crawl_sources(run_dir, destinations)
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
            if os.environ.get('KEEP_FAILED_RUNS') == '1' and sys.exc_info()[0] is not None:
                print(f'Kept failed run: {run_dir}', flush=True)
            elif os.environ.get('KEEP_SUCCESS_RUNS') == '1' and sys.exc_info()[0] is None:
                print(f'Kept run: {run_dir}', flush=True)
            else:
                shutil.rmtree(run_dir, ignore_errors=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', nargs='?', choices=('auto', 'full', 'daily', 'status'), default='auto')
    args = ap.parse_args(argv)
    try:
        return run_job(args.mode)
    except (RuntimeError, ValueError, OSError) as exc:
        print(f'Fresh catalog failed: {exc}', file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
