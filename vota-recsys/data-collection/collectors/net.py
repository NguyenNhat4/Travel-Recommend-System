"""Shared network machinery: robots, rate limiting, retry, block detection.

None of this is per-collector. A source module says which URLs exist and how to
read one; everything about *how politely* we ask lives here, once, so a new
collector cannot accidentally opt out of the spec section 8 rules.
"""

from __future__ import annotations

import logging
import random
import re
import threading
import time
import urllib.robotparser
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

from collectors.base import BlockedError, RobotsDenied, RobotsUnavailable
from runtime import shutdown

log = logging.getLogger("net")


# =============================================================================
# rate limiting
# =============================================================================
class DomainRateLimiter:
    """At most ``rps`` requests per second **per host**, across all threads.

    Keyed on the actual request host, not on a collector name: an API collector
    whose ``hosts`` list disagreed with its ``base_url`` would otherwise get a
    bucket for a host it never calls, leaving the real one unthrottled.

    ``domain_aliases`` merges hosts that sit on the same infrastructure, so
    ``vinpearl.com`` and ``vinwonders.com`` share one 0.5 rps budget rather than
    getting 0.5 each.
    """

    def __init__(self, default_rps: float, aliases: dict[str, str] | None = None) -> None:
        self.default_rps = max(default_rps, 0.01)
        self.aliases = {k.lower(): v.lower() for k, v in (aliases or {}).items()}
        self._next_allowed: dict[str, float] = {}
        self._rps: dict[str, float] = {}
        self._lock = threading.Lock()

    def bucket(self, url: str) -> str:
        host = urlsplit(url).netloc.lower()
        return self.aliases.get(host, host)

    def set_rps(self, url: str, rps: float) -> None:
        with self._lock:
            self._rps[self.bucket(url)] = max(rps, 0.01)

    def acquire(self, url: str) -> float:
        """Block until this host may be called again. Returns seconds waited."""
        key = self.bucket(url)
        waited = 0.0
        while True:
            with self._lock:
                rps = self._rps.get(key, self.default_rps)
                interval = 1.0 / rps
                now = time.monotonic()
                nxt = self._next_allowed.get(key, 0.0)
                if now >= nxt:
                    self._next_allowed[key] = now + interval
                    return waited
                sleep_for = nxt - now
            # shutdown.wait rather than time.sleep: on Windows a plain sleep in a
            # worker thread is not interruptible, so Ctrl-C during a rate-limit
            # pause would look like a hang.
            if shutdown.wait(min(sleep_for, 1.0)):
                return waited
            waited += min(sleep_for, 1.0)


# =============================================================================
# robots.txt
# =============================================================================
@dataclass
class RobotsDecision:
    allowed: bool
    crawl_delay: float | None
    fetched: bool
    status: int | None


class RobotsGate:
    """Checks robots.txt once per host and caches the answer.

    When robots.txt itself cannot be fetched we do **not** assume allow: the
    config default is ``abort``, because guessing in our own favour about the
    one file whose whole purpose is to say no is not a defensible reading of
    spec section 8.

    A 404 is different from a failure — a site with no robots.txt has not
    disallowed anything — so that case is treated as allow-all, which is what
    the standard says.
    """

    def __init__(self, user_agent: str, *, on_unavailable: str = "abort", ttl_s: int = 3600) -> None:
        self.user_agent = user_agent
        self.on_unavailable = on_unavailable
        self.ttl_s = ttl_s
        self._cache: dict[str, tuple[float, urllib.robotparser.RobotFileParser | None, int | None]] = {}
        self._lock = threading.Lock()

    def _load(self, base: str, client: httpx.Client) -> tuple[urllib.robotparser.RobotFileParser | None, int | None]:
        url = f"{base}/robots.txt"
        try:
            resp = client.get(url, timeout=15.0)
        except httpx.HTTPError as exc:
            log.warning("robots.txt unreachable at %s: %s", url, exc)
            return None, None
        if resp.status_code == 404:
            log.info("no robots.txt at %s (404) — nothing disallowed", url)
            rp = urllib.robotparser.RobotFileParser()
            rp.parse([])
            return rp, 404
        if resp.status_code >= 400:
            log.warning("robots.txt %s returned %s", url, resp.status_code)
            return None, resp.status_code
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(resp.text.splitlines())
        log.info("robots.txt loaded from %s (%d bytes)", url, len(resp.content))
        return rp, resp.status_code

    def check(self, url: str, client: httpx.Client) -> RobotsDecision:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(base)
            if cached and (now - cached[0]) < self.ttl_s:
                rp, status = cached[1], cached[2]
            else:
                rp, status = self._load(base, client)
                self._cache[base] = (now, rp, status)

        if rp is None:
            if self.on_unavailable == "allow":
                log.warning("robots.txt unavailable for %s; config says allow", base)
                return RobotsDecision(True, None, False, status)
            return RobotsDecision(False, None, False, status)

        allowed = rp.can_fetch(self.user_agent, url)
        delay = rp.crawl_delay(self.user_agent)
        return RobotsDecision(allowed, float(delay) if delay else None, True, status)


