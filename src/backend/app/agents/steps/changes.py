"""Đổi khách sạn, chuyến bay khi người dùng chưa nói đổi thế nào (kịch bản bản 5; góp ý của người dùng 09/10/2026).

Luật tất định, không gọi LLM:

- "Đổi khách sạn" trơn, lịch đang hiện có phương án khác: hỏi một câu, liệt kê các phương án đã tính sẵn cho lịch đó; nút
  "Lấy phương án N" đi vào luồng đổi tức thì đã có (`option_swap`, AC-AGT-04). Câu có hướng ("rẻ hơn", "gần biển") hoặc giao
  cho trợ lý chọn thì không hỏi, `extract` hiểu như trước.
- "Đổi chuyến bay": liệt kê chuyến khác cùng ngày của từng chặng (`previous_flights`, dựng ở `compose`), mỗi chuyến một nút.
  Câu đã nói rõ ("chuyến về muộn hơn", "rẻ hơn", "sớm hơn", bấm nút có số hiệu, "bạn chọn giúp") thì chọn luôn chuyến đó
  (`constraints.chosen_flights`) và lập lại lịch, vì giờ bay đổi thì cửa sổ ngày đến, ngày về cũng đổi (AC-AGT-02).
"""
from __future__ import annotations

from copy import deepcopy
import re

from src.backend.app.domain.itinerary.normalization import fold

from .messages import display_date, distance, event, message, money, titled

CHOOSE_STAY, CHOOSE_FLIGHT = "choose_stay", "choose_flight"
REASONS = frozenset({CHOOSE_STAY, CHOOSE_FLIGHT})
MAX_CHIPS = 3
MAX_CHIP_CHARS = 60

_CHANGE = re.compile(r"\b(?:doi|thay|chon lai|chuyen sang|lay)\b")
_HOTEL = re.compile(r"\b(?:khach san|ks|cho o|noi o|cho nghi|resort|homestay|hostel|hotel)\b")
_FLIGHT = re.compile(r"\b(?:chuyen bay|ve may bay|ve bay|chang bay|may bay|gio bay|chuyen di|chuyen ve|chieu di|"
                     r"chieu ve|chang di|chang ve|flight)\b")
#: "Đổi vé" đứng một mình (đã có lịch có vé máy bay) cũng là đổi chuyến bay; "đổi vé VinWonders" thì không, nên chỉ nhận
#: câu ngắn đúng dạng này ("vé" và "về" cùng thành "ve" sau `fold`).
_BARE_TICKET = re.compile(r"^(?:doi|thay) ve(?: (?:di|nhe|nha|giup minh|khac))*$")
_RETURN = re.compile(r"\b(?:chuyen ve|chieu ve|chang ve|luot ve|bay ve)\b")
_OUTBOUND = re.compile(r"\b(?:chuyen di|chieu di|chang di|luot di)\b")
_WANTS = (("cheaper", re.compile(r"\b(?:re hon|re nhat|gia thap hon|tiet kiem hon)\b")),
          ("earlier", re.compile(r"\b(?:som hon|som nhat)\b")),
          ("later", re.compile(r"\b(?:muon hon|tre hon|khuya hon|muon nhat)\b")),
          ("any", re.compile(r"\b(?:chon giup|tuy ban|nao cung duoc|bat ky|ban chon)\b")))
_DELEGATE = _WANTS[-1][1]
#: Từ đệm của câu đổi khách sạn trơn ("đổi khách sạn khác đi nhé"); còn chữ khác (rẻ hơn, gần biển…) thì để `extract` hiểu.
_STAY_FILLER = frozenset({"doi", "thay", "khach", "san", "ks", "cho", "o", "noi", "nghi", "khac", "di", "nhe", "nha", "giup",
                          "minh", "cai", "nay", "sang", "mot", "lai", "a", "ban", "voi", "duoc", "khong", "nhi", "thu",
                          "hotel", "resort", "homestay", "hostel", "lay", "chon", "muon", "can"})
#: Số hiệu chuyến bay viết tách ("vj 167") → liền ("vj167"), so trên chuỗi đã `fold`.
_SPLIT_NUMBER = re.compile(r"\b([a-z]{1,2}|[a-z]\d)\s+(\d{2,4})\b")


def _text(state: dict) -> str:
    return _SPLIT_NUMBER.sub(r"\1\2", fold(state.get("query", "")))


