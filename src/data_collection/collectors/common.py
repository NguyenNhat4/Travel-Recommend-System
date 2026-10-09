"""Hạ tầng dùng chung: thư mục dữ liệu, cache raw, trạng thái resume, robots.txt,
giới hạn tốc độ, HTTP client và phiên trình duyệt Playwright."""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
import os
import random
import re
import shutil
import sqlite3
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

import httpx
from protego import Protego

from . import live_control

log = logging.getLogger("crawler")

ROOT = Path(__file__).resolve().parent.parent
CRAWLER_UA = os.environ.get(
    "CRAWLER_USER_AGENT",
    "Mozilla/5.0 (compatible; VOTA-RecSys-Internship/1.0; data-collection)",
)


# --------------------------------------------------------------------------- paths


@dataclass(frozen=True)
class Paths:
    data: Path

    @property
    def raw(self) -> Path:
        return self.data / "raw"

    @property
    def interim(self) -> Path:
        return self.data / "interim"

    @property
    def state(self) -> Path:
        return self.data / "state"

    @property
    def profiles(self) -> Path:
        return self.data / "browser-profile"

    @property
    def logs(self) -> Path:
        return self.data / "logs"

    def ensure(self) -> "Paths":
        for p in (self.raw, self.interim, self.state, self.profiles, self.logs):
            p.mkdir(parents=True, exist_ok=True)
        return self


def default_data_dir() -> Path:
    return Path(os.environ.get("VOTA_DATA_DIR", ROOT / "data"))


def setup_logging(paths: Paths, verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)
    fh = logging.FileHandler(paths.logs / f"crawl-{datetime.now():%Y%m%d}.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s %(message)s"))
    root.addHandler(fh)
    for noisy in ("httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def url_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- raw cache


class RawCache:
    """Lưu mọi trang/response ra đĩa (gzip) TRƯỚC khi parse.
    Parser sai thì chạy `crawl.py reparse` từ cache, không phải fetch lại."""

    def __init__(self, paths: Paths, source: str):
        self.dir = paths.raw / source

    @classmethod
    def shared(cls, paths: Paths, source: str) -> "RawCache":
        """Cache trang dùng chung giữa nhiều job (danh sách sân bay, sitemap): đặt CRAWL_SHARED_CACHE để mỗi trang chỉ tải
        một lần thay vì một lần cho mỗi job. Không đặt biến này thì giống cache riêng của job."""
        shared = os.environ.get("CRAWL_SHARED_CACHE")
        return cls(Paths(Path(shared)) if shared else paths, source)

    def path(self, key: str, ext: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", key)
        if len(safe) > 120 or safe != key:
            safe = f"{safe[:60]}-{url_key(key)[:16]}"
        return self.dir / ext / f"{safe}.{ext}.gz"

    def has(self, key: str, ext: str) -> bool:
        return self.path(key, ext).exists()

    def read(self, key: str, ext: str) -> str | None:
        p = self.path(key, ext)
        if not p.exists():
            return None
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return f.read()

    def write(self, key: str, ext: str, text: str) -> Path:
        p = self.path(key, ext)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + f".{os.getpid()}.tmp")  # theo pid: nhiều tiến trình cùng ghi cache dùng chung
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            f.write(text)
        tmp.replace(p)
        return p

    def read_json(self, key: str) -> Any | None:
        text = self.read(key, "json")
        return None if text is None else json.loads(text)

    def write_json(self, key: str, data: Any) -> Path:
        return self.write(key, "json", json.dumps(data, ensure_ascii=False))

    def write_bytes(self, key: str, ext: str, data: bytes) -> Path:
        p = self.path(key, ext)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + f".{os.getpid()}.tmp")
        with gzip.open(tmp, "wb") as f:
            f.write(data)
        tmp.replace(p)
        return p

    def read_bytes(self, key: str, ext: str) -> bytes | None:
        p = self.path(key, ext)
        if not p.exists():
            return None
        with gzip.open(p, "rb") as f:
            return f.read()


