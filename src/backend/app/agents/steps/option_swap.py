"""Lượt chọn một phương án khác (AC-AGT-04, chốt 2026-10-08): lấy lịch `compose` đã dựng và kiểm ở lượt trước, không
tìm lại, không gọi LLM.

Lịch của từng phương án được lưu trong hội thoại (`previous_options[i].itinerary`), cùng lịch đang chọn
(`previous_plan`). Chọn phương án N thì lịch N thành lịch đang chọn, còn lịch đang chọn thành một phương án để quay
lại được. Chênh km tính lại từ km tuyệt đối của từng lịch, chênh tiền tính lại tuyến tính từ chênh tiền đã có (cùng
một mốc), nên không cộng dồn sai số làm tròn.
"""
from __future__ import annotations

from copy import deepcopy

from src.backend.app.domain.itinerary.routing import MAX_OPTIONS, OPTION_MIN_KM

from . import messages
from .classification import picked_option
from .composition import options_text, stay_options_payload, with_options_warning
from .messages import event
from .narration import product_link

#: Chênh km nhỏ hơn mức này coi như bằng 0 khi so (km đã làm tròn 0,1).
_EPS = 1e-6


def chosen_option(state: dict) -> dict | None:
    """Phương án được chọn ở lượt này (nút "Đổi sang khách sạn này" hoặc nhắn "lấy phương án N"), chỉ khi lượt trước có
    lưu lịch của phương án đó và lịch đang chọn; None thì lượt này đi luồng thường."""
    if not state.get("previous_plan"):
        return None
    pick = state.get("select_stay_option") or {}
    if pick.get("index") is not None:
        option = next((option for option in state.get("previous_options", [])
                       if option.get("index") == pick["index"]), None)
    else:
        option = picked_option(state)
    return option if option and option.get("itinerary") and option.get("distanceKm") is not None else None


def _over_budget(itinerary: dict, intent: dict) -> int | None:
    budget, total = intent.get("budget"), itinerary.get("estimatedTotal")
    return total - budget if budget is not None and total is not None and total > budget else None


def _order(entry: dict) -> tuple:
    return (0, entry["moneyDelta"]) if entry["kmDelta"] < 0 else (1, -entry["moneyDelta"])


def rebased(current: dict, chosen: dict, others: list[dict], intent: dict) -> list[dict]:
    """Phương án khác sau khi chọn `chosen`: lịch đang chọn (luôn giữ, để quay lại) và các phương án còn lại chênh từ
    `OPTION_MIN_KM`; thứ tự như `routing._options` (gần hơn theo tiền tăng dần, rồi xa hơn theo tiền giảm dần), tối đa
    `MAX_OPTIONS`, đánh số lại từ 1."""
    entries = []
    for entry, previous in [(current, True), *((other, False) for other in others)]:
        km_delta = round(entry["distanceKm"] - chosen["distanceKm"], 1)
        if not previous and abs(km_delta) < OPTION_MIN_KM - _EPS:
            continue
        money_delta = (0 if previous else entry["moneyDelta"]) - chosen["moneyDelta"]
        entries.append(({**entry, "kmDelta": km_delta, "moneyDelta": money_delta,
                         "overBudget": _over_budget(entry["itinerary"], intent)}, previous))
    rest = sorted((entry for entry, previous in entries if not previous), key=_order)[:MAX_OPTIONS - 1]
    kept = sorted([entry for entry, previous in entries if previous] + rest, key=_order)
    return [{**entry, "index": index} for index, entry in enumerate(kept, start=1)]


def stored_products(state: dict) -> dict:
    """Nguồn grounding của lượt chọn phương án: sản phẩm trong các lịch đã lưu phía server ở lượt trước (lịch đang chọn
    và lịch của từng phương án, đều đã được `validate_plan` kiểm với kết quả tool lúc `compose`), không lấy từ client.
    Trả `candidates`, `sources`, `flight_options` cho `finalize` kiểm lại lịch mới như mọi lượt khác."""
    candidates, sources, flights = {}, {}, {"outbound": [], "return": []}
    plans = [state["previous_plan"], *state.get("previous_options", [])]
    for plan in plans:
        itinerary = plan["itinerary"]
        for item in [*(itinerary.get("stays") or []),
                     *(slot for day in itinerary.get("days", []) for slot in day.get("slots", []))]:
            product = item.get("product")
            if product:
                candidates[product["productId"]] = product
                sources[product["productId"]] = "recommendation" if item.get("source") == "RECOMMENDATION" \
                    else "search"
        for leg in itinerary.get("flights") or []:
            key = "return" if leg.get("direction") == "RETURN" else "outbound"
            if all(known["productId"] != leg["product"]["productId"] for known in flights[key]):
                flights[key].append(leg["product"])
    for products in (state["previous_plan"].get("searchResults") or {}).values():
        candidates.update({product["productId"]: product for product in products})
    # `summary` không giữ `priceAdults`; lấy lại từ khách sạn lưu kèm lịch để `finalize` tính đúng số phòng.
    for plan in plans:
        for stay in plan.get("stays") or []:
            product = candidates.get(stay["productId"])
            if product is not None and "priceAdults" in stay:
                candidates[stay["productId"]] = {
                    **product, "attributes": {**(product.get("attributes") or {}), "priceAdults": stay["priceAdults"]}}
    return {"candidates": candidates, "sources": sources, "flight_options": flights}