def robots_report(cfg, src) -> list[str]:  # noqa: ANN001
    """Lines for ``cli robots-check``. Fetches robots.txt and nothing else."""
    lines = [f"source: {src.name}", f"user-agent: {cfg.user_agent}"]
    if not src.respect_robots:
        lines.append("respect_robots: false (local source, nothing is fetched)")
        return lines
    gate = RobotsGate(
        cfg.user_agent,
        on_unavailable=str(cfg.section("robots").get("on_unavailable", "abort")),
        ttl_s=int(cfg.section("robots").get("cache_ttl_s", 3600)),
    )
    with build_client(cfg, src) as client:
        probes = [src.base_url or ""]
        for pat in src.get("url_patterns", []) or []:
            probes.append((src.base_url or "") + "/vi/khach-san/example")
            break
        for seed in (src.get("link_harvest", {}) or {}).get("seeds", []) or []:
            probes.append(seed)
        for sm in src.get("sitemaps", []) or []:
            probes.append(sm)
        # Sources that address their endpoints directly (an API collector with
        # `overpass_url`/`wikivoyage_api` and no `base_url`) would otherwise
        # report nothing at all, which reads as "checked and fine".
        for key in ("overpass_url", "wikivoyage_api", "wikipedia_api"):
            if src.get(key):
                probes.append(str(src.get(key)))
        # The URLs we would ACTUALLY request. Probing only the homepage is
        # actively misleading: every OTA allows `/` and disallows the search
        # results underneath it, so a report showing "ALLOW https://booking.com"
        # reads as a green light for a crawl that robots.txt forbids.
        template = str(src.get("listing_url_template", ""))
        if template:
            try:
                sample = template.format(
                    destination="Nha Trang", city="Nha Trang", city_id="Nha Trang",
                    checkin="2026-10-15", checkout="2026-10-16", nights=1,
                    adults=2, rooms=1, offset=0, page=1,
                )
                probes.append(sample)
            except (KeyError, IndexError) as exc:  # pragma: no cover - bad template
                lines.append(f"  (listing_url_template not renderable: {exc})")
        for host in src.hosts:
            probes.append(f"https://{host}/")
        seen = set()
        for url in probes:
            if not url or url in seen:
                continue
            seen.add(url)
            d = gate.check(url, client)
            verdict = "ALLOW" if d.allowed else "DISALLOW"
            extra = f" crawl-delay={d.crawl_delay}" if d.crawl_delay else ""
            if not d.fetched:
                extra += f" (robots.txt not readable, status={d.status})"
            lines.append(f"  {verdict:9} {url}{extra}")
    return lines