_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.S | re.I)
_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.S | re.I)
_SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S | re.I)
_KEEP_VARS = re.compile(r"\b(b_hotel_id|b_map_center_latitude|b_map_center_longitude|b_dest_id)\W{1,4}(-?[\d.]+)")


def _slim_script(m: re.Match) -> str:
    tag = m.group(0)
    head = tag[:200].lower()
    if "application/ld+json" in head or 'data-drupal-selector="drupal-settings-json"' in head:
        return tag
    found = dict(_KEEP_VARS.findall(tag))
    if found:  # chỉ giữ vài biến cần cho parser thay vì cả script vài trăm KB
        body = ", ".join(f"{k}: '{v}'" for k, v in found.items())
        return f"<script>/* crawler-kept */ {body}</script>"
    return ""


def strip_elements(html: str, selectors: tuple[str, ...]) -> str:
    """Xoá các khối theo CSS selector (vd. review, tên người đánh giá) trước khi lưu cache."""
    if not selectors:
        return html
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    removed = 0
    for sel in selectors:
        for el in soup.select(sel):
            el.decompose()
            removed += 1
    return str(soup) if removed else html


def slim_html(html: str) -> str:
    """Bỏ script theo dõi, CSS, SVG (phần lớn dung lượng); giữ JSON-LD, drupal settings và biến cần cho parser."""
    html = _SCRIPT_RE.sub(_slim_script, html)
    html = _STYLE_RE.sub("", html)
    return _SVG_RE.sub("<svg></svg>", html)


# --------------------------------------------------------------------------- JSONL


class JsonlWriter:
    """Ghi nối tiếp từng record, flush ngay để dừng giữa chừng không mất dữ liệu."""

    def __init__(self, path: Path, mode: str = "a"):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._f = open(path, mode, encoding="utf-8")
        self.count = 0

    def write(self, record: dict) -> None:
        self._f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._f.flush()
        self.count += 1

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> "JsonlWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def read_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                log.warning("Bỏ dòng JSON hỏng %s:%d", path.name, n)


# --------------------------------------------------------------------------- resume state


