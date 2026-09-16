"""Hand-curated products from YAML, through the same contract as every crawler.

Why this exists: spec section 0 item 1 requires all five taxonomies
(``hotel|flight|combo|attraction|golf``), and tracing each one through the
designed sources leaves **golf** and **combo** depending on a single unverified
source. Amadeus has no package or golf-course endpoint, and the OTAs have
neither. So one wrong URL guess — or, as it turned out, one WAF rule — silently
turns the section 4.2 five-value taxonomy CHECK into a three-value reality, and
the Friday demo's headline artefact ("đếm được số product theo category") shows
two empty rows.

This is an honest source, not a workaround:

* every row is provenanced as ``source='manual'`` and appears in the README
  section 12 item 1 extraction table like any other source;
* ``source_priority`` is the lowest in ``config.yaml``, so the moment a crawled
  source provides the same product, vinpearl (or an OTA) wins every field on
  merge and this contributes nothing but coverage;
* fields nobody has verified are left **null** rather than invented. That lowers
  ``quality_score``, which is correct — the score is supposed to report
  incompleteness, not hide it. In particular prices are omitted: the spec's
  "đừng tự đoán" applies to a price at least as much as to a destination.

It reads local YAML, so it makes no requests: ``respect_robots`` is false for
this source because there is nothing to ask permission of.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterator

import yaml

from collectors.base import BaseCollector, RawPage, Target, register
from ids import slugify, source_ref

log = logging.getLogger("collector.manual")

HERE = Path(__file__).resolve().parent.parent


@register
class ManualCollector(BaseCollector):
    source = "manual"
    parser_version = "manual-1.0.0"
    rate_limit_rps = 0.5
    respect_robots = False

    def __init__(self, cfg, src, *, fetcher=None) -> None:  # noqa: ANN001
        super().__init__(cfg, src, fetcher=fetcher)
        self.unmatched_urls: list[str] = []
        self.on_discovery_page = None

    # =========================================================================
    # discover
    # =========================================================================
    def discover(self) -> Iterator[Target]:
        """One target per YAML file.

        Modelled as targets-and-pages rather than a direct DB write so the whole
        pipeline is identical for curated data: the file is "fetched" into the
        raw cache, gets a ``raw_pages`` row, and is parsed from there. That means
        ``parse --reparse`` works on curated rows too, and a mistake in the
        parsing rules costs a re-parse rather than a re-typing.
        """
        for rel in self.src.get("files", []) or []:
            path = HERE / rel
            if not path.exists():
                log.warning("manual file listed in config but missing on disk: %s", path)
                continue
            yield Target(
                url=path.as_uri(),
                page_type="api",
                quote_ctx=None,
                priority=90,
                meta={"manual_path": str(rel)},
            )

    # =========================================================================
    # fetch
    # =========================================================================
    def fetch(self, target: Target) -> RawPage:
        """Read the local file. No network, so no rate limiter and no robots."""
        rel = target.meta.get("manual_path")
        path = HERE / rel if rel else Path(target.url.replace("file:///", ""))
        content = path.read_bytes()
        return RawPage(
            url=target.url,
            http_status=200,
            content=content,
            content_type="application/x-yaml",
            quote_ctx=None,
            meta={"attempts": 1, "elapsed_ms": 0, "waited_ms": 0, "manual_path": rel},
        )

    # =========================================================================
    # parse
    # =========================================================================
    def parse(self, raw: RawPage) -> list[dict]:
        doc = yaml.safe_load(raw.content.decode("utf-8")) or {}
        taxonomy = doc.get("taxonomy")
        if taxonomy not in ("golf", "combo", "hotel", "attraction", "flight"):
            raise ValueError(
                f"manual file {raw.url} has taxonomy={taxonomy!r}; expected one of the "
                "five spec section 5.1 values"
            )
        curated_by = doc.get("curated_by") or "unknown"
        curated_at = doc.get("curated_at") or ""
        note = doc.get("provenance_note") or ""

        rows: list[dict] = []
        for item in doc.get("items") or []:
            name = (item.get("name") or "").strip()
            if not name:
                log.warning("manual item with no name in %s, skipped", raw.url)
                continue
            ref = source_ref(self.source, taxonomy, slugify(name))
            payload: dict[str, Any] = {
                "source_ref": ref,
                "page_kind": "product",
                "taxonomy_hint": taxonomy,
                "category_raw": taxonomy,
                "name_raw": name,
                "description_html": item.get("description"),
                "destination_raw": item.get("destination"),
                "address_raw": item.get("address"),
                "phone_raw": item.get("phone"),
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
                "images": item.get("images") or [],
                # Deliberately absent unless the YAML states one. See the module
                # docstring: an invented price is not better than a null one.
                "price_raw": item.get("price_raw"),
                "currency_raw": item.get("currency") or "VND",
                "star_rating_raw": item.get("star_rating"),
                "amenity_labels": item.get("amenities") or [],
                "spec_pairs": item.get("spec_pairs") or [],
                "quote_ctx": None,
                "_prov": {
                    "_source": f"manual YAML {raw.meta.get('manual_path') or raw.url}",
                    "curated_by": curated_by,
                    "curated_at": curated_at,
                    "note": note,
                    **{k: "manual:curated" for k in item if k not in ("spec_pairs",)},
                },
            }
            if taxonomy == "golf":
                payload["golf"] = {
                    "courseName": item.get("course_name") or name,
                    "holes_raw": item.get("holes"),
                    "par_raw": item.get("par"),
                    "tee_raw": item.get("tee_time_slots"),
                    "caddie_fee_included": item.get("caddie_fee_included"),
                    "buggy_included": item.get("buggy_included"),
                    "weekday_price": item.get("weekday_price"),
                    "weekend_price": item.get("weekend_price"),
                }
            elif taxonomy == "combo":
                payload["combo"] = {
                    "nights_raw": item.get("nights"),
                    "components": item.get("components"),
                    "min_pax": item.get("min_pax"),
                    "valid_from": item.get("valid_from"),
                    "valid_to": item.get("valid_to"),
                    "transfer_included": item.get("transfer_included"),
                }
            elif taxonomy == "attraction":
                payload["opening_hours_raw"] = item.get("opening_hours")
                payload["ticket_label_raw"] = item.get("ticket_type")
                payload["poi_name"] = item.get("poi_name") or name
            rows.append(payload)

        if not rows:
            raise ValueError(f"manual file {raw.url} produced no items")
        log.info("manual: %d %s item(s) from %s", len(rows), taxonomy, raw.meta.get("manual_path"))
        return rows


def validate_manual_files(cfg) -> list[str]:  # noqa: ANN001
    """Report problems in the curated YAML without touching the database.

    Used by a test, so a typo in a hand-maintained file fails in CI rather than
    at 5pm on Thursday.
    """
    problems: list[str] = []
    for rel in (cfg.source("manual").get("files") or []):
        path = HERE / rel
        if not path.exists():
            problems.append(f"{rel}: missing")
            continue
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            problems.append(f"{rel}: unparseable YAML ({exc})")
            continue
        if doc.get("taxonomy") not in ("golf", "combo", "hotel", "attraction", "flight"):
            problems.append(f"{rel}: taxonomy must be one of the five section 5.1 values")
        if not doc.get("curated_by"):
            problems.append(f"{rel}: curated_by is required (provenance)")
        items = doc.get("items") or []
        if not items:
            problems.append(f"{rel}: no items")
        seen: set[str] = set()
        canonical = set(cfg.canonical_destination_names)
        for i, item in enumerate(items):
            label = item.get("name") or f"item[{i}]"
            if not item.get("name"):
                problems.append(f"{rel}: {label} has no name")
            if not item.get("description"):
                problems.append(f"{rel}: {label} has no description")
            dest = item.get("destination")
            if dest and dest not in canonical:
                problems.append(
                    f"{rel}: {label} destination {dest!r} is not one of the 15 canonical "
                    "names in spec section 6.1"
                )
            key = slugify(item.get("name") or label)
            if key in seen:
                problems.append(f"{rel}: duplicate name {label!r}")
            seen.add(key)
    return problems
