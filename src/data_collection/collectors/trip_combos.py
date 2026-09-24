"""trip.com – combo chuyến bay + khách sạn (`/packages/`, nguồn mới 23/09/2026, chỉ tiếng Việt, chỉ tuyến
nội địa từ 2 sân bay cửa ngõ lớn nhất tới các điểm đến đã có `trip_hotel_city_id`).

CẢNH BÁO ROBOTS.TXT: giống hệt collectors/trip_hotels.py — `/packages/` không bị robots.txt cấm theo path
riêng, NHƯNG toàn bộ dữ liệu (chuyến bay + khách sạn trong combo) đều tải qua các API `/restapi/soa2/*`
(`FlightHotelHomePageService`, `FlightSelectSearch`, `getHotelList`...) — CÙNG nhóm bị cấm broad-brush như
khách sạn (kiểm tra thật 23/09/2026: `Disallow: /restapi/soa2/*`). Không hợp lệ hơn trip_hotels.py; cùng một
quyết định người dùng đã xác nhận chấp nhận rủi ro cho mục đích nghiên cứu nội bộ — xem docstring
collectors/trip_hotels.py và lịch sử hội thoại lúc thêm 2 file này. Dùng `BrowserSession` trực tiếp, không
qua `Http`/`Robots`, cùng lý do đã giải thích ở trip_hotels.py.

Cơ chế (kiểm tra thật qua browser 23/09/2026 — xem lịch sử hội thoại lúc thêm file này):
  trip_combos  /packages/list?adult=&child=0&infants=0&aCityCode=<IATA đến>&dCityCode=<IATA đi>&
                    tripWay=round-trip&classType=ys&dDate=&rDate=&hCity=<trip_hotel_city_id>&iDate=&oDate=&
                    room=1&locale=vi-VN&curr=VND
                  → URL này KHÔNG cần phiên tìm kiếm trước (khác giả định ban đầu) — điều hướng thẳng bằng
                    URL với ngày tuỳ ý vẫn tự dựng lại kết quả đúng (kiểm chứng: đổi ngày tuỳ ý, kết quả khớp
                    ngày mới). Trang render phía client (không có blob JSON nhúng sẵn như /hotels/detail/),
                    nên phải đợi nội dung thật load rồi đọc DOM.
                  → Thẻ chuyến bay: `div.fcc-card` (mặc định có 1 thẻ `.fcc-card--selected` = rẻ nhất/gợi ý) —
                    2 `div.fcc-segment` (đi + về) mỗi cái có `fcc-segment-date`, `fcc-airline-logo` (mã hãng
                    trong tên file ảnh), `fcc-time`/`fcc-airport` (giờ+sân bay đi/đến), `fcc-segment-duration`.
                    KHÔNG có giá riêng trên thẻ chuyến bay — giá combo nằm ở thẻ khách sạn.
                  → Thẻ khách sạn: `div.hotel-card-vs`, thuộc tính `data-exposure-content` chứa sẵn
                    `HotelId=<id>&RoomId=<id>&FltHotelPrice=<giá combo/người, đã gồm thuế phí>` — đáng tin cậy
                    hơn parse text hiển thị. Cuộn thêm tải thêm thẻ (infinite scroll, giống trang khách sạn
                    thường). Không có URL/permalink riêng cho từng combo (chọn bằng nút "Chọn", không phải
                    link) — trường `url` trong bản ghi lưu URL trang tìm kiếm dùng chung, giống cách
                    `trip_experiences` (trip.py) lưu `listUrl` vì lý do tương tự.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from .common import (
    BlockBreaker,
    BrowserOptions,
    BrowserSession,
    HostRateLimiter,
    JsonlWriter,
    Paths,
    RawCache,
    StateDB,
    looks_like_challenge,
    now_iso,
    slim_html,
)
from .plan import DEFAULT_BUDGET, DESTINATIONS, Budget, Destination
from .textutil import clean_text, first_float, first_int, parse_price

log = logging.getLogger("crawler.trip_combos")

BASE = "https://vn.trip.com"
HOTEL_CARD_SELECTOR = "div.hotel-card-vs"
FLIGHT_CARD_SELECTOR = "div.fcc-card"
MAX_SCROLLS = 6
EXPOSURE_RE = re.compile(r"HotelId=(\d+).*?RoomId=(\d+).*?FltHotelPrice=(\d+)")
HUB_NAMES = ("TP. Hồ Chí Minh", "Hà Nội")  # 2 cửa ngõ lớn nhất – xem docstring: phạm vi v1 cố tình nhỏ


@dataclass
class TripComboOptions:
    delay: float = 3.0
    limit: int | None = None
    max_blocks: int = 6
    rediscover: bool = False
    destinations: tuple[Destination, ...] = DESTINATIONS
    budget: Budget = field(default_factory=lambda: DEFAULT_BUDGET)
    depart: date | None = None
    nights: int = 3
    adults: int = 2
    browser: BrowserOptions = field(default_factory=BrowserOptions)


def combo_routes(destinations: tuple[Destination, ...]) -> list[tuple[Destination, Destination]]:
    """(gốc, đích) cho mỗi cặp cửa ngõ lớn → điểm đến khác đã có cả sân bay lẫn trip_hotel_city_id.
    Cố tình nhỏ (2 gốc × còn lại) thay vì mọi cặp trong 67 điểm đến — xem docstring đầu file."""
    by_name = {d.name: d for d in destinations}
    hubs = [by_name[n] for n in HUB_NAMES if n in by_name and by_name[n].airports]
    targets = [d for d in destinations if d.airports and d.trip_hotel_city_id]
    return [(hub, dest) for hub in hubs for dest in targets if dest.name != hub.name]


class TripCombos:
    source = "trip_combos"

    def __init__(self, paths: Paths, opts: TripComboOptions, state: StateDB):
        self.paths, self.opts, self.state = paths, opts, state
        self.cache = RawCache(paths, self.source)
        self.limiter = HostRateLimiter(opts.delay)
        self.breaker = BlockBreaker(opts.max_blocks)
        self.depart = opts.depart or (date.today() + timedelta(days=21))
        self.return_ = self.depart + timedelta(days=max(1, opts.nights))

    def search_url(self, origin_iata: str, dest_iata: str, hotel_city_id: str) -> str:
        params = {
            "adult": self.opts.adults, "child": 0, "infants": 0,
            "aCityCode": dest_iata, "dCityCode": origin_iata,
            "tripWay": "round-trip", "classType": "ys",
            "dDate": self.depart.isoformat(), "rDate": self.return_.isoformat(),
            "hCity": hotel_city_id, "iDate": self.depart.isoformat(), "oDate": self.return_.isoformat(),
            "room": 1, "locale": "vi-VN", "curr": "VND",
        }
        return f"{BASE}/packages/list?" + urlencode(params)

    async def run(self, session: BrowserSession) -> dict:
        routes = combo_routes(self.opts.destinations)
        if self.opts.limit:
            routes = routes[: self.opts.limit]
        page = await session.new_page()
        written = skipped = 0
        try:
            with JsonlWriter(self.paths.interim / f"{self.source}.jsonl", "a") as writer:
                for origin, dest in routes:
                    if self.breaker.tripped:
                        break
                    key = f"route:{origin.airports[0]}-{dest.airports[0]}:{self.depart.isoformat()}"
                    if not self.opts.rediscover and self.state.is_discovered(self.source, key):
                        skipped += 1
                        continue
                    n = await self._one_route(page, writer, origin, dest)
                    self.state.mark_discovered(self.source, key, n)
                    written += n
                    log.info("[%s] %s → %s: %d combo", self.source, origin.name, dest.name, n)
        finally:
            await page.close()
        log.info("[%s] Xong: %d bản ghi mới, %d tuyến đã có trước đó (bỏ qua)", self.source, written, skipped)
        result = {"done": written, "skippedRoutes": skipped}
        if self.breaker.tripped:
            result["stopped"] = "blocked"
        return result

    async def _one_route(self, page, writer: JsonlWriter, origin: Destination, dest: Destination) -> int:
        url = self.search_url(origin.airports[0], dest.airports[0], dest.trip_hotel_city_id)
        await self.limiter.wait(url)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        except Exception as e:
            log.warning("[%s] %s→%s: không mở được trang (%s)", self.source, origin.name, dest.name, str(e)[:120])
            return 0
        want = self.opts.budget.trip_combos
        html = await self._wait_for_cards(page)
        if html is None:
            if self.breaker.blocked():
                log.error("[%s] Bị chặn %d lần liên tiếp – dừng.", self.source, self.breaker.streak)
            return 0
        self.breaker.ok()
        stalled = 0
        hotel_cards = _count(html, HOTEL_CARD_SELECTOR)
        for _ in range(MAX_SCROLLS):
            if hotel_cards >= want or stalled >= 3:
                break
            await page.mouse.wheel(0, 4000)
            await page.wait_for_timeout(1200)
            html = await page.content()
            now = _count(html, HOTEL_CARD_SELECTOR)
            stalled = 0 if now > hotel_cards else stalled + 1
            hotel_cards = now
        self.cache.write(f"{origin.airports[0]}-{dest.airports[0]}-{self.depart.isoformat()}", "html", slim_html(html))
        fetched_at = now_iso()
        flight = parse_flight_card(html)
        records = parse_combo_hotels(html, flight, origin, dest, url, fetched_at)[:want]
        for rec in records:
            writer.write(rec)
        return len(records)

    async def _wait_for_cards(self, page, timeout_ms: int = 20_000) -> str | None:
        try:
            await page.wait_for_selector(HOTEL_CARD_SELECTOR, timeout=timeout_ms)
        except Exception:
            html = await page.content()
            if looks_like_challenge(html, await page.title()):
                return None
            return html  # có thể tuyến này thật sự không có combo (vd trip.com không bán) – để parser quyết
        return await page.content()


def _count(html: str, selector: str) -> int:
    return len(BeautifulSoup(html, "lxml").select(selector))


# ---------------------------------------------------------------------- parsing: thẻ chuyến bay


def parse_flight_card(html: str) -> dict | None:
    """Thẻ chuyến bay đang chọn (mặc định rẻ nhất) → tóm tắt chặng đi/về. Không có giá riêng trên thẻ này."""
    soup = BeautifulSoup(html, "lxml")
    card = soup.select_one("div.fcc-card--selected") or soup.select_one(FLIGHT_CARD_SELECTOR)
    if card is None:
        return None
    segments = []
    for seg in card.select("div.fcc-segment"):
        logo = seg.select_one("img.fcc-airline-logo")
        airline_code = None
        if logo is not None and logo.get("src"):
            m = re.search(r"/([a-z0-9]+)\.png", logo["src"])
            airline_code = m.group(1).upper() if m else None
        depart = seg.select_one("div.fcc-depart")
        arrive = seg.select_one("div.fcc-arrive")
        segments.append({
            "date": clean_text(node_text_or_none(seg.select_one(".fcc-segment-date"))),
            "airlineCode": airline_code,
            "cabin": clean_text(node_text_or_none(seg.select_one(".fcc-segment-cabin"))),
            "durationText": clean_text(node_text_or_none(seg.select_one(".fcc-segment-duration"))),
            "departTime": clean_text(node_text_or_none(depart.select_one(".fcc-time") if depart else None)),
            "departAirport": clean_text(node_text_or_none(depart.select_one(".fcc-airport") if depart else None)),
            "arriveTime": clean_text(node_text_or_none(arrive.select_one(".fcc-time") if arrive else None)),
            "arriveAirport": clean_text(node_text_or_none(arrive.select_one(".fcc-airport") if arrive else None)),
        })
    if not segments:
        return None
    return {"outbound": segments[0], "inbound": segments[1] if len(segments) > 1 else None}


def node_text_or_none(el) -> str | None:
    return el.get_text() if el is not None else None


# ---------------------------------------------------------------------- parsing: thẻ khách sạn (combo)


def parse_combo_hotels(html: str, flight: dict | None, origin: Destination, dest: Destination, url: str, fetched_at: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    seen: set[str] = set()
    for card in soup.select(HOTEL_CARD_SELECTOR):
        exposure = card.get("data-exposure-content") or ""
        m = EXPOSURE_RE.search(exposure)
        if not m:
            continue
        hotel_id, room_id, price = m.groups()
        if hotel_id in seen:
            continue
        seen.add(hotel_id)
        name_el = card.select_one(".title-info .title span")
        name = clean_text(name_el.get_text()) if name_el is not None else None
        if not name:
            continue
        stars = len(card.select(".title-info i.jji-star"))
        position = clean_text(node_text_or_none(card.select_one(".position-info")))
        score = first_float(node_text_or_none(card.select_one(".com-score")))
        review_count_el = card.select_one("[data-analyze-aria-text^='reviews_']")
        review_count = first_int(node_text_or_none(review_count_el))
        room_type = clean_text(node_text_or_none(card.select_one(".room-info-name")))
        separate_price_el = card.select_one(".origin-price-content")
        separate_price, _ = parse_price(node_text_or_none(separate_price_el), "VND") if separate_price_el is not None else (None, None)
        img_el = card.select_one("img.m-lazyImg__img")
        image = img_el.get("src") if img_el is not None else None
        out.append({
            "recordType": "trip_combo",
            "source": "trip_combos",
            "key": f"combo:{origin.airports[0]}-{dest.airports[0]}:{hotel_id}",
            "url": url,
            "fromCode": origin.airports[0],
            "toCode": dest.airports[0],
            "fromCity": origin.name,
            "toCity": dest.name,
            "destination": dest.name,
            "departDate": flight["outbound"]["date"] if flight and flight.get("outbound") else None,
            "returnDate": flight["inbound"]["date"] if flight and flight.get("inbound") else None,
            "flight": flight,
            "hotelId": hotel_id,
            "roomId": room_id,
            "hotelName": name,
            "starRating": stars or None,
            "position": position,
            "reviewScore": score,
            "reviewScoreScale": 10.0 if score is not None else None,
            "reviewCount": review_count,
            "roomType": room_type,
            "price": int(price),
            "currency": "VND",
            "separatePrice": separate_price,
            "image": image,
            "crawledAt": fetched_at,
        })
    return out


async def run(paths: Paths, opts: TripComboOptions, state: StateDB) -> dict:
    async with BrowserSession(paths, "trip_combos", opts.browser) as session:
        crawler = TripCombos(paths, opts, state)
        return await crawler.run(session)


_CACHE_KEY_RE = re.compile(r"^([A-Z]{3})-([A-Z]{3})-(\d{4}-\d{2}-\d{2})$")


def reparse(paths: Paths) -> int:
    """Parse lại từ cache HTML thô (data/raw/trip_combos/html/*.html.gz), không gọi mạng. Khoá cache là
    `<iata gốc>-<iata đích>-<ngày đi>` (xem TripCombos._one_route) nên suy lại được Destination qua DESTINATIONS."""
    by_iata = {code: d for d in DESTINATIONS for code in d.airports}
    cache = RawCache(paths, "trip_combos")
    out = paths.interim / "trip_combos.jsonl"
    tmp = out.with_suffix(".jsonl.tmp")
    n = 0
    html_dir = cache.dir / "html"
    with JsonlWriter(tmp, "w") as writer:
        for f in sorted(html_dir.glob("*.html.gz")) if html_dir.is_dir() else []:
            m = _CACHE_KEY_RE.match(f.name.removesuffix(".html.gz"))
            if not m or m.group(1) not in by_iata or m.group(2) not in by_iata:
                continue
            origin, dest = by_iata[m.group(1)], by_iata[m.group(2)]
            html = cache.read(f.name.removesuffix(".html.gz"), "html")
            if not html:
                continue
            url = TripCombos(paths, TripComboOptions(), None).search_url(origin.airports[0], dest.airports[0], dest.trip_hotel_city_id or "")
            flight = parse_flight_card(html)
            for rec in parse_combo_hotels(html, flight, origin, dest, url, now_iso()):
                writer.write(rec)
                n += 1
    if n == 0 and out.exists():
        tmp.unlink(missing_ok=True)
        log.warning("[trip_combos] Không parse được bản ghi nào từ cache – giữ nguyên %s", out)
        return 0
    tmp.replace(out)
    log.info("[trip_combos] Parse lại %d bản ghi từ cache → %s", n, out)
    return n
