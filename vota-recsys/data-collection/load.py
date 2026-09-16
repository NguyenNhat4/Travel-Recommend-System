"""Clusters -> ``products`` + ``product_sources``. The DoD artefact (spec section 0 item 1).

Idempotency is the whole job here, and it has one non-obvious rule.

``product_id`` resolution order:

1. Look up ``product_sources`` by ``(source, source_ref)`` for **every** member
   of the cluster. If any member is already mapped, reuse that ``product_id``.
2. Only a cluster with no mapped member at all mints a new
   ``uuid5(NS_VOTA_PRODUCT, cluster_key)``.

Step 1 is what makes the daily fix loop survivable. ``dedup`` blocks by
destination, so editing the destination alias map changes cluster membership,
which changes ``cluster_key``, which under a pure ``uuid5`` scheme would mint a
brand-new ``product_id`` for a product that already exists — orphaning every
seeded event that points at it. And that loop
(``report -> edit aliases -> normalize --force -> dedup -> load -> report``) is
the normal way this dataset gets fixed, not an edge case.

The upsert is also conditional on the row actually differing:

    ON CONFLICT (product_id) DO UPDATE SET ..., updated_at = now()
     WHERE (products.* IS DISTINCT FROM EXCLUDED.*)

Without that ``WHERE``, ``updated_at`` advances on every ``load`` even when
nothing changed. That breaks the "read 20 descriptions" freshness gate — it
compares the review timestamp against ``max(products.updated_at)`` — so a review
that genuinely happened would read as stale on Friday, at the demo.

Nothing here adds a column to ``products``: ``cluster_key`` lives in
``product_load_meta``, because spec section 4.2 is a field-for-field CDP mirror.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import text

import db
import exitcodes
from config import Config
from ids import product_uuid
from merge import merge_cluster, project
from models import PRODUCTS_COLUMNS
from quality import demo_threshold, quality_score

log = logging.getLogger("load")

_MEMBER_FIELDS = (
    "source", "source_ref", "page_kind", "parent_source_ref", "name", "taxonomy",
    "destination", "description", "attributes", "unit_price", "currency", "available",
    "available_from", "available_to", "image_url", "images", "latitude", "longitude",
    "quality_score", "name_normalized", "address", "phone", "star_rating", "brand",
    "quote_ctx",
)


def _member_columns(prefix: str) -> str:
    """Qualified select list. ``source`` and ``source_ref`` exist on both
    ``product_cluster_members`` and ``products_normalised``, so an unqualified
    list is ambiguous in the join."""
    return ", ".join(f"{prefix}.{f}" for f in _MEMBER_FIELDS)


def run_load(
    cfg: Config,
    *,
    max_products_per_source: int | None = None,
    dry_run: bool = False,
    argv: list[str] | None = None,
) -> int:
    db.check_connection(cfg)
    db.assert_migrated(cfg)
    norm_version = str(cfg.section("normalise").get("normaliser_version", "1.0.0"))
    dedup_version = str(cfg.section("dedup").get("dedup_version", "1.0.0"))

    clusters = _clusters(cfg, dedup_version, norm_version)
    if not clusters:
        log.error(
            "nothing to load: products_normalised is empty at normaliser_version %s. "
            "Run `python -m cli normalize` first.", norm_version,
        )
        return exitcodes.GATE_FAILED

    inserted = updated = unchanged = skipped_parent = rejected = 0
    per_source: dict[str, int] = {}

    with db.command_lock(cfg, "load"):
        with db.crawl_run("__load__", "load", cfg, argv=argv) as run:
            # Clear this stage's previous verdicts first. A reject left over
            # from an earlier run that now succeeds would keep showing up in
            # `report` as a lost product, which is exactly the signal that
            # table exists to give — so it has to mean "this run".
            with db.session_scope(cfg) as s:
                s.execute(text("DELETE FROM normalise_rejects WHERE reason = 'load'"))
            run.note("dedup_version", dedup_version)
            run.note("normaliser_version", norm_version)
            run.note("demo_threshold", demo_threshold(cfg))

            for cluster_key, members in clusters.items():
                # A property row is a merge parent, not a sellable product: its
                # fields were folded onto its rooms during normalise. Loading it
                # would add a priceless phantom hotel that duplicates its own
                # rooms and inflates the section 0.1 count with non-products.
                members = [m for m in members if m.get("page_kind") != "property"]
                if not members:
                    skipped_parent += 1
                    continue

                cap_hit = False
                for m in members:
                    if max_products_per_source is not None:
                        if per_source.get(m["source"], 0) >= max_products_per_source:
                            cap_hit = True
                if cap_hit:
                    continue

                try:
                    columns, attributes, winners = merge_cluster([dict(m) for m in members], cfg)
                    row, problems = project(columns, attributes)
                except Exception as exc:  # noqa: BLE001 - one cluster must not stop the load
                    log.exception("merge failed for cluster %s", cluster_key)
                    _reject_cluster(cfg, cluster_key, members, f"merge: {exc}")
                    rejected += 1
                    continue

                if problems:
                    _reject_cluster(cfg, cluster_key, members, "; ".join(problems))
                    rejected += 1
                    continue

                row["quality_score"] = quality_score(row, cfg)[0]
                product_id = _resolve_product_id(cfg, cluster_key, members)

                if dry_run:
                    print(
                        f"{row['taxonomy']:10} {row['destination']:16} "
                        f"q={row['quality_score']:.2f} {product_id} {row['name']}"
                    )
                    inserted += 1
                    continue

                outcome = _upsert_product(cfg, product_id, row, cluster_key, dedup_version, cfg)
                if outcome == "inserted":
                    inserted += 1
                elif outcome == "updated":
                    updated += 1
                else:
                    unchanged += 1

                _upsert_sources(cfg, product_id, members)
                _write_merge_log(cfg, product_id, winners, dedup_version)
                for m in members:
                    per_source[m["source"]] = per_source.get(m["source"], 0) + 1

            run.set("clusters", len(clusters))
            run.set("inserted", inserted)
            run.set("updated", updated)
            run.set("unchanged", unchanged)
            run.set("skipped_merge_parents", skipped_parent)
            run.set("rejected", rejected)
            run.set("per_source", per_source)

    log.info(
        "load done: inserted=%d updated=%d unchanged=%d merge-parents-skipped=%d rejected=%d",
        inserted, updated, unchanged, skipped_parent, rejected,
    )
    if inserted + updated + unchanged == 0:
        return exitcodes.GATE_FAILED
    return exitcodes.OK


# =============================================================================
# clusters
# =============================================================================
def _clusters(cfg: Config, dedup_version: str, norm_version: str) -> dict[str, list[dict]]:
    """Cluster members for this dedup version.

    Falls back to one-member clusters when ``dedup`` has not run. The spec makes
    every command independently re-runnable (section 2), so ``load`` right after
    ``normalize`` should produce products rather than an unexplained empty
    result — it just produces un-deduplicated ones, and says so.
    """
    with db.session_scope(cfg) as s:
        rows = s.execute(
            text(
                f"""
                SELECT m.cluster_key, m.is_primary, m.match_score, {_member_columns('pn')}
                  FROM product_cluster_members m
                  JOIN products_normalised pn
                    ON pn.source = m.source AND pn.source_ref = m.source_ref
                   AND pn.normaliser_version = :nv
                 WHERE m.dedup_version = :dv
                 ORDER BY m.cluster_key, m.source_ref
                """
            ),
            {"dv": dedup_version, "nv": norm_version},
        ).mappings().all()

        if rows:
            out: dict[str, list[dict]] = {}
            for r in rows:
                out.setdefault(r["cluster_key"], []).append(dict(r))
            log.info("loading %d dedup cluster(s) at version %s", len(out), dedup_version)
            return out

        log.warning(
            "no dedup clusters at version %s — treating every normalised row as its own "
            "product. Run `python -m cli dedup` to merge duplicates across sources.",
            dedup_version,
        )
        singles = s.execute(
            text(
                f"SELECT pn.source_ref AS cluster_key, true AS is_primary, "
                f"NULL::real AS match_score, {_member_columns('pn')} "
                f"FROM products_normalised pn WHERE pn.normaliser_version = :nv "
                f"ORDER BY pn.source_ref"
            ),
            {"nv": norm_version},
        ).mappings().all()
    return {r["cluster_key"]: [dict(r)] for r in singles}


# =============================================================================
# identity
# =============================================================================
def _resolve_product_id(cfg: Config, cluster_key: str, members: list[dict]) -> uuid.UUID:
    """See the module docstring — an existing mapping always wins."""
    refs = [(m["source"], m["source_ref"]) for m in members]
    with db.session_scope(cfg) as s:
        for source, ref in refs:
            row = s.execute(
                text(
                    "SELECT product_id FROM product_sources "
                    "WHERE source = :s AND source_ref = :r"
                ),
                {"s": source, "r": ref},
            ).first()
            if row:
                return row[0] if isinstance(row[0], uuid.UUID) else uuid.UUID(str(row[0]))
        row = s.execute(
            text("SELECT product_id FROM product_load_meta WHERE cluster_key = :k"),
            {"k": cluster_key},
        ).first()
        if row:
            return row[0] if isinstance(row[0], uuid.UUID) else uuid.UUID(str(row[0]))
    return product_uuid(cluster_key)


# =============================================================================
# writes
# =============================================================================
_INSERT_COLUMNS = tuple(
    c for c in PRODUCTS_COLUMNS if c not in ("product_id", "created_at", "updated_at")
)

_UPSERT_PRODUCT = text(
    f"""
    INSERT INTO products (product_id, {", ".join(_INSERT_COLUMNS)})
    VALUES (
        :product_id, :name, :taxonomy, :destination, :description,
        CAST(:attributes AS jsonb), :unit_price, :currency, :available,
        :available_from, :available_to, :image_url, :source_ref,
        :latitude, :longitude, CAST(:images AS jsonb), :quality_score
    )
    ON CONFLICT (product_id) DO UPDATE SET
        name = EXCLUDED.name,
        taxonomy = EXCLUDED.taxonomy,
        destination = EXCLUDED.destination,
        description = EXCLUDED.description,
        attributes = EXCLUDED.attributes,
        unit_price = EXCLUDED.unit_price,
        currency = EXCLUDED.currency,
        available = EXCLUDED.available,
        available_from = EXCLUDED.available_from,
        available_to = EXCLUDED.available_to,
        image_url = EXCLUDED.image_url,
        source_ref = EXCLUDED.source_ref,
        latitude = EXCLUDED.latitude,
        longitude = EXCLUDED.longitude,
        images = EXCLUDED.images,
        quality_score = EXCLUDED.quality_score,
        updated_at = now()
      WHERE (
        products.name, products.taxonomy, products.destination, products.description,
        products.attributes, products.unit_price, products.currency, products.available,
        products.available_from, products.available_to, products.image_url,
        products.source_ref, products.latitude, products.longitude, products.images,
        products.quality_score
      ) IS DISTINCT FROM (
        EXCLUDED.name, EXCLUDED.taxonomy, EXCLUDED.destination, EXCLUDED.description,
        EXCLUDED.attributes, EXCLUDED.unit_price, EXCLUDED.currency, EXCLUDED.available,
        EXCLUDED.available_from, EXCLUDED.available_to, EXCLUDED.image_url,
        EXCLUDED.source_ref, EXCLUDED.latitude, EXCLUDED.longitude, EXCLUDED.images,
        EXCLUDED.quality_score
      )
    RETURNING (xmax = 0) AS was_insert
    """
)


def _upsert_product(
    cfg: Config,
    product_id: uuid.UUID,
    row: dict[str, Any],
    cluster_key: str,
    dedup_version: str,
    cfg_for_meta: Config,
) -> str:
    """Insert or update one product. Returns ``inserted|updated|unchanged``.

    ``xmax = 0`` distinguishes an insert from an update in the RETURNING clause;
    no row returned at all means the conditional WHERE suppressed a no-op write,
    which is the ``unchanged`` case the idempotency gate checks for.
    """
    params = dict(row)
    params["product_id"] = str(product_id)
    params["attributes"] = json.dumps(row.get("attributes") or {}, ensure_ascii=False, default=str)
    params["images"] = json.dumps(row.get("images") or [], ensure_ascii=False)
    with db.session_scope(cfg) as s:
        res = s.execute(_UPSERT_PRODUCT, params).first()
        s.execute(
            text(
                """
                INSERT INTO product_load_meta (product_id, cluster_key, dedup_version, meta)
                VALUES (:pid, :ck, :dv, CAST(:meta AS jsonb))
                ON CONFLICT (product_id) DO UPDATE SET
                    cluster_key = EXCLUDED.cluster_key,
                    dedup_version = EXCLUDED.dedup_version,
                    meta = EXCLUDED.meta,
                    loaded_at = now()
                """
            ),
            {
                "pid": str(product_id),
                "ck": cluster_key,
                "dv": dedup_version,
                # products_demo reads demo_threshold from here so the 0.5 is not
                # duplicated as a SQL literal in the view.
                "meta": json.dumps({"demo_threshold": demo_threshold(cfg_for_meta)}),
            },
        )
    if res is None:
        return "unchanged"
    return "inserted" if res[0] else "updated"


def _upsert_sources(cfg: Config, product_id: uuid.UUID, members: list[dict]) -> None:
    """Map every member onto the product (spec section 7 ``product_sources``).

    ``PRIMARY KEY (source, source_ref)`` is the natural key, so a member that
    moves to a different cluster is re-pointed rather than duplicated.
    """
    with db.session_scope(cfg) as s:
        for m in members:
            s.execute(
                text(
                    """
                    INSERT INTO product_sources (product_id, source, source_ref, is_primary, match_score)
                    VALUES (:pid, :src, :ref, :prim, :score)
                    ON CONFLICT (source, source_ref) DO UPDATE SET
                        product_id = EXCLUDED.product_id,
                        is_primary = EXCLUDED.is_primary,
                        match_score = EXCLUDED.match_score
                    """
                ),
                {
                    "pid": str(product_id),
                    "src": m["source"],
                    "ref": m["source_ref"],
                    "prim": bool(m.get("is_primary")),
                    "score": m.get("match_score"),
                },
            )


def _write_merge_log(
    cfg: Config, product_id: uuid.UUID, winners: list[dict], dedup_version: str
) -> None:
    with db.session_scope(cfg) as s:
        for w in winners:
            s.execute(
                text(
                    """
                    INSERT INTO product_merge_log
                           (product_id, field, winning_source, winning_ref, strategy, dedup_version)
                    VALUES (:pid, :f, :ws, :wr, :st, :dv)
                    ON CONFLICT (product_id, field) DO UPDATE SET
                        winning_source = EXCLUDED.winning_source,
                        winning_ref = EXCLUDED.winning_ref,
                        strategy = EXCLUDED.strategy,
                        dedup_version = EXCLUDED.dedup_version
                    """
                ),
                {
                    "pid": str(product_id),
                    "f": w["field"],
                    "ws": w["winning_source"],
                    "wr": w["winning_ref"],
                    "st": w["strategy"],
                    "dv": dedup_version,
                },
            )


def _reject_cluster(cfg: Config, cluster_key: str, members: list[dict], reason: str) -> None:
    """Record why a cluster produced no product.

    Same reasoning as ``normalise_rejects``: a product that silently disappears
    between stages is the hardest failure to diagnose, so the gap is always
    explainable from the database.
    """
    primary = members[0] if members else {}
    with db.session_scope(cfg) as s:
        s.execute(
            text(
                "INSERT INTO normalise_rejects (source, source_ref, staging_id, "
                "normaliser_version, reason, detail, payload_excerpt) "
                "VALUES (:s, :ref, NULL, :v, 'load', :d, CAST(:p AS jsonb))"
            ),
            {
                "s": primary.get("source", "?"),
                "ref": cluster_key,
                "v": str(cfg.section("normalise").get("normaliser_version", "1.0.0")),
                "d": reason[:2000],
                "p": json.dumps(
                    {
                        "cluster_key": cluster_key,
                        "members": [m.get("source_ref") for m in members],
                    },
                    ensure_ascii=False,
                ),
            },
        )
    log.warning("cluster %s not loaded: %s", cluster_key, reason)
