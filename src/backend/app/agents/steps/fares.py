"""Hỏi giá vé máy bay trước khi lập lịch (kịch bản bản 5 cảnh 6, người dùng chốt 2026-10-10).

"Vé ra Hà Nội bao nhiêu?": thiếu nơi đi hoặc điểm đến thì hỏi lại đúng chỗ thiếu (kèm nút những nơi có chuyến); đủ thì
báo vé một chiều rẻ nhất trong cửa sổ bán của catalog (hoặc đúng ngày đi nếu đã có), cùng vài ngày rẻ khác. Mọi thứ
tất định: tuyến và chuyến lấy qua `application/itinerary/flights.flight_options` như chặng bay của lịch trình, câu do code
dựng, không gọi LLM. Chỉ tiếng Việt ở đợt này (người dùng chốt 2026-10-10).
"""
from __future__ import annotations

import re
from datetime import date, datetime

from src.backend.app.application.itinerary.flights import _all, canonical_city, flight_options
from src.backend.app.application.ports.itinerary_tools import ToolExecutorPort
from src.backend.app.domain.itinerary import flights as flight_rules
from src.backend.app.domain.itinerary.normalization import fold
from src.backend.app.domain.search.normalize import DESTINATION_ALIASES

from .classification import REQUIRED_FIELDS
from .messages import event, message, money, titled

#: Câu nhắc tới vé hoặc chuyến bay (so trên chuỗi đã `fold`); "bay" đứng một mình dễ trùng "bây giờ" nên phải đi kèm hướng.
_FLIGHT = re.compile(r"\b(?:ve may bay|ve bay|chuyen bay|may bay|bay (?:ra|vao|tu|den|toi|ve|di)|"
                     r"ve (?:ra|vao|tu|den|toi|di|khu hoi|mot chieu))\b")
#: Câu hỏi giá.
_PRICE = re.compile(r"\b(?:bao nhieu|gia(?! dinh)|re nhat|bao tien|het bao|mat bao)\b")
#: Câu trả lời cho lần hỏi lại nơi đi/điểm đến: ngắn, không phải câu hỏi, không phải lời thôi.
MAX_REPLY_WORDS = 5
_DECLINE = re.compile(r"^(?:thoi|khong|ko|k|khoi|cam on|thanks|ok thoi)\b")
#: Số ngày rẻ khác nêu thêm, và số nút nơi đi.
OTHER_DAYS = 3
ORIGIN_CHIPS = 3


def asked(state: dict) -> bool:
    """Câu này hỏi giá vé máy bay; hoặc là câu trả lời ngắn cho lần hỏi lại nơi đi, điểm đến của lượt trước."""
    query = fold(state.get("query", ""))
    if _FLIGHT.search(query) and _PRICE.search(query):
        return True
    reply = state.get("query", "")
    return (bool(state.get("pending_fare")) and 0 < len(query.split()) <= MAX_REPLY_WORDS and "?" not in reply
            and not _DECLINE.match(query))


def detected(state: dict) -> dict | None:
    """Update của `classify` khi câu hỏi giá vé (đi `explore`, nhánh giá vé); None thì đi luồng thường.

    Đã có lịch thì không bắt ở đây: giá vé của lịch nằm trong lịch, đổi vé đi `changes`.
    """
    if state.get("previous_plan") or not asked(state):
        return None
    return {"decision": "explore", "fare_question": True, "interaction_type": "conversation", "missing_fields": [],
            "events": [event("classify", "route fare question")]}


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


#: "từ <nơi> ra/đến ...": nơi đi người dùng nói, kể cả nơi catalog không có chuyến (để nói rõ là chưa có chuyến).
_FROM_PHRASE = re.compile(r"\b(?:từ|tu)\s+(.+?)(?=\s+(?:ra|vào|vao|đến|den|tới|toi|về|ve|đi|di|bay|giá|gia|bao)\b|[?.,!]|$)",
                          re.IGNORECASE)
MAX_PLACE_WORDS = 4


def _from_phrase(text: str) -> str | None:
    match = _FROM_PHRASE.search(text or "")
    if not match:
        return None
    place = " ".join(match.group(1).split())
    return place if 0 < len(place.split()) <= MAX_PLACE_WORDS else None


def _bare_reply(state: dict) -> str | None:
    """Trả lời câu hỏi lại nơi đi bằng đúng tên một nơi catalog không có chuyến ("Cần Thơ")."""
    if not (state.get("pending_fare") or {}).get("destination"):
        return None
    place = " ".join(str(state.get("query", "")).strip(" .!").split())
    return place if 0 < len(place.split()) <= MAX_PLACE_WORDS else None


def _toward(text: str, position: int) -> bool:
    """Tên ở `position` đứng sau từ chỉ hướng tới ("ra", "vào", "đến"): là điểm đến."""
    before = f" {fold(text)} "[:position].split()
    return bool(before) and before[-1] in ("ra", "vao", "den", "toi", "ve")


def _origin_named(text: str, cities: list[tuple[int, str]]) -> str | None:
    """Nơi đứng sau "từ" là nơi đi; hai nơi không có "từ" ("Sài Gòn ra Hà Nội") thì nơi đầu là nơi đi."""
    padded = f" {fold(text)} "
    for position, name in cities:
        if padded[max(0, position - 4):position].endswith(" tu"):
            return name
    return cities[0][1] if len(cities) >= 2 else None


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