class StateDB:
    """Hàng đợi URL bền vững (SQLite). Dừng bằng Ctrl+C rồi chạy lại là tiếp tục."""

    def __init__(self, paths: Paths):
        # Lượt cào lớn mở nhiều site (tiến trình crawl.py) cùng lúc trên cùng file: chờ khoá tới 60 giây, và thử lại lệnh
        # bật WAL vì SQLite có thể trả "database is locked" ngay (không qua busy timeout) khi hai tiến trình cùng đổi
        # journal mode của một file mới.
        self.conn = sqlite3.connect(paths.state / "crawl_state.sqlite", timeout=60)
        for attempt in range(40):
            try:
                self.conn.execute("PRAGMA journal_mode=WAL")
                break
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc) or attempt == 39:
                    raise
                time.sleep(0.05 * (attempt + 1))
        # Tạo/nâng cấp schema trong một transaction giữ khoá ghi: tiến trình khác chờ tới lượt thay vì cùng ALTER TABLE.
        self.conn.execute("BEGIN IMMEDIATE")
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS items (
                source TEXT NOT NULL,
                url TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 100,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                meta TEXT,
                updated_at TEXT,
                PRIMARY KEY (source, url)
            )"""
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_items_status ON items(source, status, priority)")
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS discovery (
                source TEXT NOT NULL,
                key TEXT NOT NULL,
                found INTEGER,
                done_at TEXT,
                PRIMARY KEY (source, key)
            )"""
        )
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(items)")}
        if "plan" not in cols:  # nâng cấp DB cũ
            self.conn.execute("ALTER TABLE items ADD COLUMN plan TEXT")
        self.conn.commit()

    def add_many(self, source: str, rows: Iterable[tuple]) -> int:
        """rows: (url, priority) hoặc (url, priority, plan_dict). URL đã có thì giữ trạng thái và plan của lần
        phát hiện đầu tiên (điểm đến, thứ hạng), chỉ nhận priority tốt hơn."""
        before = self.conn.total_changes
        now = now_iso()
        for row in rows:
            url, prio = row[0], row[1]
            plan = json.dumps(row[2], ensure_ascii=False) if len(row) > 2 and row[2] else None
            self.conn.execute(
                """INSERT INTO items(source, url, priority, plan, updated_at) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(source, url) DO UPDATE SET
                     plan = COALESCE(items.plan, excluded.plan),
                     priority = MIN(items.priority, excluded.priority)""",
                (source, url, prio, plan, now),
            )
        self.conn.commit()
        return self.conn.total_changes - before

    def is_discovered(self, source: str, key: str) -> bool:
        return self.conn.execute("SELECT 1 FROM discovery WHERE source = ? AND key = ?", (source, key)).fetchone() is not None

    def mark_discovered(self, source: str, key: str, found: int) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO discovery(source, key, found, done_at) VALUES (?, ?, ?, ?)",
            (source, key, found, now_iso()),
        )
        self.conn.commit()

    def plan_of(self, source: str, url: str) -> dict:
        row = self.conn.execute("SELECT plan FROM items WHERE source = ? AND url = ?", (source, url)).fetchone()
        return json.loads(row[0]) if row and row[0] else {}

    def urls_with_plan(self, source: str) -> list[tuple[str, dict, str]]:
        cur = self.conn.execute("SELECT url, plan, status FROM items WHERE source = ? AND plan IS NOT NULL", (source,))
        return [(u, json.loads(p), st) for u, p, st in cur]

    def pending(self, source: str, max_attempts: int) -> list[str]:
        cur = self.conn.execute(
            """SELECT url FROM items
               WHERE source = ? AND (status = 'pending' OR (status = 'failed' AND attempts < ?))
               ORDER BY priority, attempts, rowid""",
            (source, max_attempts),
        )
        return [r[0] for r in cur]

    def done_items(self, source: str) -> list[tuple[str, dict]]:
        cur = self.conn.execute(
            "SELECT url, meta FROM items WHERE source = ? AND status = 'done' ORDER BY rowid", (source,)
        )
        return [(u, json.loads(m) if m else {}) for u, m in cur]

    def mark(self, source: str, url: str, status: str, error: str | None = None, meta: dict | None = None) -> None:
        inc = 1 if status in ("failed", "blocked") else 0
        self.conn.execute(
            """UPDATE items SET status = ?, attempts = attempts + ?, last_error = ?,
               meta = COALESCE(?, meta), updated_at = ? WHERE source = ? AND url = ?""",
            (
                "failed" if status == "blocked" else status,
                inc,
                (error or "")[:500] or None,
                json.dumps(meta, ensure_ascii=False) if meta is not None else None,
                now_iso(),
                source,
                url,
            ),
        )
        self.conn.commit()

    def counts(self, source: str | None = None) -> dict[str, dict[str, int]]:
        q = "SELECT source, status, COUNT(*) FROM items"
        args: tuple = ()
        if source:
            q += " WHERE source = ?"
            args = (source,)
        q += " GROUP BY source, status"
        out: dict[str, dict[str, int]] = {}
        for src, status, n in self.conn.execute(q, args):
            out.setdefault(src, {})[status] = n
        return out

    def reset_failed(self, source: str) -> int:
        cur = self.conn.execute(
            "UPDATE items SET status = 'pending', attempts = 0 WHERE source = ? AND status = 'failed'", (source,)
        )
        self.conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self.conn.close()


# --------------------------------------------------------------------------- politeness


