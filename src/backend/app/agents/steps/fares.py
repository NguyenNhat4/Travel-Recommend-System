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

from src.backend.app.application.itinerary.flights import _all, canonical_city, flight_options
from src.backend.app.application.ports.itinerary_tools import ToolExecutorPort
from src.backend.app.domain.itinerary import flights as flight_rules
from src.backend.app.domain.itinerary.normalization import fold
from src.backend.app.domain.search.normalize import DESTINATION_ALIASES

from .classification import REQUIRED_FIELDS
from .messages import event, message, money, titled

#: Số ngày rẻ khác nêu thêm, số nút nơi đi, và số tuyến nêu khi so nhiều điểm đến.
OTHER_DAYS = 3
ORIGIN_CHIPS = 3
OTHER_ROUTES = 3
#: Kiểu câu trả lời giá vé.
CHEAPEST, DEAREST = "cheapest", "dearest"


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
    item = flight_rules.brief(product)
    parts = [part for part in (item.get("airline"), item.get("flightNumber")) if part]
    if item.get("departure"):
        parts.append(message(state, "fare_departs", time=item["departure"]))
    return " ".join(parts)


def _one_way(products: list[dict], today: date) -> list[dict]:
    """Chuyến một chiều còn bán từ hôm nay."""
    return [p for p in products if flight_rules._bookable(p) and not flight_rules._is_round_trip(p)
            and (day := flight_rules.flight_date(p)) is not None and day >= today]


def _by_day(usable: list[dict], kind: str) -> list[tuple[date, dict]]:
    """Chuyến rẻ nhất (hoặc đắt nhất) của từng ngày, xếp từ rẻ nhất (hoặc đắt nhất) trở đi; hoà thì ngày sớm hơn."""
    sign = -1 if kind == DEAREST else 1
    best: dict[date, dict] = {}
    for product in sorted(usable, key=lambda p: (sign * float(p["unitPrice"]), flight_rules._departure_minutes(p))):
        best.setdefault(flight_rules.flight_date(product), product)
    return sorted(best.items(), key=lambda item: (sign * float(item[1]["unitPrice"]), item[0]))


def answer_text(state: dict, origin: str, destination: str, products: list[dict], today: date,
                kind: str = CHEAPEST, start: str | None = None, more: bool = False,
                cheaper: bool = False) -> tuple[str, str]:
    """(tiêu đề, câu) cho vé một chiều `origin` → `destination`; `products` là chuyến của tuyến đó.

    Đã có ngày đi: nêu vé của đúng ngày đó, rồi so với cả đợt đang mở bán ("rẻ nhất chưa?" phải trả lời được là còn ngày
    rẻ hơn, chat thử 10/10). `kind = DEAREST`: vé đắt nhất thay cho rẻ nhất. `more`: hỏi tiếp ngày khác của tuyến vừa
    báo, nêu các ngày kế tiếp. `cheaper`: hỏi còn vé rẻ hơn mức vừa báo, nói rõ khi không còn.
    """
    start = start or (state.get("intent") or {}).get("startDate")
    usable = _one_way(products, today)
    title = message(state, "fare_title", origin=origin, destination=destination)
    if not usable:
        return title, message(state, "fare_none", origin=origin, destination=destination)
    language = state.get("language", "vi")
    ranked = _by_day(usable, kind)
    window_end = max(day for day, _ in ranked).strftime("%d/%m")
    lines = []
    on_day = [item for item in ranked if item[0].isoformat() == start] if start else []
    best_day, best = ranked[0]
    fields = {"origin": origin, "destination": destination, "end": window_end}
    if start and on_day:
        day, product = on_day[0]
        lines.append(message(state, f"fare_on_day_{kind}", **fields, money=money(product["unitPrice"], language),
                             day=day.strftime("%d/%m"), flight=_flight_text(state, product)))
    elif start:
        lines.append(message(state, "fare_none_on_day", **fields, day=_day(start)))
    if not on_day or on_day[0][0] != best_day:
        key = f"fare_window_{kind}" if start else f"fare_{kind}"
        lines.append(message(state, key, **fields, money=money(best["unitPrice"], language),
                             day=best_day.strftime("%d/%m"), flight=_flight_text(state, best)))
    elif start:
        lines.append(message(state, f"fare_is_best_{kind}", **fields))
    rest = [item for item in ranked[1:] if item[0].isoformat() != start]
    if more and len(rest) > OTHER_DAYS:
        # "ngày khác thì sao" sau khi đã báo giá: các ngày tiếp theo, không lặp lại ba ngày vừa nêu.
        rest = rest[OTHER_DAYS:]
    others = [message(state, f"fare_other_day_{kind}", day=other_day.strftime("%d/%m"),
                      money=money(product["unitPrice"], language))
              for other_day, product in rest[:OTHER_DAYS]]
    if others:
        lines.append(message(state, "fare_other_days", days=", ".join(others)))
    if cheaper and kind == CHEAPEST and not start:
        # "rẻ hơn nữa ko" sau khi đã báo giá rẻ nhất: nói thẳng là không còn vé rẻ hơn trong đợt mở bán.
        lines.insert(0, message(state, "fare_already_cheapest", end=window_end))
    lines.append(message(state, "fare_note"))
    return title, "\n".join(lines)


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
                  kind: str) -> tuple[str, str]:
    """(tiêu đề, câu) so vé một chiều từ `origin` tới mọi điểm đến có chuyến: tuyến rẻ nhất (hoặc đắt nhất) trước."""
    language = state.get("language", "vi")
    best = []
    for destination, products in by_destination.items():
        ranked = _by_day(_one_way(products, today), kind)
        if ranked:
            best.append((destination, *ranked[0]))
    title = message(state, "fare_anywhere_title", origin=origin)
    if not best:
        return title, message(state, "fare_anywhere_none", origin=origin)
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
    return title, "\n".join(lines)


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


