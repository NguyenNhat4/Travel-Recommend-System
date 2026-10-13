"""Serializable itinerary state; runtime clients, models and credentials stay outside it."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from operator import add
from pydantic import BaseModel, Field

from src.backend.app.domain.itinerary.types import (
    Candidates, Constraints, DropSummary, PlanWarning, Product, Sources, ToolCall, ToolErrorPayload, ToolResult,
    TripIntent,
)


class LabEvent(BaseModel):
    """Append-only audit event for grading and debugging."""

    node: str
    event_type: str
    message: str
    latency_ms: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentState(TypedDict, total=False):
    """Current-turn data overwrites; `events` is the only append-only audit field.

    `decision` gộp ba cờ điều hướng cũ (`route`, `decision`, `evaluation_result`): mỗi node routing
    (`routing.py`) chỉ đọc giá trị node liền trước vừa ghi, nên gộp không mất thông tin — xem
    docs/spec/agent/state-fields.md.
    """

    query: str
    interaction_type: str
    attempt: int
    max_attempts: int
    final_answer: str | None
    tool_plan: list[ToolCall]
    tool_results: list[ToolResult]
    events: Annotated[list[dict[str, Any]], add]
    conversation_id: str
    conversation_history: list[dict[str, str]]
    intent: TripIntent
    previous_intent: TripIntent
    intent_override: TripIntent
    constraints: Constraints
    missing_fields: list[str]
    start_date_asked: bool
    clarification_rounds: int
    clarification_reason: str | None
    invalid_inputs: list[dict[str, Any]]
    refusal: bool
    blocked_by_guardrail: str | None
    unclear_input: str | None
    candidates: Candidates
    sources: Sources
    warnings: list[PlanWarning]
    nearest_open_date: str | None
    flight_options: dict[str, Any]  # `application/itinerary/flights.flight_options` của lượt này (AC-AGT-02)
    drop_summary: dict[str, DropSummary]
    # Mã điểm tham quan node `filter` bỏ vì trùng (`domain/itinerary/dedupe.apply_pairs`), AC-AGT-04 chốt 2026-10-08.
    dropped_duplicates: list[dict[str, Any]]
    response: dict[str, Any]  # `ItineraryResponse` envelope; contract-owned, see domain/itinerary/types.py
    http_status: int
    decision: str
    validation_issues: list[str]
    request_id: str
    started_at: float
    latency_ms: int
    details: dict[str, Product]
    detail_errors: dict[str, ToolErrorPayload]
    supported_destinations: list[str] | None
    destination_kind: str | None
    language: str
    previous_selection: list[Product]
    # Phương án khác của lịch lượt này (`composition._stay_options`) và của lịch đã hiện ở lượt trước, để "lấy phương
    # án N" biết khách sạn nào (AC-AGT-04, chốt 2026-10-08).
    stay_options: list[dict[str, Any]]
    previous_options: list[dict[str, Any]]
    # Lượt chọn phương án bằng hàng thẻ (contract 1.20.0 `selectStayOption`, chốt 2026-10-08): lựa chọn trong request,
    # lịch đang chọn của lượt này (`composition.composed`/`option_swap.swapped`) và của lượt trước. Mỗi phương án trong
    # `stay_options`/`previous_options` mang lịch đầy đủ (`itinerary`, `warnings`, `distanceKm`) để chọn không tìm lại.
    select_stay_option: dict[str, Any] | None
    current_plan: dict[str, Any] | None
    previous_plan: dict[str, Any] | None
    # Trò chuyện và khám phá trước khi lập lịch (FR-AGT-06, chốt 2026-10-10), lưu qua các lượt:
    # - `plan_consent`: người dùng đã xin hoặc đồng ý lập lịch; chưa đồng ý thì không hỏi thông tin chuyến, không form.
    # - `pending_offer`: lời mời lập lịch trợ lý vừa hỏi (`{"destination": ...}`), để "ok" lượt sau là đồng ý.
    # - `offered_destinations`: điểm đến đã được mời bằng câu; lượt khám phá sau chỉ giữ nút lập lịch.
    # - `dont_know_count`: số lần liên tiếp người dùng chưa biết đi đâu (bậc 1 hỏi kiểu chuyến, bậc 2 tự chọn).
    # - `last_suggestions`: nút gợi ý lượt trước, để lượt này không lặp.
    plan_consent: bool
    pending_offer: dict[str, Any] | None
    offered_destinations: list[str]
    dont_know_count: int
    last_suggestions: list[str]
    # - `rejected_destinations`: nơi người dùng đã chê ("chán, Đà Nẵng đi rồi"); không gợi ý lại trong hội thoại.
    rejected_destinations: list[str]
    # - `pending_fare`: lần hỏi lại của câu hỏi giá vé (`{"origin"|"destination": ...}`), để câu trả lời ngắn lượt sau
    #   ("Sài Gòn") điền đúng chỗ còn thiếu (kịch bản bản 5 cảnh 6).
    pending_fare: dict[str, Any] | None
    # - `skipped_details`: chi tiết không bắt buộc người dùng đã nói là không có ("không có ngân sách"); không hỏi lại.
    skipped_details: list[str]
    # - `shown`: sản phẩm đã cho xem trong hội thoại (thẻ khám phá, thẻ vé, sản phẩm của lịch), mỗi cái một mã `#n` kèm
    #   một dòng thông tin (`steps/shown.py`); `finalize` ghi từ response đã kiểm. Chỉ để nhớ, loại, so; không phải nguồn
    #   sản phẩm hay giá của response.
    shown: dict[str, Any]
    # Rollout-only conversational state; the disabled graph preserves its original checkpoint payload.
    orchestrator_active: bool
    waiting_jobs: list[dict[str, Any]]
    rejected_refs: list[str]
    orchestrator_turn: dict[str, Any]
    turn_jobs: list[dict[str, Any]]
    turn_codes: dict[str, str]
    turn_seq: int
    turn_pending: list[dict[str, Any]]
    turn_results: list[dict[str, Any]]
    turn_rounds: int
    turn_tool_calls: int
    turn_signatures: list[str]
    turn_unfinished: list[dict[str, Any]]
    turn_violations: list[str]
    force_answer: bool
    #: Mã phanh đầu tiên làm lượt phải trả lời sớm (`steps/limits.py`); chỉ trong lượt, không lưu.
    turn_limit_reason: str | None
    gate_repairs: int
    orchestrator_prefill: dict[str, Any] | None
    orchestrator_fare_ids: list[str]
    jobs_progress: bool
    turn_declines_offer: bool
    turn_stop: bool
    turn_plan_reason: str | None
    turn_plan_accepted: bool
    button_jobs: bool
    button_pending_jobs: list[dict[str, Any]]
    fare_question: bool
    # Chỉ trong lượt, code đối chiếu với catalog rồi mới dùng:
    # - `fare_ask`: câu hỏi vé máy bay (`models.FareQuestion`) của job vé hoặc của nút vé (`fares.chip_reply`).
    # - `other_questions`: câu hỏi khác trong cùng tin nhắn (orchestrator gửi khi chọn `plan`), thành nút gợi ý.
    fare_ask: dict[str, Any]
    other_questions: list[str]
    # - `form_request`: người dùng xin form để tự điền ("cho mình cái form"); lượt này luôn kèm form.
    form_request: bool
    # Đổi vé khi chưa nói đổi thế nào (kịch bản bản 5): chặng đã chọn kèm chuyến khác cùng ngày. `flight_choices` là của lịch
    # lượt này (`composition.composed`, None khi lượt này không dựng lịch), `previous_flights` là của lịch đang hiện.
    flight_choices: list[dict[str, Any]] | None
    previous_flights: list[dict[str, Any]]
    # Chỉ trong lượt: lượt đổi cần hỏi lại (`{"kind": "stay"|"flight", "directions": [...], "unmatched": ...}`).
    change_request: dict[str, Any] | None
    # Chỉ trong lượt này: `converse` thêm nút gợi ý vào câu "chưa hiểu" khi `precheck` chặn tin rác.
    offer_suggestions: bool


def make_event(node: str, event_type: str, message: str, **metadata: Any) -> dict[str, Any]:
    """Create a normalized event payload."""
    return LabEvent(node=node, event_type=event_type, message=message, metadata=metadata).model_dump()