class HostRateLimiter:
    """Khoảng cách tối thiểu giữa hai request tới cùng một host (có jitter).
    Nhiều worker dùng chung nên tổng tốc độ mỗi host không vượt 1/min_interval."""

    def __init__(self, min_interval: float, jitter: float = 0.35, per_host: dict[str, float] | None = None):
        self.min_interval = min_interval
        self.jitter = jitter
        self.per_host = per_host or {}
        self._next: dict[str, float] = {}      # mốc sớm nhất do bị phạt (penalise)
        self._last: dict[str, float] = {}      # lúc request gần nhất tới host
        self._factor: dict[str, float] = {}    # jitter của khoảng chờ kế tiếp
        self._locks: dict[str, asyncio.Lock] = {}
        self.shared_db = os.environ.get("CRAWL_RATE_DB")
        if self.shared_db:
            Path(self.shared_db).parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.shared_db, timeout=30) as db:
                db.execute("CREATE TABLE IF NOT EXISTS rate_slots (host TEXT PRIMARY KEY, ready REAL NOT NULL, interval REAL NOT NULL)")

    def reserve_shared(self, host: str, interval: float) -> float:
        """Atomic cross-process reservation; wall time survives process restarts."""
        with sqlite3.connect(self.shared_db, timeout=30) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT ready, interval FROM rate_slots WHERE host=?", (host,)).fetchone()
            interval = max(interval, row[1] if row else 0)
            ready = max(time.time(), row[0] if row else 0)
            db.execute("INSERT OR REPLACE INTO rate_slots VALUES (?, ?, ?)", (host, ready + interval, interval))
        return ready

    def set_interval(self, host: str, seconds: float) -> None:
        self.per_host[host] = max(self.per_host.get(host, 0.0), seconds)

    async def wait(self, url_or_host: str) -> None:
        host = urlsplit(url_or_host).netloc or url_or_host
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            if self.shared_db:
                control = await live_control.hold_while_paused()
                base = control["delay"] if control.get("delay") is not None else self.min_interval
                interval = max(base, self.per_host.get(host, 0.0))
                ready = self.reserve_shared(host, interval * (1 + random.uniform(0, self.jitter)))
                await asyncio.sleep(max(0, ready - time.time()))
                return
            # Monitor có thể tạm dừng nguồn hoặc đổi delay khi lượt đang chạy (collectors/live_control.py): tính lại mốc
            # chờ mỗi giây để thay đổi có hiệu lực ngay cả giữa một khoảng chờ dài.
            while True:
                control = await live_control.hold_while_paused()
                base = control["delay"] if control.get("delay") is not None else self.min_interval
                interval = max(base, self.per_host.get(host, 0.0))
                last = self._last.get(host)
                ready = self._next.get(host, 0.0)
                if last is not None:
                    ready = max(ready, last + interval * self._factor.get(host, 1.0))
                now = time.monotonic()
                if ready <= now:
                    break
                await asyncio.sleep(min(ready - now, 1.0))
            self._last[host] = time.monotonic()
            self._factor[host] = 1 + random.uniform(0, self.jitter)

    def penalise(self, url_or_host: str, seconds: float) -> None:
        host = urlsplit(url_or_host).netloc or url_or_host
        if self.shared_db:
            with sqlite3.connect(self.shared_db, timeout=30) as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("INSERT INTO rate_slots VALUES (?, ?, ?) ON CONFLICT(host) DO UPDATE SET ready=MAX(ready, excluded.ready)",
                           (host, time.time() + seconds, self.min_interval))
        self._next[host] = max(self._next.get(host, 0.0), time.monotonic() + seconds)


class Robots:
    """robots.txt theo từng host (hỗ trợ wildcard nhờ protego). Tôn trọng Crawl-delay."""

    def __init__(self, client: httpx.AsyncClient, limiter: HostRateLimiter, user_agent: str = "*"):
        self.client = client
        self.limiter = limiter
        self.ua = user_agent
        self._cache: dict[str, Protego | None] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def _load(self, origin: str) -> Protego | None:
        url = f"{origin}/robots.txt"
        try:
            r = await self.client.get(url, timeout=30)
        except httpx.HTTPError as e:
            log.warning("Không tải được %s (%s) – coi như cho phép", url, e)
            return None
        if r.status_code >= 500:
            log.warning("%s trả %s – tạm coi như cấm", url, r.status_code)
            return Protego.parse("User-agent: *\nDisallow: /")
        if r.status_code >= 400:
            return None
        rp = Protego.parse(r.text)
        delay = rp.crawl_delay(self.ua)
        if delay:
            self.limiter.set_interval(urlsplit(origin).netloc, float(delay))
        return rp

    async def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        lock = self._locks.setdefault(origin, asyncio.Lock())
        async with lock:
            if origin not in self._cache:
                self._cache[origin] = await self._load(origin)
        rp = self._cache[origin]
        return True if rp is None else rp.can_fetch(url, self.ua)


