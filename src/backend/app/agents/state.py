from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    """State passed between LangGraph nodes."""

    query: str
    context: str
    analysis: str
    response: str
    error: str
    metadata: dict
