"""vn.trip.com — flights first, attractions second, hotels as a bonus.

Spec section 1 and section 9 are specific about the priority here: the point of
trip.com is **flight** inventory, because cross-category recommendation in Week
3 needs a vertical that is not accommodation, plus attractions. Hotels from this
source are explicitly "chỉ là bonus".

Expected outcome is a block — and the collectors slice's prediction is that the
listing pages are a JS-only shell, which the block detector reads as a soft
block. If that happens, ``collectors/amadeus.py`` is the designed path to flight
products (``/v2/shopping/flight-offers``), and it covers the same
HAN/SGN <-> CXR/PQC/DAD/HPH route matrix from ``config.flight_routes``.

Nothing here attempts to render JavaScript. See ``collectors/ota.py`` for what
is deliberately absent and why.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator

from collectors import extract
from collectors.base import BaseCollector, RawPage, Target, register
from collectors.ota import OtaHotelCollector, _as_list, _dig_num
from ids import slugify, source_ref

log = logging.getLogger("collector.trip")


@register
class TripCollector(OtaHotelCollector):
    source = "trip"
    parser_version = "trip-1.0.0"
    rate_limit_rps = 0.5
    default_extract_preference = ("next_data", "jsonld", "dom")

    # =========================================================================
    # discover
    # =========================================================================
    def discover(self) -> Iterator[Target]:
        """Flight searches over the config route matrix, then attractions.

        Deliberately does **not** call the inherited hotel listing discovery:
        hotels here are a bonus the spec explicitly deprioritises, and spending
        the 0.5 rps budget on them ahead of flights would invert the priority
        section 1 sets.
        """
        contexts = self.quote_contexts()
        ctx = contexts[0] if contexts else None
        quote = self.cfg.resolve_quote_context(ctx) if ctx else {}
        depart = quote.get("checkin")

        routes = self.cfg.section("flight_routes")
        origins = list(routes.get("origins") or [])
        dests = list(routes.get("destinations") or [])
        pairs = [(o, d) for o in origins for d in dests if o != d]
        if routes.get("both_directions", True):
            pairs += [(d, o) for o, d in pairs]

        if not depart:
            log.warning("no quote context resolved; no flight targets planned")
        else:
            for origin, destination in pairs:
                yield Target(
                    url=(
                        f"{self.src.base_url}/flights/{origin.lower()}-to-"
                        f"{destination.lower()}/tickets-{origin.lower()}-"
                        f"{destination.lower()}?ddate={depart}"
                    ),
                    page_type="list",
                    quote_ctx=ctx,
                    priority=10,
                    meta={
                        "kind": "flight",
                        "origin": origin,
                        "destination_iata": destination,
                        "depart": depart,
                    },
                )

        for name in self.cfg.canonical_destination_names:
            yield Target(
                url=f"{self.src.base_url}/things-to-do/search?keyword={name}",
                page_type="list",
                quote_ctx=None,
                priority=30,
                meta={"kind": "attraction", "destination": name},
            )

    # =========================================================================
    # parse
    # =========================================================================
    def parse(self, raw: RawPage) -> list[dict]:
        kind = (raw.meta or {}).get("kind", "hotel")
        if kind == "flight":
            return self._parse_flights(raw)
        if kind == "attraction":
            return self._parse_attractions(raw)
        return super().parse(raw)

    def _parse_flights(self, raw: RawPage) -> list[dict]:
        blob, label = extract.state_blob(raw.content)
        if not blob:
            raise ValueError(
                f"trip: no state blob in {raw.url}. The flight results are almost "
                "certainly rendered client-side, which this pipeline does not do "
                "(spec section 1). Use `python -m cli discover --source amadeus` for "
                "flight products instead."
            )
        iata_map = self.cfg.iata_to_destination()
        origin = (raw.meta or {}).get("origin")
        arrival = (raw.meta or {}).get("destination_iata")

        items: list[dict] = []
        for key in ("flightList", "itineraryList", "routeList", "flights"):
            for found in extract.find_key(blob, key, limit=4):
                if isinstance(found, list):
                    items.extend(x for x in found if isinstance(x, dict))

        rows: list[dict] = []
        seen: set[str] = set()
        for item in items:
            carrier = item.get("airlineName") or item.get("airlineCode") or item.get("carrier")
            number = item.get("flightNo") or item.get("flightNumber")
            if not carrier or not number:
                continue
            key = f"{number}-{origin}-{arrival}"
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "source_ref": source_ref(self.source, "flight", slugify(key)),
                    "page_kind": "product",
                    "taxonomy_hint": "flight",
                    "category_raw": "Flight",
                    "name_raw": f"{carrier} {number} {origin} - {arrival}",
                    "description_html": None,
                    # Arrival city, per config.flight_routes.destination_rule and
                    # question D3: using the origin would give every seeded trip
                    # two destinations and break the section 10 invariant.
                    "destination_raw": iata_map.get(str(arrival), arrival),
                    "price_raw": _dig_num(item, "price", "lowestPrice", "adultPrice"),
                    "currency_raw": item.get("currency") or "VND",
                    "quote_ctx": raw.quote_ctx,
                    "quote_params": (raw.meta or {}).get("quote_params"),
                    "flight": {
                        "carrier": carrier,
                        "flightNo": str(number),
                        "originIata": origin,
                        "destinationIata": arrival,
                        "departTime": item.get("departureTime") or item.get("depTime"),
                        "arriveTime": item.get("arrivalTime") or item.get("arrTime"),
                        "durationMin": _dig_num(item, "duration", "durationMinutes"),
                        "stops": _dig_num(item, "stopCount", "stops") or 0,
                        "cabinClass": item.get("cabinClass") or item.get("classGrade"),
                    },
                    "_prov": {
                        "name_raw": f"trip:{label} airline + flightNo",
                        "price_raw": f"trip:{label} price",
                        "flight": f"trip:{label}",
                        "_strategy": label or "state",
                    },
                }
            )
        if not rows:
            raise ValueError(f"trip: state blob present but no flights parsed from {raw.url}")
        return rows

    def _parse_attractions(self, raw: RawPage) -> list[dict]:
        destination = (raw.meta or {}).get("destination")
        blocks = extract.jsonld_blocks(raw.content)
        nodes = [
            extract.jsonld_pick(n)
            for n in extract.jsonld_of_type(blocks, "TouristAttraction", "Product", "Event")
        ]
        rows: list[dict] = []
        for node in nodes:
            name = node.get("name")
            if not name:
                continue
            offers = node.get("offers")
            offer = offers[0] if isinstance(offers, list) and offers else (offers or {})
            rating = (
                node.get("aggregateRating")
                if isinstance(node.get("aggregateRating"), dict)
                else {}
            )
            rows.append(
                {
                    "source_ref": source_ref(self.source, "attraction", slugify(str(name))),
                    "page_kind": "product",
                    "taxonomy_hint": "attraction",
                    "category_raw": "Things to do",
                    "name_raw": name,
                    "description_html": node.get("description"),
                    "destination_raw": destination,
                    "images": [i for i in _as_list(node.get("image")) if isinstance(i, str)],
                    "price_raw": (offer or {}).get("price") or (offer or {}).get("lowPrice"),
                    "currency_raw": (offer or {}).get("priceCurrency"),
                    "opening_hours_raw": node.get("openingHoursSpecification")
                    or node.get("openingHours"),
                    "aggregate_rating_raw": rating.get("ratingValue"),
                    "review_count_raw": rating.get("reviewCount"),
                    "rating_best_raw": rating.get("bestRating"),
                    "poi_name": name,
                    "quote_ctx": None,
                    "_prov": {
                        "name_raw": "trip:jsonld name",
                        "description_html": "trip:jsonld description",
                        "opening_hours_raw": "trip:jsonld openingHoursSpecification",
                        "_strategy": "jsonld",
                    },
                }
            )
        if not rows:
            raise ValueError(
                f"trip: no attractions in {raw.url}. Likely a client-rendered page; "
                "Amadeus activities is the designed alternative."
            )
        return rows
