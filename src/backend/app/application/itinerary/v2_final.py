"""Dựng response assistant v2 từ quyết định orc đã qua kiểm (PRD architecture §3).

Chỉ điền dữ kiện theo mã orc chọn: tên, giá, ảnh lấy từ sản phẩm tra trong lượt; tiền của lịch lấy từ kết quả
build_itinerary. Không thêm, bớt hay xếp lại thẻ. Câu cảnh báo do code viết cho các mã orc đã công bố.
"""
from __future__ import annotations

import re
import secrets
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from src.backend.app.domain.itinerary.draft_validation import entry_mode
from src.backend.app.domain.itinerary.planning import stay_rooms
from src.shared.contracts.scripts.bundle_openapi import bundle

from .product_registry import ProductRegistry

ENTRY = Path(__file__).resolve().parents[4] / "shared/contracts/assistant-v2.openapi.yaml"
PRODUCT_FIELDS = ("productId", "name", "taxonomy", "destination", "brand", "status", "unitPrice", "currency",
                  "priceUnit", "priceAsOf", "available", "availabilityStatus", "bookable", "availableFrom",
                  "availableTo", "imageUrl", "rating", "reviewCount", "attributes", "description", "fareClasses", "entryPolicy")
WARNINGS = {
    "vi": {
        "FREE_ENTRY_ASSUMED": "Các điểm tham quan tự do chưa có xác nhận đầy đủ về phí vào cửa; bạn nên kiểm tra trước khi đi. Mua sắm và dịch vụ tại chỗ có thể tính phí riêng.",
        "OVER_TRIP_BUDGET": "Tổng chi phí các sản phẩm trong lịch là {total}, vượt ngân sách {budget} là {over}.",
        "PRICE_UNKNOWN": "Một số sản phẩm chưa có giá nên chưa tính được tổng; phần đã biết giá là {subtotal}.",
        "OPENING_HOURS_UNKNOWN": "Giờ mở cửa của một số điểm chưa có trong dữ liệu, bạn nên kiểm tra trước khi đi.",
        "TIMING_ESTIMATED": "Một số giờ trong lịch là ước tính, chưa xác minh từ dữ liệu.",
        "TRAVEL_TIME_UNKNOWN": "Thời gian di chuyển giữa các điểm chưa được tính vào lịch.",
        "PRICE_CAPACITY_UNKNOWN": "Chưa rõ giá phòng đã bao gồm bao nhiêu người; tính theo sức chứa chỉ là ước tính, cần xác nhận trước khi đặt.",
        "ROOM_CAPACITY_UNKNOWN": "Chưa có sức chứa tối đa của một số hạng phòng; cần xác nhận trước khi đặt.",
        "OPTIMIZATION_UNAVAILABLE": "Chưa sắp lại thứ tự cho bớt đi lại được vì thiếu vị trí của một số điểm.",
        "SIMULATED_PRICE": "Giá vé máy bay trong lịch là giá minh hoạ của dữ liệu.",
    },
    "en": {
        "FREE_ENTRY_ASSUMED": "Entry fees for these freely accessible places are not fully confirmed; please check before visiting. Shopping and on-site services may cost extra.",
        "OVER_TRIP_BUDGET": "The selected products total {total}, which is {over} over your {budget} budget.",
        "PRICE_UNKNOWN": "Some products have no price yet, so the total is unknown; the priced part is {subtotal}.",
        "OPENING_HOURS_UNKNOWN": "Opening hours of some places are not in our data; please check before you go.",
        "TIMING_ESTIMATED": "Some times in this plan are estimates, not verified from data.",
        "TRAVEL_TIME_UNKNOWN": "Travel time between places is not included in the plan.",
        "PRICE_CAPACITY_UNKNOWN": "Guests included in the room price are unknown; occupancy-based room costs are estimates to confirm before booking.",
        "ROOM_CAPACITY_UNKNOWN": "Maximum occupancy is missing for some room types; confirm it before booking.",
        "OPTIMIZATION_UNAVAILABLE": "The order could not be optimised because some locations are missing.",
        "SIMULATED_PRICE": "Flight prices in this plan are illustrative catalog prices.",
    },
}
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?")
COVERAGE = {"vi": "Chỉ gồm các sản phẩm trong lịch; chưa gồm ăn uống và đi lại tự túc.",
            "en": "Only the products in this plan; meals and self-arranged transport are not included."}


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    components = bundle(ENTRY)["components"]
    return Draft202012Validator({"$ref": "#/components/schemas/AssistantV2Final", "components": components},
                                format_checker=FormatChecker())


