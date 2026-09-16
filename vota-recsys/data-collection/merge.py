"""Field-level merge across the sources in one dedup cluster (spec section 7).

Spec section 7 fixes which source wins which field:

===================================== ==========================================
field                                 winner
===================================== ==========================================
``name``, ``description``, ``images``  vinpearl.com
``unitPrice``, ``available``, dates    OTA (booking > agoda > trip)
structured ``attributes``              booking.com
``latitude/longitude``, ``address``    whichever has it, OTA first
``aggregateRating``, ``reviewCount``   the OTA with the highest ``reviewCount``
===================================== ==========================================

That table is expressed **declaratively** in ``config.merge`` rather than as a
chain of ``if source == ...``, for two reasons: section 12 item 2 requires the
rule to appear in the README, and generating it from the same data the merge
actually uses is the only way the README cannot drift from the code.

Two invariants this module is responsible for:

* **Only real columns reach a column.** ``products`` has exactly the 19 columns
  in spec section 4.2. ``address``, ``brand``, ``starRating``,
  ``aggregateRating``, ``reviewCount`` and ``phone`` are section 5.2/5.3
  *attributes*, not columns, and putting them in an INSERT column list would
  either crash or tempt someone into widening the CDP mirror — the section 13
  trap. :func:`project` splits the two and a test asserts the split.
* **No NOT NULL column can come out None.** Seven ``products`` columns are
  NOT NULL. A strategy that follows another field (``currency`` following
  ``unit_price``, say) returns nothing for a cluster with no priced member —
  which is most attraction and golf rows — so every NOT NULL column gets an
  explicit terminal default, and :func:`assert_defaults_cover_not_null` checks
  that at startup rather than at INSERT time.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from config import Config
from models import PRODUCTS_COLUMNS

log = logging.getLogger("merge")

#: NOT NULL in the spec section 4.2 DDL. ``product_id``, ``created_at`` and
#: ``updated_at`` are supplied by load itself.
NOT_NULL_COLUMNS: tuple[str, ...] = (
    "name", "taxonomy", "destination", "attributes", "currency", "available",
    "images", "source_ref",
)

#: Terminal defaults for the NOT NULL columns. ``name`` and ``taxonomy`` have
#: none on purpose: a cluster with no name is not a product, and load rejects it
#: into ``normalise_rejects`` rather than inventing a placeholder.
COLUMN_DEFAULTS: dict[str, Any] = {
    "destination": "unknown",
    "attributes": {},
    "currency": "VND",
    "available": True,
    "images": [],
}

REQUIRED_NO_DEFAULT: tuple[str, ...] = ("name", "taxonomy", "source_ref")


class MergeError(Exception):
    pass


def assert_defaults_cover_not_null() -> None:
    """Every NOT NULL column has a default or is explicitly required."""
    missing = [
        c
        for c in NOT_NULL_COLUMNS
        if c not in COLUMN_DEFAULTS and c not in REQUIRED_NO_DEFAULT
    ]
    if missing:
        raise MergeError(
            f"NOT NULL columns with neither a default nor a required-marker: {missing}"
        )


# =============================================================================
# strategies
# =============================================================================
def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _order(cfg: Config, name: Any) -> list[str]:
    """Resolve an order reference like ``content_order`` to a source list."""
    merge = cfg.section("merge")
    if isinstance(name, list):
        return [str(x) for x in name]
    key = str(name)
    if key in merge and isinstance(merge[key], list):
        return [str(x) for x in merge[key]]
    return [str(name)]


def _by_source(members: list[dict], order: list[str]) -> list[dict]:
    """Members sorted by the configured source order, unlisted sources last."""
    rank = {s: i for i, s in enumerate(order)}
    return sorted(members, key=lambda m: (rank.get(m["source"], len(order)), m["source_ref"]))


def _s_source_order(
    field: str, members: list[dict], rule: dict, cfg: Config
) -> tuple[Any, dict | None]:
    # _attr_or_column, not m.get: this strategy resolves both real columns and
    # section 5.2 attributes (which live inside member["attributes"]), and a
    # plain .get() silently returns None for every attribute — so starRating,
    # amenities and brand would never merge at all.
    candidates = _by_source(members, _order(cfg, rule.get("order", "content_order")))
    if rule.get("prefer_vietnamese"):
        # The language guard that makes ingesting English Amadeus text safe.
        # Without it, an Amadeus description can win `description` purely by
        # source order on a cluster where the Vietnamese source ranked lower,
        # and the Week 2 model comparison is then run on a half-English corpus.
        from quality import real_vietnamese

        vietnamese = [
            m for m in candidates if real_vietnamese(_attr_or_column(m, field)) >= 0.3
        ]
        if vietnamese:
            candidates = vietnamese
    tie_break = rule.get("tie_break")
    if tie_break == "longest":
        candidates = sorted(
            candidates,
            key=lambda m: (
                _order(cfg, rule.get("order", "content_order")).index(m["source"])
                if m["source"] in _order(cfg, rule.get("order", "content_order"))
                else 99,
                -len(str(_attr_or_column(m, field) or "")),
            ),
        )
    for m in candidates:
        value = _attr_or_column(m, field)
        if _present(value):
            return value, m
    fallback = rule.get("fallback_order")
    if fallback:
        for m in _by_source(members, _order(cfg, fallback)):
            value = _attr_or_column(m, field)
            if _present(value):
                return value, m
    return None, None


def _s_max_by(field: str, members: list[dict], rule: dict, cfg: Config) -> tuple[Any, dict | None]:
    key = rule.get("key", "reviewCount")
    restrict = rule.get("restrict_to")
    pool = members
    if restrict:
        allowed = set(_order(cfg, restrict))
        pool = [m for m in members if m["source"] in allowed] or members
    best: tuple[float, dict] | None = None
    for m in pool:
        value = _attr_or_column(m, field)
        if not _present(value):
            continue
        weight = _as_number(_attr_or_column(m, key)) or 0.0
        if best is None or weight > best[0]:
            best = (weight, m)
    if best is None:
        return None, None
    return _attr_or_column(best[1], field), best[1]


def _s_first_of(field: str, members: list[dict], rule: dict, cfg: Config) -> tuple[Any, dict | None]:
    """First element of another field — how ``image_url`` derives from ``images``."""
    source_field = rule.get("field", "images")
    value, winner = _s_source_order(
        source_field, members, {"order": rule.get("order", "content_order")}, cfg
    )
    if isinstance(value, list) and value:
        return value[0], winner
    return None, None


def _s_constant(field: str, members: list[dict], rule: dict, cfg: Config) -> tuple[Any, dict | None]:
    return rule.get("value"), None


def _s_primary_member(
    field: str, members: list[dict], rule: dict, cfg: Config
) -> tuple[Any, dict | None]:
    """``products.source_ref`` is scalar but a merged product has several.

    It takes the primary member's ref — the winner of ``name``. Recorded here
    and in ``docs/decisions/cdp-schema-questions.md`` (question A2) because a
    later integrator needs to know that the full mapping lives in
    ``product_sources``, not in this column.
    """
    primary = next((m for m in members if m.get("is_primary")), None) or _by_source(
        members, _order(cfg, "content_order")
    )[0]
    return primary["source_ref"], primary


_STRATEGIES = {
    "source_order": _s_source_order,
    "max_by": _s_max_by,
    "first_of": _s_first_of,
    "constant": _s_constant,
    "primary_member": _s_primary_member,
}


# =============================================================================
# merge
# =============================================================================
def merge_cluster(members: list[dict], cfg: Config) -> tuple[dict[str, Any], dict[str, Any], list[dict]]:
    """Merge one cluster.

    Returns ``(columns, attributes, winner_log)``, where ``columns`` contains
    only spec section 4.2 column names and ``attributes`` only section 5.2 keys.
    """
    if not members:
        raise MergeError("merge_cluster called with no members")
    merge_cfg = cfg.section("merge")
    column_rules: dict[str, dict] = merge_cfg.get("columns") or {}
    attribute_rules: dict[str, dict] = merge_cfg.get("attributes") or {}

    if not any(m.get("is_primary") for m in members):
        primary = _by_source(members, _order(cfg, "content_order"))[0]
        primary["is_primary"] = True

    columns: dict[str, Any] = {}
    winners: list[dict] = []

    for field, rule in column_rules.items():
        if field not in PRODUCTS_COLUMNS:
            raise MergeError(
                f"merge.columns.{field} is not a column of products. The spec "
                f"section 4.2 columns are {PRODUCTS_COLUMNS}. Section 5.2 "
                "attributes belong under merge.attributes."
            )
        strategy = _STRATEGIES.get(str(rule.get("strategy", "source_order")))
        if strategy is None:
            raise MergeError(f"unknown merge strategy {rule.get('strategy')!r} for {field}")
        value, winner = strategy(field, members, rule, cfg)
        if not _present(value) and "default" in rule:
            value, winner = rule["default"], None
        columns[field] = value
        winners.append(
            {
                "field": field,
                "winning_source": winner["source"] if winner else None,
                "winning_ref": winner["source_ref"] if winner else None,
                "strategy": str(rule.get("strategy", "source_order")),
            }
        )

    # Attributes: union across members, then per-key precedence for the keys
    # that have a rule. Union first so a source-specific attribute nobody wrote
    # a rule for is still carried.
    all_keys: set[str] = set()
    for m in members:
        all_keys.update((m.get("attributes") or {}).keys())

    attributes: dict[str, Any] = {}
    default_rule = attribute_rules.get("_default") or {"strategy": "source_order", "order": "content_order"}
    for key in sorted(all_keys):
        rule = attribute_rules.get(key) or default_rule
        strategy = _STRATEGIES.get(str(rule.get("strategy", "source_order")))
        if strategy is None:
            continue
        value, winner = strategy(key, members, rule, cfg)
        if _present(value):
            attributes[key] = value
            winners.append(
                {
                    "field": f"attributes.{key}",
                    "winning_source": winner["source"] if winner else None,
                    "winning_ref": winner["source_ref"] if winner else None,
                    "strategy": str(rule.get("strategy", "source_order")),
                }
            )

    columns["attributes"] = attributes
    return columns, attributes, winners


def project(columns: dict[str, Any], attributes: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Coerce a merged cluster into an insertable ``products`` row.

    Returns ``(row, problems)``. ``problems`` is non-empty when a required
    column has no value, in which case the caller rejects the cluster instead of
    inserting a placeholder.
    """
    assert_defaults_cover_not_null()
    row: dict[str, Any] = {}
    problems: list[str] = []

    for col in PRODUCTS_COLUMNS:
        if col in ("product_id", "created_at", "updated_at"):
            continue  # supplied by load
        value = columns.get(col)
        if not _present(value) and col in COLUMN_DEFAULTS:
            value = COLUMN_DEFAULTS[col]
        if col == "attributes":
            value = attributes or {}
        if col == "images" and value is None:
            value = []
        if col in REQUIRED_NO_DEFAULT and not _present(value):
            # An empty string here is as bad as a null: a product with no name
            # is not a product.
            problems.append(f"{col} is required but no member supplied it")
        elif col in NOT_NULL_COLUMNS and value is None:
            # Only None violates NOT NULL. `{}` and `[]` are the legitimate
            # empty values for the attributes and images columns, and treating
            # them as missing would reject every product that simply has no
            # attributes yet.
            problems.append(f"{col} is NOT NULL and resolved to None with no default")
        row[col] = value

    if row.get("currency"):
        row["currency"] = str(row["currency"])[:3].upper()
    if isinstance(row.get("unit_price"), (int, float)):
        row["unit_price"] = Decimal(str(row["unit_price"]))
    return row, problems


