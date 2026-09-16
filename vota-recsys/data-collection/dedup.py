"""Cross-source deduplication (spec section 7).

The same resort appears on vinpearl, booking and agoda with different names,
descriptions and prices. The algorithm the spec specifies, and this implements:

1. Block by ``destination``.
2. A pair is a candidate if coordinates are within 150 m, **or**
   ``similarity(name_normalized) >= 0.82`` (pg_trgm) with ``starRating``
   differing by at most 1.
3. Score the pair; merge above the threshold, and write the 0.70-0.82 grey zone
   to ``dedup_review.csv`` for a human to read.

Three implementation decisions worth stating:

**``similarity()`` for both the candidate test and the score.** The textbook
version of this generates candidates with the indexable ``%`` operator, since a
trgm GIN index accelerates ``%`` and ``<->`` but not the ``similarity()``
function. That is not what this does, deliberately: psycopg's server-side
parameter binding does not reliably pass a literal ``%`` through to Postgres,
and the workarounds are all fragile in a way a dedup rule should not be. At this
scale it costs nothing — pairs are blocked by ``destination`` first, so even a
5,000-product catalogue is a few hundred rows per block. The GIN index in
migration 005 stays for when the catalogue is large enough to need it.

**Union by smaller root key.** Transitive matches are real: A~B and B~C must end
up in one cluster. A plain union-find whose root depends on edge order would
give a different ``cluster_key`` on every run, and since ``load`` derives
``product_id`` from ``cluster_key`` for new clusters, the catalogue would churn.
Unioning toward the smaller key makes the root ``min(member_key)`` regardless of
the order edges arrive, so re-running dedup is a no-op.

**Grain and taxonomy are not crossed.** A ``page_kind='property'`` row must not
merge with a ``'room'`` row (different grain — one hotel vs one room type), and
a hotel must not merge with a flight. Both are config flags rather than
hardcoded, but both default to off.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text

import db
import exitcodes
from config import Config

log = logging.getLogger("dedup")


# =============================================================================
# union-find
# =============================================================================
class UnionFind:
    """Union by **smaller root key**, not by rank or size.

    Consequence: a component's root is always ``min(member_key)`` whatever order
    the edges arrive in, so ``cluster_key`` — and therefore the ``product_id``
    minted from it — is identical on every re-run. Union-by-rank would be
    marginally faster and would make the output order-dependent, which is the
    wrong trade here.
    """

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        # Path compression, iterative so a long chain cannot blow the stack.
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        lo, hi = (ra, rb) if ra < rb else (rb, ra)
        self.parent[hi] = lo

    def groups(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for node in list(self.parent):
            out.setdefault(self.find(node), []).append(node)
        for members in out.values():
            members.sort()
        return out


# =============================================================================
# scoring
# =============================================================================
def match_score(pair: dict[str, Any], cfg: Config) -> float:
    """Weighted score over the section 5.3 dedup fields.

    Each component contributes only when it has evidence; the score is the
    weighted mean over the components that do. Scoring an absent component as 0
    would punish a pair for missing data rather than for disagreeing, and most
    pairs are missing something.
    """
    weights = cfg.section("dedup").get("match_score_weights") or {}
    dist_threshold = float(cfg.section("dedup").get("distance_m_threshold", 150))

    parts: list[tuple[float, float]] = []

    sim = pair.get("name_similarity")
    if sim is not None:
        parts.append((float(weights.get("name_similarity", 0.45)), float(sim)))

    distance = pair.get("distance_m")
    if distance is not None:
        # 1.0 at zero distance, 0.0 at twice the threshold.
        closeness = max(0.0, 1.0 - float(distance) / (dist_threshold * 2))
        parts.append((float(weights.get("distance", 0.25)), closeness))

    star_delta = pair.get("star_delta")
    if star_delta is not None:
        parts.append((float(weights.get("star_rating", 0.10)), 1.0 if abs(float(star_delta)) < 0.5 else 0.5))

    for key, weight_key in (
        ("brand_match", "brand"),
        ("address_match", "address"),
        ("phone_match", "phone"),
    ):
        value = pair.get(key)
        if value is not None:
            parts.append((float(weights.get(weight_key, 0.05)), 1.0 if value else 0.0))

    total_weight = sum(w for w, _ in parts)
    if total_weight <= 0:
        return 0.0
    return round(sum(w * v for w, v in parts) / total_weight, 4)


# =============================================================================
# candidate pairs
# =============================================================================
_CANDIDATES_SQL = """
SELECT a.source        AS a_source,
       a.source_ref    AS a_ref,
       b.source        AS b_source,
       b.source_ref    AS b_ref,
       a.destination   AS destination,
       similarity(a.name_normalized, b.name_normalized) AS name_similarity,
       crawl_distance_m(a.latitude, a.longitude, b.latitude, b.longitude) AS distance_m,
       CASE WHEN a.star_rating IS NOT NULL AND b.star_rating IS NOT NULL
            THEN abs(a.star_rating - b.star_rating) END AS star_delta,
       CASE WHEN a.brand IS NOT NULL AND b.brand IS NOT NULL
            THEN (lower(a.brand) = lower(b.brand)) END AS brand_match,
       CASE WHEN a.address IS NOT NULL AND b.address IS NOT NULL
            THEN (similarity(a.address, b.address) > 0.6) END AS address_match,
       CASE WHEN a.phone IS NOT NULL AND b.phone IS NOT NULL
            THEN (a.phone = b.phone) END AS phone_match,
       a.page_kind AS a_grain, b.page_kind AS b_grain,
       a.taxonomy  AS a_taxonomy, b.taxonomy AS b_taxonomy,
       a.name AS a_name, b.name AS b_name,
       a.unit_price AS a_price, b.unit_price AS b_price,
       a.address AS a_address, b.address AS b_address,
       a.phone AS a_phone, b.phone AS b_phone
  FROM products_normalised a
  JOIN products_normalised b
    ON a.destination = b.destination
   AND a.normaliser_version = b.normaliser_version
   -- One ordered pair per unordered pair, and never a row with itself.
   AND (a.source, a.source_ref) < (b.source, b.source_ref)
   AND (
         -- Name similar enough to be worth scoring...
         similarity(a.name_normalized, b.name_normalized) >= :grey_low
         -- ...or close enough on the ground that the name does not matter.
         OR (a.latitude IS NOT NULL AND b.latitude IS NOT NULL
             AND crawl_distance_m(a.latitude, a.longitude, b.latitude, b.longitude) < :dist)
       )
 WHERE a.normaliser_version = :nv
   AND a.destination <> 'unknown'
