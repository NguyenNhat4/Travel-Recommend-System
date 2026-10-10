"""Compile the fifteen-node itinerary graph with request-scoped runtime dependencies."""

from __future__ import annotations

import inspect
from functools import partial, wraps
from time import perf_counter
from typing import Any

from src.backend.app.application.ports.itinerary_tools import ConversationStorePort, ToolExecutorPort
from src.backend.app.application.ports.conversation_archive import ConversationArchivePort

from .state import AgentState


def _stamp_latency(update: Any, started: float) -> Any:
    """Ghi thời gian chạy của node vào các event nó vừa trả; event đã tự đo thì giữ nguyên."""
    if not isinstance(update, dict) or not update.get("events"):
        return update
    elapsed_ms = max(1, round((perf_counter() - started) * 1000))
    events = [item if item.get("latency_ms") else {**item, "latency_ms": elapsed_ms}
              for item in update["events"]]
    return {**update, "events": events}


def timed(node):
    """Bọc node (sync hoặc async) để `LabEvent.latency_ms` là thời gian chạy thật của node đó."""
    if inspect.iscoroutinefunction(node):
        @wraps(node)
        async def run_async(state):
            started = perf_counter()
            return _stamp_latency(await node(state), started)
        return run_async

    @wraps(node)
    def run_sync(state):
        started = perf_counter()
        return _stamp_latency(node(state), started)
    return run_sync


