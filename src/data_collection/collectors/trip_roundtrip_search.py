"""Observed round-trip fares from Trip's Vietnamese public flight-search UI.

Same browser collection as trip_business: search outbound, take the recommended
return, read the whole-journey fare modal. One modal lists every cabin, so one
search yields economy and business totals. No login, checkout or challenge
solving; a denied search is a failure, never "sold out".
"""
from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlsplit

from .common import RawCache, now_iso

# Exact labels only; a mixed-cabin label ("Thương Gia (chiều đi)") stays unknown.
CABINS = {'hạng phổ thông': 'ECONOMY', 'phổ thông': 'ECONOMY', 'phổ thông đặc biệt': 'PREMIUM_ECONOMY',
          'hạng phổ thông đặc biệt': 'PREMIUM_ECONOMY', 'thương gia': 'BUSINESS', 'hạng thương gia': 'BUSINESS',
          'hạng nhất': 'FIRST'}
_TIMES = re.compile(r'lúc (\d\d:\d\d), (\d+) tháng (\d+), (\d{4})')
_FLIGHT = re.compile(r'Thông tin máy bay: ([^,\n]+), ([A-Z0-9]{2}\d{1,4}),')

# Selectors inspected against the public UI on 2026-09-30 (desktop layout).
CAPTURE = """() => {
 const visible=e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length);
 if([...document.querySelectorAll('button')].some(e=>visible(e)&&e.innerText.trim()==='Tải lại'))return null;
 const legs=[...document.querySelectorAll('[aria-label]')].filter(e=>visible(e)&&/^Chặng \\d+/.test(e.getAttribute('aria-label')||''))
  .map(e=>e.getAttribute('aria-label').replace(/\\s+/g,' ').trim());
 const cards=[];
 for(const cabin of document.querySelectorAll('[data-testid="mid_result_item_class_cabin"]')) {
  if(!visible(cabin))continue;
  const card=cabin.closest('.J_brandedFarePolicy');
  if(!card)continue;
  const prices=card.querySelectorAll('[data-mid-fare-price="true"]');
  if(prices.length!==1||!prices[0].innerText.includes('₫'))continue;
  cards.push({cabin:(cabin.getAttribute('aria-label')||cabin.innerText).replace(/\\s+/g,' ').trim(),
   price:Number(prices[0].getAttribute('data-price')), roundTrip:/Khứ hồi/.test(card.innerText),
   payment:(card.innerText.match(/Hình thức thanh toán:\\s*([^\\n]+)/)||[])[1]||null});
 }
 return {legs, cards, separateTickets:/tách thành nhiều đặt vé/.test(document.body.innerText)};
}"""


DENIED = (403, 429, 432)  # 432 = Trip "whaleguard block"
BLOCK_WAIT_SECONDS = 45


async def open_search(page, url: str, what: str, *, retries: int = 1):
    """Open a search page; on HTTP 432 wait 45 s and try again (once by default). Still denied → raise."""
    for attempt in range(retries + 1):
        response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        status = response.status if response is not None else None
        if status not in DENIED:
            return response
        if status != 432 or attempt == retries:
            raise RuntimeError(f'{what} denied: HTTP {status}')
        await asyncio.sleep(BLOCK_WAIT_SECONDS)


def _city(code: str) -> str:
    return 'NHA' if code.upper() == 'CXR' else code.upper()  # Trip lists Cam Ranh under city NHA


def _leg(text: str, number: int) -> dict | None:
    times = _TIMES.findall(text)
    flight = _FLIGHT.search(text)
    if not text.startswith(f'Chặng {number} ') or len(times) != 2 or not flight:
        return None
    dep, arr = [datetime.fromisoformat(f'{int(y):04}-{int(m):02}-{int(d):02}T{t}:00+07:00') for t, d, m, y in times]
    if arr <= dep or (arr - dep).total_seconds() > 6 * 3600:
        return None
    return {'airline': flight[1].strip(), 'flightNumber': flight[2], 'departureAt': dep.isoformat(),
            'arrivalAt': arr.isoformat(), 'durationMinutes': int((arr - dep).total_seconds() / 60)}