def money(value: int, language: str) -> str:
    grouped = f"{int(value):,}"
    return f"{grouped.replace(',', '.')} ₫" if language == "vi" else f"{grouped} VND"


def card(product: dict[str, Any]) -> dict[str, Any]:
    return {key: product[key] for key in PRODUCT_FIELDS if key in product}


def _fact_text(field: str, value: Any, language: str) -> str:
    if isinstance(value, bool):
        return ("có" if value else "không") if language == "vi" else ("yes" if value else "no")
    if isinstance(value, int) and field.endswith(("start_minute", "end_minute", "startMinute", "endMinute")):
        return f"{value // 60:02d}:{value % 60:02d}"
    if isinstance(value, (int, float)) and field.endswith(("_vnd", "Price")):
        return money(value, language)
    if isinstance(value, str) and ISO_DATE.match(value):
        day = date.fromisoformat(value[:10]).strftime("%d/%m/%Y")
        return f"{value[11:16]} {day}" if "T" in value else day
    return str(value)


def _segment_text(segment: dict[str, Any], registry: ProductRegistry, results: dict[str, dict[str, Any]],
                  language: str) -> str:
    if segment["type"] == "text":
        return segment["text"]
    if segment["type"] == "product":
        # Cùng dạng link với lời diễn giải v1: widget đặt thẻ ngay sau dòng đầu tiên nhắc sản phẩm (AC-AGT-07).
        product = registry.product(segment["ref"])
        name = " ".join(product["name"].replace("[", " ").replace("]", " ").split())
        return f"[{name}](product:{product['productId']})"
    return _fact_text(segment["field"], fact(registry, results, segment["ref"], segment["field"]), language)


_SENTENCE_END = re.compile(r"[.!?…](?=\s+\S)")


def _join(parts: list[tuple[str, bool]]) -> str:
    """Nối đoạn chữ và dữ kiện, thêm khoảng trắng khi model quên.

    Widget đặt thẻ sau dòng đầu tiên nhắc sản phẩm, nên câu chứa sản phẩm (`True`) kết thúc đoạn: thẻ đứng ngay sau
    câu đó thay vì dồn thành danh sách cuối câu trả lời (AC-AGT-07). Câu mới bắt đầu sau dấu kết câu, hoặc ngay sau
    tên sản phẩm khi chữ tiếp theo viết hoa (model đặt tên như tiêu đề, không có dấu chấm).
    """
    text, open_product, after_product = "", False, False
    for part, is_product in parts:
        if is_product:
            if text.strip() and text.rstrip()[-1] in ".!?…":
                text = text.rstrip() + "\n\n"
            open_product = True
        elif open_product and part.strip():
            body = part.lstrip()
            if (after_product or text.rstrip()[-1:] in (".", "!", "?", "…")) and body[0].isupper():
                text, part, open_product = text.rstrip() + "\n\n", body, False
            else:
                end = next((m for m in _SENTENCE_END.finditer(part) if part[m.end():].lstrip()[:1].isupper()), None)
                if end:
                    part = part[:end.end()] + "\n\n" + part[end.end():].lstrip()
                    open_product = False
        if text and part and not text[-1].isspace() and not part[0].isspace() and part[0] not in ".,;:!?)…/":
            text += " "
        text += part
        after_product = is_product
    return text.strip()