class Http:
    """httpx cho những endpoint không cần trình duyệt (sitemap, API không bị chặn)."""

    def __init__(self, limiter: HostRateLimiter, respect_robots: bool = True):
        self.client = httpx.AsyncClient(
            headers={"User-Agent": CRAWLER_UA, "Accept-Encoding": "gzip, deflate"},
            follow_redirects=True,
            timeout=httpx.Timeout(60, connect=20),
            http2=False,
        )
        self.limiter = limiter
        self.robots = Robots(self.client, limiter) if respect_robots else None

    async def get(self, url: str, *, headers: dict | None = None, retries: int = 4) -> httpx.Response:
        if self.robots and not await self.robots.allowed(url):
            raise PermissionError(f"robots.txt không cho phép: {url}")
        delay = 5.0
        for attempt in range(1, retries + 1):
            await self.limiter.wait(url)
            t0 = time.monotonic()
            try:
                r = await self.client.get(url, headers=headers)
            except httpx.HTTPError as e:
                log.debug("GET %s → lỗi %s sau %.0f ms (lần %d)", url, type(e).__name__, (time.monotonic() - t0) * 1000, attempt)
                if attempt == retries:
                    raise
                log.warning("Lỗi mạng %s (%s) – thử lại sau %.0fs", url, e, delay)
                await asyncio.sleep(delay)
                delay *= 2
                continue
            log.debug("GET %s → HTTP %s · %.0f ms · %d B (lần %d)", url, r.status_code,
                      (time.monotonic() - t0) * 1000, len(r.content), attempt)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = _retry_after(r) or delay
                log.warning("%s trả %s – chờ %.0fs rồi thử lại", url, r.status_code, wait)
                self.limiter.penalise(url, wait)
                await asyncio.sleep(wait)
                delay *= 2
                continue
            return r
        raise RuntimeError("unreachable")

    async def close(self) -> None:
        await self.client.aclose()


def _retry_after(r: httpx.Response) -> float | None:
    v = r.headers.get("Retry-After")
    if not v:
        return None
    try:
        return min(float(v), 900.0)
    except ValueError:
        return None


# --------------------------------------------------------------------------- browser


class ChallengeBlocked(Exception):
    """Trang thử thách chống bot không qua được trong thời gian cho phép."""


class PageGone(Exception):
    """URL không còn trỏ tới sản phẩm (redirect đi nơi khác / 404)."""


CHALLENGE_TITLES = (
    "just a moment", "attention required", "checking your browser", "chờ một chút", "một chút thôi",
    "performing security verification", "access denied",
)
# Chỉ những dấu hiệu có trên trang thử thách, KHÔNG có trên trang thường
# (Cloudflare chèn /cdn-cgi/challenge-platform vào cả trang thường nên không dùng được).
CHALLENGE_MARKERS = ("cf_chl_opt", 'id="challenge-error-text"', 'id="challenge-running"', "reportChallengeError", "/chal_report")


def looks_like_challenge(html: str, title: str | None = None) -> bool:
    if title is None:
        m = re.search(r"<title[^>]*>(.*?)</title>", html[:5000], re.S | re.I)
        title = m.group(1) if m else ""
    t = (title or "").strip().lower()
    if any(x in t for x in CHALLENGE_TITLES):
        return True
    head = html[:20000]
    return any(m in head for m in CHALLENGE_MARKERS)


@dataclass
class BrowserOptions:
    locale: str = "vi-VN"
    headless: bool = False
    block_resources: bool = True
    fast: bool = False  # không chờ tải xong trang + chặn CSS/tracker: dữ liệu cần đã có trong HTML server trả về
    challenge_timeout: float = 45.0
    manual_wait: float = 300.0
    pages_before_recycle: int = 150
    # Mở lại hẳn Chromium sau ngần này trang (0 = không): RAM của trình duyệt tăng dần theo số trang dù đã thay tab (lượt VM
    # 08/10/2026: Booking từ ~1 lên ~2 GB sau 24 trang; đo local cây tiến trình Booking 125 trang: đỉnh PSS 2.485 MB, thường
    # 1,9–2,3 GB); làm mới ~1.800 khách sạn trên VM 4 GB (job giới hạn FRESH_MEMORY 2500m) cần chặn mức này.
    pages_before_restart: int = 100
    channel: str | None = None


