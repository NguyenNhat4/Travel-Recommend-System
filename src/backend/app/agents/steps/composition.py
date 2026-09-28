"""Dựng lịch trình từ candidate bằng luật tất định; không có lượt gọi LLM nào ở đây."""
from __future__ import annotations

from copy import deepcopy
import logging

from src.backend.app.domain.itinerary.planning import compose_plan, render_proposal, summary, validate_plan

from . import messages
from .messages import failure

logger = logging.getLogger("uvicorn.error")

MAX_PER_GROUP = 6
WARNINGS = {
    "SNAPSHOT_ONLY": "Giá và trạng thái là snapshot tham khảo; chưa xác nhận tồn kho theo ngày hoặc số khách.",
    "SCHEDULE_ESTIMATE": "Khung buổi là dự kiến; cần kiểm tra giờ mở cửa, thời gian di chuyển và điều kiện "
                         "trẻ em trước khi đặt.",
    "UNKNOWN_TOTAL": "Chưa đủ đơn vị giá, số lượng hoặc điều kiện để tính tổng chi phí; không coi giá thiếu là 0.",
    "PRODUCT_COST_ONLY": "Tổng chỉ gồm các sản phẩm được chọn; chưa bao gồm chi phí phát sinh ngoài lịch trình.",
    "UNKNOWN_BUDGET": "Chưa đủ dữ liệu toàn chuyến để xác nhận ngân sách.",
}


def grouped(state: dict) -> dict:
    """Candidate gom theo taxonomy cho response FALLBACK, tối đa sáu sản phẩm mỗi nhóm."""
    groups = {}
    for product in state.get("candidates", {}).values():
        groups.setdefault(product["taxonomy"], [])
        if len(groups[product["taxonomy"]]) < MAX_PER_GROUP:
            groups[product["taxonomy"]].append(summary(product))
    return groups


def fallback(state: dict) -> dict:
    """Không dựng được lịch trình: trả danh sách ứng viên, hoặc lỗi khi không còn gì để trả."""
    if not state.get("candidates"):
        return failure(state, "LLM_UNAVAILABLE", messages.COMPOSE_UNAVAILABLE, retryable=True)
    return {"decision": "fallback",
            "response": {"status": "FALLBACK", "conversationId": state["conversation_id"],
                         "intent": state["intent"], "message": messages.FALLBACK,
                         "searchResults": grouped(state)}}


def _no_results_suggestions(state: dict) -> list[str]:
    """Gợi ý điều chỉnh dựa trên ràng buộc đang bật (docs/spec/agent/field-review.md §2.2); tối đa ba mục."""
    constraints = state.get("constraints", {})
    suggestions = []
    if constraints.get("require_hotel") or constraints.get("specific_hotel"):
        suggestions.append(messages.message(state, "suggestion_hotel"))
    if constraints.get("hotel_price_max") is not None:
        suggestions.append(messages.message(state, "suggestion_price"))
    if constraints.get("star_rating_min") is not None:
        suggestions.append(messages.message(state, "suggestion_star_rating"))
    if constraints.get("specific_activity"):
        suggestions.append(messages.message(state, "suggestion_activity"))
    if constraints.get("exclude_taxonomies"):
        suggestions.append(messages.message(state, "suggestion_taxonomy"))
    if not suggestions:
        suggestions.append(messages.message(state, "suggestion_generic"))
    return suggestions[:3]


def retrieval_outcome(state: dict) -> dict | None:
    """The replies that retrieval itself settles; None means there is an itinerary to build."""
    decision = state.get("decision")
    if decision == "no_results":
        return {"response": {"status": "NO_RESULTS", "conversationId": state["conversation_id"],
                             "intent": state["intent"], "message": messages.NO_RESULTS,
                             "suggestions": _no_results_suggestions(state)}}
    if decision == "fallback":
        return fallback(state)
    return None


def _budget_warnings(plan: dict, intent: dict, warnings: list) -> None:
    """Cảnh báo về tổng tiền; tổng của phần sản phẩm không được dùng để xác nhận ngân sách cả chuyến."""
    if plan["estimatedTotal"] is None:
        warnings.append({"code": "UNKNOWN_TOTAL", "message": WARNINGS["UNKNOWN_TOTAL"]})
        return
    warnings.append({"code": "PRODUCT_COST_ONLY", "message": WARNINGS["PRODUCT_COST_ONLY"]})
    # A known subtotal cannot certify a whole-trip budget.
    if intent.get("budget") is not None:
        plan.update(estimatedTotal=None, budgetStatus="UNKNOWN")
        warnings.append({"code": "UNKNOWN_TOTAL", "message": WARNINGS["UNKNOWN_BUDGET"]})


def composed(state: dict) -> dict:
    """Build the itinerary from the retrieved candidates with fixed rules; no model is consulted."""
    proposal = compose_plan(state["candidates"], state["intent"])
    plan = render_proposal(proposal, state["candidates"], state["sources"], state["intent"])
    if validate_plan(plan, state["candidates"], state["sources"], state["intent"], state.get("constraints", {})):
        raise ValueError("invalid composition")
    warnings = deepcopy(state.get("warnings", []))
    warnings.append({"code": "SNAPSHOT_ONLY", "message": WARNINGS["SNAPSHOT_ONLY"]})
    warnings.append({"code": "SCHEDULE_ESTIMATE", "message": WARNINGS["SCHEDULE_ESTIMATE"]})
    _budget_warnings(plan, state["intent"], warnings)
    for day in plan["days"]:
        if not any(slot["product"] for slot in day["slots"]):
            warnings.append({"code": "DAY_WITHOUT_PRODUCTS",
                             "message": f"Ngày {day['day']} dành cho nghỉ ngơi hoặc hoạt động chung, "
                                        "chưa có sản phẩm được chọn."})
    return {"response": {"status": "COMPLETED", "conversationId": state["conversation_id"],
                         "intent": state["intent"], "itinerary": plan, "warnings": warnings}}


def compose_or_fallback(state: dict) -> dict:
    """Luật tự bác đề xuất của chính nó là bug backend, không phải lỗi model — log rồi mới fallback."""
    try:
        return composed(state)
    except Exception:
        # Rules rejecting their own proposal is a backend defect, not a model failure; never hide it.
        logger.exception("itinerary.composition_failed requestId=%s", state.get("request_id", "unknown"))
        return fallback(state)