def _itinerary(plan: dict[str, Any], language: str) -> dict[str, Any]:
    draft, products, costs = plan["draft"], plan["products"], plan["costs"]
    start = date.fromisoformat(draft["start_date"])
    party = {"adults": draft["adults"], "children": draft["children"]}
    days = [{"dayIndex": day["day_index"], "date": (start + timedelta(days=day["day_index"] - 1)).isoformat(),
             "activities": [{"product": card(products[a["product_ref"]]), "startMinute": a["start_minute"],
                             "endMinute": a["end_minute"], "timingSource": a["timing_source"],
                             "assumption": a["assumption"]} for a in day["activities"]]}
            for day in plan["plan_days"]]
    stays = [{"product": card(products[stay["product_ref"]]), "checkIn": stay["check_in"],
              "checkOut": stay["check_out"], "rooms": stay.get("computed_rooms", stay_rooms(products[stay["product_ref"]], party)),
              "nights": (date.fromisoformat(stay["check_out"]) - date.fromisoformat(stay["check_in"])).days}
             for stay in draft["stays"]]
    return {"planResultId": plan["plan_result_id"], "party": party,
            "destination": draft["destination"], "startDate": draft["start_date"],
            "days": days, "stays": stays,
            "flights": [{"product": card(products[f["product_ref"]]), "role": f["role"]} for f in draft["flights"]],
            "nights": plan["nights"], "feasibility": plan["feasibility"],
            "costs": {"knownSubtotalVnd": costs["known_subtotal_vnd"], "estimatedTotalVnd": costs["estimated_total_vnd"],
                      "unpricedProductIds": [products[ref]["productId"] for ref in costs["unpriced_refs"]],
                      "tripBudgetVnd": costs["trip_budget_vnd"], "overByVnd": costs["over_by_vnd"],
                      "budgetStatus": costs["budget_status"], "coverageNotes": [COVERAGE[language]]}}


def _warning_text(code: str, costs: dict[str, Any], language: str) -> str:
    amounts = {key: money(costs[name], language) if costs[name] is not None else ""
               for key, name in (("total", "estimated_total_vnd"), ("budget", "trip_budget_vnd"),
                                 ("over", "over_by_vnd"), ("subtotal", "known_subtotal_vnd"))}
    return WARNINGS[language][code].format(**amounts)


