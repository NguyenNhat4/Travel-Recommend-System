"""products_staging -> products_normalised (spec section 6).

Every rule in spec section 6.2 lives here, and nowhere else. A collector emits
the source's own wording; this module is the only place that renames, converts,
maps or derives anything. That split is what makes a wrong rule a
``normalize --force`` instead of a re-crawl.

The rules, and the trap each one exists to avoid:

* **Text** — strip tags, collapse whitespace, normalise to NFC, then stop. Never
  lowercase, never strip diacritics, never truncate. The name and description
  are the embedding input (handbook section 3: "Tên và mô tả sản phẩm chính là
  thứ mà embedding model thực sự đọc"), so folding them destroys the dataset's
  only real asset.
* **Lookup vs storage** — diacritics *are* folded to build a comparison key for
  destination matching. The stored value keeps them. Confusing the two is how a
  catalogue ends up named "khach san vinpearl nha trang".
* **Destination** — canonical list plus aliases from config; anything unmatched
  becomes ``'unknown'`` and is reported for manual review. Never guessed.
* **Price** — parse the displayed string, keep the original, convert foreign
  currency at a fixed rate that is recorded with the run.
* **Attributes** — a per-taxonomy allowlist from spec section 5.2. The columns
  are guarded by the DDL; the JSONB is what Week 2/3 queries by name, so it
  gets a registry too.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from selectolax.parser import HTMLParser
from sqlalchemy import text

import db
import exitcodes
from config import Config
from ids import lookup_key
from quality import quality_score
from runtime import shutdown

log = logging.getLogger("normalise")

# =============================================================================
# attribute registry (spec section 5.2)
# =============================================================================
#: The exact attribute names spec section 5.2 lists, per taxonomy. Anything not
#: here is dropped rather than written into ``products.attributes``. Section 13's
#: "tự bịa field" trap is closed for columns by the DDL; this closes it for the
#: JSONB, which is the half Week 2/3 actually queries by name.
ATTRIBUTE_KEYS: dict[str, tuple[str, ...]] = {
    "hotel": (
        "starRating", "roomType", "bedType", "maxOccupancy", "sizeSqm", "view",
        "amenities", "breakfastIncluded", "freeCancellation", "cancellationPolicy",
        "checkIn", "checkOut", "address", "brand", "aggregateRating", "reviewCount",
        "familyFriendly", "privatePool", "beachfront", "petFriendly", "hasSpa",
        "hasKidsClub",
    ),
    "attraction": (
        "ticketType", "duration", "openingHours", "includedServices",
        "heightRestrictionCm", "ageRestriction", "poiName", "indoorOutdoor", "bestFor",
        "address", "aggregateRating", "reviewCount",
    ),
    "flight": (
        "carrier", "flightNo", "originIata", "destinationIata", "departTime",
        "arriveTime", "durationMin", "stops", "cabinClass", "baggageAllowanceKg",
        "fareType", "refundable",
    ),
    "combo": (
        "components", "nights", "minPax", "validFrom", "validTo", "blackoutDates",
        "transferIncluded", "address", "aggregateRating", "reviewCount",
    ),
    "golf": (
        "courseName", "holes", "par", "teeTimeSlots", "caddieFeeIncluded",
        "weekdayPrice", "weekendPrice", "buggyIncluded", "address",
        "aggregateRating", "reviewCount",
    ),
}

#: Allowed for every taxonomy. ``descriptionEn`` carries English source text so
#: it never lands in ``products.description`` — see ``description_policy``.
ATTRIBUTE_COMMON: tuple[str, ...] = ("descriptionEn", "phone", "sourceCategory", "quoteContext")


# =============================================================================
# text (spec section 6.2)
# =============================================================================
_WS_RE = re.compile(r"[ \t\r\f\v ]+")
_NL_RE = re.compile(r"\n{3,}")


#: Tags that end a line of prose. Everything else is inline.
_BLOCK_TAGS = (
    "p", "div", "section", "article", "li", "ul", "ol", "tr", "td", "th", "table",
    "h1", "h2", "h3", "h4", "h5", "h6", "br", "hr", "blockquote", "dd", "dt", "dl",
)
_BLOCK_RE = re.compile(
    r"</?(?:" + "|".join(_BLOCK_TAGS) + r")\b[^>]*>", re.IGNORECASE
)


def strip_html(value: str | None) -> str:
    """Tags out, text kept, entities decoded. Nothing else.

    Block-level tags become newlines and inline tags become nothing, which
    matters more than it looks: extracting with a newline separator on *every*
    element turns "Hướng <b>biển</b> tuyệt đẹp" into three lines, and a
    description chopped at every ``<b>`` reads to a reader — and embeds to a
    model — as broken text rather than a sentence.
    """
    if not value:
        return ""
    if "<" not in value:
        return value
    tree = HTMLParser(value)
    for sel in ("script", "style", "noscript", "template"):
        for node in tree.css(sel):
            node.decompose()
    body = tree.body or tree.root
    if body is None:
        return value
    marked = _BLOCK_RE.sub("\n", body.html or "")
    inner = HTMLParser(marked)
    target = inner.body or inner.root
    return target.text(separator="", strip=False) if target is not None else marked


def normalise_text(value: str | None, *, keep_newlines: bool = True) -> str:
    """The section 6.2 text rule.

    NFC, tags removed, whitespace collapsed, diacritics and case untouched, and
    **no length limit** — section 5.1 marks description as "full text, không
    truncate", and a truncated description is a failure mode section 13 names
    explicitly.
    """
    if not value:
        return ""
    s = strip_html(value)
    s = unicodedata.normalize("NFC", s)
    s = s.replace("​", "").replace("﻿", "")
    s = _WS_RE.sub(" ", s)
    if keep_newlines:
        s = _NL_RE.sub("\n\n", s)
        s = "\n".join(line.strip() for line in s.split("\n"))
        return s.strip()
    return s.replace("\n", " ").strip()


def build_description(payload: dict, cfg: Config) -> str:
    """Assemble the description, dropping any review section by heading.

    Spec section 5.4 forbids review content; dropping by heading keeps the real
    description whole instead of cutting it short, which section 5.1 forbids
    just as firmly.
    """
    deny = [
        lookup_key(str(h))
        for h in (cfg.section("normalise").get("text") or {}).get(
            "description_heading_denylist", []
        )
    ]
    blocks = payload.get("description_blocks") or []
    if blocks:
        parts: list[str] = []
        for block in blocks:
            heading = lookup_key(str(block.get("heading") or ""))
            if heading and any(d and d in heading for d in deny):
                continue
            body = normalise_text(block.get("html"))
            if body:
                parts.append(body)
        joined = "\n\n".join(parts).strip()
        if joined:
            return joined
    return normalise_text(payload.get("description_html"))


# =============================================================================
# price (spec section 6.2)
# =============================================================================
_NUM_RE = re.compile(r"(\d[\d.,\s ]*)")


def parse_price(raw: Any, cfg: Config) -> tuple[Decimal | None, str | None]:
    """``"3.400.000đ"`` -> ``(Decimal('3400000'), 'VND')``.

    Handles the shapes Vietnamese sites actually print: dot thousands
    separators, comma thousands separators, a "từ" prefix, a range whose lower
    bound is the answer, and the "3,4tr" / "250k" shorthands.

    Returns ``(None, None)`` rather than guessing when there is no usable
    number. A wrong price is worse than a missing one, because ``quality_score``
    can see a missing one.
    """
    if raw is None or raw == "":
        return None, None
    if isinstance(raw, (int, float, Decimal)):
        try:
            value = Decimal(str(raw))
        except InvalidOperation:
            return None, None
        return (value if value > 0 else None), None

    s = unicodedata.normalize("NFC", str(raw)).strip()
    if not s:
        return None, None

    price_cfg = cfg.section("normalise").get("price") or {}
    symbols: dict[str, str] = price_cfg.get("currency_symbols") or {}
    currency: str | None = None
    lowered = s.lower()
    # Longest symbol first so "VND" wins over a bare "d".
    for symbol, code in sorted(symbols.items(), key=lambda kv: -len(kv[0])):
        if symbol.lower() in lowered:
            currency = code
            break

    match = _NUM_RE.search(s)
    if not match:
        return None, currency
    digits = match.group(1)
    tail = s[match.end() : match.end() + 8].lower().lstrip()

    multiplier = Decimal(1)
    for suffix in price_cfg.get("million_suffixes") or []:
        if tail.startswith(str(suffix).lower()):
            multiplier = Decimal(1_000_000)
            break
    else:
        for suffix in price_cfg.get("thousand_suffixes") or []:
            if tail.startswith(str(suffix).lower()):
                multiplier = Decimal(1_000)
                break

    cleaned = re.sub(r"[\s ]", "", digits).rstrip(".,")
    if multiplier > 1:
        # "3,4tr" / "3.4tr": here the separator is a decimal point.
        cleaned = cleaned.replace(",", ".")
        parts = cleaned.split(".")
        cleaned = parts[0] + ("." + parts[1] if len(parts) > 1 else "")
    else:
        # Group marks only: both "." and "," are thousands separators in the
        # shapes these sites use, so drop them rather than guessing a locale.
        cleaned = cleaned.replace(".", "").replace(",", "")
    try:
        value = Decimal(cleaned) * multiplier
    except InvalidOperation:
        return None, currency

    lo = Decimal(str(price_cfg.get("min_plausible_vnd", 0)))
    hi = Decimal(str(price_cfg.get("max_plausible_vnd", 10**12)))
    if currency in (None, "VND") and not (lo <= value <= hi):
        log.debug("implausible VND price %s from %r", value, raw)
        return None, currency
    return (value if value > 0 else None), currency


def to_vnd(
    amount: Decimal | None, currency: str | None, cfg: Config
) -> tuple[Decimal | None, Decimal | None]:
    """Convert to VND at the fixed configured rate. Returns ``(vnd, rate_used)``.

    The rate and its ``as_of`` date are recorded on the run so README section 12
    item 3 ("tỷ giá đã dùng + ngày áp dụng") is generated rather than
    remembered.
    """
    if amount is None:
        return None, None
    code = (currency or "VND").upper()
    rates = cfg.section("fx_rates").get("rates") or {}
    if code == "VND":
        return amount.quantize(Decimal("0.01")), Decimal(1)
    if code not in rates:
        log.warning("no FX rate for %s; leaving the price unset rather than guessing", code)
        return None, None
    rate = Decimal(str(rates[code]))
    return (amount * rate).quantize(Decimal("0.01")), rate


# =============================================================================
# destination (spec section 6.1)
# =============================================================================
def map_destination(fields: list[str | None], cfg: Config) -> tuple[str, str]:
    """Map free text to one of the 15 canonical destinations.

    Returns ``(name, method)`` with method in ``exact|alias|none``.

    Matching is on **word boundaries** over a diacritic-folded key, with no
    minimum alias length. A length floor — the obvious way to stop short aliases
    firing everywhere — would make ``Huế`` and ``Hue`` (three characters, and one
    of the 15 canonical names) permanently unmatchable, along with every 3-letter
    IATA code.

    Anything unmatched returns ``'unknown'``: spec section 6.1 says "không tự
    đoán", and a product in the wrong city is worse than one in no city.
    """
    index = cfg.destination_index
    for value in fields:
        if not value:
            continue
        key = lookup_key(str(value))
        if key and key in index:
            return index[key], "exact"
    for value in fields:
        if not value:
            continue
        key = lookup_key(str(value))
        if not key:
            continue
        for alias_key, name in index.items():
            if re.search(rf"(?<![0-9a-z]){re.escape(alias_key)}(?![0-9a-z])", key):
                return name, "alias"
    return "unknown", "none"


def destination_from_geo(lat: float | None, lon: float | None, cfg: Config) -> tuple[str, str]:
    """Nearest canonical centroid within ``geo_fallback_km``, else unknown.

    Deliberately tight: 25 km around a known city centroid is evidence, whereas
    nearest-centroid-at-any-distance would file a Mekong Delta hotel under Cần
    Thơ purely because nothing else is closer.
    """
    if lat is None or lon is None:
        return "unknown", "none"
    import math

    limit_km = float(cfg.section("destinations").get("geo_fallback_km", 25))
    best: tuple[float, str] | None = None
    for dest in cfg.destinations.values():
        if dest.lat is None or dest.lon is None:
            continue
        dlat = math.radians(dest.lat - lat)
        dlon = math.radians(dest.lon - lon)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat))
            * math.cos(math.radians(dest.lat))
            * math.sin(dlon / 2) ** 2
        )
        km = 2 * 6371 * math.asin(math.sqrt(a))
        if best is None or km < best[0]:
            best = (km, dest.name)
    if best and best[0] <= limit_km:
        return best[1], "geo"
    return "unknown", "none"


# =============================================================================
# taxonomy (spec section 6.2 — map in config, never hardcoded)
# =============================================================================
def map_taxonomy(source: str, payload: dict, cfg: Config) -> str | None:
    """``taxonomy_hint`` from url_patterns wins; the category table is the fallback.

    ``url_patterns[].taxonomy`` is the single declaration for site sources: the
    collector already classified the URL through it, so re-deriving a taxonomy
    from page text here would be a second source of truth that can disagree.
    """
    hint = payload.get("taxonomy_hint")
    if hint in ATTRIBUTE_KEYS:
        return hint
    table = (cfg.section("taxonomy_map").get("by_category") or {}).get(source) or {}
    category = payload.get("category_raw")
    if category:
        key = lookup_key(str(category))
        for raw_label, taxonomy in table.items():
            if lookup_key(str(raw_label)) == key:
                return taxonomy
    return cfg.section("taxonomy_map").get("default")


# =============================================================================
# images (spec section 6.2)
# =============================================================================
def clean_image_url(url: str, source: str, cfg: Config) -> str:
    """Drop resize parameters and rewrite thumbnail buckets to full size.

    Spec section 6.2 says drop resize params and keep the biggest version;
    section 5.1 repeats it. The bucket rewrite is a substitution on the site's
    own documented size tokens — it evades nothing, it just asks for the
    full-size file instead of the 60px card thumbnail that happened to be in the
    listing markup.
    """
    rules = cfg.section("normalise").get("images") or {}
    per_source = (rules.get("per_source") or {}).get(source) or {}
    drop = {
        str(p).lower()
        for p in (per_source.get("drop_query_params") or rules.get("drop_query_params") or [])
    }
    parts = urlsplit(url)
    query = urlencode(
        [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in drop
        ]
    )
    path = parts.path
    rewrite = per_source.get("bucket_path_rewrite") or {}
    if rewrite.get("from") and rewrite.get("to"):
        path = re.sub(str(rewrite["from"]), str(rewrite["to"]), path, flags=re.IGNORECASE)
    return urlunsplit((parts.scheme, parts.netloc, path, query, ""))


def normalise_images(payload: dict, source: str, cfg: Config) -> list[str]:
    rules = cfg.section("normalise").get("images") or {}
    limit = int(rules.get("max_images_per_product", 20))
    out: list[str] = []
    for raw in payload.get("images") or []:
        url = raw.get("url") if isinstance(raw, dict) else raw
        if not url or not isinstance(url, str):
            continue
        cleaned = clean_image_url(url.strip(), source, cfg)
        if cleaned and cleaned not in out:
            out.append(cleaned)
        if len(out) >= limit:
            break
    return out


# =============================================================================
# phone (spec section 5.3)
# =============================================================================
def normalise_phone(raw: str | None, cfg: Config) -> str | None:
    """Reduce a published phone number to a comparable form.

    Needed because section 5.3 lists ``phone`` as a dedup field and the match
    score consumes it: an un-normalised phone makes that feature effectively
    constant-false and quietly weakens every comparison.
    """
    if not raw:
        return None
    cfg_phone = cfg.section("normalise").get("phone") or {}
    cc = str(cfg_phone.get("default_country_code", "84"))
    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return None
    if digits.startswith("00" + cc):
        digits = digits[2 + len(cc) :]
    elif digits.startswith(cc) and len(digits) > 9:
        digits = digits[len(cc) :]
    digits = digits.lstrip("0")
    return f"+{cc}{digits}" if digits else None


# =============================================================================
# ratings (spec section 7 merges by reviewCount, so scales must agree first)
# =============================================================================
def rescale_rating(value: Any, source: str, best: Any, cfg: Config) -> float | None:
    """Put every source's rating on one scale before anything compares them.

    booking and agoda publish 0-10, JSON-LD carries a per-page ``bestRating``,
    Amadeus e-reputation is 0-100. Spec section 7 merges ``aggregateRating`` by
    taking the source with the highest ``reviewCount`` — so without rescaling
    first, one column holds 8.7, 4.4 and 87 with no unit and no way to tell
    which is which.
    """
    if value in (None, ""):
        return None
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return None
    ratings = cfg.section("ratings")
    target = float(ratings.get("target_scale", 5))
    configured = (ratings.get("scale_by_source") or {}).get(source)

    from_scale: float | None = None
    if configured == "jsonld":
        from_scale = _as_float(best)
    elif configured not in (None, "null"):
        from_scale = _as_float(configured)
    if from_scale is None:
        from_scale = _as_float(best) or target
    if not from_scale or from_scale <= 0:
        return None
    return round(raw * target / from_scale, 3)


# =============================================================================
# derived attributes (spec section 5.2)
# =============================================================================
def _match_any(haystack: str, needles: list[Any]) -> bool:
    key = lookup_key(haystack)
    return any(lookup_key(str(n)) in key for n in needles if str(n).strip())


def derive_attributes(payload: dict, taxonomy: str, cfg: Config) -> dict[str, Any]:
    """Produce the section 5.2 attributes that sources only state in prose.

    The six hotel booleans, ``view``, ``brand``, ``nights`` and ``duration`` are
    all required by section 5.2 and no site publishes them as fields. They are
    derived from amenity labels, spec tables and description text using keyword
    lists in ``config.derive``, so a wrong keyword is a YAML edit.
    """
    derive = cfg.section("derive")
    out: dict[str, Any] = {}

    text_pool = " ".join(
        str(x)
        for x in (
            payload.get("name_raw") or "",
            payload.get("description_html") or "",
            " ".join(str(a) for a in (payload.get("amenity_labels") or [])),
            " ".join(
                f"{p.get('label', '')} {p.get('value', '')}"
                for p in (payload.get("spec_pairs") or [])
            ),
        )
    )

    if taxonomy == "hotel":
        for flag, needles in (derive.get("flag_keywords") or {}).items():
            if _match_any(text_pool, list(needles)):
                out[flag] = True
        for view, needles in (derive.get("view_keywords") or {}).items():
            if _match_any(text_pool, list(needles)):
                out["view"] = view
                break
        pairs = {
            lookup_key(p.get("label", "")): p.get("value")
            for p in payload.get("spec_pairs") or []
        }
        for key, names in (
            ("checkIn", ("check in", "gio nhan phong", "nhan phong")),
            ("checkOut", ("check out", "gio tra phong", "tra phong")),
            ("sizeSqm", ("dien tich", "size", "room size")),
            ("maxOccupancy", ("so khach", "occupancy", "suc chua")),
            ("bedType", ("loai giuong", "bed type", "giuong")),
            ("cancellationPolicy", ("chinh sach huy", "cancellation")),
            ("roomType", ("loai phong", "room type")),
        ):
            for label, value in pairs.items():
                if any(n in label for n in names) and value:
                    out[key] = value
                    break

    if taxonomy == "attraction":
        labels = derive.get("attraction_labels") or {}
        pairs = payload.get("spec_pairs") or []
        if payload.get("opening_hours_raw"):
            out["openingHours"] = payload["opening_hours_raw"]
        for attr, cfg_key in (
            ("openingHours", "opening_hours"),
            ("duration", "duration"),
            ("heightRestrictionCm", "height_restriction"),
            ("ageRestriction", "age_restriction"),
            ("includedServices", "included_services"),
        ):
            if out.get(attr):
                continue
            for pair in pairs:
                if _match_any(str(pair.get("label", "")), list(labels.get(cfg_key) or [])):
                    out[attr] = pair.get("value")
                    break
        if not out.get("duration"):
            default = (derive.get("duration_defaults") or {}).get("attraction")
            if default:
                # Labelled as a default, not passed off as a fact: Week 4 needs
                # a duration to build an itinerary, and a marked guess beats a
                # null there.
                out["duration"] = f"{default} phút (mặc định)"
        label = payload.get("ticket_label_raw")
        if label:
            for ticket_type, needles in (derive.get("ticket_type_keywords") or {}).items():
                if _match_any(str(label), list(needles)):
                    out["ticketType"] = ticket_type
                    break
        for io, needles in (derive.get("indoor_outdoor_keywords") or {}).items():
            if _match_any(text_pool, list(needles)):
                out["indoorOutdoor"] = io
                break
        if payload.get("poi_name"):
            out["poiName"] = normalise_text(payload["poi_name"], keep_newlines=False)

    if taxonomy == "combo":
        combo = payload.get("combo") or {}
        if combo.get("nights_raw"):
            out["nights"] = int(combo["nights_raw"])
        if combo.get("min_pax"):
            out["minPax"] = _as_int(combo["min_pax"])
        if combo.get("valid_from"):
            out["validFrom"] = str(combo["valid_from"])
        if combo.get("valid_to"):
            out["validTo"] = str(combo["valid_to"])
        if combo.get("transfer_included") is not None:
            out["transferIncluded"] = bool(combo["transfer_included"])
        labels = [
            normalise_text(c, keep_newlines=False) for c in combo.get("component_labels") or []
        ]
        components = combo.get("components")
        if components:
            out["components"] = components
        elif labels:
            out["components"] = [{"name": c} for c in labels if c]

    if taxonomy == "golf":
        golf = payload.get("golf") or {}
        if golf.get("courseName"):
            out["courseName"] = normalise_text(golf["courseName"], keep_newlines=False)
        for attr, raw_key in (("holes", "holes_raw"), ("par", "par_raw")):
            value = golf.get(raw_key)
            if value:
                m = re.search(r"\d+", str(value))
                if m:
                    out[attr] = int(m.group())
        if golf.get("tee_raw"):
            out["teeTimeSlots"] = (
                golf["tee_raw"]
                if isinstance(golf["tee_raw"], list)
                else [normalise_text(str(golf["tee_raw"]), keep_newlines=False)]
            )
        for attr, key in (
            ("caddieFeeIncluded", "caddie_fee_included"),
            ("buggyIncluded", "buggy_included"),
        ):
            if golf.get(key) is not None:
                out[attr] = bool(golf[key])
        for attr, key in (("weekdayPrice", "weekday_price"), ("weekendPrice", "weekend_price")):
            amount, currency = parse_price(golf.get(key), cfg)
            vnd, _ = to_vnd(amount, currency, cfg)
            if vnd is not None:
                out[attr] = float(vnd)

    if taxonomy == "flight":
        flight = payload.get("flight") or {}
        for key in ATTRIBUTE_KEYS["flight"]:
            if flight.get(key) not in (None, ""):
                out[key] = flight[key]

    brand_map = derive.get("brand_map") or {}
    brand = payload.get("brand_raw")
    if not brand:
        for label in brand_map:
            if _match_any(str(payload.get("name_raw") or ""), [label]):
                brand = label
                break
    if brand:
        out["brand"] = brand_map.get(str(brand), str(brand))

    amenities = [
        normalise_text(a, keep_newlines=False) for a in (payload.get("amenity_labels") or [])
    ]
    amenities = [a for a in amenities if a]
    if amenities:
        out["amenities"] = amenities

    return out


def filter_attributes(attrs: dict[str, Any], taxonomy: str, *, source: str) -> dict[str, Any]:
    """Keep only spec section 5.2 keys for this taxonomy, plus the common ones."""
    allowed = set(ATTRIBUTE_KEYS.get(taxonomy, ())) | set(ATTRIBUTE_COMMON)
    kept: dict[str, Any] = {}
    dropped: list[str] = []
    for k, v in attrs.items():
        if v in (None, "", [], {}):
            continue
        if k in allowed:
            kept[k] = v
        else:
            dropped.append(k)
    if dropped:
        log.debug("%s/%s: dropped non-section-5.2 attributes %s", source, taxonomy, dropped)
    return kept


# =============================================================================
# one record
# =============================================================================
def normalise_record(row: dict, cfg: Config) -> dict[str, Any] | tuple[None, str, str]:
    """Turn one staging row into a ``products_normalised`` record.

    Returns the record, or ``(None, reason, detail)`` when the row cannot become
    a product. Rejections are written to ``normalise_rejects`` rather than
    dropped: a product that silently vanishes between staging and ``products``
    is the hardest thing in this pipeline to debug.
    """
    payload: dict[str, Any] = row["payload"] or {}
    source: str = row["source"]
    src = cfg.source(source)

    name = normalise_text(payload.get("name_raw"), keep_newlines=False)
    if not name:
        return None, "no_name", "payload.name_raw is empty"

    page_kind = payload.get("page_kind") or "product"
    taxonomy = map_taxonomy(source, payload, cfg)
    if not taxonomy:
        return None, "no_taxonomy", (
            f"neither taxonomy_hint nor taxonomy_map.by_category.{source} resolved "
            f"category_raw={payload.get('category_raw')!r}"
        )

    description = build_description(payload, cfg)
    description_en: str | None = None
    if src.description_policy == "en_to_attributes" and description:
        # English prose would contaminate the Vietnamese corpus Week 2's model
        # comparison depends on, while making the "missing description" number
        # look healthy. Park it in attributes instead.
        description_en, description = description, ""

    price_raw = payload.get("price_raw") or payload.get("price_value")
    amount, currency = parse_price(price_raw, cfg)
    if currency is None:
        currency = (payload.get("currency_raw") or "VND") or "VND"
    unit_price, fx_rate = to_vnd(amount, currency, cfg)

    lat = _as_float(payload.get("latitude"))
    lon = _as_float(payload.get("longitude"))
    address = normalise_text(payload.get("address_raw"), keep_newlines=False) or None

    destination, method = map_destination(
        [payload.get("destination_raw"), address, payload.get("name_raw")], cfg
    )
    if destination == "unknown":
        destination, method = destination_from_geo(lat, lon, cfg)

    images = normalise_images(payload, source, cfg)
    rating = rescale_rating(
        payload.get("aggregate_rating_raw"), source, payload.get("rating_best_raw"), cfg
    )
    review_count = _as_int(payload.get("review_count_raw"))
    star = _as_float(_first_number(payload.get("star_rating_raw")))
    phone = normalise_phone(payload.get("phone_raw"), cfg)

    attrs = derive_attributes(payload, taxonomy, cfg)
    if star is not None:
        attrs["starRating"] = star
    if rating is not None:
        attrs["aggregateRating"] = rating
    if review_count is not None:
        attrs["reviewCount"] = review_count
    if address:
        attrs["address"] = address
    if phone:
        attrs["phone"] = phone
    if description_en:
        attrs["descriptionEn"] = description_en
    if payload.get("category_raw"):
        attrs["sourceCategory"] = payload["category_raw"]
    if payload.get("quote_ctx"):
        attrs["quoteContext"] = payload["quote_ctx"]
    attrs = filter_attributes(attrs, taxonomy, source=source)

    available_from = available_to = None
    quote_params = payload.get("quote_params") or {}
    if quote_params.get("checkin"):
        # What we can honestly claim: this product was priced and offered for
        # the window we actually quoted. Question A1 in
        # docs/decisions/cdp-schema-questions.md asks CDP what these two columns
        # are supposed to mean upstream.
        available_from = _as_date(quote_params.get("checkin"))
        available_to = _as_date(quote_params.get("checkout"))

    return {
        "source": source,
        "source_ref": payload["source_ref"],
        "staging_id": row["id"],
        "parser_version": row["parser_version"],
        "normaliser_version": str(cfg.section("normalise").get("normaliser_version", "1.0.0")),
        "page_kind": page_kind,
        "parent_source_ref": payload.get("parent_source_ref"),
        "name": name,
        "taxonomy": taxonomy,
        "destination": destination,
        "description": description or None,
        "attributes": attrs,
        "unit_price": unit_price,
        "currency": "VND",
        "available": True,
        "available_from": available_from,
        "available_to": available_to,
        "image_url": images[0] if images else None,
        "images": images,
        "latitude": lat,
        "longitude": lon,
        "name_normalized": lookup_key(name),
        "address": address,
        "phone": phone,
        "star_rating": star,
        "brand": attrs.get("brand"),
        "destination_raw": normalise_text(payload.get("destination_raw"), keep_newlines=False)
        or None,
        "dest_match_method": method,
        "price_raw": str(price_raw) if price_raw not in (None, "") else None,
        "fx_rate_used": fx_rate,
        "quote_ctx": payload.get("quote_ctx"),
    }


def fold_property_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Push hotel-level fields down onto each room row.

    A vinpearl hotel page emits one ``page_kind='property'`` row plus one
    ``'room'`` row per room type. The property row holds the description,
    images, geo, address and amenities; the room rows hold the name and the
    price. Without this fold every room arrives with no description and no
    coordinates, and the property row becomes a priceless phantom product
    duplicating its own rooms.

    A property row with no children stays a product: a hotel should not vanish
    just because its room list is rendered client-side.
    """
    by_ref = {r["source_ref"]: r for r in records}
    child_count: dict[str, int] = {}
    for r in records:
        parent = r.get("parent_source_ref")
        if parent:
            child_count[parent] = child_count.get(parent, 0) + 1

    inherit = (
        "description", "images", "image_url", "latitude", "longitude", "address",
        "phone", "star_rating", "brand", "destination", "destination_raw",
        "dest_match_method",
    )
    out: list[dict[str, Any]] = []
    for r in records:
        if r["page_kind"] == "property":
            if child_count.get(r["source_ref"], 0) == 0:
                out.append({**r, "page_kind": "product"})
            else:
                out.append(r)  # merge parent; load skips it
            continue
        parent = by_ref.get(r.get("parent_source_ref") or "")
        if parent is None:
            out.append(r)
            continue
        merged = dict(r)
        for field in inherit:
            if merged.get(field) in (None, "", [], {}) and parent.get(field) not in (
                None, "", [], {},
            ):
                merged[field] = parent[field]
        parent_attrs = {**(parent.get("attributes") or {})}
        parent_attrs.update(merged.get("attributes") or {})
        merged["attributes"] = parent_attrs
        out.append(merged)
    return out


