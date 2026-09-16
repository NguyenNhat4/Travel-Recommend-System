"""OpenStreetMap (Overpass) + Vietnamese Wikipedia — the keyless fallback.

Spec section 9 lists OpenStreetMap / Wikivoyage as a fallback for "destinations,
POI, attractions cho itinerary assistant". It earns a real implementation rather
than a footnote, because it is the only section 9 source that needs no
credentials: when vinpearl is unreachable and nobody has an Amadeus key yet,
this is what can still put attractions in the database today.

What it actually gives, honestly:

* **Real Vietnamese names.** OSM POIs in Vietnam are usually tagged with the
  local name, which is exactly the embedding input handbook section 3 cares
  about.
* **Real coordinates**, which section 5.1 wants for dedup and the Week 4
  itinerary.
* **``opening_hours``** on many POIs — one of the two fields section 5.2 singles
  out as needed from Week 1 so nobody has to re-crawl for the itinerary work.
* **Descriptions: often nothing.** OSM is a geographic database, not a content
  one. Where a POI carries a ``wikipedia`` tag, ``discover`` emits a second
  target for the Vietnamese Wikipedia extract, which is a genuine description of
  that attraction. Where it does not, ``description`` stays **NULL** and
  ``quality_score`` falls accordingly — that is the honest outcome. Synthesising
  "X là một điểm tham quan ở Y" from the tags would produce exactly the generic
  filler spec section 7 tells you to read 20 descriptions to catch.

Overpass is a shared volunteer service. It is queried at the same 0.5 rps as
everything else, one bounded query per destination, with the timeout and result
size capped in the query itself.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from typing import Any, Iterator

from collectors.base import BaseCollector, RawPage, Target, register
from ids import source_ref, slugify

log = logging.getLogger("collector.osm")

#: POI kinds worth having, mapped to a taxonomy. Golf courses are included
#: because `golf` is one of the five required taxonomies and has almost no other
#: source (see data/manual/golf.yaml for the same problem).
_POI_TAGS: tuple[tuple[str, str, str], ...] = (
    ("tourism", "attraction", "attraction"),
    ("tourism", "theme_park", "attraction"),
    ("tourism", "museum", "attraction"),
    ("tourism", "viewpoint", "attraction"),
    ("tourism", "zoo", "attraction"),
    ("tourism", "aquarium", "attraction"),
    ("leisure", "water_park", "attraction"),
    ("leisure", "golf_course", "golf"),
    ("historic", "monument", "attraction"),
    ("historic", "castle", "attraction"),
    ("historic", "ruins", "attraction"),
)


@register
class OsmCollector(BaseCollector):
    source = "osm"
    parser_version = "osm-1.0.0"
    rate_limit_rps = 0.5

    def __init__(self, cfg, src, *, fetcher=None) -> None:  # noqa: ANN001
        super().__init__(cfg, src, fetcher=fetcher)
        self.overpass = str(src.get("overpass_url", "https://overpass-api.de/api/interpreter"))
        self.wiki_api = str(src.get("wikivoyage_api", "https://vi.wikipedia.org/w/api.php"))
        self.unmatched_urls: list[str] = []
        self.on_discovery_page = None
        self.cache = None

    # =========================================================================
    # discover
    # =========================================================================
    def discover(self) -> Iterator[Target]:
        """One Overpass query per destination, plus Wikipedia follow-ups.

        The Wikipedia targets can only be planned once the Overpass results are
        in, so they come from a second ``discover`` pass: run
        ``discover --source osm`` again (or with ``--from-cache``) after the
        first fetch and the already-cached Overpass responses are read from disk
        rather than re-requested. That is the whole reason ``fetch`` writes bytes
        before rows — a second discovery wave costs nothing.
        """
        radius_km = int((self.src.get("probe") or {}).get("radius_km", 25))
        for name, dest in self.cfg.destinations.items():
            if dest.lat is None or dest.lon is None:
                continue
            query = self._overpass_query(dest.lat, dest.lon, radius_km * 1000)
            yield Target(
                url=f"{self.overpass}?data={urllib.parse.quote(query)}",
                page_type="api",
                quote_ctx=None,
                priority=20,
                meta={"endpoint": "overpass", "destination": name},
            )

        yield from self._wikipedia_targets()

    def _overpass_query(self, lat: float, lon: float, radius_m: int) -> str:
        """Bounded Overpass QL: explicit timeout, capped output, named POIs only."""
        clauses = "\n  ".join(
            f'nwr["{k}"="{v}"]["name"](around:{radius_m},{lat},{lon});'
            for k, v, _ in _POI_TAGS
        )
        return f"[out:json][timeout:60];\n(\n  {clauses}\n);\nout center tags 200;"

    def _wikipedia_targets(self) -> Iterator[Target]:
        """Vietnamese Wikipedia extracts for POIs that declare a ``wikipedia`` tag.

        Read from already-parsed staging rows, so this needs no network and adds
        a target only where a real article exists.
        """
        try:
            import db
            from sqlalchemy import text

            with db.session_scope(self.cfg) as s:
                rows = s.execute(
                    text(
                        "SELECT DISTINCT payload->'_prov'->>'_wikipedia' AS article "
                        "FROM products_staging "
                        "WHERE source = 'osm' AND payload->'_prov' ? '_wikipedia'"
                    )
                ).all()
        except Exception as exc:  # noqa: BLE001 - first run, before any staging rows
            log.debug("no wikipedia follow-ups yet (%s)", exc)
            return

        for (article,) in rows:
            if not article:
                continue
            lang, _, title = str(article).partition(":")
            if not title:
                lang, title = "vi", str(article)
            if lang != "vi":
                # Only Vietnamese articles: an English extract would land in
                # products.description and contaminate the corpus, which is the
                # same problem description_policy solves for Amadeus.
                continue
            params = urllib.parse.urlencode(
                {
                    "action": "query",
                    "format": "json",
                    "prop": "extracts",
                    "explaintext": "1",
                    "exintro": "0",
                    "redirects": "1",
                    "titles": title,
                }
            )
            yield Target(
                url=f"{self.wiki_api}?{params}",
                page_type="api",
                quote_ctx=None,
                priority=25,
                meta={"endpoint": "wikipedia", "article": title},
            )

    # =========================================================================
    # fetch
    # =========================================================================
    def fetch(self, target: Target) -> RawPage:
        raw = self.http_fetch(target)
        raw.content_type = raw.content_type or "application/json"
        return raw

    # =========================================================================
    # parse
    # =========================================================================
    def parse(self, raw: RawPage) -> list[dict]:
        endpoint = (raw.meta or {}).get("endpoint")
        doc = json.loads(raw.content.decode("utf-8", errors="replace"))
        if endpoint == "overpass":
            return self._parse_overpass(raw, doc)
        if endpoint == "wikipedia":
            return self._parse_wikipedia(raw, doc)
        raise ValueError(f"osm: no parser for endpoint {endpoint!r}")

    def _parse_overpass(self, raw: RawPage, doc: dict) -> list[dict]:
        destination = (raw.meta or {}).get("destination")
        taxonomy_for = {(k, v): t for k, v, t in _POI_TAGS}
        rows: list[dict] = []

        for el in doc.get("elements") or []:
            tags: dict[str, Any] = el.get("tags") or {}
            name = tags.get("name:vi") or tags.get("name")
            if not name:
                continue
            taxonomy = None
            for (key, value), tax in taxonomy_for.items():
                if tags.get(key) == value:
                    taxonomy = tax
                    break
            if taxonomy is None:
                continue

            osm_id = f"{el.get('type', 'node')}/{el.get('id')}"
            center = el.get("center") or {}
            lat = el.get("lat") or center.get("lat")
            lon = el.get("lon") or center.get("lon")

            spec_pairs = [
                {"label": label, "value": str(tags[tag])}
                for tag, label in (
                    ("opening_hours", "Giờ mở cửa"),
                    ("phone", "Điện thoại"),
                    ("website", "Website"),
                    ("fee", "Phí vào cửa"),
                    ("wheelchair", "Tiếp cận xe lăn"),
                )
                if tags.get(tag)
            ]

            prov: dict[str, Any] = {
                "name_raw": "osm:tags.name:vi or tags.name",
                "latitude": "osm:element lat/center",
                "longitude": "osm:element lon/center",
                "destination_raw": "osm:request destination",
                "_endpoint": "overpass",
                "_osm_id": osm_id,
            }
            # description:vi is a real Vietnamese description when present.
            description = tags.get("description:vi") or tags.get("description")
            if description:
                prov["description_html"] = "osm:tags.description:vi"
            if tags.get("wikipedia"):
                # Picked up by the second discovery wave.
                prov["_wikipedia"] = tags["wikipedia"]
            if tags.get("opening_hours"):
                prov["opening_hours_raw"] = "osm:tags.opening_hours"

            rows.append(
                {
                    "source_ref": source_ref(self.source, osm_id),
                    "page_kind": "product",
                    "taxonomy_hint": taxonomy,
                    "category_raw": next(
                        (v for k, v, _ in _POI_TAGS if tags.get(k) == v), taxonomy
                    ),
                    "name_raw": name,
                    # NULL when OSM has none. See the module docstring: a
                    # synthesised "X is an attraction in Y" is exactly the
                    # generic filler section 7 warns about.
                    "description_html": description,
                    "destination_raw": destination or tags.get("addr:city"),
                    "address_raw": ", ".join(
                        str(tags[t])
                        for t in ("addr:housenumber", "addr:street", "addr:city")
                        if tags.get(t)
                    )
                    or None,
                    "phone_raw": tags.get("phone") or tags.get("contact:phone"),
                    "latitude": lat,
                    "longitude": lon,
                    "opening_hours_raw": tags.get("opening_hours"),
                    "spec_pairs": spec_pairs,
                    "poi_name": name,
                    "quote_ctx": None,
                    "_prov": prov,
                }
            )
        log.info("osm: %d POI(s) for %s", len(rows), destination)
        return rows

    def _parse_wikipedia(self, raw: RawPage, doc: dict) -> list[dict]:
        """Attach a Vietnamese Wikipedia extract as a description.

        Emitted as its own staging row keyed to the article, with
        ``parent_source_ref`` unset: it is matched to the POI by name at dedup
        time rather than by a fabricated link, so a wrong article cannot silently
        rewrite a POI's description.
        """
        pages = ((doc.get("query") or {}).get("pages")) or {}
        rows: list[dict] = []
        for page in pages.values():
            if "missing" in page:
                continue
            title = page.get("title")
            extract = (page.get("extract") or "").strip()
            if not title or len(extract) < 120:
                continue
            rows.append(
                {
                    "source_ref": source_ref(self.source, "wikipedia", slugify(title)),
                    "page_kind": "product",
                    "taxonomy_hint": "attraction",
                    "category_raw": "attraction",
                    "name_raw": title,
                    "description_html": extract,
                    "destination_raw": None,
                    "quote_ctx": None,
                    "_prov": {
                        "name_raw": "wikipedia:vi title",
                        "description_html": "wikipedia:vi extract (prop=extracts&explaintext)",
                        "_endpoint": "wikipedia",
                    },
                }
            )
        return rows
