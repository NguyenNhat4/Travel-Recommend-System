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


def _first(products: list[Product], product_id: str | None) -> list[Product]:
    """Đưa chuyến người dùng đã chọn lên đầu (nếu nó có trong danh sách); thứ tự còn lại giữ nguyên."""
    if not product_id:
        return products
    chosen = [product for product in products if product["productId"] == product_id]
    return chosen + [product for product in products if product["productId"] != product_id]


def choose_flights(options: dict[str, Any], intent: TripIntent,
                   chosen: dict[str, str] | None = None) -> tuple[list[FlightLeg], str | None]:
    """(chặng bay chọn được, lý do thiếu). `options` do application dựng: `status` và hai danh sách chuyến thô.

    `options["status"]` khác None là lý do đã biết trước khi chọn (chưa có nơi đi, không có tuyến, tra lỗi...).
    `outbound` là chuyến của tuyến nơi đi → điểm đến (gồm vé khứ hồi), `return` là chuyến của tuyến ngược lại.
    `chosen` (`constraints.chosen_flights`, `{"OUTBOUND"|"RETURN": productId}`): chuyến người dùng đã chọn khi đổi vé; chỉ
    dùng khi chuyến đó còn bán đúng ngày của chặng, khi đó không ưu tiên vé khứ hồi nữa.
    Sản phẩm trả về là bản nguyên của catalog; nơi gọi chuyển sang `summary` khi đưa vào response.
    """
    chosen = chosen or {}
    if options.get("status"):
        return [], options["status"]
    dates = trip_dates(intent)
    if dates is None:
        return [], NO_FLIGHT_ON_DATES
    out_day, back_day = dates
    count = passengers(intent)
    outbound = [p for p in options.get("outbound", []) if _bookable(p)]
    inbound = [p for p in options.get("return", []) if _bookable(p)]
    going = _first(sorted((p for p in outbound if not _is_round_trip(p) and flight_date(p) == out_day), key=_order),
                   chosen.get("OUTBOUND"))
    coming = _first(sorted((p for p in inbound if not _is_round_trip(p) and flight_date(p) == back_day),
                           key=lambda p: _order(p, late=True)), chosen.get("RETURN"))
    picked = {going[0]["productId"] if going else None, coming[0]["productId"] if coming else None}
    round_trips = _first(sorted((p for p in outbound if _is_round_trip(p) and flight_date(p) == out_day
                                 and _return_date(p) == back_day), key=_order), chosen.get("ROUND_TRIP"))
    if round_trips and not (set(chosen.values()) & picked):
        return [_leg(round_trips[0], "ROUND_TRIP", out_day, count, back=back_day)], None
    legs = ([_leg(going[0], "OUTBOUND", out_day, count)] if going else []) + \
           ([_leg(coming[0], "RETURN", back_day, count)] if coming else [])
    if not legs:
        return [], NO_FLIGHT_ON_DATES
    return legs, None if len(legs) == 2 else ONE_WAY_ONLY


#: Số ngày gần nhất có vé gợi ý khi ngày đã chọn không có chuyến (`nearest_dates`).
NEAREST_DATES = 2
#: Số chuyến khác cùng ngày đưa ra khi người dùng muốn đổi vé (`flight_choices`).
MAX_ALTERNATIVES = 2


def brief(product: Product) -> dict[str, Any]:
    """Thông tin gọn của một chuyến để hỏi đổi vé: mã, số hiệu, hãng, giờ cất cánh, giá."""
    attributes = product.get("attributes") or {}
    clock = attributes.get("departureTimeLocal") or str(attributes.get("departureAt") or "")[11:16]
    item = {"productId": product["productId"], "flightNumber": attributes.get("flightNumber"),
            "airline": attributes.get("airline"), "departure": clock or None, "unitPrice": product.get("unitPrice")}
    back = attributes.get("returnFlight")
    if isinstance(back, dict) and back.get("flightNumber"):
        # Vé khứ hồi: hai vé cùng chuyến đi có thể khác chuyến về, nên phải nêu cả chuyến về (golden TC-14, 10/10).
        item["returnFlightNumber"] = back["flightNumber"]
        item["returnDeparture"] = str(back.get("departureAt") or "")[11:16] or None
    return item


