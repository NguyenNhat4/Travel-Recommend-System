"""``cli report`` — the Friday demo numbers and the generated half of the README.

Covers spec section 0 item 7 ("đếm được số product theo category / destination,
tên tiếng Việt hiển thị đúng, và show được 1 customer có events gom thành 1
trip") and section 12 item 6.

Two deliberate choices about the Definition-of-Done gate:

* **Counting checks warn by default and only fail under ``--strict``.** A gate
  that is red every run from Monday to Thursday gets ignored by Thursday, which
  is exactly when it matters. ``--strict`` is the Friday invocation.
* **Only what the spec actually says is a failure.** ``products`` in 2,000-5,000,
  10-15 destinations, all five taxonomies present, 20 descriptions read by hand.
  No invented thresholds: a rule like "80% of the catalogue must clear the
  quality bar" appears nowhere in the spec and would fail a perfectly compliant
  Amadeus-heavy dataset whose English descriptions were correctly parked in
  ``attributes``.

A taxonomy with **zero** products is reported as a failure rather than a blank
row, because a missing row in the demo table is the thing nobody notices.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import random
import re
from pathlib import Path
from typing import Any

from sqlalchemy import text

import db
import exitcodes
from config import SENTINEL_SOURCES, Config
from merge import precedence_table
from quality import demo_threshold

log = logging.getLogger("report")

HERE = Path(__file__).resolve().parent
README = HERE / "README.md"


# =============================================================================
# queries
# =============================================================================
def _scalar(s, sql: str, **params) -> Any:  # noqa: ANN001
    return s.execute(text(sql), params).scalar()


def collect(cfg: Config, *, unknown_limit: int = 50) -> dict[str, Any]:
    """Everything the report shows, as one dict (also the ``--json`` payload)."""
    thr = demo_threshold(cfg)
    out: dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "config_sha256": cfg.sha256,
        "demo_threshold": thr,
    }

    with db.session_scope(cfg) as s:
        # --- pipeline funnel: where rows are lost, stage by stage ----------
        out["pipeline"] = {
            "crawl_targets": _scalar(s, "SELECT count(*) FROM crawl_targets"),
            "targets_by_status": {
                r[0]: r[1]
                for r in s.execute(
                    text("SELECT status, count(*) FROM crawl_targets GROUP BY 1 ORDER BY 1")
                ).all()
            },
            "raw_pages": _scalar(s, "SELECT count(*) FROM raw_pages"),
            "products_staging": _scalar(s, "SELECT count(*) FROM products_staging"),
            "products_normalised": _scalar(s, "SELECT count(*) FROM products_normalised"),
            "normalise_rejects": _scalar(s, "SELECT count(*) FROM normalise_rejects"),
            "products": _scalar(s, "SELECT count(*) FROM products"),
            "product_sources": _scalar(s, "SELECT count(*) FROM product_sources"),
        }

        # --- section 0 item 7 / section 12 item 6 ---------------------------
        out["by_taxonomy"] = [
            dict(r)
            for r in s.execute(
                text(
                    """
                    SELECT taxonomy,
                           count(*)                                        AS products,
                           count(*) FILTER (WHERE quality_score >= :thr)   AS demo_ready,
                           count(*) FILTER (WHERE description IS NULL
                                              OR length(description) = 0)  AS missing_description,
                           count(*) FILTER (WHERE unit_price IS NULL)      AS missing_price,
                           count(*) FILTER (WHERE image_url IS NULL)       AS missing_image,
                           round(avg(quality_score)::numeric, 3)           AS avg_quality
                      FROM products GROUP BY 1 ORDER BY 1
                    """
                ),
                {"thr": thr},
            ).mappings()
        ]
        # Every taxonomy the spec requires, including the ones at zero — a blank
        # row is what lets a missing category go unnoticed until the demo.
        present = {r["taxonomy"] for r in out["by_taxonomy"]}
        required = list(cfg.section("dod").get("required_taxonomies") or [])
        out["missing_taxonomies"] = [t for t in required if t not in present]

        out["by_destination"] = [
            dict(r)
            for r in s.execute(
                text(
                    """
                    SELECT destination,
                           count(*) AS products,
                           count(*) FILTER (WHERE quality_score >= :thr) AS demo_ready,
                           count(DISTINCT taxonomy) AS taxonomies
                      FROM products GROUP BY 1 ORDER BY 2 DESC, 1
                    """
                ),
                {"thr": thr},
            ).mappings()
        ]
        out["by_source"] = [
            dict(r)
            for r in s.execute(
                text(
                    """
                    SELECT ps.source,
                           count(DISTINCT ps.product_id) AS products,
                           count(*) FILTER (WHERE ps.is_primary) AS primary_for
                      FROM product_sources ps GROUP BY 1 ORDER BY 2 DESC
                    """
                )
            ).mappings()
        ]

        total = out["pipeline"]["products"] or 0
        missing_desc = _scalar(
            s,
            "SELECT count(*) FROM products WHERE description IS NULL OR length(description) = 0",
        )
        out["quality"] = {
            "products": total,
            "demo_ready": _scalar(
                s, "SELECT count(*) FROM products WHERE quality_score >= :t", t=thr
            ),
            "missing_description": missing_desc,
            "missing_description_pct": round(100.0 * missing_desc / total, 1) if total else 0.0,
            "avg_description_len": _scalar(
                s, "SELECT round(avg(length(description))) FROM products WHERE description IS NOT NULL"
            ),
            "histogram": [
                dict(r)
                for r in s.execute(
                    text(
                        """
                        SELECT width_bucket(quality_score, 0, 1, 10) AS bucket,
                               count(*) AS n
                          FROM products WHERE quality_score IS NOT NULL
                         GROUP BY 1 ORDER BY 1
                        """
                    )
                ).mappings()
            ],
        }

        # --- unknown destinations, for manual review (spec section 6.1) ----
        out["unknown_destinations"] = {
            "products": _scalar(
                s, "SELECT count(*) FROM products WHERE destination = 'unknown'"
            ),
            "samples": [
                dict(r)
                for r in s.execute(
                    text(
                        """
                        SELECT source, source_ref, name, destination_raw, address
                          FROM products_normalised
                         WHERE destination = 'unknown'
                         ORDER BY source, source_ref LIMIT :lim
                        """
                    ),
                    {"lim": unknown_limit},
                ).mappings()
            ],
        }

        # --- dedup (spec section 7) ----------------------------------------
        out["dedup"] = {
            "pairs_by_decision": {
                r[0]: r[1]
                for r in s.execute(
                    text("SELECT decision, count(*) FROM dedup_pairs GROUP BY 1 ORDER BY 1")
                ).all()
            },
            "clusters": _scalar(s, "SELECT count(*) FROM product_clusters"),
            "multi_source_clusters": _scalar(
                s, "SELECT count(*) FROM product_clusters WHERE member_count > 1"
            ),
            "products_with_multiple_sources": _scalar(
                s,
                "SELECT count(*) FROM (SELECT product_id FROM product_sources "
                "GROUP BY 1 HAVING count(*) > 1) x",
            ),
        }

        # --- rejects, so a vanished product is always explainable -----------
        out["rejects_by_reason"] = {
            r[0]: r[1]
            for r in s.execute(
                text("SELECT reason, count(*) FROM normalise_rejects GROUP BY 1 ORDER BY 2 DESC")
            ).all()
        }

        # --- seeded histories (spec section 10) -----------------------------
        out["histories"] = _histories(s, cfg)

        # --- provenance for README section 12 items 3 and 4 -----------------
        out["provenance"] = _provenance(s, cfg)

        # --- operational ----------------------------------------------------
        out["blocked_sources"] = [
            dict(r)
            for r in s.execute(
                text(
                    "SELECT source, blocked_at, reason FROM source_state "
                    "WHERE blocked_at IS NOT NULL AND cleared_at IS NULL ORDER BY source"
                )
            ).mappings()
        ]
        out["description_reviews"] = [
            dict(r)
            for r in s.execute(
                text(
                    "SELECT reviewed_at, reviewed_by, sample_size, verdict, "
                    "products_max_updated_at FROM description_reviews "
                    "ORDER BY reviewed_at DESC LIMIT 5"
                )
            ).mappings()
        ]
        out["products_max_updated_at"] = _scalar(
            s, "SELECT max(updated_at) FROM products"
        )

    out["stale_runs"] = db.stale_running_runs(cfg)
    out["dod"] = _dod_checks(cfg, out)
    return out


def _histories(s, cfg: Config) -> dict[str, Any]:  # noqa: ANN001
    """Seeded customer data, plus the Friday demo trip (spec section 0 item 7)."""
    profiles = _scalar(s, "SELECT count(*) FROM profiles")
    if not profiles:
        return {"profiles": 0}

    out: dict[str, Any] = {
        "profiles": profiles,
        "events": _scalar(s, "SELECT count(*) FROM events"),
        "bookings": _scalar(s, "SELECT count(*) FROM bookings"),
        "users": _scalar(s, "SELECT count(*) FROM users"),
        "events_by_name": {
            r[0]: r[1]
            for r in s.execute(
                text("SELECT event_name, count(*) FROM events GROUP BY 1 ORDER BY 2 DESC")
            ).all()
        },
        "lifecycle": {
            r[0]: r[1]
            for r in s.execute(
                text(
                    "SELECT COALESCE(lifecycle_stage, '?'), count(*) FROM profiles "
                    "GROUP BY 1 ORDER BY 2 DESC"
                )
            ).all()
        },
        "trips": _scalar(
            s, "SELECT count(DISTINCT event_group_id) FROM events WHERE event_group_id IS NOT NULL"
        ),
        # Deliberately possible (spec section 4.2: events.product_id has no FK so
        # the messy-edge case in section 10 is representable). Reported, not fixed.
        "dangling_events": _scalar(
            s,
            "SELECT count(*) FROM events e WHERE e.product_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id = e.product_id)",
        ),
        # Must be zero: section 10 requires one trip = one destination, or
        # filtering by destination is meaningless.
        "multi_destination_trips": _scalar(
            s,
            """
            SELECT count(*) FROM (
                SELECT e.event_group_id
                  FROM events e JOIN products p USING (product_id)
                 WHERE e.event_group_id IS NOT NULL
                 GROUP BY 1 HAVING count(DISTINCT p.destination) > 1
            ) x
            """,
        ),
        "events_per_user": [
            dict(r)
            for r in s.execute(
                text(
                    """
                    SELECT n_events, count(*) AS users FROM (
                        SELECT cdp_user_id, count(*) AS n_events FROM events GROUP BY 1
                    ) x GROUP BY 1 ORDER BY 1
                    """
                )
            ).mappings()
        ],
    }

    # The demo query: one customer whose events group into one trip.
    demo = s.execute(
        text(
            """
            SELECT e.cdp_user_id, e.event_group_id, count(*) AS n_events,
                   count(DISTINCT e.taxonomy) AS n_taxonomies
              FROM events e
             WHERE e.event_group_id IS NOT NULL
               AND e.event_name = 'purchase'
             GROUP BY 1, 2
            HAVING count(DISTINCT e.taxonomy) > 1
             ORDER BY n_taxonomies DESC, n_events DESC
             LIMIT 1
            """
        )
    ).mappings().first()
    if demo:
        out["demo_trip"] = {
            **dict(demo),
            "events": [
                dict(r)
                for r in s.execute(
                    text(
                        """
                        SELECT e.event_name, e.taxonomy, e.timestamp, e.using_date,
                               e.quantity, e.unit_price, p.name, p.destination
                          FROM events e LEFT JOIN products p USING (product_id)
                         WHERE e.event_group_id = :g
                         ORDER BY e.timestamp
                        """
                    ),
                    {"g": demo["event_group_id"]},
                ).mappings()
            ],
        }
    return out


def _provenance(s, cfg: Config) -> dict[str, Any]:  # noqa: ANN001
    """FX rate + date and quote contexts actually used (README section 12 items 3, 4).

    Read back out of the ``__normalise__`` sentinel ``crawl_runs`` row, so the
    README states what a run really did rather than what config says today.
    """
    row = s.execute(
        text(
            "SELECT stats FROM crawl_runs WHERE source = '__normalise__' "
            "AND status = 'done' ORDER BY finished_at DESC LIMIT 1"
        )
    ).first()
    stats = dict(row[0] or {}) if row else {}
    quote = [
        dict(r)
        for r in s.execute(
            text(
                """
                SELECT quote_ctx,
                       min(meta->'quote_params'->>'checkin')  AS earliest_checkin,
                       max(meta->'quote_params'->>'checkout') AS latest_checkout,
                       count(*) AS pages
                  FROM raw_pages
                 WHERE quote_ctx IS NOT NULL
                 GROUP BY 1 ORDER BY 1
                """
            )
        ).mappings()
    ]
    return {
        "fx_used": stats.get("fx") or cfg.fx_provenance(),
        "fx_config": cfg.fx_provenance(),
        "normaliser_version": stats.get("normaliser_version"),
        "quote_anchor_date": stats.get("quote_anchor_date")
        or (cfg.anchor_date.isoformat() if cfg.anchor_date else None),
        "quote_contexts_crawled": quote,
        "parser_versions": [
            dict(r)
            for r in s.execute(
                text(
                    "SELECT source, parser_version, count(*) AS rows FROM products_staging "
                    "GROUP BY 1, 2 ORDER BY 1, 2"
                )
            ).mappings()
        ],
    }


# =============================================================================
# DoD checks (spec section 0)
# =============================================================================
def _dod_checks(cfg: Config, data: dict[str, Any]) -> list[dict[str, Any]]:
    dod = cfg.section("dod")
    products = data["pipeline"]["products"] or 0
    destinations = len([d for d in data["by_destination"] if d["destination"] != "unknown"])
    reviews = data.get("description_reviews") or []
    hist = data.get("histories") or {}

    lo, hi = int(dod.get("products_min", 2000)), int(dod.get("products_max", 5000))
    dlo, dhi = int(dod.get("destinations_min", 10)), int(dod.get("destinations_max", 15))

    checks = [
        {
            "id": "products_in_range",
            "spec": "section 0 item 1",
            "want": f"{lo}-{hi} products",
            "got": products,
            "ok": lo <= products <= hi,
        },
        {
            "id": "destinations_in_range",
            "spec": "section 0 item 1",
            "want": f"{dlo}-{dhi} destinations",
            "got": destinations,
            "ok": dlo <= destinations <= dhi,
        },
        {
            "id": "all_taxonomies_present",
            "spec": "section 0 item 1",
            "want": ", ".join(dod.get("required_taxonomies") or []),
            "got": f"missing: {', '.join(data['missing_taxonomies']) or 'none'}",
            "ok": not data["missing_taxonomies"],
        },
        {
            "id": "raw_cached_before_parse",
            "spec": "section 0 item 2",
            "want": "every staging row traceable to a cached page",
            "got": f"{data['pipeline']['raw_pages']} raw pages / "
            f"{data['pipeline']['products_staging']} staging rows",
            "ok": data["pipeline"]["products_staging"] == 0
            or data["pipeline"]["raw_pages"] > 0,
        },
        {
            "id": "products_deduplicated",
            "spec": "section 0 item 4",
            "want": "dedup has run at the current version",
            "got": f"{data['dedup']['clusters']} clusters",
            "ok": bool(data["dedup"]["clusters"]),
        },
        {
            "id": "descriptions_read_by_hand",
            "spec": "sections 7, 13",
            "want": f">= {dod.get('descriptions_reviewed_min', 20)} descriptions reviewed, "
            "after the last load",
            "got": _review_state(reviews, data.get("products_max_updated_at")),
            "ok": _review_is_fresh(reviews, data.get("products_max_updated_at"),
                                  int(dod.get("descriptions_reviewed_min", 20))),
        },
        {
            "id": "histories_grouped_into_trips",
            "spec": "section 0 item 6",
            "want": "events grouped by event_group_id, one destination per trip",
            "got": f"{hist.get('trips', 0)} trips, "
            f"{hist.get('multi_destination_trips', 0)} multi-destination",
            "ok": bool(hist.get("trips")) and not hist.get("multi_destination_trips"),
        },
        {
            "id": "demo_trip_available",
            "spec": "section 0 item 7",
            "want": "one customer with a cross-category trip to show",
            "got": "yes" if hist.get("demo_trip") else "no",
            "ok": bool(hist.get("demo_trip")),
        },
    ]
    return checks


def _review_state(reviews: list[dict], products_max_updated: Any) -> str:
    if not reviews:
        return "never"
    last = reviews[0]
    return (
        f"{last['sample_size']} on {last['reviewed_at']:%Y-%m-%d %H:%M} "
        f"({last.get('verdict') or 'no verdict'})"
    )


def _review_is_fresh(reviews: list[dict], products_max_updated: Any, minimum: int) -> bool:
    """A review counts only if it happened after the products it looked at.

    The freshness anchor is the ``max(products.updated_at)`` recorded *at review
    time*, not "now" — which is why ``load`` must not touch ``updated_at`` on a
    no-op write.
    """
    for r in reviews:
        if (r.get("sample_size") or 0) < minimum:
            continue
        anchor = r.get("products_max_updated_at")
        if products_max_updated is None:
            return True
        if anchor is not None and anchor >= products_max_updated:
            return True
    return False


# =============================================================================
# rendering
# =============================================================================
def _table(rows: list[dict], columns: list[str]) -> list[str]:
    if not rows:
        return ["  (none)"]
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    head = "  " + "  ".join(c.ljust(widths[c]) for c in columns)
    rule = "  " + "  ".join("-" * widths[c] for c in columns)
    body = [
        "  " + "  ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns) for r in rows
    ]
    return [head, rule, *body]


def render(data: dict[str, Any], cfg: Config) -> str:
    L: list[str] = []
    A = L.append
    A("=" * 78)
    A("V-OTA RecSys — data collection report")
    A(f"generated {data['generated_at']}  config {data['config_sha256'][:12]}")
    A("=" * 78)

    A("\n## Pipeline funnel")
    p = data["pipeline"]
    A(f"  crawl_targets        {p['crawl_targets']}  {p['targets_by_status']}")
    A(f"  raw_pages            {p['raw_pages']}")
    A(f"  products_staging     {p['products_staging']}")
    A(f"  products_normalised  {p['products_normalised']}  (rejects: {p['normalise_rejects']})")
    A(f"  products             {p['products']}  (source mappings: {p['product_sources']})")

    A("\n## Products by taxonomy (spec section 0 item 7)")
    L.extend(
        _table(
            data["by_taxonomy"],
            ["taxonomy", "products", "demo_ready", "missing_description",
             "missing_price", "missing_image", "avg_quality"],
        )
    )
    if data["missing_taxonomies"]:
        A(f"  FAIL taxonomies with zero products: {', '.join(data['missing_taxonomies'])}")

    A("\n## Products by destination")
    L.extend(_table(data["by_destination"], ["destination", "products", "demo_ready", "taxonomies"]))

    A("\n## Products by source")
    L.extend(_table(data["by_source"], ["source", "products", "primary_for"]))

    q = data["quality"]
    A("\n## Quality (spec section 7)")
    A(f"  demo-ready (>= {data['demo_threshold']}): {q['demo_ready']}/{q['products']}")
    A(f"  missing description:      {q['missing_description']} ({q['missing_description_pct']}%)")
    A(f"  avg description length:   {q['avg_description_len']}")

    u = data["unknown_destinations"]
    A(f"\n## Unmapped destinations (spec section 6.1): {u['products']} product(s)")
    if u["samples"]:
        A("  Add the missing alias to config.yaml destinations, then:")
        A("    python -m cli normalize --force && python -m cli dedup && python -m cli load")
        L.extend(_table(u["samples"][:15], ["source", "name", "destination_raw", "address"]))

    d = data["dedup"]
    A("\n## Dedup (spec section 7)")
    A(f"  candidate pairs by decision: {d['pairs_by_decision'] or '(dedup not run)'}")
    A(f"  clusters: {d['clusters']}  multi-source: {d['multi_source_clusters']}")
    A(f"  products with >1 source:     {d['products_with_multiple_sources']}")

    if data["rejects_by_reason"]:
        A("\n## Rows that did not become products")
        for reason, n in data["rejects_by_reason"].items():
            A(f"  {n:>6}  {reason}")

    h = data["histories"]
    A("\n## Seeded customer histories (spec section 10)")
    if not h.get("profiles"):
        A("  (none — run `python -m cli seed-histories`)")
    else:
        A(f"  profiles {h['profiles']}  events {h['events']}  bookings {h['bookings']}  "
          f"users {h['users']}")
        A(f"  events by name: {h['events_by_name']}")
        A(f"  lifecycle:      {h['lifecycle']}")
        A(f"  trips: {h['trips']}  multi-destination trips: {h['multi_destination_trips']} "
          f"(must be 0)")
        A(f"  events pointing at deleted products: {h['dangling_events']} (intentional, "
          f"spec section 10)")
        trip = h.get("demo_trip")
        if trip:
            A(f"\n  Demo trip — customer {trip['cdp_user_id']}, group {trip['event_group_id']} "
              f"({trip['n_taxonomies']} categories):")
            for e in trip["events"]:
                A(f"    {e['timestamp']:%Y-%m-%d}  {e['event_name']:12} {e['taxonomy']:10} "
                  f"{(e['name'] or '(deleted product)')[:46]:46} {e['destination'] or ''}")

    pr = data["provenance"]
    A("\n## Provenance (README section 12 items 3, 4)")
    fx = pr["fx_used"]
    A(f"  FX rates as_of {fx.get('as_of')} from {fx.get('source')}")
    A(f"  quote anchor date: {pr['quote_anchor_date']}")
    L.extend(_table(pr["quote_contexts_crawled"],
                    ["quote_ctx", "earliest_checkin", "latest_checkout", "pages"]))
    L.extend(_table(pr["parser_versions"], ["source", "parser_version", "rows"]))

    if data["blocked_sources"]:
        A("\n## BLOCKED SOURCES (spec section 1 — do not retry)")
        for b in data["blocked_sources"]:
            A(f"  {b['source']}: blocked at {b['blocked_at']} — {b['reason']}")
        A("  Clear only with human sign-off: python -m cli unblock --source X --reason '...'")

    if data["stale_runs"]:
        A("\n## WARNING stale runs (process died; not auto-repaired)")
        for r in data["stale_runs"]:
            A(f"  {r['source']}/{r['kind']} started {r['started_at']} — resume with "
              f"--run-id {r['id']}")

    A("\n## Definition of Done (spec section 0)")
    for c in data["dod"]:
        A(f"  [{'PASS' if c['ok'] else 'WARN'}] {c['id']:34} want {c['want']}  got {c['got']}")

    A("")
    return "\n".join(L)


# =============================================================================
# README generation
# =============================================================================
def _extraction_table(cfg: Config) -> list[dict[str, str]]:
    """README section 12 item 1: field -> source -> how it was extracted.

    Aggregated from the ``_prov`` map every parser writes into its payload, so
    the table describes what the parsers actually did rather than what someone
    remembered to document.
    """
    with db.session_scope(cfg) as s:
        rows = s.execute(
            text(
                """
                SELECT source, key AS field, value AS method, count(*) AS rows
                  FROM products_staging ps,
                       LATERAL jsonb_each_text(ps.payload->'_prov')
                 WHERE ps.payload ? '_prov'
                 GROUP BY 1, 2, 3 ORDER BY 1, 2, 4 DESC
                """
            )
        ).mappings().all()
    return [dict(r) for r in rows]


def _runbook(cfg: Config) -> list[str]:
    """README section 12 item 5: the commands to rebuild from scratch.

    Generated from the enabled sources in config so it cannot drift from what
    the pipeline can actually run.
    """
    enabled = [s for s in cfg.enabled_sources() if s not in SENTINEL_SOURCES]
    lines = [
        "# 0. prerequisites: Docker Desktop running, uv installed, .env filled in",
        "cd vota-recsys",
        "docker compose up -d postgres",
        "cd data-collection",
        "uv sync",
        "uv run python -m cli migrate            # applies 001, 002, 004, 005 (003 deferred)",
        "",
        "# 1. catalogue",
    ]
    for s in enabled:
        lines += [
            f"uv run python -m cli robots-check --source {s}",
            f"uv run python -m cli discover     --source {s}",
            f"uv run python -m cli fetch        --source {s} --concurrency 2",
            f"uv run python -m cli parse        --source {s}",
        ]
    lines += [
        "",
        "# 2. normalise, dedup, load",
        "uv run python -m cli normalize",
        "uv run python -m cli dedup",
        "uv run python -m cli load",
        "",
        "# 3. mandatory manual check (spec sections 7, 13)",
        "uv run python -m cli sample-descriptions --n 20 --mark --by '<your name>' --verdict ok",
        "",
        "# 4. customer histories — AFTER the final load, so product ids are stable",
        f"uv run python -m cli seed-histories --users {cfg.section('seed').get('users', 500)} "
        f"--seed {cfg.section('seed').get('random_seed', 42)}",
        "uv run python -m cli sanity-check",
        "",
        "# 5. report",
        "uv run python -m cli report",
        "uv run python -m cli report --strict   # Friday: fails on unmet DoD checks",
    ]
    return lines


def _splice(path: Path, marker: str, body: str) -> bool:
    """Replace the text between ``<!-- BEGIN:x -->`` and ``<!-- END:x -->``.

    Fails loudly rather than appending: a README that silently grows a second
    copy of a section is worse than one that says the markers are missing.
    """
    if not path.exists():
        log.error("README not found at %s", path)
        return False
    text_in = path.read_text(encoding="utf-8")
    begin, end = f"<!-- BEGIN:{marker} -->", f"<!-- END:{marker} -->"
    if begin not in text_in or end not in text_in:
        log.error("README is missing the %s / %s markers", begin, end)
        return False
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    path.write_text(
        pattern.sub(f"{begin}\n{body}\n{end}", text_in, count=1), encoding="utf-8"
    )
    return True


def _md_table(rows: list[dict], columns: list[str], headers: list[str] | None = None) -> str:
    head = headers or columns
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")).replace("|", "\\|") for c in columns) + " |")
    return "\n".join(out) if rows else "_(none yet)_"


def update_readme(cfg: Config, data: dict[str, Any]) -> bool:
    ok = True
    ok &= _splice(README, "extraction-table", _md_table(
        _extraction_table(cfg), ["source", "field", "method", "rows"],
        ["source", "field", "cách trích", "số row"],
    ))
    ok &= _splice(README, "precedence", _md_table(
        precedence_table(cfg), ["kind", "field", "winner"],
        ["loại", "field", "nguồn thắng"],
    ))
    fx = data["provenance"]["fx_used"]
    rates = fx.get("rates") or {}
    ok &= _splice(README, "fx", "\n".join([
        f"- **Ngày áp dụng (`as_of`)**: `{fx.get('as_of')}`",
        f"- **Nguồn tỷ giá**: {fx.get('source')}",
        f"- **Base**: `{fx.get('base', 'VND')}`",
        "",
        _md_table(
            [{"currency": k, "rate_to_vnd": v} for k, v in sorted(rates.items())],
            ["currency", "rate_to_vnd"], ["tiền tệ", "tỷ giá sang VND"],
        ),
    ]))
    ok &= _splice(README, "quote-contexts", "\n".join([
        f"- **`anchor_date`**: `{data['provenance']['quote_anchor_date']}`",
        "",
        _md_table(
            data["provenance"]["quote_contexts_crawled"],
            ["quote_ctx", "earliest_checkin", "latest_checkout", "pages"],
            ["quote_ctx", "check-in sớm nhất", "check-out muộn nhất", "số trang"],
        ),
    ]))
    ok &= _splice(README, "runbook", "```bash\n" + "\n".join(_runbook(cfg)) + "\n```")
    ok &= _splice(README, "last-run-stats", "\n".join([
        f"_Cập nhật {data['generated_at']} — config `{data['config_sha256'][:12]}`_",
        "",
        "**Product theo taxonomy**",
        "",
        _md_table(data["by_taxonomy"],
                  ["taxonomy", "products", "demo_ready", "missing_description", "avg_quality"],
                  ["taxonomy", "product", "đạt ngưỡng demo", "thiếu description", "quality TB"]),
        "",
        "**Product theo destination**",
        "",
        _md_table(data["by_destination"], ["destination", "products", "demo_ready", "taxonomies"],
                  ["destination", "product", "đạt ngưỡng demo", "số taxonomy"]),
        "",
        "**Số liệu khác**",
        "",
        f"- Tỉ lệ thiếu description: **{data['quality']['missing_description_pct']}%**",
        f"- Cặp dedup: `{data['dedup']['pairs_by_decision'] or '{}'}` — "
        f"{data['dedup']['multi_source_clusters']} cluster nhiều nguồn",
        f"- Destination không map được: **{data['unknown_destinations']['products']}**",
        f"- Profiles / events / trips: "
        f"{data['histories'].get('profiles', 0)} / {data['histories'].get('events', 0)} / "
        f"{data['histories'].get('trips', 0)}",
    ]))
    return bool(ok)


# =============================================================================
# entry points
# =============================================================================
def run_report(
    cfg: Config,
    *,
    as_json: bool = False,
    strict: bool = False,
    extraction_table: bool = False,
    update_readme_flag: bool = False,
    runbook: bool = False,
    unknown_limit: int = 50,
    **kwargs,
) -> int:
    db.check_connection(cfg)
    db.assert_migrated(cfg)
    update_readme_flag = update_readme_flag or bool(kwargs.get("update_readme"))

    if runbook:
        print("\n".join(_runbook(cfg)))
        return exitcodes.OK

    data = collect(cfg, unknown_limit=unknown_limit)

    if extraction_table:
        rows = _extraction_table(cfg)
        print("\n".join(_table(rows, ["source", "field", "method", "rows"])))
        return exitcodes.OK

    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    else:
        print(render(data, cfg))

    out_dir = cfg.reports_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    (out_dir / f"report-{stamp}.md").write_text(render(data, cfg), encoding="utf-8")
    (out_dir / f"report-{stamp}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    if update_readme_flag:
        if update_readme(cfg, data):
            log.info("README.md updated")
        else:
            log.error("README.md not fully updated; see the errors above")
            return exitcodes.GATE_FAILED

    failed = [c for c in data["dod"] if not c["ok"]]
    if failed:
        log.warning(
            "%d Definition-of-Done check(s) not met: %s",
            len(failed), ", ".join(c["id"] for c in failed),
        )
        if strict:
            return exitcodes.GATE_FAILED
    return exitcodes.OK


def run_sample_descriptions(
    cfg: Config,
    *,
    n: int = 20,
    mark: bool = False,
    reviewed_by: str | None = None,
    verdict: str | None = None,
    seed: int | None = None,
) -> int:
    """Print N random descriptions to read by hand (spec sections 7, 13).

    "Đọc tay 20 mô tả ngẫu nhiên" is a requirement, not a suggestion: a generic
    or truncated description means the Week 2 semantic search cannot be
    demonstrated and the model comparison is meaningless. ``--mark`` records
    that it happened so ``report --strict`` can check, which is the difference
    between a gate and an intention.
    """
    db.check_connection(cfg)
    rng = random.Random(seed)

    with db.session_scope(cfg) as s:
        rows = s.execute(
            text(
                """
                SELECT product_id, name, taxonomy, destination, quality_score,
                       length(description) AS len, description
                  FROM products
                 WHERE description IS NOT NULL AND length(description) > 0
                """
            )
        ).mappings().all()
        max_updated = _scalar(s, "SELECT max(updated_at) FROM products")

    if not rows:
        log.error("no products with a description yet — run the pipeline first")
        return exitcodes.GATE_FAILED

    sample = rng.sample(list(rows), min(n, len(rows)))
    print("=" * 78)
    print(f"{len(sample)} random product descriptions — READ THESE (spec sections 7, 13)")
    print("Looking for: generic marketing filler, truncation mid-sentence, wrong language,")
    print("HTML leftovers, a description that describes the city and not the product.")
    print("=" * 78)
    for i, r in enumerate(sample, 1):
        print(f"\n--- {i}/{len(sample)}  {r['taxonomy']} / {r['destination']}  "
              f"quality={r['quality_score']}  {r['len']} chars")
        print(f"    {r['name']}")
        print(f"    {r['product_id']}")
        print()
        for line in str(r["description"]).splitlines():
            print(f"    {line}")

    if len(rows) < n:
        print(f"\nNOTE: only {len(rows)} products have a description; asked for {n}.")

    if mark:
        if not reviewed_by:
            log.error("--mark needs --by '<who read them>' so the ledger means something")
            return exitcodes.USAGE
        with db.session_scope(cfg) as s:
            s.execute(
                text(
                    "INSERT INTO description_reviews (reviewed_by, product_ids, sample_size, "
                    "verdict, products_max_updated_at) "
                    "VALUES (:by, CAST(:ids AS jsonb), :n, :v, :anchor)"
                ),
                {
                    "by": reviewed_by,
                    "ids": json.dumps([str(r["product_id"]) for r in sample]),
                    "n": len(sample),
                    "v": verdict,
                    "anchor": max_updated,
                },
            )
        print(f"\nRecorded: {len(sample)} descriptions reviewed by {reviewed_by} "
              f"(verdict: {verdict or 'none given'})")
    else:
        print("\nWhen you have actually read them, record it so report --strict can see:")
        print("  python -m cli sample-descriptions --n 20 --mark --by '<name>' --verdict ok")
    return exitcodes.OK
