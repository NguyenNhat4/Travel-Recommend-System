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


def make_event(node: str, event_type: str, message: str, **metadata: Any) -> dict[str, Any]:
    """Create a normalized event payload."""
    return LabEvent(node=node, event_type=event_type, message=message, metadata=metadata).model_dump()
