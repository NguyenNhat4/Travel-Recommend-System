"""Deterministic itinerary construction and grounding rules."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import re
from typing import Any

from .normalization import strip_accents
from .types import Candidates, Constraints, Party, Plan, Product, Proposal, Sources, TripIntent

NOTES = {
    "VISIT": "Tham quan theo khung giờ đề xuất.",
    "RELAX": "Dành thời gian nghỉ ngơi và thư giãn.",
    "FAMILY": "Hoạt động phù hợp để gia đình cùng trải nghiệm.",
    "REST": "Nghỉ ngơi để giữ lịch trình thoải mái.",
    "MEAL": "Tự do dùng bữa; chưa gắn với sản phẩm đặt chỗ.",
    "TRANSFER": "Di chuyển giữa các điểm trong lịch trình.",
}
SUMMARY_FIELDS = (
    "productId", "name", "taxonomy", "destination", "unitPrice", "currency",
    "available", "availableFrom", "availableTo", "imageUrl", "rating",
    "reviewCount", "attributes", "priceUnit",
)
# `attributes` chỉ giữ khoá FE thật sự đọc trong lịch trình (docs/spec/agent/field-review.md §2.1);
# nguồn đầy đủ vẫn ở `candidates`/`ProductDetail`, không mất dữ liệu.
SUMMARY_ATTRIBUTE_KEYS = frozenset({"oceanView", "privateBeach", "pool", "ticketed"})
# Flights and combos have no confirmed slot mapping, so they can be retrieved but never scheduled.
STAY_TAXONOMY = "hotel"
SLOT_TAXONOMIES = frozenset({"attraction", "golf"})
SCHEDULABLE_TAXONOMIES = frozenset({STAY_TAXONOMY, *SLOT_TAXONOMIES})
# Pace is not a scheduling input yet; this is the cap the itinerary has always been held to.
MAX_ACTIVITIES_PER_DAY = 2
# Multi-day passes and tours ("[03 ngày không giới hạn] - VinWonders + Safari", "4D3N", "Thẻ Hội Viên 90 ngày")
# cannot fit one slot of one day; they are offered next to the itinerary for the user to consider separately.
MULTI_DAY_MINUTES = 2 * 24 * 60
_SPAN_PATTERNS = (
    re.compile(r"(\d{1,3})[\s-]*(?:ngày|ngay|days?)\b", re.IGNORECASE),
    re.compile(r"(\d{1,2})\s*D\s*\d{1,2}\s*N\b"),
    re.compile(r"(\d{1,2})\s*N\s*\d{1,2}\s*Đ\b", re.IGNORECASE),
)


def normalized(value: str | None) -> str:
    """Accent- and case-insensitive comparison key for names and destinations."""
    return " ".join(strip_accents((value or "").casefold()).split())


def empty_intent() -> TripIntent:
    return {"destination": None, "startDate": None, "days": None, "party": None,
            "budget": None, "interests": [], "pace": None}


def merge_intent(current: TripIntent | None, patch: TripIntent | None) -> TripIntent:
    result = deepcopy(current or empty_intent())
    for key, value in (patch or {}).items():
        if value is not None:
            result[key] = deepcopy(value)
    return result


def summary(product: Product) -> Product:
    if not isinstance(product, dict):
        return {}
    result = {key: deepcopy(product[key]) for key in SUMMARY_FIELDS if key in product}
    attributes = {key: value for key, value in result.get("attributes", {}).items()
                 if key in SUMMARY_ATTRIBUTE_KEYS}
    if attributes:
        result["attributes"] = attributes
    else:
        result.pop("attributes", None)
    return result


def parse_day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def allowed_times(product: Product) -> list[str]:
    duration = product.get("attributes", {}).get("durationMinutes")
    return ["MORNING"] if isinstance(duration, (int, float)) and duration >= 360 else ["MORNING", "NOON", "AFTERNOON", "EVENING"]


def multi_day_span(product: Product) -> int | None:
    """Number of days a pass or tour covers when it is two or more, else None.

    Read from `durationMinutes` (two days or more) or from the name ("03 ngày", "2 Day", "4D3N", "3N2Đ").
    "[01 ngày]" and a full-day tour are single-day and stay schedulable.
    """
    duration = product.get("attributes", {}).get("durationMinutes")
    spans = [int(duration // (24 * 60))] if isinstance(duration, (int, float)) and duration >= MULTI_DAY_MINUTES else []
    for pattern in _SPAN_PATTERNS:
        spans.extend(int(match.group(1)) for match in pattern.finditer(product.get("name") or ""))
    longest = max(spans, default=0)
    return longest if longest >= 2 else None


def multi_day_offers(candidates: Candidates, sources: Sources) -> list[Product]:
    """Available multi-day passes/tours, never put in a slot: shown for the user to consider separately."""
    offers = [product for product in candidates.values()
              if product.get("available") and product.get("taxonomy") in SLOT_TAXONOMIES and multi_day_span(product)]
    return sorted(offers, key=lambda product: (_source_rank(sources, product), *_price_key(product), product["productId"]))


def _source(value: str | None) -> str:
    return "RECOMMENDATION" if value == "recommendation" else "SEARCH"


def _because(product: Product, source: str | None) -> list[dict[str, Any]]:
    return deepcopy(product.get("because", [])) if source == "recommendation" else []


def free_to_visit(product: Product) -> bool:
    """Điểm tham quan tự do: nguồn ghi `ticketed=false`, hoặc điểm tham quan/golf không có giá.

    Người dùng chốt 01/10/2026: điểm không có giá là nơi vào chơi tự do (bãi biển, thắng cảnh), nên tính 0 đ vào tổng
    và hiển thị "tham quan tự do" (`docs/prd/architecture.md` §3). Khách sạn, vé máy bay, combo thiếu giá vẫn là chưa biết.
    """
    if (product.get("attributes") or {}).get("ticketed") is False:
        return True
    return product.get("unitPrice") is None and product.get("taxonomy") in SLOT_TAXONOMIES


def _known_cost(product: Product, *, nights: int, party: Party | None) -> int | None:
    if free_to_visit(product):
        return 0
    price, unit = product.get("unitPrice"), product.get("priceUnit", "UNKNOWN")
    if price is None or unit == "UNKNOWN":
        return None
    if unit == "PER_NIGHT":
        return int(price * nights) if party is not None else None
    if unit == "PER_PERSON":
        return int(price * (party["adults"] + party["children"])) if party is not None else None
    return int(price) if unit == "PER_PACKAGE" else None


def totals(plan: Plan, intent: TripIntent) -> tuple[int | None, str]:
    products: list[tuple[Product, int]] = []
    if plan.get("stay"):
        products.append((plan["stay"]["product"], plan["stay"]["nights"]))
    products.extend((slot["product"], 1) for day in plan.get("days", [])
                    for slot in day.get("slots", []) if slot.get("product") is not None)
    amounts = [_known_cost(product, nights=nights, party=intent.get("party")) for product, nights in products]
    if any(amount is None for amount in amounts):
        return None, "UNKNOWN"
    total = sum(amounts)
    budget = intent.get("budget")
    if budget is None:
        return total, "NO_BUDGET"
    return total, "WITHIN_BUDGET" if total <= budget else "OVER_BUDGET"


def _parent_key(product: Product) -> str:
    return product.get("attributes", {}).get("parentProductId") or product["productId"]


def _price_key(product: Product) -> tuple[int, float]:
    """Cheapest first; an unknown price cannot be compared, so it goes last."""
    price = product.get("unitPrice")
    return (1, 0.0) if price is None else (0, float(price))


def _source_rank(sources: Sources, product: Product) -> int:
    # Search (and Similar, which also carries source "search") is preferred over Recommendation:
    # a recommended item only fills a slot/stay when no searched candidate is available for it.
    return 0 if sources.get(product["productId"]) != "recommendation" else 1


def _stay_order(sources: Sources, product: Product) -> tuple[Any, ...]:
    star = product.get("attributes", {}).get("starRating")
    return (_source_rank(sources, product), *_price_key(product),
            -(star if isinstance(star, (int, float)) else -1), product["productId"])


def _activity_order(sources: Sources, product: Product) -> tuple[Any, ...]:
    # A full-day item needs a day to itself, so it is placed before anything that can share one.
    return (_source_rank(sources, product), 0 if allowed_times(product) == ["MORNING"] else 1,
            *_price_key(product), product["productId"])


def compose_plan(candidates: Candidates, sources: Sources, intent: TripIntent) -> Proposal:
    """Choose products and lay them out on days with fixed rules. No model is involved.

    Ordering is total and depends only on product data and source, so the same candidates always
    produce the same proposal. Search-sourced candidates are always chosen over Recommendation-sourced
    ones for the same slot; a recommendation only fills a slot/stay left empty by Search. The result is
    fed to `render_proposal`, which still enforces every rule; this function only has to avoid
    proposing something the renderer would reject.
    """
    days_count = intent.get("days")
    if not isinstance(days_count, int) or days_count < 1:  # upper bound is enforced by TripIntent
        raise ValueError("invalid trip duration")
    usable = [product for product in candidates.values() if product.get("available")]
    stays = sorted((p for p in usable if p.get("taxonomy") == STAY_TAXONOMY),
                   key=lambda product: _stay_order(sources, product))
    stay = stays[0] if stays else None
    taken = {_parent_key(stay), stay["productId"]} if stay else set()
    activities: list[Product] = []
    for product in sorted((p for p in usable if p.get("taxonomy") in SLOT_TAXONOMIES and not multi_day_span(p)),
                          key=lambda product: _activity_order(sources, product)):
        key = _parent_key(product)
        if key in taken or product["productId"] in taken:
            continue
        taken.update({key, product["productId"]})
        activities.append(product)
    per_day: list[list[Product]] = [[] for _ in range(days_count)]
    full_days: set[int] = set()
    for product in activities:
        full_day = allowed_times(product) == ["MORNING"]
        # Spread across the trip instead of filling day one: least loaded day wins, earliest breaks ties.
        open_days = [index for index in range(days_count)
                     if not per_day[index] or (not full_day and index not in full_days
                                               and len(per_day[index]) < MAX_ACTIVITIES_PER_DAY)]
        if full_day:
            open_days = [index for index in open_days if not per_day[index]]
        if not open_days:
            continue  # more activities than the trip can hold; the extras are simply not scheduled
        index = min(open_days, key=lambda day: (len(per_day[day]), day))
        if full_day:
            full_days.add(index)
        per_day[index].append(product)
    slots = []
    for index, products in enumerate(per_day):
        for position, product in enumerate(products):
            times = allowed_times(product)
            slots.append({"day": index + 1, "note_kind": "VISIT", "activity_type": None,
                          "product_id": product["productId"],
                          "time": times[0] if len(times) == 1 else ("MORNING" if position == 0 else "AFTERNOON")})
    return {"stay_id": stay["productId"] if stay else None, "slots": slots}


def render_proposal(proposal: Proposal, candidates: Candidates,
                    sources: Sources, intent: TripIntent) -> Plan:
    days_count = intent.get("days")
    if not isinstance(days_count, int) or days_count < 1:  # upper bound is enforced by TripIntent
        raise ValueError("invalid trip duration")
    start = parse_day(intent.get("startDate"))
    days = [{"day": number,
             **({"date": (start + timedelta(days=number - 1)).isoformat()} if start else {}),
             "slots": []} for number in range(1, days_count + 1)]
    used: set[str] = set()
    parent_keys: set[str] = set()
    stay = None
    stay_id = proposal.get("stay_id")
    if stay_id:
        product = candidates.get(stay_id)
        if product is None or product.get("taxonomy") != STAY_TAXONOMY:
            raise ValueError("invalid stay")
        used.add(stay_id)
        parent_keys.add(product.get("attributes", {}).get("parentProductId") or stay_id)
        stay = {"product": summary(product), "nights": max(1, days_count - 1),
                "note": NOTES["RELAX"], "source": _source(sources.get(stay_id)),
                "because": _because(product, sources.get(stay_id))}
    occupied_full_days: set[int] = set()
    for proposed in proposal.get("slots", []):
        day_number = proposed.get("day")
        if not isinstance(day_number, int) or not 1 <= day_number <= days_count:
            raise ValueError("invalid day")
        product_id, note_kind = proposed.get("product_id"), proposed.get("note_kind", "VISIT")
        if note_kind not in NOTES:
            raise ValueError("invalid note")
        if product_id is None:
            if not proposed.get("activity_type"):
                raise ValueError("activity type required")
            days[day_number - 1]["slots"].append({"time": proposed["time"],
                "activityType": proposed["activity_type"], "product": None,
                "note": NOTES[note_kind], "source": None, "because": []})
            continue
        product = candidates.get(product_id)
        if product is None or product_id in used or product.get("taxonomy") not in SLOT_TAXONOMIES:
            raise ValueError("invalid product selection")
        parent = product.get("attributes", {}).get("parentProductId") or product_id
        if parent in parent_keys or product_id in parent_keys:
            raise ValueError("duplicate parent selection")
        duration = product.get("attributes", {}).get("durationMinutes")
        if day_number in occupied_full_days or (isinstance(duration, (int, float)) and duration >= 360 and days[day_number - 1]["slots"]):
            raise ValueError("full-day overlap")
        if isinstance(duration, (int, float)) and duration >= 360:
            occupied_full_days.add(day_number)
        used.add(product_id)
        parent_keys.add(parent)
        source = sources.get(product_id)
        days[day_number - 1]["slots"].append({"time": proposed["time"], "activityType": None,
            "product": summary(product), "note": NOTES[note_kind], "source": _source(source),
            "because": _because(product, source)})
    plan: Plan = {**({"stay": stay} if stay else {}), "days": days,
        "bookableCount": len(used), "estimatedTotal": None, "currency": "VND",
        "budgetStatus": "UNKNOWN", "priceAsOf": None}
    plan["estimatedTotal"], plan["budgetStatus"] = totals(plan, intent)
    return plan


def validate_plan(plan: Plan, candidates: Candidates,
                  sources: Sources, intent: TripIntent, constraints: Constraints) -> list[str]:
    issues: list[str] = []
    days = plan.get("days")
    if not isinstance(days, list) or [day.get("day") for day in days] != list(range(1, (intent.get("days") or 0) + 1)):
        return ["days"]
    selected = ([plan["stay"]["product"]] if plan.get("stay") else []) + [
        slot["product"] for day in days for slot in day.get("slots", []) if slot.get("product")]
    seen: set[str] = set()
    for product in selected:
        product_id = product.get("productId")
        source = candidates.get(product_id)
        if source is None or product != summary(source):
            issues.append("grounding")
            continue
        if product_id in seen:
            issues.append("duplicate_product")
        seen.add(product_id)
        if normalized(product.get("destination")) != normalized(intent.get("destination")):
            issues.append("destination")
        if not product.get("available"):
            issues.append("availability")
    for day in days:
        paid = [slot for slot in day.get("slots", []) if slot.get("product")]
        for slot in day.get("slots", []):
            if slot.get("note") not in NOTES.values():
                issues.append("note")
        if any(slot["product"].get("attributes", {}).get("durationMinutes", 0) >= 360 for slot in paid) and len(paid) > 1:
            issues.append("schedule")
    if constraints.get("require_hotel") and not plan.get("stay"):
        issues.append("required_hotel")
    expected_total, expected_status = totals(plan, intent)
    if plan.get("estimatedTotal") != expected_total or plan.get("budgetStatus") != expected_status:
        issues.append("total")
    return sorted(set(issues))


def estimate_total(plan: Plan) -> int | None:
    values = [slot["product"].get("unitPrice") for day in plan.get("days", [])
              for slot in day.get("slots", []) if slot.get("product")]
    return None if any(value is None for value in values) else int(sum(values))
