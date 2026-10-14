"""Pure grounding and scope checks for conversational answers (FR-AGT-06/07, NFR-REL-01)."""
from __future__ import annotations

import re
from copy import deepcopy

from .exploration import price, short_name
from .geo import coords, haversine_km
from .normalization import fold
from .planning import summary

PLACEHOLDER = re.compile(r"\[\[(price|hours|rating|reviews|stars|distance|price_diff):(?:(job\d+):)?(#\d+)\]\]")
FARE_BLOCK = re.compile(r"\[\[fare_block:(\d+)\]\]")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
# Product numbers must be supplied by a placeholder. References and product names inside links are exempt.
RAW_FACT = re.compile(r"(?:\d[\d., ]*\s*(?:₫|đồng|vnd|usd|đ\b|k\b|tr\b|triệu|nghìn|ngàn|trieu|nghin|ngan|đ/|sao\b|điểm\b|đánh giá|reviews?\b|stars?\b|km\b|kilomet|mét\b|metres?\b|%|h\b|giờ\b|phút\b|hours?\b|minutes?\b))|(?:\b\d{1,2}:\d{2}\b)|(?:\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b)", re.IGNORECASE)
UNKNOWN_PLACEHOLDER = re.compile(r"\[\[[^\]]+\]\]")
REASON_PHRASES = {"cheapest": ("rẻ nhất", "giá thấp nhất", "cheapest"),
                  "dearest": ("đắt nhất", "giá cao nhất", "most expensive"),
                  "top_rated": ("điểm cao nhất", "highest rated"),
                  "most_reviewed": ("nhiều đánh giá nhất", "nhiều người đánh giá nhất", "most reviewed")}


def _active(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row.get("status") not in ("failed", "superseded")]


def visible(rows: list[dict], codes: dict[str, str]) -> dict[str, list[tuple[dict, dict]]]:
    """Only products the model actually received in this turn's briefs."""
    registry: dict[str, list[tuple[dict, dict]]] = {}
    for row in _active(rows):
        products = {product["productId"]: product for product in row.get("products") or []}
        for ref in row.get("listed") or []:
            product = products.get(codes.get(ref))
            if product:
                registry.setdefault(ref, []).append((row, product))
    return registry


def in_scope(ref: str, row: dict, product: dict, seen: dict, rejected: list[str]) -> bool:
    spec = row.get("spec") or {}
    if ref in rejected or row.get("answer_only"):
        return False
    if row.get("kind") == "fare":
        return True
    if row.get("intent") == "about_shown":
        return ref in (spec.get("refers_to") or [])
    if spec.get("destination") and fold(product.get("destination")) != fold(spec["destination"]):
        return False
    if fold(product.get("destination")) in {fold(name) for name in spec.get("excluded_destinations") or []}:
        return False
    if spec.get("taxonomy") and product.get("taxonomy") != spec["taxonomy"]:
        return False
    if "query_ids" in row and product["productId"] not in row["query_ids"]:
        return False
    if row.get("intent") == "more":
        historical = (seen.get("seen") or {}).get(product["productId"])
        if historical and fold(historical.get("place")) == fold(product.get("destination")) \
                and historical.get("taxonomy") == product.get("taxonomy"):
            return False
        return not any(item.get("productId") == product["productId"]
                       and fold(item.get("place")) == fold(product.get("destination"))
                       and item.get("taxonomy") == product.get("taxonomy") for item in seen.get("items") or [])
    if row.get("intent") in ("cheaper", "dearer"):
        anchor = row.get("anchor_product") or {}
        base, value = price(anchor), price(product)
        if base is None or value is None or product.get("priceUnit") != anchor.get("priceUnit") \
                or product.get("currency") != anchor.get("currency"):
            return False
        return value < base if row["intent"] == "cheaper" else value > base
    return True


