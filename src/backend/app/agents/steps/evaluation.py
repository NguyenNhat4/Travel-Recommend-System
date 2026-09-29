"""Luật chấm kết quả truy xuất: lọc candidate có grounding rồi chọn `decision` cho node sau."""
from __future__ import annotations

from copy import deepcopy

from src.backend.app.application.itinerary.retrieval import collect
from src.backend.app.application.itinerary.tool_contracts import SIMILAR_PRODUCTS
from src.backend.app.domain.itinerary.planning import SCHEDULABLE_TAXONOMIES, SLOT_TAXONOMIES, STAY_TAXONOMY

DROPPED_MESSAGE = "Một sản phẩm chưa đủ căn cứ hoặc không đáp ứng yêu cầu đã được loại."

# Similar là best-effort ở lượt đổi món: lỗi của nó không được đẩy lượt sang retry rồi FALLBACK.
SIMILAR_NO_ALTERNATIVE = {"PRODUCT_NOT_FOUND", "PRODUCT_NOT_INDEXED"}  # "không có phương án": luôn mềm
SIMILAR_UNAVAILABLE = {"SEARCH_UNAVAILABLE", "TOOL_TIMEOUT"}  # mềm khi đã có search trả dữ liệu


def _similar_unavailable(error: dict) -> bool:
    """Similar hỏng phía server hoặc đường truyền. In-process báo `SEARCH_UNAVAILABLE`; mode http còn gặp 5xx
    (kể cả 500 dạng text, đọc thành `INVALID_TOOL_RESPONSE` kèm `httpStatus`) và lỗi kết nối (`TOOL_HTTP_ERROR`
    không có `httpStatus`). Response 2xx sai hợp đồng (`httpStatus` rỗng hoặc 2xx) vẫn là lỗi vĩnh viễn."""
    status = error.get("httpStatus")
    return (error.get("code") in SIMILAR_UNAVAILABLE or (status is not None and status >= 500)
            or (error.get("code") == "TOOL_HTTP_ERROR" and status is None))


def _soft_similar_error(item: dict, search_ok: bool) -> bool:
    if item.get("name") != SIMILAR_PRODUCTS:
        return False
    error = item["error"]
    return error.get("code") in SIMILAR_NO_ALTERNATIVE or (search_ok and _similar_unavailable(error))


def tool_errors(state: dict) -> list[dict]:
    """Mọi lỗi của lượt truy xuất: lỗi từng tool call cộng lỗi lấy chi tiết sản phẩm, trừ lỗi mềm của Similar."""
    results = state.get("tool_results", [])
    search_ok = any(item.get("name") == "search_products" and "data" in item for item in results)
    errors = [item["error"] for item in results if "error" in item and not _soft_similar_error(item, search_ok)]
    errors.extend(state.get("detail_errors", {}).values())
    return errors


def _relaxed_constraints(state: dict) -> dict:
    """Recommendation tự bỏ vertical nào thì ghi lại, trừ khi người dùng bắt buộc có khách sạn."""
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
    return {"candidates": candidates, "sources": sources, "constraints": constraints, "warnings": warnings,
            "decision": decision, "evaluation_result": evaluation}
