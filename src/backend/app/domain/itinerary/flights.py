"""Chặng bay của lịch trình (AC-AGT-02): chọn vé bằng luật tất định từ chuyến bay thật của catalog. Thuần Python.

`application/itinerary/flights.py` lấy chuyến của tuyến nơi đi → điểm đến (chặng đi, vé khứ hồi) và của tuyến ngược lại
(chặng về); hàm ở đây chỉ quyết định có chặng bay hay không, chọn vé nào và vì sao không có. LLM không chọn hay tạo chuyến.

Thứ tự chọn: vé khứ hồi khớp cả hai ngày trước; không có thì ghép hai chặng một chiều. Trong cùng loại: bay thẳng trước
(chuyến không khai `nonstop` xếp sau chuyến khai bay thẳng), rồi giá thấp, rồi giờ hợp lý (đi sớm, về muộn), rồi productId.
Chuyến không có giá hoặc hết chỗ bị bỏ, để tổng của cả chuyến không thành chưa biết vì một vé.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from .geo import Point, point_at
from .normalization import fold
from .types import FlightLeg, Product, TripIntent

#: Lý do không có (đủ) chặng bay — thành mã warning `FLIGHT_<lý do>`. EXCLUDED và DAY_TRIP không cảnh báo:
#: người dùng tự loại, hoặc chuyến trong ngày không cần vé.
NO_ORIGIN, EXCLUDED, DAY_TRIP, SAME_CITY, NO_ROUTE, NO_FLIGHT_ON_DATES, ONE_WAY_ONLY, UNAVAILABLE = (
    "NO_ORIGIN", "EXCLUDED", "DAY_TRIP", "SAME_CITY", "NO_ROUTE", "NO_FLIGHT_ON_DATES", "ONE_WAY_ONLY", "UNAVAILABLE")
SILENT_REASONS = frozenset({EXCLUDED, DAY_TRIP, SAME_CITY})
ROUND_TRIP = "roundTrip"
VIETNAM = timezone(timedelta(hours=7))


def trip_dates(intent: TripIntent) -> tuple[date, date] | None:
    """(ngày bay đi, ngày bay về): về vào ngày cuối của chuyến, `startDate + days − 1`."""
    if not intent.get("startDate") or not isinstance(intent.get("days"), int) or intent["days"] < 1:
        return None
    start = date.fromisoformat(intent["startDate"])
    return start, start + timedelta(days=intent["days"] - 1)


def skip_reason(intent: TripIntent, constraints: dict[str, Any]) -> str | None:
    """Lý do không cần tra chuyến bay; None nghĩa là phải tra catalog."""
    if "flight" in (constraints.get("exclude_taxonomies") or []):
        return EXCLUDED
    if not intent.get("origin"):
        return NO_ORIGIN
    if fold(intent["origin"]) == fold(intent.get("destination")):
        return SAME_CITY
    if (intent.get("days") or 0) < 2 and not constraints.get("require_flight"):
        return DAY_TRIP
    return None


def passengers(intent: TripIntent) -> int:
    party = intent.get("party") or {}
    return max(1, int(party.get("adults") or 0) + int(party.get("children") or 0))


def flight_date(product: Product) -> date | None:
    """Ngày cất cánh theo giờ Việt Nam: `departureAt` (có múi giờ +07:00), không có thì `availableFrom` (= ngày bay)."""
    departure = (product.get("attributes") or {}).get("departureAt") or product.get("availableFrom")
    try:
        return date.fromisoformat(str(departure)[:10]) if departure else None
    except ValueError:
        return None


def _return_date(product: Product) -> date | None:
    value = (product.get("attributes") or {}).get("returnDate")
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _departure_minutes(product: Product) -> int:
    attributes = product.get("attributes") or {}
    clock = attributes.get("departureTimeLocal") or str(attributes.get("departureAt") or "")[11:16]
    try:
        hours, minutes = str(clock).split(":")[:2]
        return int(hours) * 60 + int(minutes)
    except ValueError:
        return 12 * 60


def _bookable(product: Product) -> bool:
    return bool(product.get("available")) and product.get("unitPrice") is not None


def _order(product: Product, *, late: bool = False) -> tuple:
    nonstop = (product.get("attributes") or {}).get("nonstop")
    minutes = _departure_minutes(product)
    return (0 if nonstop is True else 1, float(product["unitPrice"]), -minutes if late else minutes, product["productId"])


def _is_round_trip(product: Product) -> bool:
    return (product.get("attributes") or {}).get("tripType") == ROUND_TRIP


def _leg(product: Product, direction: str, day: date, count: int, *, back: date | None = None) -> FlightLeg:
    return {"product": product, "direction": direction, "date": day.isoformat(),
            "returnDate": back.isoformat() if back else None, "passengers": count, "source": "SEARCH"}


def choose_flights(options: dict[str, Any], intent: TripIntent) -> tuple[list[FlightLeg], str | None]:
    """(chặng bay chọn được, lý do thiếu). `options` do application dựng: `status` và hai danh sách chuyến thô.

    `options["status"]` khác None là lý do đã biết trước khi chọn (chưa có nơi đi, không có tuyến, tra lỗi...).
    `outbound` là chuyến của tuyến nơi đi → điểm đến (gồm vé khứ hồi), `return` là chuyến của tuyến ngược lại.
    Sản phẩm trả về là bản nguyên của catalog; nơi gọi chuyển sang `summary` khi đưa vào response.
    """
    if options.get("status"):
        return [], options["status"]
    dates = trip_dates(intent)
    if dates is None:
        return [], NO_FLIGHT_ON_DATES
    out_day, back_day = dates
    count = passengers(intent)
    outbound = [p for p in options.get("outbound", []) if _bookable(p)]
    inbound = [p for p in options.get("return", []) if _bookable(p)]
    round_trips = sorted((p for p in outbound if _is_round_trip(p) and flight_date(p) == out_day
                          and _return_date(p) == back_day), key=_order)
    if round_trips:
        return [_leg(round_trips[0], "ROUND_TRIP", out_day, count, back=back_day)], None
    going = sorted((p for p in outbound if not _is_round_trip(p) and flight_date(p) == out_day), key=_order)
    coming = sorted((p for p in inbound if not _is_round_trip(p) and flight_date(p) == back_day),
                    key=lambda p: _order(p, late=True))
    legs = ([_leg(going[0], "OUTBOUND", out_day, count)] if going else []) + \
           ([_leg(coming[0], "RETURN", back_day, count)] if coming else [])
    if not legs:
        return [], NO_FLIGHT_ON_DATES
    return legs, None if len(legs) == 2 else ONE_WAY_ONLY


def _local(value: Any, day: str | None = None, clock: Any = None) -> datetime | None:
    """Thời điểm theo giờ Việt Nam, không múi giờ. `value` là ISO datetime; không có thì ghép `day` với `clock` HH:MM."""
    try:
        if value:
            moment = datetime.fromisoformat(str(value))
            return moment.astimezone(VIETNAM).replace(tzinfo=None) if moment.tzinfo else moment
        if day and clock:
            return datetime.fromisoformat(f"{day}T{str(clock)[:5]}")
    except ValueError:
        return None
    return None


def flight_times(legs: list[FlightLeg]) -> tuple[datetime | None, datetime | None]:
    """(giờ hạ cánh chặng đi, giờ cất cánh chặng về) theo giờ Việt Nam; thiếu dữ liệu thì None, không đoán.

    Vé khứ hồi: hạ cánh chặng đi là `arrivalAt` của chính vé, cất cánh chặng về là `returnFlight.departureAt`.
    """
    landing = take_off = None
    for leg in legs:
        attributes = (leg.get("product") or {}).get("attributes") or {}
        if leg.get("direction") in ("OUTBOUND", "ROUND_TRIP"):
            landing = _local(attributes.get("arrivalAt"), leg.get("date"), attributes.get("arrivalTimeLocal"))
        if leg.get("direction") == "RETURN":
            take_off = _local(attributes.get("departureAt"), leg.get("date"), attributes.get("departureTimeLocal"))
        if leg.get("direction") == "ROUND_TRIP":
            take_off = _local((attributes.get("returnFlight") or {}).get("departureAt"))
    return landing, take_off


def airports(legs: list[FlightLeg]) -> tuple[Point | None, Point | None]:
    """(sân bay đến ở điểm đến, sân bay đi khi về) của các chặng đã chọn, để tính km cả chuyến (AC-AGT-04, chốt 2026-10-09).

    Catalog ghi toạ độ sân bay đến của chuyến ở `latitude`/`longitude` và sân bay đi ở `originLatitude`/`originLongitude`:
    chặng đi và vé khứ hồi cho sân bay đến (vé khứ hồi về từ chính sân bay đó), chặng về cho sân bay đi. Chỉ có một chiều
    thì dùng sân bay của chiều đó cho cả hai đầu. Không có chặng hay toạ độ thì (None, None): km tính như trước.
    """
    arrival = departure = None
    for leg in legs:
        attributes = (leg.get("product") or {}).get("attributes") or {}
        if leg.get("direction") in ("OUTBOUND", "ROUND_TRIP"):
            arrival = point_at(attributes)
        if leg.get("direction") == "ROUND_TRIP":
            departure = arrival
        if leg.get("direction") == "RETURN":
            departure = point_at(attributes, "originLatitude", "originLongitude")
    return arrival or departure, departure or arrival


def flight_candidates(options: dict[str, Any]) -> dict[str, Product]:
    """productId → chuyến bay đã tra của lượt này: nguồn grounding của `Plan.flights`."""
    return {product["productId"]: product for key in ("outbound", "return") for product in options.get(key, [])
            if product.get("productId")}


def flight_cost(leg: FlightLeg) -> int | None:
    """Tiền một vé trong lịch trình: giá một khách × số khách (`priceBasis: per_person`, kể cả vé khứ hồi)."""
    price = (leg.get("product") or {}).get("unitPrice")
    return None if price is None else int(price * leg.get("passengers", 1))