def flight_choices(options: dict[str, Any], legs: list[FlightLeg], limit: int = MAX_ALTERNATIVES) -> list[dict[str, Any]]:
    """Mỗi chặng một chiều đã chọn kèm tối đa `limit` chuyến khác cùng ngày, cùng chiều, còn bán, theo thứ tự chọn vé.

    Lượt sau người dùng nói "đổi chuyến bay" thì trợ lý hỏi bằng đúng các chuyến này (kịch bản bản 5). Vé khứ hồi đổi sang vé
    khứ hồi khác cùng ngày đi, ngày về (golden TC-14, LLM thật 10/10: lịch có vé khứ hồi thì "đổi chuyến bay" lập lại đúng vé cũ).
    """
    pools = {"OUTBOUND": options.get("outbound", []), "RETURN": options.get("return", []),
             "ROUND_TRIP": options.get("outbound", [])}
    choices = []
    for leg in legs:
        if leg["direction"] not in pools:
            continue
        day, chosen_id = date.fromisoformat(leg["date"]), leg["product"]["productId"]
        round_trip = leg["direction"] == "ROUND_TRIP"
        back = date.fromisoformat(leg["returnDate"]) if round_trip and leg.get("returnDate") else None
        others = sorted((p for p in pools[leg["direction"]] if _bookable(p) and _is_round_trip(p) == round_trip
                         and flight_date(p) == day and p["productId"] != chosen_id
                         and (not round_trip or _return_date(p) == back)),
                        key=lambda p: _order(p, late=leg["direction"] == "RETURN"))
        chosen = brief(leg["product"])
        # Catalog có thể có nhiều sản phẩm cho cùng một chuyến (cùng số hiệu, khác giá): đó không phải chuyến khác. Bỏ bản
        # trùng với chuyến đang chọn và giữ một bản cho mỗi chuyến (golden TC-14 với LLM thật, 10/10).
        seen = {_flight_key(chosen)}
        alternatives = []
        for product in others:
            item = brief(product)
            if _flight_key(item) in seen:
                continue
            seen.add(_flight_key(item))
            alternatives.append(item)
        choices.append({"direction": leg["direction"], "date": leg["date"], "chosen": chosen,
                        "alternatives": alternatives[:limit]})
    return choices


def _flight_key(item: dict[str, Any]) -> tuple:
    """Một chuyến (hoặc cặp chuyến khứ hồi) theo số hiệu; thiếu số hiệu thì theo mã sản phẩm."""
    if not item.get("flightNumber"):
        return (item["productId"],)
    return (fold(item["flightNumber"]), fold(item.get("returnFlightNumber")), item.get("departure"))


def nearest_dates(options: dict[str, Any], intent: TripIntent, today: date,
                  limit: int = NEAREST_DATES) -> list[dict[str, Any]]:
    """Ngày khởi hành gần ngày đã chọn nhất mà có vé, giữ nguyên số ngày của chuyến (kịch bản bản 5, cảnh 10).

    Ngày có đủ hai chiều (vé khứ hồi đúng ngày về, hoặc chặng đi và chặng về một chiều) xếp trước ngày chỉ có chiều đi;
    cùng loại thì ngày gần ngày đã chọn hơn trước, rồi ngày sớm hơn. Không xét ngày đã qua và chính ngày đã chọn. Dữ liệu
    là các chuyến `flight_options` đã tải cho lượt này, nên không tra thêm gì.
    """
    dates = trip_dates(intent)
    if dates is None or options.get("status"):
        return []
    chosen, span = dates[0], dates[1] - dates[0]
    outbound = [p for p in options.get("outbound", []) if _bookable(p)]
    inbound = {flight_date(p) for p in options.get("return", []) if _bookable(p) and not _is_round_trip(p)}
    by_day: dict[date, list[Product]] = {}
    complete: set[date] = set()
    for product in outbound:
        day = flight_date(product)
        if day is None or day < today or day == chosen:
            continue
        if _is_round_trip(product):
            if _return_date(product) != day + span:
                continue
            complete.add(day)
        elif day + span in inbound:
            complete.add(day)
        by_day.setdefault(day, []).append(product)
    ranked = sorted(by_day, key=lambda day: (day not in complete, abs((day - chosen).days), day))
    return [{"startDate": day.isoformat(), "complete": day in complete,
             "price": min(float(product["unitPrice"]) for product in by_day[day])} for day in ranked[:limit]]


#: Xa nhất chừng này ngày quanh ngày đã chọn khi tìm ngày đi chung (cửa sổ mở bán của catalog là 30 ngày).
JOINT_SEARCH_DAYS = 60


def joint_start(chosen: date, days: int, today: date, flight_starts: list[date] | None,
                windows: list[tuple[date | None, date | None, int]]) -> date | None:
    """Ngày đi gần `chosen` nhất mà mọi phần đang thiếu vì ngày cùng có (chat thử M09: vé gợi ý 28/10, khách sạn 05/11,
    vé tham quan 05/11 — người dùng không biết chọn ngày nào).

    `flight_starts`: ngày đi có đủ chuyến hai chiều (None khi vé không thiếu vì ngày). `windows`: (mở, đóng, độ lệch)
    của từng phần khác, ngày `start + độ lệch` phải còn trong cửa sổ (khách sạn: đêm cuối = số ngày − 2; vé tham quan:
    ngày cuối = số ngày − 1). Không phần nào thiếu thì None.
    """
    if flight_starts is None and not windows:
        return None

    def fits(day: date) -> bool:
        return day >= today and day != chosen and all(
            (opens is None or day >= opens) and (closes is None or day + timedelta(days=max(offset, 0)) <= closes)
            for opens, closes, offset in windows)

    if flight_starts is not None:
        candidates = flight_starts
    else:
        candidates = [chosen + timedelta(days=step) for step in range(-JOINT_SEARCH_DAYS, JOINT_SEARCH_DAYS + 1)]
    found = sorted((day for day in candidates if fits(day)), key=lambda day: (abs((day - chosen).days), day))
    return found[0] if found else None


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
