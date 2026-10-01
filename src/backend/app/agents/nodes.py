"""Mười hai node của graph itinerary — mỗi node một hàm, luật chi tiết nằm ở các module cạnh file này.

LLM chỉ đọc yêu cầu và viết câu chữ (`classify`, `extract`, `tool` khi khớp điểm đến, `clarify`, `converse`,
`narrate`); sản phẩm, giá và lịch trình đều do luật tất định dựng từ dữ liệu tool trả về. Mọi lượt gọi LLM nhận
cùng ngữ cảnh hội thoại (`steps/history.llm_context`).

Bảy node có thêm biến thể `_async` vì LangGraph cần cả hàm sync lẫn async cho cùng một node
(`graph.py` nối chúng qua `RunnableLambda(func, afunc=...)`); `tool` chỉ có bản async.

    intake → classify ─┬→ extract ─┬→ tool → evaluate ─┬→ compose → narrate ──┐
                       │           │                   ├→ retry ──────────────┤
                       │           ├→ clarify ─────────┤                      ├→ finalize → END
                       ├→ converse ┼───────────────────┤                      │
                       └→ dead_letter ←────────────────┴──────────────────────┘

Bảng tra cứu từng node: `docs/spec/agent/langgraph-nodes.md` §6; tên field: `docs/spec/agent/state-fields.md`.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import logging
from time import time
import uuid

from src.backend.app.application.itinerary.contracts import error_response
from src.backend.app.application.itinerary.retrieval import hydrate
from src.backend.app.application.ports.conversation_archive import ConversationArchivePort
from src.backend.app.application.ports.itinerary_tools import ConversationStorePort, ToolExecutorPort
from src.backend.app.domain.itinerary.normalization import normalize_intent
from src.backend.app.domain.itinerary.planning import empty_intent

from .steps import composition, conversation, evaluation, guardrails, messages, narration, tool_planning, validation
from .steps.classification import extract_result, extraction_input, route_input, route_result
from .steps.failures import terminal_failure
from .steps.history import append_conversation_turn, sanitize_conversation_history
from .steps.messages import chat_model, event, failure, message
from .models import ConversationalAnswer, Extraction, ItineraryNarration, TurnRoute
from .state import AgentState

logger = logging.getLogger("uvicorn.error")

MAX_ATTEMPTS = 2


def intake_node(state: AgentState) -> dict:
    """Khởi tạo state cho lượt này.

    Đọc: `query`/`message`, `conversation_id`, `conversation_history`, `intent`, `constraints`,
    `previous_selection`, `language`.
    Ghi: toàn bộ field của `AgentState` về giá trị đầu lượt, kể cả bộ đếm retry và mốc đo latency;
    `previous_intent` là bản chụp intent đầu lượt để `narrate` nêu được lượt này đổi gì.
    Đi tiếp: `classify`.
    """
    return {"query": state.get("query", state.get("message", "")).strip(),
            "conversation_id": state.get("conversation_id") or str(uuid.uuid4()),
            "conversation_history": sanitize_conversation_history(state.get("conversation_history", [])),
            "intent": deepcopy(state.get("intent") or empty_intent()),
            "previous_intent": deepcopy(state.get("intent") or empty_intent()),
            "constraints": deepcopy(state.get("constraints", {})),
            "previous_selection": deepcopy(state.get("previous_selection", [])),
            "attempt": 0,
            "max_attempts": min(max(1, state.get("max_attempts", MAX_ATTEMPTS)), MAX_ATTEMPTS),
            "tool_plan": [], "tool_results": [], "details": {}, "detail_errors": {},
            "supported_destinations": None,
            "candidates": {}, "sources": {}, "response": {}, "warnings": [],
            "missing_fields": [], "start_date_asked": bool(state.get("start_date_asked", False)),
            "clarification_rounds": int(state.get("clarification_rounds", 0) or 0),
            "invalid_inputs": [],
            "interaction_type": "", "refusal": False, "blocked_by_guardrail": None, "unclear_input": None,
            "final_answer": None, "http_status": 200, "decision": "", "validation_issues": [],
            "started_at": time(), "language": state.get("language") or "vi",
            "events": [event("intake", "request initialized")]}


async def intake_node_async(state: AgentState, *, store: ConversationStorePort | None = None,
                            owner: str = "anonymous", archive: ConversationArchivePort | None = None,
                            cdp_user_id: str | None = None) -> dict:
    """`intake` trên đường async: nạp intent/constraints/lịch sử đã lưu của hội thoại.

    Đọc thêm: bản ghi trong `ConversationStorePort` theo `conversation_id` và chủ sở hữu.
    Ghi thêm: intent/constraints/`previous_selection`/`conversation_history` của lượt trước,
    hoặc lỗi `CONVERSATION_NOT_FOUND` (404).
    """
    update = intake_node(state)
    if store is not None and state.get("conversation_id"):
        try:
            previous = await store.load(state["conversation_id"], owner)
        except Exception:
            logger.exception("itinerary.conversation_cache_load_failed requestId=%s",
                             state.get("request_id", "unknown"))
            previous = None
        if previous is None and archive is not None and cdp_user_id:
            try:
                previous = await archive.restore(state["conversation_id"], cdp_user_id)
                if previous is not None:
                    await store.save(state["conversation_id"], previous, owner)
            except Exception:
                logger.exception("itinerary.conversation_archive_restore_failed requestId=%s",
                                 state.get("request_id", "unknown"))
        if previous is None:
            update.update(failure(state, "CONVERSATION_NOT_FOUND", message(update, "conversation_not_found"), 404))
        else:
            update.update(intent=previous["intent"], previous_intent=deepcopy(previous["intent"]),
                          constraints=previous.get("constraints", {}),
                          start_date_asked=bool(previous.get("start_date_asked", False)),
                          clarification_rounds=int(previous.get("clarification_rounds", 0) or 0),
                          language=state.get("language") or previous.get("language", "vi"),
                          previous_selection=previous.get("previous_selection", []),
                          conversation_history=sanitize_conversation_history(
                              previous.get("conversation_history", [])))
    return update


def _travel_without_message(state: AgentState) -> dict | None:
    """Chip sửa tay (`intentOverride`, không có message) chắc chắn là lượt du lịch: không cần LLM phân luồng."""
    if not state.get("query") and state.get("intent_override"):
        return {"decision": "travel", "interaction_type": "travel", "refusal": False,
                "events": [event("classify", "route travel (intent override)")]}
    return None


def _guardrail_blocked_input(state: AgentState) -> dict | None:
    """Chèn lệnh/đòi secret khớp mẫu tất định: từ chối ngay, không tốn lượt gọi LLM nào (`classify` lẫn
    `converse` sau đó) và không đưa câu độc hại vào ngữ cảnh của một LLM lần nào nữa."""
    reason = guardrails.input_violation(state.get("query", ""))
    if reason is None:
        return None
    return {"decision": "simple", "interaction_type": "out_of_scope", "refusal": True,
            "missing_fields": [], "blocked_by_guardrail": reason,
            "events": [event("classify", "guardrail blocked input", pattern=reason)]}


def _guardrail_junk_input(state: AgentState) -> dict | None:
    """Tầng 1 (NFR-SEC-04): tin nhắn rác hiển nhiên không tốn lượt gọi LLM nào. Rác → `unclear_input`,
    `converse` trả câu "chưa hiểu" cố định; chỉ có tục tĩu → nhánh từ chối của guardrail (`blocked_by_guardrail`).
    Event chỉ ghi tên luật, không ghi câu người dùng."""
    verdict = guardrails.input_quality(state.get("query", ""))
    if verdict is None:
        return None
    kind, rule = verdict
    update = {"decision": "simple", "missing_fields": [],
              "events": [event("classify", "guardrail tier1", rule=rule)]}
    if kind == guardrails.ABUSIVE:
        return {**update, "interaction_type": "out_of_scope", "refusal": True,
                "blocked_by_guardrail": f"{kind}:{rule}"}
    return {**update, "interaction_type": "conversation", "refusal": False, "unclear_input": rule}


def _llm_failed(state: AgentState, node: str, mode: str, timeout_seconds: float | None = None) -> dict:
    logger.exception("itinerary.llm_failed requestId=%s node=%s mode=%s timeoutSeconds=%s",
                     state.get("request_id", "unknown"), node, mode, timeout_seconds)
    return {**failure(state, "LLM_UNAVAILABLE", message(state, "llm_understand"), retryable=True),
            "events": [event(node, "LLM_UNAVAILABLE")]}


def classify_node(state: AgentState, *, llm=None) -> dict:
    """Phân luồng lượt chat, không trích gì khác. **Gọi LLM** (prompt ngắn, output một nhãn).

    Đọc: `query` và ngữ cảnh hội thoại chung (`history.llm_context`).
    Ghi: `decision` (`travel`/`simple`/`error`), `interaction_type` (`travel`/`conversation`/`out_of_scope`), `refusal`, `missing_fields`.
    Đi tiếp (`routing.route_after_classify`): `extract` khi là du lịch · `converse` khi trò chuyện hoặc
    ngoài phạm vi (đặt chỗ, thanh toán, chèn lệnh đều là ngoài phạm vi) · `dead_letter` khi lỗi.
    """
    if state.get("decision") == "error":
        return {"events": [event("classify", "request rejected")]}
    shortcut = _travel_without_message(state)
    if shortcut is not None:
        return shortcut
    blocked = _guardrail_blocked_input(state) or _guardrail_junk_input(state)
    if blocked is not None:
        return blocked
    try:
        result = chat_model(llm).with_structured_output(TurnRoute).invoke(route_input(state))
        return route_result(state, result)
    except Exception:
        return _llm_failed(state, "classify", "sync")


async def classify_node_async(state: AgentState, *, llm=None, timeout_seconds: float = 2) -> dict:
    """`classify` trên đường async: LLM quá `timeout_seconds` thì coi như provider lỗi (`LLM_UNAVAILABLE`)."""
    if state.get("decision") == "error":
        return {"events": [event("classify", "request rejected")]}
    shortcut = _travel_without_message(state)
    if shortcut is not None:
        return shortcut
    blocked = _guardrail_blocked_input(state) or _guardrail_junk_input(state)
    if blocked is not None:
        return blocked
    try:
        result = await asyncio.wait_for(
            chat_model(llm).with_structured_output(TurnRoute).ainvoke(route_input(state)), timeout_seconds)
        return route_result(state, result)
    except Exception:
        return _llm_failed(state, "classify", "async", timeout_seconds)


def extract_node(state: AgentState, *, llm=None) -> dict:
    """Trích intent của lượt du lịch và quyết định còn thiếu gì. **Gọi LLM.**

    Đọc: `query`, ngữ cảnh hội thoại chung, `intent_override`, `start_date_asked`.
    Ghi: `intent`, `constraints`, `missing_fields`, `start_date_asked`, `clarification_reason`, `invalid_inputs`,
    `decision` (`tool`/`missing_info`/`error`). Ngày đi đã qua, số ngày/số người/ngân sách ngoài giới hạn bị xoá
    khỏi intent và hỏi lại (`clarification_reason = "invalid_input"`). Người dùng muốn đổi một trường mà chưa nói giá trị mới
    ('đổi ngày') thì LLM điền `change_without_value`: hỏi lại trường đó (`clarification_reason = "change_without_value"`), giữ intent cũ. Trên đường async, điểm đến ngoài catalog
    (ngoài Việt Nam) cũng bị xoá và hỏi lại ngay, kể cả khi còn thiếu số ngày; `supported_destinations` ghi sẵn cho `tool`.
    Đi tiếp (`routing.route_after_extract`): `tool` khi đủ điểm đến, số ngày và đã xử lý ngày đi ·
    `clarify` khi thiếu, mâu thuẫn hoặc có điều kiện không xác minh được · `dead_letter` khi lỗi.
    """
    try:
        result = chat_model(llm).with_structured_output(Extraction).invoke(extraction_input(state))
        return extract_result(state, result)
    except Exception:
        return _llm_failed(state, "extract", "sync")


async def extract_node_async(state: AgentState, *, llm=None, timeout_seconds: float = 2,
                             tools: ToolExecutorPort | None = None, tool_timeout_seconds: float = 1) -> dict:
    """`extract` trên đường async: LLM quá `timeout_seconds` thì coi như provider lỗi (`LLM_UNAVAILABLE`).

    Có `tools` thì kiểm điểm đến với catalog ngay sau khi trích (chỉ phục vụ Việt Nam, xem `check_destination`).
    """
    try:
        result = await asyncio.wait_for(
            chat_model(llm).with_structured_output(Extraction).ainvoke(extraction_input(state)), timeout_seconds)
        update = extract_result(state, result)
    except Exception:
        return _llm_failed(state, "extract", "async", timeout_seconds)
    return await tool_planning.check_destination(state, update, tools=tools, timeout_seconds=tool_timeout_seconds,
                                                 llm=llm, llm_timeout_seconds=timeout_seconds)


async def tool_node(state: AgentState, *, tools: ToolExecutorPort | None = None,
                    timeout_seconds: float = 1, llm=None, require_recommendations: bool = False,
                    llm_timeout_seconds: float = 2) -> dict:
    """Chuẩn hóa điểm đến, lập tool plan rồi gọi Search/Recommendation. **Có thể gọi LLM.**

    Đọc: `intent`, `constraints`, `conversation_history`, `tool_plan` (lần retry), `tool_results`
    và `details` của lần trước.
    Ghi: `intent`/`constraints` đã chuẩn hóa, `supported_destinations`, `tool_plan`, `tool_results`,
    `details`, `detail_errors`; điểm đến ngoài catalog thì xoá điểm đến khỏi intent, ghi `invalid_inputs` và
    `decision = "invalid_input"` (hỏi lại qua `clarify`).
    Đi tiếp: `evaluate` — kể cả khi mọi lời gọi đều lỗi, vì `evaluate` mới phân loại tạm thời/vĩnh viễn.
    """
    intent, constraints, changed = normalize_intent(state.get("intent", {}), state.get("constraints", {}))
    supported = state.get("supported_destinations")
    if intent.get("destination") and supported is None and getattr(tools, "supports_catalog", False):
        supported = await tool_planning.catalog_destinations(tools, timeout_seconds)
    if supported is not None and intent.get("destination"):
        rejected = await tool_planning.canonical_destination(state, intent, changed, supported,
                                                             llm, llm_timeout_seconds)
        if rejected is not None:
            return {**rejected, "supported_destinations": supported}
    plan, plan_error = await tool_planning.build_plan(
        state, intent, constraints, tools=tools, llm=llm, llm_timeout_seconds=llm_timeout_seconds,
        require_recommendations=require_recommendations)
    if plan_error is not None:
        return plan_error
    results = await tool_planning.run_calls(state, plan, tools, timeout_seconds)
    details, detail_errors = await hydrate(results, tools, state.get("details", {}), timeout_seconds)
    return {"tool_plan": plan, "tool_results": results, "details": details, "detail_errors": detail_errors,
            "intent": intent, "constraints": constraints, "supported_destinations": supported,
            "events": [event("tool", "retrieval completed" + (f" (normalized {', '.join(changed)})" if changed else ""),
                             calls=len(results), detail_errors=len(detail_errors), changed=changed)]}


def evaluate_node(state: AgentState) -> dict:
    """Lọc candidate có grounding và quyết định hướng xử lý. **Không gọi LLM.**

    Đọc: `tool_results`, `detail_errors`, `intent`, `constraints`.
    Ghi: `candidates`, `sources`, `warnings`, `decision` (`compose`/`no_results`/`fallback`/`constraint_clarification`/
    `needs_retry`/`failed`), `details={}` (đã tiêu thụ). Vertical mà Recommendation
    bỏ chỉ lọc candidate của lượt này, không ghi vào `constraints`.
    Đi tiếp (`routing.route_after_evaluate`): `compose` · `clarify` khi `constraint_clarification` ·
    `retry` khi lỗi tạm thời · `dead_letter` khi lỗi vĩnh viễn hoặc lỗi auth.
    """
    if state.get("decision") == "error":
        return {"events": [event("evaluate", "request rejected")]}
    if state.get("decision") == "invalid_input":  # `tool` đã từ chối điểm đến: chưa có gì để chấm
        return {"events": [event("evaluate", "invalid input")]}
    update = evaluation.evaluate_retrieval(state)
    if "candidates" not in update:  # chưa có điểm đến thì chưa có gì để chấm
        return {**update, "events": [event("evaluate", update["decision"])]}
    return {**update, "events": [event("evaluate", update["decision"], verified=len(update["candidates"]))]}


def ask_clarification_node(state: AgentState, *, llm=None) -> dict:
    """Ask for what a trip still lacks; the model words the question, fixed text is the fallback.

    Đọc: `conversation_history`, `missing_fields`, `clarification_reason`, `invalid_inputs`, `decision`, `intent`.
    Ghi: `response` `NEEDS_CLARIFICATION` kèm `knownIntent` (và `missingFields` nếu có).
    Đi tiếp: `finalize`. Riêng `decision = constraint_clarification` dùng câu cố định, không hỏi LLM.
    """
    if state.get("decision") == "constraint_clarification":
        return conversation.clarify_result(conversation.constraint_clarification(state))
    try:
        result = chat_model(llm).with_structured_output(ConversationalAnswer).invoke(
            conversation.conversation_input(state))
        update = conversation.conversational_update(state, result)
    except Exception:
        logger.exception("itinerary.llm_failed requestId=%s node=clarify mode=sync",
                         state.get("request_id", "unknown"))
        update = conversation.clarification_fallback(state)
    return conversation.clarify_result(update)


async def ask_clarification_node_async(state: AgentState, *, llm=None, timeout_seconds: float = 3) -> dict:
    """`clarify` trên đường async: LLM lỗi hoặc quá `timeout_seconds` thì dùng câu cố định theo đúng lý do."""
    if state.get("decision") == "constraint_clarification":
        return conversation.clarify_result(conversation.constraint_clarification(state))
    try:
        result = await asyncio.wait_for(
            chat_model(llm).with_structured_output(ConversationalAnswer).ainvoke(
                conversation.conversation_input(state)), timeout_seconds)
        update = conversation.conversational_update(state, result)
    except Exception:
        logger.exception("itinerary.llm_failed requestId=%s node=clarify mode=async timeoutSeconds=%s",
                         state.get("request_id", "unknown"), timeout_seconds)
        update = conversation.clarification_fallback(state)
    return conversation.clarify_result(update)


def converse_node(state: AgentState, *, llm=None) -> dict:
    """Reply to chit-chat and refusals. No product has been retrieved at this point.

    Đọc: `query`, `conversation_history`, `interaction_type`, `refusal`, `intent`, `missing_fields`.
    Ghi: `response` `NEEDS_CLARIFICATION`, hoặc `VALIDATION_ERROR` (400) khi yêu cầu ngoài phạm vi.
    Đi tiếp: `finalize`. `blocked_by_guardrail` (từ `classify`) thì dùng câu từ chối cố định, `unclear_input`
    (tin nhắn rác, tầng 1) thì dùng câu "chưa hiểu" cố định — cả hai không gọi LLM.
    """
    if state.get("blocked_by_guardrail"):
        update = conversation.conversational_fallback(state)
        return {**update, "events": [event("converse", "guardrail blocked input, skipped LLM",
                                            pattern=state["blocked_by_guardrail"])]}
    if state.get("unclear_input"):
        return {**conversation.unclear_input_reply(state),
                "events": [event("converse", "unclear input, skipped LLM", rule=state["unclear_input"])]}
    try:
        result = chat_model(llm).with_structured_output(ConversationalAnswer).invoke(
            conversation.conversation_input(state))
        update = conversation.conversational_update(state, result)
    except Exception:
        logger.exception("itinerary.llm_failed requestId=%s node=converse mode=sync",
                         state.get("request_id", "unknown"))
        update = conversation.conversational_fallback(state)
    return {**update, "events": [event("converse", "response drafted")]}


async def converse_node_async(state: AgentState, *, llm=None, timeout_seconds: float = 3) -> dict:
    """`converse` trên đường async: LLM lỗi hoặc quá `timeout_seconds` thì trả lời bằng câu cố định."""
    if state.get("blocked_by_guardrail"):
        update = conversation.conversational_fallback(state)
        return {**update, "events": [event("converse", "guardrail blocked input, skipped LLM",
                                            pattern=state["blocked_by_guardrail"])]}
    if state.get("unclear_input"):
        return {**conversation.unclear_input_reply(state),
                "events": [event("converse", "unclear input, skipped LLM", rule=state["unclear_input"])]}
    try:
        result = await asyncio.wait_for(
            chat_model(llm).with_structured_output(ConversationalAnswer).ainvoke(
                conversation.conversation_input(state)), timeout_seconds)
        update = conversation.conversational_update(state, result)
    except Exception:
        logger.exception("itinerary.llm_failed requestId=%s node=converse mode=async timeoutSeconds=%s",
                         state.get("request_id", "unknown"), timeout_seconds)
        update = conversation.conversational_fallback(state)
    return {**update, "events": [event("converse", "response drafted")]}


def compose_node(state: AgentState) -> dict:
    """Turn retrieved products into a reply. Pure computation: no model, so no async variant.

    Đọc: `decision`, `candidates`, `sources`, `intent`, `constraints`, `warnings`.
    Ghi: `response` `COMPLETED` (lịch trình dựng bằng `compose_plan`), hoặc `NO_RESULTS`/`FALLBACK`.
    Đi tiếp: `narrate`.
    """
    update = composition.retrieval_outcome(state) or composition.compose_or_fallback(state)
    completed = update.get("response", {}).get("status") == "COMPLETED"
    return {**update, "events": [event("compose", "itinerary composed by rules" if completed
                                       else "no itinerary composed")]}


def _narration_skipped(state: AgentState) -> dict | None:
    if state.get("response", {}).get("status") != "COMPLETED":
        return {"events": [event("narrate", "skipped (no itinerary)")]}
    return None


def _narration_update(state: AgentState, result: ItineraryNarration | None) -> dict:
    update, reason = narration.narrated(state, result)
    return {**update, "events": [event("narrate", "itinerary narrated" if reason == "llm"
                                       else "narration fallback by rules", reason=reason)]}


def narrate_node(state: AgentState, *, llm=None) -> dict:
    """Viết lời diễn giải cho lịch trình `COMPLETED` như một người lập kế hoạch du lịch. **Gọi LLM.**

    Đọc: `response` (lịch trình đã dựng), `intent`, `previous_intent`, ngữ cảnh hội thoại chung, `language`.
    Ghi: `response.message` (dòng đầu `**Tiêu đề**`, câu ghi nhận thay đổi do backend chèn, sản phẩm là link
    `[Tên](product:id)` với tên canonical, giá điền từ dữ liệu) và `response.itinerary.title`. Status khác
    `COMPLETED` đi qua nguyên vẹn. LLM lỗi, quá giờ hoặc viết id lạ/số tiền tự đặt thì dùng `narration.fallback_message`.
    Đi tiếp: `finalize`.
    """
    skipped = _narration_skipped(state)
    if skipped is not None:
        return skipped
    try:
        result = chat_model(llm).with_structured_output(ItineraryNarration).invoke(narration.narration_input(state))
    except Exception:
        logger.exception("itinerary.llm_failed requestId=%s node=narrate mode=sync", state.get("request_id", "unknown"))
        result = None
    return _narration_update(state, result)


async def narrate_node_async(state: AgentState, *, llm=None, timeout_seconds: float = 3) -> dict:
    """`narrate` trên đường async: LLM lỗi hoặc quá `timeout_seconds` thì dùng bản dựng bằng luật."""
    skipped = _narration_skipped(state)
    if skipped is not None:
        return skipped
    try:
        result = await asyncio.wait_for(
            chat_model(llm).with_structured_output(ItineraryNarration).ainvoke(narration.narration_input(state)),
            timeout_seconds)
    except Exception:
        logger.exception("itinerary.llm_failed requestId=%s node=narrate mode=async timeoutSeconds=%s",
                         state.get("request_id", "unknown"), timeout_seconds)
        result = None
    return _narration_update(state, result)


def retry_or_fallback_node(state: AgentState) -> dict:
    """Quyết định thử lại lượt truy xuất, tối đa một lần. **Không gọi LLM.**

    Đọc: `attempt`, `max_attempts`, `candidates`.
    Ghi: `attempt` tăng khi còn lượt, `decision` (`""` để thử lại, `fallback` hoặc `error`).
    Đi tiếp (`routing.route_after_retry`): `tool`, `compose` hoặc `dead_letter`.
    """
    attempt = state.get("attempt", 0)
    can_retry = attempt < min(state.get("max_attempts", MAX_ATTEMPTS), MAX_ATTEMPTS) - 1
    decision = "" if can_retry else "fallback" if state.get("candidates") else "error"
    if can_retry:
        attempt += 1
    return {"attempt": attempt, "decision": decision,
            "events": [event("retry", "retry bounded", attempt=attempt)]}


def dead_letter_node(state: AgentState) -> dict:
    """Kết thúc có kiểm soát khi không còn đường đi tiếp. **Không gọi LLM.**

    Đọc: `response` (lỗi đã có từ node trước), `tool_results`, `detail_errors`.
    Ghi: `ErrorResponse` chuẩn — lỗi auth (401), `LLM_UNAVAILABLE` khi không lập nổi plan,
    còn lại `SEARCH_UNAVAILABLE`. Không che lỗi thành thành công.
    Đi tiếp: `finalize`.
    """
    if state.get("response", {}).get("error"):
        return {"events": [event("dead_letter", "request rejected")]}
    return {**terminal_failure(state), "events": [event("dead_letter", "controlled failure")]}


def finalize_node(state: AgentState) -> dict:
    """Chốt chặn cuối cho mọi nhánh: validate response theo contract và grounding. **Không gọi LLM.**

    Đọc: `response`, `http_status`, `candidates`, `sources`, `intent`, `constraints`,
    `conversation_history`, `query`, `started_at`.
    Ghi: `response` đã kiểm, `http_status`, `validation_issues`, `final_answer`,
    `conversation_history`, `latency_ms`.
    Sai schema hoặc lệch grounding (kể cả link sản phẩm trong `message` của `COMPLETED`) thì thay bằng
    `ITINERARY_VALIDATION_FAILED` (500). Câu chữ LLM tự viết (`question`/`error.message`/`message` của `COMPLETED`)
    lộ secret hoặc tuyên bố đã đặt/đã thanh toán thì thay bằng câu cố định (`guardrails.output_violations`;
    `COMPLETED` dùng `narration.fallback_message`), giữ nguyên `status`/`http_status`.
    Đi tiếp: `END`.
    """
    response = deepcopy(state.get("response", {}))
    http_status = state.get("http_status", 200)
    issues = validation.response_issues(state, response, http_status)
    guardrail_issues: list[str] = []
    if issues:
        response = error_response("ITINERARY_VALIDATION_FAILED", messages.VALIDATION_FAILED,
                                  state.get("request_id", ""))
        http_status = 500
    else:
        guardrail_issues = guardrails.output_violations(response)
        if guardrail_issues and response.get("status") == "COMPLETED":
            # Lịch trình vẫn đúng; chỉ lời diễn giải bị thay bằng bản dựng bằng luật.
            response["message"] = narration.fallback_message(state, response)
        elif guardrail_issues:
            # Câu chữ do luật tất định soạn lại, đúng theo `refusal` đã ghi lúc trước — không gọi LLM lần nữa.
            response = conversation.conversational_fallback(state).get("response", response)
    all_issues = issues + [f"guardrail:{reason}" for reason in guardrail_issues]
    answer = validation.answer_text(response)
    history = append_conversation_turn(state.get("conversation_history", []), state.get("query", ""), answer)
    outcome = "validation failed" if issues else "guardrail output filtered" if guardrail_issues else "response validated"
    return {"response": response, "http_status": http_status, "validation_issues": all_issues,
            "final_answer": answer, "conversation_history": history,
            "latency_ms": max(0, int((time() - state.get("started_at", time())) * 1000)),
            "events": [event("finalize", outcome, issues=all_issues)]}


async def finalize_node_async(state: AgentState, *, store: ConversationStorePort | None = None,
                              owner: str = "anonymous", archive: ConversationArchivePort | None = None,
                              cdp_user_id: str | None = None) -> dict:
    """`finalize` trên đường async: lưu hội thoại để lượt sau nối tiếp được.

    Ghi thêm (qua `ConversationStorePort`): intent, constraints, lịch sử user/assistant đã giới hạn,
    ngôn ngữ và các sản phẩm đã hiển thị.
    Điểm đến ngoài catalog là câu hỏi lại (200) với `intent.destination = None`, nên phần còn lại của chuyến đi
    được lưu như mọi lượt hỏi lại khác.
    """
    update = finalize_node(state)
    if store is not None and update["http_status"] == 200:
        intent = state["intent"]
        response = update["response"]
        selection = (validation.selection_snapshot(response) if response.get("status") == "COMPLETED"
                     else state.get("previous_selection", []))
        working_state = {"intent": intent,
                         "constraints": state.get("constraints", {}),
                         "start_date_asked": state.get("start_date_asked", False),
                         "clarification_rounds": state.get("clarification_rounds", 0),
                         "conversation_history": update["conversation_history"],
                         "language": state.get("language", "vi"),
                         "previous_selection": selection}
        await store.save(state["conversation_id"], working_state, owner)
        if archive is not None and cdp_user_id:
            try:
                await archive.record_turn(state["conversation_id"], cdp_user_id, {
                    "request_id": state.get("request_id", "unknown"),
                    "query": state.get("query", ""),
                    "answer": update["final_answer"],
                    "response": update["response"],
                    "intent": intent,
                    "working_state": working_state,
                })
            except Exception:
                # Archive là best-effort: lỗi DB không được biến một lượt chat hợp lệ thành 500.
                logger.exception("itinerary.conversation_archive_write_failed requestId=%s",
                                 state.get("request_id", "unknown"))
    return update