@dataclass
class FetchResult:
    html: str
    final_url: str
    title: str
    elapsed: float
    extra: dict = field(default_factory=dict)


def clean_browser_cache(profile_dir: Path) -> None:
    """Xóa các thư mục cache tạm của Chromium (Cache, Code Cache, GPUCache...) để tránh đầy ổ đĩa VM."""
    if not profile_dir.is_dir():
        return
    cache_subs = (
        "Default/Cache",
        "Default/Code Cache",
        "Default/GPUCache",
        "Default/DawnGraphiteCache",
        "Default/DawnWebGPUCache",
        "GrShaderCache",
        "ShaderCache",
        "GPUCache",
    )
    for sub in cache_subs:
        target = profile_dir / sub
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)


class BrowserSession:
    """Chromium thật qua Playwright, profile bền vững theo từng site.

    Không có kỹ thuật che giấu nào: không stealth plugin, không đổi fingerprint,
    không proxy, không giải CAPTCHA. Trang thử thách JavaScript tự hoàn tất như
    trình duyệt bình thường; nếu vẫn bị chặn thì dừng, chờ, hoặc để người dùng tự
    xử lý trong cửa sổ trình duyệt (chế độ có giao diện)."""

    def __init__(self, paths: Paths, name: str, opts: BrowserOptions):
        self.paths = paths
        self.name = name
        self.opts = opts
        self._pw = None
        self.context = None
        self._manual_notice = 0.0

    async def __aenter__(self) -> "BrowserSession":
        try:
            from playwright.async_api import async_playwright
        except ImportError as e:  # pragma: no cover
            raise SystemExit("Thiếu Playwright: pip install -r requirements.txt && playwright install chromium") from e
        self._pw = await async_playwright().start()
        profile = self.paths.profiles / self.name
        profile.mkdir(parents=True, exist_ok=True)
        launch: dict[str, Any] = dict(
            user_data_dir=str(profile),
            headless=self.opts.headless,
            locale=self.opts.locale,
            timezone_id="Asia/Ho_Chi_Minh",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9" if self.opts.locale == "en-US" else "vi-VN,vi;q=0.9,en;q=0.6"},
        )
        if self.opts.channel:
            launch["channel"] = self.opts.channel
        self._launch = launch
        try:
            await self._open_context()
        except Exception as e:
            await self._pw.stop()
            if "Executable doesn't exist" in str(e):
                raise SystemExit("Chưa cài trình duyệt cho Playwright. Chạy: playwright install chromium") from e
            if "headed browser without having a XServer" in str(e) or "Missing X server" in str(e):
                raise SystemExit("Không có màn hình để mở trình duyệt. Chạy lại với --headless") from e
            raise
        return self

    async def _open_context(self) -> None:
        self.context = await self._pw.chromium.launch_persistent_context(**self._launch)
        if self.opts.block_resources:
            await self.context.route("**/*", _block_fast if self.opts.fast else _block_heavy)

    async def restart(self) -> None:
        """Đóng rồi mở lại Chromium (cùng profile, cùng chế độ chặn tài nguyên) khi trình duyệt không mở được tab mới
        nữa (vd. "Target.createTarget: Failed to open a new tab"); tab cũ của context trước đều không dùng được nữa."""
        try:
            await self.context.close()
        except Exception as e:
            log.debug("Đóng trình duyệt trước khi mở lại: %s", e)
        await self._open_context()

    async def set_fast(self, fast: bool) -> None:
        """Đổi chế độ chặn tài nguyên giữa chừng. Trang tìm kiếm Booking chỉ tải thêm kết quả khi có CSS (cuộn không
        kích hoạt được khi bị chặn), nên bước tìm URL tạm tắt --fast rồi bật lại cho các trang khách sạn."""
        if not self.opts.block_resources or self.opts.fast == fast:
            return
        await self.context.unroute("**/*")
        self.opts = replace(self.opts, fast=fast)
        await self.context.route("**/*", _block_fast if fast else _block_heavy)

    async def __aexit__(self, *exc) -> None:
        try:
            if self.context:
                await self.context.close()
        except Exception as e:  # cửa sổ đã bị đóng tay / trình duyệt đã thoát
            log.debug("Đóng trình duyệt: %s", e)
        finally:
            if self._pw:
                await self._pw.stop()
            clean_browser_cache(self.paths.profiles / self.name)

    async def new_page(self):
        pages = self.context.pages
        if pages and pages[0].url in ("about:blank", ""):
            page = pages[0]
        else:
            page = await self.context.new_page()
        page.set_default_timeout(60_000)
        return page

    async def _looks_like_challenge(self, page) -> bool:
        try:
            title = await page.title()
            head = await page.evaluate(
                "() => (document.documentElement ? document.documentElement.outerHTML.slice(0, 20000) : '')"
            )
        except Exception:
            return True  # đang điều hướng giữa chừng
        return looks_like_challenge(head, title)

    async def fetch_html(
        self,
        page,
        url: str,
        ready_selector: str,
        expect_url: re.Pattern | None = None,
        settle_ms: int = 800,
        error_markers: tuple[str, ...] = (),
    ) -> FetchResult:
        t0 = time.monotonic()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        except Exception as e:
            soft = ("ERR_ABORTED", "interrupted by another navigation", "Timeout")
            if not any(x in str(e) or x in type(e).__name__ for x in soft):
                raise
            log.debug("[%s] goto %s: %s – tiếp tục chờ nội dung", self.name, url, str(e)[:120])
        deadline = t0 + self.opts.challenge_timeout
        manual = False
        while True:
            challenged = await self._looks_like_challenge(page)
            if not challenged:
                try:
                    if await page.query_selector(ready_selector):
                        break
                    if error_markers:
                        text = await page.evaluate("() => document.body ? document.body.innerText.slice(0, 4000) : ''")
                        if any(m in text for m in error_markers):
                            break  # trang lỗi của website: trả về luôn để parser đánh dấu thử lại sau
                except Exception:
                    pass  # đang điều hướng giữa chừng
            now = time.monotonic()
            if not challenged and now - t0 > 8:
                if expect_url is not None and not expect_url.search(page.url):
                    raise PageGone(f"chuyển hướng sang {page.url}")
            if now > deadline:
                if challenged and not self.opts.headless and not manual:
                    manual = True
                    deadline = now + self.opts.manual_wait
                    if now - self._manual_notice > 120:
                        self._manual_notice = now
                        log.warning(
                            "[%s] Trang thử thách chưa qua sau %.0fs. Nếu cửa sổ trình duyệt hiện yêu cầu xác minh, "
                            "hãy tự xử lý trong cửa sổ đó; script chờ tối đa %.0fs.",
                            self.name,
                            self.opts.challenge_timeout,
                            self.opts.manual_wait,
                        )
                    continue
                if challenged:
                    raise ChallengeBlocked(f"bị chặn bởi trang thử thách: {url}")
                break  # không thấy selector nhưng cũng không bị chặn: để parser quyết định
            await asyncio.sleep(1.0)
        if not self.opts.fast:
            try:
                await page.wait_for_load_state("load", timeout=15_000)
            except Exception:
                pass
            if settle_ms:
                await page.wait_for_timeout(settle_ms)
        html = await page.content()
        title = await page.title()
        if looks_like_challenge(html, title):
            log.debug("[%s] mở %s → trang thử thách sau %.1f s", self.name, url, time.monotonic() - t0)
            raise ChallengeBlocked(f"bị chặn bởi trang thử thách: {url}")
        log.debug("[%s] mở %s → %s · %.1f s · %d B HTML", self.name, url, page.url, time.monotonic() - t0, len(html))
        return FetchResult(html=html, final_url=page.url, title=title, elapsed=time.monotonic() - t0)

    async def fetch_json(
        self, page, url: str, *, method: str = "GET", body: Any = None, headers: dict | None = None
    ) -> tuple[int, Any]:
        """Gọi API từ bên trong trang (cùng origin với frontend, như chính website gọi).

        `body` là dict (tự json.stringify) hoặc chuỗi đã encode sẵn; bỏ trống với GET."""
        payload = body if body is None or isinstance(body, str) else json.dumps(body)
        status, text = await page.evaluate(
            """async ([url, method, payload, headers]) => {
                const init = { method, headers: headers || {} };
                if (payload !== null) init.body = payload;
                const r = await fetch(url, init);
                return [r.status, await r.text()];
            }""",
            [url, method, payload, headers or {}],
        )
        try:
            return status, json.loads(text)
        except json.JSONDecodeError:
            return status, text