def archived(working_state: dict, response: dict) -> dict:
    """Working state ghi vào archive cùng `response`: bỏ các lịch mà `response` đã có, để một dòng không lưu lặp lịch
    (`previous_plan.itinerary`/`searchResults` = `response.itinerary`/`searchResults` của lượt `COMPLETED`,
    `previous_options[i].itinerary` = `response.stayOptions.options[i].itinerary`). `restored` dựng lại."""
    archived_state = dict(working_state)
    plan = working_state.get("previous_plan")
    if plan and response.get("itinerary"):
        archived_state["previous_plan"] = {key: value for key, value in plan.items()
                                           if key not in ("itinerary", "searchResults")}
    if response.get("stayOptions"):
        archived_state["previous_options"] = [{key: value for key, value in option.items() if key != "itinerary"}
                                              for option in working_state.get("previous_options", [])]
    return archived_state


def restored(previous: dict) -> dict:
    """Ngược với `archived`: lấy lại lịch từ `lastResponse` (response của dòng archive đó). Thiếu lịch thì giữ nguyên;
    khi đó `chosen_option` trả None và lượt chọn đi luồng thường."""
    previous = dict(previous)
    response = previous.pop("lastResponse", None) or {}
    plan = previous.get("previous_plan")
    if plan and "itinerary" not in plan and response.get("itinerary"):
        previous["previous_plan"] = {**plan, "itinerary": response["itinerary"],
                                     **({"searchResults": response["searchResults"]} if response.get("searchResults") else {})}
    itineraries = {option.get("index"): option.get("itinerary")
                   for option in (response.get("stayOptions") or {}).get("options", [])}
    if any(itineraries.values()) and previous.get("previous_options"):
        previous["previous_options"] = [
            option if "itinerary" in option or not itineraries.get(option.get("index"))
            else {**option, "itinerary": itineraries[option["index"]]}
            for option in previous["previous_options"]]
    return previous


def silent(state: dict) -> bool:
    """Lượt bấm thẻ (`selectStayOption`) không thêm tin nhắn vào khung chat; lượt gõ "lấy phương án N" thì có câu trả lời."""
    return bool(state.get("select_stay_option"))


def _change_message(state: dict, chosen: dict, title: str) -> str:
    """Câu trả lời ngắn cho lượt gõ "lấy phương án N" (do code dựng, mọi số từ backend)."""
    language = state.get("language", "vi")
    hotels = ", ".join(product_link(stay["product"]) for stay in chosen["itinerary"].get("stays") or [])
    money_delta, km_delta = chosen["moneyDelta"], chosen["kmDelta"]
    money = messages.message(state, "swap_money_more" if money_delta > 0 else "swap_money_less",
                             money=messages.money(abs(money_delta), language)) if money_delta else \
        messages.message(state, "swap_money_same")
    km = messages.message(state, "swap_km_less" if km_delta < 0 else "swap_km_more",
                          km=messages.distance(abs(km_delta), language))
    return f"**{title}**\n" + messages.message(state, "swap_done", hotels=hotels, money=money, km=km,
                                                total_km=messages.distance(chosen["distanceKm"], language))


def swapped(state: dict, chosen: dict) -> dict:
    """Update của node `apply_option`: response `COMPLETED` với lịch của phương án đã chọn và hàng thẻ mới. Lượt bấm thẻ
    không có `message` (không thêm tin nhắn vào khung chat, chốt 2026-10-08; client giữ lời diễn giải cũ); lượt gõ
    "lấy phương án N" có câu ngắn do code dựng. Ghi
    `current_plan`/`stay_options` mới để lượt sau chọn tiếp hoặc quay lại."""
    current = state["previous_plan"]
    others = [option for option in state.get("previous_options", []) if option.get("index") != chosen["index"]]
    options = rebased(current, chosen, others, state["intent"])
    itinerary = deepcopy(chosen["itinerary"])
    itinerary["title"] = current["itinerary"].get("title") or messages.message(state, "options_swap_title")
    response = {"status": "COMPLETED", "conversationId": state["conversation_id"], "intent": state["intent"],
                "itinerary": itinerary,
                "warnings": with_options_warning(chosen["warnings"],
                                                 options_text(state, chosen["distanceKm"], options) if options
                                                 else None)}
    if not silent(state):
        response["message"] = _change_message(state, chosen, itinerary["title"])
    if current.get("searchResults"):
        response["searchResults"] = deepcopy(current["searchResults"])
    if options:
        response["stayOptions"] = stay_options_payload(chosen["distanceKm"], options)
    new_current = {"itinerary": itinerary, "warnings": chosen["warnings"], "distanceKm": chosen["distanceKm"],
                   "stays": chosen["stays"]}
    if current.get("searchResults"):
        new_current["searchResults"] = current["searchResults"]
    constraints = deepcopy(state.get("constraints", {}))
    # Khách sạn người dùng đã chọn được giữ cho các lượt sau (như "lấy phương án N" trước đây); tên lấy từ lịch đã hiện.
    constraints["specific_hotel"] = chosen["stays"][0]["name"]
    constraints["require_hotel"] = True
    return {"response": response, "stay_options": options, "current_plan": new_current, "constraints": constraints,
            **stored_products(state), "decision": "option", "interaction_type": "travel",
            "events": [event("apply_option", "stay option applied", index=chosen["index"])]}