# =============================================================================
# runner
# =============================================================================
def run_normalise(
    cfg: Config,
    *,
    source: str | None = None,
    force: bool = False,
    limit: int | None = None,
    argv: list[str] | None = None,
) -> int:
    version = str(cfg.section("normalise").get("normaliser_version", "1.0.0"))
    db.check_connection(cfg)
    db.assert_migrated(cfg)

    sources = [source] if source else cfg.source_names()
    total_in = total_out = total_rejected = 0

    with db.command_lock(cfg, "normalise"):
        with db.crawl_run("__normalise__", "normalise", cfg, argv=argv) as run:
            run.note("normaliser_version", version)
            run.note("fx", cfg.fx_provenance())
            run.note("quote_contexts", cfg.enabled_quote_contexts())
            if cfg.anchor_date:
                run.note("quote_anchor_date", cfg.anchor_date.isoformat())

            for name in sources:
                rows = _latest_staging(cfg, name, version, force=force, limit=limit)
                if not rows:
                    continue
                total_in += len(rows)
                log.info("normalising %d staging row(s) from %s", len(rows), name)
                _clear_rejects(cfg, name, version)

                records: list[dict[str, Any]] = []
                for row in rows:
                    try:
                        result = normalise_record(row, cfg)
                    except Exception as exc:  # noqa: BLE001 - one row must not kill the run
                        log.exception("normalise failed for staging id=%s", row["id"])
                        _reject(cfg, row, version, "exception", f"{type(exc).__name__}: {exc}")
                        total_rejected += 1
                        continue
                    if isinstance(result, tuple):
                        _, reason, detail = result
                        _reject(cfg, row, version, reason, detail)
                        total_rejected += 1
                        continue
                    records.append(result)
                    if shutdown.requested:
                        break

                records = fold_property_rows(records)
                for record in records:
                    record["quality_score"] = quality_score(record, cfg)[0]
                _upsert_normalised(cfg, records)
                total_out += len(records)
                run.bump(f"normalised_{name}", len(records))

            unknown = _unknown_destination_count(cfg, version)
            run.set("staging_rows_read", total_in)
            run.set("normalised_rows", total_out)
            run.set("rejected_rows", total_rejected)
            run.set("unknown_destination_rows", unknown)

    log.info(
        "normalise done: read=%d wrote=%d rejected=%d unknown-destination=%d",
        total_in, total_out, total_rejected, _unknown_destination_count(cfg, version),
    )
    if total_out == 0 and total_in == 0:
        log.error(
            "nothing to normalise: products_staging is empty for %s. "
            "Run discover/fetch/parse first, or `python -m cli report` for per-stage counts.",
            source or "any source",
        )
        return exitcodes.GATE_FAILED
    return exitcodes.OK


