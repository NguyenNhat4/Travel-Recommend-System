"""Small durable ID schedule for bounded, fair Trip.com price refreshes.

The state contains IDs and crawl timestamps only. Prices and source responses
always come from a new crawl, never from this file.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def read_targets(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding='utf-8'))
    rows, seen = [], set()
    for row in data.get('hotels') or []:
        hotel_id = str(row.get('trip_hotel_id') or '')
        city = row.get('destination') or row.get('city_name') or data.get('city_name')
        city_id = str(row.get('city_id') or '')
        if not hotel_id.isdigit() or not city or not city_id.isdigit():
            raise ValueError(f'ID hoặc thành phố không hợp lệ: {row}')
        if hotel_id not in seen:
            rows.append({'trip_hotel_id': hotel_id, 'city_id': city_id, 'destination': city})
            seen.add(hotel_id)
    if not rows:
        raise ValueError('Danh sách ID rỗng')
    return rows


def read_state(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('version') != 1 or not isinstance(data.get('hotels'), dict):
        raise ValueError(f'File lịch cào không hợp lệ: {path}')
    return data['hotels']


def write_state(path: Path, hotels: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix='.trip-schedule-',
                                     delete=False, encoding='utf-8') as tmp:
        json.dump({'version': 1, 'hotels': hotels}, tmp, ensure_ascii=False, sort_keys=True)
        tmp.write('\n')
        name = tmp.name
    os.replace(name, path)


def select_batch(targets: list[dict[str, str]], state: dict[str, dict], limit: int) -> list[dict[str, str]]:
    if limit < 1:
        raise ValueError('Giới hạn khách sạn mỗi lượt phải >= 1')
    # Never attempted IDs go first. Afterwards the oldest attempt runs first;
    # failures rotate too, so one persistently blocked hotel cannot starve others.
    return sorted(targets, key=lambda row: state.get(row['trip_hotel_id'], {}).get('lastAttemptAt') or '')[:limit]


def record_batch(targets: list[dict[str, str]], coverage: dict, state: dict[str, dict],
                 now: str) -> dict[str, dict]:
    stays = {row['checkin'] for row in coverage['stays']}
    if not stays or len(stays) != len(coverage['stays']):
        raise ValueError('Báo cáo ngày giá không hợp lệ')
    target_ids = {row['trip_hotel_id'] for row in targets}
    results: dict[str, dict[str, str]] = {}
    for row in coverage['results']:
        hotel_id, day = str(row['hotelId']), row['checkin']
        if hotel_id not in target_ids or day in results.setdefault(hotel_id, {}):
            raise ValueError('Báo cáo giá có ID lạ hoặc hotel-ngày trùng')
        results[hotel_id][day] = row['status']
    if set(results) != target_ids or any(set(days) != stays for days in results.values()):
        raise ValueError('Báo cáo giá thiếu ID hoặc ngày')
    updated = dict(state)
    for hotel_id, dates in results.items():
        entry = dict(updated.get(hotel_id) or {})
        entry['lastAttemptAt'] = now
        if all(status in ('priced', 'sold_out') for status in dates.values()):
            entry['lastSuccessAt'] = now
        updated[hotel_id] = entry
    return updated


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='mode', required=True)
    select = sub.add_parser('select')
    select.add_argument('--targets', type=Path, required=True)
    select.add_argument('--state', type=Path, required=True)
    select.add_argument('--limit', type=int, required=True)
    select.add_argument('--output', type=Path, required=True)
    record = sub.add_parser('record')
    record.add_argument('--targets', type=Path, required=True)
    record.add_argument('--state', type=Path, required=True)
    record.add_argument('--coverage', type=Path, required=True)
    args = ap.parse_args(argv)
    targets = read_targets(args.targets)
    state = read_state(args.state)
    if args.mode == 'select':
        chosen = select_batch(targets, state, args.limit)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({'hotels': chosen}, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'Trip rotation: {len(chosen)}/{len(targets)} IDs → {args.output}')
    else:
        coverage = json.loads(args.coverage.read_text(encoding='utf-8'))
        now = datetime.now(timezone.utc).isoformat()
        updated = record_batch(targets, coverage, state, now)
        write_state(args.state, updated)
        print(f'Trip rotation recorded: {len(targets)} IDs → {args.state}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