async def _block_heavy(route) -> None:
    if route.request.resource_type in ("image", "media", "font"):
        await route.abort()
    else:
        await route.continue_()


_TRACKER_HOSTS = re.compile(
    r"(googletagmanager|google-analytics|doubleclick|googleadservices|facebook\.net|clarity\.ms|tiktok|"
    r"yandex|hotjar|criteo|bing\.com|useinsider|kakao|naver|daum\.net|affilired)", re.I,
)


async def _block_fast(route) -> None:
    req = route.request
    if req.resource_type in ("image", "media", "font", "stylesheet") or _TRACKER_HOSTS.search(req.url):
        await route.abort()
    else:
        await route.continue_()


class RunLock:
    """Không cho chạy cùng một nguồn ở hai tiến trình (sẽ crawl trùng URL và tranh profile trình duyệt)."""

    def __init__(self, paths: Paths, name: str):
        self.path = paths.state / f"{name}.lock"
        self._fh = None

    def __enter__(self) -> "RunLock":
        self._fh = open(self.path, "a+")
        try:
            import fcntl

            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:  # Windows: bỏ qua khoá
            pass
        except OSError:
            self._fh.close()
            raise SystemExit(
                f"Nguồn '{self.path.stem}' đang được một tiến trình khác chạy (khoá {self.path}). "
                "Mỗi nguồn chỉ chạy một tiến trình; muốn nhanh hơn thì tăng --concurrency."
            )
        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(str(os.getpid()))
        self._fh.flush()
        return self

    def __exit__(self, *exc) -> None:
        if self._fh:
            self._fh.close()