def _attr_or_column(member: dict, field: str) -> Any:
    """Look a field up as a column first, then inside ``attributes``.

    Needed because ``max_by`` rules reference ``reviewCount`` — an attribute —
    while other strategies reference real columns, and a caller should not have
    to know which is which.
    """
    if field in member:
        return member[field]
    return (member.get("attributes") or {}).get(field)


def _as_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def precedence_table(cfg: Config) -> list[dict[str, str]]:
    """The section 7 rule as rows, for README section 12 item 2.

    Generated from ``config.merge`` — the same data the merge reads — so the
    documented rule and the implemented rule cannot disagree.
    """
    merge_cfg = cfg.section("merge")
    rows: list[dict[str, str]] = []
    for group, label in (("columns", "column"), ("attributes", "attribute")):
        for field, rule in (merge_cfg.get(group) or {}).items():
            if field == "_default":
                continue
            strategy = str(rule.get("strategy", "source_order"))
            if strategy == "constant":
                winner = f"constant {rule.get('value')!r}"
            elif strategy == "max_by":
                winner = (
                    f"highest {rule.get('key')} among "
                    + ", ".join(_order(cfg, rule.get("restrict_to", "ota_order")))
                )
            elif strategy == "primary_member":
                winner = "primary member (winner of name)"
            elif strategy == "first_of":
                winner = f"first element of {rule.get('field')}"
            else:
                winner = " > ".join(_order(cfg, rule.get("order", "content_order")))
                if rule.get("fallback_order"):
                    winner += " (then " + " > ".join(_order(cfg, rule["fallback_order"])) + ")"
                if rule.get("prefer_vietnamese"):
                    winner += "; Vietnamese text preferred"
            rows.append({"kind": label, "field": field, "winner": winner, "strategy": strategy})
    return rows
