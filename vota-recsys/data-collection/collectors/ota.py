"""Shared base for the OTA accommodation collectors (booking.com, agoda.com).

**These are expected to yield nothing, and that is the correct outcome.**

Spec section 1 is explicit: all three OTAs run anti-bot, and if we are blocked
the answer is to stop and use a fallback, not to try harder. Section 13 lists
"Đụng anti-bot rồi cố vượt" as a known trap whose cost is the whole week. So
these collectors are written to be *correct when they work* and to *fail
cleanly and loudly when they do not* — the block detector latches the source,
the runner exits 4, and the pipeline moves to Amadeus or the curated data.

They are still worth having:

* If a destination listing is served as HTML with JSON-LD or ``__NEXT_DATA__``,
  this gets real structured attributes — which is what section 7 makes
  booking.com the winner for.
* The contract is identical to every other source, so if access is ever granted
  (a partner API, a data-sharing agreement) only the fetch layer changes.
* Having them present and visibly latched is better documentation of the
  Wednesday checkpoint than a comment saying "we did not try".

What is deliberately absent: no browser automation, no UA rotation, no proxy
pool, no CAPTCHA handling, no cookie replay. ``tests/test_invariants.py``
asserts the user agent never contains "Mozilla", so a well-meaning change in
that direction fails the suite.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator

from collectors import extract
from collectors.base import BaseCollector, RawPage, Target, register  # noqa: F401
from ids import slugify, source_ref

log = logging.getLogger("collector.ota")


class OtaHotelCollector(BaseCollector):
    """Destination listing -> hotel detail, via embedded JSON where possible."""

    #: Which embedded-JSON strategies to try, in order. From config so a site
    #: change is a YAML edit (spec section 13 prefers embedded JSON to DOM).
    default_extract_preference: tuple[str, ...] = ("jsonld", "next_data", "dom")

    def __init__(self, cfg, src, *, fetcher=None) -> None:  # noqa: ANN001
        super().__init__(cfg, src, fetcher=fetcher)
        self.unmatched_urls: list[str] = []
        self.on_discovery_page = None
        self.cache = None

    # =========================================================================
    # discover
    # =========================================================================
    def quote_contexts(self) -> list[str | None]:
        """Accommodation prices depend on the search parameters, so every
        target carries a quote context (spec section 5.5)."""
        return list(self.cfg.enabled_quote_contexts()) or [None]

    def listing_url(self, destination: str, quote: dict[str, Any], page: int) -> str:
        """Build one destination listing URL. Subclasses may override."""
        template = str(self.src.get("listing_url_template", ""))
        if not template:
            raise ValueError(f"sources.{self.source}.listing_url_template is not set")
        return template.format(
            destination=destination,
            city=destination,
            city_id=destination,
            checkin=quote.get("checkin", ""),
            checkout=quote.get("checkout", ""),
            nights=quote.get("nights", 1),
            adults=quote.get("adults", 2),
            rooms=quote.get("rooms", 1),
            offset=page * 25,
            page=page + 1,
        )

    def discover(self) -> Iterator[Target]:
        max_pages = int(self.src.get("max_pages_per_destination", 1))
        contexts = self.quote_contexts()
        for ctx in contexts:
            quote = self.cfg.resolve_quote_context(ctx) if ctx else {}
            for destination in self.cfg.canonical_destination_names:
                for page in range(max_pages):
                    yield Target(
                        url=self.listing_url(destination, quote, page),
                        page_type="list",
                        quote_ctx=ctx,
                        priority=50,
                        meta={"destination": destination, "page": page},
                    )

    # =========================================================================
    # fetch
    # =========================================================================
    def fetch(self, target: Target) -> RawPage:
        return self.http_fetch(target)

    # =========================================================================
    # parse
    # =========================================================================
    def parse(self, raw: RawPage) -> list[dict]:
        body = raw.content
        destination = (raw.meta or {}).get("destination")
        preference = tuple(
            self.src.get("extract_preference") or self.default_extract_preference
        )

        rows: list[dict] = []
        for strategy in preference:
            if strategy == "jsonld":
                rows = self._from_jsonld(raw, body, destination)
            elif strategy in ("next_data", "initial_state"):
                rows = self._from_state(raw, body, destination)
            elif strategy == "dom":
                rows = self._from_dom(raw, body, destination)
            if rows:
                log.info("%s: %d row(s) from %s", self.source, len(rows), strategy)
                break

        if not rows:
            # An HTML shell with no data is the usual shape of a soft block; the
            # BlockDetector in net.py catches the obvious markers, and this
            # message covers the quieter version.
            raise ValueError(
                f"{self.source}: no products found in {raw.url} using "
                f"{preference}. Either the page is a JS-only shell (a soft block — "
                f"switch to a fallback, spec section 9) or the site shape changed and "
                f"sources.{self.source}.extract_preference needs updating."
            )
        return rows

    # -- strategies --------------------------------------------------------
    def _from_jsonld(self, raw: RawPage, body: bytes, destination: str | None) -> list[dict]:
        blocks = extract.jsonld_blocks(body)
        nodes = extract.jsonld_of_type(
            blocks, "Hotel", "Resort", "LodgingBusiness", "Apartment", "BedAndBreakfast"
        )
        rows: list[dict] = []
        for node in nodes:
            # Allowlisted before anything is read: raw JSON-LD on these sites
            # nests reviewer names and review bodies, which spec section 5.4
            # forbids collecting.
            picked = extract.jsonld_pick(node)
            name = picked.get("name")
            if not name:
                continue
            address = picked.get("address") if isinstance(picked.get("address"), dict) else {}
            geo = picked.get("geo") if isinstance(picked.get("geo"), dict) else {}
            rating = (
                picked.get("aggregateRating")
                if isinstance(picked.get("aggregateRating"), dict)
                else {}
            )
            offers = picked.get("offers")
            offer = offers[0] if isinstance(offers, list) and offers else (offers or {})
            rows.append(
                {
                    "source_ref": source_ref(self.source, slugify(str(name))),
                    "page_kind": "product",
                    "taxonomy_hint": "hotel",
                    "category_raw": str(picked.get("@type") or "Hotel"),
                    "name_raw": name,
                    "description_html": picked.get("description"),
                    "destination_raw": address.get("addressLocality") or destination,
                    "address_raw": ", ".join(
                        str(x)
                        for x in (
                            address.get("streetAddress"),
                            address.get("addressLocality"),
                            address.get("addressRegion"),
                        )
                        if x
                    )
                    or None,
                    "phone_raw": picked.get("telephone"),
                    "latitude": geo.get("latitude"),
                    "longitude": geo.get("longitude"),
                    "images": [
                        i for i in _as_list(picked.get("image")) if isinstance(i, str)
                    ],
                    "star_rating_raw": _rating_value(picked.get("starRating")),
                    "aggregate_rating_raw": rating.get("ratingValue"),
                    "review_count_raw": rating.get("reviewCount") or rating.get("ratingCount"),
                    "rating_best_raw": rating.get("bestRating"),
                    "price_raw": (offer or {}).get("price") or (offer or {}).get("lowPrice"),
                    "currency_raw": (offer or {}).get("priceCurrency"),
                    "amenity_labels": [
                        a.get("name") if isinstance(a, dict) else a
                        for a in _as_list(picked.get("amenityFeature"))
                    ],
                    "quote_ctx": raw.quote_ctx,
                    "quote_params": (raw.meta or {}).get("quote_params"),
                    "_prov": {
                        "name_raw": f"{self.source}:jsonld name",
                        "description_html": f"{self.source}:jsonld description",
                        "price_raw": f"{self.source}:jsonld offers.price",
                        "aggregate_rating_raw": f"{self.source}:jsonld aggregateRating",
                        "star_rating_raw": f"{self.source}:jsonld starRating",
                        "_strategy": "jsonld",
                    },
                }
            )
        return rows

    def _from_state(self, raw: RawPage, body: bytes, destination: str | None) -> list[dict]:
        """Read hotel records out of a framework state blob.

        The blob is read, never stored: booking's Apollo cache carries review
        nodes, and keeping it would put reviewer content into
        ``products_staging`` in violation of spec section 5.4.
        """
        blob, label = extract.state_blob(body)
        if not blob:
            return []
        candidates: list[dict] = []
        for key in ("properties", "hotels", "searchResults", "results", "items"):
            for found in extract.find_key(blob, key, limit=4):
                if isinstance(found, list):
                    candidates.extend(x for x in found if isinstance(x, dict))
        rows: list[dict] = []
        for item in candidates:
            name = item.get("name") or item.get("displayName") or item.get("hotelName")
            if not isinstance(name, str) or not name.strip():
                continue
            rows.append(
                {
                    "source_ref": source_ref(
                        self.source,
                        slugify(str(item.get("id") or item.get("hotelId") or name)),
                    ),
                    "page_kind": "product",
                    "taxonomy_hint": "hotel",
                    "category_raw": str(item.get("accommodationType") or "Hotel"),
                    "name_raw": name,
                    "description_html": item.get("description"),
                    "destination_raw": (
                        item.get("city") or item.get("cityName") or destination
                    ),
                    "address_raw": item.get("address"),
                    "latitude": _dig_num(item, "latitude", "lat"),
                    "longitude": _dig_num(item, "longitude", "lon", "lng"),
                    "price_raw": _dig_num(item, "price", "grossPrice", "displayPrice"),
                    "currency_raw": item.get("currency") or item.get("currencyCode"),
                    "star_rating_raw": _dig_num(item, "starRating", "stars", "class"),
                    # Only the aggregate and the count (spec section 5.4).
                    "aggregate_rating_raw": _dig_num(item, "reviewScore", "rating"),
                    "review_count_raw": _dig_num(item, "reviewCount", "reviewsCount"),
                    "quote_ctx": raw.quote_ctx,
                    "quote_params": (raw.meta or {}).get("quote_params"),
                    "_prov": {
                        "name_raw": f"{self.source}:{label} name",
                        "price_raw": f"{self.source}:{label} price",
                        "_strategy": label or "state",
                    },
                }
            )
        return rows

    def _from_dom(self, raw: RawPage, body: bytes, destination: str | None) -> list[dict]:
        """Last resort (spec section 13 prefers embedded JSON for a reason)."""
        tree = extract.tree_of(body)
        rows: list[dict] = []
        for sel in (
            "[data-testid=property-card]",
            "[class*=PropertyCard]",
            "[class*=property-card]",
            "li[class*=hotel]",
        ):
            cards = tree.css(sel)
            if not cards:
                continue
            for card in cards:
                name = extract.select_text_in(card, "[data-testid=title], h2, h3, [class*=name]")
                if not name:
                    continue
                rows.append(
                    {
                        "source_ref": source_ref(self.source, slugify(name)),
                        "page_kind": "product",
                        "taxonomy_hint": "hotel",
                        "category_raw": "Hotel",
                        "name_raw": name,
                        "destination_raw": destination,
                        "price_raw": extract.select_text_in(
                            card, "[data-testid*=price], [class*=price]"
                        ),
                        "quote_ctx": raw.quote_ctx,
                        "quote_params": (raw.meta or {}).get("quote_params"),
                        "_prov": {"name_raw": f"{self.source}:dom {sel}", "_strategy": "dom"},
                    }
                )
            if rows:
                break
        return rows


# =============================================================================
# helpers
# =============================================================================
def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _rating_value(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("ratingValue") or value.get("value")
    return value


def _dig_num(item: dict, *keys: str) -> Any:
    for k in keys:
        v = item.get(k)
        if isinstance(v, (int, float, str)) and str(v).strip():
            return v
        if isinstance(v, dict):
            for inner in ("value", "amount", "gross", "raw"):
                if v.get(inner) not in (None, ""):
                    return v[inner]
    return None
