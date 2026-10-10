"""Fresh Vietnamese Trip hotel metadata over HTTP and room prices from JSON.

This adapts the existing Travel collector's city list and HTML parser. Chromium
is used only for the room API that Trip loads after the room section scrolls
into view. Every response belongs to the current run directory.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import math
import random
import shutil
import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from curl_cffi.requests import AsyncSession
from playwright.async_api import async_playwright

import log
from . import live_control
from .common import BrowserOptions, BrowserSession, Paths, StateDB, now_iso
from .plan import DEFAULT_BUDGET, Destination
from .trip import _scrub as scrub_people
from .trip_hotels import DETAIL_ANCHOR, TripHotels, TripHotelsOptions, extract_anchored_json, parse_hotel_detail

BASE = 'https://vn.trip.com/hotels/detail/?'
LIVE_KEY = 'tripHotels'   # khoá chỉnh tốc độ live trên monitor (collectors/live_control.py)
HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.7',
}


@dataclass(frozen=True)
class LiveOptions:
    http_workers: int = 4
    price_workers: int = 2
    delay_min: float = 0.5
    delay_max: float = 1.0
    offsets: tuple[int, ...] = (14, 30, 60)


async def next_start(clock: dict, options: LiveOptions) -> None:
    """Giữ khoảng chờ ngẫu nhiên giữa hai lần mở trang. Monitor có thể tạm dừng hoặc đổi khoảng chờ khi lượt đang chạy;
    mốc chờ được tính lại mỗi giây nên thay đổi có hiệu lực ngay."""
    loop = asyncio.get_running_loop()
    bounds, gap = None, 0.0
    while True:
        control = await live_control.hold_while_paused(LIVE_KEY)
        low = control.get('delayMin', options.delay_min)
        high = max(low, control.get('delayMax', options.delay_max))
        if (low, high) != bounds:
            bounds, gap = (low, high), random.uniform(low, high)
        wait = clock['last'] + gap - loop.time()
        if wait <= 0:
            break
        await asyncio.sleep(min(wait, 1.0))
    clock['last'] = loop.time()


def stays(offsets: tuple[int, ...], today: date | None = None) -> list[tuple[str, str]]:
    today = today or date.today()
    if not offsets or any(offset < 1 for offset in offsets):
        raise ValueError('Cần ít nhất một mốc ngày nhận phòng sau hôm nay')
    return [(day.isoformat(), (day + timedelta(days=1)).isoformat())
            for day in sorted({today + timedelta(days=offset) for offset in offsets})]


def detail_url(target: dict, checkin: str, checkout: str) -> str:
    params = {'hotelId': target['trip_hotel_id'], 'cityId': target['city_id'],
              'checkIn': checkin, 'checkOut': checkout, 'adult': 2, 'children': 0,
              'crn': 1, 'curr': 'VND', 'locale': 'vi-VN'}
    return BASE + urlencode(params)


async def discover(paths: Paths, destinations: tuple[Destination, ...], scan_per_city: int,
                   new_per_city: int, known: set[str]) -> tuple[list[dict], list[dict]]:
    if scan_per_city < 1 or new_per_city < 1:
        raise ValueError('Mức tìm ID và số ID mới mỗi thành phố phải >= 1')
    opts = TripHotelsOptions(destinations=destinations,
                             budget=replace(DEFAULT_BUDGET, trip_hotels=min(scan_per_city, new_per_city) if not known else scan_per_city),
                             browser=BrowserOptions(headless=False))
    state = StateDB(paths)
    chosen, report = [], []
    try:
        async with BrowserSession(paths, 'trip_hotels_fresh', opts.browser) as session:
            crawler = TripHotels(paths, opts, state)
            page = await session.new_page()
            try:
                for city in destinations:
                    if not city.trip_hotel_city_id:
                        continue
                    cards = await crawler._collect_cards(page, city)
                    candidates = [card for card in cards if str(card.get('hotelId') or '').isdigit()]
                    new = [card for card in candidates if card['hotelId'] not in known]
                    selected = new[:new_per_city] or candidates[:1]
                    for card in selected:
                        chosen.append({'trip_hotel_id': card['hotelId'], 'city_id': city.trip_hotel_city_id,
                                       'destination': city.name, 'card': card})
                    report.append({'city': city.name, 'discovered': len(candidates),
                                   'selected': len(selected), 'newSelected': min(len(new), new_per_city)})
            finally:
                await page.close()
    finally:
        state.close()
    seen, unique = set(), []
    for row in chosen:
        if row['trip_hotel_id'] not in seen:
            unique.append(row)
            seen.add(row['trip_hotel_id'])
    return unique, report


def _write_capture(run_dir: Path, hotel_id: str, name: str, payload: dict) -> Path:
    """Raw của một lần hỏi, để monitor xem lại: JSON nén, đã bỏ review/tên người (handbook) trước khi ghi đĩa."""
    path = run_dir / 'raw' / 'trip_hotels' / hotel_id / f'{name}.json.gz'
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, 'wt', encoding='utf-8') as out:
        json.dump(scrub_people(payload), out, ensure_ascii=False)
    return path


async def fetch_metadata(targets: list[dict], stay: tuple[str, str], run_dir: Path,
                         options: LiveOptions) -> dict[str, dict | None]:
    semaphore = asyncio.Semaphore(options.http_workers)
    start_lock = asyncio.Lock()
    clock = {'last': float('-inf')}
    out: dict[str, dict | None] = {}
    session = AsyncSession(impersonate="chrome124", timeout=30)

    async def one(target: dict) -> None:
        hotel_id = target['trip_hotel_id']
        url = detail_url(target, *stay)
        async with semaphore:
            for attempt in range(2):
                async with start_lock:
                    await next_start(clock, options)
                started = time.monotonic()
                try:
                    response = await session.get(url, headers=HEADERS, allow_redirects=True)
                    detail = extract_anchored_json(response.text, DETAIL_ANCHOR) if response.status_code == 200 else None
                    ok = bool(detail)
                    log.say(f'Trip meta {hotel_id} lần {attempt + 1}: HTTP {response.status_code} · '
                            f'{round((time.monotonic() - started) * 1000)} ms · {len(response.content)} B'
                            + ('' if ok else ' · thiếu hotelDetailResponse'), event='trip.meta',
                            severity='INFO' if ok else 'WARNING', source='tripHotels', step='trip-hotels.prices',
                            http_status=response.status_code, hotel_id=str(hotel_id))
                    if not ok:
                        continue
                    _write_capture(run_dir, hotel_id, f'{stay[0]}.detail', {
                        'url': url, 'fetchedAt': now_iso(), 'httpStatus': response.status_code,
                        'hotelDetailResponse': detail})
                    out[hotel_id] = parse_hotel_detail(response.text, url, target.get('card') or {}, now_iso(),
                                                        checkin=stay[0], checkout=stay[1], adults=2)
                    return
                except Exception as exc:
                    log.say(f'Trip meta {hotel_id} lần {attempt + 1}: lỗi {type(exc).__name__}: {str(exc)[:160]}',
                            event='trip.meta', severity='WARNING', source='tripHotels', step='trip-hotels.prices',
                            hotel_id=str(hotel_id))
                    if attempt == 1:
                        break
        out[hotel_id] = None

    try:
        await asyncio.gather(*(one(target) for target in targets))
    finally:
        await session.close()
    return out


def price_packet(payload: dict) -> tuple[str, dict[str, dict], int]:
    """Accept only a real room JSON response; an empty/bad response is unknown."""
    if not isinstance(payload, dict):
        return 'missing', {}, 0
    data = payload.get('data') or {}
    if not isinstance(data, dict):
        return 'missing', {}, 0
    physical = data.get('physicRoomMap') or {}
    sales = data.get('saleRoomMap') or {}
    if not isinstance(physical, dict) or not isinstance(sales, dict):
        return 'missing', {}, 0
    offers = len(sales)
    best: dict[str, dict] = {}
    for sale in sales.values():
        if not isinstance(sale, dict) or (sale.get('bookingStatusInfo') or {}).get('isFullRoom'):
            continue
        room_id = str(sale.get('physicalRoomId') or '')
        info = sale.get('priceInfo') or {}
        if room_id not in physical or (info.get('currency') or 'VND').upper() != 'VND':
            continue
        try:
            amount = float(info.get('price'))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(amount) or amount <= 0:
            continue
        if room_id not in best or amount < best[room_id]['price']:
            best[room_id] = {'price': round(amount),
                             'occupancy': (sale.get('guestCountInfo') or {}).get('guestCount')}
    if best:
        return 'priced', {'physical': physical, 'best': best}, offers
    # Hết phòng: Trip đánh dấu cả danh sách và không còn phòng nào mở (không có hạng bán, hoặc mọi hạng `isFullRoom`).
    # Trước đây trường hợp sau rơi vào `missing` và làm bước giá phòng `partial` (lượt local 07/10: 5/231 lượt).
    all_full = all(isinstance(sale, dict) and (sale.get('bookingStatusInfo') or {}).get('isFullRoom')
                   for sale in sales.values())
    if data.get('isRoomListSoldOut') is True and all_full:
        return 'sold_out', {'physical': physical, 'best': {}}, 0
    return 'missing', {}, offers


async def wait_for_prices(page, ready: asyncio.Event) -> None:
    """Stop waiting as soon as room evidence arrives; keep the existing maximum wait."""
    for ratio in (0.55, 0.75, 0.95):
        if ready.is_set():
            return
        await page.evaluate(f'window.scrollTo(0, document.body.scrollHeight * {ratio})')
        try:
            await asyncio.wait_for(ready.wait(), timeout=1.3)
            return
        except asyncio.TimeoutError:
            pass
    try:
        await asyncio.wait_for(ready.wait(), timeout=16)
    except asyncio.TimeoutError:
        pass


async def capture_prices(targets: list[dict], date_pairs: list[tuple[str, str]], run_dir: Path,
                         options: LiveOptions) -> dict[tuple[str, str], tuple[str, dict, int, str | None]]:
    jobs = asyncio.Queue()
    planned = [(target, checkin, checkout) for target in targets for checkin, checkout in date_pairs]
    for job in planned:
        jobs.put_nowait(job)
    results = {}
    start_lock = asyncio.Lock()
    clock = {'last': float('-inf')}
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(run_dir / 'trip_price_profile'), headless=False,
            locale='vi-VN', timezone_id='Asia/Ho_Chi_Minh',
            viewport={'width': 1366, 'height': 768},
            args=['--disable-blink-features=AutomationControlled'])
        try:
            async def worker() -> None:
                while not jobs.empty():
                    try:
                        target, checkin, checkout = jobs.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    hotel_id = target['trip_hotel_id']
                    url = detail_url(target, checkin, checkout)
                    page = await context.new_page()
                    packets: list[dict] = []
                    response_statuses: list[int] = []
                    capture_error = None
                    ready = asyncio.Event()
                    pending: set[asyncio.Task] = set()
                    browser_html = None
                    async def receive(response) -> None:
                        if 'getHotelRoomListOversea' not in response.url:
                            return
                        response_statuses.append(response.status)
                        if response.status != 200:
                            return
                        try:
                            body = await response.json()
                            if isinstance(body, dict):
                                packets.append(body)
                                if price_packet(body)[0] != 'missing':
                                    ready.set()
                        except Exception:
                            pass
                    def on_response(response) -> None:
                        if 'getHotelRoomListOversea' not in response.url:
                            return
                        task = asyncio.create_task(receive(response))
                        pending.add(task)
                        task.add_done_callback(pending.discard)
                    page.on('response', on_response)
                    try:
                        await page.route('**/*', lambda route: route.abort()
                                         if route.request.resource_type in ('image', 'media', 'font')
                                         else route.continue_())
                        async with start_lock:
                            await next_start(clock, options)
                        navigation = await page.goto(url, wait_until='domcontentloaded', timeout=60_000)
                        if checkin == date_pairs[0][0] and navigation and navigation.status == 200:
                            # Raw navigation response keeps the SSR blob after React
                            # removes it from the live DOM during hydration.
                            browser_html = await navigation.text()
                        await wait_for_prices(page, ready)
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)
                    except Exception as exc:
                        capture_error = type(exc).__name__
                    finally:
                        page.remove_listener("response", on_response)
                        for task in pending:
                            task.cancel()
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)
                        await page.close()
                    status, data, offers = next((parsed for packet in packets
                                                 if (parsed := price_packet(packet))[0] != 'missing'),
                                                ('missing', {}, 0))
                    _write_capture(run_dir, hotel_id, f'{checkin}.rooms', {
                        'url': url, 'fetchedAt': now_iso(), 'status': status, 'offers': offers,
                        'packets': packets, 'httpStatuses': response_statuses, 'errorKind': capture_error})
                    previous = results.get((hotel_id, checkin))
                    if status != 'missing' or previous is None:  # lần thử lại hỏng không xoá kết quả cũ
                        results[(hotel_id, checkin)] = (status, data, offers, browser_html or (previous or (None,) * 4)[3])
                    log.say(f'Trip {hotel_id}@{checkin}: {status}, {offers} offers · '
                            f'HTTP {response_statuses} · error={capture_error}', event='trip.price',
                            source='tripHotels', step='trip-hotels.prices', hotel_id=str(hotel_id),
                            checkin=str(checkin), offers=offers)
                    jobs.task_done()
            await asyncio.gather(*(worker() for _ in range(min(options.price_workers, jobs.qsize()))))
            # Một vòng thử lại cho (khách sạn, ngày) chưa bắt được gói giá: thường là lỗi thoáng qua (HTTP 200 nhưng
            # 0 gói trong 16 s). Lượt local 07/10: 1/219 như vậy làm cả bước `partial` dù khách sạn có giá ở ngày khác.
            for job in planned:
                if results.get((job[0]['trip_hotel_id'], job[1]), ('missing',))[0] == 'missing':
                    jobs.put_nowait(job)
            if not jobs.empty():
                log.say(f'Trip: thử lại {jobs.qsize()} lượt chưa có gói giá', event='trip.price.retry',
                        source='tripHotels', step='trip-hotels.prices', retries=jobs.qsize())
                await asyncio.gather(*(worker() for _ in range(min(options.price_workers, jobs.qsize()))))
        finally:
            try:
                await context.close()
            finally:
                shutil.rmtree(run_dir / "trip_price_profile", ignore_errors=True)
    return results


def assemble(targets: list[dict], date_pairs: list[tuple[str, str]], metadata: dict,
             captures: dict, run_dir: Path) -> tuple[list[dict], dict]:
    records, coverage = [], []
    for target in targets:
        hotel_id = target['trip_hotel_id']
        complete = True
        room_data: dict[str, dict] = {}
        fallback_html = None
        for checkin, checkout in date_pairs:
            status, data, offers, html = captures.get((hotel_id, checkin), ('missing', {}, 0, None))
            coverage.append({'hotelId': hotel_id, 'checkin': checkin, 'checkout': checkout,
                             'status': status, 'sourceOffers': offers})
            complete &= status in ('priced', 'sold_out')
            fallback_html = fallback_html or html
            if status == 'missing':
                continue
            for room_id, info in data['physical'].items():
                if not isinstance(info, dict) or not info.get('name'):
                    continue
                row = room_data.setdefault(str(room_id), {'roomId': str(room_id), 'name': info['name'],
                                                         'currency': 'VND', 'pricesByDate': {}})
                row['images'] = [image.get('url') for image in info.get('pictureInfo') or []
                                 if isinstance(image, dict) and image.get('url')][:5]
                offer = data['best'].get(str(room_id))
                if offer:
                    row['pricesByDate'][checkin] = offer['price']
                    row['maxOccupancy'] = offer.get('occupancy')
        if not complete:
            continue
        record = metadata.get(hotel_id)
        if record is None and fallback_html:
            url = detail_url(target, *date_pairs[0])
            _write_capture(run_dir, hotel_id, f'{date_pairs[0][0]}.detail', {
                'url': url, 'fetchedAt': now_iso(), 'source': 'browser',
                'hotelDetailResponse': extract_anchored_json(fallback_html, DETAIL_ANCHOR)})
            record = parse_hotel_detail(fallback_html, url, target.get('card') or {}, now_iso(),
                                        checkin=date_pairs[0][0], checkout=date_pairs[0][1], adults=2)
        if not record:
            for row in coverage:
                if row['hotelId'] == hotel_id:
                    row['status'] = 'missing'
            continue
        rooms = {str(room['roomId']): room for room in record.get('rooms') or [] if room.get('roomId')}
        for room_id, incoming in room_data.items():
            old = rooms.get(room_id) or {}
            rooms[room_id] = {**old, **incoming}
        record['rooms'] = list(rooms.values())
        queried = [checkin for checkin, _ in date_pairs]
        record['priceDatesQueried'] = queried
        for room in record['rooms']:
            prices = room.get('pricesByDate') or {}
            room['minPrice'] = prices[min(prices)] if prices else None
            room['availabilityByDate'] = {day: day in prices for day in queried}
        prices = [room['minPrice'] for room in record['rooms'] if room.get('minPrice')]
        record['minPrice'] = min(prices) if prices else None
        record['currency'] = 'VND'
        record['plan'] = {'destination': target['destination'], **({'via': 'refresh'} if target.get('refresh') else {})}
        record['crawledAt'] = now_iso()
        records.append(record)
    report = {'stays': [{'checkin': a, 'checkout': b} for a, b in date_pairs],
              'requestedHotels': len(targets), 'completedHotels': [r['hotelId'] for r in records],
              'results': coverage,
              'unpricedHotelDates': [f"{r['hotelId']}@{r['checkin']}" for r in coverage if r['status'] == 'missing'],
              'partialAllowed': True}
    (run_dir / 'trip_price_coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if records:
        interim = run_dir / 'interim' / 'trip_hotels.jsonl'
        interim.parent.mkdir(parents=True, exist_ok=True)
        interim.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in records), encoding='utf-8')
    return records, report


async def crawl(paths: Paths, targets: list[dict], options: LiveOptions) -> tuple[list[dict], dict]:
    if not 1 <= options.http_workers <= 10 or not 1 <= options.price_workers <= 10:
        raise ValueError('Workers phải từ 1 đến 10')
    if options.delay_min < 0 or options.delay_max < options.delay_min:
        raise ValueError('Delay không hợp lệ')
    date_pairs = stays(options.offsets)
    metadata = await fetch_metadata(targets, date_pairs[0], paths.data, options)
    captures = await capture_prices(targets, date_pairs, paths.data, options)
    return assemble(targets, date_pairs, metadata, captures, paths.data)
