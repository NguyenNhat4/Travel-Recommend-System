"""Luật chấm kết quả truy xuất: lọc candidate có grounding rồi chọn `decision` cho node sau."""
from __future__ import annotations

from copy import deepcopy

from src.backend.app.application.itinerary.retrieval import collect
from src.backend.app.domain.itinerary.planning import SCHEDULABLE_TAXONOMIES, SLOT_TAXONOMIES, STAY_TAXONOMY

DROPPED_MESSAGE = "Một sản phẩm chưa đủ căn cứ hoặc không đáp ứng yêu cầu đã được loại."


def tool_errors(state: dict) -> list[dict]:
    """Mọi lỗi của lượt truy xuất: lỗi từng tool call cộng lỗi lấy chi tiết sản phẩm."""
    errors = [item["error"] for item in state.get("tool_results", []) if "error" in item]
    errors.extend(state.get("detail_errors", {}).values())
    return errors


def _relaxed_constraints(state: dict) -> dict:
    """Ràng buộc chỉ dùng để chấm lượt này: thêm vertical Recommendation đã bỏ, trừ khi bắt buộc có khách sạn.

    `excludedVerticals` là thứ user đã mua trong chuyến thật trên CDP, không phải điều user yêu cầu.
    Không được ghi vào `constraints` của state: `finalize` sẽ lưu nó sang lượt sau, và `tool` sẽ cấm
    tìm hẳn vertical đó ở mọi lượt tiếp theo.
    """
    constraints = deepcopy(state.get("constraints", {}))
    for item in state.get("tool_results", []):
        data = item.get("data", {})
        if (item.get("name") == "get_recommendations" and data.get("strategy") == "cross_vertical"
                and not constraints.get("require_hotel")):
            excluded = data.get("diagnostics", {}).get("excludedVerticals", [])
            constraints["exclude_taxonomies"] = sorted(set(constraints.get("exclude_taxonomies", []) + excluded))
    return constraints


def _decision(errors: list[dict], candidates: dict, constraints: dict) -> tuple[str, str]:
    """(`evaluation_result`, `decision`) — xem `routing.route_after_evaluate` để biết nhánh tương ứng."""
    # Authentication failures must never be hidden by a successful Search call.
    permanent = any(not e["retryable"] for e in errors)
    auth_error = any(e.get("httpStatus") == 401 or e.get("code") in {"INVALID_TOKEN", "TOKEN_EXPIRED"} for e in errors)
    if auth_error:
        return "failed", "error"
    if errors and not permanent:
        return "needs_retry", ""
    if errors:
        return ("success", "fallback") if candidates else ("failed", "error")
    if not candidates:
        decision = "no_results"
        if any(constraints.get(key) for key in ("require_hotel", "specific_hotel", "specific_activity")):
            decision = "constraint_clarification"
        return "success", decision
    decision = "compose"
    # Ba kiểm tra dưới đây chạy tuần tự: không còn sản phẩm xếp được lịch thì `fallback` thắng, vì
    # hỏi lại người dùng về một điều kiện cũng không dựng nổi lịch trình.
    if constraints.get("require_hotel") and not any(p["taxonomy"] == STAY_TAXONOMY for p in candidates.values()):
        decision = "constraint_clarification"
    if constraints.get("specific_activity") and not any(p["taxonomy"] in SLOT_TAXONOMIES for p in candidates.values()):
        decision = "constraint_clarification"
    if not any(p["taxonomy"] in SCHEDULABLE_TAXONOMIES for p in candidates.values()):
        decision = "fallback"
    return "success", decision


def evaluate_retrieval(state: dict) -> dict:
    """Update của `evaluate` (chưa gồm `events`): candidate, nguồn grounding, cảnh báo và quyết định."""
    errors = tool_errors(state)
    if not state.get("intent", {}).get("destination"):
        evaluation = "failed" if any(not e["retryable"] for e in errors) else "needs_retry" if errors else "success"
        return {"evaluation_result": evaluation}
    constraints = _relaxed_constraints(state)
    candidates, sources, dropped = collect(state.get("tool_results", []), state.get("details", {}),
                                           state["intent"], constraints)
    warnings = [{"code": reason, "message": DROPPED_MESSAGE, "productId": pid} for pid, reason in dropped.items()]
    evaluation, decision = _decision(errors, candidates, constraints)
    return {"candidates": candidates, "sources": sources, "warnings": warnings,
            "decision": decision, "evaluation_result": evaluation}
