"""Hai node dùng LLM để viết câu chữ: `clarify` (hỏi thiếu thông tin) và `converse` (chat/từ chối)."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from src.backend.app.application.itinerary.contracts import bounds
from src.backend.app.domain.itinerary import preferences
from src.backend.app.domain.itinerary.planning import empty_intent

from ..models import ConversationalAnswer
from . import exploration, messages
from .classification import TRIP_DETAILS, vietnam_today
from .explanations import constraint_question
from .history import llm_context, prompt_yaml
from .messages import display_date, event, failure, message, titled
from .prompts import CONVERSATION_PROMPT
from .turn_notes import question_note

#: Form gợi ý phủ mọi trường bắt buộc của chuyến đi, kể cả trường người dùng đã nói, để sửa được tại chỗ.
FORM_FIELDS = ("destination", "days", "startDate", "party", "budget", "origin")
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
    defaults["interests"] = _form_interests(defaults)
    return {"fields": [*FORM_FIELDS, "interests"], "defaults": defaults, "startDateMin": today,
            "interestOptions": preferences.labels()}


def _form_interests(intent: dict) -> list[str]:
    """Ô sở thích tích sẵn (FR-AGT-06): sở thích khách sạn đã nói, và "Phù hợp trẻ nhỏ" khi đoàn có trẻ em. Sở thích khác
    (điểm tham quan) giữ nguyên trong `interests` để câu xác nhận không làm mất."""
    interests = [value for value in intent.get("interests") or [] if isinstance(value, str)]
    wanted = {item.key for item in preferences.from_interests(interests)}
    if ((intent.get("party") or {}).get("children") or 0) > 0:
        wanted.add("familyFriendly")
    others = [value for value in interests if not preferences.is_preference(value)]
    return [*others, *(item.label for item in preferences.PREFERENCES if item.key in wanted)]


def _valid_ranges() -> dict:
    """Giới hạn hợp lệ theo contract, đưa cho LLM để nó nêu đúng con số."""
    return {"days": dict(zip(("min", "max"), bounds("TripIntent", "days"))),
            "adults_min": bounds("Party", "adults")[0], "children_min": bounds("Party", "children")[0],
            "budget_min": bounds("TripIntent", "budget")[0]}


def _invalid_for_llm(state: dict) -> list[dict]:
    """`invalid_inputs` với ngày đã định dạng dd/mm/yyyy sẵn: LLM chỉ chép lại, không tự đổi định dạng."""
    return [{**item, "value": display_date(item["value"]) if item["field"] == "startDate" else item["value"]}
            for item in state.get("invalid_inputs", [])]


def _form_shown(state: dict) -> bool:
    """Câu hỏi kèm `clarificationForm`: đã hỏi một lượt mà vẫn thiếu trường bắt buộc (`suggest_form`), hoặc giá trị
    không hợp lệ ở lượt đã hỏi một lần mà vẫn thiếu điểm đến/số ngày.

    Không kèm khi đang hỏi chọn điểm đến theo loại ("đi biển"): form điền sẵn điểm đến đầu catalog, có thể không hợp loại.
    """
    reason = state.get("clarification_reason")
    if reason == "destination_kind":
        return False
    if reason == "suggest_form":
        return True
    return state.get("clarification_rounds", 0) >= 2 and bool({"destination", "days"} & set(state.get("missing_fields") or []))


def invalid_title(state: dict) -> str:
    """Dòng tiêu đề in đậm dự phòng khi LLM không đặt `title`."""
    items = state.get("invalid_inputs", [])
    key = f"invalid_title_{items[0]['reason']}" if len(items) == 1 else "invalid_title_many"
    return message(state, key)


def reply_title(state: dict) -> str | None:
    """Tiêu đề cố định của câu hỏi/từ chối này, theo lý do và phần còn thiếu; `None` với chào hỏi, cảm ơn.

    Dùng khi LLM không đặt `title` hoặc không viết được câu (câu dự phòng luôn có tiêu đề cùng dạng).
    """
    if state.get("interaction_type") == "conversation":
        return None
    reason = state.get("clarification_reason")
    if reason == "invalid_input":
        return invalid_title(state)
    if reason == "change_without_value":
        return message(state, "title_change_without_value")
    if reason == "destination_kind":
        return message(state, "title_destination_kind")
    if reason in {"suggest_form", "conflict", "unverified"}:
        return message(state, {"suggest_form": "title_form", "conflict": "title_conflict",
                               "unverified": "title_unverified"}[reason])
    if state.get("refusal"):
        return message(state, "title_out_of_scope")
    missing = state.get("missing_fields", [])
    if missing and set(missing) <= set(TRIP_DETAILS):
        return message(state, "title_trip_details")
    if _days_and_details(missing):
        return message(state, "title_days_and_details")
    if {"destination", "days"} <= set(missing):
        return message(state, "title_missing_both")
    if "destination" in missing:
        return message(state, "title_missing_destination")
    return message(state, "title_missing_days")


def conversation_input(state: dict) -> list:
    """Chỉ gửi ngữ cảnh đã chốt cho LLM; nó viết câu chữ, không được tự quyết luồng."""
    language = "Vietnamese" if state.get("language", "vi") == "vi" else "English"
    payload = {"message": state.get("query", ""), **llm_context(state),
               # Lượt này hỏi gì và vì sao (đã chốt ở `extract`), để câu trả lời không mượn lý do cũ trong lịch sử.
               "this_turn": question_note(state),
               "interaction_type": state.get("interaction_type", ""),
               "missing_fields": state.get("missing_fields", []),
               "clarification_reason": state.get("clarification_reason"),
               "refusal": bool(state.get("refusal")),
               # Trước khi đồng ý lập lịch (FR-AGT-06): không hỏi thông tin chuyến; bậc "không biết"; nút gợi ý.
               "plan_consent": bool(state.get("plan_consent")),
               "pending_offer": state.get("pending_offer"),
               "dont_know_level": int(state.get("dont_know_count", 0) or 0),
               "catalog_destinations": (state.get("supported_destinations") or [])[:exploration.CATALOG_HINT],
               "previous_suggestions": state.get("last_suggestions", []),
               "rejected_destinations": state.get("rejected_destinations", [])}
    if state.get("clarification_reason") == "invalid_input":
        payload.update(invalid_inputs=_invalid_for_llm(state), today=display_date(vietnam_today().isoformat()),
                       valid_ranges=_valid_ranges(), form_shown=_form_shown(state),
                       supported_destinations=state.get("supported_destinations") or [])
    elif state.get("clarification_reason") == "destination_kind":
        payload.update(destination_kind=state.get("destination_kind"),
                       supported_destinations=state.get("supported_destinations") or [])
    elif state.get("clarification_reason") == "change_without_value":
        # Để LLM đoán năm khi hỏi xác nhận một câu trả lời chưa đọc được ("1410" → "14/10/2026?").
        payload["today"] = display_date(vietnam_today().isoformat())
    return [("system", CONVERSATION_PROMPT + f"\nReply in {language}."),
            ("human", prompt_yaml(payload))]


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
    if _form_shown(state):
        response["clarificationForm"] = clarification_form(state)
        if "startDate" in (missing or []):
            response["suggestions"] = date_suggestions(state)
    return {"response": response}


def date_suggestions(state: dict) -> list[str]:
    """Nút chọn nhanh ngày đi dưới form (kịch bản bản 5, cảnh 8): người dùng bấm thay cho điền ô ngày; câu trên nút là lời
    người dùng ("Thứ 7 này (17/10)"), `extract` đọc được ngày tương đối như mọi câu chat."""
    today = vietnam_today()
    saturday = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
    return [message(state, "chip_date_this_saturday", date=display_date(saturday.isoformat())[:5]),
            message(state, "chip_date_next_saturday", date=display_date((saturday + timedelta(days=7)).isoformat())[:5])]


def with_suggestions(state: dict, update: dict, proposed: list[str] | None = None) -> dict:
    """Gắn nút gợi ý vào câu trả lời của lượt trò chuyện (FR-AGT-06): nút LLM đề xuất qua kiểm, thiếu thì nút mẫu."""
    response = update.get("response") or {}
    if not state.get("offer_suggestions") or response.get("status") != "NEEDS_CLARIFICATION":
        return update
    supported = state.get("supported_destinations") or []
    suggestions = exploration.checked_suggestions(proposed or [], state.get("last_suggestions", []),
                                                  exploration.conversation_templates(state, supported),
                                                  destinations=supported, avoid=state.get("rejected_destinations"))
    if not suggestions:
        return update
    return {**update, "response": {**response, "suggestions": suggestions}}


def conversational_update(state: dict, result: ConversationalAnswer) -> dict:
    """Câu LLM viết ra. Yêu cầu ngoài phạm vi (đặt vé hộ, chuyện ngoài du lịch) là câu trả lời thường 200 kèm nút, không
    còn là lỗi 400 (FR-AGT-06, chốt 2026-10-10); chỉ đầu vào bị guardrail chặn mới bị từ chối bằng lỗi."""
    answer = ConversationalAnswer.model_validate(result)
    if state.get("explore_place") and not state.get("blocked_by_guardrail") and not state.get("refusal"):
        # Hỏi về một nơi cụ thể mà không tra ra nơi đó trong catalog: `converse` không có dữ liệu nơi đó, câu LLM viết
        # có thể tự nói giờ, giá ("Văn Miếu không mở buổi tối" — sai, chat thử M03). Thay bằng câu cố định, giữ nút.
        answer = answer.model_copy(update={"title": message(state, "title_unverified_fact"),
                                           "message": message(state, "unverified_fact",
                                                              place=state["explore_place"])})
    fallback_title = reply_title(state)
    # Dòng đầu in đậm do backend ghép, để mọi câu trả lời có cùng một dạng; chào hỏi, cảm ơn thì không có tiêu đề.
    text = titled(answer.title or fallback_title, answer.message.strip()) if fallback_title else answer.message.strip()
    if state.get("blocked_by_guardrail"):
        return failure(state, "VALIDATION_ERROR", text, 400)
    return with_suggestions(state, _question_response(state, text), answer.suggestions)


def _invalid_input_question(state: dict) -> str:
    """Phần thân câu cố định: mỗi giá trị sai một dòng lý do, rồi phần còn thiếu (tiêu đề do `titled` thêm)."""
    items = state.get("invalid_inputs", [])
    today = display_date(vietnam_today().isoformat())
    lines = [message(state, f"invalid_reason_{item['reason']}", today=today, min_adults=bounds("Party", "adults")[0],
                     destinations=", ".join(state.get("supported_destinations") or []),
                     value=display_date(item["value"]) if item["field"] == "startDate" else item["value"])
             for item in items]
    covered = {item["field"] for item in items}
    rest = [key for key in state.get("missing_fields", []) if key not in covered]
    if {"destination", "days"} <= set(rest):
        lines.append(message(state, "missing_both"))
    elif "destination" in rest:
        lines.append(message(state, "missing_destination"))
    elif "days" in rest:
        lines.append(message(state, "missing_days"))
    details = [key for key in rest if key in TRIP_DETAILS]
    if details:
        joined = message(state, "detail_joiner").join(message(state, f"detail_{key}") for key in details)
        lines.append(message(state, "missing_trip_details", details=joined))
    return "\n".join(lines)


def _days_and_details(missing: list[str]) -> bool:
    """Hỏi gộp số ngày cùng chi tiết chuyến (ngày đi, số người…) trong một câu (AC-AGT-01, kịch bản cảnh 7)."""
    return "days" in missing and len(missing) > 1 and set(missing) - {"days"} <= set(TRIP_DETAILS)


def clarification_fallback(state: dict) -> dict:
    """Fixed-wording question used when the model is unavailable, and for checks the model must not phrase."""
    missing = state.get("missing_fields", [])
    reason = state.get("clarification_reason")
    if reason == "invalid_input":
        question = _invalid_input_question(state)
    elif reason == "change_without_value":
        fields = message(state, "detail_joiner").join(message(state, f"change_field_{key}") for key in missing)
        question = message(state, "change_without_value", fields=fields)
    elif reason == "destination_kind":
        # Không liệt kê điểm đến: luật không biết nơi nào hợp loại ("biển"), chỉ LLM chọn được từ danh sách.
        question = message(state, "destination_kind", kind=state.get("destination_kind") or "")
    elif reason == "suggest_form":
        question = message(state, "suggest_form")
    elif reason == "conflict":
        question = messages.CLARIFY_CONFLICT
    elif reason == "unverified":
        question = messages.CLARIFY_UNVERIFIED
    elif missing and set(missing) <= set(TRIP_DETAILS):
        details = message(state, "detail_joiner").join(message(state, f"detail_{key}") for key in missing)
        question = message(state, "missing_trip_details", details=details)
    elif _days_and_details(missing):
        details = message(state, "detail_joiner").join(message(state, f"detail_{key}") for key in missing
                                                       if key != "days")
        question = message(state, "missing_days_and_details", details=details)
    elif len(missing) == 2:
        question = message(state, "missing_both")
    elif "destination" in missing:
        question = message(state, "missing_destination")
    else:
        question = message(state, "missing_days")
    title = reply_title(state)
    return _question_response(state, titled(title, question) if title else question)


def conversational_fallback(state: dict) -> dict:
    """Bản dự phòng cho `converse`: đầu vào bị guardrail chặn thì trả lỗi cố định; ngoài phạm vi thì câu cố định 200
    kèm nút; còn lại hỏi như `clarify`."""
    if state.get("blocked_by_guardrail"):
        return failure(state, "VALIDATION_ERROR", messages.REFUSAL_BLOCKED, 400)
    if state.get("refusal"):
        return with_suggestions(state, {"response": {"status": "NEEDS_CLARIFICATION",
                                                     "conversationId": state["conversation_id"],
                                                     "question": messages.REFUSAL, "knownIntent": state["intent"]}})
    return with_suggestions(state, clarification_fallback(state))


def unclear_input_reply(state: dict) -> dict:
    """Tin nhắn rác (guardrail tầng 1): hỏi lại bằng câu cố định, 200, không có `missingFields`."""
    return {"response": {"status": "NEEDS_CLARIFICATION", "conversationId": state["conversation_id"],
                         "question": messages.UNCLEAR_INPUT, "knownIntent": state["intent"]}}


def constraint_clarification(state: dict) -> dict:
    """Retrieval finished but no product meets a required condition; ask before relaxing it.

    Câu cố định nêu lý do thật lấy từ `drop_summary` (sai ngày, vượt giá, không có tên đó...) kèm chip gợi ý;
    không biết lý do thì dùng câu chung `CLARIFY_CONSTRAINT`.
    """
    explained = constraint_question(state)
    question, suggestions = explained if explained else (messages.CLARIFY_CONSTRAINT, [])
    response = {"status": "NEEDS_CLARIFICATION", "conversationId": state["conversation_id"],
                "knownIntent": state["intent"], "question": question}
    if suggestions:
        response["suggestions"] = suggestions
    return {"response": response}


def clarify_result(update: dict) -> dict:
    """Câu hỏi đã soạn cũng là `final_answer` của lượt này."""
    return {**update, "final_answer": update["response"]["question"],
            "events": [event("clarify", "clarification requested")]}
