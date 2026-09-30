"""Observed business fares from Trip's Vietnamese public flight-search UI.

User-requested browser collection for the internal demo, like trip_hotels; kept
separate from the robots-aware SEO collector. No login, checkout or challenge
solving. A denied/challenged search is recorded as failed, never as sold out.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlencode, urlsplit, parse_qs
from zoneinfo import ZoneInfo

from .common import JsonlWriter, Paths, RawCache, now_iso

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
    response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
    if response is not None and response.status in (403, 429):
        raise RuntimeError(f'business search denied: HTTP {response.status}')
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


async def enrich(paths: Paths, *, offsets=(14,), max_flights=8, delay=2.5, routes=()) -> dict:
    from playwright.async_api import async_playwright
    if not offsets or any(n < 0 or n > 29 for n in offsets) or not 1 <= max_flights <= 50:
        raise ValueError('business offsets must be 0..29; max_flights must be 1..50')
    interim = paths.interim / 'trip_flights.jsonl'
    if not interim.exists():
        return {'quotes': 0, 'searches': 0, 'failed': 0}
    latest = {}
    for line in interim.read_text().splitlines():
        row = json.loads(line)
        if row.get('key'):
            latest[row['key']] = row
    selected = set(routes) if routes else DEFAULT_ROUTES
    plans = [r for r in latest.values() if r.get('fromAirports') and r.get('toAirports')
             and (r['fromAirports'][0], r['toAirports'][0]) in selected]
    report = {'quotes': 0, 'searches': 0, 'failed': 0}
    if not plans:
        return report
    cache = RawCache(paths, 'trip_business')
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context(locale='vi-VN', timezone_id='Asia/Ho_Chi_Minh')
            page = await context.new_page()
            with JsonlWriter(interim, 'a') as writer:
                for route in plans:
                    for offset in offsets:
                        day = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date() + timedelta(days=offset)
                        report['searches'] += 1
                        try:
                            quotes = await collect_route(page, route, day, max_flights, delay, cache)
                        except Exception as exc:
                            report['failed'] += 1
                            log.warning('trip.business.failed route=%s day=%s kind=%s', route['key'], day, type(exc).__name__)
                            continue
                        if quotes:
                            # Keep SEO observation time intact; each business quote owns its timestamp.
                            writer.write({**route, 'businessQuotes': quotes})
                            report['quotes'] += len(quotes)
                        else:
                            report['failed'] += 1
                            log.warning('trip.business.no_verified_quotes route=%s day=%s', route['key'], day)
                        await asyncio.sleep(max(2.0, delay))
        finally:
            await browser.close()
    log.info('trip.business.complete %s', report)
    return report
