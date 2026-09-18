"""Conditional edges for the graph; at most one retry of a transient failure."""
from .state import AgentState


def route_after_classify(state: AgentState) -> str:
    return {"simple": "answer", "tool": "tool", "missing_info": "clarify",
            "error": "dead_letter"}.get(state.get("route"), "dead_letter")


def route_after_evaluate(state: AgentState) -> str:
    return {"needs_retry": "retry", "failed": "dead_letter"}.get(state.get("evaluation_result"), "answer")


def route_after_retry(state: AgentState) -> str:
    if state.get("decision") == "fallback" and state.get("candidates"):
        return "answer"
    if state.get("decision") == "error":
        return "dead_letter"
    return "tool" if state.get("attempt", 0) < min(state.get("max_attempts", 2), 2) else "dead_letter"
