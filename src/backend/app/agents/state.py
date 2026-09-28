"""Serializable itinerary state; runtime clients, models and credentials stay outside it."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, TypedDict

from operator import add
from pydantic import BaseModel, Field, field_validator


class Route(StrEnum):
    SIMPLE = "simple"
    TOOL = "tool"
    MISSING_INFO = "missing_info"
    ERROR = "error"
    DEAD_LETTER = "dead_letter"
    DONE = "done"


class LabEvent(BaseModel):
    """Append-only audit event for grading and debugging."""

    node: str
    event_type: str
    message: str
    latency_ms: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)




class AgentState(TypedDict, total=False):
    """Current-turn data overwrites; events/messages/errors are append-only audit fields."""

    thread_id: str
    scenario_id: str
    query: str
    interaction_type: str
    route: str
    attempt: int
    max_attempts: int
    evaluation_result: str | None
    pending_question: str | None
    final_answer: str | None
    messages: Annotated[list[str], add]
    tool_plan: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    errors: Annotated[list[str], add]
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
    llm_used: bool
    details: dict[str, dict[str, Any]]
    detail_errors: dict[str, dict[str, Any]]
    supported_destinations: list[str] | None
    language: str
    previous_selection: list[dict[str, Any]]


class Scenario(BaseModel):
    id: str
    query: str
    expected_route: Route
    should_retry: bool = False
    max_attempts: int = 3
    tags: list[str] = Field(default_factory=list)

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty")
        return value


def initial_state(scenario: Scenario) -> AgentState:
    """Create a serializable initial state for one scenario."""
    return {
        "thread_id": f"thread-{scenario.id}",
        "scenario_id": scenario.id,
        "query": scenario.query,
        "route": "",
        "attempt": 0,
        "max_attempts": scenario.max_attempts,
        "evaluation_result": None,
        "pending_question": None,
        "final_answer": None,
        "messages": [],
        "tool_results": [],
        "errors": [],
        "events": [],
    }


def make_event(node: str, event_type: str, message: str, **metadata: Any) -> dict[str, Any]:
    """Create a normalized event payload."""
    return LabEvent(node=node, event_type=event_type, message=message, metadata=metadata).model_dump()