def render_final(decision: dict[str, Any], *, registry: ProductRegistry, plans: dict[str, dict[str, Any]],
                 results: dict[str, dict[str, Any]], conversation_id: str, run_id: str,
                 language: str = "vi") -> tuple[dict[str, Any], dict[str, Any]]:
    """Response theo contract và phần nhớ cho lượt sau: thẻ đã hiện (`shown`) và lệnh của nút (`actions`).

    Response không khớp contract thì ValueError (orc sửa lại), không tự cắt cho vừa.
    """
    plan = plans[decision["plan_result_id"]] if decision["plan_effect"] == "replace" else None
    paragraphs = [_join([(_segment_text(segment, registry, results, language), segment["type"] == "product")
                         for segment in decision["answer"]])]
    if plan:
        paragraphs += [_warning_text(w["code"], plan["costs"], language) for w in plan["warnings"]
                       if w["code"] in decision["disclosures"]]

    shown_refs: list[str] = [ref for refs in decision["cards"].values() for ref in refs]
    presented_refs = shown_refs + [a["product_ref"] for a in decision["alternatives"]]
    presented_refs += [s["ref"] for s in decision["answer"] if s["type"] == "product"]
    assumed_refs = [ref for ref in dict.fromkeys(presented_refs) if entry_mode(registry.product(ref)) == "assumed_free"]
    plan_assumed = any(w["code"] == "FREE_ENTRY_ASSUMED" for w in plan["warnings"]) if plan else False
    if assumed_refs and not plan_assumed and "FREE_ENTRY_ASSUMED" in decision["disclosures"]:
        paragraphs.append(WARNINGS[language]["FREE_ENTRY_ASSUMED"])
    actions: dict[str, dict[str, Any]] = {}
    alternatives = []
    for alternative in decision["alternatives"]:
        ref, alternative_id, action_id = alternative["product_ref"], secrets.token_hex(6), secrets.token_hex(8)
        option = plans.get(alternative["plan_result_id"] or "")
        actions[action_id] = {"type": "select_alternative", "alternativeId": alternative_id, "product_ref": ref,
                              "name": registry.product(ref)["name"], "draft": option["draft"] if option else None}
        alternatives.append({"alternativeId": alternative_id, "product": card(registry.product(ref)),
                             "violates": alternative["violates"], "disclosures": [alternative["disclosure"]],
                             "itinerary": _itinerary(option, language) if option else None,
                             "uiAction": {"type": "select_alternative", "actionId": action_id,
                                          "alternativeId": alternative_id}})
        shown_refs.append(ref)
    suggestions = []
    for suggestion in decision["suggestions"]:
        if suggestion["fare_query"] is None:
            suggestions.append({"label": suggestion["label"], "message": suggestion["label"], "uiAction": None})
            continue
        action_id = secrets.token_hex(8)
        actions[action_id] = {"type": "fare_query", "label": suggestion["label"], "query": suggestion["fare_query"]}
        suggestions.append({"label": suggestion["label"], "message": None,
                            "uiAction": {"type": "fare_query", "actionId": action_id}})

    final = {
        "conversationId": conversation_id, "runId": run_id, "turnKind": decision["turn_kind"],
        "message": "\n\n".join(p for p in paragraphs if p),
        "recommendations": {taxonomy: [card(registry.product(ref)) for ref in refs]
                            for taxonomy, refs in decision["cards"].items()},
        "alternatives": alternatives,
        "itinerary": _itinerary(plan, language) if plan else None,
        "planEffect": decision["plan_effect"], "planRevision": 0,
        "warnings": [{"id": w["code"], "code": w["code"], "severity": "warning",
                      "message": _warning_text(w["code"], plan["costs"], language),
                      "productIds": [plan["products"][ref]["productId"] for ref in w["refs"]]}
                     for w in plan["warnings"]] if plan else [],
        "suggestions": suggestions,
    }
    if assumed_refs:
        existing = next((w for w in final["warnings"] if w["code"] == "FREE_ENTRY_ASSUMED"), None)
        product_ids = [registry.product(ref)["productId"] for ref in assumed_refs]
        if existing:
            existing["productIds"] = list(dict.fromkeys(existing["productIds"] + product_ids))
        else:
            final["warnings"].append({"id": "FREE_ENTRY_ASSUMED", "code": "FREE_ENTRY_ASSUMED",
                                      "severity": "warning", "message": WARNINGS[language]["FREE_ENTRY_ASSUMED"],
                                      "productIds": product_ids})
    errors = [error.message for error in _validator().iter_errors(final)]
    if errors:
        raise ValueError("; ".join(errors)[:500])
    if plan:
        shown_refs += list(plan["products"])
    shown = {}
    for ref in dict.fromkeys(shown_refs):
        product = registry.product(ref)
        shown[ref] = {"productId": product["productId"], "name": product["name"], "taxonomy": product["taxonomy"]}
    return final, {"shown": shown, "actions": actions}


def fact(registry: ProductRegistry, results: dict[str, dict[str, Any]], ref: str, field: str) -> Any:
    """Giá trị dữ kiện orc trích: `p3` + field sản phẩm, hoặc `c2` + đường dẫn trong data của lời gọi đó."""
    if ref.startswith("p"):
        return registry.fact(ref, field)
    value: Any = (results.get(ref) or {}).get("data")
    for key in field.split("."):
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list) and key.isdigit() and int(key) < len(value):
            value = value[int(key)]
        else:
            value = None
    return value if isinstance(value, (str, int, float, bool)) else None
