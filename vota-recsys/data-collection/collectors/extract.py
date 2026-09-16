"""Extraction helpers shared by every site collector.

Spec section 13's advice is to prefer embedded JSON over DOM scraping, because
"parse DOM vỡ mỗi lần site đổi layout". So the ranked strategy is JSON-LD, then
framework state blobs (``__NEXT_DATA__``, ``__NUXT__``, ``__INITIAL_STATE__``),
then CSS selectors as a last resort.

The one non-obvious rule here is :func:`jsonld_pick`: JSON-LD is read through an
**allowlist**, never stored verbatim. Real hotel and attraction pages nest
``review: [{author: {name: ...}, reviewBody: ...}]`` inside the ``Hotel``
object, so keeping the raw block would persist reviewer names into
``products_staging`` — a direct violation of spec section 5.4 — and would also
make the payload validator reject every page that has reviews, turning the
highest-value source into zero products.
"""

from __future__ import annotations

import html
import json
import logging
import re
import unicodedata
from typing import Any, Iterable, Iterator
from urllib.parse import urljoin, urlsplit

from selectolax.parser import HTMLParser

log = logging.getLogger("extract")

# =============================================================================
# JSON-LD
# =============================================================================
#: Keys kept from a schema.org node. Everything else is dropped before the
#: payload is built, including the review containers.
JSONLD_ALLOWED: frozenset[str] = frozenset(
    {
        "@type",
        "@id",
        "name",
        "description",
        "url",
        "image",
        "address",
        "geo",
        "telephone",
        "starRating",
        "priceRange",
        "offers",
        "price",
        "priceCurrency",
        "lowPrice",
        "highPrice",
        "availability",
        "validFrom",
        "validThrough",
        "openingHoursSpecification",
        "openingHours",
        "amenityFeature",
        "brand",
        "containedInPlace",
        "touristType",
        "aggregateRating",
        # Needed for the nested Rating node that `starRating` points at:
        # schema.org writes it as {"@type":"Rating","ratingValue":5}, so without
        # ratingValue in the allowlist starRating survives as an empty shell and
        # every hotel loses its star class.
        "ratingValue",
        "bestRating",
        "worstRating",
        "minValue",
        "maxValue",
        # address / geo / offer sub-fields
        "streetAddress",
        "addressLocality",
        "addressRegion",
        "postalCode",
        "addressCountry",
        "latitude",
        "longitude",
        "value",
        "unitText",
        "dayOfWeek",
        "opens",
        "closes",
        "itemOffered",
        "eligibleQuantity",
    }
)

#: The only rating fields spec section 5.4 permits.
AGGREGATE_RATING_ALLOWED: frozenset[str] = frozenset(
    {"@type", "ratingValue", "reviewCount", "ratingCount", "bestRating", "worstRating"}
)

#: Dropped outright, at any depth.
JSONLD_DENIED: frozenset[str] = frozenset(
    {"review", "reviews", "author", "publisher", "comment", "creator", "editor", "sameAs"}
)