# =============================================================================
# block detection (spec sections 1, 9, 13)
# =============================================================================
_SCRIPTISH_RE = re.compile(
    r"<(?:script|style|template)[^>]*>.*?</(?:script|style|template)>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
# Any opening script/style/template tag still present AFTER the paired rule has
# run is orphaned - its closing tag was lost to truncation.
_ORPHAN_OPEN_RE = re.compile(r"<(?:script|style|template)[^>]*>", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def _looks_like_html(lowered_body: str) -> bool:
    head = lowered_body[:2000]
    return "<html" in head or "<!doctype html" in head or "<body" in head


def _visible_text(body: str) -> str:
    """Readable text only: scripts, styles and tags removed.

    ``<noscript>`` is deliberately kept. We are a non-JavaScript client, so its
    content is exactly what we can see — and it is where the interesting text
    lives: booking.com puts "we need to verify that you're not a robot" in a
    noscript block, so stripping it would report 0 visible characters and throw
    away the one line that explains the block.

    Regex rather than a parser because this runs on every fetched page inside
    the hot path, and the answer only has to be "roughly how much prose is
    here".
    """
    stripped = _SCRIPTISH_RE.sub(" ", body)
    # A truncated page can end inside a <script>, leaving the paired rule above
    # with no closing tag to match. Cut from the orphaned opening tag to the end,
    # or the JavaScript source itself gets counted as prose - which is exactly
    # how agoda's 218 KB JS-only page scored as "plenty of text" and slipped
    # past the empty-shell rule.
    orphan = _ORPHAN_OPEN_RE.search(stripped)
    if orphan:
        stripped = stripped[: orphan.start()]
    stripped = _TAG_RE.sub(" ", stripped)
    return _WS_RE.sub(" ", stripped).strip()


def _visible_text_length(body: str) -> int:
    return len(_visible_text(body))


@dataclass
class BlockDetector:
    """Decides when a source is refusing us, so the runner can stop.

    Getting this right is what makes the "do not circumvent" rule operational.
    The failure mode it prevents is not ethical hand-wringing — it is spending
    Tuesday retrying a site that decided on Monday it did not want us, and
    arriving at Wednesday's checkpoint with nothing.
    """

    consecutive_threshold: int = 3
    body_markers: tuple[str, ...] = ()
    empty_shell_max_text: int = 200
    _streak: int = field(default=0, repr=False)

    def inspect(self, *, status: int, body: bytes, url: str) -> dict[str, Any] | None:
        if status in (403, 429):
            self._streak += 1
            if self._streak >= self.consecutive_threshold:
                return {"status": status, "url": url, "marker": f"{self._streak}x{status}"}
            return None

        if 200 <= status < 300:
            self._streak = 0
            text = body[:200_000].decode("utf-8", errors="replace")
            lowered = text.lower()
            for marker in self.body_markers:
                if marker.lower() in lowered:
                    return {"status": status, "url": url, "marker": marker}

            # A 2xx that carries almost no readable text is the quiet form of a
            # block, and the one that actually happens: booking.com answers a
            # search URL with HTTP 202 and 4 KB saying "we need to verify that
            # you're not a robot". Matching on markers alone missed it, because
            # 202 is a success code and the wording changes; measuring the
            # visible text does not depend on the wording.
            #
            # Only for HTML — a JSON API response is legitimately tag-free and
            # would be flagged on every call.
            if self.empty_shell_max_text > 0 and _looks_like_html(lowered):
                visible = _visible_text_length(text)
                if visible <= self.empty_shell_max_text:
                    return {
                        "status": status,
                        "url": url,
                        "marker": f"empty-shell:{visible}-visible-chars",
                        "excerpt": _visible_text(text)[:200],
                    }
            return None

        self._streak = 0
        return None

    def reset(self) -> None:
        self._streak = 0


# =============================================================================
# client + fetching
# =============================================================================
def build_client(cfg, src) -> httpx.Client:  # noqa: ANN001
    """An httpx client with an honest identity and sane timeouts.

    The User-Agent comes from config/env and is validated to not impersonate a
    browser (``config.Config.user_agent`` raises on "Mozilla"). That check is
    not cosmetic: a browser UA on a crawler is the first step of anti-bot
    evasion, which spec section 1 rules out.
    """
    http = cfg.section("http")
    return httpx.Client(
        headers={
            "User-Agent": cfg.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/json,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.5",
        },
        timeout=httpx.Timeout(
            float(http.get("total_timeout_s", 60.0)),
            connect=float(http.get("connect_timeout_s", 10.0)),
            read=float(http.get("read_timeout_s", 30.0)),
        ),
        follow_redirects=bool(http.get("follow_redirects", True)),
        max_redirects=int(http.get("max_redirects", 5)),
    )


class NoNetFetcher:
    """Injected into collectors during ``parse``.

    "fetch không bao giờ parse, parse không bao giờ fetch" (spec section 2) is
    enforced, not trusted: if a parser reaches for the network — to resolve a
    lazy-loaded gallery, say — it raises here instead of quietly turning
    ``parse --reparse`` into a second crawl.
    """

    def get(self, *a, **kw):  # noqa: ANN002, ANN003, ARG002
        raise RuntimeError(
            "parse must not fetch (spec section 2). If a field needs another page, "
            "emit a Target for it from discover() so fetch can cache it."
        )

    request = get
    post = get


@dataclass
class FetchResult:
    url: str
    status: int
    content: bytes
    content_type: str
    attempts: int
    elapsed_ms: int
    waited_ms: int
    redirected_from: str | None = None


class TransientExhausted(RuntimeError):
    """Retried ``max_retries`` times and still failing."""


class Fetcher:
    """One HTTP GET/POST with robots, rate limiting, retry and block detection.

    Retry is hand-rolled rather than delegated to tenacity because the two rules
    that matter cannot be expressed as "retry on exception": 403 must **never**
    be retried (it is the block signal), and ``Retry-After`` must be honoured
    when the server sends it.
    """

    def __init__(
        self,
        cfg,  # noqa: ANN001
        src,  # noqa: ANN001
        *,
        client: httpx.Client,
        limiter: DomainRateLimiter,
        robots: RobotsGate | None,
        detector: BlockDetector,
    ) -> None:
        self.cfg = cfg
        self.src = src
        self.client = client
        self.limiter = limiter
        self.robots = robots
        self.detector = detector
        http = cfg.section("http")
        self.max_retries = int(http.get("max_retries", 3))
        self.backoff_base = float(http.get("backoff_base_s", 2.0))
        self.backoff_jitter = float(http.get("backoff_jitter_s", 0.5))
        self.retry_statuses = set(http.get("retry_statuses", [408, 429, 500, 502, 503, 504]))
        self.terminal_statuses = set(http.get("terminal_statuses", [400, 401, 403, 404, 410, 451]))
        self.honour_retry_after = bool(http.get("honour_retry_after", True))
        self.max_retry_after = float(http.get("max_retry_after_s", 120))
        self.max_bytes = int(http.get("max_bytes_per_page", 8_000_000))
        limiter.set_rps(src.base_url or "https://example.invalid", src.rate_limit_rps)

    # -- robots ------------------------------------------------------------
    def check_robots(self, url: str) -> None:
        if not self.src.respect_robots:
            return
        if str(self.src.get("robots_policy", "robots_txt")) == "api_terms":
            # A per-source, explicitly-configured exception for documented APIs
            # whose robots.txt disallows the API path to keep search engines out
            # (Overpass "Disallow: /api/", MediaWiki "Disallow: /w/"), while the
            # service publishes a usage policy for programmatic clients.
            #
            # Narrow on purpose. It does not disable robots for a website, it
            # cannot be set globally, and config.yaml requires a
            # `usage_policy_url` next to it — so the decision is greppable and
            # attributable rather than a blanket respect_robots: false that
            # would also excuse crawling a site that told us not to.
            log.info(
                "robots_policy=api_terms for %s: honouring the API usage policy at %s "
                "instead of robots.txt (%s)",
                self.src.name, self.src.get("usage_policy_url", "<unset>"), url,
            )
            return
        assert self.robots is not None
        d = self.robots.check(url, self.client)
        if not d.fetched and not d.allowed:
            # Could not read robots.txt at all. Distinct from a disallow: see
            # RobotsUnavailable for why the difference is worth a class.
            raise RobotsUnavailable(urlsplit(url).netloc, d.status)
        if not d.allowed:
            raise RobotsDenied(url)
        if d.crawl_delay:
            # A site asking for slower than our own limit wins.
            implied = 1.0 / d.crawl_delay
            if implied < self.src.rate_limit_rps:
                self.limiter.set_rps(url, implied)

    # -- the request -------------------------------------------------------
    def get(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        json_body: Any = None,
        data: Any = None,
    ) -> FetchResult:
        self.check_robots(url)
        waited_total = 0.0
        last_error: str = ""

        for attempt in range(1, self.max_retries + 1):
            if shutdown.requested:
                raise KeyboardInterrupt
            waited = self.limiter.acquire(url)
            waited_total += waited
            started = time.monotonic()
            try:
                resp = self.client.request(
                    method, url, headers=headers, json=json_body, data=data
                )
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                log.warning(
                    "fetch retry url=%s attempt=%d/%d err=%s",
                    url, attempt, self.max_retries, last_error,
                )
                if attempt < self.max_retries:
                    self._backoff(attempt)
                    continue
                raise TransientExhausted(last_error) from exc

            elapsed_ms = int((time.monotonic() - started) * 1000)
            body = resp.content
            if len(body) > self.max_bytes:
                log.warning(
                    "fetch skip url=%s bytes=%d exceeds max_bytes_per_page=%d",
                    url, len(body), self.max_bytes,
                )
                body = body[: self.max_bytes]

            blocked = self.detector.inspect(status=resp.status_code, body=body, url=url)
            if blocked:
                raise BlockedError(self.src.name, blocked)

            if resp.status_code in self.terminal_statuses:
                # No retry, by design. 403 in particular is a decision, not a
                # transient fault; retrying it is probing.
                return FetchResult(
                    url=str(resp.url),
                    status=resp.status_code,
                    content=body,
                    content_type=resp.headers.get("content-type", ""),
                    attempts=attempt,
                    elapsed_ms=elapsed_ms,
                    waited_ms=int(waited_total * 1000),
                    redirected_from=url if str(resp.url) != url else None,
                )

            if resp.status_code in self.retry_statuses and attempt < self.max_retries:
                retry_after = self._retry_after(resp)
                log.warning(
                    "fetch retry url=%s status=%d attempt=%d/%d retry_after=%s",
                    url, resp.status_code, attempt, self.max_retries, retry_after,
                )
                self._backoff(attempt, override=retry_after)
                continue

            return FetchResult(
                url=str(resp.url),
                status=resp.status_code,
                content=body,
                content_type=resp.headers.get("content-type", ""),
                attempts=attempt,
                elapsed_ms=elapsed_ms,
                waited_ms=int(waited_total * 1000),
                redirected_from=url if str(resp.url) != url else None,
            )

        raise TransientExhausted(last_error or "retries exhausted")

    def _retry_after(self, resp: httpx.Response) -> float | None:
        if not self.honour_retry_after:
            return None
        raw = resp.headers.get("retry-after")
        if not raw:
            return None
        try:
            return min(float(raw), self.max_retry_after)
        except ValueError:
            return None

    def _backoff(self, attempt: int, *, override: float | None = None) -> None:
        delay = override if override is not None else self.backoff_base ** attempt
        delay += random.uniform(0, self.backoff_jitter)
        if shutdown.wait(delay):
            raise KeyboardInterrupt


def make_fetcher(cfg, src, *, client: httpx.Client | None = None) -> Fetcher:  # noqa: ANN001
    rl = cfg.section("ratelimit")
    bd = cfg.section("block_detector")
    rb = cfg.section("robots")
    limiter = DomainRateLimiter(
        float(rl.get("default_rps", 0.5)), rl.get("domain_aliases") or {}
    )
    robots = (
        RobotsGate(
            cfg.user_agent,
            on_unavailable=str(rb.get("on_unavailable", "abort")),
            ttl_s=int(rb.get("cache_ttl_s", 3600)),
        )
        if src.respect_robots
        else None
    )
    detector = BlockDetector(
        consecutive_threshold=int(bd.get("consecutive_403_429", 3)),
        body_markers=tuple(bd.get("body_markers") or ()),
        empty_shell_max_text=int(bd.get("empty_shell_max_text_chars", 200)),
    )
    return Fetcher(
        cfg,
        src,
        client=client or build_client(cfg, src),
        limiter=limiter,
        robots=robots,
        detector=detector,
    )