def _latest_staging(
    cfg: Config, source: str, version: str, *, force: bool, limit: int | None
) -> list[dict[str, Any]]:
    """Newest staging row per ``(source, source_ref)``, by ``parser_version``.

    ``parse --reparse`` after a version bump adds rows rather than replacing
    them (spec section 8), so several versions of one product coexist and
    normalise has to pick the current one. Ordering is on the parsed semver
    tuple rather than the string — which is why ``config.validate`` insists on
    the semver shape in the first place.
    """
    sql = [
        "SELECT DISTINCT ON (ps.source, ps.source_ref)",
        "       ps.id, ps.source, ps.source_ref, ps.parser_version, ps.payload",
        "  FROM products_staging ps",
        " WHERE ps.source = :s",
    ]
    params: dict[str, Any] = {"s": source, "v": version}
    if not force:
        sql.append(
            "   AND NOT EXISTS (SELECT 1 FROM products_normalised pn"
            "                    WHERE pn.source = ps.source"
            "                      AND pn.source_ref = ps.source_ref"
            "                      AND pn.normaliser_version = :v"
            "                      AND pn.parser_version = ps.parser_version)"
        )
    sql.append(
        " ORDER BY ps.source, ps.source_ref,"
        "          string_to_array(split_part(ps.parser_version, '-', 2), '.')::int[] DESC,"
        "          ps.id DESC"
    )
    if limit:
        sql.append(" LIMIT :lim")
        params["lim"] = limit
    with db.session_scope(cfg) as s:
        rows = s.execute(text("\n".join(sql)), params).mappings().all()
    return [dict(r) for r in rows]


