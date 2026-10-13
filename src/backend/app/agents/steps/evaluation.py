"""Luật chấm kết quả truy xuất: lọc candidate có grounding rồi chọn `decision` cho node sau."""
from __future__ import annotations

from copy import deepcopy

from src.backend.app.application.itinerary.retrieval import (NOT_ON_SALE, collect, drop_summary, nearest_open_date,
                                                           reference_only)
from src.backend.app.application.itinerary.tool_contracts import SIMILAR_PRODUCTS
from src.backend.app.domain.itinerary import preferences
from src.backend.app.domain.itinerary.planning import SCHEDULABLE_TAXONOMIES, SLOT_TAXONOMIES, STAY_TAXONOMY

from . import messages, progress
from .classification import vietnam_today
from .messages import display_date

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


def _decision(errors: list[dict], candidates: dict, constraints: dict) -> str:
    """`decision` cho `routing.route_after_evaluate`: compose/no_results/fallback/constraint_clarification/
    needs_retry/failed."""
    # Authentication failures must never be hidden by a successful Search call.
    permanent = any(not e["retryable"] for e in errors)
    auth_error = any(e.get("httpStatus") == 401 or e.get("code") in {"INVALID_TOKEN", "TOKEN_EXPIRED"} for e in errors)
    if auth_error:
        return "failed"
    if errors and not permanent:
        return "needs_retry"
    if errors:
        return "fallback" if candidates else "failed"
    if not candidates:
        if any(constraints.get(key) for key in ("require_hotel", "specific_hotel", "specific_activity")):
            return "constraint_clarification"
        return "no_results"
    decision = "compose"
    # Ba kiểm tra dưới đây chạy tuần tự: không còn sản phẩm xếp được lịch thì `fallback` thắng, vì
    # hỏi lại người dùng về một điều kiện cũng không dựng nổi lịch trình.
    if constraints.get("require_hotel") and not any(p["taxonomy"] == STAY_TAXONOMY for p in candidates.values()):
        decision = "constraint_clarification"
    if constraints.get("specific_activity") and not any(p["taxonomy"] in SLOT_TAXONOMIES for p in candidates.values()):
        decision = "constraint_clarification"
    if not any(p["taxonomy"] in SCHEDULABLE_TAXONOMIES for p in candidates.values()):
        decision = "fallback"
    return decision


def _retrieved(state: dict) -> dict:
    """productId → sản phẩm (projection của tool, bổ sung chi tiết đã nạp) để cảnh báo nêu được ngày mở bán."""
    products = {}
    for result in state.get("tool_results", []):
        data = result.get("data", {})
        for projection in (*data.get("results", []), *data.get("recommendations", [])):
            if projection.get("productId"):
                products[projection["productId"]] = {**state.get("details", {}).get(projection["productId"], {}),
                                                     **projection}
    return products


def _dropped_message(state: dict, reason: str, product: dict) -> str:
    """Bị loại vì ngày thì nêu cửa sổ mở bán thật của sản phẩm; lý do khác giữ câu chung."""
    if reason == "PRODUCT_DROPPED_DATE" and product.get("availableFrom") and product.get("availableTo"):
        return messages.message(state, "dropped_date", start=display_date(product["availableFrom"]),
                                end=display_date(product["availableTo"]))
    return DROPPED_MESSAGE


def _preferred_stays(state: dict, candidates: dict, sources: dict) -> tuple[dict, dict]:
    """Lọc mềm theo sở thích khách sạn (FR-AGT-06): bỏ khách sạn không hợp chỉ khi còn đủ khách sạn hợp
    (`preferences.preferred`); sản phẩm khác giữ nguyên."""
    wanted = preferences.from_interests((state.get("intent") or {}).get("interests"))
    hotels = [product for product in candidates.values() if product.get("taxonomy") == STAY_TAXONOMY]
    kept = {product["productId"] for product in preferences.preferred(hotels, wanted)}
    if len(kept) == len(hotels):
        return candidates, sources
    dropped = {product['productId'] for product in hotels} - kept
    row = progress.group('plan:hotel', 'hotel', state.get('intent'))
    if row:
        for pid in dropped:
            row['counter'].record(pid, 'PREFERENCE')
    return ({pid: product for pid, product in candidates.items() if pid not in dropped},
            {pid: source for pid, source in sources.items() if pid not in dropped})


def evaluate_retrieval(state: dict) -> dict:
    """Update của `evaluate` (chưa gồm `events`): candidate, nguồn grounding, cảnh báo và quyết định."""
    errors = tool_errors(state)
    if not state.get("intent", {}).get("destination"):
        decision = "failed" if any(not e["retryable"] for e in errors) else "needs_retry" if errors else "compose"
        return {"decision": decision}
    constraints = _relaxed_constraints(state)
    def counts(kind):
        row = progress.group(f'plan:{kind}', kind, state.get('intent'))
        return row['counter'] if row else None
    candidates, sources, dropped = collect(state.get("tool_results", []), state.get("details", {}),
                                           state["intent"], constraints, counts=counts)
    candidates = reference_only(candidates, dropped)
    sources = {pid: source for pid, source in sources.items() if pid in candidates}
    candidates, sources = _preferred_stays(state, candidates, sources)
    products = _retrieved(state)
    if progress.active():
        for pid, reason in dropped.items():
            row = progress.group(f"plan:{products.get(pid, {}).get('taxonomy')}", products.get(pid, {}).get('taxonomy'), state.get('intent'))
            if row:
                row['counter'].record(pid, reason, outside=reason in ('PRODUCT_DROPPED_DESTINATION','PRODUCT_DROPPED_EXCLUDED','PRODUCT_DROPPED_TAXONOMY'))
        for result in state.get('tool_results') or []:
            kind = (result.get('arguments') or {}).get('taxonomy')
            row = progress.group(f'plan:{kind}',kind,state.get('intent'))
            if row:
                row['status'] = 'failed' if result.get('error') else ('ok' if row['counter'].snapshot()['eligible'] else 'empty')
    warnings = [{"code": reason, "message": _dropped_message(state, reason, products.get(pid, {})), "productId": pid}
                for pid, reason in dropped.items()]
    decision = _decision(errors, candidates, constraints)
    update = {"candidates": candidates, "sources": sources, "warnings": warnings, "decision": decision}
    # Cần `details` (chứa ngày mở bán) trước khi xoá bên dưới; `compose`/`clarify` dùng các ngày này để nói lý do
    # và gợi ý đặt lại chuyến.
    if decision == "no_results" or any(product.get(NOT_ON_SALE) for product in candidates.values()):
        # Lịch tham khảo (điểm tham quan chưa mở bán cho ngày đi) cũng cần ngày gần nhất còn bán để gợi ý đặt lại.
        update["nearest_open_date"] = nearest_open_date(state.get("tool_results", []), state.get("details", {}),
                                                        state["intent"], constraints, vietnam_today())
    if decision in {"compose", "constraint_clarification"}:
        update["drop_summary"] = drop_summary(state.get("tool_results", []), state.get("details", {}),
                                              state["intent"], constraints, vietnam_today())
    # `details` đã được `collect()` tiêu thụ ở trên; không giữ lại payload ProductDetail nặng trong state/trace.
    return {**update, "details": {}}