def _stay_options(state: dict) -> list[dict]:
    """Phương án khác của lịch đang hiện mà lượt chọn đổi được ngay (có lịch đã dựng)."""
    if not state.get("previous_plan"):
        return []
    return [option for option in state.get("previous_options") or []
            if option.get("itinerary") and option.get("distanceKm") is not None and option.get("stays")][:MAX_CHIPS]


def _stay_change(state: dict) -> dict | None:
    text = _text(state)
    if not (_CHANGE.search(text) and _HOTEL.search(text)) or _DELEGATE.search(text) or not _stay_options(state):
        return None
    if set(text.split()) - _STAY_FILLER:
        return None
    return {"decision": "missing_info", "clarification_reason": CHOOSE_STAY, "interaction_type": "travel",
            "refusal": False, "missing_fields": [], "change_request": {"kind": "stay"},
            "events": [event("classify", "route clarify (change hotel without direction)")]}


def _names(text: str, number: str | None) -> bool:
    number = fold(number).replace(" ", "")
    return bool(number) and re.search(rf"\b{re.escape(number)}\b", text) is not None


def _picked_by_number(text: str, choices: list[dict]) -> tuple[str, dict] | None:
    """Chuyến khác (cùng ngày) người dùng nêu số hiệu, ví dụ bấm nút "Về chuyến VJ167 lúc 21:45". Vé khứ hồi phải khớp cả số
    hiệu chuyến về, vì hai vé khứ hồi có thể chung chuyến đi."""
    for choice in choices:
        for alternative in choice.get("alternatives") or []:
            if _names(text, alternative.get("flightNumber")) and (
                    not alternative.get("returnFlightNumber") or _names(text, alternative["returnFlightNumber"])):
                return choice["direction"], alternative
    return None


def _best(want: str, chosen: dict, alternatives: list[dict]) -> dict | None:
    """Chuyến hợp ý nhất: rẻ hơn thì rẻ nhất; sớm hơn thì gần giờ cũ nhất trong các chuyến sớm hơn; muộn hơn tương tự."""
    price, clock = chosen.get("unitPrice"), chosen.get("departure") or ""
    if want == "any":
        return alternatives[0] if alternatives else None
    if want == "cheaper":
        pool = [item for item in alternatives if price is not None and (item.get("unitPrice") or price) < price]
        return min(pool, key=lambda item: item["unitPrice"]) if pool else None
    if want == "earlier":
        pool = [item for item in alternatives if item.get("departure") and clock and item["departure"] < clock]
        return max(pool, key=lambda item: item["departure"]) if pool else None
    pool = [item for item in alternatives if item.get("departure") and clock and item["departure"] > clock]
    return min(pool, key=lambda item: item["departure"]) if pool else None


def _pick(state: dict, direction: str, alternative: dict) -> dict:
    constraints = deepcopy(state.get("constraints") or {})
    constraints["chosen_flights"] = {**(constraints.get("chosen_flights") or {}), direction: alternative["productId"]}
    return {"decision": "tool", "interaction_type": "travel", "refusal": False, "plan_consent": True,
            "constraints": constraints,
            "events": [event("classify", "route tool (flight picked)", direction=direction)]}


def _flight_change(state: dict) -> dict | None:
    choices = state.get("previous_flights") or []
    if not choices:
        return None
    text = _text(state)
    picked = _picked_by_number(text, choices)
    if picked is not None:
        return _pick(state, *picked)
    if not ((_CHANGE.search(text) and _FLIGHT.search(text)) or _BARE_TICKET.match(text)):
        return None
    directions = [choice for choice in choices
                  if (not _RETURN.search(text) or choice["direction"] == "RETURN")
                  and (not _OUTBOUND.search(text) or choice["direction"] == "OUTBOUND")] or choices
    want = next((name for name, pattern in _WANTS if pattern.search(text)), None)
    request = {"kind": "flight", "directions": [choice["direction"] for choice in directions]}
    if want is not None:
        found = [(choice["direction"], best) for choice in directions
                 for best in [_best(want, choice["chosen"], choice.get("alternatives") or [])] if best is not None]
        if len(found) == 1:
            return _pick(state, *found[0])
        if not found:
            request["unmatched"] = want
    return {"decision": "missing_info", "clarification_reason": CHOOSE_FLIGHT, "interaction_type": "travel",
            "refusal": False, "missing_fields": [], "change_request": request,
            "events": [event("classify", "route clarify (change flight)", want=want)]}


