"""Observed business fares from Trip's Vietnamese public flight-search UI.

User-requested browser collection for the internal demo, like trip_hotels; kept
separate from the robots-aware SEO collector. No login, checkout or challenge
solving. A denied/challenged search is recorded as failed, never as sold out.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlsplit, parse_qs
from zoneinfo import ZoneInfo

from .common import JsonlWriter, Paths, RawCache, now_iso
from .trip_roundtrip_search import open_search

log = logging.getLogger('crawler')
DEFAULT_ROUTES = {('HAN', 'SGN'), ('SGN', 'HAN'), ('HAN', 'DAD'), ('SGN', 'DAD'), ('SGN', 'PQC'), ('HAN', 'CXR')}


def parse_quote(quote: dict) -> dict | None:
    """Fail closed: the price and cabin must come from the same visible fare card."""
    if not re.fullmatch(r'Thương Gia(?: \([^\n]+\))?', quote.get('cabin', ''), re.I):
        return None
    if type(quote.get('price')) is not int or quote['price'] <= 0 or quote.get('currency') not in (None, 'VND'):
        return None
    text = quote.get('flight', '')
    times = re.findall(r'lúc (\d\d:\d\d), (\d+) tháng (\d+), (\d{4})', text)
    flight = re.search(r'Thông tin máy bay: ([^,\n]+), ([A-Z0-9]{2}\d{1,4}),', text)
    if len(times) != 2 or not flight or 'Chặng 2' in text:
        return None
    try:
        dep, arr = [datetime.fromisoformat(f'{int(y):04}-{int(m):02}-{int(d):02}T{t}:00+07:00') for t,d,m,y in times]
        observed = datetime.fromisoformat(quote['observedAt'].replace('Z', '+00:00'))
        url = urlsplit(quote['url'])
        params = parse_qs(url.query)
        origin, destination = params['dcity'][0].upper(), params['acity'][0].upper()
        # Trip's observed policy IDs use city NHA for Cam Ranh airport CXR.
        policy_origin, policy_destination = (('NHA' if code == 'CXR' else code) for code in (origin, destination))
        if (url.scheme != 'https' or url.hostname != 'vn.trip.com'
                or not observed.tzinfo or params.get('ddate') != [dep.date().isoformat()]
                or params.get('triptype') != ['ow'] or params.get('class') != ['c']
                or params.get('quantity') != ['1']
                or params.get('midpolicyid') != [f'1:{policy_origin}-{policy_destination}:{flight[2]}']):
            return None
    except (KeyError, ValueError):
        return None
    if arr <= dep or (arr-dep).total_seconds() > 6*3600:
        return None
    return {**quote, 'originAirport': origin, 'destinationAirport': destination, 'airline': flight[1], 'flightNumber': flight[2], 'departureAt': dep.isoformat(),
            'arrivalAt': arr.isoformat(), 'durationMinutes': int((arr-dep).total_seconds()/60)}


# Selectors inspected against the public UI on 2026-09-30. Each policy card has
# exactly one data-mid-fare-price and its own mid_result_item_class_cabin.
CAPTURE = """() => {
 const visible=e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length);
 if([...document.querySelectorAll('button')].some(e=>visible(e)&&e.innerText.trim()==='Tải lại'))return null;
 const legs=[...document.querySelectorAll('[aria-label]')].filter(e=>visible(e)&&/^Chặng \\d+/.test(e.getAttribute('aria-label')||''));
 if(legs.length!==1)return null;
 for(const cabin of document.querySelectorAll('[data-testid="mid_result_item_class_cabin"]')) {
  if(!visible(cabin))continue;
  let card=cabin.closest('.J_brandedFarePolicy');
  if(!card)continue;
  let prices=card.querySelectorAll('[data-mid-fare-price="true"]');
  if(prices.length!==1||!prices[0].innerText.includes('₫'))continue;
  return {flight:legs[0].getAttribute('aria-label').replace(/\\s+/g,' ').trim(),
   price:Number(prices[0].getAttribute('data-price')),currency:'VND',
   cabin:cabin.getAttribute('aria-label')||cabin.innerText,
   payment:(card.innerText.match(/Hình thức thanh toán:\\s*([^\\n]+)/)||[])[1]||null};
 }
 return null;
}"""


async def collect_route(page, route: dict, day: date, limit: int, delay: float, cache: RawCache) -> list[dict]:
    origin, destination = route['fromAirports'][0], route['toAirports'][0]
    url = 'https://vn.trip.com/flights/showfarefirst?' + urlencode(dict(
        dcity=origin.lower(), acity=destination.lower(), ddate=day.isoformat(), triptype='ow',
        **{'class': 'c'}, quantity=1, sort='recommended'))
    await open_search(page, url, 'business search')
    buttons = page.get_by_role('button', name='Chọn giá này', exact=True)
    await buttons.first.wait_for(state='visible', timeout=45000)
    quotes = []
    for index in range(min(limit, await buttons.count())):
        await buttons.nth(index).click(timeout=10000)
        try:
            await page.locator('[data-testid="mid_result_item_class_cabin"]').first.wait_for(state='visible', timeout=15000)
            captured = await page.evaluate(CAPTURE)
            if captured:
                captured.update(url=page.url, observedAt=now_iso())
                cache.write_json(f'{origin}-{destination}-{day}-{index}', captured)
                parsed = parse_quote(captured)
                if parsed and parsed['departureAt'][:10] == day.isoformat():
                    quotes.append(captured)
        finally:
            await page.get_by_role('button', name='Đóng', exact=True).click(timeout=10000)
        await asyncio.sleep(max(2.0, delay))
    return quotes


def parse_days(spec: str) -> tuple[int, ...]:
    """'1-29' or '7,14,21' → relative departure days (0..29)."""
    days = set()
    for part in str(spec).split(','):
        part = part.strip()
        if not part:
            continue
        lo, _, hi = part.partition('-')
        days.update(range(int(lo), int(hi or lo) + 1))
    if not days or min(days) < 0 or max(days) > 29:
        raise ValueError('fare days must be within 0..29')
    return tuple(sorted(days))


def state_path(paths: Paths) -> Path:
    """Fresh runs get a new data dir each time; the rotation must survive them (CATALOG_STATE_DIR)."""
    root = os.environ.get('CATALOG_STATE_DIR')
    return (Path(root) if root else paths.state) / 'trip_fares_rotation.json'


def plan_tasks(routes: list[dict], today: date, days, stays, state: dict, business: bool = True) -> list[dict]:
    """Every (route, day) business search and (route, day, stay) round-trip search, least recently tried first.

    Untried tasks come first, nearest departure first, so a budget-limited run fills the window over several runs.
    """
    tasks = []
    for offset in days:
        day = today + timedelta(days=offset)
        for order, route in enumerate(routes):
            pair = f"{route['fromAirports'][0]}-{route['toAirports'][0]}"
            if business:
                tasks.append({'key': f'ow-business:{pair}:{day}', 'kind': 'business', 'route': route, 'day': day,
                              'order': order})
            for stay in stays:
                tasks.append({'key': f'rt:{pair}:{day}:{stay}', 'kind': 'roundtrip', 'route': route, 'day': day,
                              'stay': stay, 'order': order})
    return sorted(tasks, key=lambda t: ((state.get(t['key']) or {}).get('lastAttemptAt') or '', t['day'], t['order'],
                                        t.get('stay', 0)))


def _save_state(path: Path, state: dict, today: date) -> None:
    keep = {k: v for k, v in state.items() if k.split(':')[2] >= today.isoformat()}
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(keep, ensure_ascii=False, indent=1) + '\n')
    temp.replace(path)


async def enrich(paths: Paths, *, offsets=tuple(range(1, 30)), max_flights=4, delay=2.5, routes=(),
                 stays=(3, 5, 7), pairs=2, minutes=30.0, deadline=None, max_failures=3) -> dict:
    """Business one-way and round-trip fares, rotated across runs within a time budget.

    `deadline` (time.monotonic) is the source's hard stop; work ends 3 minutes before it so the
    source can still flush interim files. Only exceptions count as failures; an empty search does not.
    """
    from playwright.async_api import async_playwright
    from . import trip_roundtrip_search
    if (not offsets or any(n < 0 or n > 29 for n in offsets) or not 1 <= max_flights <= 50
            or any(n < 1 or n > 29 for n in stays) or not 1 <= pairs <= 10 or minutes < 0):
        raise ValueError('fare days must be 0..29, stays 1..29, max_flights 1..50, pairs 1..10')
    report = {'searches': 0, 'quotes': 0, 'roundTripQuotes': 0, 'failed': 0, 'empty': 0, 'planned': 0, 'left': 0}
    interim = paths.interim / 'trip_flights.jsonl'
    if not interim.exists() or minutes == 0:
        return report
    latest = {}
    for line in interim.read_text().splitlines():
        row = json.loads(line)
        if row.get('key'):
            latest[row['key']] = row
    selected = set(routes) if routes else DEFAULT_ROUTES
    plans = sorted((r for r in latest.values() if r.get('fromAirports') and r.get('toAirports')
                    and (r['fromAirports'][0], r['toAirports'][0]) in selected),
                   key=lambda r: (r['fromAirports'][0], r['toAirports'][0]))
    if not plans:
        return report
    today = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date()
    store = state_path(paths)
    try:
        state = json.loads(store.read_text())
    except (FileNotFoundError, ValueError):
        state = {}
    tasks = plan_tasks(plans, today, offsets, stays, state)
    report['planned'] = len(tasks)
    stop = time.monotonic() + minutes * 60
    if deadline is not None:
        stop = min(stop, deadline - 180)
    cache = RawCache(paths, 'trip_business')
    streak = 0
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context(locale='vi-VN', timezone_id='Asia/Ho_Chi_Minh')
            page = await context.new_page()
            with JsonlWriter(interim, 'a') as writer:
                for done, task in enumerate(tasks):
                    if time.monotonic() >= stop or streak >= max_failures:
                        report['left'] = len(tasks) - done
                        if streak >= max_failures:
                            report['stopped'] = 'failures'  # likely blocked: stop instead of hammering the site
                        break
                    route, day = task['route'], task['day']
                    entry = state.setdefault(task['key'], {})
                    entry['lastAttemptAt'] = now_iso()
                    report['searches'] += 1
                    try:
                        if task['kind'] == 'business':
                            quotes = await collect_route(page, route, day, max_flights, delay, cache)
                            field, counter = 'businessQuotes', 'quotes'
                        else:
                            quotes = await trip_roundtrip_search.collect(
                                page, route['fromAirports'][0], route['toAirports'][0], day, task['stay'],
                                pairs, delay, cache)
                            field, counter = 'roundTripQuotes', 'roundTripQuotes'
                    except Exception as exc:
                        report['failed'] += 1
                        streak += 1
                        entry['lastError'] = type(exc).__name__
                        log.warning('trip.fares.failed task=%s kind=%s', task['key'], type(exc).__name__)
                        _save_state(store, state, today)
                        continue
                    streak = 0
                    entry.pop('lastError', None)
                    if quotes:
                        # Keep SEO observation time intact; each quote owns its timestamp.
                        writer.write({**route, field: quotes})
                        report[counter] += len(quotes)
                        entry['lastSuccessAt'] = entry['lastAttemptAt']
                    else:
                        report['empty'] += 1
                        log.info('trip.fares.no_verified_quotes task=%s', task['key'])
                    _save_state(store, state, today)
                    await asyncio.sleep(max(2.0, delay))
        finally:
            await browser.close()
    log.info('trip.fares.complete %s', report)
    return report
