"""Hỏi giá vé máy bay trước khi lập lịch (kịch bản bản 5 cảnh 6, người dùng chốt 2026-10-10).

"Vé ra Hà Nội bao nhiêu?": thiếu nơi đi hoặc điểm đến thì hỏi lại đúng chỗ thiếu (kèm nút những nơi có chuyến); đủ thì
báo vé một chiều rẻ nhất trong cửa sổ bán của catalog (hoặc đúng ngày đi nếu đã có), cùng vài ngày rẻ khác. Mọi thứ
tất định: tuyến và chuyến lấy qua `application/itinerary/flights.flight_options` như chặng bay của lịch trình, câu do code
dựng, không gọi LLM. Chỉ tiếng Việt ở đợt này (người dùng chốt 2026-10-10).
"""
from __future__ import annotations

import asyncio
import re
from datetime import date, datetime

from src.backend.app.application.itinerary.flights import _all, canonical_city, flight_options
from src.backend.app.application.ports.itinerary_tools import ToolExecutorPort
from src.backend.app.domain.itinerary import flights as flight_rules
from src.backend.app.domain.itinerary.normalization import fold
from src.backend.app.domain.itinerary.place_aliases import place_of
from src.backend.app.domain.search.normalize import DESTINATION_ALIASES

from .classification import REQUIRED_FIELDS
from .messages import event, message, money, titled

#: Câu nhắc tới vé hoặc chuyến bay (so trên chuỗi đã `fold`); "bay" đứng một mình dễ trùng "bây giờ" nên phải đi kèm hướng.
_FLIGHT = re.compile(r"\b(?:ve may bay|ve bay|chuyen bay|may bay|bay (?:ra|vao|tu|den|toi|ve|di)|"
                     r"ve (?:ra|vao(?! cua| cong)|tu|den|toi|di|khu hoi|mot chieu))\b")
#: Danh từ vé máy bay rõ ràng (không tính "bay từ", vốn hay nằm trong câu xin lập lịch).
_FLIGHT_NOUN = re.compile(r"\b(?:ve may bay|ve bay|chuyen bay|may bay)\b")
#: Câu hỏi giá.
_PRICE = re.compile(r"\b(?:bao nhieu|gia(?! dinh)|re nhat|bao tien|het bao|mat bao)\b")
#: Hỏi rẻ/đắt mà không nói "giá" ("vé nào rẻ", "đắt nhất thì sao").
_CHEAP = re.compile(r"\b(?:re|re hon|re nhat|mem nhat|thap nhat)\b")
_DEAR = re.compile(r"\b(?:dat nhat|mac nhat|cao nhat|dat hon|dat tien nhat)\b")
#: Người dùng nhắc là mình đang hỏi/xem vé ("tao hỏi vé máy bay mà").
_ASKING = re.compile(r"\b(?:hoi|xem|tra|check|tim|kiem|coi)\b")
#: Câu xin lập lịch, đặt vé, huỷ: không phải câu hỏi giá vé dù có chữ "vé", "bay".
_NOT_FARE = re.compile(r"\b(?:lap lich|len lich|ke hoach|lich trinh|dat ve|dat cho|book|mua ve|huy|doi sang|doi ve)\b")
#: "vé" chung chung và các loại vé khác máy bay (chat thử 10/10: "giờ tao đi hà nội thì vé nào rẻ").
_TICKET = re.compile(r"\bve\b")
_OTHER_KIND = re.compile(r"\b(?:khach san|ks|gia phong|thue phong|dat phong|phong nghi|tham quan|vao cong|vao cua|cap treo|show|tour|xe|tau|combo|"
                         r"cong vien|vui choi|bao tang)\b")
#: Câu hỏi tiếp sau khi đã báo giá vé ("đắt nhất thì sao", "ngày khác thì sao", "rẻ nhất chưa").
_FOLLOW_UP = re.compile(r"\b(?:dat nhat|mac nhat|cao nhat|re nhat|thap nhat|re hon|dat hon|ngay khac|ngay nao|"
                        r"chuyen khac|chuyen nao|som nhat|muon nhat|gio nao|con ve|khu hoi|chieu ve)\b")
#: Không quan trọng điểm đến ("đi đâu cũng được, miễn đắt nhất").
_ANYWHERE = re.compile(r"\b(?:di dau cung (?:duoc|dc)|dau cung (?:duoc|dc)|noi nao cung (?:duoc|dc)|bat ky dau|"
                       r"dau cung xong|di dau cung)\b")
#: Câu trả lời cho lần hỏi lại nơi đi/điểm đến: ngắn, không phải câu hỏi, không phải lời thôi.
MAX_REPLY_WORDS = 5
_DECLINE = re.compile(r"^(?:thoi|khong|ko|k|khoi|cam on|thanks|ok thoi)\b")
#: Số ngày rẻ khác nêu thêm, số nút nơi đi, và số tuyến nêu khi so nhiều điểm đến.
OTHER_DAYS = 3
ORIGIN_CHIPS = 3
OTHER_ROUTES = 3
#: Kiểu câu trả lời giá vé.
CHEAPEST, DEAREST = "cheapest", "dearest"