class BlockBreaker:
    """Dừng cả lượt chạy khi bị chặn liên tiếp, thay vì tiếp tục gõ cửa."""

    def __init__(self, limit: int):
        self.limit = limit
        self.streak = 0
        self.tripped = False

    def ok(self) -> None:
        self.streak = 0

    def blocked(self) -> bool:
        self.streak += 1
        if self.streak >= self.limit:
            self.tripped = True
        return self.tripped

    def cooldown(self) -> float:
        return min(60.0 * (2 ** (self.streak - 1)), 900.0)


class Progress:
    def __init__(self, label: str, total: int, every: float = 30.0):
        self.label, self.total, self.every = label, total, every
        self.done = self.failed = self.skipped = 0
        self.t0 = self._last = time.monotonic()

    def tick(self, kind: str = "done") -> None:
        setattr(self, kind, getattr(self, kind) + 1)
        now = time.monotonic()
        if now - self._last >= self.every:
            self._last = now
            self.report()

    def report(self) -> None:
        n = self.done + self.failed + self.skipped
        rate = n / max(time.monotonic() - self.t0, 1e-6)
        left = max(self.total - n, 0)
        eta = left / rate if rate > 0 else float("inf")
        log.info(
            "[%s] %d/%d xong · %d lỗi · %d bỏ qua · %.2f trang/phút · còn ~%s",
            self.label, self.done, self.total, self.failed, self.skipped, rate * 60, _fmt_eta(eta),
        )


def _fmt_eta(seconds: float) -> str:
    if seconds == float("inf"):
        return "?"
    h, rem = divmod(int(seconds), 3600)
    m = rem // 60
    return f"{h}h{m:02d}m" if h else f"{m}m"