def requested_groups(rows: list[dict]) -> dict[int, dict]:
    """One target per source job; continuation aliases must not multiply the requested count."""
    groups = {}
    for row in rows:
        spec = row.get("spec") or {}
        count = spec.get("requested_count")
        if row.get("kind") == "explore" and row.get("intent") != "about_shown" \
                and row.get("status") != "superseded" and type(count) is int and count >= 1:
            groups[row.get("source_job", row["job"])] = {"count": min(20, count), "requested": count, "spec": spec}
    return groups


def raw_violations(text: str, known_refs=()) -> list[str]:
    stripped = LINK.sub(lambda match: "" if match.group(2) in known_refs else match.group(1),
                        PLACEHOLDER.sub("", FARE_BLOCK.sub("", text)))
    problems = ["raw_product_number"] if RAW_FACT.search(stripped) or re.search(r"(?:VND|USD|[$€£])\s*\d|\b\d{1,2}h\d{2}\b|\b\d+(?:[.,]\d+)?\s*/\s*(?:5|10)\b", stripped, re.IGNORECASE) else []
    if UNKNOWN_PLACEHOLDER.search(stripped):
        problems.append("unknown_placeholder")
    # Direct URLs/IDs are never accepted from the model, even when the text contains no price.
    if re.search(r"https?://|product:", stripped):
        problems.append("raw_product_link")
    return problems


def _money(value, language: str) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return ""
    return f"{value:,.0f} ₫".replace(",", ".") if language == "vi" else f"VND {value:,.0f}"


def _value(kind: str, row: dict, product: dict, language: str) -> str | None:
    attrs = product.get("attributes") or {}
    if kind == "price":
        if price(product) is None:
            return "tham quan tự do, không mất vé" if product.get("taxonomy") in ("attraction", "golf") and \
                (attrs.get("ticketed") is False or product.get("unitPrice") == 0) else ""
        unit = {"PER_NIGHT": "/đêm", "PER_PERSON": "/khách", "PER_PACKAGE": "/gói"} if language == "vi" else \
            {"PER_NIGHT": "/night", "PER_PERSON": "/person", "PER_PACKAGE": "/package"}
        return _money(product["unitPrice"], language) + unit.get(product.get("priceUnit"), "")
    if kind in ("rating", "reviews", "stars"):
        value = attrs.get("starRating") if kind == "stars" else product.get("reviewCount" if kind == "reviews" else "rating")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return ""
        suffix = {"rating": " điểm", "reviews": " đánh giá", "stars": " sao"} if language == "vi" else \
            {"rating": " rating", "reviews": " reviews", "stars": " stars"}
        return f"{value:g}" + suffix[kind]
    if kind == "hours":
        return str(attrs.get("openingHours") or "")
    anchor = row.get("anchor_product")
    if not anchor:
        return None
    if kind == "distance":
        origin, destination = coords(anchor), coords(product)
        if origin is None or destination is None:
            return ""
        return f"{haversine_km(origin, destination):.1f} km"
    if kind == "price_diff":
        if price(anchor) is None or price(product) is None or product.get("priceUnit") != anchor.get("priceUnit"):
            return None
        return _money(abs(price(product) - price(anchor)), language)
    return None


def inspect(turn: dict, rows: list[dict], codes: dict[str, str], language: str = "vi") -> dict:
    text = "\n".join(str(turn.get(key) or "") for key in ("title", "message"))
    text += "\n" + str((turn.get("offer") or {}).get("text") or "")
    registry = visible(rows, codes)
    problems = raw_violations(text, registry)
    unknown = set()
    if turn.get("action") == "ask" and not turn.get("question"):
        problems.append("ask_missing_question")
    if turn.get("action") == "answer" and "?" in str(turn.get("message") or "") and not turn.get("question"):
        problems.append("undeclared_question")
    for ref in turn.get("refers_to") or []:
        if ref not in registry:
            unknown.add(ref)
    for match in PLACEHOLDER.finditer(text):
        kind, job_key, ref = match.groups()
        entries = registry.get(ref, [])
        if not entries:
            unknown.add(ref)
            problems.append("placeholder_not_retrieved")
            continue
        if kind in ("distance", "price_diff") and not job_key:
            problems.append("comparison_missing_job")
            continue
        entries = [(row, product) for row, product in entries if not job_key or f"job{row['job']}" == job_key]
        values = {_value(kind, row, product, language) for row, product in entries}
        if len(values) != 1 or None in values:
            problems.append("ambiguous_placeholder")
    if unknown:
        problems.append("references_not_retrieved")
    return {"violations": sorted(set(problems)), "unknown_refs": sorted(unknown)}