def vague(state: dict) -> bool:
    """Hỏi giá "vé" mà không nói vé gì ("vé nào rẻ", "vé ở Hà Nội bao nhiêu"): phải hỏi lại vé máy bay, khách sạn hay vé
    tham quan, không đoán (chat thử 10/10: trợ lý lập lịch luôn)."""
    query = fold(state.get("query", ""))
    if place_of(state.get("query", "")) is not None:
        # "bà nà vé bao nhiêu": vé vào một nơi nổi tiếng, không mơ hồ; lượt khám phá trả lời bằng thẻ nơi đó.
        return False
    return bool(_TICKET.search(query) and (_PRICE.search(query) or _CHEAP.search(query) or _DEAR.search(query))
                and not _FLIGHT.search(query) and not _OTHER_KIND.search(query) and not _NOT_FARE.search(query))


def mode(query: str) -> str:
    """Hỏi vé đắt nhất hay rẻ nhất (mặc định rẻ nhất)."""
    return DEAREST if _DEAR.search(fold(query)) else CHEAPEST


def anywhere(query: str) -> bool:
    return bool(_ANYWHERE.search(fold(query)))


def asked(state: dict) -> bool:
    """Câu này là câu hỏi giá vé máy bay, hoặc nối tiếp câu hỏi giá vé đang dở (`pending_fare`).

    - Có chữ vé/chuyến bay và hỏi giá, rẻ, đắt; hoặc nói rõ đang hỏi vé máy bay ("tao hỏi vé máy bay mà").
    - "vé" chung chung kèm hỏi giá: hỏi lại loại vé (`vague`).
    - Vừa hỏi lại loại vé: câu chọn vé máy bay là tiếp; chọn khách sạn, vé tham quan thì đi luồng thường.
    - Vừa báo giá vé: "đắt nhất thì sao", "ngày khác", "đi đâu cũng được miễn đắt nhất" là tiếp.
    - Đang hỏi lại nơi đi, điểm đến: câu trả lời ngắn là tiếp; hỏi rẻ/đắt nhất, "đâu cũng được" cũng là tiếp.
    """
    query = fold(state.get("query", ""))
    pending = state.get("pending_fare") or {}
    if _NOT_FARE.search(query):
        return False
    if place_of(state.get("query", "")) is not None and not _FLIGHT_NOUN.search(query):
        # "văn miếu vé vào cửa bao nhiêu": vé vào một nơi nổi tiếng, lượt khám phá trả lời bằng thẻ nơi đó.
        return False
    if vague(state):
        return True
    if _FLIGHT.search(query) and (_PRICE.search(query) or _CHEAP.search(query) or _DEAR.search(query)):
        return True
    if _FLIGHT_NOUN.search(query) and (_ASKING.search(query) or pending):
        return True
    if pending.get("kind_asked"):
        return False
    if pending and (_FOLLOW_UP.search(query) or _ANYWHERE.search(query)):
        return True
    if pending.get("answered"):
        return False
    reply = state.get("query", "")
    return (bool(pending) and 0 < len(query.split()) <= MAX_REPLY_WORDS and "?" not in reply
            and not _DECLINE.match(query) and not _OTHER_KIND.search(query))


def detected(state: dict) -> dict | None:
    """Update của `classify` khi câu hỏi giá vé (đi `explore`, nhánh giá vé); None thì đi luồng thường.

    Đã có lịch vẫn bắt câu **hỏi** giá vé: trả lời theo tuyến của chuyến, không lập lại lịch (chat thử 10/10: "giá máy
    bay đó rẻ nhất chưa" lập lại cả lịch 25 giây). Câu **đổi** vé đi `changes`, chạy trước luật này.
    """
    if not asked(state):
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
    folded = fold(place)
    if _TICKET.search(folded) or _FLIGHT.search(folded) or _FOLLOW_UP.search(folded) or _ASKING.search(folded):
        return None  # "vé máy bay", "rẻ nhất": không phải tên nơi
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
                kind: str = CHEAPEST) -> tuple[str, str]:
    """(tiêu đề, câu) cho vé một chiều `origin` → `destination`; `products` là chuyến của tuyến đó.

    Đã có ngày đi: nêu vé của đúng ngày đó, rồi so với cả đợt đang mở bán ("rẻ nhất chưa?" phải trả lời được là còn ngày
    rẻ hơn, chat thử 10/10). `kind = DEAREST`: vé đắt nhất thay cho rẻ nhất.
    """
    start = (state.get("intent") or {}).get("startDate")
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
    others = [message(state, f"fare_other_day_{kind}", day=other_day.strftime("%d/%m"),
                      money=money(product["unitPrice"], language))
              for other_day, product in ranked[1:1 + OTHER_DAYS] if other_day.isoformat() != start]
    if others:
        lines.append(message(state, "fare_other_days", days=", ".join(others)))
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