def detected(state: dict) -> dict | None:
    """Update của `classify` khi câu là đổi khách sạn hoặc chuyến bay xử lý được bằng luật; None thì đi luồng thường."""
    return _flight_change(state) or _stay_change(state)


def _short(text: str, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _money_delta(state: dict, value: int | float) -> str:
    language = state.get("language", "vi")
    if not value:
        return message(state, "swap_money_same")
    return message(state, "swap_money_more" if value > 0 else "swap_money_less", money=money(abs(value), language))


def _km_delta(state: dict, value: float) -> str:
    language = state.get("language", "vi")
    return message(state, "swap_km_less" if value < 0 else "swap_km_more", km=distance(abs(value), language))


def _stay_question(state: dict) -> dict:
    options = _stay_options(state)
    lines = [message(state, "change_stay_intro")]
    for option in options:
        hotels = " → ".join(stay["name"] for stay in option["stays"])
        lines.append(message(state, "change_stay_line", index=option["index"], hotels=hotels,
                             money=_money_delta(state, option.get("moneyDelta") or 0),
                             km=_km_delta(state, option.get("kmDelta") or 0)))
    chips = []
    for option in options[:MAX_CHIPS - 1]:
        prefix = message(state, "chip_stay_option", index=option["index"], hotel="")
        chips.append(prefix + _short(option["stays"][0]["name"], MAX_CHIP_CHARS - len(prefix)))
    chips.append(message(state, "chip_stay_any"))
    return {"title": message(state, "change_stay_title"), "body": "\n".join(lines), "suggestions": chips}


def _price_delta(state: dict, chosen: dict, alternative: dict) -> str:
    before, after = chosen.get("unitPrice"), alternative.get("unitPrice")
    if before is None or after is None or after == before:
        return message(state, "flight_price_same")
    key = "flight_price_more" if after > before else "flight_price_less"
    return message(state, key, money=money(abs(after - before), state.get("language", "vi")))


def _flight_question(state: dict) -> dict:
    request = state.get("change_request") or {}
    wanted = set(request.get("directions") or ())
    choices = [choice for choice in state.get("previous_flights") or [] if not wanted or choice["direction"] in wanted]
    language = state.get("language", "vi")
    lines, chips = [], []
    if request.get("unmatched"):
        lines.append(message(state, f"change_flight_no_{request['unmatched']}"))
    if not any(choice.get("alternatives") for choice in choices):
        lines.append(message(state, "change_flight_none"))
    else:
        lines.append(message(state, "change_flight_intro"))
        for choice in choices:
            leg = message(state, f"change_flight_leg_{choice['direction']}", date=display_date(choice["date"]))
            if not choice.get("alternatives"):
                lines.append(message(state, "change_flight_leg_none", leg=leg))
                continue
            lines.append(f"{leg}:")
            for alternative in choice["alternatives"]:
                price = money(alternative["unitPrice"], language) if alternative.get("unitPrice") is not None else "—"
                values = {"flight": alternative.get("flightNumber") or "", "airline": alternative.get("airline") or "",
                          "time": alternative.get("departure") or "", "price": price,
                          "delta": _price_delta(state, choice["chosen"], alternative),
                          "back_flight": alternative.get("returnFlightNumber") or "",
                          "back_time": alternative.get("returnDeparture") or ""}
                round_trip = bool(alternative.get("returnFlightNumber"))
                lines.append(message(state, "change_flight_line_round" if round_trip else "change_flight_line", **values))
                if len(chips) < MAX_CHIPS - 1:
                    chips.append(message(state, "chip_flight_round", **values) if round_trip else
                                 message(state, "chip_flight", way=message(state, f"chip_way_{choice['direction']}"),
                                         **values))
    chips.append(message(state, "chip_change_date"))
    return {"title": message(state, "change_flight_title"), "body": "\n".join(lines), "suggestions": chips}


def question(state: dict) -> dict:
    """Câu hỏi của `clarify` cho lượt đổi (câu cố định, không gọi LLM), kèm nút là các lựa chọn cụ thể."""
    built = _flight_question(state) if state.get("clarification_reason") == CHOOSE_FLIGHT else _stay_question(state)
    response = {"status": "NEEDS_CLARIFICATION", "conversationId": state["conversation_id"],
                "question": titled(built["title"], built["body"]), "knownIntent": state["intent"]}
    if built["suggestions"]:
        response["suggestions"] = built["suggestions"][:MAX_CHIPS]
    return {"response": response}
