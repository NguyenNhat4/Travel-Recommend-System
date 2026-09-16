"""vinpearl.com — the source that decides dataset quality.

Spec section 1 puts this first for three reasons: the Vietnamese descriptions are
the best embedding input available, the products are what a stakeholder
recognises in the demo, and there is no anti-bot wall to work around.

Two design choices worth knowing before reading the code:

**Everything about the site's shape is config, not code.** Every URL pattern in
``config.yaml`` is a guess about a site none of us has crawled. So ``discover``
classifies URLs through ``sources.vinpearl.url_patterns`` and reports what it
could not classify via ``--dump-unmatched``; correcting a wrong guess is a YAML
edit, not a parser change and a re-crawl.

**One product per room type** (spec section 9). A hotel page therefore produces
N+1 staging rows: one ``page_kind='property'`` row carrying the hotel-level
description, images, geo and amenities, and one ``page_kind='room'`` row per room
type pointing at it via ``parent_source_ref``. The property row is a merge
parent, *not* a sellable product — ``normalise`` folds its fields down onto each
room and ``load`` does not emit it. Skipping that fold would put ~50 priceless
phantom hotels into ``products``, each duplicating its own rooms.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterator
from urllib.parse import urlsplit

from collectors import extract
from collectors.base import (
    BaseCollector,
    BlockedError,
    RawPage,
    RobotsUnavailable,
    Target,
    classify_url,
    register,
)
from ids import slugify, source_ref

log = logging.getLogger("collector.vinpearl")


@register
class VinpearlCollector(BaseCollector):
    source = "vinpearl"
    parser_version = "vinpearl-1.0.0"
    rate_limit_rps = 0.5

    def __init__(self, cfg, src, *, fetcher=None) -> None:  # noqa: ANN001
        super().__init__(cfg, src, fetcher=fetcher)
        self.unmatched_urls: list[str] = []
        self.on_discovery_page = None
        self.cache = None
        self.from_cache = False
        self.dump_unmatched = False

    # =========================================================================
    # discover
    # =========================================================================
    def quote_contexts(self) -> list[str | None]:
        """Hotel pages are priced per stay; tickets and golf are not.

        Returning both means a hotel target exists once per enabled context
        while a ticket target has ``quote_ctx = NULL`` — the section 4.1
        "NULL với trang không phụ thuộc ngày" case.
        """
        return [*self.cfg.enabled_quote_contexts(), None]

    def discover(self) -> Iterator[Target]:
        seen: set[str] = set()
        emitted = 0

        for url in self._candidate_urls():
            if url in seen:
                continue
            seen.add(url)
            hit = classify_url(self.src, url)
            if hit is None:
                # Not an error: sitemaps contain blog posts, policies and
                # images. Only surfaced via --dump-unmatched so a genuinely
                # wrong pattern list is visible rather than silently empty.
                if len(self.unmatched_urls) < 2000:
                    self.unmatched_urls.append(url)
                continue
            page_type, taxonomy = hit
            if page_type == "list":
                continue

            for target in self._targets_for(url, page_type, taxonomy):
                emitted += 1
                yield target

        if emitted == 0:
            log.error(
                "no vinpearl targets classified. Run "
                "`python -m cli discover --source vinpearl --dry-run --dump-unmatched` "
                "and correct sources.vinpearl.url_patterns in config.yaml."
            )

    def _targets_for(self, url: str, page_type: str, taxonomy: str | None) -> Iterator[Target]:
        """One target per applicable quote context.

        Only accommodation is quoted: a VinWonders ticket price does not depend
        on a check-in date, so giving it a quote context would multiply the
        crawl for no information.
        """
        priority = {"hotel": 10, "combo": 20, "attraction": 30, "golf": 40}.get(taxonomy or "", 50)
        if taxonomy == "hotel":
            for ctx in self.cfg.enabled_quote_contexts():
                yield Target(
                    url=url,
                    page_type=page_type,
                    quote_ctx=ctx,
                    priority=priority,
                    meta={"taxonomy_hint": taxonomy},
                )
        else:
            yield Target(
                url=url,
                page_type=page_type,
                quote_ctx=None,
                priority=priority,
                meta={"taxonomy_hint": taxonomy},
            )

    def _candidate_urls(self) -> Iterator[str]:
        sitemaps = list(self.src.get("sitemaps", []) or [])
        if sitemaps:
            got_any = False
            for url in extract.iter_sitemap_pages(
                self.fetcher, sitemaps, on_page=self._on_discovery
            ):
                got_any = True
                yield url
            if got_any:
                return
            log.warning("no sitemap yielded URLs; falling back to a bounded link harvest")

        harvest = self.src.get("link_harvest", {}) or {}
        if not harvest.get("enabled", False):
            log.error("sitemaps produced nothing and link_harvest is disabled")
            return
        yield from self._harvest_links(
            list(harvest.get("seeds", []) or []),
            max_depth=int(harvest.get("max_depth", 2)),
            max_pages=int(harvest.get("max_pages", 300)),
        )

    def _harvest_links(self, seeds: list[str], *, max_depth: int, max_pages: int) -> Iterator[str]:
        """Bounded breadth-first crawl of listing pages, when no sitemap exists.

        Bounded on purpose: an unbounded fallback at 0.5 rps is how a Tuesday
        disappears. Every page fetched here goes through the cache and gets a
        ``raw_pages`` row like any other, so the bytes are re-parseable.
        """
        frontier = [(s, 0) for s in seeds]
        visited: set[str] = set()
        fetched = 0
        while frontier and fetched < max_pages:
            url, depth = frontier.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                result = self.fetcher.get(url)
            except (RobotsUnavailable, BlockedError):
                # No permission to crawl this host at all — propagate so the
                # runner reports the real cause instead of "no URLs matched".
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("harvest fetch failed %s: %s", url, exc)
                continue
            fetched += 1
            if result.status >= 400:
                continue
            self._on_discovery(url, result, result.content)
            tree = extract.tree_of(result.content)
            for link in extract.links(tree, url):
                if classify_url(self.src, link):
                    yield link
                elif depth + 1 <= max_depth and link not in visited:
                    frontier.append((link, depth + 1))

    def _on_discovery(self, url: str, result, body: bytes) -> None:  # noqa: ANN001
        if self.on_discovery_page is not None:
            self.on_discovery_page(url, result, body)

    # =========================================================================
    # fetch
    # =========================================================================
    def fetch(self, target: Target) -> RawPage:
        return self.http_fetch(target)

    # =========================================================================
    # parse
    # =========================================================================
    def parse(self, raw: RawPage) -> list[dict]:
        hit = classify_url(self.src, raw.url)
        taxonomy = (hit[1] if hit else None) or raw.meta.get("taxonomy_hint")
        if not taxonomy:
            raise ValueError(
                f"no taxonomy for {raw.url}: url_patterns did not classify it. "
                "Fix sources.vinpearl.url_patterns rather than guessing here."
            )

        body = raw.content
        blocks = extract.jsonld_blocks(body)
        # Allowlisted before anything is read, let alone stored: raw JSON-LD
        # nests reviewer names and review bodies (spec section 5.4).
        nodes = [
            extract.jsonld_pick(n)
            for n in extract.jsonld_of_type(
                blocks, "Hotel", "Resort", "LodgingBusiness", "Product",
                "TouristAttraction", "GolfCourse", "Offer", "Place",
            )
        ]
        meta = extract.og_meta(body)
        tree = extract.tree_of(body)
        state, state_label = extract.state_blob(body)

        base = self._common_fields(raw, tree, nodes, meta, state, state_label)

        if taxonomy == "hotel":
            return self._parse_hotel(raw, tree, nodes, base)
        if taxonomy == "attraction":
            return self._parse_attraction(raw, tree, nodes, base)
        if taxonomy == "golf":
            return self._parse_golf(raw, tree, base)
        if taxonomy == "combo":
            return self._parse_combo(raw, tree, base)
        raise ValueError(f"unhandled taxonomy {taxonomy!r} for {raw.url}")

    # -- shared field extraction -------------------------------------------
    def _common_fields(
        self,
        raw: RawPage,
        tree,  # noqa: ANN001
        nodes: list[dict[str, Any]],
        meta: dict[str, str],
        state: dict[str, Any] | None,
        state_label: str | None,
    ) -> dict[str, Any]:
        """Fields every taxonomy shares, plus the ``_prov`` provenance map.

        ``_prov`` records *how* each field was obtained. It is what makes README
        section 12 item 1 ("mỗi field lấy từ đâu") a generated table instead of
        a hand-maintained claim that drifts the first time a parser changes.
        """
        prov: dict[str, str] = {}

        def take(field: str, *candidates: tuple[Any, str]) -> Any:
            for value, how in candidates:
                if value not in (None, "", [], {}):
                    prov[field] = how
                    return value
            return None

        primary = nodes[0] if nodes else {}
        address = primary.get("address") if isinstance(primary.get("address"), dict) else {}
        geo = primary.get("geo") if isinstance(primary.get("geo"), dict) else {}
        rating = (
            primary.get("aggregateRating")
            if isinstance(primary.get("aggregateRating"), dict)
            else {}
        )

        name = take(
            "name_raw",
            (primary.get("name"), "jsonld:name"),
            (meta.get("title"), "og:title"),
            (extract.select_text(tree, "h1"), "dom:h1"),
        )
        desc_blocks = extract.description_blocks(
            tree, "div.description", "section.description", "div[class*=intro]", "article"
        )
        description = take(
            "description_html",
            (primary.get("description"), "jsonld:description"),
            (
                extract.select_attr(tree, "div.description", "outerHTML")
                or (desc_blocks[0]["html"] if desc_blocks else None),
                "dom:description-block",
            ),
            (meta.get("description"), "og:description"),
        )
        images = take(
            "images",
            (_as_list(primary.get("image")), "jsonld:image"),
            ([meta["image"]] if meta.get("image") else None, "og:image"),
            (extract.collect_images(tree, raw.url), "dom:img/srcset"),
        )
        phone = take("phone_raw", (extract.phone_of(tree, nodes), "jsonld:telephone|tel:href"))
        address_raw = take(
            "address_raw",
            (_join_address(address), "jsonld:address"),
            (extract.select_text(tree, "address", "[class*=address]"), "dom:address"),
        )
        destination_raw = take(
            "destination_raw",
            (address.get("addressLocality"), "jsonld:address.addressLocality"),
            (address.get("addressRegion"), "jsonld:address.addressRegion"),
            (_breadcrumb_tail(tree), "dom:breadcrumb"),
            (address_raw, "derived:address_raw"),
        )
        lat = take("latitude", (_as_float(geo.get("latitude")), "jsonld:geo.latitude"))
        lon = take("longitude", (_as_float(geo.get("longitude")), "jsonld:geo.longitude"))
        star = take(
            "star_rating_raw",
            (_star_of(primary.get("starRating")), "jsonld:starRating"),
            (extract.select_text(tree, "[class*=star]"), "dom:star"),
        )
        agg = take("aggregate_rating_raw", (rating.get("ratingValue"), "jsonld:aggregateRating"))
        # Spec section 5.4 allows the review COUNT but no review content.
        rcount = take(
            "review_count_raw",
            (rating.get("reviewCount"), "jsonld:aggregateRating.reviewCount"),
            (rating.get("ratingCount"), "jsonld:aggregateRating.ratingCount"),
        )
        best = take("rating_best_raw", (rating.get("bestRating"), "jsonld:aggregateRating.bestRating"))
        pairs = take("spec_pairs", (extract.spec_pairs(tree), "dom:spec-table/dl"))
        amenities = take(
            "amenity_labels",
            (_amenity_labels(primary), "jsonld:amenityFeature"),
            (
                [extract.text_of(n) for n in tree.css("[class*=amenit] li, [class*=tien-ich] li")]
                or None,
                "dom:amenity-list",
            ),
        )
        brand = take("brand_raw", (_brand_of(primary), "jsonld:brand"))

        if state_label:
            prov["_state_blob"] = state_label

        return {
            "name_raw": name,
            "description_html": description,
            "description_blocks": _drop_review_blocks(desc_blocks, self.cfg),
            "images": images or [],
            "phone_raw": phone,
            "address_raw": address_raw,
            "destination_raw": destination_raw,
            "latitude": lat,
            "longitude": lon,
            "star_rating_raw": star,
            "aggregate_rating_raw": agg,
            "review_count_raw": rcount,
            "rating_best_raw": best,
            "spec_pairs": pairs or [],
            "amenity_labels": amenities or [],
            "brand_raw": brand,
            "quote_ctx": raw.quote_ctx,
            "quote_params": raw.meta.get("quote_params"),
            "_prov": prov,
        }

    # -- hotel: N+1 rows ---------------------------------------------------
    def _parse_hotel(
        self, raw: RawPage, tree, nodes: list[dict[str, Any]], base: dict[str, Any]  # noqa: ANN001
    ) -> list[dict]:
        hotel_slug = _slug_of(raw.url)
        property_ref = source_ref(self.source, hotel_slug)

        rows: list[dict] = [
            {
                **base,
                "source_ref": property_ref,
                "page_kind": "property",
                "taxonomy_hint": "hotel",
                "category_raw": "Khách sạn & Resort",
                "price_raw": _price_text(tree),
            }
        ]

        rooms = self._room_types(tree, nodes)
        if not rooms:
            # No room breakdown on the page. The property row stays and load
            # emits it as a single product (a property row is only suppressed
            # when it actually has children), so a hotel is never lost just
            # because its room list is rendered client-side.
            log.info("no room types found on %s; keeping the property row alone", raw.url)
            rows[0]["page_kind"] = "product"
            rows[0]["_prov"] = {**base["_prov"], "page_kind": "derived:no-room-types"}
            return rows

        for room in rooms:
            room_slug = slugify(room["name"])
            rows.append(
                {
                    # Room-level fields only. normalise folds the property row's
                    # description/images/geo down onto each room via
                    # parent_source_ref, so they are not duplicated here.
                    "source_ref": source_ref(self.source, hotel_slug, room_slug),
                    "parent_source_ref": property_ref,
                    "page_kind": "room",
                    "taxonomy_hint": "hotel",
                    "category_raw": "Khách sạn & Resort",
                    "name_raw": f"{base['name_raw']} - {room['name']}",
                    "description_html": room.get("description"),
                    "price_raw": room.get("price_raw"),
                    "images": room.get("images") or [],
                    "spec_pairs": room.get("spec_pairs") or [],
                    "amenity_labels": room.get("amenities") or [],
                    "quote_ctx": raw.quote_ctx,
                    "quote_params": raw.meta.get("quote_params"),
                    "_prov": {
                        "name_raw": "derived:hotel name + room name",
                        "price_raw": room.get("_prov_price", "dom:room-card"),
                        "room_source": room.get("_prov", "dom:room-card"),
                    },
                }
            )
        return rows

    def _room_types(self, tree, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:  # noqa: ANN001
        """Room types from JSON-LD offers first, then room cards in the DOM."""
        rooms: list[dict[str, Any]] = []

        for node in nodes:
            for offer in _as_list(node.get("offers")):
                if not isinstance(offer, dict):
                    continue
                offered = offer.get("itemOffered")
                name = None
                if isinstance(offered, dict):
                    name = offered.get("name")
                name = name or offer.get("name")
                if not name:
                    continue
                rooms.append(
                    {
                        "name": extract.text_of(name) if not isinstance(name, str) else name,
                        "price_raw": str(offer.get("price") or ""),
                        "_prov": "jsonld:offers.itemOffered",
                        "_prov_price": "jsonld:offers.price",
                    }
                )
        if rooms:
            return _dedupe_rooms(rooms)

        selectors = (
            "[class*=room-card]",
            "[class*=roomCard]",
            "[class*=room-item]",
            "[class*=loai-phong]",
            "li[class*=room]",
        )
        for sel in selectors:
            cards = tree.css(sel)
            if not cards:
                continue
            for card in cards:
                name = extract.select_text_in(card, "h2, h3, h4, [class*=name], [class*=title]")
                if not name:
                    continue
                rooms.append(
                    {
                        "name": name,
                        "price_raw": extract.select_text_in(card, "[class*=price], [class*=gia]"),
                        "description": (card.html or "") if len(card.html or "") > 60 else None,
                        "images": extract.collect_images(card, "", limit=6)
                        if hasattr(card, "css")
                        else [],
                        "amenities": [
                            extract.text_of(n) for n in card.css("li")
                        ],
                        "_prov": f"dom:{sel}",
                        "_prov_price": f"dom:{sel} [class*=price]",
                    }
                )
            if rooms:
                break
        return _dedupe_rooms(rooms)

    # -- attraction --------------------------------------------------------
    def _parse_attraction(
        self, raw: RawPage, tree, nodes: list[dict[str, Any]], base: dict[str, Any]  # noqa: ANN001
    ) -> list[dict]:
        """One row per ticket type (spec section 5.2 ``ticketType``).

        ``openingHours`` and ``duration`` are collected here from JSON-LD and
        the spec table. Spec section 5.2 is explicit that Week 4's itinerary
        work needs them and that they should not be backfilled later — a second
        crawl for two fields is the kind of avoidable week this plan is built to
        prevent.
        """
        poi = base["name_raw"]
        slug = _slug_of(raw.url)
        opening = _opening_hours(nodes, base["spec_pairs"], self.cfg)
        tickets = _ticket_rows(tree)

        common = {
            **base,
            "taxonomy_hint": "attraction",
            "category_raw": "Vé tham quan",
            "poi_name": poi,
            "opening_hours_raw": opening,
            "ticket_rows": tickets,
        }
        if not tickets:
            return [
                {
                    **common,
                    "source_ref": source_ref(self.source, slug),
                    "page_kind": "product",
                    "price_raw": _price_text(tree),
                }
            ]

        rows: list[dict] = []
        for row in tickets:
            rows.append(
                {
                    **common,
                    "source_ref": source_ref(self.source, slug, slugify(row["label"])),
                    "page_kind": "product",
                    "name_raw": f"{poi} - {row['label']}",
                    "price_raw": row.get("price_raw"),
                    "ticket_label_raw": row["label"],
                    "_prov": {**base["_prov"], "ticket_rows": "dom:ticket-table"},
                }
            )
        return rows

    # -- golf --------------------------------------------------------------
    def _parse_golf(self, raw: RawPage, tree, base: dict[str, Any]) -> list[dict]:  # noqa: ANN001
        pairs = {p["label"].lower(): p["value"] for p in base["spec_pairs"]}
        return [
            {
                **base,
                "source_ref": source_ref(self.source, _slug_of(raw.url)),
                "page_kind": "product",
                "taxonomy_hint": "golf",
                "category_raw": "Golf",
                "price_raw": _price_text(tree),
                "golf": {
                    "courseName": base["name_raw"],
                    "holes_raw": _first_match(pairs, "hố", "hole"),
                    "par_raw": _first_match(pairs, "par"),
                    "tee_raw": _first_match(pairs, "tee", "giờ"),
                },
            }
        ]

    # -- combo -------------------------------------------------------------
    def _parse_combo(self, raw: RawPage, tree, base: dict[str, Any]) -> list[dict]:  # noqa: ANN001
        text_all = extract.text_of(tree.css_first("body"))
        nights = None
        pattern = self.cfg.section("derive").get("combo_nights_regex")
        if pattern:
            m = re.search(pattern, text_all or "", re.IGNORECASE)
            if m:
                nights = int(m.group(1))
        return [
            {
                **base,
                "source_ref": source_ref(self.source, _slug_of(raw.url)),
                "page_kind": "product",
                "taxonomy_hint": "combo",
                "category_raw": "Combo & Ưu đãi",
                "price_raw": _price_text(tree),
                "combo": {
                    "nights_raw": nights,
                    "component_labels": [
                        extract.text_of(n)
                        for n in tree.css("[class*=include] li, [class*=bao-gom] li")
                    ],
                },
            }
        ]


# =============================================================================
# helpers
# =============================================================================
def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _slug_of(url: str) -> str:
    path = urlsplit(url).path.rstrip("/")
    return slugify(path.rsplit("/", 1)[-1] or "index")


def _join_address(address: dict[str, Any]) -> str:
    parts = [
        address.get("streetAddress"),
        address.get("addressLocality"),
        address.get("addressRegion"),
        address.get("postalCode"),
    ]
    return ", ".join(str(p).strip() for p in parts if p)


def _breadcrumb_tail(tree) -> str:  # noqa: ANN001
    for sel in ("nav[aria-label*=readcrumb] li", "[class*=breadcrumb] li", "ol[class*=crumb] li"):
        items = [extract.text_of(n) for n in tree.css(sel)]
        items = [i for i in items if i]
        if len(items) >= 2:
            return items[-1] if items[-1] else items[-2]
    return ""


def _star_of(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("ratingValue") or value.get("value")
    return value


def _amenity_labels(node: dict[str, Any]) -> list[str] | None:
    out: list[str] = []
    for a in _as_list(node.get("amenityFeature")):
        if isinstance(a, dict) and a.get("name"):
            out.append(str(a["name"]))
        elif isinstance(a, str):
            out.append(a)
    return out or None


def _brand_of(node: dict[str, Any]) -> str | None:
    brand = node.get("brand")
    if isinstance(brand, dict):
        return brand.get("name")
    if isinstance(brand, str):
        return brand
    return None


def _price_text(tree) -> str:  # noqa: ANN001
    """The price string exactly as shown; normalise parses it (spec section 6.2)."""
    return extract.select_text(
        tree,
        "[class*=price] [class*=value]",
        "[class*=price]",
        "[class*=gia-phong]",
        "[class*=gia]",
        "[itemprop=price]",
    )


def _ticket_rows(tree) -> list[dict[str, str]]:  # noqa: ANN001
    rows: list[dict[str, str]] = []
    for sel in ("[class*=ticket] tr", "[class*=ve] tr", "table tr"):
        for tr in tree.css(sel):
            cells = [extract.text_of(c) for c in tr.css("td, th")]
            cells = [c for c in cells if c]
            if len(cells) >= 2 and re.search(r"\d", cells[-1]):
                rows.append({"label": cells[0], "price_raw": cells[-1]})
        if rows:
            break
    return rows


def _opening_hours(
    nodes: list[dict[str, Any]], pairs: list[dict[str, str]], cfg
) -> Any:  # noqa: ANN001
    for node in nodes:
        spec = node.get("openingHoursSpecification")
        if spec:
            return spec
        if node.get("openingHours"):
            return node["openingHours"]
    labels = (cfg.section("derive").get("attraction_labels") or {}).get("opening_hours", [])
    for pair in pairs:
        low = pair["label"].lower()
        if any(str(lbl).lower() in low for lbl in labels):
            return pair["value"]
    return None


def _first_match(pairs: dict[str, str], *needles: str) -> str | None:
    for label, value in pairs.items():
        if any(n in label for n in needles):
            return value
    return None


def _dedupe_rooms(rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in rooms:
        key = slugify(r["name"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _drop_review_blocks(blocks: list[dict[str, str]], cfg) -> list[dict[str, str]]:  # noqa: ANN001
    """Remove sections whose heading is on the review denylist.

    Spec section 5.4 forbids review content. Dropping by heading keeps the real
    description intact instead of truncating it, which section 5.1 also forbids.
    """
    deny = [
        str(h).lower()
        for h in (cfg.section("normalise").get("text") or {}).get(
            "description_heading_denylist", []
        )
    ]
    if not deny:
        return blocks
    kept = []
    for b in blocks:
        heading = (b.get("heading") or "").lower()
        if heading and any(d in heading for d in deny):
            continue
        kept.append(b)
    return kept
