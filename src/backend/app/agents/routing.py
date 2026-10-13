"""Conditional edges for the graph; at most one retry of a transient failure."""
from .state import AgentState
from .steps.option_swap import chosen_option


def route_after_intake(state: AgentState) -> str:
    """Bấm nút đổi khách sạn đi thẳng `apply_option`; còn lại qua luật đầu vào `precheck`."""
    if not state.get("response") and chosen_option(state) is not None:
        return "apply_option"
    return "precheck"


def route_after_precheck(state: AgentState) -> str:
    """Luật tất định đã quyết thì đi đúng nhánh; tin cần hiểu đi orchestrator.

    `converse`: câu cố định khi bị chặn · `tool`: đổi chuyến bay bằng luật (`steps/changes.py`), chuyến đi đã đủ thông
    tin nên tìm và lập lại lịch ngay · `run_jobs`: nút vé do code tạo.
    """
    return {"simple": "converse", "travel": "extract", "missing_info": "clarify", "tool": "tool",
            "error": "dead_letter", "orchestrate": "orchestrate",
            "run_jobs": "run_jobs"}.get(state.get("decision"), "dead_letter")


def route_after_extract(state: AgentState) -> str:
    """Chưa đồng ý lập lịch thì `extract` trả lượt cho `gatekeep` với lời mời (FR-AGT-06)."""
    return {"tool": "tool", "missing_info": "clarify", "error": "dead_letter",
            "gatekeep": "gatekeep"}.get(state.get("decision"), "dead_letter")


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


def route_after_orchestrate(state: AgentState) -> str:
    if state.get("decision") == "error":
        return "dead_letter"
    return state.get("decision") if state.get("decision") in ("extract", "run_jobs", "gatekeep") else "gatekeep"


def route_after_jobs(state: AgentState) -> str:
    return state["decision"] if state.get("decision") in ("gatekeep", "run_jobs") else "orchestrate"


def route_after_gatekeep(state: AgentState) -> str:
    return state.get("decision") if state.get("decision") in ("orchestrate", "run_jobs") else "finalize"
