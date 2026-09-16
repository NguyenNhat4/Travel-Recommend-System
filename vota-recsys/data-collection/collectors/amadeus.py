"""Amadeus Self-Service API — the volume source (spec section 9 fallback).

The spec treats Amadeus as a fallback for when crawling fails. On this project
it is better understood as the *volume* source and vinpearl as the *quality*
source, because the arithmetic does not work otherwise: vinpearl has roughly
45-50 Vietnamese properties, which is a few hundred products at room-type grain,
and the three OTAs are expected to yield zero. The 2,000-5,000 product floor in
section 0 item 1 is only reachable with Amadeus hotels, activities and flights.

That is why ``amadeus-probe`` exists and why the README says to run it first: a
~20-request probe reports how many rows the free test tier actually has per
Vietnamese destination, and *that number*, not vinpearl, decides the week.

Two things to know about the data:

**Descriptions are English.** ``description_policy: en_to_attributes`` in config
routes them to ``attributes.descriptionEn`` and leaves
``products.description`` NULL. Letting English prose into the description column
would make the "missing description" metric look healthy while contaminating the
Vietnamese corpus that Week 2's model comparison depends on — and the whole
point of preferring vinpearl is that Vietnamese product text is this dataset's
most valuable asset.

**One hotel arrives across three endpoints.** Geo and address come from
``/reference-data/locations/hotels``, price from ``/shopping/hotel-offers``,
rating from ``/e-reputation/hotel-sentiments``. Giving all three the same
``source_ref`` would collide on
``UNIQUE (source, source_ref, parser_version)`` and the last one parsed would
silently overwrite the other two. So refs are faceted —
``amadeus:hotel:<id>``, ``amadeus:offer:<id>``, ``amadeus:sentiment:<id>`` —
with ``parent_source_ref`` pointing at the hotel facet, and normalise folds them
back together.

The test tier is rate limited; this collector still runs at the same 0.5 rps as
everything else, because spec section 8 states that ceiling with no exemption
for APIs, and the whole budget finishes in about fifteen minutes anyway.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Iterator

from collectors.base import BaseCollector, RawPage, Target, register
from ids import source_ref

log = logging.getLogger("collector.amadeus")

TOKEN_PATH = "/v1/security/oauth2/token"


class AmadeusAuthError(RuntimeError):
    pass


@register
class AmadeusCollector(BaseCollector):
    source = "amadeus"
    parser_version = "amadeus-1.0.0"
    rate_limit_rps = 0.5

    def __init__(self, cfg, src, *, fetcher=None) -> None:  # noqa: ANN001
        super().__init__(cfg, src, fetcher=fetcher)
        self.base_url = (
            os.environ.get("AMADEUS_BASE_URL") or src.base_url or "https://test.api.amadeus.com"
        ).rstrip("/")
        # hosts must be the host we really call, or the rate limiter and robots
        # gate protect a domain that sees no traffic while the real one is
        # effectively unlimited.
        from urllib.parse import urlsplit

        host = urlsplit(self.base_url).netloc.lower()
        if host and host not in [h.lower() for h in self.hosts]:
            self.hosts = (host,)
        self._token: str | None = None
        self._token_expires: float = 0.0
        self.unmatched_urls: list[str] = []
        self.on_discovery_page = None

    # =========================================================================
    # auth
    # =========================================================================
    def _credentials(self) -> tuple[str, str]:
        key = os.environ.get("AMADEUS_CLIENT_ID", "").strip()
        secret = os.environ.get("AMADEUS_CLIENT_SECRET", "").strip()
        if not key or not secret:
            raise AmadeusAuthError(
                "AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET are not set.\n"
                "  1. Register at https://developers.amadeus.com/register\n"
                "  2. Create a Self-Service app to get an API Key and API Secret\n"
                "  3. Put them in vota-recsys/.env (never commit them)\n"
                "The free test tier is enough for Week 1."
            )
        return key, secret

    def _access_token(self) -> str:
        """OAuth2 client_credentials, cached until shortly before expiry."""
        if self._token and time.monotonic() < self._token_expires:
            return self._token
        key, secret = self._credentials()
        result = self.fetcher.get(
            f"{self.base_url}{TOKEN_PATH}",
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "client_id": key, "client_secret": secret},
        )
        if result.status != 200:
            raise AmadeusAuthError(
                f"token request returned {result.status}: "
                f"{result.content[:300].decode('utf-8', 'replace')}"
            )
        payload = json.loads(result.content)
        self._token = payload["access_token"]
        # Refresh a minute early rather than discovering expiry mid-run.
        self._token_expires = time.monotonic() + max(60, int(payload.get("expires_in", 1799)) - 60)
        log.info("amadeus token acquired, valid ~%ss", payload.get("expires_in"))
        return self._token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token()}", "Accept": "application/json"}

    # =========================================================================
    # discover
    # =========================================================================
    def quote_contexts(self) -> list[str | None]:
        return [*self.cfg.enabled_quote_contexts(), None]

    def discover(self) -> Iterator[Target]:
        """Build the request plan from config budgets and the canonical destinations.

        Nothing is fetched here beyond what the plan needs: each Target is one
        API call, and ``fetch`` performs it. Keeping the plan declarative means
        the call budget is visible in config rather than emergent from a loop.
        """
        budgets = self.src.get("budgets", {}) or {}
        ctx = self.cfg.enabled_quote_contexts()[0] if self.cfg.enabled_quote_contexts() else None
        quote = self.cfg.resolve_quote_context(ctx) if ctx else None
        radius = int((self.src.get("probe") or {}).get("radius_km", 20))

        for name, dest in self.cfg.destinations.items():
            if dest.lat is None or dest.lon is None:
                continue
            for _ in range(int(budgets.get("hotels_by_geocode_per_destination", 1))):
                yield Target(
                    url=(
                        f"{self.base_url}/v1/reference-data/locations/hotels/by-geocode"
                        f"?latitude={dest.lat}&longitude={dest.lon}&radius={radius}"
                        f"&radiusUnit=KM&hotelSource=ALL"
                    ),
                    page_type="api",
                    quote_ctx=None,
                    priority=10,
                    meta={"endpoint": "hotels_by_geocode", "destination": name},
                )
            for _ in range(int(budgets.get("activities_per_destination", 1))):
                yield Target(
                    url=(
                        f"{self.base_url}/v1/shopping/activities"
                        f"?latitude={dest.lat}&longitude={dest.lon}&radius={radius}"
                    ),
                    page_type="api",
                    quote_ctx=None,
                    priority=20,
                    meta={"endpoint": "activities", "destination": name},
                )

        # Flights: the HAN/SGN <-> CXR/PQC/DAD/HPH... matrix from spec section 9.
        routes = self.cfg.section("flight_routes")
        origins = list(routes.get("origins") or [])
        dests = list(routes.get("destinations") or [])
        depart = (quote or {}).get("checkin")
        if depart:
            pairs = [(o, d) for o in origins for d in dests]
            if routes.get("both_directions", True):
                pairs += [(d, o) for o, d in pairs]
            for origin, destination in pairs:
                if origin == destination:
                    continue
                yield Target(
                    url=(
                        f"{self.base_url}/v2/shopping/flight-offers"
                        f"?originLocationCode={origin}&destinationLocationCode={destination}"
                        f"&departureDate={depart}&adults={(quote or {}).get('adults', 1)}"
                        f"&currencyCode=VND&max=20&nonStop=false"
                    ),
                    page_type="api",
                    quote_ctx=ctx,
                    priority=30,
                    meta={
                        "endpoint": "flight_offers",
                        "origin": origin,
                        "destination_iata": destination,
                    },
                )
        else:
            log.warning("no quote context resolved, so no flight targets were planned")

    # =========================================================================
    # fetch
    # =========================================================================
    def fetch(self, target: Target) -> RawPage:
        raw = self.http_fetch(target, headers=self._auth_headers())
        # Cached as .json.gz through the same cache and raw_pages path as any
        # HTML page, so parse --reparse works identically for API data.
        raw.content_type = raw.content_type or "application/json"
        return raw

    # =========================================================================
    # parse
    # =========================================================================
    def parse(self, raw: RawPage) -> list[dict]:
        endpoint = (raw.meta or {}).get("endpoint")
        try:
            doc = json.loads(raw.content.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"amadeus {endpoint}: response is not JSON ({exc})") from exc

        if isinstance(doc, dict) and doc.get("errors"):
            raise ValueError(f"amadeus {endpoint} returned errors: {doc['errors'][:2]}")

        data = (doc or {}).get("data") or []
        if endpoint == "hotels_by_geocode":
            return self._parse_hotels(raw, data)
        if endpoint == "activities":
            return self._parse_activities(raw, data)
        if endpoint == "flight_offers":
            return self._parse_flights(raw, doc)
        if endpoint == "hotel_offers":
            return self._parse_offers(raw, data)
        if endpoint == "hotel_sentiments":
            return self._parse_sentiments(raw, data)
        raise ValueError(f"amadeus: no parser for endpoint {endpoint!r}")

    # -- hotels ------------------------------------------------------------
    def _parse_hotels(self, raw: RawPage, data: list[dict]) -> list[dict]:
        destination = (raw.meta or {}).get("destination")
        rows: list[dict] = []
        for h in data:
            hotel_id = h.get("hotelId") or h.get("id")
            if not hotel_id:
                continue
            geo = h.get("geoCode") or {}
            address = h.get("address") or {}
            rows.append(
                {
                    "source_ref": source_ref(self.source, "hotel", hotel_id),
                    "page_kind": "product",
                    "taxonomy_hint": "hotel",
                    "category_raw": "HOTEL",
                    "name_raw": h.get("name") or hotel_id,
                    # Deliberately no description: the reference-data endpoint
                    # does not carry one, and inventing a "hotel in X" sentence
                    # would poison the embedding corpus with filler.
                    "description_html": None,
                    "destination_raw": destination
                    or address.get("cityName")
                    or address.get("countryCode"),
                    "address_raw": ", ".join(
                        str(x)
                        for x in (
                            *(address.get("lines") or []),
                            address.get("postalCode"),
                            address.get("cityName"),
                        )
                        if x
                    )
                    or None,
                    "latitude": geo.get("latitude"),
                    "longitude": geo.get("longitude"),
                    "brand_raw": h.get("chainCode"),
                    "amenity_labels": h.get("amenities") or [],
                    "star_rating_raw": h.get("rating"),
                    "quote_ctx": raw.quote_ctx,
                    "quote_params": (raw.meta or {}).get("quote_params"),
                    "_prov": {
                        "name_raw": "amadeus:/v1/reference-data/locations/hotels/by-geocode name",
                        "latitude": "amadeus:geoCode.latitude",
                        "longitude": "amadeus:geoCode.longitude",
                        "address_raw": "amadeus:address",
                        "brand_raw": "amadeus:chainCode",
                        "destination_raw": "amadeus:request destination",
                        "_endpoint": "hotels_by_geocode",
                        "_dupe_id": h.get("dupeId"),
                    },
                }
            )
        return rows

    def _parse_offers(self, raw: RawPage, data: list[dict]) -> list[dict]:
        """Price facet. Folded onto the hotel facet by ``parent_source_ref``."""
        rows: list[dict] = []
        for entry in data:
            hotel = entry.get("hotel") or {}
            hotel_id = hotel.get("hotelId")
            offers = entry.get("offers") or []
            if not hotel_id or not offers:
                continue
            offer = offers[0]
            price = offer.get("price") or {}
            room = (offer.get("room") or {}).get("typeEstimated") or {}
            description = (offer.get("room") or {}).get("description") or {}
            rows.append(
                {
                    "source_ref": source_ref(self.source, "offer", hotel_id),
                    "parent_source_ref": source_ref(self.source, "hotel", hotel_id),
                    "page_kind": "product",
                    "taxonomy_hint": "hotel",
                    "category_raw": "HOTEL",
                    "name_raw": hotel.get("name") or hotel_id,
                    # English text: description_policy routes it to
                    # attributes.descriptionEn, never to products.description.
                    "description_html": description.get("text"),
                    "price_raw": price.get("total") or price.get("base"),
                    "currency_raw": price.get("currency"),
                    "spec_pairs": [
                        {"label": k, "value": str(v)}
                        for k, v in room.items()
                        if v not in (None, "")
                    ],
                    "quote_ctx": raw.quote_ctx,
                    "quote_params": (raw.meta or {}).get("quote_params"),
                    "_prov": {
                        "price_raw": "amadeus:/v3/shopping/hotel-offers offers[0].price.total",
                        "description_html": "amadeus:offers[0].room.description.text (English)",
                        "_endpoint": "hotel_offers",
                    },
                }
            )
        return rows

    def _parse_sentiments(self, raw: RawPage, data: list[dict]) -> list[dict]:
        """Rating facet. Only the aggregate and the count (spec section 5.4)."""
        rows: list[dict] = []
        for entry in data:
            hotel_id = entry.get("hotelId")
            if not hotel_id:
                continue
            rows.append(
                {
                    "source_ref": source_ref(self.source, "sentiment", hotel_id),
                    "parent_source_ref": source_ref(self.source, "hotel", hotel_id),
                    "page_kind": "product",
                    "taxonomy_hint": "hotel",
                    "category_raw": "HOTEL",
                    "name_raw": entry.get("name") or hotel_id,
                    # overallRating is 0-100 here; config.ratings.scale_by_source
                    # rescales it to the shared 0-5 scale in normalise.
                    "aggregate_rating_raw": entry.get("overallRating"),
                    "review_count_raw": entry.get("numberOfReviews"),
                    "rating_best_raw": 100,
                    "quote_ctx": None,
                    "_prov": {
                        "aggregate_rating_raw": "amadeus:/v2/e-reputation overallRating (0-100)",
                        "review_count_raw": "amadeus:numberOfReviews",
                        "_endpoint": "hotel_sentiments",
                    },
                }
            )
        return rows

    # -- activities --------------------------------------------------------
    def _parse_activities(self, raw: RawPage, data: list[dict]) -> list[dict]:
        destination = (raw.meta or {}).get("destination")
        rows: list[dict] = []
        for a in data:
            aid = a.get("id")
            if not aid:
                continue
            geo = a.get("geoCode") or {}
            price = a.get("price") or {}
            rows.append(
                {
                    "source_ref": source_ref(self.source, "activity", aid),
                    "page_kind": "product",
                    "taxonomy_hint": "attraction",
                    "category_raw": "ACTIVITY",
                    "name_raw": a.get("name") or aid,
                    "description_html": a.get("shortDescription") or a.get("description"),
                    "destination_raw": destination,
                    "latitude": geo.get("latitude"),
                    "longitude": geo.get("longitude"),
                    "price_raw": price.get("amount"),
                    "currency_raw": price.get("currencyCode"),
                    "images": [p for p in (a.get("pictures") or []) if isinstance(p, str)],
                    "opening_hours_raw": a.get("bookingLink") and None,
                    "spec_pairs": (
                        [{"label": "minimumDuration", "value": str(a["minimumDuration"])}]
                        if a.get("minimumDuration")
                        else []
                    ),
                    "quote_ctx": None,
                    "_prov": {
                        "name_raw": "amadeus:/v1/shopping/activities name",
                        "description_html": "amadeus:shortDescription (English)",
                        "price_raw": "amadeus:price.amount",
                        "images": "amadeus:pictures",
                        "_endpoint": "activities",
                    },
                }
            )
        return rows

    # -- flights -----------------------------------------------------------
    def _parse_flights(self, raw: RawPage, doc: dict) -> list[dict]:
        """One product per distinct (carrier, flightNo, route, cabin).

        Flights are required for the Week 3 cross-category work (spec section 1),
        and ``destination`` is the **arrival** city — see question D3 in
        cdp-schema-questions.md. Using the origin would put every seeded trip in
        two destinations and break the section 10 one-trip-one-destination rule.
        """
        carriers = ((doc.get("dictionaries") or {}).get("carriers")) or {}
        iata_map = self.cfg.iata_to_destination()
        rows: list[dict] = []
        seen: set[str] = set()

        for offer in doc.get("data") or []:
            price = offer.get("price") or {}
            travellers = offer.get("travelerPricings") or []
            cabin = None
            baggage = None
            if travellers:
                segs = travellers[0].get("fareDetailsBySegment") or []
                if segs:
                    cabin = segs[0].get("cabin")
                    baggage = (segs[0].get("includedCheckedBags") or {}).get("weight")

            for itinerary in offer.get("itineraries") or []:
                segments = itinerary.get("segments") or []
                if not segments:
                    continue
                first, last = segments[0], segments[-1]
                carrier = first.get("carrierCode")
                number = first.get("number")
                origin = (first.get("departure") or {}).get("iataCode")
                arrival = (last.get("arrival") or {}).get("iataCode")
                if not all((carrier, number, origin, arrival)):
                    continue
                key = f"{carrier}{number}-{origin}-{arrival}-{cabin or 'X'}"
                if key in seen:
                    continue
                seen.add(key)

                carrier_name = carriers.get(carrier, carrier)
                rows.append(
                    {
                        "source_ref": source_ref(self.source, "flight", key),
                        "page_kind": "product",
                        "taxonomy_hint": "flight",
                        "category_raw": "FLIGHT_OFFER",
                        "name_raw": f"{carrier_name} {carrier}{number} {origin} - {arrival}",
                        "description_html": None,
                        "destination_raw": iata_map.get(arrival, arrival),
                        "price_raw": price.get("total") or price.get("grandTotal"),
                        "currency_raw": price.get("currency"),
                        "quote_ctx": raw.quote_ctx,
                        "quote_params": (raw.meta or {}).get("quote_params"),
                        "flight": {
                            "carrier": carrier_name,
                            "flightNo": f"{carrier}{number}",
                            "originIata": origin,
                            "destinationIata": arrival,
                            "departTime": (first.get("departure") or {}).get("at"),
                            "arriveTime": (last.get("arrival") or {}).get("at"),
                            "durationMin": _iso_duration_minutes(itinerary.get("duration")),
                            "stops": max(0, len(segments) - 1),
                            "cabinClass": cabin,
                            "baggageAllowanceKg": baggage,
                            "fareType": (offer.get("pricingOptions") or {}).get("fareType"),
                            "refundable": (offer.get("pricingOptions") or {}).get(
                                "refundableFare"
                            ),
                        },
                        "_prov": {
                            "name_raw": "amadeus:/v2/shopping/flight-offers carrier + number + route",
                            "price_raw": "amadeus:price.total",
                            "destination_raw": "amadeus:arrival iataCode (config flight_routes.destination_rule)",
                            "flight": "amadeus:itineraries[].segments[]",
                            "_endpoint": "flight_offers",
                        },
                    }
                )
        return rows


def _iso_duration_minutes(value: str | None) -> int | None:
    """``'PT2H15M'`` -> ``135``."""
    if not value or not value.startswith("PT"):
        return None
    import re

    hours = re.search(r"(\d+)H", value)
    minutes = re.search(r"(\d+)M", value)
    total = (int(hours.group(1)) * 60 if hours else 0) + (int(minutes.group(1)) if minutes else 0)
    return total or None


# =============================================================================
# coverage probe
# =============================================================================
def run_probe(cfg) -> int:  # noqa: ANN001
    """~20 requests: how much Vietnamese inventory does the test tier actually have?

    Run this before anything else. Spec section 0's checkpoint asks whether
    there is usable data by Wednesday; this answers the same question on Monday
    morning, for the source that has to carry the volume. If the counts here are
    thin, the honest move is to add another section 9 source (OpenStreetMap /
    Wikivoyage) rather than to discover the shortfall on Thursday.
    """
    import exitcodes
    from collectors.net import make_fetcher

    src = cfg.source("amadeus")
    fetcher = make_fetcher(cfg, src)
    collector = AmadeusCollector(cfg, src, fetcher=fetcher)

    try:
        collector._access_token()
    except AmadeusAuthError as exc:
        log.error("%s", exc)
        return exitcodes.CONFIG_OR_DB

    probe = src.get("probe") or {}
    names = list(probe.get("destinations") or list(cfg.destinations)[:5])
    radius = int(probe.get("radius_km", 20))
    total_hotels = total_activities = 0

    print("=" * 78)
    print("Amadeus coverage probe — these counts decide the week")
    print("=" * 78)
    print(f"{'destination':18} {'hotels':>8} {'activities':>11}")
    print("-" * 40)

    for name in names:
        dest = cfg.destinations.get(name)
        if not dest or dest.lat is None:
            continue
        hotels = activities = -1
        try:
            r = fetcher.get(
                f"{collector.base_url}/v1/reference-data/locations/hotels/by-geocode"
                f"?latitude={dest.lat}&longitude={dest.lon}&radius={radius}"
                f"&radiusUnit=KM&hotelSource=ALL",
                headers=collector._auth_headers(),
            )
            hotels = len((json.loads(r.content) or {}).get("data") or []) if r.status == 200 else -1
        except Exception as exc:  # noqa: BLE001
            log.warning("hotels probe failed for %s: %s", name, exc)
        try:
            r = fetcher.get(
                f"{collector.base_url}/v1/shopping/activities"
                f"?latitude={dest.lat}&longitude={dest.lon}&radius={radius}",
                headers=collector._auth_headers(),
            )
            activities = (
                len((json.loads(r.content) or {}).get("data") or []) if r.status == 200 else -1
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("activities probe failed for %s: %s", name, exc)

        total_hotels += max(hotels, 0)
        total_activities += max(activities, 0)
        print(f"{name:18} {hotels:>8} {activities:>11}")

    routes = cfg.section("flight_routes")
    n_routes = len(routes.get("origins") or []) * len(routes.get("destinations") or [])
    if routes.get("both_directions", True):
        n_routes *= 2

    print("-" * 40)
    print(f"{'TOTAL (probed)':18} {total_hotels:>8} {total_activities:>11}")
    print()
    print(f"Destinations probed:      {len(names)} of {len(cfg.destinations)}")
    print(f"Planned flight routes:    {n_routes}")
    print()
    print("Extrapolation to the full run:")
    if names:
        per_dest_h = total_hotels / len(names)
        per_dest_a = total_activities / len(names)
        est = per_dest_h * len(cfg.destinations) + per_dest_a * len(cfg.destinations)
        print(f"  ~{per_dest_h:.0f} hotels + ~{per_dest_a:.0f} activities per destination")
        print(f"  ~{est:.0f} products from {len(cfg.destinations)} destinations, "
              f"plus ~{n_routes * 10}-{n_routes * 25} flight products")
        floor = int(cfg.section("dod").get("products_min", 2000))
        if est + n_routes * 10 < floor:
            print()
            print(f"  WARNING: that is short of the {floor}-product floor in spec section 0 "
                  f"item 1.")
            print("  Add another spec section 9 source now, not on Thursday:")
            print("    - enable sources.osm (Overpass POIs + Wikivoyage prose, no API key)")
            print("    - extend data/manual/*.yaml")
    return exitcodes.OK
