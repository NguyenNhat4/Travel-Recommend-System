"""Identifier construction. Every id in this pipeline is deterministic.

Determinism is not a nicety here: `discover` runs more than once, `parse
--reparse` is routine, and the daily fix loop is
``report -> edit aliases -> normalize --force -> dedup -> load -> report``. If
any id depended on wall-clock time or insertion order, each pass through that
loop would mint new rows and orphan the seeded events that point at them.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid

# =============================================================================
# product_id
# =============================================================================
# Frozen. Changing this constant re-mints the entire catalogue: every
# product_id changes, every product_sources row is orphaned, and every seeded
# event points at a product that no longer exists.
# tests/test_ids.py pins both the constant and one known output.
NS_VOTA_PRODUCT = uuid.UUID("6f2a1c74-9b3e-5d81-a4c0-1e7b8d5f3a29")


def product_uuid(cluster_key: str) -> uuid.UUID:
    """Deterministic product_id for a dedup cluster.

    Note this is only used for clusters with no already-mapped member. load.py
    checks ``product_sources`` first and reuses an existing product_id, because
    ``cluster_key`` legitimately changes when the destination alias map is
    edited (dedup blocks by destination, so cluster membership moves) and a
    product_id must survive that.
    """
    return uuid.uuid5(NS_VOTA_PRODUCT, cluster_key)


# =============================================================================
# crawl_targets.url_hash
# =============================================================================
def url_hash(url: str) -> str:
    """Stable hash of a normalised URL, for UNIQUE (source, url_hash, quote_ctx)."""
    return hashlib.sha256(normalise_url(url).encode("utf-8")).hexdigest()


_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "gclid",
        "fbclid",
        "msclkid",
        "ref",
        "_ga",
        "sid",
    }
)


def normalise_url(url: str) -> str:
    """Canonical form of a URL for identity purposes.

    Lowercases the scheme and host (host names are case-insensitive) but leaves
    the path alone, because a path can be case-sensitive and Vietnamese slugs
    must not be altered. Drops tracking parameters and the fragment, and sorts
    the remaining query so parameter order does not create a second target for
    the same page.
    """
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    query = urlencode(
        sorted(
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in _TRACKING_PARAMS
        )
    )
    return urlunsplit((scheme, netloc, path, query, ""))


# =============================================================================
# source_ref
# =============================================================================
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(value: str, *, max_len: int = 60) -> str:
    """ASCII slug for use inside a source_ref.

    Diacritics are folded here **only** because a source_ref is an identifier,
    not display text. Every human-facing string keeps its diacritics (spec
    section 6.2); see normalise.normalise_text.
    """
    folded = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(c for c in folded if not unicodedata.combining(c))
    ascii_only = ascii_only.replace("đ", "d").replace("Đ", "D")
    slug = _SLUG_STRIP.sub("-", ascii_only.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "x"


_WS = re.compile(r"\s+")


def lookup_key(value: str) -> str:
    """Fold a string into a comparison key: NFC, casefold, diacritics removed.

    Used for destination alias matching and name comparison. This is a *lookup*
    key only — the value actually stored always keeps its diacritics and its
    original casing (spec section 6.2: "giữ nguyên dấu tiếng Việt. Không
    lowercase, không bỏ dấu"). Confusing the two is how a catalogue ends up with
    "khach san vinpearl nha trang" as a product name.
    """
    if not value:
        return ""
    folded = unicodedata.normalize("NFKD", unicodedata.normalize("NFC", value))
    stripped = "".join(c for c in folded if not unicodedata.combining(c))
    stripped = stripped.replace("đ", "d").replace("Đ", "D").replace("ð", "d")
    return _WS.sub(" ", stripped).strip().casefold()


def source_ref(source: str, *parts: str) -> str:
    """Build ``<source>:<part>[:<part>...]`` (spec section 5.1).

    Faceted refs matter for API sources that describe one product across several
    endpoints. Amadeus returns a hotel's geo from ``locations/hotels``, its price
    from ``shopping/hotel-offers`` and its rating from ``e-reputation``; giving
    all three the same ref would make them collide on
    ``UNIQUE (source, source_ref, parser_version)`` and the last one parsed
    would silently overwrite the other two. So they become
    ``amadeus:hotel:<id>``, ``amadeus:offer:<id>``, ``amadeus:sentiment:<id>``
    and normalise folds them by ``parent_source_ref``.
    """
    if not parts:
        raise ValueError("source_ref needs at least one part")
    cleaned = [str(p).strip().replace(":", "-") for p in parts if str(p).strip()]
    if not cleaned:
        raise ValueError(f"source_ref({source!r}, ...) got only empty parts")
    return f"{source}:" + ":".join(cleaned)


def split_source_ref(ref: str) -> tuple[str, str]:
    """``'vinpearl:nha-trang:deluxe'`` -> ``('vinpearl', 'nha-trang:deluxe')``."""
    source, _, rest = ref.partition(":")
    if not rest:
        raise ValueError(f"malformed source_ref: {ref!r}")
    return source, rest


# =============================================================================
# event_group_id / reference_no (spec section 10, handbook section 6)
# =============================================================================
def event_group_id(order_date: str, seq: int) -> str:
    """``OFF20260810001`` — the shape the handbook example uses.

    order_date is an ISO date string; seq is per-day and 1-based.
    """
    return f"OFF{order_date.replace('-', '')}{seq:03d}"


_B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def booking_reference(order_date: str, seq: int) -> str:
    """``VP20260810A3F9K2`` — deterministic from (date, seq) so re-seeding with
    the same ``--seed`` and ``--now`` produces identical rows."""
    digest = hashlib.sha256(f"{order_date}:{seq}".encode()).digest()
    tail = "".join(_B32[b % 32] for b in digest[:6])
    return f"VP{order_date.replace('-', '')}{tail}"