def _one_question(body: str) -> str:
    """Keep one literal question mark; extra questions become statements, without interpreting intent."""
    first = body.find("?")
    return body if first < 0 else body[:first + 1] + body[first + 1:].replace("?", ".")


def render(turn: dict, rows: list[dict], codes: dict[str, str], *, seen: dict, language: str,
           rejected_refs: list[str] = (), rejected_destinations: list[str] = (), hotel_only: bool = False, fallback: bool = False) -> dict:
    """Select cards, replace verified placeholders, and insert all active code-written fare answers."""
    registry = visible(rows, codes)
    refs = list(turn.get("cards") or [])
    requests = requested_groups(rows)
    # When an explicit count was requested, fill remaining slots only with fresh, listed, eligible products.
    refs += [ref for ref, entries in registry.items()
             if any(row.get("source_job", row["job"]) in requests for row, _ in entries)]
    fare_rows = [row for row in _active(rows) if row.get("kind") == "fare"]
    answered = [row for row in fare_rows if row.get("status") in ("answered", "unavailable")]
    asked = [row for row in fare_rows if row.get("status") == "asked"]
    # Ensure primary flights from each answer take precedence over ancillary day cards.
    fare_refs = []
    for row in answered:
        linked_ids = [match.group(2).removeprefix("product:") for match in LINK.finditer(row.get("fare_block", ""))]
        fare_refs += [ref for product_id in linked_ids for ref, pid in codes.items() if pid == product_id and ref in registry]
    fare_refs += [ref for row in answered for ref in row.get("listed") or []]
    refs = fare_refs + refs if requests else refs + fare_refs
    products, selected, dropped = {}, [], []
    limits = {"attraction": 3, "hotel": 4 if hotel_only else 2, "combo": 4, "golf": 4, "flight": 4}
    requested_by_kind = {}
    for target in requests.values():
        kind = target["spec"].get("taxonomy")
        if kind:
            requested_by_kind[kind] = requested_by_kind.get(kind, 0) + target["count"]
        else:
            for kind in ("attraction", "hotel", "combo", "golf"):
                requested_by_kind[kind] = 20
    limits.update({kind: min(20, count) for kind, count in requested_by_kind.items()})
    counts: dict[str, int] = {}
    group_counts: dict[int, int] = {}
    for ref in dict.fromkeys(refs):
        entries = registry.get(ref, [])
        eligible = [(row, product) for row, product in entries if in_scope(ref, row, product, seen, rejected_refs)
                    and product.get("destination") not in rejected_destinations]
        if not eligible:
            dropped.append(ref)
            continue
        row, product = eligible[-1]
        root = row.get("source_job", row["job"])
        taxonomy = product["taxonomy"]
        if len(selected) >= 20 or counts.get(taxonomy, 0) >= limits.get(taxonomy, 0) \
                or (root in requests and group_counts.get(root, 0) >= requests[root]["count"]):
            dropped.append(ref)
            continue
        products[ref] = product
        selected.append(ref)
        counts[taxonomy] = counts.get(taxonomy, 0) + 1
        group_counts[root] = group_counts.get(root, 0) + 1
    text = str(turn.get("message") or "")
    if fallback:
        text = "\n".join(f"Bạn có thể xem [{short_name(product).lstrip('-–| ').strip()}]({ref})." if language == "vi" else
                         f"You can explore [{short_name(product).lstrip('-–| ').strip()}]({ref})." for ref, product in products.items()
                         if product.get("taxonomy") != "flight")
        if not text and not fare_rows:
            text = "Mình chưa tra được thêm dữ liệu phù hợp; bạn có thể đổi nơi hoặc hỏi cụ thể hơn." if language == "vi" else \
                "I could not retrieve more matching data; try another destination or a more specific question."
    prefill = deepcopy(turn)
    prefill["message"] = text

    def fill(match):
        kind, job_key, ref = match.groups()
        entries = [(row, product) for row, product in registry.get(ref, []) if not job_key or f"job{row['job']}" == job_key]
        values = {_value(kind, row, product, language) for row, product in entries}
        return next(iter(values)) or "" if len(values) == 1 and None not in values else ""

    # price already includes the catalog unit; remove a model-added unit before filling it.
    text = re.sub(r"(\[\[price:(?:job\d+:)?#\d+\]\])\s*/(?:đêm|khách|người|gói|night|person|package)\b", r"\1", text, flags=re.IGNORECASE)
    text = PLACEHOLDER.sub(fill, text)
    # A comparative label is allowed only on a linked reference carrying that code-computed label.
    lines = []
    for line in text.splitlines():
        mentioned = [match.group(2) for match in LINK.finditer(line) if match.group(2) in registry]
        labels = {label for ref in mentioned for row, _ in registry[ref] for label in (row.get("reasons") or {}).get(ref, [])} if len(mentioned) == 1 else set()
        for reason, phrases in REASON_PHRASES.items():
            if reason not in labels:
                for phrase in phrases:
                    line = re.sub(re.escape(phrase), "phù hợp" if language == "vi" else "matching", line, flags=re.IGNORECASE)
        lines.append(line)
    text = "\n".join(lines)

    def relink(match):
        ref = match.group(2)
        product = products.get(ref)
        if product:
            return f"[{short_name(product).lstrip('-–| ').strip()}](product:{product['productId']})"
        if ref in registry:
            return short_name(registry[ref][-1][1]).lstrip('-–| ').strip()
        return match.group(1)

    text = LINK.sub(relink, text)
    # Each non-flight card needs its own lead-in at its first mention.
    for ref, product in products.items():
        if product.get("taxonomy") != "flight" and f"(product:{product['productId']})" not in text:
            text += ("\nBạn có thể xem " if language == "vi" else "\nYou can explore ") + \
                f"[{short_name(product).lstrip('-–| ').strip()}](product:{product['productId']})."
    # Only one fare question survives; its buttons go first, and the rest wait exactly one turn.
    question_row = min(asked, key=lambda row: row["job"]) if asked else None
    blocks = {row["job"]: row.get("fare_block", "") for row in answered}
    if question_row:
        blocks[question_row["job"]] = question_row.get("fare_block", "")
        text = text.replace("?", ".")
    seen_blocks = set()

    def insert(match):
        number = int(match.group(1))
        if number not in blocks or number in seen_blocks:
            return ""
        seen_blocks.add(number)
        return blocks[number]

    text = FARE_BLOCK.sub(insert, text)
    for number, block in blocks.items():
        if number not in seen_blocks:
            text += "\n\n" + block
    # Code fare links remain canonical; they refer to verified active jobs even when card slots are full.
    suggestions = list(question_row.get("suggestions") or []) if question_row else []
    suggestions += list(turn.get("suggestions") or [])
    waiting = [deepcopy(row["spec"]) for row in asked if row is not question_row]
    pending = question_row.get("pending_fare") if question_row else fare_rows[-1].get("pending_fare") if fare_rows else None
    grouped: dict[str, list[dict]] = {}
    for ref in selected:
        product = products[ref]
        grouped.setdefault(product["taxonomy"], []).append(summary(product))
    fare_ids = [product["productId"] for row in fare_rows for product in row.get("products") or []]
    return {"body": _one_question(text.strip()), "searchResults": grouped, "selected": selected,
            "dropped": dropped, "suggestions": suggestions[:3], "waiting_jobs": waiting,
            "pending_fare": pending, "fare_question": bool(question_row), "prefill": prefill,
            "fare_ids": fare_ids, "shortfalls": [{"job": root, "requested": target["count"],
                "selected": group_counts.get(root, 0), "spec": target["spec"]} for root, target in requests.items()
                if group_counts.get(root, 0) < target["count"]]}