def _response(state: dict, title: str | None, body: str, chips: list[str], intent: dict) -> dict:
    response = {"status": "NEEDS_CLARIFICATION", "conversationId": state["conversation_id"],
                "question": titled(title, body), "knownIntent": intent}
    if chips:
        response["suggestions"] = chips
    return response


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


def _kind_question(state: dict, destination: str | None, intent: dict, supported: list[str]) -> dict:
    """Hỏi lại "vé" nào: vé máy bay, khách sạn hay vé tham quan, kèm ba nút tự đủ nghĩa."""
    intent = _talked_about(state, intent, destination)
    place = destination or ""
    suffix = "_at" if destination else ""
    chips = [message(state, f"chip_kind_flight{suffix}", destination=place),
             message(state, f"chip_kind_hotel{suffix}", destination=place),
             message(state, f"chip_kind_sights{suffix}", destination=place)]
    body = message(state, f"fare_ask_kind{suffix}", destination=place)
    response = _response(state, None, body, chips, intent)
    return {"response": response, "pending_fare": {"destination": destination, "kind_asked": True}, "intent": intent,
            "supported_destinations": supported, "final_answer": response["question"],
            "events": [event("explore", "fare question, ticket kind unclear", destination=destination)]}


async def _anywhere(state: dict, origin: str | None, tools: ToolExecutorPort, supported: list[str], intent: dict,
                    timeout_seconds: float, today: date, kind: str) -> dict:
    """"Đi đâu cũng được, miễn đắt nhất": so các tuyến từ nơi đi; chưa biết nơi đi thì hỏi."""
    if origin is None:
        chips = [message(state, "chip_fare_from", origin=name) for name in supported[:ORIGIN_CHIPS]]
        response = _response(state, None, message(state, "fare_ask_origin_anywhere"), chips, intent)
        return {"response": response, "pending_fare": {"anywhere": True, **_kind_key(kind)},
                "supported_destinations": supported, "final_answer": response["question"],
                "events": [event("explore", "fare question anywhere, origin missing")]}
    origin = canonical_city(origin)
    by_destination = await _origin_routes(tools, origin, supported, timeout_seconds)
    title, body = anywhere_text(state, origin, by_destination, today, kind)
    other = DEAREST if kind == CHEAPEST else CHEAPEST
    chips = [message(state, f"chip_fare_{other}_anywhere")]
    best = _anywhere_best(by_destination, today, kind)
    if best:
        chips.append(message(state, "chip_sights", destination=best))
    response = _response(state, title, body, chips, intent)
    return {"response": response, "pending_fare": {"origin": origin, "anywhere": True, "answered": True, "best": best},
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


async def answer(state: dict, *, tools: ToolExecutorPort | None, supported: list[str] | None,
                 timeout_seconds: float, today: date | None = None) -> dict:
    """Update của nhánh giá vé trong `explore`: hỏi lại chỗ thiếu, hoặc báo vé rẻ nhất (đắt nhất).

    Đọc `fare_ask` (LLM đã hiểu từ câu chữ). Chỗ LLM để trống lấy từ lần hỏi lại còn treo (`pending_fare`) rồi từ chuyến
    (`intent`). Sau khi báo giá, `pending_fare` giữ tuyến vừa trả lời (`answered`) để câu hỏi tiếp ("đắt nhất thì sao",
    "ngày khác", "còn đi Đà Nẵng thì sao") còn nơi đi, nơi đến; `classify` bỏ nó khi người dùng chuyển sang chuyện khác.
    """
    today = today or datetime.now(flight_rules.VIETNAM).date()
    supported = supported or []
    ask = state.get("fare_ask") or {}
    intent = dict(state.get("intent") or {})
    pending = state.get("pending_fare") or {}
    kind = DEAREST if ask.get("dearest") else CHEAPEST
    if pending.get("kind_asked"):
        # Vừa hỏi lại loại vé và người dùng chọn vé máy bay: điểm đến của lần hỏi lại vẫn dùng được.
        pending = {"destination": pending.get("destination")}
        state = {**state, "pending_fare": pending}
    destination = _place(ask.get("destination"), supported) or _known(state, "destination")
    origin_text = ask.get("origin")
    if ask.get("kind_unclear"):
        return _kind_question(state, destination or _place(state.get("explore_city"), supported), intent, supported)
    if tools is not None and getattr(tools, "supports_catalog", False) and (
            ask.get("anywhere") or (pending.get("anywhere") and not ask.get("destination"))):
        origin = _place(origin_text, supported) or _known(state, "origin")
        return await _anywhere(state, origin, tools, supported, intent, timeout_seconds, today, kind)
    if destination is None:
        chips = [message(state, "chip_fare_to", destination=name) for name in supported[:ORIGIN_CHIPS]]
        update = {"pending_fare": {"origin": _place(origin_text, supported) or _known(state, "origin"),
                                   **_kind_key(kind)}}
        return {"response": _response(state, None, message(state, "fare_ask_destination"), _chips(state, None, chips),
                                      intent),
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
    start = None
    if ask.get("return_leg") and intent.get("origin") and intent.get("destination") and intent.get("startDate"):
        # "chuyến bay về mấy giờ" khi đã có lịch: chiều về của chính chuyến đi (điểm đến → nơi đi), đúng ngày cuối
        # (chat thử M11). Lấy từ chuyến, không từ chữ LLM đọc ra, để chiều bay không bị đảo hai lần.
        origin, destination = canonical_city(intent["destination"]), canonical_city(intent["origin"])
        start = _return_day(intent)
    if origin is None:
        chips = [message(state, "chip_fare_from", origin=name) for name in origins[:ORIGIN_CHIPS]]
        body = message(state, "fare_ask_origin", destination=destination,
                       origins=", ".join(origins[:ORIGIN_CHIPS])) if origins else \
            message(state, "fare_no_routes", destination=destination)
        return {"response": _response(state, None, body, _chips(state, destination, chips), intent), "intent": intent,
                "pending_fare": {"destination": destination, **_kind_key(kind)}, "supported_destinations": supported,
                "events": [event("explore", "fare question, origin missing", destination=destination)]}
    options = await flight_options(tools, {"origin": origin, "destination": destination, "days": 2},
                                   {}, timeout_seconds, state.get("request_id", "unknown"))
    if not state.get("previous_plan") and start is None:
        # Chưa có lịch: nơi đi vừa biết được ghi cho chuyến. Đã có lịch thì câu hỏi giá vé không đổi chuyến.
        intent = {**intent, "origin": origin if not intent.get("origin") else intent["origin"]}
    same_route = pending.get("answered") and {pending.get("origin"), pending.get("destination")} == {origin, destination}
    if options.get("status") == flight_rules.UNAVAILABLE:
        title, body = None, message(state, "fare_unavailable")
    elif options.get("status") or not options.get("outbound"):
        title, body = None, message(state, "fare_none", origin=origin, destination=destination)
    else:
        title, body = answer_text(state, options.get("origin") or origin, destination, options["outbound"], today,
                                  kind, start, more=bool(ask.get("other_days") and same_route),
                                  cheaper=bool(ask.get("cheaper") and same_route))
    other = DEAREST if kind == CHEAPEST else CHEAPEST
    # Câu gộp nhiều ý ("hà nội có gì chơi, vé bay từ sg bao nhiêu, ks nào gần hồ gươm"): trả lời vé, phần còn lại thành nút.
    asks = state.get("other_questions") or []
    if asks:
        body = f"{body}\n{message(state, 'fare_other_asks')}"
    extra = asks or [message(state, f"chip_fare_{other}"), message(state, "chip_hotels", destination=destination)]
    response = _response(state, title, body, _chips(state, destination, extra), intent)
    if start is not None:
        origin, destination = destination, origin  # tuyến của chuyến, để câu hỏi tiếp vẫn đúng chiều đi
    return {"response": response, "pending_fare": {"origin": origin, "destination": destination, "answered": True},
            "intent": intent, "supported_destinations": supported, "final_answer": response["question"],
            "events": [event("explore", "fare answered", origin=origin, destination=destination, kind=kind,
                             status=options.get("status"))]}
