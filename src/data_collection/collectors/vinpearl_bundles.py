"""Vinpearl combo vé máy bay khứ hồi + khách sạn (API bundle của booking.vinpearl.com) — HTTP thường, không cần trình duyệt.

  /api/bundle/locations/all                         → điểm đi/đến (id, airportCode, isDomestic)
  /api/bundle/v2/search?StartLocationId&StartAirportCode&EndLocationId&EndAirportCode&DepartureDate&ReturnDate
                       &RoomOccupancy=2_0_0&Room=1&PromotionCode=
      → data.bundleData[]: {hotel, flight[], pricePerson, totalPrice}; 23/09/2026: HAN → CXR +30 ngày trả 5 khách sạn, ~15 s.

Cache nguội phía server: lần gọi đầu cho một (tuyến, ngày) hay trả 404 FLIGHT_NOT_FOUND hoặc rất chậm, gọi lại sau ~20 s
thì 200 (khảo sát của nhánh crawler, 22/09/2026). Vì vậy 404 được gọi lại `retries_404` lần; 404 sau cùng = tuyến/ngày đó
không có combo. 401/403/429 là bị chặn: dừng theo BlockBreaker, không thử vượt.

Một combo = (sân bay đi, khách sạn); giá theo từng ngày khởi hành nằm trong `pricesByDate` của MỘT bản ghi, không tách dòng.
Ngày đã hỏi ở lượt trước mà lượt này không hỏi lại (lỗi mạng, bị chặn) được giữ nếu chưa qua; ngày đã qua bị bỏ.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urlencode

from .common import BlockBreaker, HostRateLimiter, Http, JsonlWriter, Paths, RawCache, now_iso, read_jsonl
from .plan import DESTINATIONS
from .textutil import clean_text, html_to_text, uniq
from .vinpearl import API_HEADERS, HOTEL_API, _static_url, _to_float

log = logging.getLogger("crawler.vinpearl_bundles")

SOURCE = "vinpearl_bundles"
DEFAULT_ORIGINS = ("HAN", "SGN")
BLOCK_STATUSES = (401, 403, 429)
AIRPORT_CITY = {a: d.name for d in DESTINATIONS for a in d.airports}


@dataclass
class BundleOptions:
    days: int = 30
    start_offset: int = 0
    origins: tuple[str, ...] = DEFAULT_ORIGINS
    delay: float = 4.0
    nights: int = 1
    adults: int = 2
    retries_404: int = 2
    retry_wait: float = 20.0
    max_blocks: int = 3
    limit_routes: int | None = None
    offline: bool = False
    today: date | None = None


def plan_routes(locations: list[dict], origins: tuple[str, ...]) -> list[tuple[dict, dict]]:
    """Mỗi sân bay đi trong `origins` × mọi điểm đến nội địa khác sân bay. Điểm đi lấy location đầu tiên có mã đó."""
    domestic = [x for x in locations if isinstance(x, dict) and x.get("isDomestic") and x.get("id") and x.get("airportCode")]
    routes = []
    for code in origins:
        start = next((x for x in domestic if x["airportCode"] == code), None)
        if start is None:
            log.warning("Không có điểm đi %s trong danh sách bundle – bỏ qua", code)
            continue
        routes.extend((start, end) for end in domestic if end["airportCode"] != code)
    return routes


def hotel_info(h: dict) -> dict:
    return {
        "hotelId": h.get("hotelId"),
        "hotelCode": h.get("code"),
        "hotelName": clean_text(h.get("name")),
        "starRating": _to_float(h.get("star")),
        "address": clean_text(h.get("address")),
        "latitude": _to_float(h.get("latitude")),
        "longitude": _to_float(h.get("longtitude") or h.get("longitude")),  # API viết sai chính tả "longtitude"
        "shortDescription": clean_text(h.get("shortDescription")),
        "description": html_to_text(h.get("description")),
        "amenities": uniq(clean_text(a.get("name")) for a in h.get("amenity") or [] if isinstance(a, dict)),
        "tags": uniq(clean_text(t.get("name")) for t in h.get("hotelTags") or [] if isinstance(t, dict)),
        "images": uniq(_static_url(m.get("url")) for m in sorted(h.get("media") or [], key=lambda m: m.get("order") or 0)
                       if isinstance(m, dict))[:15],
        "urlSlug": h.get("urlSlug"),
        "tripAdvisorRating": _to_float(h.get("rating")),
        "reviewCount": int(_to_float(h.get("reviewCount")) or 0) or None,  # số lượt tổng hợp, không có nội dung review
    }


def merge_records(previous: list[dict], observed: dict[str, dict], queried: dict[str, set[str]], today: date) -> list[dict]:
    """Gộp quan sát của lượt này vào bản ghi cũ theo key.
    `observed`: key → bản ghi mới (pricesByDate chỉ gồm ngày lượt này thấy). `queried`: tuyến → các ngày có câu trả lời
    dứt khoát trong lượt này (200, kể cả rỗng, hoặc 404 sau khi gọi lại). Ngày đã hỏi lại thì lấy kết quả mới — không thấy
    combo ngày đó nghĩa là hết; ngày chưa hỏi lại thì giữ giá cũ nếu chưa qua."""
    cut = today.isoformat()
    out: dict[str, dict] = {}
    for old in previous:
        key = old.get("key")
        if not key:
            continue
        again = queried.get(old.get("route") or "", set())
        keep = {d: p for d, p in (old.get("pricesByDate") or {}).items() if d >= cut and d not in again}
        keep_pp = {d: p for d, p in (old.get("pricePerPersonByDate") or {}).items() if d in keep}
        rec = dict(old, pricesByDate=keep, pricePerPersonByDate=keep_pp,
                   datesQueried=sorted({d for d in old.get("datesQueried") or [] if d >= cut} | again))
        out[key] = rec
    for key, new in observed.items():
        base = out.get(key)
        if base is None:
            out[key] = new
            continue
        prices = {**base["pricesByDate"], **new["pricesByDate"]}
        per_person = {**base.get("pricePerPersonByDate", {}), **new.get("pricePerPersonByDate", {})}
        out[key] = dict(new, pricesByDate=dict(sorted(prices.items())), pricePerPersonByDate=dict(sorted(per_person.items())),
                        datesQueried=sorted(set(base.get("datesQueried") or []) | set(new.get("datesQueried") or [])))
    return sorted(out.values(), key=lambda r: r["key"])


class BundleCollector:
    def __init__(self, paths: Paths, opts: BundleOptions):
        self.paths = paths
        self.opts = opts
        self.cache = RawCache(paths, SOURCE)
        self.http = Http(HostRateLimiter(opts.delay))
        self.breaker = BlockBreaker(opts.max_blocks)

    async def _get(self, key: str, url: str, retry_404: bool = False) -> tuple[str, object | None]:
        """→ ("ok", JSON) | ("none", None) khi 404 sau khi gọi lại | ("fail", None) khi lỗi/bị chặn."""
        if self.opts.offline:
            data = self.cache.read_json(key)
            return ("ok", data) if data is not None else ("fail", None)
        attempts = 1 + (self.opts.retries_404 if retry_404 else 0)
        for attempt in range(1, attempts + 1):
            try:
                r = await self.http.get(url, headers=API_HEADERS)
            except PermissionError as e:
                log.warning("%s", e)
                return "fail", None
            except Exception as e:
                log.warning("Lỗi gọi %s: %s", url, e)
                return "fail", None
            if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
                self.breaker.ok()
                data = r.json()
                self.cache.write_json(key, data)
                return "ok", data
            if r.status_code == 404 and retry_404:
                if attempt < attempts:
                    log.info("404 (cache nguội phía server?) %s – gọi lại sau %.0fs", url, self.opts.retry_wait)
                    self.http.limiter.penalise(url, self.opts.retry_wait)
                    continue
                return "none", None
            if r.status_code in BLOCK_STATUSES:
                self.breaker.blocked()
                log.warning("Bị chặn HTTP %s tại %s (lần %d liên tiếp)", r.status_code, url, self.breaker.streak)
            else:
                log.warning("HTTP %s cho %s: %s", r.status_code, url, r.text[:200])
            return "fail", None
        return "fail", None

    async def run(self) -> tuple[list[dict], dict]:
        today = self.opts.today or date.today()
        stats = {"routes": 0, "requests": 0, "ok": 0, "empty": 0, "noCombo": 0, "failed": 0, "combos": 0}
        status, locations = await self._get("api-bundle-locations-all", f"{HOTEL_API}/api/bundle/locations/all")
        if status != "ok" or not isinstance(locations, list):
            stats["error"] = "không đọc được danh sách điểm đi/đến"
            return [], stats
        routes = plan_routes(locations, self.opts.origins)
        if self.opts.limit_routes:
            routes = routes[: self.opts.limit_routes]
        stats["routes"] = len(routes)
        dates = [today + timedelta(days=self.opts.start_offset + i) for i in range(self.opts.days)]
        observed: dict[str, dict] = {}
        queried: dict[str, set[str]] = {}
        crawled_at = now_iso()
        for n, (start, end) in enumerate(routes, 1):
            route = f"{start['airportCode']}-{end['id']}"
            log.info("Combo %d/%d: %s → %s (%s), %d ngày", n, len(routes), start["airportCode"], end.get("name"), end["airportCode"], len(dates))
            for day in dates:
                if self.breaker.tripped:
                    stats["stopped"] = "blocked"
                    log.error("Bị chặn liên tiếp %d lần – dừng combo Vinpearl, giữ phần đã có.", self.breaker.streak)
                    return [], stats
                params = {
                    "StartLocationId": start["id"], "StartAirportCode": start["airportCode"],
                    "EndLocationId": end["id"], "EndAirportCode": end["airportCode"],
                    "DepartureDate": day.isoformat(), "ReturnDate": (day + timedelta(days=self.opts.nights)).isoformat(),
                    "RoomOccupancy": f"{self.opts.adults}_0_0", "Room": 1, "PromotionCode": "",
                }
                key = f"bundle-{start['airportCode']}-{end['id']}-{day.isoformat()}-{self.opts.adults}a{self.opts.nights}n"
                stats["requests"] += 1
                status, data = await self._get(key, f"{HOTEL_API}/api/bundle/v2/search?{urlencode(params)}", retry_404=True)
                if status == "fail":
                    stats["failed"] += 1
                    continue
                queried.setdefault(route, set()).add(day.isoformat())
                bundles = ((data or {}).get("data") or {}).get("bundleData") or [] if isinstance(data, dict) else []
                if status == "none":
                    stats["noCombo"] += 1
                elif not bundles:
                    stats["empty"] += 1
                else:
                    stats["ok"] += 1
                for b in bundles:
                    h = b.get("hotel") or {}
                    total = _to_float(b.get("totalPrice"))
                    if not h.get("hotelId") or not total:
                        continue
                    key_rec = f"bundle:{start['airportCode']}:{h['hotelId']}"
                    rec = observed.get(key_rec)
                    if rec is None:
                        rec = observed[key_rec] = {
                            "recordType": "vinpearl_bundle",
                            "source": "vinpearl",
                            "key": key_rec,
                            "route": route,
                            "originAirport": start["airportCode"],
                            "originCity": AIRPORT_CITY.get(start["airportCode"]) or clean_text(start.get("name")),
                            "destinationAirport": end["airportCode"],
                            "destinationLocationId": end["id"],
                            "destinationLocationName": clean_text(end.get("name")),
                            **hotel_info(h),
                            "nights": self.opts.nights,
                            "adults": self.opts.adults,
                            "rooms": 1,
                            "pricesByDate": {},
                            "pricePerPersonByDate": {},
                            "datesQueried": [],
                            "crawledAt": crawled_at,
                            "lastSeenAt": crawled_at,
                        }
                    rec["pricesByDate"][day.isoformat()] = total
                    per_person = _to_float(b.get("pricePerson"))
                    if per_person:
                        rec["pricePerPersonByDate"][day.isoformat()] = per_person
        for rec in observed.values():
            rec["datesQueried"] = sorted(queried.get(rec["route"], set()))
        previous = list(read_jsonl(self.paths.interim / f"{SOURCE}.jsonl"))
        records = merge_records(previous, observed, queried, today)
        stats["combos"] = len(records)
        return records, stats

    async def close(self) -> None:
        await self.http.close()


async def run(paths: Paths, opts: BundleOptions) -> dict:
    collector = BundleCollector(paths, opts)
    try:
        records, stats = await collector.run()
    finally:
        await collector.close()
    out = paths.interim / f"{SOURCE}.jsonl"
    if not records or not (stats.get("ok") or stats.get("empty") or stats.get("noCombo")):
        log.warning("Combo Vinpearl: lượt này không có câu trả lời nào – giữ nguyên %s (%s)", out, stats)
        return stats
    tmp = out.with_suffix(".jsonl.tmp")
    with JsonlWriter(tmp, "w") as writer:
        for rec in records:
            writer.write(rec)
    tmp.replace(out)
    log.info("Combo Vinpearl: %s → %s", stats, out)
    return stats
