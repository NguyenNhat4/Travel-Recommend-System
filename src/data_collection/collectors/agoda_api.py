"""agoda.com qua HTTP thường, không trình duyệt: sitemap → trang khách sạn (hotel_id) → API GetSecondaryData theo từng ngày.

Đã xác minh 23/09/2026 bằng request thật (User-Agent của dự án, không cookie/token):
  https://www.agoda.com/vi-vn/sitemaps.xml → 105 file con; khách sạn ở sitemaps-wl_1_lang_24_pagetype_7_page_<n>.xml (41 file,
      ~684 KB mỗi file khi tải có nén, 45.000 URL mọi quốc gia, ~292 URL Việt Nam mỗi file)
  https://www.agoda.com/vi-vn/<slug>/hotel/<city>-vn.html → HTML có `hotel_id=<số>` (một lần mỗi khách sạn, id không đổi)
  https://www.agoda.com/api/cronos/property/BelowFoldParams/GetSecondaryData?checkIn=YYYY-MM-DD&los=1&adults=2&rooms=1&hotel_id=<id>
      → JSON ~1,4 MB (~200 KB khi nén): hotelInfo, aboutHotel (mô tả tiếng Anh), mosaicInitData (ảnh), mapParams (toạ độ),
        roomGridData.masterRooms (hạng phòng + các gói giá của ĐÚNG ngày đó, USD đã gồm thuế phí), reviews (chỉ giữ điểm, số lượt)
  robots.txt (User-agent: *) không cấm các đường dẫn trên.

Không có endpoint trả cả lịch giá: mỗi (khách sạn, ngày) là một request. Tiến độ ghi ngay vào data/state/agoda_api.sqlite nên
dừng lúc nào cũng được (Ctrl+C, hết hạn giờ của daily.py), lượt sau làm tiếp. Thứ tự: mọi khách sạn có ít nhất một ngày giá trước,
rồi mới lấp dần các ngày còn lại; còn ngân sách thì làm mới giá các ngày gần. Raw (đã bỏ review, bản dịch giao diện, cms) chỉ lưu
khi thông tin khách sạn được làm mới (lần đầu, rồi 30 ngày một lần); các ngày khác chỉ lưu giá đã tách.
Điều khoản của agoda hạn chế truy cập tự động: giữ nhịp chậm (mặc định 4 s + jitter), 429/5xx thì lùi và thử lại, bị chặn lặp lại
(403/401/429/trang thử thách) thì dừng cả lượt — không có cơ chế vượt chặn.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

from .common import BlockBreaker, HostRateLimiter, Http, JsonlWriter, Paths, RawCache, looks_like_challenge, now_iso, read_jsonl
from .plan import Destination
from .textutil import fold, html_to_text, uniq

log = logging.getLogger("crawler.agoda_api")

SOURCE = "agoda_api"
SITE = "https://www.agoda.com"
SITEMAP_INDEX = f"{SITE}/vi-vn/sitemaps.xml"
HOTEL_SITEMAP_RE = re.compile(r"<loc>(https://www\.agoda\.com/vi-vn/sitemaps-wl_1_lang_24_pagetype_7_page_\d+\.xml)</loc>")
HOTEL_URL_RE = re.compile(r"<loc>(https://www\.agoda\.com/vi-vn/([a-z0-9-]+)/hotel/([a-z0-9-]+)-vn\.html)</loc>")
HOTEL_ID_RE = re.compile(r"hotel_id=(\d+)")
SECONDARY = f"{SITE}/api/cronos/property/BelowFoldParams/GetSecondaryData"
JSON_HEADERS = {"Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.8"}
BLOCK_STATUSES = (401, 403, 429)
# city-slug trong URL khách sạn (bỏ -vn) không suy ra được từ tên điểm đến / agoda_city của plan.py — kiểm 23/09/2026
CITY_ALIASES = {"dong-hoi-quang-binh": "Quảng Bình", "cua-lo-beach": "Nghệ An"}
STATIC_REFRESH_DAYS = 30
KEEP_RAW_KEYS = ("hotelId", "hotelInfo", "mapParams", "breadcrumbs", "currencyInfo")


def match_city(city: str, destinations: tuple[Destination, ...]) -> str | None:
    """city-slug của URL khách sạn → điểm đến trong kế hoạch. Khớp slug thành phố của plan (agoda_city), tên điểm đến bỏ dấu
    (khoảng trắng → '-' hoặc bỏ hẳn: halong = Hạ Long), hoặc slug bắt đầu bằng tên đó + '-' (pleiku-gia-lai → Pleiku)."""
    c = city.removesuffix("-vn")
    for d in destinations:
        name = re.sub(r"[^a-z0-9 ]+", "", fold(d.name)).strip()
        keys = {name.replace(" ", "-"), name.replace(" ", "")}
        if d.agoda_city:
            keys.add(d.agoda_city.removesuffix("-vn"))
        if c in keys or c.replace("-", "") in keys or any(c.startswith(k + "-") for k in keys if k):
            return d.name
    alias = CITY_ALIASES.get(c)
    return alias if alias in {d.name for d in destinations} else None


def slim_response(d: dict) -> dict:
    """Bản raw để lưu: bỏ review (chỉ giữ điểm và số lượt), bản dịch giao diện, cms, tracking; giữ đủ để parse lại."""
    about = {k: v for k, v in (d.get("aboutHotel") or {}).items() if k in ("hotelDesc", "featureGroups", "hotelName", "usefulInfoGroups")}
    reviews = {k: (d.get("reviews") or {}).get(k) for k in ("score", "scoreText", "reviewsCount", "basedOn")}
    images = [{"location": (x or {}).get("location")} for x in ((d.get("mosaicInitData") or {}).get("images") or [])[:30]]
    rooms = []
    for m in (d.get("roomGridData") or {}).get("masterRooms") or []:
        if not isinstance(m, dict):
            continue
        keep = {k: m.get(k) for k in ("id", "name", "maxOccupancy", "maxExtrabeds", "bedConfigurationSummary", "features", "isDormitory")}
        keep["images"] = (m.get("images") or [])[:6]
        keep["rooms"] = [{k: o.get(k) for k in ("inclusivePrice", "currency", "ratePlanName", "isBreakfastIncluded", "isFreeCancellation")}
                         for o in m.get("rooms") or [] if isinstance(o, dict)]
        rooms.append(keep)
    return {**{k: d.get(k) for k in KEEP_RAW_KEYS}, "aboutHotel": about, "reviews": reviews, "mosaicInitData": {"images": images},
            "roomGridData": {"masterRooms": rooms}}


def _num(v) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _img(u: str | None) -> str | None:
    if not u:
        return None
    return "https:" + u if u.startswith("//") else u


def parse_static(d: dict) -> dict:
    info = d.get("hotelInfo") or {}
    addr = info.get("address") or {}
    about = d.get("aboutHotel") or {}
    latlng = (d.get("mapParams") or {}).get("latlng") or [None, None]
    reviews = d.get("reviews") or {}
    count = reviews.get("reviewsCount")
    if not count:
        m = re.search(r"([\d,.]+)\s*review", html_to_text(reviews.get("basedOn") or "") or "")
        count = int(re.sub(r"[,.]", "", m.group(1))) if m else None
    facilities = uniq(f.get("name") for g in about.get("featureGroups") or [] for f in (g or {}).get("feature") or []
                      if isinstance(f, dict) and f.get("available") and f.get("name"))
    return {
        "hotelId": d.get("hotelId"),
        "name": info.get("name") or about.get("hotelName"),
        "nameEn": info.get("englishName"),
        "propertyType": info.get("accommodationType"),
        "starRating": _num((info.get("starRating") or {}).get("value")) or None,
        "address": {"street": addr.get("address"), "locality": addr.get("areaName"), "region": addr.get("cityName"),
                    "full": addr.get("full")},
        "latitude": _num(latlng[0]) if len(latlng) > 1 else None,
        "longitude": _num(latlng[1]) if len(latlng) > 1 else None,
        "description": html_to_text((about.get("hotelDesc") or {}).get("overview")),
        "facilities": facilities[:80],
        "images": uniq(_img((x or {}).get("location")) for x in ((d.get("mosaicInitData") or {}).get("images") or [])[:20]),
        "reviewScore": _num(reviews.get("score")),
        "reviewCount": int(count) if count else None,
        "rooms": parse_room_types(d),
    }


def parse_room_types(d: dict) -> dict[str, dict]:
    """Thông tin tĩnh của các hạng phòng có trong response (hạng hết phòng ngày đó không xuất hiện — gộp qua nhiều ngày)."""
    out = {}
    for m in (d.get("roomGridData") or {}).get("masterRooms") or []:
        if not isinstance(m, dict) or m.get("id") is None or not m.get("name"):
            continue
        titles = [f.get("title") for f in m.get("features") or [] if isinstance(f, dict) and f.get("title")]
        size = next((re.search(r"([\d.]+)\s*m", t) for t in titles if t.lower().startswith("room size")), None)
        out[str(m["id"])] = {
            "roomId": str(m["id"]),
            "name": m.get("name"),
            "maxOccupancy": m.get("maxOccupancy"),
            "maxExtraBeds": m.get("maxExtrabeds"),
            "bedType": ((m.get("bedConfigurationSummary") or {}).get("title")),
            "sizeM2": _num(size.group(1)) if size else None,
            "features": uniq(t for t in titles if not t.lower().startswith("room size"))[:20],
            "images": uniq(_img(u) for u in (m.get("images") or [])[:6]),
            "isDormitory": m.get("isDormitory") or None,
        }
    return out


def parse_prices(d: dict) -> dict[str, dict]:
    """Giá rẻ nhất của từng hạng phòng cho đúng ngày đã hỏi: gói có inclusivePrice nhỏ nhất (đã gồm thuế phí, 1 đêm, 2 người)."""
    currency = (d.get("currencyInfo") or {}).get("code")
    out = {}
    for m in (d.get("roomGridData") or {}).get("masterRooms") or []:
        if not isinstance(m, dict) or m.get("id") is None:
            continue
        offers = [o for o in m.get("rooms") or [] if isinstance(o, dict) and _num((o.get("inclusivePrice") or {}).get("display"))]
        if not offers:
            continue
        best = min(offers, key=lambda o: _num(o["inclusivePrice"]["display"]))
        out[str(m["id"])] = {"price": _num(best["inclusivePrice"]["display"]), "currency": best.get("currency") or currency,
                             "ratePlan": best.get("ratePlanName"), "breakfast": best.get("isBreakfastIncluded"),
                             "freeCancellation": best.get("isFreeCancellation")}
    return out


# ---------------------------------------------------------------------- trạng thái


class AgodaState:
    def __init__(self, paths: Paths):
        self.db = sqlite3.connect(paths.state / "agoda_api.sqlite", timeout=60)
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS hotels (url TEXT PRIMARY KEY, slug TEXT NOT NULL, city TEXT NOT NULL, destination TEXT,
                rank INTEGER, first_seen TEXT, last_seen TEXT, hotel_id INTEGER, id_status TEXT, static_json TEXT, static_at TEXT);
            CREATE TABLE IF NOT EXISTS prices (hotel_id INTEGER NOT NULL, day TEXT NOT NULL, status TEXT NOT NULL, rooms_json TEXT,
                fetched_at TEXT NOT NULL, PRIMARY KEY (hotel_id, day));
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        """)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(hotels)")}
        if "refresh" not in columns:  # state của lượt cũ (trước khi có làm mới khách sạn đang có trong DB)
            self.db.execute("ALTER TABLE hotels ADD COLUMN refresh INTEGER NOT NULL DEFAULT 0")
            self.db.commit()

    def meta(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
        self.db.commit()

    def close(self) -> None:
        self.db.close()


@dataclass
class AgodaOptions:
    destinations: tuple[Destination, ...]
    per_city: int = 50
    days: int = 30
    delay: float = 4.0
    max_requests: int | None = None
    max_blocks: int = 3
    discover: bool = False
    rediscover_days: int = 7
    refresh_near_days: int = 7
    refresh_hours: float = 20.0
    limit_hotels: int | None = None
    export_only: bool = False
    max_hours: float | None = None
    today: date | None = None
    # Khách sạn đang có trong DB cần hỏi lại giá (fresh_catalog_db.refresh_targets): luôn trong phạm vi, ngoài per_city
    refresh: tuple[dict, ...] = ()


class AgodaCollector:
    def __init__(self, paths: Paths, opts: AgodaOptions):
        self.paths = paths
        self.opts = opts
        self.state = AgodaState(paths)
        self.cache = RawCache(paths, SOURCE)
        self.http = Http(HostRateLimiter(opts.delay, jitter=0.25))
        self.breaker = BlockBreaker(opts.max_blocks)
        self.requests = 0
        self.deadline = time.monotonic() + opts.max_hours * 3600 if opts.max_hours else None
        self.stats = {"sitemapFiles": 0, "hotelsInSitemap": 0, "idResolved": 0, "priceOk": 0, "priceNone": 0, "failed": 0}

    def _budget_left(self) -> bool:
        """Còn được gọi mạng: chưa bị chặn, chưa hết ngân sách request, chưa hết giờ (--max-hours: dừng êm, không coi là lỗi)."""
        return (not self.breaker.tripped and (self.opts.max_requests is None or self.requests < self.opts.max_requests)
                and (self.deadline is None or time.monotonic() < self.deadline))

    async def _get(self, url: str, headers: dict | None = None):
        """→ (mã HTTP, response) hoặc (None, None) khi lỗi mạng/robots. Đếm request, ghi nhận bị chặn."""
        self.requests += 1
        try:
            r = await self.http.get(url, headers=headers)
        except PermissionError as e:
            log.warning("%s", e)
            return None, None
        except Exception as e:
            log.warning("Lỗi gọi %s: %s", url, e)
            return None, None
        body_head = r.text[:3000] if "html" in r.headers.get("content-type", "") else ""
        if r.status_code in BLOCK_STATUSES or (body_head and looks_like_challenge(body_head)):
            self.breaker.blocked()
            log.warning("Bị chặn (HTTP %s) tại %s – lần %d liên tiếp", r.status_code, url, self.breaker.streak)
            return r.status_code, None
        self.breaker.ok()
        return r.status_code, r

    # ------------------------------------------------------------------ 1. tìm khách sạn
    async def discover(self) -> None:
        status, r = await self._get(SITEMAP_INDEX)
        if r is None or status != 200:
            log.error("Không đọc được sitemap index (HTTP %s)", status)
            return
        files = HOTEL_SITEMAP_RE.findall(r.text)
        now = now_iso()
        seen = 0
        for n, url in enumerate(files, 1):
            if not self._budget_left():
                return
            status, resp = await self._get(url)
            if resp is None or status != 200:
                log.warning("Bỏ qua sitemap %s (HTTP %s)", url, status)
                continue
            self.stats["sitemapFiles"] += 1
            rows = [(hotel_url, slug, city, n * 100_000 + rank, now, now)
                    for rank, (hotel_url, slug, city) in enumerate(HOTEL_URL_RE.findall(resp.text))]
            with self.state.db:
                self.state.db.executemany("""
                    INSERT INTO hotels (url, slug, city, rank, first_seen, last_seen) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET last_seen = excluded.last_seen""", rows)
            seen += len(rows)
            log.info("Sitemap %d/%d: %d khách sạn Việt Nam", n, len(files), len(rows))
        self.stats["hotelsInSitemap"] = seen
        if self.stats["sitemapFiles"] == len(files) and files:
            self.state.set_meta("discoveredAt", now)

    def _discovery_due(self) -> bool:
        last = self.state.meta("discoveredAt")
        if self.opts.discover or not last:
            return True
        return datetime.now(timezone.utc) - datetime.fromisoformat(last.replace("Z", "+00:00")) > timedelta(days=self.opts.rediscover_days)

    # ------------------------------------------------------------------ 2. phạm vi
    def _known_keys(self) -> set[str]:
        """Khách sạn Agoda đã có trong dữ liệu trước đó (interim agoda_hotels + catalog): ưu tiên giữ trong phạm vi."""
        keys = {r.get("key") for r in read_jsonl(self.paths.interim / "agoda_hotels.jsonl") if r.get("key")}
        catalog = self.paths.data / "products.jsonl"
        if catalog.exists():
            with open(catalog, encoding="utf-8") as f:
                for line in f:
                    for ref in re.findall(r"agoda:hotel:([a-z0-9-]+):([a-z0-9-]+)", line):
                        keys.add(f"hotel:{ref[0]}:{ref[1]}")
        return keys

    def select_scope(self) -> list[tuple]:
        """Gán điểm đến theo city-slug; mỗi điểm đến tối đa per_city khách sạn: khách sạn đã có trước, rồi theo thứ tự sitemap."""
        rows = self.state.db.execute("SELECT url, slug, city, rank, hotel_id, id_status FROM hotels").fetchall()
        known = self._known_keys()
        by_dest: dict[str, list] = {}
        unmatched: dict[str, int] = {}
        for url, slug, city, rank, hotel_id, id_status in rows:
            dest = match_city(city, self.opts.destinations)
            if dest is None:
                unmatched[city] = unmatched.get(city, 0) + 1
                continue
            if id_status == "gone":
                continue
            by_dest.setdefault(dest, []).append((f"hotel:{slug}:{city}" not in known, rank, url, slug, city, dest, hotel_id))
        with self.state.db:
            self.state.db.executemany("UPDATE hotels SET destination=? WHERE url=?",
                                      [(x[5], x[2]) for group in by_dest.values() for x in group])
        scope = []
        for dest, group in sorted(by_dest.items()):
            scope.extend(sorted(group)[: self.opts.per_city])
        if self.opts.limit_hotels:
            scope = sorted(scope, key=lambda x: (x[0], x[1]))[: self.opts.limit_hotels]
        top = sorted(unmatched.items(), key=lambda kv: -kv[1])[:10]
        log.info("Phạm vi: %d khách sạn / %d điểm đến (tối đa %d mỗi điểm); city-slug ngoài kế hoạch: %s",
                 len(scope), len(by_dest), self.opts.per_city, ", ".join(f"{c} {n}" for c, n in top) or "không")
        self.stats["scope"] = len(scope)
        return [(url, slug, city, dest, hotel_id) for _, _, url, slug, city, dest, hotel_id in scope]

    def add_refresh(self, scope: list[tuple]) -> list[tuple]:
        """Khách sạn đang có trong DB (`opts.refresh`) vào phạm vi sau khách sạn mới tìm theo điểm đến, không tính vào per_city
        và không lọc theo điểm đến kế hoạch: lượt cào lớn làm mới cả catalog chứ không chỉ top N mỗi điểm đến. Điểm đến lấy
        từ DB; hotel_id đã biết thì không phải mở lại trang khách sạn."""
        if not self.opts.refresh:
            return scope
        now = now_iso()
        with self.state.db:
            for order, item in enumerate(self.opts.refresh):
                self.state.db.execute("""
                    INSERT INTO hotels (url, slug, city, destination, rank, first_seen, last_seen, hotel_id, id_status, refresh)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(url) DO UPDATE SET refresh = 1, destination = COALESCE(hotels.destination, excluded.destination),
                        hotel_id = COALESCE(hotels.hotel_id, excluded.hotel_id),
                        id_status = COALESCE(hotels.id_status, excluded.id_status)""",
                    (item["url"], item["slug"], item["city"], item["destination"], 10**9 + order, now, now,
                     item.get("hotelId"), "ok" if item.get("hotelId") else None))
        chosen = {url for url, *_ in scope}
        extra = []
        for item in self.opts.refresh:
            if item["url"] in chosen:
                continue
            row = self.state.db.execute("SELECT destination, hotel_id, id_status FROM hotels WHERE url=?",
                                        (item["url"],)).fetchone()
            if row[2] == "gone":
                continue
            chosen.add(item["url"])
            extra.append((item["url"], item["slug"], item["city"], row[0], row[1]))
        self.stats["refreshScope"] = len(self.opts.refresh)
        log.info("Agoda: thêm %d/%d khách sạn đang có trong DB vào phạm vi làm mới", len(extra), len(self.opts.refresh))
        return scope + extra

    # ------------------------------------------------------------------ 3. hotel_id
    async def resolve_ids(self, scope: list[tuple]) -> list[tuple]:
        out = []
        for url, slug, city, dest, hotel_id in scope:
            if hotel_id is None and self._budget_left():
                status, r = await self._get(url)
                if r is not None and status == 200:
                    m = HOTEL_ID_RE.search(r.text)
                    hotel_id = int(m.group(1)) if m else None
                    id_status = "ok" if hotel_id else "no-id"
                    self.stats["idResolved"] += bool(hotel_id)
                elif status in (404, 410):
                    id_status = "gone"
                else:
                    id_status = None
                with self.state.db:
                    self.state.db.execute("UPDATE hotels SET hotel_id=?, id_status=? WHERE url=?", (hotel_id, id_status, url))
            if hotel_id:
                out.append((url, slug, city, dest, hotel_id))
        return out

    # ------------------------------------------------------------------ 4. giá theo ngày
    def plan_tasks(self, hotels: list[tuple], today: date) -> list[tuple[int, str]]:
        """(hotel_id, ngày): ngày còn thiếu trong cửa sổ theo vòng (mọi khách sạn ngày thiếu thứ 1, rồi thứ 2…), sau đó làm mới
        các ngày gần đã cũ hơn refresh_hours."""
        window = [(today + timedelta(days=i)).isoformat() for i in range(self.opts.days)]
        have: dict[int, dict[str, str]] = {}
        for hid, day, fetched_at in self.state.db.execute(
                "SELECT hotel_id, day, fetched_at FROM prices WHERE day >= ? AND status IN ('ok', 'none')", (window[0],)):
            have.setdefault(hid, {})[day] = fetched_at
        missing = []
        for order, (_, _, _, _, hid) in enumerate(hotels):
            todo = [d for d in window if d not in have.get(hid, {})]
            missing.extend((k, order, hid, d) for k, d in enumerate(todo))
        tasks = [(hid, d) for _, _, hid, d in sorted(missing)]
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=self.opts.refresh_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        near = set(window[: self.opts.refresh_near_days])
        stale = sorted((fetched, hid, d) for hid, days in have.items() for d, fetched in days.items() if d in near and fetched < cutoff)
        return tasks + [(hid, d) for _, hid, d in stale]

    async def fetch_day(self, hotel_id: int, day: str) -> None:
        params = {"checkIn": day, "los": 1, "adults": 2, "rooms": 1, "travellerType": -1, "hotel_id": hotel_id, "all": "false",
                  "isHostPropertiesEnabled": "true"}
        status, r = await self._get(f"{SECONDARY}?{urlencode(params)}", headers=JSON_HEADERS)
        now = now_iso()
        if r is None or status != 200 or "json" not in r.headers.get("content-type", ""):
            if status in (404, 410):
                self.stats["priceNone"] += 1
                with self.state.db:
                    self.state.db.execute("INSERT OR REPLACE INTO prices VALUES (?, ?, 'none', NULL, ?)", (hotel_id, day, now))
            else:
                self.stats["failed"] += 1
            return
        d = r.json()
        prices = parse_prices(d)
        row = self.state.db.execute("SELECT url, static_json, static_at FROM hotels WHERE hotel_id=?", (hotel_id,)).fetchone()
        static = json.loads(row[1]) if row and row[1] else None
        due = static is None or not row[2] or datetime.now(timezone.utc) - datetime.fromisoformat(
            row[2].replace("Z", "+00:00")) > timedelta(days=STATIC_REFRESH_DAYS)
        with self.state.db:
            if due:
                fresh = parse_static(d)
                fresh["rooms"] = {**(static or {}).get("rooms", {}), **fresh["rooms"]}
                self.cache.write_json(f"secondary-{hotel_id}", slim_response(d))
                self.state.db.execute("UPDATE hotels SET static_json=?, static_at=? WHERE hotel_id=?",
                                      (json.dumps(fresh, ensure_ascii=False), now, hotel_id))
            elif static is not None:
                new_rooms = {k: v for k, v in parse_room_types(d).items() if k not in static.get("rooms", {})}
                if new_rooms:
                    static["rooms"] = {**static.get("rooms", {}), **new_rooms}
                    self.state.db.execute("UPDATE hotels SET static_json=? WHERE hotel_id=?", (json.dumps(static, ensure_ascii=False), hotel_id))
            self.state.db.execute("INSERT OR REPLACE INTO prices VALUES (?, ?, 'ok', ?, ?)",
                                  (hotel_id, day, json.dumps(prices, ensure_ascii=False), now))
        self.stats["priceOk"] += 1

    # ------------------------------------------------------------------ 5. xuất interim
    def export(self, today: date) -> int:
        """Một bản ghi mỗi khách sạn đã có thông tin tĩnh: hạng phòng + giá theo ngày (chỉ ngày chưa qua) → interim/agoda_api.jsonl."""
        cut = today.isoformat()
        prices: dict[int, list] = {}
        for hid, day, status, rooms_json, fetched_at in self.state.db.execute(
                "SELECT hotel_id, day, status, rooms_json, fetched_at FROM prices WHERE day >= ? ORDER BY day", (cut,)):
            prices.setdefault(hid, []).append((day, status, json.loads(rooms_json) if rooms_json else {}, fetched_at))
        out = self.paths.interim / f"{SOURCE}.jsonl"
        tmp = out.with_suffix(".jsonl.tmp")
        n = 0
        with JsonlWriter(tmp, "w") as w:
            for url, slug, city, dest, hid, static_json, refresh in self.state.db.execute(
                    "SELECT url, slug, city, destination, hotel_id, static_json, refresh FROM hotels "
                    "WHERE static_json IS NOT NULL AND destination IS NOT NULL ORDER BY rank"):
                static = json.loads(static_json)
                days = prices.get(hid, [])
                rooms = []
                for rid, room in static.get("rooms", {}).items():
                    by_day = {day: p[rid] for day, st, p, _ in days if st == "ok" and rid in p}
                    rooms.append({**room, "pricesByDate": {d: v["price"] for d, v in by_day.items()},
                                  "currency": next((v["currency"] for v in by_day.values() if v.get("currency")), None),
                                  "ratePlans": uniq(v.get("ratePlan") for v in by_day.values())[:6],
                                  "breakfastIncluded": any(v.get("breakfast") for v in by_day.values()) or None,
                                  "freeCancellation": any(v.get("freeCancellation") for v in by_day.values()) or None})
                w.write({"recordType": "agoda_api_hotel", "source": SOURCE, "key": f"hotel:{slug}:{city}", "url": url, "slug": slug,
                         "citySlug": city, "hotelId": hid,
                         "plan": {"destination": dest, **({"via": "refresh"} if refresh else {})},
                         **{k: v for k, v in static.items() if k != "rooms"}, "rooms": rooms,
                         "datesQueried": [day for day, st, _, _ in days if st in ("ok", "none")],
                         "priceQuery": {"nights": 1, "adults": 2, "rooms": 1},
                         "crawledAt": max((f for _, _, _, f in days), default=None)})
                n += 1
        if n:
            tmp.replace(out)
        else:
            tmp.unlink(missing_ok=True)
        return n

    async def run(self) -> dict:
        today = self.opts.today or date.today()
        try:
            if not self.opts.export_only:
                if self._discovery_due():
                    await self.discover()
                hotels = await self.resolve_ids(self.add_refresh(self.select_scope()))
                tasks = self.plan_tasks(hotels, today)
                self.stats["tasks"] = len(tasks)
                log.info("Agoda: %d khách sạn có hotel_id, %d lượt hỏi giá cần làm (ngân sách %s request)",
                         len(hotels), len(tasks), self.opts.max_requests or "không giới hạn")
                started = time.monotonic()
                for n, (hid, day) in enumerate(tasks, 1):
                    if not self._budget_left():
                        break
                    await self.fetch_day(hid, day)
                    if n % 50 == 0:
                        rate = n / max(time.monotonic() - started, 1)
                        log.info("Agoda giá: %d/%d (%.2f req/s, ok %d, lỗi %d)", n, len(tasks), rate, self.stats["priceOk"], self.stats["failed"])
        finally:
            self.stats["requests"] = self.requests
            self.stats["exported"] = self.export(today)
            await self.http.close()
            self.state.close()
        if self.breaker.tripped:
            self.stats["stopped"] = "blocked"
        return self.stats


async def run(paths: Paths, opts: AgodaOptions) -> dict:
    stats = await AgodaCollector(paths, opts).run()
    log.info("Agoda API: %s", stats)
    return stats
