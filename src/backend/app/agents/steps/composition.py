"""Dựng lịch trình từ candidate bằng luật tất định; không có lượt gọi LLM nào ở đây."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date, timedelta
import logging

from src.backend.app.domain.itinerary import flights as flight_rules
from src.backend.app.domain.itinerary.planning import (SCHEDULABLE_TAXONOMIES, STAY_TAXONOMY, compose_plan, day_windows,
                                                        free_to_visit, multi_day_offers, price_plan, render_proposal,
                                                        stay_rooms, summary, validate_plan)

from src.backend.app.application.itinerary.retrieval import NOT_ON_SALE

from . import messages
from .classification import vietnam_today
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
    "STAY_ROOMS_UNKNOWN": "Khách sạn chưa ghi giá gồm bao nhiêu người lớn, nên giá chưa tính đủ số phòng cho cả đoàn; "
                          "tổng đang tính 1 phòng.",
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
    text = messages.message(state, f"flight_warn_{key}", **values)
    if reason in (flight_rules.NO_FLIGHT_ON_DATES, flight_rules.ONE_WAY_ONLY):
        text = " ".join(filter(None, (text, _nearest_dates_sentence(state, options, intent))))
    return {"code": f"FLIGHT_{reason}", "message": text}


def _nearest_dates_sentence(state: dict, options: dict, intent: dict) -> str | None:
    """Câu gợi ý ngày gần nhất có vé, giữ số ngày của chuyến; dữ liệu là chuyến đã tải lượt này (không tra thêm)."""
    found = flight_rules.nearest_dates(options, intent, vietnam_today())
    joint = state.get("joint_date")
    if joint:
        # Ngày đi chung (có cả khách sạn, vé tham quan) đứng đầu và là ví dụ "đổi sang".
        found = [{"startDate": joint, "complete": True}, *(item for item in found if item["startDate"] != joint)]
        found = found[:flight_rules.NEAREST_DATES]
    if not found:
        return None
    days = intent.get("days") or 1
    items = []
    for item in found:
        start = date.fromisoformat(item["startDate"])
        label = messages.message(state, "flight_nearest_both" if item["complete"] else "flight_nearest_out_only",
                                 out=display_date(item["startDate"]),
                                 back=display_date((start + timedelta(days=days - 1)).isoformat()))
        items.append(label)
    return messages.message(state, "flight_nearest", dates=messages.message(state, "detail_joiner").join(items),
                            example=display_date(found[0]["startDate"])[:5])


def _sale_window(state: dict, product: dict) -> str:
    start, end = product.get("availableFrom"), product.get("availableTo")
    if start and end:
        return messages.message(state, "sale_window", start=display_date(start), end=display_date(end))
    return messages.message(state, "sale_window_unknown")


def _not_on_sale(state: dict, plan: dict) -> list[dict]:
    """Điểm tham quan giữ làm tham khảo vì vé chưa mở bán cho ngày đi (`retrieval.NOT_ON_SALE`): không tính là mục đặt
    được, mỗi điểm một cảnh báo `PRODUCT_NOT_ON_SALE_FOR_DATE` nêu cửa sổ mở bán thật (code là chuỗi tự do, contract
    không đổi)."""
    flagged = [slot["product"]["productId"] for day in plan["days"] for slot in day["slots"]
               if slot.get("product") and state["candidates"].get(slot["product"]["productId"], {}).get(NOT_ON_SALE)
               and not free_to_visit(state["candidates"][slot["product"]["productId"]])]
    if not flagged:
        return []
    plan["bookableCount"] = max(0, plan.get("bookableCount", 0) - len(flagged))
    warnings = []
    for product_id in flagged:
        product = state["candidates"][product_id]
        warnings.append({"code": "PRODUCT_NOT_ON_SALE_FOR_DATE", "productId": product_id,
                         "message": messages.message(state, "not_on_sale_item",
                                                     window=_sale_window(state, product))})
    return warnings


def with_flights(plan: dict, legs: list, intent: dict) -> dict:
    """Gắn chặng bay chọn bằng luật (AC-AGT-02) vào lịch trình và tính lại tổng."""
    if legs:
        plan["flights"] = [{**leg, "product": summary(leg["product"])} for leg in legs]
        plan["bookableCount"] = plan.get("bookableCount", 0) + len(legs)
        price_plan(plan, intent)
    return plan


def _planned(state: dict, proposal: dict, legs: list, flight_reason: str | None, windows: dict,
             fixed_cost: int | None) -> tuple[dict, list[dict]]:
    """Lịch trình đã kiểm và cảnh báo của một proposal (lịch chính hoặc một phương án khác), chưa có `STAY_OPTIONS`.
    Luật tự bác đề xuất của nó thì ném `ValueError`."""
    plan = render_proposal(proposal, state["candidates"], state["sources"], state["intent"])
    plan = with_flights(plan, legs, state["intent"])
    flight_warning = _flight_warning(state, flight_reason, legs)
    if validate_plan(plan, state["candidates"], state["sources"], state["intent"], state.get("constraints", {}),
                     flight_rules.flight_candidates(state.get("flight_options") or {})):
        raise ValueError("invalid composition")
    warnings = deepcopy(state.get("warnings", []))
    if flight_warning:
        warnings.append(flight_warning)
    warnings += _not_on_sale(state, plan)
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
    if _uses_recommendation(plan):
        warnings.append({"code": "RECOMMENDATION_FALLBACK", "message": WARNINGS["RECOMMENDATION_FALLBACK"]})
    for stay in plan.get("stays") or []:
        # Thiếu `priceAdults` thì tiền khách sạn tính 1 phòng (AC-AGT-04, chốt 2026-10-09): báo để không hiểu nhầm là đủ.
        if stay_rooms(state["candidates"][stay["product"]["productId"]], state["intent"].get("party")) is None:
            warnings.append({"code": "STAY_ROOMS_UNKNOWN", "message": WARNINGS["STAY_ROOMS_UNKNOWN"],
                             "productId": stay["product"]["productId"]})
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
    return plan, warnings


def with_options_warning(warnings: list[dict], text: str | None) -> list[dict]:
    """Chèn cảnh báo `STAY_OPTIONS` ngay sau `PLAN_CRITERIA` (thứ tự cũ của mục "Phương án khác"); `warnings` đến từ
    `_planned` nên chưa có `STAY_OPTIONS`."""
    if not text:
        return warnings
    at = next((index + 1 for index, warning in enumerate(warnings) if warning.get("code") == "PLAN_CRITERIA"),
              len(warnings))
    return warnings[:at] + [{"code": "STAY_OPTIONS", "message": text}] + warnings[at:]


def stay_options_payload(distance_km: float, options: list[dict]) -> dict:
    """Trường `stayOptions` của response (contract 1.20.0) từ các phương án lưu trong state."""
    return {"distanceKm": distance_km,
            "options": [{key: option[key] for key in ("index", "kmDelta", "moneyDelta", "overBudget", "itinerary")}
                        for option in options]}


def _joint_date(state: dict, flight_reason: str | None) -> str | None:
    """Một ngày đi gợi ý chung cho mọi phần đang thiếu vì ngày (vé máy bay, khách sạn, vé tham quan chưa mở bán), để các
    câu gợi ý cùng nói một ngày (`flight_rules.joint_start`). Dữ liệu là kết quả đã tải lượt này."""
    intent = state["intent"]
    dates = flight_rules.trip_dates(intent)
    if dates is None:
        return None
    days, today = intent["days"], vietnam_today()
    flight_starts = None
    if flight_reason in (flight_rules.NO_FLIGHT_ON_DATES, flight_rules.ONE_WAY_ONLY):
        found = flight_rules.nearest_dates(state.get("flight_options") or {}, intent, today,
                                           limit=flight_rules.JOINT_SEARCH_DAYS)
        flight_starts = [date.fromisoformat(item["startDate"]) for item in found if item["complete"]]
    windows = []
    stay = (state.get("drop_summary") or {}).get(STAY_TAXONOMY) or {}
    if stay.get("openFrom") and stay.get("openTo") and days >= 2 and not _has_stay_candidate(state):
        windows.append((date.fromisoformat(stay["openFrom"]), date.fromisoformat(stay["openTo"]), days - 2))
    closing = [product.get("availableTo") for product in state["candidates"].values()
               if product.get(NOT_ON_SALE) and product.get("availableTo")]
    if closing:
        windows.append((None, date.fromisoformat(max(closing)), days - 1))
    joint = flight_rules.joint_start(dates[0], days, today, flight_starts, windows)
    return joint.isoformat() if joint else None


def _has_stay_candidate(state: dict) -> bool:
    return any(product.get("taxonomy") == STAY_TAXONOMY for product in state["candidates"].values())


def composed(state: dict) -> dict:
    """Build the itinerary from the retrieved candidates with fixed rules; no model is consulted.

    Vé được chọn trước khi xếp lịch, để hoạt động của ngày đến và ngày về nằm trong cửa sổ giờ bay (AC-AGT-02).
    Mỗi phương án khác cũng được dựng thành lịch đầy đủ (cùng luật, cùng kiểm tra) để client xem trước và lượt
    "chọn phương án" chỉ lấy lịch đó ra, không tìm lại (AC-AGT-04, chốt 2026-10-08).
    """
    options_by_route = state.get("flight_options") or {}
    legs, flight_reason = flight_rules.choose_flights(options_by_route, state["intent"],
                                                      (state.get("constraints") or {}).get("chosen_flights"))
    # Mọi câu gợi ý đổi ngày (vé, khách sạn, vé tham quan) cùng nói một ngày đi có đủ các phần đó.
    joint = _joint_date(state, flight_reason)
    if joint:
        state = {**state, "joint_date": joint, "nearest_open_date": joint}
    windows = day_windows(state["intent"], legs)
    # Vé trừ vào ngân sách khi chọn khách sạn (chốt 2026-10-08); vé chưa rõ giá thì không so được với ngân sách.
    fares = [flight_rules.flight_cost(leg) for leg in legs]
    fixed_cost = None if any(fare is None for fare in fares) else sum(fares)
    proposal = compose_plan(state["candidates"], state["sources"], state["intent"], windows, fixed_cost,
                            flight_rules.airports(legs))
    plan, warnings = _planned(state, proposal, legs, flight_reason, windows, fixed_cost)
    options = []
    for option, proposed in zip(_stay_options(state, proposal), proposal.get("options") or []):
        try:
            option["itinerary"], option["warnings"] = _planned(
                state, {**proposed["proposal"], "criteria": proposal.get("criteria")}, legs, flight_reason, windows,
                fixed_cost)
        except ValueError:
            # Luật bác lịch của một phương án là bug backend: log, bỏ phương án đó, lịch chính vẫn trả.
            logger.exception("itinerary.option_composition_failed requestId=%s", state.get("request_id", "unknown"))
            continue
        option["distanceKm"] = round(proposal["distance_km"] + option["kmDelta"], 1)
        options.append({**option, "index": len(options) + 1})
    response = {"status": "COMPLETED", "conversationId": state["conversation_id"],
                "intent": state["intent"], "itinerary": plan,
                "warnings": with_options_warning(warnings, options_text(state, proposal["distance_km"], options) if options else None)}
    offers = _multi_day_offers(state)
    if offers:
        response["searchResults"] = offers
    current = None
    if options:
        response["stayOptions"] = stay_options_payload(proposal["distance_km"], options)
        current = {"itinerary": plan, "warnings": warnings, "distanceKm": proposal["distance_km"],
                   "stays": [_stored_stay(state["candidates"][stay["product"]["productId"]],
                                          stay.get("fromNight", 1), stay["nights"])
                             for stay in plan.get("stays") or []]}
        if offers:
            current["searchResults"] = offers
    # Chuyến khác cùng ngày của từng chặng, để lượt sau "đổi chuyến bay" hỏi bằng lựa chọn cụ thể (`steps/changes.py`).
    return {"response": response, "stay_options": options, "current_plan": current,
            "flight_choices": flight_rules.flight_choices(options_by_route, legs),
            **({"nearest_open_date": joint} if joint else {})}


def _stored_stay(product: dict, from_night: int, nights: int) -> dict:
    """Một khách sạn của lịch lưu trong hội thoại. Kèm `priceAdults` của candidate: lịch trong response chỉ có `summary`
    (không giữ khoá này), mà lượt chọn phương án phải tính lại đúng số phòng để `finalize` kiểm (AC-AGT-04, 2026-10-09)."""
    stored = {"productId": product["productId"], "name": product["name"], "fromNight": from_night, "nights": nights}
    price_adults = (product.get("attributes") or {}).get("priceAdults")
    if price_adults is not None:
        stored["priceAdults"] = price_adults
    return stored


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
            stays.append(_stored_stay(product, stay["from_night"], stay["nights"]))
        options.append({"index": index, "stays": stays, "kmDelta": option["km_delta"],
                        "moneyDelta": option["money_delta"], "overBudget": option["over_budget"]})
    return options


def options_text(state: dict, distance_km: float, options: list[dict]) -> str:
    """Mục "Phương án khác" (AC-AGT-04, chốt 2026-10-08): mọi con số do code tính, LLM không viết lại."""
    language = state.get("language", "vi")
    lines = [messages.message(state, "options_total", km=messages.distance(distance_km, language))]
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
