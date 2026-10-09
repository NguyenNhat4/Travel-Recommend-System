"""Conditional edges for the graph; at most one retry of a transient failure."""
from .state import AgentState
from .steps.option_swap import chosen_option


def route_after_intake(state: AgentState) -> str:
    """Chọn đúng một phương án đã hiện ở lượt trước thì đổi lịch ngay; còn lại (kể cả intake lỗi) đi `classify`."""
    if not state.get("response") and chosen_option(state) is not None:
        return "apply_option"
    return "classify"


def route_after_classify(state: AgentState) -> str:
    return {"simple": "converse", "travel": "extract", "missing_info": "clarify",
            "error": "dead_letter"}.get(state.get("decision"), "dead_letter")


def route_after_extract(state: AgentState) -> str:
    return {"tool": "tool", "missing_info": "clarify", "error": "dead_letter"}.get(state.get("decision"), "dead_letter")


def route_after_evaluate(state: AgentState) -> str:
    decision = state.get("decision")
    if decision in {"constraint_clarification", "invalid_input"}:
        return "clarify"
    return {"needs_retry": "retry", "failed": "dead_letter", "error": "dead_letter"}.get(decision, "filter")


def route_after_retry(state: AgentState) -> str:
    if state.get("decision") == "fallback" and state.get("candidates"):
        return "filter"
    if state.get("decision") == "error":
        return "dead_letter"
    return "tool" if state.get("attempt", 0) < min(state.get("max_attempts", 2), 2) else "dead_letter"
