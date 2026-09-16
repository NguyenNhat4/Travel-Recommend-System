"""The collector contract (spec section 8) and the staging payload contract.

``BaseCollector.fetch`` is kept **synchronous**, exactly as the spec writes it.
The runner gets its ``--concurrency 2`` from a small thread pool rather than by
making the whole contract async: at 0.5 rps per domain the binding constraint is
the rate limiter, not the I/O model, so asyncio would buy nothing and would
change the signature the spec specifies.
"""

from __future__ import annotations

import importlib
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator

log = logging.getLogger("collector")

PAGE_TYPES = ("list", "detail", "price", "room", "api")
PAGE_KINDS = ("product", "property", "room")

PARSER_VERSION_RE = re.compile(r"^[a-z0-9_]+-(\d+)\.(\d+)\.(\d+)$")


def parse_parser_version(value: str) -> tuple[int, int, int]:
    """``'vinpearl-1.2.3'`` -> ``(1, 2, 3)``.

    ``normalize`` has to order staging rows by ``parser_version`` to pick the
    current payload for a ``(source, source_ref)``. A date-shaped version like
    ``vinpearl-2026.09.1`` mixed into the same comparison mis-sorts (2026 > 1),
    so the shape is enforced here at import time rather than discovered when a
    normalise run silently picks last week's payload.
    """
    m = PARSER_VERSION_RE.match(value)
    if not m:
        raise ValueError(
            f"parser_version must be '<source>-<major>.<minor>.<patch>', got {value!r}"
        )
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


# =============================================================================
# contract types (spec section 8)
# =============================================================================
@dataclass
class Target:
    url: str
    page_type: str  # list|detail|price|room|api
    quote_ctx: str | None = None
    priority: int = 100
    #: Carried into ``crawl_targets`` only as far as the schema allows; the rest
    #: rides along in-process (API sources need a method/body, and re-deriving
    #: them at fetch time from the URL alone is not possible).
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.page_type not in PAGE_TYPES:
            raise ValueError(f"page_type must be one of {PAGE_TYPES}, got {self.page_type!r}")


@dataclass
class RawPage:
    url: str
    http_status: int
    content: bytes
    content_type: str
    quote_ctx: str | None
    #: Set by the runner after the bytes are on disk, so ``parse`` can attribute
    #: a staging row to the page it came from without re-reading the DB.
    raw_page_id: int | None = None
    target_id: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class BlockedError(RuntimeError):
    """The source is challenging us. Stop; do not work around it.

    Spec sections 1 and 13 are unambiguous: a block means switch to the
    fallback, not try harder. Raising this aborts the source, latches
    ``source_state``, and exits with ``exitcodes.BLOCKED``.
    """

    def __init__(self, source: str, detail: dict[str, Any]) -> None:
        super().__init__(f"{source} is blocking us: {detail}")
        self.source = source
        self.detail = detail


class RobotsDenied(RuntimeError):
    """robots.txt explicitly disallows this URL for our user agent.

    A normal, per-target outcome: the target is marked ``skipped`` and the run
    continues, because other paths on the same host may well be allowed.
    """

    def __init__(self, url: str) -> None:
        super().__init__(f"robots.txt disallows {url} for our user agent")
        self.url = url


class RobotsUnavailable(RuntimeError):
    """robots.txt could not be read at all, so permission cannot be established.

    Kept separate from :class:`RobotsDenied` because the operator response is
    different, and conflating them is expensive. "This path is disallowed" means
    skip it and carry on. "I could not read robots.txt" — a 403 from a WAF, say —
    means we have no basis to crawl anything on that host, and the honest move is
    to stop and use a fallback source (spec sections 1, 9). Reporting that as
    "no URLs matched" would send someone off editing regexes for a site that
    never let them in.
    """

    def __init__(self, host: str, status: int | None) -> None:
        super().__init__(
            f"robots.txt at {host} is not readable (status={status}); "
            "cannot establish permission to crawl"
        )
        self.host = host
        self.status = status


