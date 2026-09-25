"""Chốt chặn cuối: kiểm response theo contract và grounding, rồi rút câu trả lời hiển thị."""
from __future__ import annotations

from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.domain.itinerary.planning import summary, validate_plan


def response_issues(state: dict, response: dict, http_status: int) -> list:
    """Danh sách lỗi; rỗng nghĩa là response được phép trả cho client."""
    # Error envelopes and successful response unions both come from OpenAPI.
    if not valid("ItineraryResponse" if http_status == 200 else "ErrorResponse", response):
        return ["schema"]
    issues = []
    try:
        if response.get("status") == "COMPLETED":
            issues = validate_plan(response["itinerary"], state["candidates"], state["sources"],
                                   state["intent"], state.get("constraints", {}))
            if response.get("intent") != state["intent"] or response["conversationId"] != state["conversation_id"]:
                issues.append("intent")
        if response.get("status") == "FALLBACK":
            for products in response["searchResults"].values():
                if any(p != summary(state.get("candidates", {}).get(p["productId"], {})) for p in products):
                    issues.append("fallback_grounding")
    except (KeyError, TypeError, ValueError):
        issues.append("invalid_plan")
    return issues


def answer_text(response: dict) -> str:
    """Một dòng tóm tắt cho UI: câu hỏi, message, lỗi, hoặc tên các sản phẩm đã xếp lịch."""
    if response.get("status") == "COMPLETED":
        names = [slot["product"]["name"] for day in response["itinerary"]["days"]
                 for slot in day["slots"] if slot["product"]]
        if response["itinerary"].get("stay"):
            names.insert(0, response["itinerary"]["stay"]["product"]["name"])
        return "Lịch trình tham khảo: " + "; ".join(names)
    return response.get("question", response.get("message", response.get("error", {}).get("message", "")))


def selection_snapshot(response: dict) -> list[dict]:
    """Compact productId/name/taxonomy of what was actually shown, to exclude on a later swap request."""
    if response.get("status") != "COMPLETED":
        return []
    items = []
    stay = response["itinerary"].get("stay")
    if stay and stay.get("product"):
        items.append({key: stay["product"][key] for key in ("productId", "name", "taxonomy")})
    for day in response["itinerary"]["days"]:
        for slot in day["slots"]:
            if slot["product"]:
                items.append({key: slot["product"][key] for key in ("productId", "name", "taxonomy")})
    return items