"""


def _candidate_pairs(
    cfg: Config, *, destination: str | None, taxonomy: str | None
) -> list[dict[str, Any]]:
    d = cfg.section("dedup")
    sql = _CANDIDATES_SQL
    params: dict[str, Any] = {
        "nv": str(cfg.section("normalise").get("normaliser_version", "1.0.0")),
        "dist": float(d.get("distance_m_threshold", 150)),
    }
    if destination:
        sql += " AND a.destination = :dest"
        params["dest"] = destination
    if taxonomy:
        sql += " AND a.taxonomy = :tax AND b.taxonomy = :tax"
        params["tax"] = taxonomy

    params["grey_low"] = float((d.get("grey_zone") or {}).get("low", 0.70))
    with db.session_scope(cfg) as s:
        rows = s.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# runner
# =============================================================================
def run_dedup(
    cfg: Config,
    *,
    destination: str | None = None,
    taxonomy: str | None = None,
    argv: list[str] | None = None,
) -> int:
    db.check_connection(cfg)
    db.assert_migrated(cfg)
    d = cfg.section("dedup")
    version = str(d.get("dedup_version", "1.0.0"))
    name_threshold = float(d.get("name_similarity_threshold", 0.82))
    dist_threshold = float(d.get("distance_m_threshold", 150))
    star_max_delta = float(d.get("star_rating_max_delta", 1))
    grey = d.get("grey_zone") or {}
    grey_low, grey_high = float(grey.get("low", 0.70)), float(grey.get("high", 0.82))
    allow_cross_grain = bool(d.get("allow_cross_grain_merge", False))
    allow_cross_taxonomy = bool(d.get("allow_cross_taxonomy_merge", False))

    with db.command_lock(cfg, "dedup"):
        with db.crawl_run("__dedup__", "dedup", cfg, argv=argv) as run:
            run.note("dedup_version", version)
            run.note(
                "thresholds",
                {
                    "name_similarity": name_threshold,
                    "distance_m": dist_threshold,
                    "star_max_delta": star_max_delta,
                    "grey_zone": [grey_low, grey_high],
                },
            )

            pairs = _candidate_pairs(cfg, destination=destination, taxonomy=taxonomy)
            log.info("scored %d candidate pair(s)", len(pairs))

            overrides = _overrides(cfg)
            merged: list[dict] = []
            review: list[dict] = []
            rejected = 0

            for p in pairs:
                if not allow_cross_taxonomy and p["a_taxonomy"] != p["b_taxonomy"]:
                    rejected += 1
                    continue
                if not allow_cross_grain and p["a_grain"] != p["b_grain"]:
                    rejected += 1
                    continue

                p["match_score"] = match_score(p, cfg)
                key = (p["a_source"], p["a_ref"], p["b_source"], p["b_ref"])
                forced = overrides.get(key)

                sim = float(p["name_similarity"] or 0.0)
                near = p["distance_m"] is not None and float(p["distance_m"]) < dist_threshold
                star_ok = p["star_delta"] is None or abs(float(p["star_delta"])) <= star_max_delta
                spec_match = near or (sim >= name_threshold and star_ok)

                if forced == "merge":
                    p["decision"] = "merge"
                elif forced == "reject":
                    p["decision"] = "reject"
                elif spec_match and p["match_score"] >= grey_high:
                    p["decision"] = "merge"
                elif grey_low <= p["match_score"] < grey_high or (sim >= grey_low and not spec_match):
                    p["decision"] = "review"
                else:
                    p["decision"] = "reject"

                if p["decision"] == "merge":
                    merged.append(p)
                elif p["decision"] == "review":
                    review.append(p)
                else:
                    rejected += 1

            _write_pairs(cfg, version, pairs)
            csv_path = _write_review_csv(cfg, review)

            uf = UnionFind()
            for p in merged:
                uf.union(_key(p["a_source"], p["a_ref"]), _key(p["b_source"], p["b_ref"]))
            # Every normalised row is a cluster, including the singletons: load
            # reads clusters, so a row that matched nothing still needs one.
            for source, ref in _all_rows(cfg, destination=destination, taxonomy=taxonomy):
                uf.find(_key(source, ref))

            groups = uf.groups()
            _write_clusters(cfg, version, groups, destination=destination, taxonomy=taxonomy)

            multi = sum(1 for m in groups.values() if len(m) > 1)
            run.set("candidate_pairs", len(pairs))
            run.set("merged_pairs", len(merged))
            run.set("review_pairs", len(review))
            run.set("rejected_pairs", rejected)
            run.set("clusters", len(groups))
            run.set("multi_source_clusters", multi)
            run.set("review_csv", str(csv_path) if review else None)

    log.info(
        "dedup done: pairs=%d merged=%d review=%d rejected=%d clusters=%d (%d multi-source)",
        len(pairs), len(merged), len(review), rejected, len(groups), multi,
    )
    if review:
        log.warning(
            "%d pair(s) in the grey zone %.2f-%.2f need a human decision: %s\n"
            "  Record verdicts in dedup_overrides and re-run dedup.",
            len(review), grey_low, grey_high, csv_path,
        )
    return exitcodes.OK


def _key(source: str, ref: str) -> str:
    return ref if ref.startswith(f"{source}:") else f"{source}:{ref}"


def _all_rows(
    cfg: Config, *, destination: str | None, taxonomy: str | None
) -> list[tuple[str, str]]:
    sql = (
        "SELECT source, source_ref FROM products_normalised "
        "WHERE normaliser_version = :nv"
    )
    params: dict[str, Any] = {
        "nv": str(cfg.section("normalise").get("normaliser_version", "1.0.0"))
    }
    if destination:
        sql += " AND destination = :dest"
        params["dest"] = destination
    if taxonomy:
        sql += " AND taxonomy = :tax"
        params["tax"] = taxonomy
    with db.session_scope(cfg) as s:
        return [(r[0], r[1]) for r in s.execute(text(sql), params).all()]


def _overrides(cfg: Config) -> dict[tuple[str, str, str, str], str]:
    """Human verdicts from ``dedup_overrides``, applied before clustering.

    This is what makes reading ``dedup_review.csv`` worth doing: a decision
    recorded once survives every later re-run.
    """
    with db.session_scope(cfg) as s:
        rows = s.execute(
            text("SELECT a_source, a_ref, b_source, b_ref, decision FROM dedup_overrides")
        ).all()
    return {(r[0], r[1], r[2], r[3]): r[4] for r in rows}


def _write_pairs(cfg: Config, version: str, pairs: list[dict]) -> None:
    if not pairs:
        return
    with db.session_scope(cfg) as s:
        s.execute(
            text("DELETE FROM dedup_pairs WHERE dedup_version = :v"), {"v": version}
        )
        for p in pairs:
            s.execute(
                text(
                    """
                    INSERT INTO dedup_pairs (
                        dedup_version, a_source, a_ref, b_source, b_ref, destination,
                        name_similarity, distance_m, star_delta, brand_match,
                        address_match, phone_match, match_score, decision
                    ) VALUES (
                        :v, :a_source, :a_ref, :b_source, :b_ref, :destination,
                        :name_similarity, :distance_m, :star_delta, :brand_match,
                        :address_match, :phone_match, :match_score, :decision
                    )
                    ON CONFLICT (dedup_version, a_source, a_ref, b_source, b_ref)
                    DO UPDATE SET match_score = EXCLUDED.match_score,
                                  decision = EXCLUDED.decision,
                                  computed_at = now()
                    """
                ),
                {
                    "v": version,
                    **{
                        k: p.get(k)
                        for k in (
                            "a_source", "a_ref", "b_source", "b_ref", "destination",
                            "name_similarity", "distance_m", "star_delta", "brand_match",
                            "address_match", "phone_match", "match_score", "decision",
                        )
                    },
                },
            )


def _write_review_csv(cfg: Config, review: list[dict]) -> Path:
    """Grey-zone pairs for manual reading (spec section 7)."""
    rel = cfg.section("dedup").get("review_csv", "data/reports/dedup_review.csv")
    path = Path(__file__).resolve().parent / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "match_score", "name_similarity", "distance_m", "star_delta", "destination",
        "a_source", "a_ref", "a_name", "a_price", "a_address", "a_phone",
        "b_source", "b_ref", "b_name", "b_price", "b_address", "b_phone",
        "verdict_merge_or_reject", "reason",
    ]
    # newline="" is required on Windows or csv writes \r\r\n.
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for p in sorted(review, key=lambda x: -float(x.get("match_score") or 0)):
            w.writerow({**p, "verdict_merge_or_reject": "", "reason": ""})
    return path


def _write_clusters(
    cfg: Config,
    version: str,
    groups: dict[str, list[str]],
    *,
    destination: str | None,
    taxonomy: str | None,
) -> None:
    """Replace this version's clusters.

    Scoped by the same ``--destination`` / ``--taxonomy`` filters the run used,
    so a partial re-run does not delete clusters for blocks it never looked at.
    """
    meta = _row_meta(cfg, destination=destination, taxonomy=taxonomy)
    priority = cfg.source_priority_map()

    with db.session_scope(cfg) as s:
        keys = list(groups)
        if keys:
            s.execute(
                text(
                    "DELETE FROM product_clusters WHERE dedup_version = :v "
                    "AND cluster_key = ANY(:keys)"
                ),
                {"v": version, "keys": keys},
            )
        for cluster_key, members in groups.items():
            present = [m for m in members if m in meta]
            if not present:
                continue
            first = meta[present[0]]
            s.execute(
                text(
                    """
                    INSERT INTO product_clusters
                           (cluster_key, dedup_version, destination, taxonomy, grain, member_count)
                    VALUES (:k, :v, :dest, :tax, :grain, :n)
                    ON CONFLICT (cluster_key, dedup_version) DO UPDATE SET
                        destination = EXCLUDED.destination,
                        taxonomy = EXCLUDED.taxonomy,
                        grain = EXCLUDED.grain,
                        member_count = EXCLUDED.member_count
                    """
                ),
                {
                    "k": cluster_key,
                    "v": version,
                    "dest": first["destination"],
                    "tax": first["taxonomy"],
                    "grain": first["page_kind"],
                    "n": len(present),
                },
            )
            # is_primary is the highest-priority source in the cluster: it wins
            # `name`, and products.source_ref takes its ref (see merge.py).
            primary = max(present, key=lambda m: priority.get(meta[m]["source"], 0))
            for m in present:
                s.execute(
                    text(
                        """
                        INSERT INTO product_cluster_members
                               (cluster_key, dedup_version, source, source_ref, is_primary, match_score)
                        VALUES (:k, :v, :src, :ref, :prim, NULL)
                        ON CONFLICT (dedup_version, source, source_ref) DO UPDATE SET
                            cluster_key = EXCLUDED.cluster_key,
                            is_primary = EXCLUDED.is_primary
                        """
                    ),
                    {
                        "k": cluster_key,
                        "v": version,
                        "src": meta[m]["source"],
                        "ref": meta[m]["source_ref"],
                        "prim": m == primary,
                    },
                )


def _row_meta(
    cfg: Config, *, destination: str | None, taxonomy: str | None
) -> dict[str, dict[str, Any]]:
    sql = (
        "SELECT source, source_ref, destination, taxonomy, page_kind "
        "FROM products_normalised WHERE normaliser_version = :nv"
    )
    params: dict[str, Any] = {
        "nv": str(cfg.section("normalise").get("normaliser_version", "1.0.0"))
    }
    if destination:
        sql += " AND destination = :dest"
        params["dest"] = destination
    if taxonomy:
        sql += " AND taxonomy = :tax"
        params["tax"] = taxonomy
    with db.session_scope(cfg) as s:
        rows = s.execute(text(sql), params).mappings().all()
    return {_key(r["source"], r["source_ref"]): dict(r) for r in rows}