# =============================================================================
# the ABC
# =============================================================================
class BaseCollector(ABC):
    source: str
    parser_version: str
    rate_limit_rps: float
    respect_robots: bool = True

    #: Hosts this collector actually sends requests to. Must agree with
    #: ``base_url``; ``config.validate`` checks that, because a limiter keyed to
    #: a host we never call leaves the real host effectively unlimited.
    hosts: tuple[str, ...] = ()

    def __init__(self, cfg, src, *, fetcher=None) -> None:  # noqa: ANN001
        self.cfg = cfg
        self.src = src
        self.source = src.name
        self.parser_version = src.parser_version
        self.rate_limit_rps = src.rate_limit_rps
        self.respect_robots = src.respect_robots
        if src.hosts:
            self.hosts = src.hosts
        parse_parser_version(self.parser_version)
        #: Injected by the runner. ``parse`` receives a fetcher that raises on
        #: any network call, which is how "parse never fetches" is enforced
        #: rather than merely intended.
        self._fetcher = fetcher

    # -- contract ----------------------------------------------------------
    @abstractmethod
    def discover(self) -> Iterator[Target]:
        """Yield targets to fetch. May read the network (sitemaps, API indexes)."""

    @abstractmethod
    def fetch(self, target: Target) -> RawPage:
        """Retrieve one target. MUST NOT parse."""

    @abstractmethod
    def parse(self, raw: RawPage) -> list[dict]:
        """Return raw payloads. Do NOT normalise here (spec section 8).

        One returned dict becomes one ``products_staging`` row. Required keys
        are documented in :data:`PAYLOAD_CONTRACT`.
        """

    # -- shared helpers ----------------------------------------------------
    @property
    def fetcher(self):
        if self._fetcher is None:
            raise RuntimeError(
                f"{self.source}: no fetcher injected. Collectors are constructed by "
                "collectors.runner, which supplies one."
            )
        return self._fetcher

    def http_fetch(
        self,
        target: Target,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        json_body: Any = None,
    ) -> RawPage:
        """The ordinary implementation of :meth:`fetch` for HTTP sources.

        Collectors call this rather than reimplementing the RawPage plumbing, so
        every source records the same provenance (attempts, wait time, resolved
        quote parameters) into ``raw_pages.meta``. The resolved quote parameters
        are what make README section 12 item 4 recoverable without encoding
        dates into ``quote_ctx`` — which would break its uniqueness constraint.
        """
        result = self.fetcher.get(target.url, method=method, headers=headers, json_body=json_body)
        quote_params = None
        if target.quote_ctx:
            quote_params = self.cfg.resolve_quote_context(target.quote_ctx)
        return RawPage(
            url=result.url,
            http_status=result.status,
            content=result.content,
            content_type=result.content_type,
            quote_ctx=target.quote_ctx,
            target_id=None,
            meta={
                "attempts": result.attempts,
                "elapsed_ms": result.elapsed_ms,
                "waited_ms": result.waited_ms,
                "quote_params": quote_params,
                "page_type": target.page_type,
                "redirected_from": result.redirected_from,
                **target.meta,
            },
        )

    def quote_contexts(self) -> list[str | None]:
        """Which quote contexts this source needs.

        A source whose prices do not depend on search parameters returns
        ``[None]``, and its targets get ``quote_ctx = NULL`` — matching the
        section 4.1 comment "NULL với trang không phụ thuộc ngày".
        """
        return [None]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} {self.source} {self.parser_version}>"


# =============================================================================
# staging payload contract
# =============================================================================
#: What a ``parse`` result may contain. Field names stay as the SOURCE names
#: (spec section 4.1: "field thô, tên field giữ như nguồn"); normalise.py is the
#: only place that renames or converts anything.
#:
#: Keys marked (req) are required by the parse runner's validator.
PAYLOAD_CONTRACT: dict[str, str] = {
    "source_ref": "(req) '<source>:<id>' — unique per product within the source",
    "page_kind": "(req) product|property|room — 'property' rows are merge parents, not products",
    "parent_source_ref": "for page_kind='room': the property row it belongs to",
    "taxonomy_hint": "(req) from url_patterns/API kind, NOT guessed by the parser",
    "category_raw": "the source's own category string, for taxonomy_map.by_category",
    "name_raw": "(req) product name, untouched except HTML unescape + NFC",
    "description_html": "full description, still HTML; never truncated",
    "description_blocks": "list of {heading, html} so a reviews section can be dropped",
    "price_raw": "the price string exactly as shown ('3.400.000đ')",
    "price_value": "numeric price when the source gives one as a number",
    "currency_raw": "currency as the source states it",
    "destination_raw": "breadcrumb / address locality text — normalise maps it",
    "address_raw": "full address string",
    "phone_raw": "telephone as published (spec section 5.3 dedup field)",
    "latitude": "float",
    "longitude": "float",
    "images": "list of URLs, largest variant available",
    "star_rating_raw": "hotel class as published",
    "aggregate_rating_raw": "rating value as published — rescaled by normalise",
    "review_count_raw": "number of reviews (spec section 5.4 allows the COUNT only)",
    "rating_best_raw": "JSON-LD bestRating when present, so the scale is known",
    "amenity_labels": "list of amenity strings, source wording",
    "spec_pairs": "list of {label, value} from spec tables — where openingHours etc. come from",
    "ticket_rows": "list of {label, price_raw} for attraction ticket types",
    "brand_raw": "chain/brand string",
    "quote_ctx": "the bare context name ('base') or null",
    "quote_params": "resolved {checkin, checkout, nights, adults, rooms} for provenance",
    "flight": "dict of carrier/flightNo/origin/destination/times for taxonomy=flight",
    "combo": "dict of components/nights/validity for taxonomy=combo",
    "golf": "dict of holes/par/tee times for taxonomy=golf",
    "_prov": "(req) {field: 'how it was extracted'} — generates README section 12 item 1",
}

