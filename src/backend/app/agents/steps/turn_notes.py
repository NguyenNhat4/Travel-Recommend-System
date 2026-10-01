"""Câu ngắn mô tả chuyến đi và từng lượt trợ lý theo nghĩa, dựng bằng luật từ state (không gọi LLM).

LLM đọc lại hội thoại qua các câu này thay vì nguyên văn: lịch trình dài kèm giá bị thay bằng
"gửi lịch trình Hà Nội 3 ngày: …", câu hỏi lại kèm lý do thật ("không dùng được điểm đến "biển": …").
Không có giá hay số tiền nào ở đây, để LLM không chép giá của lịch trình cũ thành ràng buộc mới.
"""
from __future__ import annotations

from .messages import display_date, message, money, party_text

#: Số tên sản phẩm tối đa trong ghi chú một lịch trình; đủ để người dùng nhắc lại "khách sạn đó", "tour kia".
MAX_NOTE_PRODUCTS = 8
INTENT_FIELDS = ("destination", "days", "startDate", "party", "budget")


def _field(state: dict, field: str) -> str:
    return message(state, f"change_field_{field}")


def _fields(state: dict, fields) -> str:
    return message(state, "detail_joiner").join(_field(state, field) for field in fields)


def _value(state: dict, field: str, value) -> str:
    if field == "startDate":
        return display_date(value)
    if field == "party":
        return party_text(state, value)
    if field == "budget":
        return money(value, state.get("language", "vi"))
    if field == "days":
        return message(state, "trip_days", days=value)
    return str(value)


def trip_summary(state: dict, intent: dict | None = None) -> str:
    """Chuyến đi đã biết trong một dòng, kèm các trường còn thiếu: "Hà Nội, 3 ngày; chưa có: ngày khởi hành, …"."""
    intent = intent if intent is not None else state.get("intent") or {}
    parts = []
    if intent.get("destination"):
        parts.append(intent["destination"])
    if intent.get("days"):
        parts.append(message(state, "trip_days", days=intent["days"]))
    if intent.get("startDate"):
        parts.append(message(state, "trip_from", date=display_date(intent["startDate"])))
    if intent.get("party"):
        parts.append(party_text(state, intent["party"]))
    if intent.get("budget") is not None:
        parts.append(message(state, "trip_budget", budget=money(intent["budget"], state.get("language", "vi"))))
    if intent.get("interests"):
        parts.append(message(state, "trip_interests", interests=", ".join(intent["interests"])))
    missing = [field for field in INTENT_FIELDS if intent.get(field) is None]
    if not parts:
        return message(state, "trip_none")
    text = ", ".join(parts)
    return f"{text}; {message(state, 'trip_missing', fields=_fields(state, missing))}" if missing else text


def stage(state: dict) -> str:
    """Hội thoại đang ở đâu: đã gửi lịch trình, đang hỏi thông tin, hay vừa bắt đầu."""
    if state.get("previous_selection"):
        return message(state, "stage_planned")
    if state.get("conversation_history"):
        return message(state, "stage_collecting")
    return message(state, "stage_start")


def _itinerary_names(itinerary: dict) -> list[str]:
    names = []
    stay = itinerary.get("stay")
    if stay and stay.get("product"):
        names.append(stay["product"]["name"])
    for day in itinerary.get("days", []):
        names.extend(slot["product"]["name"] for slot in day.get("slots", []) if slot.get("product"))
    return list(dict.fromkeys(names))[:MAX_NOTE_PRODUCTS]


def _invalid_parts(state: dict) -> list[str]:
    parts = []
    for item in state.get("invalid_inputs") or []:
        value = display_date(item["value"]) if item["field"] == "startDate" else item["value"]
        parts.append(message(state, "note_invalid", field=_field(state, item["field"]), value=value,
                             reason=message(state, f"note_reason_{item['reason']}")))
    return parts


def question_note(state: dict) -> str:
    """Lượt hỏi lại (`clarify`/`converse`): hỏi gì và vì sao, theo `clarification_reason` đã chốt ở `extract`."""
    if state.get("unclear_input"):
        return message(state, "note_unclear")
    if state.get("refusal"):
        return message(state, "note_refusal")
    if state.get("decision") == "constraint_clarification":
        return message(state, "note_constraint")
    reason = state.get("clarification_reason")
    missing = state.get("missing_fields") or []
    if reason == "invalid_input":
        parts = _invalid_parts(state)
        if missing:
            parts.append(message(state, "note_ask", fields=_fields(state, missing)))
        return "; ".join(parts)
    if reason == "change_without_value":
        intent = state.get("intent") or {}
        notes = [message(state, "note_change_current", field=_field(state, field),
                         current=_value(state, field, intent[field]))
                 if intent.get(field) is not None else message(state, "note_change", field=_field(state, field))
                 for field in missing]
        return "; ".join(notes)
    if reason == "destination_kind":
        return message(state, "note_kind", kind=state.get("destination_kind") or "")
    if reason == "suggest_form":
        return message(state, "note_form", fields=_fields(state, missing))
    if reason == "conflict":
        return message(state, "note_conflict")
    if reason == "unverified":
        return message(state, "note_unverified")
    if state.get("interaction_type") == "conversation" and not missing:
        return message(state, "note_chat")
    if missing:
        return message(state, "note_ask", fields=_fields(state, missing))
    return message(state, "note_chat")


def turn_note(state: dict, response: dict, http_status: int) -> str | None:
    """Ghi chú cho câu trả lời vừa chốt ở `finalize`; `None` với lỗi hệ thống (không có gì để nhắc lại)."""
    status = response.get("status")
    destination = (state.get("intent") or {}).get("destination") or ""
    if status == "COMPLETED":
        itinerary = response.get("itinerary") or {}
        return message(state, "note_itinerary", destination=destination,
                       days=(state.get("intent") or {}).get("days") or len(itinerary.get("days", [])),
                       products=", ".join(_itinerary_names(itinerary)))
    if status == "NO_RESULTS":
        return message(state, "note_no_results", destination=destination)
    if status == "FALLBACK":
        return message(state, "note_fallback", destination=destination)
    if status == "NEEDS_CLARIFICATION":
        if not state.get("missing_fields") and response.get("missingFields"):
            state = {**state, "missing_fields": response["missingFields"]}
        return question_note(state)
    if http_status == 400 and state.get("refusal"):
        return message(state, "note_refusal")
    return None
