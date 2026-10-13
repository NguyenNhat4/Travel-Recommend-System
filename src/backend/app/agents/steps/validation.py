"""Chốt chặn cuối: kiểm response theo contract và grounding, rồi rút câu trả lời hiển thị."""
from __future__ import annotations

from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.domain.itinerary.flights import flight_candidates
from src.backend.app.domain.itinerary.planning import summary, validate_plan

from .messages import PRODUCT_LINK
from .narration import unknown_links


def response_issues(state: dict, response: dict, http_status: int) -> list:
    """Danh sách lỗi; rỗng nghĩa là response được phép trả cho client."""
    # Error envelopes and successful response unions both come from OpenAPI.
    if not valid("ItineraryResponse" if http_status == 200 else "ErrorResponse", response):
        return ["schema"]
    issues = []
    try:
        if response.get("status") == "COMPLETED":
            issues = validate_plan(response["itinerary"], state["candidates"], state["sources"],
                                   state["intent"], state.get("constraints", {}),
                                   flight_candidates(state.get("flight_options") or {}))
            if response.get("intent") != state["intent"] or response["conversationId"] != state["conversation_id"]:
                issues.append("intent")
            if unknown_links(response):
                issues.append("message_grounding")
            for option in (response.get("stayOptions") or {}).get("options", []):
                # Lịch của từng phương án (hàng thẻ, AC-AGT-04) cũng được client hiển thị: cùng chốt chặn grounding.
                if validate_plan(option["itinerary"], state["candidates"], state["sources"], state["intent"],
                                 state.get("constraints", {}),
                                 flight_candidates(state.get("flight_options") or {})):
                    issues.append("option_grounding")
        if response.get("status") in ("COMPLETED", "FALLBACK") and response.get("searchResults"):
            for products in response["searchResults"].values():
                if any(p != summary(state.get("candidates", {}).get(p["productId"], {})) for p in products):
                    issues.append("fallback_grounding")
        if response.get("status") == "NEEDS_CLARIFICATION":
            issues += _explore_issues(state, response)
    except (KeyError, TypeError, ValueError):
        issues.append("invalid_plan")
    return issues


def _explore_issues(state: dict, response: dict) -> list[str]:
    """Lượt khám phá (FR-AGT-06): mỗi thẻ là đúng sản phẩm Search trả về lượt này, và câu chỉ link tới các thẻ đó."""
    shown = {p["productId"] for products in (response.get("searchResults") or {}).values() for p in products}
    issues = []
    for products in (response.get("searchResults") or {}).values():
        if any(p != summary(state.get("candidates", {}).get(p["productId"], {})) for p in products):
            issues.append("explore_grounding")
            break
    allowed_links = shown | set(state.get("orchestrator_fare_ids") or [])
    if any(match.group(2) not in allowed_links for match in PRODUCT_LINK.finditer(response.get("question", ""))):
        issues.append("message_grounding")
    return issues


def answer_text(response: dict) -> str:
    """Câu hiển thị cho UI: câu hỏi, message (kể cả lời diễn giải của `COMPLETED`), lỗi, hoặc tên các sản phẩm đã xếp."""
    if response.get("status") == "COMPLETED" and response.get("message"):
        return response["message"]
    if response.get("status") == "COMPLETED":
        names = [slot["product"]["name"] for day in response["itinerary"]["days"]
                 for slot in day["slots"] if slot["product"]]
        itinerary = response["itinerary"]
        for stay in reversed(itinerary.get("stays") or ([itinerary["stay"]] if itinerary.get("stay") else [])):
            names.insert(0, stay["product"]["name"])
        return "Lịch trình tham khảo: " + "; ".join(names)
    return response.get("question", response.get("message", response.get("error", {}).get("message", "")))


def selection_snapshot(response: dict) -> list[dict]:
    """Compact productId/name/taxonomy of what was actually shown, to exclude on a later swap request."""
    if response.get("status") != "COMPLETED":
        return []
    items = []
    itinerary = response["itinerary"]
    for stay in itinerary.get("stays") or ([itinerary["stay"]] if itinerary.get("stay") else []):
        if stay.get("product"):
            items.append({key: stay["product"][key] for key in ("productId", "name", "taxonomy")})
    for day in response["itinerary"]["days"]:
        for slot in day["slots"]:
            if slot["product"]:
                items.append({key: slot["product"][key] for key in ("productId", "name", "taxonomy")})
    return items
