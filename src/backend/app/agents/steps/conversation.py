"""Hai node dùng LLM để viết câu chữ: `clarify` (hỏi thiếu thông tin) và `converse` (chat/từ chối)."""
from __future__ import annotations

import json

from ..models import ConversationalAnswer
from . import messages
from .history import llm_context
from .messages import event, failure, message
from .prompts import CONVERSATION_PROMPT


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
    if reason == "conflict":
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
