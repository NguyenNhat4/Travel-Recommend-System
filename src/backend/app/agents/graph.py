"""Compile the nine-node itinerary graph with request-scoped runtime dependencies."""

from __future__ import annotations

from typing import Any
from functools import partial
from src.backend.app.application.ports.itinerary_tools import ConversationStorePort, ToolExecutorPort

from .state import AgentState


def build_graph(checkpointer: Any | None = None, *, tools: ToolExecutorPort | None = None,
                tool_timeout_seconds: float = 1.0, llm: Any | None = None,
                store: ConversationStorePort | None = None, owner: str = "anonymous",
                require_recommendations: bool = False):
    """Build the lab topology with injected API tools; execute API tools using ainvoke.

    Runtime clients and JWT are captured in the tool node, never checkpointed.
    tool_timeout_seconds limits each API call; transient calls retry at most once.
    """
    if tool_timeout_seconds <= 0:
        raise ValueError("tool_timeout_seconds must be positive")
    from langgraph.graph import END, START, StateGraph
    from langchain_core.runnables import RunnableLambda

    from .nodes import (
        answer_node,
        answer_node_async,
        ask_clarification_node,
        classify_node,
        classify_node_async,
        dead_letter_node,
        evaluate_node,
        finalize_node,
        intake_node,
        intake_node_async,
        finalize_node_async,
        retry_or_fallback_node,
        tool_node,
    )
    from .routing import (
        route_after_classify,
        route_after_evaluate,
        route_after_retry,
    )

    async def run_local(state, *, node):
        # CPU-only nodes do not need a worker thread on the async path.
        return node(state)

    graph = StateGraph(AgentState)
    for name, node in {
        "evaluate": evaluate_node, "clarify": ask_clarification_node,
        "retry": retry_or_fallback_node, "dead_letter": dead_letter_node,
    }.items():
        graph.add_node(name, RunnableLambda(node, afunc=partial(run_local, node=node)))
    graph.add_node("intake", RunnableLambda(intake_node, afunc=partial(intake_node_async, store=store, owner=owner)))
    graph.add_node("finalize", RunnableLambda(finalize_node, afunc=partial(finalize_node_async, store=store, owner=owner)))
    graph.add_node("classify", RunnableLambda(partial(classify_node, llm=llm), afunc=partial(classify_node_async, llm=llm)))
    graph.add_node("answer", RunnableLambda(partial(answer_node, llm=llm), afunc=partial(answer_node_async, llm=llm)))
    graph.add_node("tool", partial(tool_node, tools=tools, timeout_seconds=tool_timeout_seconds,
                                   llm=llm, require_recommendations=require_recommendations))

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "classify")
    graph.add_conditional_edges("classify", route_after_classify)
    graph.add_edge("tool", "evaluate")
    graph.add_conditional_edges("evaluate", route_after_evaluate)
    graph.add_conditional_edges("retry", route_after_retry)
    graph.add_edge("answer", "finalize")
    graph.add_edge("clarify", "finalize")
    graph.add_edge("dead_letter", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=checkpointer)