def _kind_question(state: dict, destination: str | None, intent: dict, supported: list[str]) -> dict:
    """Hỏi lại "vé" nào: vé máy bay, khách sạn hay vé tham quan, kèm ba nút tự đủ nghĩa."""
    place = destination or ""
    suffix = "_at" if destination else ""
    chips = [message(state, f"chip_kind_flight{suffix}", destination=place),
             message(state, f"chip_kind_hotel{suffix}", destination=place),
             message(state, f"chip_kind_sights{suffix}", destination=place)]
    body = message(state, f"fare_ask_kind{suffix}", destination=place)
    response = _response(state, None, body, chips, intent)
    return {"response": response, "pending_fare": {"destination": destination, "kind_asked": True},
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
    response = _response(state, title, body, chips, intent)
    return {"response": response, "pending_fare": {"origin": origin, "anywhere": True, "answered": True},
            "supported_destinations": supported, "final_answer": response["question"],
            "events": [event("explore", "fare answered anywhere", origin=origin, routes=len(by_destination))]}


async def answer(state: dict, *, tools: ToolExecutorPort | None, supported: list[str] | None,
                 timeout_seconds: float, today: date | None = None) -> dict:
    """Update của nhánh giá vé trong `explore`: hỏi lại chỗ thiếu, hoặc báo vé rẻ nhất (đắt nhất).

    Sau khi báo giá, `pending_fare` giữ tuyến vừa trả lời (`answered`) để câu hỏi tiếp ("đắt nhất thì sao", "ngày khác")
    vẫn đi nhánh này; `classify` bỏ nó khi người dùng chuyển sang chuyện khác.
    """
    today = today or datetime.now(flight_rules.VIETNAM).date()
    supported = supported or []
    query = state.get("query", "")
    intent = dict(state.get("intent") or {})
    pending = state.get("pending_fare") or {}
    kind = mode(query) if (_DEAR.search(fold(query)) or _CHEAP.search(fold(query))) else pending.get("kind", CHEAPEST)
    named = _cities(query, supported)
    if vague(state):
        destination = named[-1][1] if named else _known(state, "destination")
        return _kind_question(state, destination, intent, supported)
    if pending.get("kind_asked"):
        # Vừa chọn "vé máy bay": điểm đến của lần hỏi lại vẫn dùng được.
        pending = {"destination": pending.get("destination")}
        state = {**state, "pending_fare": pending}
    origin_named = _origin_named(query, named)
    if origin_named is None and len(named) == 1 and pending.get("destination") and not pending.get("origin") \
            and not _toward(query, named[0][0]):
        # Trả lời câu hỏi lại "Bạn bay từ đâu ra Nha Trang?" bằng một tên ("Hà Nội"): đó là nơi đi.
        origin_named = named[0][1]
    if origin_named is None and len(named) == 1 and pending.get("anywhere") and not pending.get("origin"):
        origin_named = named[0][1]
    if tools is not None and getattr(tools, "supports_catalog", False) and (
            anywhere(query) or (pending.get("anywhere") and not [name for _, name in named if name != origin_named])):
        origin = origin_named or _from_phrase(query) or _known(state, "origin")
        return await _anywhere(state, origin, tools, supported, intent, timeout_seconds, today, kind)
    destinations = [name for _, name in named if name != origin_named]
    destination = destinations[0] if destinations else _known(state, "destination")
    if destination is None:
        chips = [message(state, "chip_fare_to", destination=name) for name in supported[:ORIGIN_CHIPS]]
        update = {"pending_fare": {"origin": origin_named or _known(state, "origin"), **_kind_key(kind)}}
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
                "pending_fare": {"destination": destination, **_kind_key(kind)}, "supported_destinations": supported,
                "events": [event("explore", "fare question, origin missing", destination=destination)]}
    options = await flight_options(tools, {"origin": origin, "destination": destination, "days": 2},
                                   {}, timeout_seconds, state.get("request_id", "unknown"))
    if not state.get("previous_plan"):
        # Chưa có lịch: nơi đi vừa biết được ghi cho chuyến. Đã có lịch thì câu hỏi giá vé không đổi chuyến.
        intent = {**intent, "origin": origin if not intent.get("origin") else intent["origin"]}
    if options.get("status") == flight_rules.UNAVAILABLE:
        title, body = None, message(state, "fare_unavailable")
    elif options.get("status") or not options.get("outbound"):
        title, body = None, message(state, "fare_none", origin=origin, destination=destination)
    else:
        title, body = answer_text(state, options.get("origin") or origin, destination, options["outbound"], today,
                                  kind)
    other = DEAREST if kind == CHEAPEST else CHEAPEST
    extra = [message(state, f"chip_fare_{other}"), message(state, "chip_hotels", destination=destination)]
    response = _response(state, title, body, _chips(state, destination, extra), intent)
    return {"response": response, "pending_fare": {"origin": origin, "destination": destination, "answered": True},
            "intent": intent, "supported_destinations": supported, "final_answer": response["question"],
            "events": [event("explore", "fare answered", origin=origin, destination=destination, kind=kind,
                             status=options.get("status"))]}