_JSONLD_RE = re.compile(
    rb'<script[^>]+type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def jsonld_blocks(body: bytes) -> list[Any]:
    """Every parseable ``application/ld+json`` block, raw.

    Callers must pass results through :func:`jsonld_pick` before putting
    anything into a payload.
    """
    out: list[Any] = []
    for m in _JSONLD_RE.finditer(body):
        text = m.group(1).decode("utf-8", errors="replace").strip()
        if not text:
            continue
        try:
            out.append(json.loads(text))
        except json.JSONDecodeError:
            # Some sites emit JSON-LD with trailing commas or embedded
            # comments. One bad block must not lose the good ones.
            cleaned = re.sub(r",\s*([}\]])", r"\1", text)
            try:
                out.append(json.loads(cleaned))
            except json.JSONDecodeError:
                log.debug("unparseable JSON-LD block (%d chars)", len(text))
    return out


def jsonld_pick(node: Any, *, allowed: Iterable[str] | None = None) -> Any:
    """Recursively keep only allowlisted keys. See the module docstring."""
    allow = frozenset(allowed) if allowed is not None else JSONLD_ALLOWED
    return _pick(node, allow)


def _pick(node: Any, allow: frozenset[str]) -> Any:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for k, v in node.items():
            key = str(k)
            low = key.lower()
            if low in {d.lower() for d in JSONLD_DENIED}:
                continue
            if key == "aggregateRating":
                if isinstance(v, dict):
                    out[key] = {
                        kk: vv for kk, vv in v.items() if kk in AGGREGATE_RATING_ALLOWED
                    }
                continue
            if key not in allow:
                continue
            out[key] = _pick(v, allow)
        return out
    if isinstance(node, list):
        return [_pick(v, allow) for v in node]
    return node


def jsonld_of_type(blocks: list[Any], *types: str) -> list[dict[str, Any]]:
    """Flatten ``@graph`` containers and return nodes matching any ``@type``."""
    wanted = {t.lower() for t in types}
    found: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "@graph" in node:
                walk(node["@graph"])
            t = node.get("@type")
            ts = [t] if isinstance(t, str) else list(t or [])
            if any(str(x).lower() in wanted for x in ts):
                found.append(node)
            for v in node.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for b in blocks:
        walk(b)
    return found


# =============================================================================
# framework state blobs
# =============================================================================
_STATE_PATTERNS = (
    (rb'<script[^>]+id\s*=\s*["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', "__NEXT_DATA__"),
    (rb"window\.__NUXT__\s*=\s*(\{.*?\})\s*[;<]", "__NUXT__"),
    (rb"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*[;<]", "__INITIAL_STATE__"),
    (rb"window\.__APOLLO_STATE__\s*=\s*(\{.*?\})\s*[;<]", "__APOLLO_STATE__"),
    (rb"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*[;<]", "__PRELOADED_STATE__"),
)


def state_blob(body: bytes) -> tuple[dict[str, Any] | None, str | None]:
    """First framework state blob found, plus which one it was.

    Returned for *reading*, not for storing: these blobs also carry review
    nodes (booking's Apollo cache in particular), so a collector must copy out
    the individual fields it wants rather than keeping the object.
    """
    for pattern, label in _STATE_PATTERNS:
        m = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
        if not m:
            continue
        text = m.group(1).decode("utf-8", errors="replace")
        try:
            return json.loads(text), label
        except json.JSONDecodeError:
            log.debug("%s present but unparseable (%d chars)", label, len(text))
    return None, None


def next_data(body: bytes) -> dict[str, Any] | None:
    blob, label = state_blob(body)
    return blob if label == "__NEXT_DATA__" else None


def dig(node: Any, *path: str | int, default: Any = None) -> Any:
    """Safe nested access: ``dig(blob, 'props', 'pageProps', 'hotel', 'name')``."""
    cur = node
    for step in path:
        if isinstance(step, int):
            if not isinstance(cur, (list, tuple)) or not (-len(cur) <= step < len(cur)):
                return default
            cur = cur[step]
        else:
            if not isinstance(cur, dict) or step not in cur:
                return default
            cur = cur[step]
    return cur if cur is not None else default


def find_key(node: Any, key: str, *, limit: int = 20) -> list[Any]:
    """Every value stored under ``key`` anywhere in a nested structure.

    Useful when a site's state shape is unknown: find ``'roomTypes'`` without
    needing to know the path to it.
    """
    out: list[Any] = []

    def walk(n: Any) -> None:
        if len(out) >= limit:
            return
        if isinstance(n, dict):
            for k, v in n.items():
                if k == key:
                    out.append(v)
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(node)
    return out


# =============================================================================
# meta tags
# =============================================================================
def og_meta(body: bytes) -> dict[str, str]:
    """OpenGraph / twitter / description meta tags, keyed without the prefix."""
    tree = HTMLParser(body.decode("utf-8", errors="replace"))
    out: dict[str, str] = {}
    for node in tree.css("meta"):
        prop = node.attributes.get("property") or node.attributes.get("name") or ""
        content = node.attributes.get("content") or ""
        if not prop or not content:
            continue
        key = prop.lower()
        for prefix in ("og:", "twitter:", "product:"):
            if key.startswith(prefix):
                key = key[len(prefix) :]
                break
        out.setdefault(key, html.unescape(content).strip())
    return out


# =============================================================================
# DOM (last resort)
# =============================================================================
def tree_of(body: bytes) -> HTMLParser:
    return HTMLParser(body.decode("utf-8", errors="replace"))


def text_of(node: Any) -> str:
    """Visible text of a selectolax node, whitespace collapsed, NFC, diacritics intact."""
    if node is None:
        return ""
    raw = node.text(separator=" ", strip=True) if hasattr(node, "text") else str(node)
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", html.unescape(raw)).strip())


def select_text(tree: HTMLParser, *selectors: str) -> str:
    """First non-empty text among several candidate selectors."""
    for sel in selectors:
        node = tree.css_first(sel)
        t = text_of(node)
        if t:
            return t
    return ""


def select_attr(tree: HTMLParser, selector: str, attr: str) -> str:
    node = tree.css_first(selector)
    if node is None:
        return ""
    return (node.attributes.get(attr) or "").strip()


def spec_pairs(tree: HTMLParser, *selectors: str) -> list[dict[str, str]]:
    """``{label, value}`` rows from definition lists and two-column spec tables.

    This is where attraction ``openingHours`` / ``duration`` and hotel
    ``checkIn`` / ``checkOut`` realistically come from: sites put them in a
    spec table, not in JSON-LD. Spec section 5.2 wants them from Week 1 so
    nobody has to re-crawl for the Week 4 itinerary work.
    """
    out: list[dict[str, str]] = []
    for sel in selectors or ("dl", "table"):
        for container in tree.css(sel):
            dts = container.css("dt")
            dds = container.css("dd")
            if dts and len(dts) == len(dds):
                for dt, dd in zip(dts, dds):
                    label, value = text_of(dt), text_of(dd)
                    if label and value:
                        out.append({"label": label, "value": value})
                continue
            for row in container.css("tr"):
                cells = row.css("th, td")
                if len(cells) == 2:
                    label, value = text_of(cells[0]), text_of(cells[1])
                    if label and value:
                        out.append({"label": label, "value": value})
    return out


def description_blocks(tree: HTMLParser, *selectors: str) -> list[dict[str, str]]:
    """``{heading, html}`` sections, so a reviews section can be dropped by name.

    Keeping the structure (rather than one flattened string) is what lets
    ``normalise`` apply ``description_heading_denylist`` and leave a "Đánh giá
    của khách" block out of ``products.description`` without also truncating the
    real description.
    """
    out: list[dict[str, str]] = []
    for sel in selectors or ("section", "article", "div.description"):
        for node in tree.css(sel):
            heading = select_text_in(node, "h1, h2, h3, h4")
            inner = node.html or ""
            if len(inner) < 40:
                continue
            out.append({"heading": heading, "html": inner})
    return out


def select_text_in(node: Any, selector: str) -> str:
    try:
        found = node.css_first(selector)
    except Exception:  # pragma: no cover - selectolax node without css
        return ""
    return text_of(found)


def collect_images(tree: HTMLParser, base_url: str, *, limit: int = 40) -> list[str]:
    """Image URLs from ``img`` (incl. lazy attrs), ``source`` and ``link rel=image_src``.

    Picks the widest candidate from a ``srcset`` because spec section 5.1 asks
    for "bản kích thước lớn nhất". No resize-parameter stripping here — that is
    ``normalise``'s job (spec section 6.2), and doing it in a parser would mean
    a change to the rule needed a re-crawl instead of a ``normalize --force``.
    """
    seen: list[str] = []

    def add(u: str | None) -> None:
        if not u:
            return
        u = u.strip()
        if not u or u.startswith("data:"):
            return
        absolute = urljoin(base_url, u)
        if absolute not in seen and len(seen) < limit:
            seen.append(absolute)

    for node in tree.css("img, source"):
        a = node.attributes
        srcset = a.get("srcset") or a.get("data-srcset")
        if srcset:
            add(_widest_from_srcset(srcset))
        for attr in ("src", "data-src", "data-original", "data-lazy-src", "data-image"):
            add(a.get(attr))
    for node in tree.css('link[rel="image_src"]'):
        add(node.attributes.get("href"))
    return seen


def _widest_from_srcset(srcset: str) -> str | None:
    best: tuple[int, str] | None = None
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        url = bits[0]
        width = 0
        if len(bits) > 1 and bits[1].endswith("w"):
            try:
                width = int(bits[1][:-1])
            except ValueError:
                width = 0
        if best is None or width > best[0]:
            best = (width, url)
    return best[1] if best else None


def links(tree: HTMLParser, base_url: str, *, same_host_only: bool = True) -> list[str]:
    host = urlsplit(base_url).netloc.lower()
    out: list[str] = []
    for node in tree.css("a[href]"):
        href = (node.attributes.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        if same_host_only and urlsplit(absolute).netloc.lower() != host:
            continue
        if absolute not in out:
            out.append(absolute)
    return out


def phone_of(tree: HTMLParser, jsonld_nodes: list[dict[str, Any]]) -> str:
    """Telephone from JSON-LD, then a ``tel:`` link, then a contact block.

    Spec section 5.3 lists ``phone`` as a dedup field and three things downstream
    consume it, so it has to actually be extracted — a ``phone_match`` feature
    that is constant-false silently weakens every match score.
    """
    for node in jsonld_nodes:
        tel = node.get("telephone")
        if isinstance(tel, str) and tel.strip():
            return tel.strip()
    for node in tree.css('a[href^="tel:"]'):
        href = node.attributes.get("href") or ""
        if href.lower().startswith("tel:"):
            return href[4:].strip()
    return ""


# =============================================================================
# sitemaps
# =============================================================================
def sitemap_urls(body: bytes) -> tuple[list[str], list[str]]:
    """Parse a sitemap or sitemap index. Returns ``(page_urls, nested_sitemaps)``.

    lxml with entity resolution and network access disabled: a sitemap is remote
    input, and stdlib ``xml.etree`` has no XXE protections.
    """
    from lxml import etree

    parser = etree.XMLParser(
        resolve_entities=False, no_network=True, huge_tree=False, recover=True
    )
    try:
        root = etree.fromstring(body, parser=parser)
    except etree.XMLSyntaxError as exc:
        log.warning("unparseable sitemap: %s", exc)
        return [], []
    if root is None:
        return [], []

    pages: list[str] = []
    nested: list[str] = []
    for el in root.iter():
        tag = etree.QName(el).localname if el.tag is not etree.Comment else ""
        if tag != "loc" or not (el.text or "").strip():
            continue
        url = el.text.strip()
        parent = etree.QName(el.getparent()).localname if el.getparent() is not None else ""
        if parent == "sitemap":
            nested.append(url)
        else:
            pages.append(url)
    return pages, nested


def iter_sitemap_pages(
    fetcher, urls: list[str], *, max_sitemaps: int = 60, on_page=None  # noqa: ANN001
) -> Iterator[str]:
    """Walk a sitemap index breadth-first, yielding page URLs.

    ``on_page`` is called with each ``(url, FetchResult)`` so the caller can put
    the sitemap bytes through the cache: a sitemap is a fetched page like any
    other, and parsing bytes that were never written to disk would break the
    section 0 item 2 ordering invariant.
    """
    queue = list(urls)
    seen: set[str] = set()
    fetched = 0
    while queue and fetched < max_sitemaps:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            result = fetcher.get(url)
        except Exception as exc:  # noqa: BLE001 - one bad sitemap must not stop discovery
            # RobotsUnavailable and BlockedError are NOT per-sitemap problems:
            # they say we have no permission to crawl this host at all, so they
            # propagate rather than being logged and skipped.
            from collectors.base import BlockedError, RobotsUnavailable

            if isinstance(exc, (RobotsUnavailable, BlockedError)):
                raise
            log.warning("sitemap fetch failed %s: %s", url, exc)
            continue
        fetched += 1
        if result.status >= 400:
            log.info("sitemap %s returned %s", url, result.status)
            continue
        body = result.content
        if body[:2] == b"\x1f\x8b":  # a .xml.gz sitemap served without decoding
            import gzip

            body = gzip.decompress(body)
        if on_page is not None:
            on_page(url, result, body)
        pages, nested = sitemap_urls(body)
        queue.extend(nested)
        yield from pages