def parse_roundtrip(capture: dict, origin: str, destination: str) -> list[dict]:
    """Fail closed. Return the cheapest verified total per cabin for one nonstop out/in pairing."""
    try:
        legs = capture.get('legs') or []
        if len(legs) != 2:  # exactly one nonstop leg each way
            return []
        go, back = _leg(legs[0], 1), _leg(legs[1], 2)
        observed = datetime.fromisoformat(capture['observedAt'].replace('Z', '+00:00'))
        url = urlsplit(capture['url'])
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
    except (KeyError, TypeError, ValueError, AttributeError):
        return []
    if not go or not back or not observed.tzinfo or back['departureAt'] <= go['arrivalAt']:
        return []
    if (url.scheme != 'https' or url.hostname != 'vn.trip.com' or params.get('triptype', '').upper() != 'RT'
            or params.get('quantity') != '1' or _city(params.get('dcity', '')) != _city(origin)
            or _city(params.get('acity', '')) != _city(destination)
            or params.get('ddate') != go['departureAt'][:10] or params.get('rdate') != back['departureAt'][:10]
            or params.get('midpolicyid') != f"1:{_city(destination)}-{_city(origin)}:{back['flightNumber']}"):
        return []
    best: dict[str, dict] = {}
    for card in capture.get('cards') or []:
        cabin = CABINS.get(re.sub(r'\s+', ' ', str(card.get('cabin') or '')).strip().lower())
        price = card.get('price')
        if not cabin or card.get('roundTrip') is not True or type(price) is not int or price <= 0:
            continue
        if cabin not in best or price < best[cabin]['price']:
            best[cabin] = {'cabinClass': cabin, 'cabinLabel': card['cabin'], 'price': price,
                           'payment': card.get('payment')}
    return [{**fare, 'originAirport': origin, 'destinationAirport': destination, 'outbound': go, 'inbound': back,
             'currency': 'VND', 'separateTickets': capture.get('separateTickets') is True,
             'observedAt': capture['observedAt'], 'url': capture['url']} for fare in best.values()]


async def collect(page, origin: str, destination: str, day: date, stay: int, pairs: int, delay: float,
                  cache: RawCache) -> list[dict]:
    """Up to `pairs` outbound cards, each with its recommended (first) return. Raw captures, parsed in normalise."""
    return_day = day + timedelta(days=stay)
    url = 'https://vn.trip.com/flights/showfarefirst?' + urlencode(dict(
        dcity=origin.lower(), acity=destination.lower(), ddate=day.isoformat(), rdate=return_day.isoformat(),
        triptype='rt', **{'class': 'y'}, quantity=1, sort='recommended'))
    captures = []
    for index in range(pairs):
        await open_search(page, url, 'round-trip search')
        outbound = page.locator('[data-testid^="u-flight-card-"] [data-testid="u_select_btn"]')
        await outbound.first.wait_for(state='visible', timeout=45000)
        if await outbound.count() <= index:
            break
        await outbound.nth(index).click(timeout=10000)
        await page.wait_for_url('**/ShowFareNext**', timeout=30000)
        inbound = page.locator('[data-testid^="u-flight-card-"] [data-testid="u_select_btn"]')
        await inbound.first.wait_for(state='visible', timeout=45000)
        await inbound.first.click(timeout=10000)
        await page.locator('[data-testid="mid_result_item_class_cabin"]').first.wait_for(state='visible', timeout=15000)
        captured = await page.evaluate(CAPTURE)
        if captured:
            captured.update(url=page.url, observedAt=now_iso())
            cache.write_json(f'{origin}-{destination}-{day}-{stay}-{index}', captured)
            if parse_roundtrip(captured, origin, destination):
                captures.append(captured)
        await asyncio.sleep(max(2.0, delay))
    return captures
