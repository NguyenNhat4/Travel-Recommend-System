"""Kiểm lịch do orc phác (assistant v2, AC-AGT-02/04): không chọn, thêm, bớt hay thay sản phẩm.

Trả vi phạm (orc phải sửa, lịch chưa dùng được) và cảnh báo (lịch dùng được nhưng phải nói cho khách). Vượt ngân
sách chỉ là cảnh báo. Thiếu giá không phải miễn phí: tổng là None và các mã thiếu giá nằm ở `unpriced_refs`.
"""
from __future__ import annotations

from datetime import date, timedelta
from itertools import permutations
import re
from typing import Any

from ..booking.party import MAX_ROOMS
from .flights import flight_date
from .geo import haversine_km, located
from .planning import stay_rooms

ACTIVITY_TAXONOMIES = {"attraction", "golf", "combo"}
ARRIVAL_BUFFER_MINUTES = 90      # hoạt động ngày đến bắt đầu sau hạ cánh ít nhất 90 phút
DEPARTURE_BUFFER_MINUTES = 150   # hoạt động ngày về kết thúc trước cất cánh ít nhất 150 phút
_HOURS = re.compile(r"\s*([01]?\d|2[0-3]):([0-5]\d)\s*[-–]\s*([01]?\d|2[0-3]):([0-5]\d)\s*")


def cost_mode(product: dict[str, Any]) -> str:
    """free chỉ khi có căn cứ (giá 0 hoặc nguồn ghi không bán vé); thiếu giá là unknown, không phải free."""
    if product.get("unitPrice") == 0 or (product.get("attributes") or {}).get("ticketed") is False:
        return "free"
    return "unknown" if product.get("unitPrice") is None else "paid"


def _opening_hours(product: dict[str, Any]) -> tuple[int, int] | None:
    """Khung giờ mở cửa dạng một khoảng HH:MM-HH:MM duy nhất; dạng khác coi như chưa biết."""
    match = _HOURS.fullmatch(str((product.get("attributes") or {}).get("openingHours") or ""))
    if not match:
        return None
    start, end = int(match[1]) * 60 + int(match[2]), int(match[3]) * 60 + int(match[4])
    return (start, end) if start < end else None


def _open_on(product: dict[str, Any], day: date) -> bool | None:
    """Ngày đó đặt/vào được không: cửa sổ bán và lịch trống (`attributes.availability`); None khi không có dữ liệu."""
    if cost_mode(product) == "free":
        return True
    try:
        if product.get("availableFrom") and day < date.fromisoformat(product["availableFrom"]):
            return False
        if product.get("availableTo") and day > date.fromisoformat(product["availableTo"]):
            return False
        calendar = (product.get("attributes") or {}).get("availability") or {}
        index = (day - date.fromisoformat(calendar["from"])).days
        return calendar["calendar"][index] == "1" if 0 <= index < len(calendar["calendar"]) else None
    except (KeyError, TypeError, ValueError):
        return None


def _activity_cost(product: dict[str, Any], people: int) -> int | None:
    """Tiền một hoạt động cho cả đoàn; None khi chưa biết giá hoặc đơn vị giá."""
    if cost_mode(product) == "free":
        return 0
    price, unit = product.get("unitPrice"), product.get("priceUnit")
    if price is None:
        return None
    return int(price * people) if unit == "PER_PERSON" else int(price) if unit == "PER_PACKAGE" else None


def _clock(value: Any) -> int | None:
    """Phút trong ngày của "HH:MM" hoặc ISO datetime."""
    text = str(value or "")
    text = text[11:16] if "T" in text else text[:5]
    try:
        hours, minutes = map(int, text.split(":"))
    except ValueError:
        return None
    return hours * 60 + minutes if 0 <= hours < 24 and 0 <= minutes < 60 else None


