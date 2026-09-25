"""trip.com – khách sạn (nguồn mới 23/09/2026, chỉ tiếng Việt).

CẢNH BÁO ROBOTS.TXT: `/hotels/list`, `/hotels/detail/*` và toàn bộ `/restapi/soa2/*` đều bị robots.txt của
trip.com cấm (kiểm tra thật 23/09/2026: `Disallow: /hotels/list`, `/hotels/detail/?hotelId=*`, `/hoh/`,
`/m/hotels/w/list`, `/restapi/soa2/*` — không có tham số nào né được, giống kết luận đã có trong trip.py cho
khách sạn trước đó). Người dùng đã được báo rõ điều này và chủ động xác nhận chấp nhận rủi ro, cho mục đích
nghiên cứu nội bộ (thực tập RecSys) — xem lịch sử quyết định lúc thêm file này. Vì vậy module này KHÔNG dùng
`Http`/`Robots` như trip.py (sẽ tự chặn mọi request qua `robots.allowed()`), mà dùng `BrowserSession` trực
tiếp như `booking_hotels.py`/`agoda_hotels.py` — cùng tiền lệ trong chính repo này cho các nguồn cần trình
duyệt thật. Để giữ ở mức "nghiên cứu" thay vì cào quy mô lớn: budget nhỏ (`Budget.trip_hotels`, mặc định 15),
rate limit thật, state resumable, và nên bắt đầu chỉ với nhóm `@deep` (xem plan.py) thay vì cả 67 điểm đến.

Cơ chế (kiểm tra thật qua browser 23/09/2026 — xem lịch sử hội thoại lúc thêm file này để đối chiếu):
  trip_hotels  /hotels/list?city=<trip_hotel_city_id>&checkin=&checkout=&adult=&crn=1&curr=VND&locale=vi-VN
                  → SSR trả sẵn ~12 thẻ khách sạn (`div.hotel-card` id=hotelId; `a.hotelName` href đã có sẵn
                    URL chi tiết đầy đủ tham số kể cả `hoteluniquekey`). Cuộn thêm kích hoạt
                    `POST /restapi/soa2/34951/fetchHotelList`, thẻ mới TỰ chèn vào DOM — đọc lại DOM sau khi
                    cuộn là đủ, không cần tự bắt/replay request như repo mẫu làm.
               /hotels/detail/?cityEnName=&cityId=&hotelId=&checkIn=&checkOut=&adult=&children=0&crn=1&
                    curr=VND&locale=vi-VN
                  → HTML ban đầu (NGAY sau khi trang load, TRƯỚC khi React hydrate) có sẵn blob JSON
                    `"hotelDetailResponse":{...}` (đúng kỹ thuật repo mẫu dùng). Blob này BIẾN MẤT khỏi DOM chỉ
                    sau ~1-2 giây vì SPA tự dọn sau hydrate (kiểm tra thật, xác nhận bằng cách gọi lại nhiều
                    lần) — phải đọc `page.content()` NGAY sau `goto()`, KHÔNG dùng độ trễ "settle" kiểu
                    `BrowserSession.fetch_html` (dùng cho booking/agoda) vì sẽ đọc hụt. Gọi lại bằng
                    `fetch()` từ trong trang (không điều hướng thật) đã kiểm chứng là KHÔNG có blob này —
                    bắt buộc phải `page.goto()` thật mỗi lần.
                  → Trường chi tiết (địa chỉ, toạ độ, mô tả, danh sách phòng) parse best-effort từ blob này;
                    trường cơ bản (tên, hạng sao, điểm đánh giá, ảnh, giá hiển thị) đã lấy đủ từ thẻ danh sách
                    nên vẫn có bản ghi dùng được ngay cả khi parse chi tiết thiếu — raw HTML luôn được cache
                    trước khi parse (theo quy ước `RawCache` của repo), sửa parser thì `crawl.py reparse
                    trip-hotels` từ cache, không cần cào lại.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from .common import (
    BlockBreaker,
    BrowserOptions,
    BrowserSession,
    ChallengeBlocked,
    HostRateLimiter,
    JsonlWriter,
    PageGone,
    Paths,
    Progress,
    RawCache,
    StateDB,
    looks_like_challenge,
    now_iso,
    slim_html,
)
from .plan import DEFAULT_BUDGET, DESTINATIONS, Budget, Destination
from .textutil import clean_text, first_float, first_int, parse_price, uniq

log = logging.getLogger("crawler.trip_hotels")

BASE = "https://vn.trip.com"
DETAIL_ANCHOR = '"hotelDetailResponse":'
CARD_SELECTOR = "div.hotel-card"
MAX_SCROLLS = 25  # mỗi vòng tải thêm ~12-20 thẻ qua fetchHotelList; đủ cho budget mặc định 15
STALL_LIMIT = 3   # số vòng cuộn liên tiếp không thêm thẻ mới thì coi như hết (trang không có nút "tải thêm")


def scroll_done(count: int, want: int, stalled: int) -> bool:
    """Dừng cuộn khi đã đủ `want` thẻ, hoặc `stalled` vòng liên tiếp không có thẻ mới (trip.com dùng infinite
    scroll, không có nút bấm như booking.com nên chỉ dừng theo 2 điều kiện này)."""
    return count >= want or stalled >= STALL_LIMIT


@dataclass
class TripHotelsOptions:
    delay: float = 3.0
    limit: int | None = None
    max_attempts: int = 3
    max_blocks: int = 6
    rediscover: bool = False
    discover_only: bool = False
    destinations: tuple[Destination, ...] = DESTINATIONS
    budget: Budget = field(default_factory=lambda: DEFAULT_BUDGET)
    checkin: date | None = None
    nights: int = 1
    adults: int = 2
    browser: BrowserOptions = field(default_factory=BrowserOptions)


class TripHotels:
    source = "trip_hotels"

    def __init__(self, paths: Paths, opts: TripHotelsOptions, state: StateDB):
        self.paths, self.opts, self.state = paths, opts, state
        self.cache = RawCache(paths, self.source)
        self.limiter = HostRateLimiter(opts.delay)
        self.breaker = BlockBreaker(opts.max_blocks)
        self.checkin = opts.checkin or (date.today() + timedelta(days=30))
        self.checkout = self.checkin + timedelta(days=max(1, opts.nights))

    # -- URL

    def search_url(self, city_id: str) -> str:
        params = {
            "city": city_id,
            "checkin": self.checkin.isoformat(),
            "checkout": self.checkout.isoformat(),
            "adult": self.opts.adults,
            "crn": 1,
            "curr": "VND",
            "locale": "vi-VN",
        }
        return f"{BASE}/hotels/list?" + urlencode(params)

    def detail_url(self, hotel_id: str, city_id: str) -> str:
        # URL rút gọn, không kèm `hoteluniquekey`/`masterhotelid_tracelogid` (token theo phiên tìm kiếm, đổi
        # mỗi lần search nên giữ nguyên sẽ làm StateDB coi là URL mới mỗi lần chạy lại) — đã kiểm chứng qua
        # browser 23/09/2026: trang chi tiết vẫn load đủ giá/dữ liệu mà không cần các tham số đó.
        params = {
            "cityId": city_id,
            "hotelId": hotel_id,
            "checkIn": self.checkin.isoformat(),
            "checkOut": self.checkout.isoformat(),
            "adult": self.opts.adults,
            "children": 0,
            "crn": 1,
            "curr": "VND",
            "locale": "vi-VN",
        }
        return f"{BASE}/hotels/detail/?" + urlencode(params)

    # -- discovery (trang danh sách)

    async def discover(self, session: BrowserSession) -> int:
        total = 0
        page = await session.new_page()
        try:
            for dest in self.opts.destinations:
                if not dest.trip_hotel_city_id:
                    continue
                key = f"list:{dest.trip_hotel_city_id}:{self.opts.budget.trip_hotels}:{self.checkin.isoformat()}"
                if not self.opts.rediscover and self.state.is_discovered(self.source, key):
                    continue
                if self.breaker.tripped:
                    break
                cards = await self._collect_cards(page, dest)
                rows = [
                    (
                        self.detail_url(c["hotelId"], dest.trip_hotel_city_id),
                        rank,
                        {"destination": dest.name, "rank": rank, "via": "trip-hotels-search", "card": c},
                    )
                    for rank, c in enumerate(cards[: self.opts.budget.trip_hotels], 1)
                ]
                self.state.add_many(self.source, rows)
                if cards:
                    self.state.mark_discovered(self.source, key, len(rows))
                total += len(rows)
                log.info("[%s] %s: %d khách sạn", self.source, dest.name, len(rows))
        finally:
            await page.close()
        return total

    async def _collect_cards(self, page, dest: Destination) -> list[dict]:
        url = self.search_url(dest.trip_hotel_city_id)
        want = self.opts.budget.trip_hotels
        await self.limiter.wait(url)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        except Exception as e:
            log.warning("[%s] %s: không mở được trang tìm kiếm (%s)", self.source, dest.name, str(e)[:120])
            return []
        await page.wait_for_timeout(1500)
        html = await page.content()
        if looks_like_challenge(html, await page.title()):
            self.breaker.blocked()
            log.warning("[%s] %s: trang thử thách khi tìm kiếm", self.source, dest.name)
            return []
        self.breaker.ok()
        cards = parse_search_cards(html)
        stalled = 0
        for _ in range(MAX_SCROLLS):
            if scroll_done(len(cards), want, stalled):
                break
            await page.mouse.wheel(0, 6000)
            await page.wait_for_timeout(1200)
            html = await page.content()
            new_cards = parse_search_cards(html)
            if len(new_cards) > len(cards):
                stalled = 0
            else:
                stalled += 1
            cards = new_cards
        self.cache.write(f"search-{dest.trip_hotel_city_id}", "html", slim_html(html))
        return cards

    # -- chi tiết (per-hotel)

    async def run(self, session: BrowserSession) -> dict:
        found = await self.discover(session)
        if found:
            log.info("[%s] Kế hoạch: đã xếp hàng %d URL", self.source, found)
        if self.opts.discover_only:
            return self.state.counts(self.source).get(self.source, {})
        urls = self.state.pending(self.source, self.opts.max_attempts)
        if self.opts.limit:
            urls = urls[: self.opts.limit]
        if not urls:
            log.info("[%s] Không còn URL nào cần crawl.", self.source)
            return self.state.counts(self.source).get(self.source, {})
        page = await session.new_page()
        progress = Progress(self.source, len(urls))
        try:
            with JsonlWriter(self.paths.interim / f"{self.source}.jsonl", "a") as writer:
                for url in urls:
                    if self.breaker.tripped:
                        break
                    await self.limiter.wait(url)
                    try:
                        html = await self._fetch_detail_now(page, url)
                    except ChallengeBlocked:
                        self.state.mark(self.source, url, "blocked", "trang thử thách")
                        progress.tick("failed")
                        if self.breaker.blocked():
                            log.error("[%s] Bị chặn %d lần liên tiếp – dừng.", self.source, self.breaker.streak)
                            break
                        self.limiter.penalise(url, self.breaker.cooldown())
                        continue
                    except PageGone:
                        self.state.mark(self.source, url, "gone", "trang không còn tồn tại")
                        progress.tick("skipped")
                        continue
                    if html is None:
                        self.state.mark(self.source, url, "failed", "không mở được trang")
                        progress.tick("failed")
                        continue
                    self.breaker.ok()
                    fetched_at = now_iso()
                    self.cache.write(url, "html", slim_html(html))
                    plan = self.state.plan_of(self.source, url)
                    record = parse_hotel_detail(
                        html, url, plan.get("card") or {}, fetched_at,
                        checkin=self.checkin.isoformat(), checkout=self.checkout.isoformat(), adults=self.opts.adults,
                    )
                    if not record:
                        self.state.mark(self.source, url, "failed", "parse: thiếu tên")
                        progress.tick("failed")
                        continue
                    record["plan"] = {k: v for k, v in plan.items() if k != "card"}
                    writer.write(record)
                    self.state.mark(self.source, url, "done", None, {"fetchedAt": fetched_at})
                    progress.tick("done")
        finally:
            await page.close()
        progress.report()
        result = self.state.counts(self.source).get(self.source, {})
        if self.breaker.tripped:
            result["stopped"] = "blocked"
        return result

    async def _fetch_detail_now(self, page, url: str, timeout: float = 15.0) -> str | None:
        """Đọc HTML chi tiết NGAY sau khi trang load — xem docstring đầu file: blob hotelDetailResponse biến
        mất khỏi DOM rất nhanh sau khi hydrate nên không dùng độ trễ "settle" như BrowserSession.fetch_html."""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        except Exception as e:
            soft = ("ERR_ABORTED", "interrupted by another navigation", "Timeout")
            if not any(x in str(e) or x in type(e).__name__ for x in soft):
                raise
            log.debug("[%s] goto %s: %s – vẫn thử đọc nội dung", self.source, url, str(e)[:120])
        t0 = time.monotonic()
        html = await page.content()
        while DETAIL_ANCHOR not in html and time.monotonic() - t0 < timeout:
            if looks_like_challenge(html, await page.title()):
                raise ChallengeBlocked(f"bị chặn bởi trang thử thách: {url}")
            await page.wait_for_timeout(250)
            html = await page.content()
        if looks_like_challenge(html, await page.title()):
            raise ChallengeBlocked(f"bị chặn bởi trang thử thách: {url}")
        return html

    def reparse(self) -> int:
        out = self.paths.interim / f"{self.source}.jsonl"
        tmp = out.with_suffix(".jsonl.tmp")
        n = 0
        with JsonlWriter(tmp, "w") as writer:
            for url, meta in self.state.done_items(self.source):
                html = self.cache.read(url, "html")
                if not html:
                    continue
                plan = self.state.plan_of(self.source, url)
                rec = parse_hotel_detail(
                    html, url, plan.get("card") or {}, meta.get("fetchedAt") or now_iso(),
                    checkin=self.checkin.isoformat(), checkout=self.checkout.isoformat(), adults=self.opts.adults,
                )
                if rec:
                    rec["plan"] = {k: v for k, v in plan.items() if k != "card"}
                    writer.write(rec)
                    n += 1
        if n == 0 and out.exists():
            tmp.unlink(missing_ok=True)
            log.warning("[%s] Không parse được bản ghi nào từ cache – giữ nguyên %s", self.source, out)
            return 0
        tmp.replace(out)
        log.info("[%s] Parse lại %d trang từ cache → %s", self.source, n, out)
        return n


# ---------------------------------------------------------------------- parsing: trang danh sách


def parse_search_cards(html: str) -> list[dict]:
    """Trang /hotels/list (đã cuộn hoặc chưa) → danh sách thẻ khách sạn theo thứ tự hiển thị.

    div.hotel-card có id=hotelId; Trip có thể dùng a.hotelName kèm href hoặc
    span.hotelName không có href (SSR quan sát 24/09/2026). URL chi tiết chuẩn
    được dựng từ ID bởi TripHotels.detail_url(). Các trường sao, đánh giá, giá
    và ảnh được lấy từ phần tử tương ứng trên thẻ nếu có."""
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    seen: set[str] = set()
    for card in soup.select(CARD_SELECTOR):
        hotel_id = str(card.get("id") or "")
        link = card.select_one("a.hotelName[href]")
        name_el = link or card.select_one("span.hotelName")
        if not hotel_id.isdigit() or name_el is None:
            continue
        name = clean_text(name_el.get_text())
        if not name or hotel_id in seen:
            continue
        seen.add(hotel_id)
        href = link["href"] if link is not None else f"/hotels/detail/?hotelId={hotel_id}"
        url = href if href.startswith("http") else f"{BASE}{href}"
        star_el = card.select_one("div.hotelStar[aria-label]")
        star = first_int(star_el.get("aria-label", "")) if star_el is not None else None
        comment_el = card.select_one("div.hotel-comment")
        comment_text = clean_text(comment_el.get_text(" ")) if comment_el is not None else ""
        score = first_float(comment_text.split("/10")[0]) if "/10" in comment_text else None
        review_count = first_int(comment_text.split("đánh giá")[0].split()[-1]) if "đánh giá" in comment_text else None
        price_el = card.select_one("div.room-price")
        price, currency = (None, None)
        if price_el is not None:
            # Nhiều mức giá trên 1 thẻ theo thứ tự: [mức giảm] [giá gốc gạch ngang] [giá cuối] "Tổng giá: ...".
            # Giá cuối luôn là số cuối cùng xuất hiện TRƯỚC "Tổng giá" (kiểm tra thật 23/09/2026) — lấy số cuối
            # thay vì số đầu (số đầu thường là mức giảm giá, không phải giá bán).
            main = price_el.get_text(" ").split("Tổng giá")[0]
            amounts = re.findall(r"\d[\d.,]*\d", main)
            price, currency = parse_price(amounts[-1], "VND") if amounts else (None, None)
        img_el = card.select_one("img.m-lazyImg__img")
        image = img_el.get("src") if img_el is not None else None
        out.append({
            "hotelId": hotel_id,
            "url": url,
            "name": name,
            "starRating": star,
            "reviewScore": score,
            "reviewScoreScale": 10.0,
            "reviewCount": review_count,
            "listPrice": price,
            "listCurrency": currency or "VND",
            "image": image,
        })
    return out


# ---------------------------------------------------------------------- parsing: trang chi tiết


def extract_anchored_json(html: str, anchor: str) -> dict | None:
    """Tìm `anchor` trong html rồi JSON-decode object cân bằng ngoặc bắt đầu từ dấu `{` ngay sau đó.

    Cần hàm quét độ sâu ngoặc riêng (không dùng regex) vì object này nằm giữa một payload JS lớn hơn nhiều —
    regex không bound an toàn được điểm kết thúc khi bên trong có chuỗi chứa `{`/`}`/dấu ngoặc kép escape."""
    idx = html.find(anchor)
    if idx < 0:
        return None
    start = html.find("{", idx)
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(html)):
        c = html[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[start : i + 1])
                    except json.JSONDecodeError:
                        return None
    return None


def parse_hotel_detail(
    html: str, url: str, card: dict, fetched_at: str,
    *, checkin: str | None = None, checkout: str | None = None, adults: int | None = None,
) -> dict | None:
    """Ghép dữ liệu thẻ danh sách (đáng tin cậy, luôn có) với blob `hotelDetailResponse` (best-effort — cache
    raw HTML đầy đủ ngay cả khi phần này parse thiếu, sửa sau bằng `crawl.py reparse trip-hotels`)."""
    detail = extract_anchored_json(html, DETAIL_ANCHOR) or {}
    base = detail.get("hotelBaseInfo") or {}
    name_info = base.get("nameInfo") or {}
    name = clean_text(card.get("name") or name_info.get("name") or name_info.get("nameLocale"))
    hotel_id = card.get("hotelId") or base.get("masterHotelId")
    if not name or not hotel_id:
        return None

    geo = base.get("position") or base.get("positionInfo") or {}
    coord = (geo.get("mapCoordinate") or [{}])[0] if isinstance(geo.get("mapCoordinate"), list) else geo
    address_info = base.get("addressInfo") or base.get("address") or {}

    room_list, physic_map = _room_data(detail)
    rooms = _rooms_from_physic_map(physic_map, room_list)

    prices = [r["minPrice"] for r in rooms if r.get("minPrice")]
    min_price = min(prices) if prices else card.get("listPrice")

    return {
        "recordType": "trip_hotel",
        "source": "trip_hotels",
        "key": f"hotel:{hotel_id}",
        "hotelId": str(hotel_id),
        "url": url,
        "name": name,
        "propertyType": clean_text((base.get("hotelCategory") or {}).get("categoryName")) or None,
        "description": clean_text(base.get("introduction") or base.get("description")) or None,
        "address": clean_text(address_info.get("address") or address_info.get("addressDesc")) or None,
        "province": clean_text(geo.get("provinceName") or geo.get("cityName")) or None,
        "city": clean_text(geo.get("cityName")) or None,
        "latitude": _to_float(coord.get("latitude")),
        "longitude": _to_float(coord.get("longitude")),
        "starRating": card.get("starRating") or base.get("star") or (base.get("hotelStar") or {}).get("star"),
        "reviewScore": card.get("reviewScore"),
        "reviewScoreScale": card.get("reviewScoreScale") or 10.0,
        "reviewCount": card.get("reviewCount"),
        "facilities": uniq(
            clean_text(x.get("title") if isinstance(x, dict) else x)
            for x in ((base.get("highlightsModule") or {}).get("highlightsItemList") or [])
        ),
        "images": uniq([card.get("image")] + _room_images(physic_map))[:15],
        "rooms": rooms,
        "minPrice": min_price,
        "currency": card.get("listCurrency") or "VND",
        "priceQuery": {"checkin": checkin, "checkout": checkout, "adults": adults, "currency": card.get("listCurrency") or "VND"},
        "crawledAt": fetched_at,
    }


def _room_data(detail: dict) -> tuple[list[dict], dict]:
    for key in ("roomListResponse", "roomList", "hotelRoomList"):
        node = detail.get(key)
        if isinstance(node, dict) and "roomList" in node:
            return node.get("roomList") or [], node.get("physicRoomMap") or {}
    return [], {}


def _rooms_from_physic_map(physic_map: dict, room_list: list[dict]) -> list[dict]:
    offers_per_room: dict[str, int] = {}
    for group in room_list:
        key = str(group.get("key") or "")
        offers_per_room[key] = len(group.get("subRoomList") or [])
    out = []
    for room_id, info in physic_map.items():
        if not isinstance(info, dict):
            continue
        images = [
            p.get("url") for p in (info.get("pictureInfo") or []) if isinstance(p, dict) and p.get("url")
        ]
        out.append({
            "roomId": str(room_id),
            "name": clean_text(info.get("name")),
            "bed": None,
            "facilities": [],
            "sizeM2": None,
            "maxOccupancy": None,
            "conditions": [],
            "minPrice": None,  # giá theo gói (subRoomList/roomToken) cần gọi riêng getHotelRoomListOversea –
                                # chưa xác nhận đủ trường qua recon, để None thay vì đoán (xem docstring đầu file)
            "currency": "VND",
            "rateCount": offers_per_room.get(str(room_id), 0),
            "images": images[:5],
        })
    return out


def _room_images(physic_map: dict) -> list[str]:
    out: list[str] = []
    for info in physic_map.values():
        if not isinstance(info, dict):
            continue
        for p in (info.get("pictureInfo") or [])[:2]:
            if isinstance(p, dict) and p.get("url"):
                out.append(p["url"])
    return out


def _to_float(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


async def run(paths: Paths, opts: TripHotelsOptions, state: StateDB) -> dict:
    async with BrowserSession(paths, "trip_hotels", opts.browser) as session:
        crawler = TripHotels(paths, opts, state)
        return await crawler.run(session)


def reparse(paths: Paths, state: StateDB) -> int:
    return TripHotels(paths, TripHotelsOptions(), state).reparse()