def answer_text(state: dict, origin: str, destination: str, products: list[dict], today: date) -> tuple[str, str]:
    """(tiêu đề, câu) cho vé một chiều `origin` → `destination`; `products` là chuyến của tuyến đó."""
    start = (state.get("intent") or {}).get("startDate")
    usable = [p for p in products if flight_rules._bookable(p) and not flight_rules._is_round_trip(p)
              and (day := flight_rules.flight_date(p)) is not None and day >= today
              and (start is None or day.isoformat() == start)]
    title = message(state, "fare_title", origin=origin, destination=destination)
    if not usable:
        key = "fare_none_on_day" if start else "fare_none"
        return title, message(state, key, origin=origin, destination=destination, day=_day(start))
    cheapest_by_day: dict[date, dict] = {}
    for product in sorted(usable, key=lambda p: (float(p["unitPrice"]), flight_rules._departure_minutes(p))):
        cheapest_by_day.setdefault(flight_rules.flight_date(product), product)
    ranked = sorted(cheapest_by_day.items(), key=lambda item: (float(item[1]["unitPrice"]), item[0]))
    day, best = ranked[0]
    language = state.get("language", "vi")
    lines = [message(state, "fare_on_day" if start else "fare_cheapest", origin=origin, destination=destination,
                     money=money(best["unitPrice"], language), day=day.strftime("%d/%m"),
                     flight=_flight_text(state, best))]
    others = [message(state, "fare_other_day", day=other_day.strftime("%d/%m"),
                      money=money(product["unitPrice"], language)) for other_day, product in ranked[1:1 + OTHER_DAYS]]
    if others and not start:
        lines.append(message(state, "fare_other_days", days=", ".join(others)))
    lines.append(message(state, "fare_note"))
    return title, "\n".join(lines)


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


async def answer(state: dict, *, tools: ToolExecutorPort | None, supported: list[str] | None,
                 timeout_seconds: float, today: date | None = None) -> dict:
    """Update của nhánh giá vé trong `explore`: hỏi lại chỗ thiếu, hoặc báo vé rẻ nhất."""
    today = today or datetime.now(flight_rules.VIETNAM).date()
    supported = supported or []
    query = state.get("query", "")
    intent = dict(state.get("intent") or {})
    named = _cities(query, supported)
    origin_named = _origin_named(query, named)
    pending = state.get("pending_fare") or {}
    if origin_named is None and len(named) == 1 and pending.get("destination") and not pending.get("origin") \
            and not _toward(query, named[0][0]):
        # Trả lời câu hỏi lại "Bạn bay từ đâu ra Nha Trang?" bằng một tên ("Hà Nội"): đó là nơi đi.
        origin_named = named[0][1]
    destinations = [name for _, name in named if name != origin_named]
    destination = destinations[0] if destinations else _known(state, "destination")
    if destination is None:
        chips = [message(state, "chip_fare_to", destination=name) for name in supported[:ORIGIN_CHIPS]]
        update = {"pending_fare": {"origin": origin_named or _known(state, "origin")}}
        return {"response": _response(state, None, message(state, "fare_ask_destination"), _chips(state, None, chips),
                                      intent),
                "supported_destinations": supported, **update,
                "events": [event("explore", "fare question, destination missing")]}
    if tools is None or not getattr(tools, "supports_catalog", False):
        return {"response": _response(state, None, message(state, "fare_unavailable"), [], intent),
                "events": [event("explore", "fare question, catalog unavailable")]}
    try:
        origins = await _routes(tools, destination, timeout_seconds)
    except Exception:
        origins = None
    if origins is None:
        return {"response": _response(state, None, message(state, "fare_unavailable"), [], intent),
                "pending_fare": {"destination": destination}, "events": [event("explore", "fare routes failed")]}
    origin = origin_named
    if origin is None:
        # Nơi đi không phải điểm đến của catalog (Hải Phòng, Vinh): tìm trong các nơi có chuyến tới điểm đến.
        found = _cities(query, origins)
        origin = found[0][1] if found else (_from_phrase(query) or _known(state, "origin") or _bare_reply(state))
    origin = canonical_city(origin) if origin else None
    if origin is None:
        chips = [message(state, "chip_fare_from", origin=name) for name in origins[:ORIGIN_CHIPS]]
        body = message(state, "fare_ask_origin", destination=destination,
                       origins=", ".join(origins[:ORIGIN_CHIPS])) if origins else \
            message(state, "fare_no_routes", destination=destination)
        return {"response": _response(state, None, body, _chips(state, destination, chips), intent),
                "pending_fare": {"destination": destination}, "supported_destinations": supported,
                "events": [event("explore", "fare question, origin missing", destination=destination)]}
    options = await flight_options(tools, {"origin": origin, "destination": destination, "days": 2},
                                   {}, timeout_seconds, state.get("request_id", "unknown"))
    intent = {**intent, "origin": origin if not intent.get("origin") else intent["origin"]}
    if options.get("status") == flight_rules.UNAVAILABLE:
        title, body = None, message(state, "fare_unavailable")
    elif options.get("status") or not options.get("outbound"):
        title, body = None, message(state, "fare_none", origin=origin, destination=destination)
    else:
        title, body = answer_text(state, options.get("origin") or origin, destination, options["outbound"], today)
    response = _response(state, title, body, _chips(state, destination, [message(state, "chip_hotels",
                                                                                   destination=destination)]), intent)
    return {"response": response, "pending_fare": None, "intent": intent, "supported_destinations": supported,
            "final_answer": response["question"],
            "events": [event("explore", "fare answered", origin=origin, destination=destination,
                             status=options.get("status"))]}
