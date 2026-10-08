"""Deterministic itinerary construction and grounding rules."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
import re
from typing import Any

from .flights import flight_cost, flight_times
from .geo import Point, band, haversine_km, located, medoid
from .routing import DayShape, STAY_CHANGE_MIN_DAYS, STAY_MIN_NIGHTS, optimize
from .normalization import strip_accents
from .types import Candidates, Constraints, Party, Plan, Product, Proposal, Sources, TripIntent

NOTES = {
    "VISIT": "Tham quan theo khung giờ đề xuất.",
    "RELAX": "Dành thời gian nghỉ ngơi và thư giãn.",
    "FAMILY": "Hoạt động phù hợp để gia đình cùng trải nghiệm.",
    "REST": "Nghỉ ngơi để giữ lịch trình thoải mái.",
    "MEAL": "Tự do dùng bữa; chưa gắn với sản phẩm đặt chỗ.",
    "TRANSFER": "Di chuyển giữa các điểm trong lịch trình.",
    "ARRIVAL": "Di chuyển từ sân bay, nhận phòng.",
    "DEPARTURE": "Ra sân bay.",
    "CHANGE_STAY": "Trả phòng, chuyển sang khách sạn mới.",
}
SUMMARY_FIELDS = (
    "productId", "name", "taxonomy", "destination", "unitPrice", "currency",
    "available", "availableFrom", "availableTo", "imageUrl", "rating",
    "reviewCount", "attributes", "priceUnit",
)
# `attributes` chỉ giữ khoá FE thật sự đọc trong lịch trình (history/2026-09-28-ap-dung-de-xuat-field-review-agent.md; giữ thêm toạ độ/địa chỉ từ 2026-10-02): tag khách sạn,
# "tham quan tự do" (`ticketed`), toạ độ và địa chỉ của bản đồ (`services/catalog.ts` đọc `latitude`/`longitude`/`address`;
# thiếu thì widget đặt mọi điểm ở tâm thành phố). Nguồn đầy đủ vẫn ở `candidates`/`ProductDetail`, không mất dữ liệu.
SUMMARY_ATTRIBUTE_KEYS = frozenset({"oceanView", "privateBeach", "pool", "ticketed", "starRating",
                                    "latitude", "longitude", "address",
                                    # Thẻ chặng bay (AC-AGT-02, user-flow §4.2): hãng, số hiệu, giờ đi/đến, bay thẳng.
                                    "airline", "flightNumber", "departureAt", "arrivalAt", "departureTimeLocal",
                                    "arrivalTimeLocal", "nonstop", "tripType", "returnDate", "returnFlight",
                                    "originCity", "destinationCity", "originAirport", "destinationAirport"})
# Flights and combos have no confirmed slot mapping, so they can be retrieved but never scheduled.
STAY_TAXONOMY = "hotel"
SLOT_TAXONOMIES = frozenset({"attraction", "golf"})
SCHEDULABLE_TAXONOMIES = frozenset({STAY_TAXONOMY, *SLOT_TAXONOMIES})
# Pace is not a scheduling input yet; this is the cap the itinerary has always been held to.
MAX_ACTIVITIES_PER_DAY = 2
# Khung giờ của từng buổi (giờ Việt Nam, phút từ 0:00). Chỉ dùng để khớp lịch với giờ bay (AC-AGT-02); hoạt động vẫn
# chỉ xếp sáng và chiều vì compose chưa đọc giờ mở cửa.
PERIODS = {"MORNING": (8 * 60, 12 * 60), "NOON": (12 * 60, 13 * 60 + 30),
           "AFTERNOON": (13 * 60 + 30, 17 * 60), "EVENING": (18 * 60, 21 * 60)}
ACTIVITY_TIMES = ("MORNING", "AFTERNOON")
# Sau khi hạ cánh: nhận hành lý, về nơi nghỉ. Trước khi cất cánh: ra sân bay, làm thủ tục.
ARRIVAL_BUFFER = timedelta(minutes=90)
DEPARTURE_BUFFER = timedelta(minutes=150)
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
    for stay in plan.get("stays") or ([plan["stay"]] if plan.get("stay") else []):
        products.append((stay["product"], stay["nights"]))
    products.extend((slot["product"], 1) for day in plan.get("days", [])
                    for slot in day.get("slots", []) if slot.get("product") is not None)
    amounts = [_known_cost(product, nights=nights, party=intent.get("party")) for product, nights in products]
    amounts.extend(flight_cost(leg) for leg in plan.get("flights", []))
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
    """Cheapest first; an unknown price cannot be compared, so it goes last. Tham quan tự do (`free_to_visit`) tính 0 đ
    như ở tổng tiền, không phải giá chưa biết."""
    if free_to_visit(product):
        return (0, 0.0)
    price = product.get("unitPrice")
    return (1, 0.0) if price is None else (0, float(price))


def _source_rank(sources: Sources, product: Product) -> int:
    # Search (and Similar, which also carries source "search") is preferred over Recommendation:
    # a recommended item only fills a slot/stay when no searched candidate is available for it.
    return 0 if sources.get(product["productId"]) != "recommendation" else 1


def _stay_order(sources: Sources, product: Product, distance: float = 0.0) -> tuple[Any, ...]:
    """`distance`: mức khoảng cách tới các hoạt động đã xếp (`geo.band`); 0 cho mọi khách sạn khi không xét vị trí."""
    star = product.get("attributes", {}).get("starRating")
    return (_source_rank(sources, product), distance, *_price_key(product),
            -(star if isinstance(star, (int, float)) else -1), product["productId"])


def _activity_order(sources: Sources, product: Product, distance: float = 0.0) -> tuple[Any, ...]:
    """`distance`: mức khoảng cách tới mốc của chuyến (`geo.band`); 0 cho mọi hoạt động khi không xét vị trí."""
    # A full-day item needs a day to itself, so it is placed before anything that can share one.
    return (_source_rank(sources, product), 0 if allowed_times(product) == ["MORNING"] else 1,
            distance, *_price_key(product), product["productId"])


def _period_at(moment: datetime) -> str:
    """Buổi chứa giờ này; trước buổi sáng tính là buổi sáng, giờ nằm giữa hai buổi tính vào buổi trước đó."""
    minutes = moment.hour * 60 + moment.minute
    started = [time for time, (start, _) in PERIODS.items() if start <= minutes]
    return started[-1] if started else "MORNING"


def day_windows(intent: TripIntent, legs: list) -> dict[int, dict[str, Any]]:
    """Cửa sổ giờ của các ngày bị giờ bay ảnh hưởng (AC-AGT-02); ngày không bị ảnh hưởng thì không có khoá.

    Mỗi ngày gồm:
    - `times`: buổi được xếp hoạt động, theo thứ tự `ACTIVITY_TIMES`;
    - `full_day`: còn trọn ngày (mọi buổi) cho hoạt động cả ngày;
    - `transfers`: dòng di chuyển `(buổi, "ARRIVAL" | "DEPARTURE")` ở buổi của giờ hạ cánh/cất cánh.
    Một buổi dùng được khi bắt đầu từ `ARRIVAL_BUFFER` sau giờ hạ cánh và kết thúc trước giờ cất cánh ít nhất
    `DEPARTURE_BUFFER`. So theo datetime, nên chuyến hạ cánh sau nửa đêm rơi đúng vào ngày hôm sau. Thiếu ngày đi hoặc
    giờ bay thì không giới hạn: không đoán giờ.
    """
    start, days_count = parse_day(intent.get("startDate")), intent.get("days")
    landing, take_off = flight_times(legs)
    if start is None or not isinstance(days_count, int) or (landing is None and take_off is None):
        return {}
    earliest = landing + ARRIVAL_BUFFER if landing else None
    latest = take_off - DEPARTURE_BUFFER if take_off else None

    def usable(day: date, time: str) -> bool:
        begin, end = (datetime.combine(day, datetime.min.time()) + timedelta(minutes=minutes) for minutes in PERIODS[time])
        return (earliest is None or begin >= earliest) and (latest is None or end <= latest)

    windows = {}
    for number in range(1, days_count + 1):
        day = start + timedelta(days=number - 1)
        transfers = [(_period_at(moment), kind) for moment, kind in ((landing, "ARRIVAL"), (take_off, "DEPARTURE"))
                     if moment is not None and moment.date() == day]
        full_day = all(usable(day, time) for time in PERIODS)
        if transfers or not full_day:
            windows[number] = {"times": [time for time in ACTIVITY_TIMES if usable(day, time)],
                               "full_day": full_day, "transfers": transfers}
    return windows


def _slot_order(slot: dict[str, Any]) -> tuple[int, int]:
    """Theo buổi; trong cùng buổi: đến nơi hoặc chuyển khách sạn trước, hoạt động giữa, ra sân bay sau."""
    kind = {"ARRIVAL": 0, "CHANGE_STAY": 0, "DEPARTURE": 2}.get(slot["note_kind"], 1)
    return list(PERIODS).index(slot["time"]), kind


def _km(positions: dict[str, Point], product_id: str, point: Point | None) -> float | None:
    own = positions.get(product_id)
    return haversine_km(own, point) if own is not None and point is not None else None


def compose_plan(candidates: Candidates, sources: Sources, intent: TripIntent,
                 windows: dict[int, dict[str, Any]] | None = None, fixed_cost: int | None = 0) -> Proposal:
    """Choose products and lay them out on days with fixed rules. No model is involved.

    Ordering is total and depends only on product data and source, so the same candidates always
    produce the same proposal. Search-sourced candidates are always chosen over Recommendation-sourced
    ones for the same slot; a recommendation only fills a slot/stay left empty by Search. The result is
    fed to `render_proposal`, which still enforces every rule; this function only has to avoid
    proposing something the renderer would reject.

    `windows` (từ `day_windows`) giới hạn buổi của ngày đến và ngày về theo giờ bay, và thêm dòng di chuyển ở hai ngày
    đó. Ngày không có trong `windows` dùng đủ `ACTIVITY_TIMES`.

    Ít di chuyển (AC-AGT-04): khi có hoạt động rõ vị trí (`geo.located`), hoạt động gần mốc của chuyến (`geo.medoid`)
    được chọn trước; luật rải ngày quyết số điểm mỗi ngày; rồi `routing.optimize` chọn khách sạn từng đêm (có thể đổi
    một lần với chuyến từ 5 ngày), điểm nào đi ngày nào và thứ tự buổi để tổng quãng đường nhỏ nhất. Proposal khi đó có
    `criteria = "DISTANCE"` và `stays` theo đêm; không điểm nào rõ vị trí thì xếp như trước, một khách sạn.

    Ngân sách (chốt 2026-10-08): `fixed_cost` là tiền vé máy bay đã chọn (None khi chưa rõ giá). Có ngân sách và biết
    tiền vé thì chỉ xét các lịch có tổng tiền không vượt ngân sách; không lịch nào vừa thì lấy lịch rẻ nhất. Proposal
    khi đó có thêm `distance_km` và `options` (phương án khác, `routing.Option`) để câu trả lời nêu "thêm X ₫ → bớt Y km".
    """
    windows = windows or {}
    days_count = intent.get("days")
    if not isinstance(days_count, int) or days_count < 1:  # upper bound is enforced by TripIntent
        raise ValueError("invalid trip duration")
    usable = [product for product in candidates.values() if product.get("available")]
    positions = located(usable)
    pool = [p for p in usable if p.get("taxonomy") in SLOT_TAXONOMIES and not multi_day_span(p)]
    pool_points = {p["productId"]: positions[p["productId"]] for p in pool if p["productId"] in positions}
    searched_points = {pid: point for pid, point in pool_points.items() if sources.get(pid) != "recommendation"}
    anchor = medoid(searched_points or pool_points)

    def to_anchor(product: Product) -> float:
        return 0.0 if anchor is None else band(_km(positions, product["productId"], anchor))

    taken: set[str] = set()
    activities: list[Product] = []
    for product in sorted(pool, key=lambda product: _activity_order(sources, product, to_anchor(product))):
        key = _parent_key(product)
        if key in taken or product["productId"] in taken:
            continue
        taken.update({key, product["productId"]})
        activities.append(product)
    times_of = [list(windows.get(index + 1, {}).get("times", ACTIVITY_TIMES)) for index in range(days_count)]
    whole_day = [windows.get(index + 1, {}).get("full_day", True) for index in range(days_count)]
    capacity = [min(MAX_ACTIVITIES_PER_DAY, len(times)) for times in times_of]
    per_day: list[list[Product]] = [[] for _ in range(days_count)]
    full_days: set[int] = set()
    for product in activities:
        full_day = allowed_times(product) == ["MORNING"]
        # Spread across the trip instead of filling day one: least loaded day wins, earliest breaks ties.
        open_days = [index for index in range(days_count) if len(per_day[index]) < capacity[index]
                     and (not per_day[index] or (not full_day and index not in full_days))]
        if full_day:
            open_days = [index for index in open_days if not per_day[index] and whole_day[index]]
        if not open_days:
            continue  # more activities than the trip can hold; the extras are simply not scheduled
        index = min(open_days, key=lambda day: (len(per_day[day]), day))
        if full_day:
            full_days.add(index)
        per_day[index].append(product)
    # Khách sạn chọn sau hoạt động, theo khoảng cách trung bình tới các hoạt động đã xếp (AC-AGT-04).
    scheduled = [positions[p["productId"]] for products in per_day for p in products if p["productId"] in positions]

    def to_activities(product: Product) -> float:
        if not scheduled:
            return 0.0
        point = positions.get(product["productId"])
        return band(None if point is None else sum(haversine_km(point, other) for other in scheduled) / len(scheduled))

    stays = sorted((p for p in usable if p.get("taxonomy") == STAY_TAXONOMY
                    and _parent_key(p) not in taken and p["productId"] not in taken),
                   key=lambda product: _stay_order(sources, product, to_activities(product)))
    nights = max(1, days_count - 1)
    chosen_stays = [{"stay_id": stays[0]["productId"], "from_night": 1, "nights": nights}] if stays else []
    if anchor is not None:
        best_rank = min((_source_rank(sources, p) for p in stays), default=0)
        hotels = [p for p in stays if p["productId"] in positions and _source_rank(sources, p) == best_rank]
        placed = {p["productId"] for products in per_day for p in products}
        party = intent.get("party")

        def money(route_stays, scheduled_products) -> tuple[int, int]:
            amounts = [_known_cost(stay.product, nights=stay.nights, party=party) for stay in route_stays]
            amounts += [_known_cost(product, nights=1, party=party) for product in scheduled_products]
            known = [amount for amount in amounts if amount is not None]
            return len(amounts) - len(known), sum(known)

        budget = intent.get("budget")
        budget_left = None if budget is None or fixed_cost is None else budget - fixed_cost
        planned = optimize(per_day, [DayShape(len(products), index in full_days)
                                     for index, products in enumerate(per_day)],
                           [p for p in activities if p["productId"] not in placed], hotels, positions, days_count, money,
                           lambda product: _stay_order(sources, product) if product.get("taxonomy") == STAY_TAXONOMY
                           else _activity_order(sources, product), budget_left)
        route = planned.route
        per_day = route.days
        options = [{"stays": [{"stay_id": stay.product["productId"], "from_night": stay.from_night,
                               "nights": stay.nights} for stay in option.stays],
                    "km_delta": round(option.km_delta, 1), "money_delta": option.money_delta,
                    "over_budget": option.over_budget} for option in planned.options]
        if route.stays:
            chosen_stays = [{"stay_id": stay.product["productId"], "from_night": stay.from_night, "nights": stay.nights}
                            for stay in route.stays]
    slots = []
    changes = {stay["from_night"] for stay in chosen_stays[1:]}
    for index, products in enumerate(per_day):
        day_slots = [{"day": index + 1, "note_kind": "VISIT", "activity_type": None, "product_id": product["productId"],
                      "time": "MORNING" if allowed_times(product) == ["MORNING"] else times_of[index][position]}
                     for position, product in enumerate(products)]
        day_slots += [{"day": index + 1, "note_kind": kind, "activity_type": "TRANSFER", "product_id": None, "time": time}
                      for time, kind in windows.get(index + 1, {}).get("transfers", [])]
        if index + 1 in changes:
            # Đêm trước ở khách sạn cũ, đêm nay ở khách sạn mới: trả phòng đầu ngày (AC-AGT-04).
            day_slots.append({"day": index + 1, "note_kind": "CHANGE_STAY", "activity_type": "TRANSFER",
                              "product_id": None, "time": "MORNING"})
        slots.extend(sorted(day_slots, key=_slot_order))
    proposal: Proposal = {"stay_id": chosen_stays[0]["stay_id"] if chosen_stays else None, "slots": slots,
                          "stays": chosen_stays}
    if anchor is not None:
        proposal["criteria"] = "DISTANCE"
        if route.stays:
            proposal["distance_km"] = round(route.cost_km, 1)
            proposal["options"] = options
    return proposal


def _stay_issue(stays: list[dict[str, Any]], days_count: int) -> bool:
    """Các khách sạn theo đêm có sai luật không (AC-AGT-04): liền nhau từ đêm 1, đủ `max(1, days − 1)` đêm, tối đa 2
    khách sạn; có đổi thì chuyến từ `STAY_CHANGE_MIN_DAYS` ngày và mỗi khách sạn ít nhất `STAY_MIN_NIGHTS` đêm."""
    night = 1
    for stay in stays:
        if stay.get("fromNight") != night or not isinstance(stay.get("nights"), int) or stay["nights"] < 1:
            return True
        night += stay["nights"]
    if stays and night - 1 != max(1, days_count - 1):
        return True
    if len(stays) > 2:
        return True
    return len(stays) == 2 and (days_count < STAY_CHANGE_MIN_DAYS or any(s["nights"] < STAY_MIN_NIGHTS for s in stays))


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
    stays = []
    proposed_stays = proposal.get("stays")
    if proposed_stays is None and proposal.get("stay_id"):
        proposed_stays = [{"stay_id": proposal["stay_id"], "from_night": 1, "nights": max(1, days_count - 1)}]
    for proposed in proposed_stays or []:
        stay_id = proposed.get("stay_id")
        product = candidates.get(stay_id)
        if product is None or product.get("taxonomy") != STAY_TAXONOMY or stay_id in used:
            raise ValueError("invalid stay")
        parent = product.get("attributes", {}).get("parentProductId") or stay_id
        if parent in parent_keys:
            raise ValueError("duplicate parent selection")
        used.add(stay_id)
        parent_keys.add(parent)
        stays.append({"product": summary(product), "nights": proposed["nights"], "fromNight": proposed["from_night"],
                      "note": NOTES["RELAX"], "source": _source(sources.get(stay_id)),
                      "because": _because(product, sources.get(stay_id))})
    if _stay_issue(stays, days_count):
        raise ValueError("invalid stays")
    stay = deepcopy(stays[0]) if stays else None
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
    plan: Plan = {**({"stay": stay, "stays": stays} if stay else {}), "days": days,
        "bookableCount": len(used), "estimatedTotal": None, "currency": "VND",
        "budgetStatus": "UNKNOWN", "priceAsOf": None}
    plan["estimatedTotal"], plan["budgetStatus"] = totals(plan, intent)
    return plan


def validate_plan(plan: Plan, candidates: Candidates,
                  sources: Sources, intent: TripIntent, constraints: Constraints,
                  flight_candidates: Candidates | None = None) -> list[str]:
    """`flight_candidates`: chuyến bay đã tra của lượt này (productId → sản phẩm). Vé không đi qua `candidates`
    vì chặng về đến nơi đi chứ không phải điểm đến, và ngày bay về nằm ngoài ngày khởi hành."""
    issues: list[str] = []
    days = plan.get("days")
    if not isinstance(days, list) or [day.get("day") for day in days] != list(range(1, (intent.get("days") or 0) + 1)):
        return ["days"]
    stays = plan.get("stays") or ([plan["stay"]] if plan.get("stay") else [])
    selected = [stay["product"] for stay in stays] + [
        slot["product"] for day in days for slot in day.get("slots", []) if slot.get("product")]
    # Khách sạn theo đêm (AC-AGT-04): `stay` là khách sạn đầu tiên để client cũ vẫn chạy.
    if plan.get("stays") and (plan.get("stay") != plan["stays"][0] or _stay_issue(plan["stays"], len(days))):
        issues.append("stays")
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
    for leg in plan.get("flights", []):
        product = leg.get("product") or {}
        source = (flight_candidates or {}).get(product.get("productId"))
        if source is None or product != summary(source) or source.get("taxonomy") != "flight":
            issues.append("grounding")
        elif product.get("productId") in seen:
            issues.append("duplicate_product")
        else:
            seen.add(product["productId"])
            if not product.get("available") or product.get("unitPrice") is None:
                issues.append("availability")
    for day in days:
        paid = [slot for slot in day.get("slots", []) if slot.get("product")]
        for slot in day.get("slots", []):
            if slot.get("note") not in NOTES.values():
                issues.append("note")
        if any(slot["product"].get("attributes", {}).get("durationMinutes", 0) >= 360 for slot in paid) and len(paid) > 1:
            issues.append("schedule")
    # Hoạt động phải nằm trong cửa sổ giờ bay (AC-AGT-02). `summary` không giữ `durationMinutes`, nên đọc bản đầy đủ.
    windows = day_windows(intent, plan.get("flights", []))
    for day in days:
        window = windows.get(day.get("day"))
        for slot in day.get("slots", []) if window else []:
            if not slot.get("product"):
                continue
            source = candidates.get(slot["product"].get("productId")) or slot["product"]
            full_day = allowed_times(source) == ["MORNING"]
            if (full_day and not window["full_day"]) or (not full_day and slot.get("time") not in window["times"]):
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