_UPSERT_NORMALISED = text(
    """
    INSERT INTO products_normalised (
        source, source_ref, staging_id, parser_version, normaliser_version,
        page_kind, parent_source_ref, name, taxonomy, destination, description,
        attributes, unit_price, currency, available, available_from, available_to,
        image_url, images, latitude, longitude, quality_score,
        name_normalized, address, phone, star_rating, brand,
        destination_raw, dest_match_method, price_raw, fx_rate_used, quote_ctx
    ) VALUES (
        :source, :source_ref, :staging_id, :parser_version, :normaliser_version,
        :page_kind, :parent_source_ref, :name, :taxonomy, :destination, :description,
        CAST(:attributes AS jsonb), :unit_price, :currency, :available,
        :available_from, :available_to, :image_url, CAST(:images AS jsonb),
        :latitude, :longitude, :quality_score,
        :name_normalized, :address, :phone, :star_rating, :brand,
        :destination_raw, :dest_match_method, :price_raw, :fx_rate_used, :quote_ctx
    )
    ON CONFLICT (source, source_ref, normaliser_version) DO UPDATE SET
        staging_id = EXCLUDED.staging_id,
        parser_version = EXCLUDED.parser_version,
        page_kind = EXCLUDED.page_kind,
        parent_source_ref = EXCLUDED.parent_source_ref,
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
        images = EXCLUDED.images,
        latitude = EXCLUDED.latitude,
        longitude = EXCLUDED.longitude,
        quality_score = EXCLUDED.quality_score,
        name_normalized = EXCLUDED.name_normalized,
        address = EXCLUDED.address,
        phone = EXCLUDED.phone,
        star_rating = EXCLUDED.star_rating,
        brand = EXCLUDED.brand,
        destination_raw = EXCLUDED.destination_raw,
        dest_match_method = EXCLUDED.dest_match_method,
        price_raw = EXCLUDED.price_raw,
        fx_rate_used = EXCLUDED.fx_rate_used,
        quote_ctx = EXCLUDED.quote_ctx,
        normalised_at = now()
    """
)


