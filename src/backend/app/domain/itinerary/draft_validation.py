"""Kiểm lịch do orc phác (assistant v2, AC-AGT-02/04): không chọn, thêm, bớt hay thay sản phẩm.

Trả vi phạm (orc phải sửa, lịch chưa dùng được) và cảnh báo (lịch dùng được nhưng phải nói cho khách). Vượt ngân
sách chỉ là cảnh báo. Thiếu giá là unknown, trừ điểm tham quan tự do có giả định được công bố.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from itertools import pairwise, permutations
from math import ceil
from typing import Any

from ..booking.party import MAX_ROOMS
from ..catalog.models import entry_policy
from .flights import flight_date
from .geo import haversine_km, located
from .planning import stay_rooms

ACTIVITY_TAXONOMIES = {"attraction", "golf", "combo"}
ARRIVAL_BUFFER_MINUTES = 90      # hoạt động ngày đến bắt đầu sau hạ cánh ít nhất 90 phút
DEPARTURE_BUFFER_MINUTES = 150   # hoạt động ngày về kết thúc trước cất cánh ít nhất 150 phút
_HOURS = re.compile(r"\s*([01]?\d|2[0-3]):([0-5]\d)\s*[-–]\s*([01]?\d|2[0-3]):([0-5]\d)\s*")


def entry_mode(product: dict[str, Any]) -> str:
    """Metadata nguồn giữ căn cứ ticketed=false qua C2; giả định không biến thành xác nhận miễn phí."""
    mode = product.get("entryPolicy")
    if mode in ("free", "assumed_free", "paid", "unknown"):
        return mode
    return entry_policy(product["taxonomy"], product.get("unitPrice"),
                        (product.get("attributes") or {}).get("ticketed"))


def cost_mode(product: dict[str, Any]) -> str:
    mode = entry_mode(product)
    return "free" if mode in ("free", "assumed_free") else mode


def _opening_hours(product: dict[str, Any]) -> tuple[int, int] | None:
    """Khung giờ mở cửa dạng một khoảng HH:MM-HH:MM duy nhất; dạng khác coi như chưa biết."""
    match = _HOURS.fullmatch(str((product.get("attributes") or {}).get("openingHours") or ""))
    if not match:
        return None
    start, end = int(match[1]) * 60 + int(match[2]), int(match[3]) * 60 + int(match[4])
    return (start, end) if start < end else None


def available_on(product: dict[str, Any], day: date) -> bool | None:
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
        return sum(haversine_km(where[a], where[b]) for a, b in pairwise(order))

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
            if (product.get("available") is False and cost_mode(product) != "free") or available_on(product, when) is False:
                flag(violations, "DATE_UNAVAILABLE", ref)
            if draft["free_only"] and cost_mode(product) != "free":
                flag(violations, "NOT_FREE", ref)
            charge(ref, _activity_cost(product, people))
            if entry_mode(product) == "assumed_free":
                flag(warnings, "FREE_ENTRY_ASSUMED", ref)

    nights_taken: set[date] = set()
    for stay in draft["stays"]:
        ref, product = stay["product_ref"], products[stay["product_ref"]]
        check_in, check_out = date.fromisoformat(stay["check_in"]), date.fromisoformat(stay["check_out"])
        nights = [check_in + timedelta(days=n) for n in range((check_out - check_in).days)]
        if product["taxonomy"] != "hotel":
            flag(violations, "WRONG_TAXONOMY", ref)
        if product.get("destination") != draft["destination"]:
            flag(violations, "WRONG_DESTINATION", ref)
        if not nights or check_in < start or check_out > last_day + timedelta(days=0 if draft.get("slot_schedule") else 1):
            flag(violations, "STAY_DATES", ref)
        if nights_taken & set(nights):
            flag(violations, "STAY_OVERLAP", ref)
        nights_taken |= set(nights)
        if product.get("available") is False or any(available_on(product, night) is False for night in nights):
            flag(violations, "DATE_UNAVAILABLE", ref)
        rooms = stay.get("computed_rooms", stay_rooms(product, party))
        if stay.get("price_capacity_unknown"):
            flag(warnings, "PRICE_CAPACITY_UNKNOWN", ref)
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


SLOTS = {"morning": (480, 720), "afternoon": (780, 1080), "evening": (1110, 1320)}


def room_count(product: dict, people: int, explicit: int | None = None) -> tuple[int | None, bool]:
    attrs = product.get("attributes") or {}
    basis = attrs.get("priceAdults")
    unknown = not isinstance(basis, int) or isinstance(basis, bool) or basis < 1
    if unknown:
        basis = attrs.get("maxOccupancy")
    valid = isinstance(basis, int) and not isinstance(basis, bool) and basis > 0
    return explicit if explicit is not None else ceil(people / basis) if valid else None, unknown


def plan_slots(args: dict, products: dict[str, dict], candidates: dict[str, dict] | None = None) -> dict:
    """Tính lịch từ các buổi đã chọn, không thêm/bớt/đổi refs (FR-AGT-03, AC-AGT-02)."""
    start = date.fromisoformat(args["start_date"])
    people = args["adults"] + (args.get("children") or 0)
    flights = [{"role": role, "product_ref": ref} for role, ref in (args.get("flights") or {}).items() if ref]
    lower, upper = 0, 1440
    for flight in flights:
        attrs = products[flight["product_ref"]].get("attributes") or {}
        if flight["role"] == "outbound":
            arrival = _clock(attrs.get("arrivalTimeLocal") or attrs.get("arrivalAt"))
            if arrival is not None:
                lower = arrival + ARRIVAL_BUFFER_MINUTES
        else:
            departure = _clock(attrs.get("departureTimeLocal") or attrs.get("departureAt"))
            if departure is not None:
                upper = departure - DEPARTURE_BUFFER_MINUTES
    def window(day, slot, ref, all_day=False):
        begin, end = (480, 1080) if all_day else SLOTS[slot]
        if day == 1:
            begin = max(begin, lower)
        if day == args["days"]:
            end = min(end, upper)
        hours = _opening_hours(products[ref])
        if hours:
            begin, end = max(begin, hours[0]), min(end, hours[1])
        return begin, end
    fixed = {(row["day"], row["slot"]): row["start_minute"] for row in args.get("fixed_times") or []}
    days, timing_issues, rows = [], [], []
    for day in args["schedule"]:
        activities, all_day = [], bool(day.get("morning") and day.get("morning") == day.get("afternoon"))
        for slot in SLOTS:
            ref = day.get(slot)
            if not ref or all_day and slot == "afternoon":
                continue
            attrs = products[ref].get("attributes") or {}
            duration = attrs.get("durationMinutes")
            catalog = isinstance(duration, int) and not isinstance(duration, bool) and duration > 0
            duration = duration if catalog else 120
            begin, end = window(day["day"], slot, ref, all_day and slot == "morning")
            begin = fixed.get((day["day"], slot), begin)
            finish = begin + duration
            if begin < window(day["day"], slot, ref, all_day and slot == "morning")[0] or begin >= 1440 or finish > end or finish > 1440:
                choices = []
                for other in args["schedule"]:
                    for other_slot in SLOTS:
                        if other.get(other_slot):
                            continue
                        lo, hi = window(other["day"], other_slot, ref)
                        if lo + duration <= hi:
                            choices.append(f"ngày {other['day']} {other_slot}")
                timing_issues.append({"code": "SLOT_DOES_NOT_FIT", "refs": [ref], "day": day["day"],
                    "slot": slot, "fix_hint": "Thời lượng không vừa giờ mở/buổi/cửa sổ bay. Buổi trống phù hợp: "
                    + (", ".join(choices) or "không có; đổi buổi hoặc chọn sản phẩm khác")})
            activities.append({"product_ref": ref, "start_minute": begin, "end_minute": finish,
                               "timing_source": "catalog" if catalog else "estimate",
                               "assumption": None if catalog else "Chưa có thời lượng, ước tính 2 giờ"})
            amount = _activity_cost(products[ref], people)
            rows.append({"ref": ref, "kind": "activities", "subtotal_vnd": amount,
                         "basis": f"giá × {people} khách" if products[ref].get("priceUnit") == "PER_PERSON"
                         else "giá gói" if amount is not None else "chưa rõ giá"})
        days.append({"day_index": day["day"], "activities": activities})
    stays, stay_view = [], []
    for selected in args.get("stays") or []:
        ref = selected["room_ref"]
        begin, end = selected.get("from_day") or 1, selected.get("to_day") or args["days"]
        rooms, unknown = room_count(products[ref], people, selected.get("rooms"))
        attrs = products[ref].get("attributes") or {}
        stay = {"product_ref": ref, "check_in": (start + timedelta(days=begin - 1)).isoformat(),
                "check_out": (start + timedelta(days=end - 1)).isoformat(), "computed_rooms": rooms,
                "price_capacity_unknown": unknown}
        stays.append(stay)
        stay_view.append({"room_ref": ref, "check_in": stay["check_in"], "check_out": stay["check_out"],
                          "nights": end - begin, "rooms": rooms,
                          "rooms_basis": "khách đã chỉ định" if selected.get("rooms") else
                          f"{people} khách / {'maxOccupancy' if unknown else 'priceAdults'}={attrs.get('maxOccupancy' if unknown else 'priceAdults')}"})
        price = products[ref].get("unitPrice")
        amount = int(price * (end - begin) * rooms) if price is not None and rooms and products[ref].get("priceUnit") == "PER_NIGHT" else None
        rows.append({"ref": ref, "kind": "stay", "subtotal_vnd": amount,
                     "basis": f"giá/đêm × {end - begin} đêm × {rooms} phòng" if amount is not None else "chưa rõ giá/phòng"})
    for flight in flights:
        ref, product = flight["product_ref"], products[flight["product_ref"]]
        price = product.get("unitPrice")
        amount = int(price * people) if price is not None and product.get("priceUnit") == "PER_PERSON" else None
        rows.append({"ref": ref, "kind": "flights", "subtotal_vnd": amount, "basis": f"giá × {people} khách"})
    origin = args.get("origin")
    if not origin and flights:
        f = flights[0]
        attrs = products[f["product_ref"]].get("attributes") or {}
        origin = attrs.get("originCity") if f["role"] == "outbound" else attrs.get("destinationCity")
    draft = {"destination": args["destination"], "start_date": args["start_date"], "days": args["days"],
             "adults": args["adults"], "children": args.get("children") or 0, "origin": origin,
             "plan_days": days, "stays": stays, "flights": flights, "trip_budget_vnd": args.get("budget_vnd"),
             "free_only": bool(args.get("free_only")), "locked_refs": args.get("locked_refs") or [],
             "optimize": "none", "slot_schedule": True}
    checked = check_draft(draft, products)
    checked["violations"] += timing_issues
    actual_refs = {r["ref"] for r in rows}
    missing_locked = set(args.get("locked_refs") or []) - actual_refs
    if missing_locked:
        checked["violations"].append({"code": "LOCKED_REF_MISSING", "refs": sorted(missing_locked)})
    for stay in stays:
        attrs = products[stay["product_ref"]].get("attributes") or {}
        if not attrs.get("parentProductId"):
            checked["violations"].append({"code": "ROOM_REQUIRED", "refs": [stay["product_ref"]]})
    if any(products[r]["taxonomy"] == "combo" for r in actual_refs):
        checked["violations"].append({"code": "COMBO_OUTSIDE_PLAN", "refs": [r for r in actual_refs if products[r]["taxonomy"] == "combo"]})
    # A full day must use two/three activities when there are unused, available candidates. A full-day
    # product already occupies morning and afternoon; flight-limited days may have fewer activities.
    chosen_refs = {ref for day in args["schedule"] for slot in SLOTS for ref in [day.get(slot)] if ref}
    pool = candidates or products
    for day, computed in zip(args["schedule"], days):
        index = day["day"]
        first_bound = lower if index == 1 else 0
        last_bound = upper if index == args["days"] else 1440
        full_window = max(480, first_bound) + 120 <= min(720, last_bound) and max(780, first_bound) + 120 <= min(1080, last_bound)
        full_day_product = bool(day.get("morning") and day.get("morning") == day.get("afternoon"))
        if not full_window or full_day_product or len(computed["activities"]) >= 2:
            continue
        when = start + timedelta(days=index - 1)
        extra = []
        for ref, product in pool.items():
            if ref in chosen_refs or product["taxonomy"] not in ("attraction", "golf") or product.get("destination") != args["destination"]:
                continue
            if product.get("available") is False or available_on(product, when) is False or draft["free_only"] and cost_mode(product) != "free":
                continue
            duration = (product.get("attributes") or {}).get("durationMinutes")
            duration = duration if isinstance(duration, int) and not isinstance(duration, bool) and duration > 0 else 120
            opening = _opening_hours(product) or (0, 1440)
            if any(not day.get(slot) and max(begin, first_bound, opening[0]) + duration <= min(end, last_bound, opening[1])
                   for slot, (begin, end) in SLOTS.items()):
                extra.append(ref)
        if len(computed["activities"]) + len(extra) >= 2:
            checked["violations"].append({"code": "TOO_FEW_ACTIVITIES", "refs": [], "day": index,
                "fix_hint": "Ngày trọn vẹn còn buổi trống và sản phẩm đã tra phù hợp; chọn thêm hoạt động, không lặp điểm của ngày khác."})
    if checked["violations"]:
        checked["feasibility"] = "infeasible"
    costs = checked["costs"]
    costs["lines"] = rows
    subtotal = costs["known_subtotal_vnd"]
    costs["share"] = {kind: sum(row["subtotal_vnd"] or 0 for row in rows if row["kind"] == kind) / subtotal if subtotal else 0
                      for kind in ("stay", "activities", "flights")}
    savings = []
    locked = set(args.get("locked_refs") or [])
    for line in rows:
        ref = line["ref"]
        if ref in locked or line["subtotal_vnd"] is None or line["subtotal_vnd"] <= 0:
            continue
        selected = products[ref]
        for other, product in (candidates or {}).items():
            if other in actual_refs or product.get("available") is False or product.get("destination") != args["destination"]:
                continue
            if product["taxonomy"] != selected["taxonomy"] or product.get("priceUnit") != selected.get("priceUnit"):
                continue
            if product.get("unitPrice") is None or selected.get("unitPrice") is None or product["unitPrice"] >= selected["unitPrice"]:
                continue
            if line["kind"] == "stay" and (product.get("attributes") or {}).get("parentProductId") != (selected.get("attributes") or {}).get("parentProductId"):
                continue
            replacement = _activity_cost(product, people) if line["kind"] == "activities" else None
            if line["kind"] == "stay":
                stay = next(stay for stay in stays if stay["product_ref"] == ref)
                count, unknown = room_count(product, people)
                nights = (date.fromisoformat(stay["check_out"]) - date.fromisoformat(stay["check_in"])).days
                if count and count <= MAX_ROOMS and not unknown:
                    replacement = int(product["unitPrice"] * nights * count)
            if replacement is not None and replacement < line["subtotal_vnd"]:
                savings.append({"replace": ref, "with": other, "save_vnd": line["subtotal_vnd"] - replacement,
                                "note": "Phương án đã tra trong lượt; cần kiểm lại lịch trước khi thay"})
    return {"draft": draft, **checked, "stays": stay_view, "savings": savings}


def suitable_slots(product: dict) -> list[str]:
    """Buổi chứa đủ thời lượng/giờ mở; metadata để orc tự chọn, không chọn sản phẩm thay orc."""
    duration = (product.get("attributes") or {}).get("durationMinutes")
    if not isinstance(duration, int) or isinstance(duration, bool) or duration < 1:
        duration = 120
    hours = _opening_hours(product) or (0, 1440)
    slots = [slot for slot, (begin, end) in SLOTS.items() if max(begin, hours[0]) + duration <= min(end, hours[1])]
    if duration > 240 and max(480, hours[0]) + duration <= min(1080, hours[1]):
        slots.append("all_day")
    return slots
