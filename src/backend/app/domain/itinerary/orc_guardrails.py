"""Kiểm câu trả lời orc đề xuất (assistant v2) trước khi hiển thị; không chọn, thêm hay cắt sản phẩm.

Mỗi vấn đề là `{"code", "field", "refs"}`. Mã thuộc `FATAL` dừng lượt ngay; mã khác trả về cho orc sửa (một lần).
Vượt ngân sách không phải vấn đề: chỉ cần công bố cảnh báo (PRD architecture §3, AC-AGT-04/06/07).
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from typing import Any

from .draft_validation import cost_mode, entry_mode
from .normalization import fold

FATAL = {"SECRET_EXPOSURE"}
MAX_CARDS_PER_TAXONOMY = 10
#: Bốn trường bắt buộc để lập lịch (AC-AGT-01); trẻ em, ngân sách, nơi đi không bắt buộc.
TRIP_FIELDS = ("destination", "start_date", "days", "adults")


def unconfirmed_trip_fields(draft: dict[str, Any], context: dict[str, Any]) -> list[str]:
    """Trường bắt buộc mà lịch dùng giá trị khác ngữ cảnh đã lưu (ngữ cảnh chỉ nhận giá trị có căn cứ từ khách).

    Lịch không được lưu với số ngày, số người hay ngày đi orc tự điền khi khách chưa nói hoặc chưa đồng ý đề xuất.
    """
    return [field for field in TRIP_FIELDS
            if context.get(field) is None or fold(str(context[field])) != fold(str(draft.get(field)))]
#: Số tiền, giờ hay link viết thẳng trong lời văn: phải đi qua đoạn fact để số đúng dữ liệu (NFR-REL-01).
_NUMBER_TEXT = re.compile(
    r"\d[\d.,]*\s*(?:vnd|vnđ|đ\b|₫|đồng|k\b|nghìn|ngàn|tr\b|triệu|tỷ|usd|\$|km\b)|\b\d{1,3}(?:[.,]\d{3})+\b"
    r"|\b\d{1,2}[:h]\d{2}\b|https?://|/product/",
    re.IGNORECASE)
_BOOKING_CLAIM = re.compile(r"đã đặt|đã thanh toán|đặt thành công|booking confirmed", re.IGNORECASE)
_SECRET = re.compile(r"sk-[a-zA-Z0-9]{10,}|bearer\s+[a-zA-Z0-9._-]{10,}|AIzaSy[a-zA-Z0-9_-]{10,}", re.IGNORECASE)
_INTERNAL_DETAILS = re.compile(
    r"\b(?:catalog(?:ue)?|cursor|offset|registry|taxonomy|toolmessage)\b"
    r"|\b(?:find_products|get_products|plan_itinerary|lookup_flights|update_trip|free_only)\b"
    r"|phân trang|trang (?:kết quả|hiện tại|vừa kiểm|đã kiểm|kế tiếp)"
    r"|(?:còn|các|những) trang (?:chưa|khác|kết quả|tiếp)", re.IGNORECASE)


def _issue(code: str, field: str, refs: list[str] | None = None) -> dict[str, Any]:
    return {"code": code, "field": field, "refs": refs or []}


def public_explanation(text: str | None) -> str | None:
    """Public decision summary, omitted when it contains unchecked figures, links or secrets."""
    if not text or len(text) > 400 or _SECRET.search(text) or _NUMBER_TEXT.search(text) or _INTERNAL_DETAILS.search(text):
        return None
    return text.strip() or None


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def final_issues(decision: dict[str, Any], *, products: dict[str, dict[str, Any]], fact: Callable[[str, str], Any],
                 plans: dict[str, dict[str, Any]], consent: bool, free_only: bool,
                 user_message: str = "", trip: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Vấn đề của quyết định respond.

    `products`: sản phẩm tra trong lượt (ref → sản phẩm); `fact(ref, field)`: giá trị server có, None khi không có;
    `plans`: lịch build_itinerary trả trong lượt (plan_result_id → kết quả); `consent`: khách đã đồng ý lập lịch.
    `trip`: ngữ cảnh chuyến sau patch của lượt; có thì lịch thay mới phải dùng đúng bốn trường bắt buộc trong đó.
    `user_message`: tin nhắn hiện tại của khách. Câu trả lời không nhắc sản phẩm/dữ kiện nào (vd. từ chối việc ngoài
    du lịch) được nhắc lại con số chính khách vừa viết; có sản phẩm thì không, để số khách nói không thành dữ kiện
    sản phẩm (NFR-REL-01).
    """
    issues = []
    seen: set[str] = set()
    per_taxonomy: Counter[str] = Counter()
    grounded = (any(segment["type"] != "text" for segment in decision["answer"])
                or any(decision["cards"].values()) or bool(decision["alternatives"]))
    said = "" if grounded else _compact(user_message)

    def unchecked_number(text: str) -> bool:
        return any(not said or _compact(match.group()) not in said for match in _NUMBER_TEXT.finditer(text))

    def check_public_text(text: str | None, field: str) -> None:
        if text and _INTERNAL_DETAILS.search(text):
            issues.append(_issue("INTERNAL_IMPLEMENTATION_DETAILS", field))

    check_public_text(decision.get("explanation"), "explanation")
    for index, suggestion in enumerate(decision["suggestions"]):
        check_public_text(suggestion["label"], f"suggestions.{index}.label")
    for index, alternative in enumerate(decision["alternatives"]):
        check_public_text(alternative["disclosure"], f"alternatives.{index}.disclosure")

    def card(ref: str, field: str, taxonomy: str | None = None) -> dict | None:
        if ref in seen:
            issues.append(_issue("DUPLICATE_CARD", field, [ref]))
        seen.add(ref)
        product = products.get(ref)
        if product is None:
            issues.append(_issue("UNGROUNDED_REF", field, [ref]))
        elif taxonomy and product["taxonomy"] != taxonomy:
            issues.append(_issue("TAXONOMY_MISMATCH", field, [ref]))
        else:
            per_taxonomy[product["taxonomy"]] += 1
        return product

    for taxonomy, refs in decision["cards"].items():
        for ref in refs:
            product = card(ref, "cards." + taxonomy, taxonomy)
            if product and free_only and taxonomy != "hotel" and taxonomy != "flight" and cost_mode(product) != "free":
                issues.append(_issue("NOT_FREE", "cards." + taxonomy, [ref]))
    for index, alternative in enumerate(decision["alternatives"]):
        product = card(alternative["product_ref"], f"alternatives.{index}")
        if product and free_only and cost_mode(product) != "free" and "free_only" not in alternative["violates"]:
            issues.append(_issue("UNDISCLOSED_NOT_FREE", f"alternatives.{index}", [alternative["product_ref"]]))
        plan = plans.get(alternative["plan_result_id"]) if alternative["plan_result_id"] else None
        if alternative["plan_result_id"] and (plan is None or plan["feasibility"] == "infeasible"):
            issues.append(_issue("INVALID_PLAN_RESULT", f"alternatives.{index}.plan_result_id"))
    for taxonomy, count in per_taxonomy.items():
        if count > MAX_CARDS_PER_TAXONOMY:
            issues.append(_issue("TAXONOMY_CARD_LIMIT", "cards." + taxonomy))

    for index, segment in enumerate(decision["answer"]):
        field = f"answer.{index}"
        if segment["type"] == "fact":
            if fact(segment["ref"], segment["field"]) is None:
                # Ghi rõ dữ kiện sai để orc sửa đúng chỗ (field không có, hoặc không phải một giá trị đơn).
                issues.append(_issue("UNSUPPORTED_FACT", field, [f'{segment["ref"]}.{segment["field"]}']))
            continue
        if segment["type"] == "product":
            if segment["ref"] not in products:
                issues.append(_issue("UNGROUNDED_REF", field, [segment["ref"]]))
            continue
        if _SECRET.search(segment["text"]):
            issues.append(_issue("SECRET_EXPOSURE", field))
        if unchecked_number(segment["text"]):
            issues.append(_issue("NUMBER_WITHOUT_FACT", field))
        if _BOOKING_CLAIM.search(segment["text"]):
            issues.append(_issue("FALSE_BOOKING_CLAIM", field))
        check_public_text(segment["text"], field)

    presented = seen | {segment["ref"] for segment in decision["answer"] if segment["type"] == "product"}
    assumed = [ref for ref in presented if ref in products and entry_mode(products[ref]) == "assumed_free"]
    if assumed and "FREE_ENTRY_ASSUMED" not in decision["disclosures"]:
        issues.append(_issue("MISSING_DISCLOSURE", "disclosures", sorted(assumed)))

    replace = decision["plan_effect"] == "replace"
    if replace != (decision["turn_kind"] == "itinerary"):
        issues.append(_issue("TURN_KIND_MISMATCH", "turn_kind"))
    if replace:
        plan = plans.get(decision["plan_result_id"] or "")
        if plan is None or plan["feasibility"] == "infeasible":
            issues.append(_issue("INVALID_PLAN_RESULT", "plan_result_id"))
        else:
            for warning in plan["warnings"]:
                if warning["code"] not in decision["disclosures"]:
                    code = "MISSING_BUDGET_DISCLOSURE" if warning["code"] == "OVER_TRIP_BUDGET" else "MISSING_DISCLOSURE"
                    issues.append(_issue(code, "disclosures", warning["refs"]))
            missing = unconfirmed_trip_fields(plan["draft"], trip) if trip is not None else []
            if missing:
                issues.append(_issue("TRIP_FIELD_UNCONFIRMED", "context_patch", missing))
        if not consent:
            issues.append(_issue("PLAN_CONSENT_REQUIRED", "plan_effect"))

    labels = [fold(suggestion["label"]) for suggestion in decision["suggestions"]]
    if len(set(labels)) < len(labels):
        issues.append(_issue("DUPLICATE_SUGGESTION", "suggestions"))
    return issues
