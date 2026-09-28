"""Serializable itinerary state; runtime clients, models and credentials stay outside it."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from operator import add
from pydantic import BaseModel, Field


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
    tool_plan: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    events: Annotated[list[dict[str, Any]], add]
    conversation_id: str
    conversation_history: list[dict[str, str]]
    intent: dict[str, Any]
    intent_override: dict[str, Any]
    constraints: dict[str, Any]
    missing_fields: list[str]
    start_date_asked: bool
    clarification_reason: str | None
    refusal: bool
    candidates: dict[str, dict[str, Any]]
    sources: dict[str, dict[str, Any]]
    warnings: list[dict[str, Any]]
    response: dict[str, Any]
    http_status: int
    decision: str
    validation_issues: list[str]
    request_id: str
    started_at: float
    latency_ms: int
    details: dict[str, dict[str, Any]]
    detail_errors: dict[str, dict[str, Any]]
    supported_destinations: list[str] | None
    language: str
    previous_selection: list[dict[str, Any]]


def make_event(node: str, event_type: str, message: str, **metadata: Any) -> dict[str, Any]:
    """Create a normalized event payload."""
    return LabEvent(node=node, event_type=event_type, message=message, metadata=metadata).model_dump()