def build_graph(checkpointer: Any | None = None, *, tools: ToolExecutorPort | None = None,
                tool_timeout_seconds: float = 1.0, llm: Any | None = None,
                store: ConversationStorePort | None = None, owner: str = "anonymous",
                archive: ConversationArchivePort | None = None, cdp_user_id: str | None = None,
                require_recommendations: bool = False, llm_timeout_seconds: float | None = None):
    """Build the lab topology with injected API tools; execute API tools using ainvoke.

    Runtime clients and JWT are captured in the tool node, never checkpointed.
    tool_timeout_seconds limits each API call; transient calls retry at most once.
    """
    if tool_timeout_seconds <= 0:
        raise ValueError("tool_timeout_seconds must be positive")
    if llm_timeout_seconds is not None and llm_timeout_seconds <= 0:
        raise ValueError("llm_timeout_seconds must be positive")
    from langgraph.graph import END, START, StateGraph
    from langchain_core.runnables import RunnableLambda

    from .nodes import (
        ask_clarification_node,
        ask_clarification_node_async,
        classify_node,
        classify_node_async,
        extract_node,
        extract_node_async,
        apply_option_node,
        compose_node,
        converse_node,
        converse_node_async,
        dead_letter_node,
        evaluate_node,
        explore_node,
        explore_node_async,
        filter_node,
        filter_node_async,
        finalize_node,
        finalize_node_async,
        intake_node,
        intake_node_async,
        narrate_node,
        narrate_node_async,
        retry_or_fallback_node,
        tool_node,
    )
    from .routing import (
        route_after_classify,
        route_after_evaluate,
        route_after_explore,
        route_after_extract,
        route_after_intake,
        route_after_retry,
    )

    # `partial` objects carry no __name__, so nodes built from one are named explicitly;
    # otherwise their trace run shows up as the generic "RunnableLambda".
    async def run_local(state, *, node):
        # CPU-only nodes do not need a worker thread on the async path.
        return node(state)

    graph = StateGraph(AgentState)
    for name, node in {
        "evaluate": evaluate_node, "compose": compose_node, "apply_option": apply_option_node,
        "retry": retry_or_fallback_node, "dead_letter": dead_letter_node,
    }.items():
        graph.add_node(name, RunnableLambda(timed(node), afunc=timed(partial(run_local, node=node))))
    graph.add_node("intake", RunnableLambda(timed(intake_node), afunc=timed(partial(
        intake_node_async, store=store, owner=owner, archive=archive, cdp_user_id=cdp_user_id))))
    graph.add_node("finalize", RunnableLambda(timed(finalize_node), afunc=timed(partial(
        finalize_node_async, store=store, owner=owner, archive=archive, cdp_user_id=cdp_user_id))))
    graph.add_node("classify", RunnableLambda(timed(partial(classify_node, llm=llm)), afunc=timed(partial(classify_node_async, llm=llm, timeout_seconds=llm_timeout_seconds if llm_timeout_seconds is not None else 2)), name="classify_node"))
    graph.add_node("extract", RunnableLambda(timed(partial(extract_node, llm=llm)), afunc=timed(partial(extract_node_async, llm=llm, timeout_seconds=llm_timeout_seconds if llm_timeout_seconds is not None else 2, tools=tools, tool_timeout_seconds=tool_timeout_seconds)), name="extract_node"))
    graph.add_node("converse", RunnableLambda(timed(partial(converse_node, llm=llm)), afunc=timed(partial(converse_node_async, llm=llm, timeout_seconds=llm_timeout_seconds if llm_timeout_seconds is not None else 3, tools=tools, tool_timeout_seconds=tool_timeout_seconds)), name="converse_node"))
    # Khám phá trước khi lập lịch (FR-AGT-06, chốt 2026-10-10): Search theo điểm đến, thẻ chọn bằng luật, LLM viết lời dẫn.
    graph.add_node("explore", RunnableLambda(timed(partial(explore_node, llm=llm)), afunc=timed(partial(explore_node_async, llm=llm, timeout_seconds=llm_timeout_seconds if llm_timeout_seconds is not None else 3, tools=tools, tool_timeout_seconds=tool_timeout_seconds)), name="explore_node"))
    graph.add_node("clarify", RunnableLambda(timed(partial(ask_clarification_node, llm=llm)), afunc=timed(partial(ask_clarification_node_async, llm=llm, timeout_seconds=llm_timeout_seconds if llm_timeout_seconds is not None else 3)), name="ask_clarification_node"))
    graph.add_node("filter", RunnableLambda(timed(partial(filter_node, llm=llm)), afunc=timed(partial(filter_node_async, llm=llm, timeout_seconds=llm_timeout_seconds if llm_timeout_seconds is not None else 2)), name="filter_node"))
    graph.add_node("narrate", RunnableLambda(timed(partial(narrate_node, llm=llm)), afunc=timed(partial(narrate_node_async, llm=llm, timeout_seconds=llm_timeout_seconds if llm_timeout_seconds is not None else 3)), name="narrate_node"))
    graph.add_node("tool", timed(partial(tool_node, tools=tools, timeout_seconds=tool_timeout_seconds,
                                   llm=llm, require_recommendations=require_recommendations,
                                   llm_timeout_seconds=llm_timeout_seconds if llm_timeout_seconds is not None else 2)))

    graph.add_edge(START, "intake")
    # Chọn một phương án đã hiện (hàng thẻ, AC-AGT-04): lấy lịch đã dựng, không phân luồng/tìm lại/gọi LLM.
    graph.add_conditional_edges("intake", route_after_intake,
                                {name: name for name in ("classify", "apply_option")})
    graph.add_conditional_edges("classify", route_after_classify,
                                {name: name for name in ("converse", "extract", "clarify", "explore", "tool",
                                                         "dead_letter")})
    graph.add_conditional_edges("extract", route_after_extract,
                                {name: name for name in ("tool", "clarify", "explore", "converse", "dead_letter")})
    graph.add_edge("tool", "evaluate")
    graph.add_conditional_edges("evaluate", route_after_evaluate,
                                {name: name for name in ("retry", "dead_letter", "filter", "clarify")})
    graph.add_conditional_edges("retry", route_after_retry,
                                {name: name for name in ("tool", "dead_letter", "filter")})
    # Bỏ điểm tham quan trùng (luật rồi LLM chỉ ra cặp) trước khi xếp lịch (AC-AGT-04, chốt 2026-10-08).
    graph.add_edge("filter", "compose")
    graph.add_edge("converse", "finalize")
    graph.add_conditional_edges("explore", route_after_explore, {name: name for name in ("extract", "finalize")})
    graph.add_edge("compose", "narrate")
    graph.add_edge("apply_option", "finalize")
    graph.add_edge("narrate", "finalize")
    graph.add_edge("clarify", "finalize")
    graph.add_edge("dead_letter", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=checkpointer)
