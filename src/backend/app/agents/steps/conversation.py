"""Hai node dùng LLM để viết câu chữ: `clarify` (hỏi thiếu thông tin) và `converse` (chat/từ chối)."""
from __future__ import annotations

from copy import deepcopy
import json

from src.backend.app.domain.itinerary.planning import empty_intent

from ..models import ConversationalAnswer
from . import messages
from .classification import vietnam_today
from .history import llm_context
from .messages import event, failure, message
from .prompts import CONVERSATION_PROMPT

#: Form gợi ý phủ mọi trường bắt buộc của chuyến đi, kể cả trường người dùng đã nói, để sửa được tại chỗ.
FORM_FIELDS = ("destination", "days", "startDate", "party", "budget")
#: Số ngày điền sẵn; người dùng chỉnh ngay trên form (giới hạn 1–7 lấy từ contract).
DEFAULT_FORM_DAYS = 1
DEFAULT_FORM_PARTY = {"type": None, "adults": 2, "children": 0}


def clarification_form(state: dict) -> dict:
    """Form đã điền sẵn gợi ý, gửi kèm khi hỏi bằng câu chữ một lượt vẫn chưa đủ thông tin.

    Giá trị người dùng đã nói luôn thắng giá trị gợi ý. `destination` để `None` khi hội thoại chưa từng
    gọi tool (chưa có danh sách catalog); frontend tự nạp danh sách điểm đến cho ô chọn.
    """
    today = vietnam_today().isoformat()
    known = {key: value for key, value in (state.get("intent") or {}).items() if value is not None}
    defaults = {**empty_intent(), **deepcopy(known)}
    if defaults.get("days") is None:
        defaults["days"] = DEFAULT_FORM_DAYS
    if not defaults.get("startDate") or defaults["startDate"] < today:
        defaults["startDate"] = today
    if defaults.get("party") is None:
        defaults["party"] = deepcopy(DEFAULT_FORM_PARTY)
    if defaults.get("destination") is None:
        supported = state.get("supported_destinations") or []
        defaults["destination"] = supported[0] if supported else None
    return {"fields": list(FORM_FIELDS), "defaults": defaults, "startDateMin": today}


def conversation_input(state: dict) -> list:
    """Chỉ gửi ngữ cảnh đã chốt cho LLM; nó viết câu chữ, không được tự quyết luồng."""
    language = "Vietnamese" if state.get("language", "vi") == "vi" else "English"
    payload = {"message": state.get("query", ""), **llm_context(state),
               "interaction_type": state.get("interaction_type", ""),
               "missing_fields": state.get("missing_fields", []),
               "clarification_reason": state.get("clarification_reason"),
               "refusal": bool(state.get("refusal"))}
    return [("system", CONVERSATION_PROMPT + f"\nReply in {language}."),
            ("human", json.dumps(payload, ensure_ascii=False))]


def _question_response(state: dict, question: str) -> dict:
    response = {"status": "NEEDS_CLARIFICATION", "conversationId": state["conversation_id"],
                "question": question, "knownIntent": state["intent"]}
    missing = state.get("missing_fields")
    if missing:
        response["missingFields"] = missing
    suggested = {}
    if "destination" in (missing or []) and state.get("supported_destinations"):
        suggested["destination"] = state["supported_destinations"]
    if "days" in (missing or []):
        suggested["days"] = list(range(1, 8))
    if suggested:
        response["suggestedValues"] = suggested
    # Lượt hỏi đầu dùng câu chữ; hỏi rồi mà vẫn thiếu điểm đến/số ngày thì đưa form thay vì hỏi lại y hệt.
    if state.get("clarification_rounds", 0) >= 2 and {"destination", "days"} & set(missing or []):
        response["clarificationForm"] = clarification_form(state)
    return {"response": response}


def conversational_update(state: dict, result: ConversationalAnswer) -> dict:
    """Câu LLM viết ra; yêu cầu ngoài phạm vi thì trả lỗi 400 thay vì câu hỏi."""
    text = ConversationalAnswer.model_validate(result).message.strip()
    if state.get("refusal"):
        return failure(state, "VALIDATION_ERROR", text, 400)
    return _question_response(state, text)


def clarification_fallback(state: dict) -> dict:
    """Fixed-wording question used when the model is unavailable, and for checks the model must not phrase."""
    missing = state.get("missing_fields", [])
    reason = state.get("clarification_reason")
    if reason == "suggest_form":
        question = message(state, "suggest_form")
    elif reason == "conflict":
        question = messages.CLARIFY_CONFLICT
    elif reason == "unverified":
        question = messages.CLARIFY_UNVERIFIED
    elif missing and set(missing) <= {"startDate", "party", "budget"}:
        details = message(state, "detail_joiner").join(message(state, f"detail_{key}") for key in missing)
        question = message(state, "missing_trip_details", details=details)
    elif len(missing) == 2:
        question = message(state, "missing_both")
    elif "destination" in missing:
        question = message(state, "missing_destination")
    else:
        question = message(state, "missing_days")
    return _question_response(state, question)


def conversational_fallback(state: dict) -> dict:
    """Bản dự phòng cho `converse`: từ chối thì trả lỗi cố định, còn lại hỏi như `clarify`."""
    if state.get("refusal"):
        return failure(state, "VALIDATION_ERROR", messages.REFUSAL, 400)
    return clarification_fallback(state)


def constraint_clarification(state: dict) -> dict:
    """Retrieval finished but no product meets a required condition; ask before relaxing it."""
    question = messages.CLARIFY_CONSTRAINT
    return {"response": {"status": "NEEDS_CLARIFICATION", "conversationId": state["conversation_id"],
                         "knownIntent": state["intent"], "question": question}}


def clarify_result(update: dict) -> dict:
    """Câu hỏi đã soạn cũng là `final_answer` của lượt này."""
    return {**update, "final_answer": update["response"]["question"],
            "events": [event("clarify", "clarification requested")]}