REQUIRED_PAYLOAD_KEYS = ("source_ref", "page_kind", "taxonomy_hint", "name_raw", "_prov")

#: Keys that must never appear anywhere in a payload, at any depth.
#: Spec section 5.4: no review text, no reviewer names, no personal traveller
#: data. Only ``aggregateRating`` and ``reviewCount`` are allowed, which is why
#: ``review_count_raw`` above is explicitly a count.
FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "review",
        "reviews",
        "reviewbody",
        "reviewtext",
        "author",
        "comment",
        "comments",
        "customerreviews",
        "guestreviews",
        "reviewer",
        "reviewername",
        "username",
        "useremail",
        "email",
        "phone_number_personal",
    }
)


def assert_no_personal_data(obj: Any, path: str = "payload") -> None:
    """Recursively reject forbidden keys (spec section 5.4).

    This is a real assertion, not a scan of stored data, because the extraction
    side never keeps a verbatim JSON-LD blob: ``extract.jsonld_pick`` applies an
    allowlist first. Real hotel JSON-LD routinely nests
    ``review: [{author: {...}, reviewBody: "..."}]`` inside the ``Hotel``
    object, so keeping the raw block would both violate section 5.4 and make
    this check reject every hotel page — turning the best source into zero
    products.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower().replace("_", "") in FORBIDDEN_PAYLOAD_KEYS:
                raise ValueError(
                    f"{path}.{k}: personal/review data is not collected "
                    f"(spec section 5.4). Extract only aggregateRating + reviewCount."
                )
            assert_no_personal_data(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            assert_no_personal_data(v, f"{path}[{i}]")


# =============================================================================
# registry
# =============================================================================
def classify_url(src, url: str) -> tuple[str, str | None] | None:  # noqa: ANN001
    """Map a URL to ``(page_type, taxonomy)`` using ``sources.<s>.url_patterns``.

    Returns ``None`` when nothing matched, so ``discover --dump-unmatched`` can
    show what the config missed.

    This lives in config rather than in a parser for the reason spec section 6.2
    gives for the taxonomy map: every pattern here is a *guess* about a site we
    have not seen, and a wrong guess should cost a YAML edit, not a code change
    and a re-crawl. ``url_exclude`` is checked first so blog and policy pages
    never become targets.
    """
    for pattern in src.get("url_exclude", []) or []:
        if re.search(pattern, url, re.IGNORECASE):
            return None
    for rule in src.get("url_patterns", []) or []:
        if re.search(rule["pattern"], url, re.IGNORECASE):
            return rule.get("page_type", "detail"), rule.get("taxonomy")
    return None


registry: dict[str, type[BaseCollector]] = {}

#: source name -> module that defines its collector.
_MODULES = {
    "vinpearl": "collectors.vinpearl",
    "booking": "collectors.booking",
    "agoda": "collectors.agoda",
    "trip": "collectors.trip",
    "amadeus": "collectors.amadeus",
    "manual": "collectors.manual",
    "osm": "collectors.osm",
}


def register(cls: type[BaseCollector]) -> type[BaseCollector]:
    registry[cls.source] = cls
    return cls


def get_collector(cfg, source: str, *, fetcher=None) -> BaseCollector:  # noqa: ANN001
    """Instantiate the collector for ``source``, importing its module on demand."""
    if source not in registry:
        module = _MODULES.get(source)
        if module is None:
            raise KeyError(
                f"no collector for source {source!r}. Known: {', '.join(sorted(_MODULES))}"
            )
        importlib.import_module(module)
    if source not in registry:
        raise KeyError(f"{_MODULES[source]} did not register a collector named {source!r}")
    return registry[source](cfg, cfg.source(source), fetcher=fetcher)
