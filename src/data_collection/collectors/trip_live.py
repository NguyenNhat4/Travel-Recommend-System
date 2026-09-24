"""Fresh Vietnamese Trip hotel metadata over HTTP and room prices from JSON.

This adapts the existing Travel collector's city list and HTML parser. Chromium
is used only for the room API that Trip loads after the room section scrolls
into view. Every response belongs to the current run directory.
"""
from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from curl_cffi.requests import AsyncSession
from playwright.async_api import async_playwright

from .common import BrowserOptions, BrowserSession, Paths, StateDB, now_iso
from .plan import DEFAULT_BUDGET, Destination
from .trip_hotels import TripHotels, TripHotelsOptions, parse_hotel_detail

BASE = 'https://vn.trip.com/hotels/detail/?'
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
                             budget=replace(DEFAULT_BUDGET, trip_hotels=scan_per_city),
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


def _capture_path(run_dir: Path, hotel_id: str, day: str, suffix: str) -> Path:
    path = run_dir / 'raw' / 'trip_hotels' / hotel_id / f'{day}.{suffix}'
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def fetch_metadata(targets: list[dict], stay: tuple[str, str], run_dir: Path,
                         options: LiveOptions) -> dict[str, dict | None]:
    semaphore = asyncio.Semaphore(options.http_workers)
    start_lock = asyncio.Lock()
    last_start = 0.0
    out: dict[str, dict | None] = {}

    async def one(target: dict) -> None:
        nonlocal last_start
        hotel_id = target['trip_hotel_id']
        url = detail_url(target, *stay)
        async with semaphore:
            for attempt in range(2):
                async with start_lock:
                    pause = max(0, last_start + random.uniform(options.delay_min, options.delay_max)
                                - asyncio.get_running_loop().time())
                    if pause:
                        await asyncio.sleep(pause)
                    last_start = asyncio.get_running_loop().time()
                try:
                    async with AsyncSession(impersonate='chrome124', timeout=30) as session:
                        response = await session.get(url, headers=HEADERS, allow_redirects=True)
                    if response.status_code != 200 or 'hotelDetailResponse' not in response.text:
                        continue
                    raw_path = _capture_path(run_dir, hotel_id, stay[0], 'html')
                    raw_path.write_text(response.text, encoding='utf-8')
                    out[hotel_id] = parse_hotel_detail(response.text, url, target.get('card') or {}, now_iso(),
                                                        checkin=stay[0], checkout=stay[1], adults=2)
                    return
                except Exception:
                    if attempt == 1:
                        break
        out[hotel_id] = None

    await asyncio.gather(*(one(target) for target in targets))
    return out


def price_packet(payload: dict) -> tuple[str, dict[str, dict], int]:
    """Accept only a real room JSON response; an empty/bad response is unknown."""
    if not isinstance(payload, dict):
        return 'missing', {}, 0
    data = payload.get('data') or {}
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
        if amount <= 0:
            continue
        if room_id not in best or amount < best[room_id]['price']:
            best[room_id] = {'price': round(amount),
                             'occupancy': (sale.get('guestCountInfo') or {}).get('guestCount')}
    if best:
        return 'priced', {'physical': physical, 'best': best}, offers
    if data.get('isRoomListSoldOut') is True and not sales:
        return 'sold_out', {'physical': physical, 'best': {}}, 0
    return 'missing', {}, offers


async def capture_prices(targets: list[dict], date_pairs: list[tuple[str, str]], run_dir: Path,
                         options: LiveOptions) -> dict[tuple[str, str], tuple[str, dict, int, str | None]]:
    jobs = asyncio.Queue()
    for target in targets:
        for checkin, checkout in date_pairs:
            jobs.put_nowait((target, checkin, checkout))
    results = {}
    start_lock = asyncio.Lock()
    last_start = 0.0
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(run_dir / 'trip_price_profile'), headless=False,
            locale='vi-VN', timezone_id='Asia/Ho_Chi_Minh',
            viewport={'width': 1366, 'height': 768},
            args=['--disable-blink-features=AutomationControlled'])
        try:
            async def worker() -> None:
                nonlocal last_start
                while not jobs.empty():
                    try:
                        target, checkin, checkout = jobs.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    hotel_id = target['trip_hotel_id']
                    url = detail_url(target, checkin, checkout)
                    page = await context.new_page()
                    packets: list[dict] = []
                    pending: set[asyncio.Task] = set()
                    browser_html = None
                    async def receive(response) -> None:
                        if 'getHotelRoomListOversea' not in response.url or response.status != 200:
                            return
                        try:
                            body = await response.json()
                            if isinstance(body, dict):
                                packets.append(body)
                        except Exception:
                            pass
                    def on_response(response) -> None:
                        task = asyncio.create_task(receive(response))
                        pending.add(task)
                        task.add_done_callback(pending.discard)
                    page.on('response', on_response)
                    try:
                        await page.route('**/*', lambda route: route.abort()
                                         if route.request.resource_type in ('image', 'media', 'font')
                                         else route.continue_())
                        async with start_lock:
                            pause = max(0, last_start + random.uniform(options.delay_min, options.delay_max)
                                        - asyncio.get_running_loop().time())
                            if pause:
                                await asyncio.sleep(pause)
                            last_start = asyncio.get_running_loop().time()
                        navigation = await page.goto(url, wait_until='domcontentloaded', timeout=60_000)
                        if checkin == date_pairs[0][0] and navigation and navigation.status == 200:
                            # Raw navigation response keeps the SSR blob after React
                            # removes it from the live DOM during hydration.
                            browser_html = await navigation.text()
                        for ratio in (0.55, 0.75, 0.95):
                            await page.evaluate(f'window.scrollTo(0, document.body.scrollHeight * {ratio})')
                            await page.wait_for_timeout(1300)
                        for _ in range(40):
                            if packets:
                                break
                            await page.wait_for_timeout(400)
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)
                    except Exception:
                        pass
                    finally:
                        await page.close()
                    status, data, offers = next((parsed for packet in packets
                                                 if (parsed := price_packet(packet))[0] != 'missing'),
                                                ('missing', {}, 0))
                    if packets:
                        raw_path = _capture_path(run_dir, hotel_id, checkin, 'json')
                        raw_path.write_text(json.dumps(packets, ensure_ascii=False), encoding='utf-8')
                    results[(hotel_id, checkin)] = (status, data, offers, browser_html)
                    print(f'Trip {hotel_id}@{checkin}: {status}, {offers} offers', flush=True)
                    jobs.task_done()
            await asyncio.gather(*(worker() for _ in range(min(options.price_workers, jobs.qsize()))))
        finally:
            await context.close()
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
        record['plan'] = {'destination': target['destination']}
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
