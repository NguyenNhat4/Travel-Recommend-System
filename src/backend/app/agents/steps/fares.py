"""Hỏi giá vé máy bay (kịch bản bản 5 cảnh 6, người dùng chốt 2026-10-10).

`classify` (LLM) nhận ra câu hỏi vé dù gõ sai, viết tắt, tiếng Anh hay nói vòng ("tao ở sài gòn, đi đâu cũng đc miễn vé
rẻ"), và đọc ra nơi đi, nơi đến, chiều về, đắt/rẻ nhất (`models.FareQuestion`, state `fare_ask`). Phần còn lại ở đây là
luật: tên nơi đối chiếu với điểm đến và tuyến bay của catalog; thiếu nơi đi hoặc điểm đến thì hỏi lại đúng chỗ thiếu
(kèm nút những nơi có chuyến); đủ thì báo vé một chiều rẻ nhất trong cửa sổ bán của catalog (hoặc đúng ngày đi nếu đã
có), cùng vài ngày rẻ khác. Tuyến và chuyến lấy qua `application/itinerary/flights.flight_options` như chặng bay của
lịch trình; câu do code dựng. Chỉ tiếng Việt ở đợt này (người dùng chốt 2026-10-10).
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from statistics import median

from src.backend.app.application.itinerary.flights import _all, canonical_city, flight_options
from src.backend.app.application.ports.itinerary_tools import ToolExecutorPort
from src.backend.app.domain.itinerary import flights as flight_rules
from src.backend.app.domain.itinerary.normalization import fold
from src.backend.app.domain.itinerary.planning import summary
from src.backend.app.domain.search.normalize import DESTINATION_ALIASES

from .classification import REQUIRED_FIELDS
from .messages import event, message, money, titled

#: Số ngày rẻ khác nêu thêm, số nút nơi đi, và số tuyến nêu khi so nhiều điểm đến.
ORIGIN_CHIPS = 3
OTHER_ROUTES = 3
#: Kiểu câu trả lời giá vé.
CHEAPEST, DEAREST = "cheapest", "dearest"
#: Thẻ ngày–giá tối đa của một câu trả lời (contract `searchResults.flight`, 1.25.0); số ngày gần nhất nêu khi ngày hỏi
#: không có chuyến; số ngày chưa có chuyến liệt kê; "bay sát ngày" khi còn từ chừng này ngày trở xuống.
MAX_FARE_CARDS = 4
NEAREST_DAYS = 2
MISSING_DAYS = 8
SOON_DAYS = 7
#: Khung giờ cất cánh (phút trong ngày) cho "đi sớm", "buổi sáng", "buổi chiều", "buổi tối".
PERIODS = {"early": (0, 9 * 60), "morning": (5 * 60, 12 * 60), "afternoon": (12 * 60, 18 * 60),
           "evening": (18 * 60, 24 * 60)}


def _cities(text: str, names: list[str]) -> list[tuple[int, str]]:
    """Các tên trong `names` (kể cả cách gọi khác đã biết) có trong câu, kèm vị trí, theo thứ tự xuất hiện."""
    padded = f" {fold(text)} "
    allowed = {fold(name): name for name in names if fold(name)}
    found: dict[str, int] = {}
    for key, name in allowed.items():
        position = padded.find(f" {key} ")
        if position >= 0:
            found[name] = position
    for alias, name in DESTINATION_ALIASES.items():
        position = padded.find(f" {fold(alias)} ")
        if fold(name) in allowed and position >= 0:
            found.setdefault(allowed[fold(name)], position)
    # Tên ngắn nằm trong tên dài hơn đã thấy ("Hà Nội" trong "sân bay Hà Nội") chỉ tính một lần.
    names_found = sorted(found.items(), key=lambda item: (item[1], -len(item[0])))
    kept: list[tuple[int, str]] = []
    for name, position in names_found:
        if not any(position >= other_pos and fold(name) in fold(other) for other_pos, other in kept):
            kept.append((position, name))
    return kept


async def _routes(tools: ToolExecutorPort, destination: str, timeout_seconds: float) -> list[str]:
    """Nơi có chuyến bay tới `destination` trong catalog (`originCity` của các tuyến), tuyến nhiều chuyến trước."""
    routes = await _all(tools, {"taxonomy": "flight", "destination": destination}, timeout_seconds)
    cities = []
    for route in routes:
        city = (route.get("attributes") or {}).get("originCity")
        if city and city not in cities and fold(city) != fold(destination):
            cities.append(city)
    return cities


def _known(state: dict, key: str) -> str | None:
    pending = state.get("pending_fare") or {}
    return pending.get(key) or (state.get("intent") or {}).get(key)


def _day(value: str | None) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%d/%m")
    except ValueError:
        return str(value)


def _flight_text(state: dict, product: dict) -> str:
    """Tên chuyến thành link tới thẻ vé ("[VietJet Air VJ124](product:<id>), cất cánh 05:05"): widget hiện thẻ ngày–giá
    của chuyến này, bấm vào mở trang vé máy bay đúng tuyến, đúng ngày (chat thử 11/10: chỉ có chữ, không bấm được)."""
    item = flight_rules.brief(product)
    label = " ".join(part for part in (item.get("airline"), item.get("flightNumber")) if part) or product.get("name")
    text = f"[{label}](product:{product['productId']})"
    if item.get("departure"):
        text += ", " + message(state, "fare_departs", time=item["departure"])
    return text


def _one_way(products: list[dict], today: date) -> list[dict]:
    """Chuyến một chiều còn bán từ hôm nay."""
    return [p for p in products if flight_rules._bookable(p) and not flight_rules._is_round_trip(p)
            and (day := flight_rules.flight_date(p)) is not None and day >= today]


def _in_period(products: list[dict], period: str | None) -> list[dict]:
    """Chuyến cất cánh trong khung giờ người dùng muốn ("đi sớm", "buổi tối"); không nói khung giờ thì giữ nguyên."""
    if period not in PERIODS:
        return products
    low, high = PERIODS[period]
    return [p for p in products if low <= flight_rules._departure_minutes(p) < high]


def _by_day(usable: list[dict], kind: str) -> list[tuple[date, dict]]:
    """Chuyến rẻ nhất (hoặc đắt nhất) của từng ngày, xếp từ rẻ nhất (hoặc đắt nhất) trở đi; hoà thì ngày sớm hơn."""
    sign = -1 if kind == DEAREST else 1
    best: dict[date, dict] = {}
    for product in sorted(usable, key=lambda p: (sign * float(p["unitPrice"]), flight_rules._departure_minutes(p))):
        best.setdefault(flight_rules.flight_date(product), product)
    return sorted(best.items(), key=lambda item: (sign * float(item[1]["unitPrice"]), item[0]))


def _short(day: date) -> str:
    return day.strftime("%d/%m")


def _availability_lines(state: dict, fields: dict, usable: list[dict], ranked: list[tuple[date, dict]],
                        period_text: str) -> list[str]:
    """"Khi nào có vé, ngày nào không có chuyến": đợt đang mở bán, số ngày có chuyến và các ngày chưa có."""
    days = sorted({flight_rules.flight_date(p) for p in usable})
    with_flights = {day for day, _ in ranked}
    first, last = days[0], days[-1]
    span = [first + timedelta(days=offset) for offset in range((last - first).days + 1)]
    missing = [day for day in span if day not in with_flights]
    lines = [message(state, "fare_availability", **fields, first=_short(first), count=len(with_flights),
                     total=len(span))]
    if missing:
        listed = ", ".join(_short(day) for day in missing[:MISSING_DAYS])
        lines.append(message(state, "fare_missing_days", period=period_text,
                             days=listed + ("…" if len(missing) > MISSING_DAYS else "")))
    else:
        lines.append(message(state, "fare_every_day", period=period_text))
    return lines


def answer_text(state: dict, origin: str, destination: str, products: list[dict], today: date,
                kind: str = CHEAPEST, start: str | None = None, more: bool = False, cheaper: bool = False,
                period: str | None = None, availability: bool = False) -> tuple[str, str, list[dict]]:
    """(tiêu đề, câu, chuyến hiện thành thẻ) cho vé một chiều `origin` → `destination`; `products` là chuyến của tuyến.

    Câu chỉ nêu chuyến trả lời câu hỏi; các ngày khác nằm ở thẻ ngày–giá bên dưới (chat thử 11/10: liệt kê ngày, giá bằng
    chữ quá dài). Đã có ngày đi (ngày người dùng hỏi hoặc ngày của chuyến): các chuyến của đúng ngày đó, rồi so với cả đợt
    mở bán; không có chuyến ngày đó thì nêu ngày gần nhất có chuyến. `period`: chỉ tính chuyến trong khung giờ đó ("đi
    sớm", "buổi tối"), không có chuyến nào trong khung thì nói rõ và tính mọi giờ. `availability`: đợt mở bán và các
    ngày chưa có chuyến. `more`: hỏi tiếp ngày khác, nêu các ngày kế tiếp. `cheaper`: nói rõ khi không còn vé rẻ hơn.
    """
    start = start or (state.get("intent") or {}).get("startDate")
    title = message(state, "fare_title", origin=origin, destination=destination)
    every = _one_way(products, today)
    if not every:
        return title, message(state, "fare_none", origin=origin, destination=destination), []
    language = state.get("language", "vi")
    lines: list[str] = []
    usable = _in_period(every, period)
    period_text = message(state, f"fare_period_{period}") if period in PERIODS else ""
    if not usable:
        lines.append(message(state, "fare_no_period", origin=origin, destination=destination, period=period_text))
        usable, period_text = every, ""
    ranked = _by_day(usable, kind)
    window_end = _short(max(day for day, _ in ranked))
    fields = {"origin": origin, "destination": destination, "end": window_end, "period": period_text}
    best_day, best = ranked[0]
    sign = -1 if kind == DEAREST else 1
    shown: list[dict] = []
    if availability:
        lines += _availability_lines(state, fields, usable, ranked, period_text)
        shown = [product for _, product in ranked[:MAX_FARE_CARDS]]
    elif start:
        day_asked = date.fromisoformat(start)
        on_day = sorted((p for p in usable if flight_rules.flight_date(p) == day_asked),
                        key=lambda p: (sign * float(p["unitPrice"]), flight_rules._departure_minutes(p)))
        if on_day:
            lines.append(message(state, f"fare_on_day_{kind}", **fields, count=len(on_day), day=_short(day_asked),
                                 money=money(on_day[0]["unitPrice"], language), flight=_flight_text(state, on_day[0])))
            shown = on_day[:MAX_FARE_CARDS - 1]
        else:
            nearest = sorted(ranked, key=lambda item: (abs((item[0] - day_asked).days), item[0]))[:NEAREST_DAYS]
            lines.append(message(state, "fare_none_on_day", **fields, day=_short(day_asked)))
            lines.append(message(state, "fare_nearest_days", days=", ".join(
                message(state, f"fare_other_day_{kind}", day=_short(day), money=money(p["unitPrice"], language))
                for day, p in sorted(nearest))))
            shown = [p for _, p in sorted(nearest)]
        if best_day != day_asked:
            lines.append(message(state, f"fare_window_{kind}", **fields, money=money(best["unitPrice"], language),
                                 day=_short(best_day), flight=_flight_text(state, best)))
            shown.append(best)
        elif on_day:
            lines.append(message(state, f"fare_is_best_{kind}", **fields))
    elif more and len(ranked) > 1:
        # "ngày khác thì sao" sau khi đã báo giá: các ngày tiếp theo, không lặp lại các ngày vừa hiện.
        rest = ranked[1:]
        rest = rest[MAX_FARE_CARDS - 1:] if len(rest) > MAX_FARE_CARDS - 1 else rest
        shown = [product for _, product in rest[:MAX_FARE_CARDS]]
        first_day, first = rest[0]
        lines.append(message(state, f"fare_more_{kind}", **fields, day=_short(first_day),
                             money=money(first["unitPrice"], language)))
    else:
        if cheaper and kind == CHEAPEST:
            # "rẻ hơn nữa ko" sau khi đã báo giá rẻ nhất: nói thẳng là không còn vé rẻ hơn trong đợt mở bán.
            lines.append(message(state, "fare_already_cheapest", end=window_end))
        lines.append(message(state, f"fare_{kind}", **fields, money=money(best["unitPrice"], language),
                             day=_short(best_day), flight=_flight_text(state, best)))
        shown = [product for _, product in ranked[:MAX_FARE_CARDS]]
    lines.append(message(state, "fare_note"))
    return title, "\n".join(lines), _unique(shown)


def _unique(products: list[dict]) -> list[dict]:
    seen: set[str] = set()
    return [p for p in products if not (p["productId"] in seen or seen.add(p["productId"]))][:MAX_FARE_CARDS]


def why_text(state: dict, origin: str, destination: str, products: list[dict], today: date,
             pending: dict) -> tuple[str, str, list[dict]]:
    """"Tại sao đắt" sau khi báo giá (chat thử 11/10: trợ lý lặp lại câu báo giá rẻ nhất).

    Catalog chỉ có giá, hãng, giờ và ngày bay, không có hạng vé hay lý do định giá: câu nói rõ điều đó, rồi chỉ nêu
    những gì dữ liệu cho thấy (so với vé rẻ nhất và mức giá phổ biến của tuyến, hãng, còn mấy ngày nữa bay), kèm thẻ của
    chính vé đó để người dùng mở trang vé máy bay tự xem. Không đoán lý do.
    """
    title = message(state, "fare_why_title", origin=origin, destination=destination)
    usable = _one_way(products, today)
    if not usable:
        return title, message(state, "fare_none", origin=origin, destination=destination), []
    language = state.get("language", "vi")
    shown_ids = pending.get("shown") or []
    subject = next((p for p in usable if shown_ids and p["productId"] == shown_ids[0]), None)
    if subject is None:
        sign = -1 if pending.get("kind") == DEAREST else 1
        subject = min(usable, key=lambda p: (sign * float(p["unitPrice"]), p["productId"]))
    prices = sorted(float(p["unitPrice"]) for p in usable)
    cheapest = min(usable, key=lambda p: (float(p["unitPrice"]), p["productId"]))
    typical = median(prices)
    price = float(subject["unitPrice"])
    day = flight_rules.flight_date(subject)
    fields = {"flight": _flight_text(state, subject), "day": _short(day), "money": money(price, language),
              "cheapest": money(cheapest["unitPrice"], language), "typical": money(typical, language)}
    lines = [message(state, "fare_why_no_reason")]
    if price > typical:
        lines.append(message(state, "fare_why_high", **fields, ratio=_ratio(state, price, float(cheapest["unitPrice"])),
                             typical_ratio=_ratio(state, price, typical)))
    else:
        lines.append(message(state, "fare_why_low", **fields, percent=round(100 * (1 - price / typical))
                             if typical else 0))
    airline = flight_rules.brief(subject).get("airline")
    cheap_airline = flight_rules.brief(cheapest).get("airline")
    if price > typical and airline and cheap_airline and fold(airline) != fold(cheap_airline):
        lines.append(message(state, "fare_why_airline", airline=airline, cheap_airline=cheap_airline))
    if day is not None and 0 <= (day - today).days <= SOON_DAYS:
        lines.append(message(state, "fare_why_soon", days=(day - today).days))
    lines.append(message(state, "fare_why_hint"))
    return title, "\n".join(lines), [subject]


def _ratio(state: dict, value: float, base: float) -> str:
    """"gấp 21 lần" khi gấp từ 2 lần, "cao hơn 35%" khi ít hơn."""
    if base <= 0:
        return ""
    if value >= 2 * base:
        return message(state, "fare_times", times=f"{value / base:.0f}")
    return message(state, "fare_percent_more", percent=round(100 * (value / base - 1)))


async def _origin_routes(tools: ToolExecutorPort, origin: str, destinations: list[str],
                         timeout_seconds: float) -> dict[str, list[dict]]:
    """Điểm đến → chuyến bay từ `origin` (chỉ các tuyến catalog có). Lỗi tải một tuyến thì bỏ tuyến đó."""
    async def flights_to(destination: str) -> tuple[str, list[dict]]:
        try:
            routes = await _all(tools, {"taxonomy": "flight", "destination": destination}, timeout_seconds)
            route = next((item for item in routes
                          if fold((item.get("attributes") or {}).get("originCity")) == fold(origin)), None)
            if route is None:
                return destination, []
            return destination, await _all(tools, {"parentProductId": route["productId"], "availableOnly": True},
                                           timeout_seconds)
        except Exception:
            return destination, []

    pairs = await asyncio.gather(*(flights_to(name) for name in destinations if fold(name) != fold(origin)))
    return {name: products for name, products in pairs if products}


def anywhere_text(state: dict, origin: str, by_destination: dict[str, list[dict]], today: date,
                  kind: str) -> tuple[str, str, list[dict]]:
    """(tiêu đề, câu, chuyến hiện thành thẻ) so vé một chiều từ `origin` tới mọi điểm đến có chuyến: tuyến rẻ nhất (hoặc
    đắt nhất) trước; thẻ là chuyến tốt nhất của vài tuyến đầu."""
    language = state.get("language", "vi")
    best = []
    for destination, products in by_destination.items():
        ranked = _by_day(_one_way(products, today), kind)
        if ranked:
            best.append((destination, *ranked[0]))
    title = message(state, "fare_anywhere_title", origin=origin)
    if not best:
        return title, message(state, "fare_anywhere_none", origin=origin), []
    sign = -1 if kind == DEAREST else 1
    best.sort(key=lambda item: (sign * float(item[2]["unitPrice"]), item[1]))
    destination, day, product = best[0]
    lines = [message(state, f"fare_anywhere_{kind}", origin=origin, destination=destination,
                     money=money(product["unitPrice"], language), day=day.strftime("%d/%m"),
                     flight=_flight_text(state, product))]
    others = [message(state, "fare_route_item", destination=name, money=money(item["unitPrice"], language))
              for name, _, item in best[1:1 + OTHER_ROUTES]]
    if others:
        lines.append(message(state, f"fare_anywhere_others_{kind}", routes=", ".join(others)))
    lines.append(message(state, "fare_note"))
    return title, "\n".join(lines), [item for _, _, item in best[:MAX_FARE_CARDS]]


def _return_day(intent: dict) -> str | None:
    """Ngày bay về của chuyến: ngày đi + số ngày - 1 (như chặng về của lịch)."""
    try:
        start = date.fromisoformat(str(intent.get("startDate")))
    except ValueError:
        return None
    return (start + timedelta(days=max(int(intent.get("days") or 1), 1) - 1)).isoformat()


def _chips(state: dict, destination: str | None, extra: list[str]) -> list[str]:
    chips = list(extra)
    if destination and not state.get("plan_consent"):
        chips.append(message(state, "chip_plan", destination=destination))
    elif destination and any((state.get("intent") or {}).get(key) is None for key in REQUIRED_FIELDS):
        chips.append(message(state, "chip_continue"))
    previous = {fold(item) for item in state.get("last_suggestions") or []}
    return [chip for chip in dict.fromkeys(chips) if fold(chip) not in previous][:3]


def _response(state: dict, title: str | None, body: str, chips: list[str], intent: dict,
              shown: list[dict] | None = None) -> dict:
    """Câu trả lời giá vé; `shown` là chuyến thật của catalog, thành thẻ ngày–giá (`searchResults.flight`, 1.25.0)."""
    response = {"status": "NEEDS_CLARIFICATION", "conversationId": state["conversation_id"],
                "question": titled(title, body), "knownIntent": intent}
    if chips:
        response["suggestions"] = chips
    if shown:
        response["searchResults"] = {"flight": [summary(product) for product in shown]}
    return response


def _cards(shown: list[dict]) -> dict:
    """`candidates` để `finalize` kiểm từng thẻ là đúng chuyến đã tra (`validation._explore_issues`)."""
    return {"candidates": {product["productId"]: product for product in shown}}


def chip_choices(chips: dict[str, dict]) -> dict:
    """Nút của câu trả lời giá vé → điều nút đó hỏi, để lượt bấm nút đi thẳng nhánh giá vé (`chip_reply`)."""
    return {fold(text): {key: value for key, value in ask.items() if value} for text, ask in chips.items()}


def chip_reply(state: dict) -> dict | None:
    """Người dùng bấm (hoặc gõ y nguyên) một nút của câu trả lời giá vé lượt trước ("Từ TP. Hồ Chí Minh", "Đắt nhất thì
    sao?"): đi thẳng nhánh giá vé với điều nút đó hỏi, không qua LLM. Chat thử 11/10: LLM hiểu "Từ TP. Hồ Chí Minh" sau
    câu "Bạn bay từ đâu ra Hà Nội?" là hỏi về Sài Gòn và trả lời Sài Gòn có gì chơi. Chỉ khớp nút do chính code tạo."""
    pending = state.get("pending_fare") or {}
    ask = (pending.get("chips") or {}).get(fold(state.get("query", "")))
    if ask is None:
        return None
    return {"fare_ask": dict(ask), "interaction_type": "conversation", "refusal": False, "decision": "explore",
            "fare_question": True, "missing_fields": [], "explore_place": None, "explore_city": None,
            "explore_focus": None, "explore_price": None, "other_questions": [], "form_request": False,
            "events": [event("classify", "route fare (button)")]}


def _kind_key(kind: str) -> dict:
    """Ghi kiểu câu hỏi (đắt nhất) vào `pending_fare` để lượt trả lời nơi đi còn nhớ; rẻ nhất là mặc định nên không ghi."""
    return {"kind": kind} if kind == DEAREST else {}


def _talked_about(state: dict, intent: dict, destination: str | None) -> dict:
    """Chưa xin lập lịch: nơi đang hỏi vé thành điểm đến đang nói tới của chuyến (như lượt khám phá vẫn ghi), để lượt sau
    "khách sạn", "chỗ đó có gì" biết là nói về đâu (trace LangSmith 2026-10-11: LLM để trống thành phố vì `trip_so_far`
    ghi "chưa có thông tin chuyến đi"). Đã đồng ý lập lịch hoặc đã có lịch thì câu hỏi vé không đổi chuyến."""
    if destination is None or state.get("plan_consent") or state.get("previous_plan"):
        return intent
    return {**intent, "destination": destination}


def _kind_question(state: dict, destination: str | None, intent: dict, supported: list[str],
                   flight_ask: dict | None = None) -> dict:
    """Hỏi lại "vé" nào: vé máy bay, khách sạn hay vé tham quan, kèm ba nút tự đủ nghĩa. `flight_ask`: điều nút vé máy
    bay hỏi tiếp (nơi đi, "đi đâu cũng được" của câu gốc: "tao ở sài gòn, đi đâu cũng đc miễn vé rẻ")."""
    intent = _talked_about(state, intent, destination)
    place = destination or ""
    suffix = "_at" if destination else ""
    flight_chip = message(state, f"chip_kind_flight{suffix}", destination=place)
    chips = [flight_chip, message(state, f"chip_kind_hotel{suffix}", destination=place),
             message(state, f"chip_kind_sights{suffix}", destination=place)]
    body = message(state, f"fare_ask_kind{suffix}", destination=place)
    response = _response(state, None, body, chips, intent)
    return {"response": response, "intent": intent, "supported_destinations": supported,
            "pending_fare": {"destination": destination, "kind_asked": True,
                             "chips": chip_choices({flight_chip: {"destination": destination, **(flight_ask or {})}})},
            "final_answer": response["question"],
            "events": [event("explore", "fare question, ticket kind unclear", destination=destination)]}


async def _anywhere(state: dict, origin: str | None, tools: ToolExecutorPort, supported: list[str], intent: dict,
                    timeout_seconds: float, today: date, kind: str) -> dict:
    """"Đi đâu cũng được, miễn đắt nhất": so các tuyến từ nơi đi; chưa biết nơi đi thì hỏi."""
    if origin is None:
        names = supported[:ORIGIN_CHIPS]
        chips = {message(state, "chip_fare_from", origin=name): {"origin": name, "anywhere": True,
                                                                 "dearest": kind == DEAREST} for name in names}
        response = _response(state, None, message(state, "fare_ask_origin_anywhere"), list(chips), intent)
        return {"response": response,
                "pending_fare": {"anywhere": True, **_kind_key(kind), "chips": chip_choices(chips)},
                "supported_destinations": supported, "final_answer": response["question"],
                "events": [event("explore", "fare question anywhere, origin missing")]}
    origin = canonical_city(origin)
    by_destination = await _origin_routes(tools, origin, supported, timeout_seconds)
    title, body, shown = anywhere_text(state, origin, by_destination, today, kind)
    other = DEAREST if kind == CHEAPEST else CHEAPEST
    other_chip = message(state, f"chip_fare_{other}_anywhere")
    chips = [other_chip]
    best = _anywhere_best(by_destination, today, kind)
    if best:
        chips.append(message(state, "chip_sights", destination=best))
    response = _response(state, title, body, chips, intent, shown)
    return {"response": response, **_cards(shown),
            "pending_fare": {"origin": origin, "anywhere": True, "answered": True, "best": best, "kind": kind,
                             "shown": [product["productId"] for product in shown],
                             "chips": chip_choices({other_chip: {"origin": origin, "anywhere": True,
                                                                 "dearest": other == DEAREST}})},
            "supported_destinations": supported, "final_answer": response["question"],
            "events": [event("explore", "fare answered anywhere", origin=origin, routes=len(by_destination))]}


def _anywhere_best(by_destination: dict[str, list[dict]], today: date, kind: str) -> str | None:
    """Điểm đến có vé rẻ nhất (đắt nhất) trong các tuyến vừa so, như dòng đầu của `anywhere_text`."""
    sign = -1 if kind == DEAREST else 1
    best = [(sign * float(ranked[0][1]["unitPrice"]), ranked[0][0], name) for name, products in by_destination.items()
            if (ranked := _by_day(_one_way(products, today), kind))]
    return min(best)[2] if best else None


def _place(name: str | None, names: list[str]) -> str | None:
    """Tên trong catalog cho chữ LLM đọc ra ("sg", "Sài Gòn", "saigon" → "TP. Hồ Chí Minh"); không khớp tên nào thì giữ
    nguyên chữ (nơi đi ngoài danh sách điểm đến, như "Cần Thơ", vẫn tra được tuyến)."""
    if not name or not name.strip():
        return None
    found = _cities(name, names)
    return found[0][1] if found else " ".join(name.split())


def _day_asked(ask: dict, today: date) -> str | None:
    """Ngày bay người dùng hỏi (LLM đã đổi "thứ 7 này" thành ngày); ngày đã qua thì bỏ."""
    try:
        day = date.fromisoformat(str(ask.get("day")))
    except ValueError:
        return None
    return day.isoformat() if day >= today else None


async def answer(state: dict, *, tools: ToolExecutorPort | None, supported: list[str] | None,
                 timeout_seconds: float, today: date | None = None) -> dict:
    """Update của nhánh giá vé trong `explore`: hỏi lại chỗ thiếu, hoặc tư vấn vé (FR-AGT-07).

    Đọc `fare_ask` (LLM đã hiểu từ câu chữ, hoặc nút vừa bấm qua `chip_reply`). Chỗ LLM để trống lấy từ lần hỏi lại còn
    treo (`pending_fare`) rồi từ chuyến (`intent`). Trả lời được: vé rẻ nhất/đắt nhất, một ngày cụ thể, một khung giờ,
    ngày nào có/không có chuyến, và "tại sao đắt" của vé vừa báo. Chuyến nêu trong câu và các ngày khác thành thẻ
    ngày–giá (`searchResults.flight`). Sau khi báo giá, `pending_fare` giữ tuyến vừa trả lời (`answered`), kiểu câu
    hỏi, các chuyến vừa hiện và nút của lượt này, để câu hỏi tiếp còn ngữ cảnh; `classify` bỏ nó khi người dùng chuyển
    sang chuyện khác.
    """
    today = today or datetime.now(flight_rules.VIETNAM).date()
    supported = supported or []
    ask = state.get("fare_ask") or {}
    intent = dict(state.get("intent") or {})
    pending = state.get("pending_fare") or {}
    if ask.get("dearest"):
        kind = DEAREST
    elif (ask.get("why") or ask.get("other_days")) and not ask.get("cheaper"):
        # "ngày khác thì sao", "tại sao đắt" sau giá đắt nhất: giữ kiểu của lần báo giá trước. Hỏi ngày, giờ bay, ngày nào
        # có chuyến thì mặc định rẻ nhất (chat thử 11/10: "muốn đi sớm" sau "đắt nhất" ra toàn vé đắt).
        kind = pending.get("kind") or CHEAPEST
    else:
        kind = CHEAPEST
    if pending.get("kind_asked"):
        # Vừa hỏi lại loại vé và người dùng chọn vé máy bay: điểm đến của lần hỏi lại vẫn dùng được.
        pending = {"destination": pending.get("destination")}
        state = {**state, "pending_fare": pending}
    destination = _place(ask.get("destination"), supported) or _known(state, "destination")
    origin_text = ask.get("origin")
    if ask.get("kind_unclear"):
        flight_ask = {"origin": _place(origin_text, supported), "anywhere": ask.get("anywhere"),
                      "dearest": ask.get("dearest")}
        place = None if ask.get("anywhere") else destination or _place(state.get("explore_city"), supported)
        return _kind_question(state, place, intent, supported, flight_ask)
    if tools is not None and getattr(tools, "supports_catalog", False) and (
            ask.get("anywhere") or (pending.get("anywhere") and not ask.get("destination"))):
        origin = _place(origin_text, supported) or _known(state, "origin")
        return await _anywhere(state, origin, tools, supported, intent, timeout_seconds, today, kind)
    if destination is None:
        origin = _place(origin_text, supported) or _known(state, "origin")
        chips = {message(state, "chip_fare_to", destination=name): {"destination": name, "origin": origin,
                                                                    "dearest": kind == DEAREST}
                 for name in supported[:ORIGIN_CHIPS]}
        update = {"pending_fare": {"origin": origin, **_kind_key(kind), "chips": chip_choices(chips)}}
        return {"response": _response(state, None, message(state, "fare_ask_destination"),
                                      _chips(state, None, list(chips)), intent),
                "supported_destinations": supported, **update,
                "events": [event("explore", "fare question, destination missing")]}
    intent = _talked_about(state, intent, destination)
    if tools is None or not getattr(tools, "supports_catalog", False):
        return {"response": _response(state, None, message(state, "fare_unavailable"), [], intent), "intent": intent,
                "events": [event("explore", "fare question, catalog unavailable")]}
    try:
        origins = await _routes(tools, destination, timeout_seconds)
    except Exception:
        origins = None
    if origins is None:
        return {"response": _response(state, None, message(state, "fare_unavailable"), [], intent),
                "pending_fare": {"destination": destination}, "events": [event("explore", "fare routes failed")]}
    # Nơi đi có thể không phải điểm đến của catalog (Hải Phòng, Cần Thơ): đối chiếu cả với các nơi có chuyến tới đó.
    origin = _place(origin_text, [*origins, *supported]) or _known(state, "origin")
    origin = canonical_city(origin) if origin else None
    start = _day_asked(ask, today)
    if ask.get("return_leg") and intent.get("origin") and intent.get("destination") and intent.get("startDate"):
        # "chuyến bay về mấy giờ" khi đã có lịch: chiều về của chính chuyến đi (điểm đến → nơi đi), đúng ngày cuối
        # (chat thử M11). Lấy từ chuyến, không từ chữ LLM đọc ra, để chiều bay không bị đảo hai lần.
        origin, destination = canonical_city(intent["destination"]), canonical_city(intent["origin"])
        start = _return_day(intent)
    if origin is None:
        chips = {message(state, "chip_fare_from", origin=name): {**ask, "origin": name, "destination": destination,
                                                                 "kind_unclear": False}
                 for name in origins[:ORIGIN_CHIPS]}
        body = message(state, "fare_ask_origin", destination=destination,
                       origins=", ".join(origins[:ORIGIN_CHIPS])) if origins else \
            message(state, "fare_no_routes", destination=destination)
        return {"response": _response(state, None, body, _chips(state, destination, list(chips)), intent),
                "intent": intent, "supported_destinations": supported,
                "pending_fare": {"destination": destination, **_kind_key(kind), "chips": chip_choices(chips)},
                "events": [event("explore", "fare question, origin missing", destination=destination)]}
    options = await flight_options(tools, {"origin": origin, "destination": destination, "days": 2},
                                   {}, timeout_seconds, state.get("request_id", "unknown"))
    if not state.get("previous_plan") and not ask.get("return_leg"):
        # Chưa có lịch: nơi đi vừa biết được ghi cho chuyến. Đã có lịch thì câu hỏi giá vé không đổi chuyến.
        intent = {**intent, "origin": origin if not intent.get("origin") else intent["origin"]}
    same_route = pending.get("answered") and {pending.get("origin"), pending.get("destination")} == {origin, destination}
    shown: list[dict] = []
    if options.get("status") == flight_rules.UNAVAILABLE:
        title, body = None, message(state, "fare_unavailable")
    elif options.get("status") or not options.get("outbound"):
        title, body = None, message(state, "fare_none", origin=origin, destination=destination)
    elif ask.get("why") and same_route:
        title, body, shown = why_text(state, options.get("origin") or origin, destination, options["outbound"], today,
                                      pending)
    else:
        title, body, shown = answer_text(state, options.get("origin") or origin, destination, options["outbound"],
                                         today, kind, start, more=bool(ask.get("other_days") and same_route),
                                         cheaper=bool(ask.get("cheaper") and same_route),
                                         period=ask.get("time_of_day"),
                                         # Câu có ngày cụ thể trả lời đúng ngày đó, kể cả khi LLM đánh dấu cả "ngày nào có".
                                         availability=bool(ask.get("availability")) and not ask.get("day"))
    other = DEAREST if kind == CHEAPEST else CHEAPEST
    route = {"origin": origin, "destination": destination}
    fare_chips = {message(state, f"chip_fare_{other}"): {**route, "dearest": other == DEAREST}}
    if not ask.get("availability"):
        fare_chips[message(state, "chip_fare_availability")] = {**route, "availability": True}
    # Câu gộp nhiều ý ("hà nội có gì chơi, vé bay từ sg bao nhiêu, ks nào gần hồ gươm"): trả lời vé, phần còn lại thành nút.
    asks = state.get("other_questions") or []
    if asks:
        body = f"{body}\n{message(state, 'fare_other_asks')}"
    extra = asks or [*fare_chips, message(state, "chip_hotels", destination=destination)]
    response = _response(state, title, body, _chips(state, destination, extra), intent, shown)
    if start is not None and ask.get("return_leg"):
        origin, destination = destination, origin  # tuyến của chuyến, để câu hỏi tiếp vẫn đúng chiều đi
        fare_chips = {text: {**value, "origin": origin, "destination": destination}
                      for text, value in fare_chips.items()}
    return {"response": response, **_cards(shown),
            "pending_fare": {"origin": origin, "destination": destination, "answered": True, "kind": kind,
                             "shown": [product["productId"] for product in shown],
                             "chips": chip_choices(fare_chips)},
            "intent": intent, "supported_destinations": supported, "final_answer": response["question"],
            "events": [event("explore", "fare answered", origin=origin, destination=destination, kind=kind,
                             status=options.get("status"), cards=len(shown))]}
