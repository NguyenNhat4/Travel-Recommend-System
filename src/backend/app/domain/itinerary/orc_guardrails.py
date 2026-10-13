"""Kiểm câu trả lời orc đề xuất (assistant v2) trước khi hiển thị; không chọn, thêm hay cắt sản phẩm.

Mỗi vấn đề là `{"code", "field", "refs"}`. Mã thuộc `FATAL` dừng lượt ngay; mã khác trả về cho orc sửa (một lần).
Vượt ngân sách không phải vấn đề: chỉ cần công bố cảnh báo (PRD architecture §3, AC-AGT-04/06/07).
"""
from __future__ import annotations

from collections import Counter
import re
from typing import Any, Callable

from .draft_validation import cost_mode
from .normalization import fold

FATAL = {"SECRET_EXPOSURE"}
MAX_CARDS_PER_TAXONOMY = 10
#: Số tiền, giờ hay link viết thẳng trong lời văn: phải đi qua đoạn fact để số đúng dữ liệu (NFR-REL-01).
_NUMBER_TEXT = re.compile(
    r"\d[\d.,]*\s*(?:vnd|vnđ|đ\b|₫|đồng|k\b|nghìn|ngàn|tr\b|triệu|tỷ|usd|\$|km\b)|\b\d{1,3}(?:[.,]\d{3})+\b"
    r"|\b\d{1,2}[:h]\d{2}\b|https?://|/product/",
    re.IGNORECASE)
_BOOKING_CLAIM = re.compile(r"đã đặt|đã thanh toán|đặt thành công|booking confirmed", re.IGNORECASE)
_SECRET = re.compile(r"sk-[a-zA-Z0-9]{10,}|bearer\s+[a-zA-Z0-9._-]{10,}|AIzaSy[a-zA-Z0-9_-]{10,}", re.IGNORECASE)


def _issue(code: str, field: str, refs: list[str] | None = None) -> dict[str, Any]:
    return {"code": code, "field": field, "refs": refs or []}


def final_issues(decision: dict[str, Any], *, products: dict[str, dict[str, Any]], fact: Callable[[str, str], Any],
                 plans: dict[str, dict[str, Any]], consent: bool, free_only: bool) -> list[dict[str, Any]]:
    """Vấn đề của quyết định respond.

    `products`: sản phẩm tra trong lượt (ref → sản phẩm); `fact(ref, field)`: giá trị server có, None khi không có;
    `plans`: lịch build_itinerary trả trong lượt (plan_result_id → kết quả); `consent`: khách đã đồng ý lập lịch.
    """
    issues = []
    seen: set[str] = set()
    per_taxonomy: Counter[str] = Counter()

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
        if _NUMBER_TEXT.search(segment["text"]):
            issues.append(_issue("NUMBER_WITHOUT_FACT", field))
        if _BOOKING_CLAIM.search(segment["text"]):
            issues.append(_issue("FALSE_BOOKING_CLAIM", field))

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
        if not consent:
            issues.append(_issue("PLAN_CONSENT_REQUIRED", "plan_effect"))

    labels = [fold(suggestion["label"]) for suggestion in decision["suggestions"]]
    if len(set(labels)) < len(labels):
        issues.append(_issue("DUPLICATE_SUGGESTION", "suggestions"))
    return issues
