"""Dựng lịch trình từ candidate bằng luật tất định; không có lượt gọi LLM nào ở đây."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import logging

from src.backend.app.domain.itinerary import flights as flight_rules
from src.backend.app.domain.itinerary.planning import (SCHEDULABLE_TAXONOMIES, compose_plan, day_windows, free_to_visit, multi_day_offers,
                                                        render_proposal, summary, totals, validate_plan)

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


#: Thứ tự liệt kê loại sản phẩm trong câu FALLBACK.
FALLBACK_TAXONOMIES = ("hotel", "attraction", "golf", "combo", "flight")


def _fallback_noun(state: dict, taxonomy: str | None) -> str:
    key = taxonomy if taxonomy in FALLBACK_TAXONOMIES else "other"
    return messages.message(state, f"fallback_noun_{key}")


def _found(state: dict, candidates: dict) -> str:
    counts = Counter(product["taxonomy"] for product in candidates.values())
    order = sorted(counts, key=lambda tax: FALLBACK_TAXONOMIES.index(tax) if tax in FALLBACK_TAXONOMIES else 99)
    return ", ".join(messages.message(state, "fallback_count", count=counts[tax], noun=_fallback_noun(state, tax))
                     for tax in order)


def fallback_message(state: dict, *, compose_failed: bool = False) -> str:
    """Câu FALLBACK dựng bằng luật từ dữ liệu thật của lượt: nguồn nào lỗi, vì sao không xếp được lịch, đã tìm được gì.
    Không qua LLM; tiêu đề cố định theo spec itinerary §4.3."""
    destination = state.get("intent", {}).get("destination") or ""
    candidates = state.get("candidates", {})
    lines: list[str] = []
    for result in state.get("tool_results", []):
        if not result.get("error"):
            continue
        if result.get("name") == "search_products":
            noun = _fallback_noun(state, (result.get("arguments") or {}).get("taxonomy"))
            lines.append(messages.message(state, "fallback_search_failed", noun=noun, destination=destination))
        elif result.get("name") == "get_recommendations":
            lines.append(messages.message(state, "fallback_recommendations_failed"))
        else:
            lines.append(messages.message(state, "fallback_source_failed"))
    if compose_failed:
        lines.append(messages.message(state, "fallback_compose_failed"))
    elif not any(product["taxonomy"] in SCHEDULABLE_TAXONOMIES for product in candidates.values()):
        lines.append(messages.message(state, "fallback_nothing_schedulable", destination=destination,
                                      found=_found(state, candidates)))
    lines.append(messages.message(state, "fallback_found", found=_found(state, candidates)))
    return messages.titled(messages.message(state, "fallback_title"), "\n".join(dict.fromkeys(lines)))


def fallback(state: dict, *, compose_failed: bool = False) -> dict:
    """Không dựng được lịch trình: trả danh sách ứng viên kèm lý do thật, hoặc lỗi khi không còn gì để trả."""
    if not state.get("candidates"):
        return failure(state, "LLM_UNAVAILABLE", messages.COMPOSE_UNAVAILABLE, retryable=True)
    return {"decision": "fallback",
            "response": {"status": "FALLBACK", "conversationId": state["conversation_id"],
                         "intent": state["intent"], "message": fallback_message(state, compose_failed=compose_failed),
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
    bỏ ràng buộc đang bật (quyết định review field 2026-09-28, history/2026-09-28-ap-dung-de-xuat-field-review-agent.md), rồi điểm đến khác trong catalog. Không tự đổi điểm đến
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
    if any(stay.get("source") == "RECOMMENDATION" for stay in plan.get("stays") or [plan.get("stay") or {}]):
        return True
    return any(slot.get("source") == "RECOMMENDATION" for day in plan.get("days", []) for slot in day.get("slots", []))


def _flight_warning(state: dict, reason: str | None, legs: list) -> dict | None:
    """Vì sao lịch trình không có (đủ) chặng bay (AC-AGT-02); None khi đủ vé hoặc người dùng không cần vé."""
    if reason is None or reason in flight_rules.SILENT_REASONS:
        return None
    intent, options = state["intent"], state.get("flight_options") or {}
    dates = flight_rules.trip_dates(intent)
    values = {"origin": options.get("origin") or intent.get("origin") or "",
              "destination": intent.get("destination") or "",
              "out": display_date(dates[0].isoformat()) if dates else "",
              "back": display_date(dates[1].isoformat()) if dates else ""}
    key = reason
    if reason == flight_rules.ONE_WAY_ONLY:
        key = "MISSING_RETURN" if legs and legs[0]["direction"] == "OUTBOUND" else "MISSING_OUTBOUND"
    return {"code": f"FLIGHT_{reason}", "message": messages.message(state, f"flight_warn_{key}", **values)}


def with_flights(plan: dict, legs: list, intent: dict) -> dict:
    """Gắn chặng bay chọn bằng luật (AC-AGT-02) vào lịch trình và tính lại tổng."""
    if legs:
        plan["flights"] = [{**leg, "product": summary(leg["product"])} for leg in legs]
        plan["bookableCount"] = plan.get("bookableCount", 0) + len(legs)
        plan["estimatedTotal"], plan["budgetStatus"] = totals(plan, intent)
    return plan


def composed(state: dict) -> dict:
    """Build the itinerary from the retrieved candidates with fixed rules; no model is consulted.

    Vé được chọn trước khi xếp lịch, để hoạt động của ngày đến và ngày về nằm trong cửa sổ giờ bay (AC-AGT-02).
    """
    legs, flight_reason = flight_rules.choose_flights(state.get("flight_options") or {}, state["intent"])
    windows = day_windows(state["intent"], legs)
    # Vé trừ vào ngân sách khi chọn khách sạn (chốt 2026-10-08); vé chưa rõ giá thì không so được với ngân sách.
    fares = [flight_rules.flight_cost(leg) for leg in legs]
    fixed_cost = None if any(fare is None for fare in fares) else sum(fares)
    proposal = compose_plan(state["candidates"], state["sources"], state["intent"], windows, fixed_cost)
    plan = render_proposal(proposal, state["candidates"], state["sources"], state["intent"])
    plan = with_flights(plan, legs, state["intent"])
    flight_warning = _flight_warning(state, flight_reason, legs)
    if validate_plan(plan, state["candidates"], state["sources"], state["intent"], state.get("constraints", {}),
                     flight_rules.flight_candidates(state.get("flight_options") or {})):
        raise ValueError("invalid composition")
    warnings = deepcopy(state.get("warnings", []))
    if flight_warning:
        warnings.append(flight_warning)
    warnings.append({"code": "SNAPSHOT_ONLY", "message": WARNINGS["SNAPSHOT_ONLY"]})
    warnings.append({"code": "SCHEDULE_ESTIMATE", "message": WARNINGS["SCHEDULE_ESTIMATE"]})
    if proposal.get("criteria") == "DISTANCE":
        # Tiêu chí xếp lịch được nói cho người dùng (AC-AGT-04); chỉ khi luật khoảng cách thật sự được dùng.
        budgeted = state["intent"].get("budget") is not None and fixed_cost is not None
        criteria = messages.message(state, "plan_criteria_budget" if budgeted else "plan_criteria")
        stays = plan.get("stays") or []
        if len(stays) > 1:
            criteria += " " + messages.message(state, "plan_criteria_change", night=stays[1]["fromNight"],
                                               first=stays[0]["product"]["name"], second=stays[1]["product"]["name"])
        warnings.append({"code": "PLAN_CRITERIA", "message": criteria})
    options = _stay_options(state, proposal)
    if options:
        warnings.append({"code": "STAY_OPTIONS", "message": _options_text(state, proposal, options)})
    if _uses_recommendation(plan):
        warnings.append({"code": "RECOMMENDATION_FALLBACK", "message": WARNINGS["RECOMMENDATION_FALLBACK"]})
    _budget_warnings(plan, state["intent"], warnings)
    no_stay = missing_stay_note(state, plan)
    if no_stay:
        warnings.append({"code": "NO_STAY_AVAILABLE", "message": no_stay})
    for day in plan["days"]:
        # Ngày giờ bay không chừa buổi nào (hạ cánh tối, bay về sáng) chỉ có dòng di chuyển: không phải ngày trống.
        if day["day"] in windows and not windows[day["day"]]["times"]:
            continue
        if not any(slot["product"] for slot in day["slots"]):
            warnings.append({"code": "DAY_WITHOUT_PRODUCTS",
                             "message": f"Ngày {day['day']} dành cho nghỉ ngơi hoặc hoạt động chung, "
                                        "chưa có sản phẩm được chọn."})
    response = {"status": "COMPLETED", "conversationId": state["conversation_id"],
                "intent": state["intent"], "itinerary": plan, "warnings": warnings}
    offers = _multi_day_offers(state)
    if offers:
        response["searchResults"] = offers
    return {"response": response, "stay_options": options}


def _stay_options(state: dict, proposal: dict) -> list[dict]:
    """Phương án khác của `compose_plan` kèm tên khách sạn lấy từ candidate (grounding); lưu vào hội thoại để lượt sau
    "lấy phương án N" biết khách sạn nào. Khách sạn không có trong candidate là lỗi luật, không bỏ qua."""
    options = []
    for index, option in enumerate(proposal.get("options") or [], start=1):
        stays = []
        for stay in option["stays"]:
            product = state["candidates"].get(stay["stay_id"])
            if product is None or product.get("taxonomy") != "hotel":
                raise ValueError("option stay is not a candidate hotel")
            stays.append({"productId": product["productId"], "name": product["name"],
                          "fromNight": stay["from_night"], "nights": stay["nights"]})
        options.append({"index": index, "stays": stays, "kmDelta": option["km_delta"],
                        "moneyDelta": option["money_delta"], "overBudget": option["over_budget"]})
    return options


def _options_text(state: dict, proposal: dict, options: list[dict]) -> str:
    """Mục "Phương án khác" (AC-AGT-04, chốt 2026-10-08): mọi con số do code tính, LLM không viết lại."""
    language = state.get("language", "vi")
    lines = [messages.message(state, "options_total", km=messages.distance(proposal["distance_km"], language))]
    for option in options:
        names = [stay["name"] for stay in option["stays"]]
        if len(option["stays"]) > 1:
            names = [f"{stay['name']} ({_nights(state, stay)})" for stay in option["stays"]]
        line = messages.message(state, "option_closer" if option["kmDelta"] < 0 else "option_cheaper",
                                n=option["index"], money=messages.money(abs(option["moneyDelta"]), language),
                                hotels=", ".join(names), km=messages.distance(abs(option["kmDelta"]), language))
        if option["overBudget"]:
            line += messages.message(state, "option_over_budget",
                                     money=messages.money(option["overBudget"], language))
        lines.append(line + ".")
    lines.append(messages.message(state, "options_pick"))
    return "\n".join(lines)


def _nights(state: dict, stay: dict) -> str:
    first, last = stay["fromNight"], stay["fromNight"] + stay["nights"] - 1
    return messages.message(state, "stay_night_single", first=first) if first == last else \
        messages.message(state, "stay_nights_range", first=first, last=last)


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
        return fallback(state, compose_failed=True)
