"""trip.com – vé máy bay nội địa, điểm tham quan, tour/hoạt động (handbook §3: nguồn flight + attraction cho gợi ý
chéo tuần 3, giờ mở cửa / thời lượng / vị trí cho trợ lý lịch trình tuần 4).

Không cần trình duyệt: trip.com trả trang SEO đầy đủ cho User-Agent khai báo là crawler.
Tôn trọng robots.txt: trang tìm chuyến bay (/flights/*-to-*/tickets-*, showfarefirst, graphql) và toàn bộ mảng
khách sạn (/hotels/list, /hotels/Detail/*, /hoh/, /m/hotels/w/list...) bị cấm nên KHÔNG cào 2 mảng này (kiểm tra
robots.txt thật ngày 22-23/09/2026, chặn theo path nên không có tham số nào né được — không thử thêm nữa).
`/things-to-do/list` (tour & hoạt động) chỉ cấm 1 path con hẹp (`/*/locales/*`) nên dùng được.

  trip_flights      /flights/airport-<iata>/        → danh sách tuyến bay từ mỗi sân bay trong kế hoạch
                    /flights/<a>-to-<b>/airfares-…/ → JSON-LD: giá thấp/cao theo tháng, các chuyến cụ thể
                                                      (số hiệu, hãng, sân bay, giờ bay, thời gian bay, giá)
  trip_attractions  /travel-guide/attraction/<city>/tourist-attractions/ (+ trang lọc theo loại)
                    /travel-guide/attraction/<city>/<poi>-<id>/  → __NEXT_DATA__: tên, giới thiệu, địa chỉ, toạ độ,
                                                      giờ mở cửa, thời lượng đề xuất, giá vé, điểm, loại hình
  trip_experiences  /things-to-do/list?citytype=dt&pagetype=city&keyword=<tên điểm đến>&pshowcode=1daytrip
                                                    → __NEXT_DATA__ chứa sẵn danh sách tour/vé hoạt động (tên, giá,
                                                      điểm đánh giá, số đánh giá, lượt đặt, thời lượng, ảnh) ngay
                                                      trong trang đầu, không cần ghé từng trang chi tiết — trang chi
                                                      tiết (/things-to-do/detail/<id>) KHÔNG có __NEXT_DATA__ hữu ích,
                                                      phần còn lại tải qua /restapi/soa2/* (bị robots.txt cấm) nên bỏ.
                                                      Chưa tìm được cách phân trang hợp lệ → mỗi điểm đến chỉ lấy
                                                      được trang đầu (~12 mục); tổng thật thường cao hơn nhiều
                                                      (vd. Nha Trang 231 hoạt động thật, mới lấy được 12). Không có
                                                      toạ độ trong dữ liệu này — record để trống, chưa nối vào
                                                      normalise.py (raw interim only, xem README/ghi chú bàn giao).

Cache raw chỉ giữ JSON-LD và phần dữ liệu sản phẩm của __NEXT_DATA__; review và tên người đánh giá bị bỏ
trước khi ghi đĩa (handbook: product data, not people data).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import quote_plus

from .common import (
    BlockBreaker,
    HostRateLimiter,
    Http,
    JsonlWriter,
    Paths,
    Progress,
    RawCache,
    StateDB,
    now_iso,
    slim_html,
)
from .plan import DEFAULT_BUDGET, DESTINATIONS, Budget, Destination
from .textutil import clean_text, first_int, html_to_text, uniq

log = logging.getLogger("crawler.trip")

BASE = "https://vn.trip.com"
HEADERS = {"Accept-Language": "vi-VN,vi;q=0.9", "Accept": "text/html,application/xhtml+xml"}
ROUTE_RE = re.compile(r"/flights/([a-z0-9-]+)-to-([a-z0-9-]+)/airfares-([a-z]{3})-([a-z]{3})/")
POI_RE = re.compile(r"(?:https?://vn\.trip\.com)?/travel-guide/attraction/([a-z0-9-]+)/([a-z0-9-]+-(\d+))(?=[/?\"'#]|$)")
TYPE_PAGE_RE = re.compile(r"/travel-guide/attraction/[a-z0-9-]+-\d+/tourist-attractions/type-[a-z0-9-]+")
NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
LD_RE = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)
PEOPLE_KEYS = re.compile(r"review|comment(?!Score|Count)|username|nickname|avatar|userInfo|author", re.I)


@dataclass
class TripOptions:
    delay: float = 2.5
    limit: int | None = None
    max_attempts: int = 3
    max_blocks: int = 6
    rediscover: bool = False
    discover_only: bool = False
    refresh: bool = False
    routes: tuple[tuple[str, str], ...] = ()
    destinations: tuple[Destination, ...] = DESTINATIONS
    budget: Budget = field(default_factory=lambda: DEFAULT_BUDGET)


class TripCrawler:
    source = ""

    def __init__(self, paths: Paths, opts: TripOptions, state: StateDB):
        self.paths, self.opts, self.state = paths, opts, state
        self.cache = RawCache(paths, self.source)
        self.shared_cache = RawCache.shared(paths, self.source)  # trang danh sách: tải một lần cho mọi job batch
        self.limiter = HostRateLimiter(opts.delay)
        self.http = Http(self.limiter)
        self.breaker = BlockBreaker(opts.max_blocks)

    # -- mạng
    async def get_html(self, url: str) -> tuple[str, str | None]:
        """→ (trạng thái, html). Trạng thái: ok | gone | blocked | failed | robots."""
        try:
            r = await self.http.get(url, headers=HEADERS)
        except PermissionError:
            return "robots", None
        except Exception as e:
            log.debug("[%s] lỗi mạng %s: %s", self.source, url, e)
            return "failed", None
        text = r.text
        if r.status_code in (404, 410):
            return "gone", None
        if r.status_code in (403, 429) or "<title>Challenge Validation" in text[:3000]:
            return "blocked", None
        if r.status_code != 200:
            return "failed", None
        return "ok", text

    async def close(self) -> None:
        await self.http.close()

    # -- khung crawl
    async def discover(self) -> int:
        raise NotImplementedError

    def extract(self, html: str) -> dict | None:
        raise NotImplementedError

    def parse(self, payload: dict, url: str) -> dict | None:
        raise NotImplementedError

    async def run(self) -> dict:
        try:
            found = await self.discover()
            if found:
                log.info("[%s] Kế hoạch: đã xếp hàng %d URL", self.source, found)
            if self.opts.discover_only:
                return self.state.counts(self.source).get(self.source, {})
            if self.opts.refresh and self.source == "trip_flights":
                self.state.conn.executemany(
                    "UPDATE items SET status='pending', attempts=0 WHERE source=? AND url=?",
                    [(self.source, u) for u in getattr(self, "discovered_urls", [])])
                self.state.conn.commit()
            urls = self.state.pending(self.source, self.opts.max_attempts)
            if self.source == "trip_flights":
                allowed = set(getattr(self, "discovered_urls", []))
                urls = [u for u in urls if u in allowed]
            if self.opts.limit:
                urls = urls[: self.opts.limit]
            if not urls:
                log.info("[%s] Không còn URL nào cần crawl. Trạng thái: %s", self.source, self.state.counts(self.source).get(self.source))
                return self.state.counts(self.source).get(self.source, {})
            progress = Progress(self.source, len(urls))
            log.info("[%s] Bắt đầu %d URL · tối thiểu %.1fs/request", self.source, len(urls), self.opts.delay)
            with JsonlWriter(self.paths.interim / f"{self.source}.jsonl", "a") as writer:
                for url in urls:
                    if self.breaker.tripped:
                        break
                    status, html = await self.get_html(url)
                    if status == "blocked":
                        self.state.mark(self.source, url, "blocked", "403/429/challenge")
                        progress.tick("failed")
                        if self.breaker.blocked():
                            log.error("[%s] Bị chặn %d lần liên tiếp – dừng. Chạy lại sau vài giờ.", self.source, self.breaker.streak)
                            break
                        self.limiter.penalise(url, self.breaker.cooldown())
                        continue
                    if status != "ok":
                        self.state.mark(self.source, url, {"gone": "gone", "robots": "skipped"}.get(status, "failed"), status)
                        progress.tick("skipped" if status in ("gone", "robots") else "failed")
                        continue
                    self.breaker.ok()
                    payload = self.extract(html)
                    if not payload:
                        self.state.mark(self.source, url, "failed", "không tìm thấy dữ liệu có cấu trúc")
                        progress.tick("failed")
                        continue
                    payload["url"] = url
                    payload["fetchedAt"] = now_iso()
                    self.cache.write_json("snapshot-" + hashlib.sha256((url + payload["fetchedAt"]).encode()).hexdigest()[:24], payload)
                    self.cache.write_json(url, payload)
                    record = self.parse(payload, url)
                    if not record:
                        self.state.mark(self.source, url, "failed", "parse: thiếu tên")
                        progress.tick("failed")
                        continue
                    plan = self.state.plan_of(self.source, url)
                    if plan:
                        record["plan"] = plan
                    record["crawledAt"] = payload["fetchedAt"]
                    writer.write(record)
                    self.state.mark(self.source, url, "done", None, {"fetchedAt": record["crawledAt"]})
                    progress.tick("done")
            progress.report()
            result = self.state.counts(self.source).get(self.source, {})
            if self.breaker.tripped:
                result["stopped"] = "blocked"
            return result
        finally:
            await self.close()

    def reparse(self) -> int:
        out = self.paths.interim / f"{self.source}.jsonl"
        tmp = out.with_suffix(".jsonl.tmp")
        n = 0
        done = dict(self.state.done_items(self.source))
        with JsonlWriter(tmp, "w") as writer:
            # đọc thẳng mọi file cache (không phụ thuộc state DB); URL được lưu kèm trong payload
            for f in sorted((self.cache.dir / "json").glob("*.json.gz")) if (self.cache.dir / "json").is_dir() else []:
                with gzip.open(f, "rt", encoding="utf-8") as fh:
                    payload = json.loads(fh.read())
                url = payload.get("url")
                if not url:
                    continue
                rec = self.parse(payload, url)
                if rec:
                    plan = self.state.plan_of(self.source, url)
                    if plan:
                        rec["plan"] = plan
                    rec["crawledAt"] = payload.get("fetchedAt") or (done.get(url) or {}).get("fetchedAt")
                    writer.write(rec)
                    n += 1
        if n == 0 and out.exists():
            tmp.unlink(missing_ok=True)
            log.warning("[%s] Không parse được bản ghi nào từ cache – giữ nguyên %s", self.source, out)
            return 0
        tmp.replace(out)
        log.info("[%s] Parse lại %d trang từ cache → %s", self.source, n, out)
        return n

    async def cached_page(self, key: str, url: str) -> str | None:
        """Trang danh sách dùng cho tìm URL: đọc cache nếu có (trừ --rediscover)."""
        html = None if self.opts.rediscover else self.shared_cache.read(key, "html")
        if html is None and not self.opts.rediscover:
            html = self.cache.read(key, "html")  # cache riêng của job từ các lần chạy trước khi có cache chung
        if html is not None:
            return html
        status, html = await self.get_html(url)
        if status != "ok":
            log.warning("[%s] không mở được %s (%s)", self.source, url, status)
            return None
        self.shared_cache.write(key, "html", slim_html(html))
        return html


# ---------------------------------------------------------------------- flights


class TripFlights(TripCrawler):
    source = "trip_flights"

    async def discover(self) -> int:
        airports = uniq(a for d in self.opts.destinations for a in d.airports)
        if self.opts.routes:
            # Job batch: chỉ tải trang của các sân bay xuất hiện trong --routes (đầu đi và đầu đến), không tải cả 20+ sân bay.
            needed = {code for pair in self.opts.routes for code in pair}
            airports = [a for a in airports if a in needed]
        pages: dict[str, list[tuple[str, str, str]]] = {}
        trip_code: dict[str, str] = {}  # IATA → mã thành phố trong URL của Trip
        for iata in airports:
            html = await self.cached_page(f"airport-{iata.lower()}", f"{BASE}/flights/airport-{iata.lower()}/")
            if not html:
                continue
            routes = [(m.group(0), m.group(3), m.group(4)) for m in ROUTE_RE.finditer(html)]
            routes = list(dict.fromkeys(routes))
            if routes:
                # URL tuyến dùng mã thành phố của Trip (Nha Trang là "nha", sân bay CXR), không phải mã IATA của sân bay.
                # Mã của sân bay này là mã đi xuất hiện nhiều nhất trên chính trang của nó.
                trip_code[iata] = Counter(r[1] for r in routes).most_common(1)[0][0]
                pages[iata] = routes
        iata_of = {code: iata for iata, code in trip_code.items()}
        rows = []
        # Cả hai đầu đều phải là sân bay đã tải. Có --routes thì so theo cặp IATA (tuyến đi → đến) đã yêu cầu.
        for iata, routes in pages.items():
            for path, a, b in routes:
                if a in iata_of and b in iata_of and a != b:
                    if self.opts.routes and (iata_of[a], iata_of[b]) not in self.opts.routes:
                        continue
                    rows.append((BASE + path, 50, {"via": "trip-airport", "airport": iata, "from": a, "to": b}))
        if rows:
            self.state.add_many(self.source, rows)
        self.discovered_urls = [r[0] for r in rows]
        log.info("[%s] %d sân bay trong kế hoạch → %d tuyến nội địa giữa các điểm đến", self.source, len(pages), len(rows))
        return len(rows)

    def extract(self, html: str) -> dict | None:
        nodes = _ld_nodes(html)
        if not any(n.get("@type") in ("Product", "Flight") for n in nodes):
            return None
        return {"ld": [n for n in nodes if n.get("@type") in ("Product", "Flight", "BreadcrumbList")]}

    def parse(self, payload: dict, url: str) -> dict | None:
        return parse_route(payload, url)


def parse_route(payload: dict, url: str) -> dict | None:
    nodes = payload.get("ld") or []
    m = ROUTE_RE.search(url)
    if not m:
        return None
    from_slug, to_slug, from_code, to_code = m.groups()
    product = next((n for n in nodes if n.get("@type") == "Product"), {})
    places = [p.get("name") for p in product.get("itinerary") or [] if isinstance(p, dict)]
    from_city = clean_text(places[0]) if places else from_slug.replace("-", " ").title()
    to_city = clean_text(places[-1]) if len(places) > 1 else to_slug.replace("-", " ").title()

    def offer(kind: str) -> dict:
        for o in product.get("offers") or []:
            if isinstance(o, dict) and str(o.get("@id", "")).endswith(f"#{kind}"):
                monthly = [
                    {"month": (s.get("validFrom") or "")[:7], "price": s.get("price"), "cheapest": s.get("description") == "Cheapest month"}
                    for s in o.get("priceSpecification") or []
                    if isinstance(s, dict) and s.get("price")
                ]
                return {"lowPrice": o.get("lowPrice"), "highPrice": o.get("highPrice"), "currency": o.get("priceCurrency"), "monthly": monthly}
        return {}

    flights = []
    round_trips = []
    for n in nodes:
        if n.get("@type") != "Flight":
            continue
        node_id = str(n.get("@id", "")).split("#")[-1]
        o = n.get("offers") if isinstance(n.get("offers"), dict) else {}
        item = {
            "flightNumber": n.get("flightNumber"),
            "airline": (n.get("provider") or {}).get("name"),
            "airlineCode": (n.get("provider") or {}).get("iataCode"),
            "from": (n.get("departureAirport") or {}).get("iataCode"),
            "fromAirport": (n.get("departureAirport") or {}).get("name"),
            "to": (n.get("arrivalAirport") or {}).get("iataCode"),
            "toAirport": (n.get("arrivalAirport") or {}).get("name"),
            "departureTime": n.get("departureTime"),
            "arrivalTime": n.get("arrivalTime"),
            "durationMinutes": _iso_minutes(n.get("estimatedFlightDuration")),
            "nonstop": n.get("isNonstop"),
            "price": o.get("price"),
            "currency": o.get("priceCurrency"),
            "priceValidUntil": o.get("priceValidUntil"),
        }
        if node_id.startswith("flight-"):
            flights.append(item)
        elif node_id.startswith("rt-"):
            round_trips.append({**item, "leg": "out" if node_id.startswith("rt-out") else "in"})
    if not product and not flights:
        return None
    durations = [f["durationMinutes"] for f in flights + round_trips if f.get("durationMinutes")]
    return {
        "recordType": "trip_route",
        "source": "trip_flights",
        "key": f"route:{from_code}-{to_code}",
        "url": url,
        "fromCode": from_code,
        "toCode": to_code,
        "fromCity": from_city,
        "toCity": to_city,
        "fromAirports": uniq(f["from"] for f in flights + [r for r in round_trips if r["leg"] == "out"] if f.get("from")),
        "toAirports": uniq(f["to"] for f in flights if f.get("to")),
        "airlines": uniq(f["airline"] for f in flights + round_trips if f.get("airline")),
        "oneWay": offer("one-way"),
        "roundTrip": offer("round-trip"),
        "minDurationMinutes": min(durations) if durations else None,
        "flights": flights,
        "roundTripLegs": round_trips,
    }


def _iso_minutes(value: str | None) -> int | None:
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?$", value or "")
    if not m or not (m.group(1) or m.group(2)):
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


# ---------------------------------------------------------------------- attractions


class TripAttractions(TripCrawler):
    source = "trip_attractions"

    async def discover(self) -> int:
        want = self.opts.budget.trip_attractions
        total = 0
        for dest in self.opts.destinations:
            if not dest.trip_city:
                continue
            key = f"list:{dest.trip_city}:{want}"
            if not self.opts.rediscover and self.state.is_discovered(self.source, key):
                continue
            list_url = f"{BASE}/travel-guide/attraction/{dest.trip_city}/tourist-attractions/"
            html = await self.cached_page(f"list-{dest.trip_city}", list_url)
            if not html:
                continue
            pois = _poi_links(html)
            type_pages = list(dict.fromkeys(TYPE_PAGE_RE.findall(html)))
            for path in type_pages[:6]:
                if len(pois) >= want:
                    break
                extra = await self.cached_page(f"list-{path.rsplit('/', 1)[-1]}-{dest.trip_city}", BASE + path + "/")
                if extra:
                    pois.extend(u for u in _poi_links(extra) if u not in pois)
            rows = [
                (u, rank, {"destination": dest.name, "rank": rank, "via": "trip-list", "city": dest.trip_city})
                for rank, u in enumerate(pois[:want], 1)
            ]
            self.state.add_many(self.source, rows)
            if pois:
                self.state.mark_discovered(self.source, key, len(rows))
            total += len(rows)
            log.info("[%s] %s: %d điểm tham quan", self.source, dest.name, len(rows))
        return total

    def extract(self, html: str) -> dict | None:
        m = NEXT_DATA_RE.search(html)
        app = {}
        if m:
            try:
                app = json.loads(m.group(1))["props"]["pageProps"]["initialState"]["appData"]
            except (json.JSONDecodeError, KeyError, TypeError):
                app = {}
        keep = {k: _scrub(app.get(k)) for k in ("poiData", "overviewData", "openTimeCellVO", "entryPolicyInfo", "urlCityName") if app.get(k) is not None}
        ld = [n for n in _ld_nodes(html) if n.get("@type") in ("Product", "BreadcrumbList", "TouristAttraction", "Place")]
        if not keep.get("poiData") and not ld:
            return None
        return {"appData": keep, "ld": ld}

    def parse(self, payload: dict, url: str) -> dict | None:
        return parse_attraction(payload, url)


def parse_attraction(payload: dict, url: str) -> dict | None:
    app = payload.get("appData") or {}
    poi = app.get("poiData") or {}
    overview = app.get("overviewData") or {}
    basic = overview.get("basicInfo") or {}
    product = next((n for n in payload.get("ld") or [] if n.get("@type") == "Product"), {})
    name = clean_text(poi.get("poiName") or basic.get("poiName") or product.get("name"))
    if not name:
        return None
    m = POI_RE.search(url)
    poi_id = poi.get("poiId") or basic.get("poiId") or (m.group(3) if m else None)
    open_info = app.get("openTimeCellVO") or overview.get("openInfo") or {}
    tickets = overview.get("ticketsAndToursInfo") or {}
    coord = basic.get("coordinate") or {}
    images = product.get("image") if isinstance(product.get("image"), list) else ([product["image"]] if product.get("image") else [])
    if not images:
        # Điểm không bán vé không có node Product trong JSON-LD, nhưng ảnh vẫn nằm trong dữ liệu trang.
        images = [x.get("imageUrl") for x in (poi.get("poiImage") or []) if isinstance(x, dict)]
        images += [x for x in ((overview.get("imageInfo") or {}).get("imageList") or []) if isinstance(x, str)]
        if poi.get("defaultUrl"):
            images.append(poi["defaultUrl"])
    crumbs = [clean_text(x.get("name")) for x in (overview.get("districtPathInfo") or poi.get("districtPathInfo") or []) if isinstance(x, dict)]
    return {
        "recordType": "trip_attraction",
        "source": "trip_attractions",
        "key": f"attraction:{poi_id}",
        "poiId": poi_id,
        "url": url.split("?")[0],
        "name": name,
        "englishName": clean_text(poi.get("poiEnglishName") or basic.get("poiEnglishName")),
        "introduction": html_to_text(basic.get("introduction")),
        "seoDescription": clean_text(product.get("description")),
        "address": clean_text(poi.get("address") or basic.get("address")),
        "district": clean_text(poi.get("districtName") or (overview.get("districtInfo") or {}).get("districtName")),
        "province": crumbs[0] if crumbs else None,
        "latitude": _to_float(poi.get("gglat") or coord.get("latitude")),
        "longitude": _to_float(poi.get("gglon") or coord.get("longitude")),
        "rating": _to_float(poi.get("rating") or (overview.get("comment") or {}).get("commentScore")),
        "ratingScale": 5,
        "reviewCount": first_int(str((overview.get("comment") or {}).get("commentCount") or "")),
        "hotScore": _to_float(poi.get("hotScore") or basic.get("hotScore")),
        "tags": uniq(clean_text(t.get("tagName") or t.get("name")) for t in (poi.get("tags") or poi.get("tagInfoList") or []) if isinstance(t, dict)),
        "rankInfo": clean_text((poi.get("rankInfo") or overview.get("rankInfo") or {}).get("description")),
        "suggestedDuration": clean_text(poi.get("suggestedDuration")),
        "openingHours": _opening_hours(open_info.get("openTimeDetailDesc") or open_info.get("openTimeDesc")),
        "openingHoursDetail": clean_text(open_info.get("openTimeTips")),
        "entryPolicies": uniq(clean_text(x.get("name")) for x in ((app.get("entryPolicyInfo") or {}).get("entryPolicyItemList") or []) if isinstance(x, dict)),
        "price": first_int(str(tickets.get("priceInt") or tickets.get("price") or "").split(".")[0]),
        "currency": "VND" if tickets.get("priceInt") or tickets.get("price") else None,
        "images": [i for i in uniq(images) if isinstance(i, str) and i.startswith("http")][:12],
    }


# ---------------------------------------------------------------------- tour & hoạt động (things-to-do)


class TripExperiences(TripCrawler):
    """1 trang danh sách/điểm đến chứa sẵn nhiều sản phẩm (khác khung 1-URL-1-bản-ghi của Attractions/Flights ở trên),
    nên tự viết run() thay vì dùng discover()/extract()/parse() của lớp cha."""

    source = "trip_experiences"

    async def run(self) -> dict:
        try:
            want = self.opts.budget.trip_experiences
            written = skipped_dest = 0
            with JsonlWriter(self.paths.interim / f"{self.source}.jsonl", "a") as writer:
                for dest in self.opts.destinations:
                    if self.breaker.tripped:
                        break
                    key = f"xp:{dest.name}"
                    if not self.opts.rediscover and self.state.is_discovered(self.source, key):
                        skipped_dest += 1
                        continue
                    url = f"{BASE}/things-to-do/list?citytype=dt&pagetype=city&keyword={quote_plus(dest.booking_query)}&pshowcode=1daytrip"
                    status, html = await self.get_html(url)
                    if status == "blocked":
                        self.state.mark_discovered(self.source, key, 0)  # tránh dò lại URL vừa bị chặn ngay lượt sau
                        if self.breaker.blocked():
                            log.error("[%s] Bị chặn %d lần liên tiếp – dừng. Chạy lại sau vài giờ.", self.source, self.breaker.streak)
                            break
                        self.limiter.penalise(url, self.breaker.cooldown())
                        continue
                    if status != "ok":
                        log.warning("[%s] %s: không mở được trang (%s)", self.source, dest.name, status)
                        continue
                    self.breaker.ok()
                    cards, total_real = _experience_cards(html)
                    n = 0
                    for card in cards[:want]:
                        rec = parse_experience(card, dest.name, url)
                        if rec:
                            rec["crawledAt"] = now_iso()
                            writer.write(rec)
                            n += 1
                    self.state.mark_discovered(self.source, key, n)
                    written += n
                    log.info("[%s] %s: %d hoạt động (trang đầu có %d, trip.com báo tổng %s)",
                              self.source, dest.name, n, len(cards), total_real if total_real is not None else "?")
            log.info("[%s] Xong: %d bản ghi mới, %d điểm đến đã lấy trước đó (bỏ qua)", self.source, written, skipped_dest)
            return {"done": written, "skippedDestinations": skipped_dest}
        finally:
            await self.close()


def _experience_cards(html: str) -> tuple[list[dict], int | None]:
    """→ (danh sách card thô, tổng số hoạt động thật trip.com báo cáo)."""
    m = NEXT_DATA_RE.search(html)
    if not m:
        return [], None
    try:
        page_model = json.loads(m.group(1))["props"]["pageProps"]["initialState"]["__STATE_MAP__"]["PageModel"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return [], None
    cards: list[dict] = []
    total: int | None = None
    for node in (page_model.get("mixList") or {}).values():
        cd = (node or {}).get("cardData") or {}
        if isinstance(cd.get("total"), int):
            total = cd["total"] if total is None else max(total, cd["total"])
        for c in cd.get("cardList") or []:
            data = c.get("data")
            if isinstance(data, dict) and data.get("title") and data.get("id"):
                cards.append(data)
    return cards, total


def parse_experience(card: dict, destination: str, list_url: str) -> dict | None:
    name = clean_text(card.get("title"))
    if not name:
        return None
    price_info = card.get("priceInfo") or {}
    price_text = "".join(p.get("text", "") for p in (price_info.get("price") or []) if isinstance(p, dict) and p.get("type") == "price")
    price = int(re.sub(r"\D", "", price_text)) if price_text and re.search(r"\d", price_text) else None
    image = card.get("image") or (card.get("imageInfo") or {}).get("url")
    url = card.get("url")
    return {
        "recordType": "trip_experience",
        "source": "trip_experiences",
        "key": f"experience:{card.get('id')}",
        "experienceId": card.get("id"),
        "url": url.split("?")[0] if url else None,
        "listUrl": list_url,
        "destination": destination,
        "name": name,
        "rating": _to_float(card.get("score")),
        "ratingScale": 5,
        "reviewCount": first_int(str(card.get("reviewsCount") or "")),
        "salesText": clean_text(card.get("sales")),
        "activityTags": uniq(clean_text(t) for t in (card.get("activityTags") or []) if isinstance(t, str)),
        "price": price,
        "currency": "VND" if price is not None else None,
        "image": image if isinstance(image, str) and image.startswith("http") else None,
    }


def _opening_hours(text: str | None) -> str | None:
    """Bỏ phần phụ thuộc thời điểm crawl: 'Mở cửa ngày mai lúc 08:30–20:00' → '08:30–20:00'."""
    t = clean_text(text)
    t = re.sub(r"^(Giờ mở cửa:|Đang mở cửa|Đã đóng cửa|Sắp đóng cửa|Mở cửa (hôm nay|ngày mai) lúc)\s*", "", t, flags=re.I)
    return t.strip(" ·,") or None


def _poi_links(html: str) -> list[str]:
    out: list[str] = []
    for m in POI_RE.finditer(html):
        if m.group(2).startswith("tourist-attractions"):
            continue
        url = f"{BASE}/travel-guide/attraction/{m.group(1)}/{m.group(2)}/"
        if url not in out:
            out.append(url)
    return out


def _ld_nodes(html: str) -> list[dict]:
    nodes: list[dict] = []
    for m in LD_RE.finditer(html):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict):
                nodes.extend(x for x in item.get("@graph", [item]) if isinstance(x, dict))
    return nodes


def _scrub(obj):
    """Bỏ mọi khoá liên quan tới review / người dùng (giữ commentScore, commentCount)."""
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items() if not PEOPLE_KEYS.search(k) or k in ("comment",)}
    if isinstance(obj, list):
        return [_scrub(x) for x in obj]
    return obj


def _to_float(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


_CRAWLERS = {"trip_flights": TripFlights, "trip_attractions": TripAttractions, "trip_experiences": TripExperiences}


async def run(paths: Paths, which: str, opts: TripOptions, state: StateDB) -> dict:
    crawler = _CRAWLERS.get(which, TripAttractions)(paths, opts, state)
    return await crawler.run()


def reparse(paths: Paths, which: str, state: StateDB) -> int:
    crawler = _CRAWLERS.get(which, TripAttractions)(paths, TripOptions(), state)
    return crawler.reparse()
