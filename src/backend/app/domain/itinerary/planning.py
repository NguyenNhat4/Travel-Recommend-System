"""Deterministic itinerary construction and grounding rules."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from typing import Any

from .normalization import strip_accents

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
    "reviewCount", "attributes", "description", "priceUnit",
)
# Flights and combos have no confirmed slot mapping, so they can be retrieved but never scheduled.
STAY_TAXONOMY = "hotel"
SLOT_TAXONOMIES = frozenset({"attraction", "golf"})
SCHEDULABLE_TAXONOMIES = frozenset({STAY_TAXONOMY, *SLOT_TAXONOMIES})


def normalized(value: str | None) -> str:
    """Accent- and case-insensitive comparison key for names and destinations."""
    return " ".join(strip_accents((value or "").casefold()).split())


def empty_intent() -> dict[str, Any]:
    return {"destination": None, "startDate": None, "days": None, "party": None,
            "budget": None, "interests": [], "pace": None}


def merge_intent(current: dict[str, Any] | None, patch: dict[str, Any] | None) -> dict[str, Any]:
    result = deepcopy(current or empty_intent())
    for key, value in (patch or {}).items():
        if value is not None:
            result[key] = deepcopy(value)
    return result


def summary(product: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(product, dict):
        return {}
    return {key: deepcopy(product[key]) for key in SUMMARY_FIELDS if key in product}


def parse_day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def allowed_times(product: dict[str, Any]) -> list[str]:
    duration = product.get("attributes", {}).get("durationMinutes")
    return ["MORNING"] if isinstance(duration, (int, float)) and duration >= 360 else ["MORNING", "NOON", "AFTERNOON", "EVENING"]


def _source(value: str | None) -> str:
    return "RECOMMENDATION" if value == "recommendation" else "SEARCH"


def _because(product: dict[str, Any], source: str | None) -> list[dict[str, Any]]:
    return deepcopy(product.get("because", [])) if source == "recommendation" else []


def _known_cost(product: dict[str, Any], *, nights: int, party: dict[str, Any] | None) -> int | None:
    price, unit = product.get("unitPrice"), product.get("priceUnit", "UNKNOWN")
    if price is None or unit == "UNKNOWN":
        return None
    if unit == "PER_NIGHT":
        return int(price * nights) if party is not None else None
    if unit == "PER_PERSON":
        return int(price * (party["adults"] + party["children"])) if party is not None else None
    return int(price) if unit == "PER_PACKAGE" else None


def totals(plan: dict[str, Any], intent: dict[str, Any]) -> tuple[int | None, str]:
    products: list[tuple[dict[str, Any], int]] = []
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


def render_proposal(proposal: dict[str, Any], candidates: dict[str, dict[str, Any]],
                    sources: dict[str, str], intent: dict[str, Any]) -> dict[str, Any]:
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
    plan: dict[str, Any] = {**({"stay": stay} if stay else {}), "days": days,
        "bookableCount": len(used), "estimatedTotal": None, "currency": "VND",
        "budgetStatus": "UNKNOWN", "priceAsOf": None}
    plan["estimatedTotal"], plan["budgetStatus"] = totals(plan, intent)
    return plan


def render_best_effort(proposal: dict[str, Any], candidates: dict[str, dict[str, Any]],
                       sources: dict[str, str], intent: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Render the proposal, dropping only the slots the rules reject.

    One unschedulable slot must not discard an otherwise valid itinerary. Slots are added one at a
    time and kept only when the plan still renders, so the result obeys exactly the same rules as
    `render_proposal`; nothing is relaxed. Returns the plan and the slots that were dropped. A
    proposal-level failure (trip duration, stay) still raises, and `validate_plan` remains the final
    word on required-hotel and grounding rules.
    """
    try:
        return render_proposal(proposal, candidates, sources, intent), []
    except ValueError:
        pass
    # An id that is in no retrieval result means the model invented it. That is a grounding failure
    # about the whole proposal, not one bad slot, so it is never repaired away quietly.
    if any(slot.get("product_id") and slot["product_id"] not in candidates
           for slot in proposal.get("slots", [])):
        raise ValueError("ungrounded product selection")
    base = {"stay_id": proposal.get("stay_id"), "slots": []}
    render_proposal(base, candidates, sources, intent)  # duration or stay problems are not repairable
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for slot in proposal.get("slots", []):
        try:
            render_proposal({**base, "slots": [*kept, slot]}, candidates, sources, intent)
        except ValueError:
            dropped.append(slot)
        else:
            kept.append(slot)
    return render_proposal({**base, "slots": kept}, candidates, sources, intent), dropped


def validate_plan(plan: dict[str, Any], candidates: dict[str, dict[str, Any]],
                  sources: dict[str, str], intent: dict[str, Any], constraints: dict[str, Any]) -> list[str]:
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
    deliberately_uncertified = (
        intent.get("budget") is not None
        and plan.get("estimatedTotal") is None
        and plan.get("budgetStatus") == "UNKNOWN"
    )
    if not deliberately_uncertified and (
        plan.get("estimatedTotal") != expected_total or plan.get("budgetStatus") != expected_status
    ):
        issues.append("total")
    return sorted(set(issues))


def estimate_total(plan: dict[str, Any]) -> int | None:
    values = [slot["product"].get("unitPrice") for day in plan.get("days", [])
              for slot in day.get("slots", []) if slot.get("product")]
    return None if any(value is None for value in values) else int(sum(values))