def _reorder(day: dict, products: dict[str, dict], locked: set[str]) -> list[dict] | None:
    """Đổi thứ tự hoạt động trong ngày cho quãng đường chim bay ngắn nhất, giữ nguyên các khung giờ.

    Chỉ làm khi ≥ 3 hoạt động, không có mã khoá, mọi khung cùng độ dài (hoán đổi được) và đủ toạ độ; không làm được
    thì None. Hoán đổi nào phạm giờ mở cửa đã biết thì bỏ qua.
    """
    activities = day["activities"]
    refs = [a["product_ref"] for a in activities]
    if len(refs) < 3 or len(set(refs)) < len(refs) or locked & set(refs):
        return None
    if len({a["end_minute"] - a["start_minute"] for a in activities}) != 1:
        return None
    points = located(products[ref] for ref in refs)
    if any(products[ref]["productId"] not in points for ref in refs):
        return None
    where = {ref: points[products[ref]["productId"]] for ref in refs}
    slots = [(a["start_minute"], a["end_minute"]) for a in activities]

    def fits(order: tuple[str, ...]) -> bool:
        for ref, (start, end) in zip(order, slots):
            hours = _opening_hours(products[ref])
            if hours and not hours[0] <= start < end <= hours[1]:
                return False
        return True

    def length(order: tuple[str, ...]) -> float:
        return sum(haversine_km(where[a], where[b]) for a, b in zip(order, order[1:]))

    best = min((order for order in permutations(refs) if fits(order)), key=length, default=tuple(refs))
    if length(best) >= length(tuple(refs)) - 0.01:
        return []
    by_ref = {a["product_ref"]: a for a in activities}
    day["activities"] = [{**by_ref[ref], "start_minute": start, "end_minute": end}
                         for ref, (start, end) in zip(best, slots)]
    return [{"product_ref": ref, "day_index": day["day_index"], "from_start_minute": by_ref[ref]["start_minute"],
             "to_start_minute": start} for ref, (start, _) in zip(best, slots) if by_ref[ref]["start_minute"] != start]