def _upsert_normalised(cfg: Config, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    with db.session_scope(cfg) as s:
        for r in records:
            params = dict(r)
            params["attributes"] = json.dumps(
                r.get("attributes") or {}, ensure_ascii=False, default=str
            )
            params["images"] = json.dumps(r.get("images") or [], ensure_ascii=False)
            s.execute(_UPSERT_NORMALISED, params)


def _clear_rejects(cfg: Config, source: str, version: str) -> None:
    """Drop this source's previous normalise verdicts before re-normalising.

    A stale reject for a row that now normalises fine would keep reporting a
    lost product, which defeats the point of recording rejects at all.
    """
    with db.session_scope(cfg) as s:
        s.execute(
            text(
                "DELETE FROM normalise_rejects WHERE source = :s "
                "AND normaliser_version = :v AND reason <> 'load'"
            ),
            {"s": source, "v": version},
        )


def _reject(cfg: Config, row: dict, version: str, reason: str, detail: str) -> None:
    payload = row.get("payload") or {}
    excerpt = {
        k: payload.get(k)
        for k in ("source_ref", "name_raw", "taxonomy_hint", "category_raw")
    }
    with db.session_scope(cfg) as s:
        s.execute(
            text(
                "INSERT INTO normalise_rejects (source, source_ref, staging_id, "
                "normaliser_version, reason, detail, payload_excerpt) "
                "VALUES (:s, :ref, :sid, :v, :r, :d, CAST(:p AS jsonb))"
            ),
            {
                "s": row["source"],
                "ref": row.get("source_ref"),
                "sid": row["id"],
                "v": version,
                "r": reason,
                "d": detail[:2000],
                "p": json.dumps(excerpt, ensure_ascii=False, default=str),
            },
        )
    log.warning("rejected %s (%s): %s", row.get("source_ref"), reason, detail)


def _unknown_destination_count(cfg: Config, version: str) -> int:
    with db.session_scope(cfg) as s:
        return int(
            s.execute(
                text(
                    "SELECT count(*) FROM products_normalised "
                    "WHERE normaliser_version = :v AND destination = 'unknown'"
                ),
                {"v": version},
            ).scalar()
            or 0
        )


# =============================================================================
# small helpers
# =============================================================================
def _as_float(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # reject NaN


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    m = re.search(r"\d+", str(value).replace(",", "").replace(".", ""))
    return int(m.group()) if m else None


def _as_date(value: Any) -> dt.date | None:
    if not value:
        return None
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _first_number(value: Any) -> Any:
    if value in (None, ""):
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", str(value))
    return m.group().replace(",", ".") if m else None
