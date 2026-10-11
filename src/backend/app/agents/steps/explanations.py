"""Câu nêu lý do khi một loại sản phẩm không còn candidate nào (`drop_summary` của `evaluate`).

Dùng ở hai chỗ: `clarify` khi điều kiện bắt buộc (khách sạn, khách sạn/hoạt động cụ thể) không có sản phẩm nào đáp
ứng, và `compose`/`narrate` khi lịch trình dựng được nhưng không có chỗ ở. Câu dựng tất định từ kết quả tool của
lượt đó (số sản phẩm, cửa sổ mở bán, ngày gần nhất), không gọi LLM, nên lý do luôn đúng dữ liệu (NFR-REL-01).
"""
from __future__ import annotations

from datetime import date, timedelta

from src.backend.app.domain.itinerary.planning import SLOT_TAXONOMIES, STAY_TAXONOMY

from . import messages
from .messages import display_date, money, titled

MAX_SUGGESTIONS = 3
#: Lý do đã có câu riêng; `PRICE_BASIS` (thiếu giá hoặc sai đơn vị giá) nói chung với `PRICE`.
REASONS = {"DATE", "PRICE", "ATTRIBUTES", "NAMED_REQUIREMENT", "UNAVAILABLE"}


def _reason(entry: dict) -> str | None:
    """Mã ngắn của lý do phổ biến nhất; None khi đã tìm mà không thấy sản phẩm nào (`count = 0`)."""
    if not entry.get("count"):
        return None
    code = (entry.get("reason") or "").removeprefix("PRODUCT_DROPPED_")
    return "PRICE" if code == "PRICE_BASIS" else code


def _trip_dates(intent: dict) -> tuple[str, str]:
    """Ngày đi và ngày về (dd/mm/yyyy) của chuyến; rỗng khi chưa có ngày đi."""
    if not intent.get("startDate"):
        return "", ""
    end = date.fromisoformat(intent["startDate"]) + timedelta(days=max(1, intent.get("days") or 1) - 1)
    return display_date(intent["startDate"]), display_date(end.isoformat())


def unmet_taxonomy(state: dict) -> str | None:
    """Loại sản phẩm của điều kiện bắt buộc chưa đáp ứng, theo đúng thứ tự kiểm của `evaluation._decision`."""
    constraints = state.get("constraints", {})
    present = {product.get("taxonomy") for product in state.get("candidates", {}).values()}
    if (constraints.get("require_hotel") or constraints.get("specific_hotel")) and STAY_TAXONOMY not in present:
        return STAY_TAXONOMY
    if constraints.get("specific_activity") and not present & SLOT_TAXONOMIES:
        summary = state.get("drop_summary") or {}
        found = [taxonomy for taxonomy in sorted(SLOT_TAXONOMIES) if taxonomy in summary]
        return max(found, key=lambda taxonomy: summary[taxonomy].get("count", 0)) if found else None
    return None


def constraint_question(state: dict) -> tuple[str, list[str]] | None:
    """(`question`, `suggestions`) cho điều kiện bắt buộc không có sản phẩm; None khi không biết lý do."""
    taxonomy = unmet_taxonomy(state)
    entry = (state.get("drop_summary") or {}).get(taxonomy) if taxonomy else None
    if entry is None:
        return None
    reason = _reason(entry)
    if reason is not None and reason not in REASONS:
        return None
    intent, constraints = state.get("intent", {}), state.get("constraints", {})
    destination = intent.get("destination") or ""
    noun = messages.message(state, "noun_hotel" if taxonomy == STAY_TAXONOMY else "noun_activity")
    start, end = _trip_dates(intent)
    named = constraints.get("specific_hotel") if taxonomy == STAY_TAXONOMY else constraints.get("specific_activity")
    price = constraints.get("hotel_price_max")
    values = {"noun": noun, "noun_cap": noun[:1].upper() + noun[1:], "destination": destination,
              "count": entry.get("count", 0), "name": named or "", "start": start, "end": end,
              "price": money(price, state.get("language", "vi")) if price is not None else ""}
    nearest = entry.get("nearestOpenDate")
    if reason is None:
        body, ask = messages.message(state, "unmet_none", **values), "unmet_ask_other"
    elif reason == "DATE":
        if entry.get("openFrom") and entry.get("openTo") and start:
            body = messages.message(state, "unmet_DATE", open_from=display_date(entry["openFrom"]),
                                    open_to=display_date(entry["openTo"]), **values)
        else:
            body = messages.message(state, "unmet_DATE_no_window", **values)
        ask = "unmet_ask_date" if nearest else "unmet_ask_other"
    else:
        body = messages.message(state, f"unmet_{reason}", **values)
        ask = "unmet_ask_other" if reason == "UNAVAILABLE" else "unmet_ask_relax"
    question = messages.message(state, ask, nearest=display_date(nearest) if nearest else "", **values)
    title = messages.message(state, f"unmet_title_{reason or 'none'}", **values)
    return titled(title, f"{body} {question}"), _suggestions(state, taxonomy, reason, nearest)


def _suggestions(state: dict, taxonomy: str, reason: str | None, nearest: str | None) -> list[str]:
    """Câu gửi được nguyên văn, mọi giá trị từ dữ liệu của lượt này: ngày gần nhất, nới yêu cầu, bỏ khách sạn."""
    intent, constraints = state.get("intent", {}), state.get("constraints", {})
    destination, days = intent.get("destination"), intent.get("days") or 1
    suggestions = []
    if reason == "DATE" and nearest:
        suggestions.append(messages.message(state, "suggestion_change_date", date=display_date(nearest)))
    if reason == "PRICE":
        suggestions.append(messages.message(state, "suggestion_price"))
    if reason == "ATTRIBUTES" and constraints.get("star_rating_min") is not None:
        suggestions.append(messages.message(state, "suggestion_star_rating"))
    if reason == "NAMED_REQUIREMENT":
        suggestions.append(messages.message(state, "suggestion_hotel" if taxonomy == STAY_TAXONOMY
                                            else "suggestion_activity"))
    if taxonomy == STAY_TAXONOMY and destination:
        suggestions.append(messages.message(state, "suggestion_no_stay", destination=destination, days=days))
    return suggestions[:MAX_SUGGESTIONS]


def missing_stay_note(state: dict, plan: dict) -> str | None:
    """Câu nói vì sao lịch trình không có chỗ ở; None khi đã có chỗ ở, chuyến một ngày hoặc không tìm khách sạn."""
    if (plan.get("stay") or {}).get("product") or (state.get("intent", {}).get("days") or 1) < 2:
        return None
    entry = (state.get("drop_summary") or {}).get(STAY_TAXONOMY)
    if entry is None:
        return None
    intent = state.get("intent", {})
    destination = intent.get("destination") or ""
    # Ngày đi chung của cả lịch (có vé, khách sạn, vé tham quan) thắng ngày gần nhất chỉ có khách sạn.
    reason, nearest = _reason(entry), state.get("joint_date") or entry.get("nearestOpenDate")
    start, _ = _trip_dates(intent)
    if reason is None:
        return messages.message(state, "no_stay_none", destination=destination)
    if reason == "DATE" and entry.get("openFrom") and entry.get("openTo") and start:
        note = messages.message(state, "no_stay_DATE", destination=destination, start=start,
                                open_from=display_date(entry["openFrom"]), open_to=display_date(entry["openTo"]))
    else:
        note = messages.message(state, "no_stay_other", destination=destination)
    if reason == "DATE" and nearest:
        note += " " + messages.message(state, "no_stay_nearest", nearest=display_date(nearest))
    return note