def check_draft(draft: dict[str, Any], products: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Kiểm `draft` (tham số build_itinerary) với `products` (ref → sản phẩm tra trong lượt)."""
    violations: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}

    def flag(target: dict, code: str, ref: str | None = None) -> None:
        refs = target.setdefault(code, [])
        if ref and ref not in refs:
            refs.append(ref)

    start = date.fromisoformat(draft["start_date"])
    last_day = start + timedelta(days=draft["days"] - 1)
    party = {"adults": draft["adults"], "children": draft["children"]}
    people = draft["adults"] + draft["children"]
    days = sorted(([{**d, "activities": list(d["activities"])} for d in draft["plan_days"]]),
                  key=lambda d: d["day_index"])
    if [d["day_index"] for d in days] != list(range(1, draft["days"] + 1)):
        flag(violations, "DAYS_MISMATCH")
    if not products:
        flag(violations, "EMPTY_PLAN")  # lịch không có sản phẩm nào không phải là lịch

    changes, skipped = [], False
    if draft["optimize"] == "reorder_within_day":
        for day in days:
            moved = _reorder(day, products, set(draft["locked_refs"]))
            skipped = skipped or (moved is None and len(day["activities"]) >= 3)
            changes += moved or []
        if skipped or not changes:
            flag(warnings, "OPTIMIZATION_UNAVAILABLE")

    subtotal, unpriced = 0, []

    def charge(ref: str, amount: int | None) -> None:
        nonlocal subtotal
        if amount is None:
            unpriced.append(ref)
        else:
            subtotal += amount

    places: set[str] = set()
    for day in days:
        when = start + timedelta(days=day["day_index"] - 1)
        periods = []
        if len(day["activities"]) > 1:
            flag(warnings, "TRAVEL_TIME_UNKNOWN")
        for activity in day["activities"]:
            ref, product = activity["product_ref"], products[activity["product_ref"]]
            begin, end = activity["start_minute"], activity["end_minute"]
            if product["taxonomy"] not in ACTIVITY_TAXONOMIES:
                flag(violations, "WRONG_TAXONOMY", ref)
            if product.get("destination") != draft["destination"]:
                flag(violations, "WRONG_DESTINATION", ref)
            place = (product.get("attributes") or {}).get("parentProductId") or product["productId"]
            if place in places:
                flag(violations, "DUPLICATE_PLACE", ref)
            places.add(place)
            if end <= begin:
                flag(violations, "INVALID_TIME", ref)
            if any(begin < other_end and end > other_start for other_start, other_end in periods):
                flag(violations, "TIME_OVERLAP", ref)
            periods.append((begin, end))
            if activity["timing_source"] == "estimate":
                flag(warnings, "TIMING_ESTIMATED", ref)
                if not activity["assumption"]:
                    flag(violations, "MISSING_ASSUMPTION", ref)
            else:
                duration = (product.get("attributes") or {}).get("durationMinutes")
                if not isinstance(duration, int) or isinstance(duration, bool):
                    flag(violations, "SOURCE_DURATION_UNKNOWN", ref)
                elif end - begin < duration:
                    flag(violations, "DURATION_TOO_SHORT", ref)
            hours = _opening_hours(product)
            if hours is None:
                flag(warnings, "OPENING_HOURS_UNKNOWN", ref)
            elif begin < hours[0] or end > hours[1]:
                flag(violations, "OUTSIDE_OPENING_HOURS", ref)
            if (product.get("available") is False and cost_mode(product) != "free") or _open_on(product, when) is False:
                flag(violations, "DATE_UNAVAILABLE", ref)
            if draft["free_only"] and cost_mode(product) != "free":
                flag(violations, "NOT_FREE", ref)
            charge(ref, _activity_cost(product, people))

    nights_taken: set[date] = set()
    for stay in draft["stays"]:
        ref, product = stay["product_ref"], products[stay["product_ref"]]
        check_in, check_out = date.fromisoformat(stay["check_in"]), date.fromisoformat(stay["check_out"])
        nights = [check_in + timedelta(days=n) for n in range((check_out - check_in).days)]
        if product["taxonomy"] != "hotel":
            flag(violations, "WRONG_TAXONOMY", ref)
        if product.get("destination") != draft["destination"]:
            flag(violations, "WRONG_DESTINATION", ref)
        if not nights or check_in < start or check_out > last_day + timedelta(days=1):
            flag(violations, "STAY_DATES", ref)
        if nights_taken & set(nights):
            flag(violations, "STAY_OVERLAP", ref)
        nights_taken |= set(nights)
        if product.get("available") is False or any(_open_on(product, night) is False for night in nights):
            flag(violations, "DATE_UNAVAILABLE", ref)
        rooms = stay_rooms(product, party)
        if rooms is None:
            flag(warnings, "PRICE_CAPACITY_UNKNOWN", ref)
        elif rooms > MAX_ROOMS:
            flag(violations, "TOO_MANY_ROOMS", ref)
        capacity = (product.get("attributes") or {}).get("maxOccupancy")
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            flag(warnings, "ROOM_CAPACITY_UNKNOWN", ref)
        elif rooms and people > rooms * capacity:
            flag(violations, "ROOM_CAPACITY_EXCEEDED", ref)
        price = product.get("unitPrice")
        charge(ref, int(price * len(nights) * rooms)
               if rooms and price is not None and product.get("priceUnit") == "PER_NIGHT" else None)

    for flight in draft["flights"]:
        ref, product = flight["product_ref"], products[flight["product_ref"]]
        attributes = product.get("attributes") or {}
        outbound = flight["role"] == "outbound"
        if product["taxonomy"] != "flight":
            flag(violations, "WRONG_TAXONOMY", ref)
        if flight_date(product) != (start if outbound else last_day):
            flag(violations, "FLIGHT_DATE", ref)
        route = (attributes.get("originCity"), attributes.get("destinationCity") or product.get("destination"))
        expected = (draft["origin"], draft["destination"]) if outbound else (draft["destination"], draft["origin"])
        if any(want and got != want for got, want in zip(route, expected)):
            flag(violations, "FLIGHT_ROUTE", ref)
        if attributes.get("simulated"):
            flag(warnings, "SIMULATED_PRICE", ref)
        if outbound:
            landing = _clock(attributes.get("arrivalTimeLocal") or attributes.get("arrivalAt"))
            late = landing is not None and any(a["start_minute"] < landing + ARRIVAL_BUFFER_MINUTES
                                               for a in days[0]["activities"])
            moment = landing
        else:
            takeoff = _clock(attributes.get("departureTimeLocal") or attributes.get("departureAt"))
            late = takeoff is not None and any(a["end_minute"] > takeoff - DEPARTURE_BUFFER_MINUTES
                                               for a in days[-1]["activities"])
            moment = takeoff
        if moment is None:
            flag(warnings, "TIMING_ESTIMATED", ref)
        if late:
            flag(violations, "AIRPORT_BUFFER", ref)
        price = product.get("unitPrice")
        charge(ref, int(price * people) if price is not None and product.get("priceUnit") == "PER_PERSON" else None)

    unpriced = list(dict.fromkeys(unpriced))
    if unpriced:
        warnings["PRICE_UNKNOWN"] = unpriced
    total = None if unpriced else subtotal
    budget = draft["trip_budget_vnd"]
    over = None if total is None or budget is None else max(0, total - budget)
    status = "not_set" if budget is None else "unknown" if total is None else "over" if over else "within"
    if status == "over":
        flag(warnings, "OVER_TRIP_BUDGET")
    feasibility = ("infeasible" if violations else
                   "provisional" if set(warnings) - {"OVER_TRIP_BUDGET"} else "verified")
    return {
        "plan_days": days, "nights": len(nights_taken), "changes": changes, "feasibility": feasibility,
        "violations": [{"code": code, "refs": refs} for code, refs in violations.items()],
        "warnings": [{"code": code, "refs": refs} for code, refs in warnings.items()],
        "costs": {"known_subtotal_vnd": subtotal, "estimated_total_vnd": total, "unpriced_refs": unpriced,
                  "trip_budget_vnd": budget, "over_by_vnd": over, "budget_status": status},
    }
