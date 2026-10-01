"""Dựng lịch trình từ candidate bằng luật tất định; không có lượt gọi LLM nào ở đây."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import logging

from src.backend.app.domain.itinerary.planning import (compose_plan, free_to_visit, multi_day_offers, render_proposal,
                                                        summary, validate_plan)

from . import messages
from .explanations import missing_stay_note
from .messages import display_date, failure

logger = logging.getLogger("uvicorn.error")

MAX_PER_GROUP = 6
WARNINGS = {
    "SNAPSHOT_ONLY": "Giá và trạng thái là snapshot tham khảo; chưa xác nhận tồn kho theo ngày hoặc số khách.",
    "SCHEDULE_ESTIMATE": "Khung buổi là dự kiến; cần kiểm tra giờ mở cửa, thời gian di chuyển và điều kiện "
                         "trẻ em trước khi đặt.",
    "UNKNOWN_TOTAL": "Chưa đủ đơn vị giá, số lượng hoặc điều kiện để tính tổng chi phí; không coi giá thiếu là 0.",
    "FREE_ENTRY_ASSUMED": "Tổng coi các điểm tham quan tự do là không mất vé; một số nơi có thể thu phí tại chỗ.",
    "PRODUCT_COST_ONLY": "Tổng chỉ gồm các sản phẩm được chọn; chưa bao gồm chi phí phát sinh ngoài lịch trình.",
    "BUDGET_ON_PRODUCT_COST": "Đối chiếu ngân sách chỉ dựa trên chi phí các sản phẩm trong lịch trình; "
                              "chưa gồm ăn uống, đi lại và phát sinh ngoài lịch trình.",
    "RECOMMENDATION_FALLBACK": "Một số mục trong lịch trình là gợi ý (Recommendation), không phải kết quả "
                               "tìm kiếm, vì không có sản phẩm tìm kiếm phù hợp cho mục đó; xem `because` ở "
                               "từng mục để biết lý do gợi ý.",
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


MAX_SUGGESTIONS = 3
#: Số gói nhiều ngày tối đa đưa kèm lịch trình mỗi loại; đủ để chọn mà không làm dài lời diễn giải.
MAX_MULTI_DAY_OFFERS = 2
MAX_ALTERNATIVE_DESTINATIONS = 2


def _date_is_the_reason(state: dict) -> bool:
    """Lý do phổ biến nhất khiến sản phẩm bị loại là ngày đi nằm ngoài cửa sổ mở bán."""
    reasons = Counter(warning["code"] for warning in state.get("warnings", []))
    return bool(reasons) and reasons.most_common(1)[0][0] == "PRODUCT_DROPPED_DATE"


def _no_results_message(state: dict) -> str:
    intent = state.get("intent", {})
    if intent.get("startDate") and intent.get("destination") and _date_is_the_reason(state):
        return messages.message(state, "no_results_date", destination=intent["destination"],
                                date=display_date(intent["startDate"]))
    return messages.message(state, "no_results")


def _no_results_suggestions(state: dict) -> list[str]:
    """Gợi ý bấm được cho NO_RESULTS, tối đa ba mục, mọi giá trị lấy từ dữ liệu thật của lượt này.

    Thứ tự: ngày gần nhất còn bán (docs/spec/hop-dong-tich-hop-itinerary-assistant.md §4.4), rồi gợi ý
    bỏ ràng buộc đang bật (field-review.md §2.2), rồi điểm đến khác trong catalog. Không tự đổi điểm đến
    thay người dùng: chỉ đưa ra để họ chọn.
    """
    constraints = state.get("constraints", {})
    intent = state.get("intent", {})
    suggestions = []
    if state.get("nearest_open_date") and intent.get("destination"):
        suggestions.append(messages.message(state, "suggestion_trip_date", destination=intent["destination"],
                                            days=intent.get("days") or 1, date=display_date(state["nearest_open_date"])))
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
    if intent.get("destination"):
        current = intent["destination"].casefold()
        alternatives = [name for name in state.get("supported_destinations") or [] if name.casefold() != current]
        suggestions.extend(
            messages.message(state, "suggestion_trip", destination=name, days=intent.get("days") or 1)
            for name in alternatives[:MAX_ALTERNATIVE_DESTINATIONS])
    if not suggestions:
        suggestions.append(messages.message(state, "suggestion_generic"))
    return suggestions[:MAX_SUGGESTIONS]


def retrieval_outcome(state: dict) -> dict | None:
    """The replies that retrieval itself settles; None means there is an itinerary to build."""
    decision = state.get("decision")
    if decision == "no_results":
        return {"response": {"status": "NO_RESULTS", "conversationId": state["conversation_id"],
                             "intent": state["intent"], "message": _no_results_message(state),
                             "suggestions": _no_results_suggestions(state)}}
    if decision == "fallback":
        return fallback(state)
    return None


def _budget_warnings(plan: dict, intent: dict, warnings: list) -> None:
    """Cảnh báo kèm tổng tiền. Tổng là dữ kiện và luôn được giữ; cảnh báo nói rõ nó chỉ gồm sản phẩm.

    Tổng của phần sản phẩm không phải chi phí cả chuyến, nên nó đi kèm `PRODUCT_COST_ONLY`. Trước đây chỗ
    này xoá luôn `estimatedTotal` khi người dùng có nêu ngân sách — huỷ dữ kiện để khỏi phải kết luận. Điều
    đó trái `architecture.md` §3 ("giá thiếu thì tổng là null" — chỉ khi thiếu giá) và FR-AGT-02, đồng thời
    làm thanh ngân sách ở frontend không bao giờ hiện được vì nó cần cả `budget` lẫn `estimatedTotal`.
    """
    if plan["estimatedTotal"] is None:
        warnings.append({"code": "UNKNOWN_TOTAL", "message": WARNINGS["UNKNOWN_TOTAL"]})
        return
    warnings.append({"code": "PRODUCT_COST_ONLY", "message": WARNINGS["PRODUCT_COST_ONLY"]})
    if any(free_to_visit(slot["product"]) for day in plan.get("days", []) for slot in day.get("slots", [])
           if slot.get("product") is not None):
        warnings.append({"code": "FREE_ENTRY_ASSUMED", "message": WARNINGS["FREE_ENTRY_ASSUMED"]})
    if intent.get("budget") is not None:
        warnings.append({"code": "BUDGET_ON_PRODUCT_COST", "message": WARNINGS["BUDGET_ON_PRODUCT_COST"]})


def _uses_recommendation(plan: dict) -> bool:
    if plan.get("stay", {}).get("source") == "RECOMMENDATION":
        return True
    return any(slot.get("source") == "RECOMMENDATION" for day in plan.get("days", []) for slot in day.get("slots", []))


def composed(state: dict) -> dict:
    """Build the itinerary from the retrieved candidates with fixed rules; no model is consulted."""
    proposal = compose_plan(state["candidates"], state["sources"], state["intent"])
    plan = render_proposal(proposal, state["candidates"], state["sources"], state["intent"])
    if validate_plan(plan, state["candidates"], state["sources"], state["intent"], state.get("constraints", {})):
        raise ValueError("invalid composition")
    warnings = deepcopy(state.get("warnings", []))
    warnings.append({"code": "SNAPSHOT_ONLY", "message": WARNINGS["SNAPSHOT_ONLY"]})
    warnings.append({"code": "SCHEDULE_ESTIMATE", "message": WARNINGS["SCHEDULE_ESTIMATE"]})
    if _uses_recommendation(plan):
        warnings.append({"code": "RECOMMENDATION_FALLBACK", "message": WARNINGS["RECOMMENDATION_FALLBACK"]})
    _budget_warnings(plan, state["intent"], warnings)
    no_stay = missing_stay_note(state, plan)
    if no_stay:
        warnings.append({"code": "NO_STAY_AVAILABLE", "message": no_stay})
    for day in plan["days"]:
        if not any(slot["product"] for slot in day["slots"]):
            warnings.append({"code": "DAY_WITHOUT_PRODUCTS",
                             "message": f"Ngày {day['day']} dành cho nghỉ ngơi hoặc hoạt động chung, "
                                        "chưa có sản phẩm được chọn."})
    response = {"status": "COMPLETED", "conversationId": state["conversation_id"],
                "intent": state["intent"], "itinerary": plan, "warnings": warnings}
    offers = _multi_day_offers(state)
    if offers:
        response["searchResults"] = offers
    return {"response": response}


def _multi_day_offers(state: dict) -> dict:
    """Gói/tour nhiều ngày không xếp vào một buổi: trả kèm trong `searchResults` để người dùng cân nhắc riêng."""
    groups: dict = {}
    for product in multi_day_offers(state["candidates"], state["sources"]):
        items = groups.setdefault(product["taxonomy"], [])
        if len(items) < MAX_MULTI_DAY_OFFERS:
            items.append(summary(product))
    return groups


def compose_or_fallback(state: dict) -> dict:
    """Luật tự bác đề xuất của chính nó là bug backend, không phải lỗi model — log rồi mới fallback."""
    try:
        return composed(state)
    except Exception:
        # Rules rejecting their own proposal is a backend defect, not a model failure; never hide it.
        logger.exception("itinerary.composition_failed requestId=%s", state.get("request_id", "unknown"))
        return fallback(state)
