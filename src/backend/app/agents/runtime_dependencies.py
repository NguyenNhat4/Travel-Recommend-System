"""Request-scoped runtime wiring. Credentials and models never enter graph state."""
from collections.abc import AsyncIterator
from hashlib import sha256
from typing import Any

from src.backend.app.application.ports.itinerary_tools import ConversationStorePort, ToolExecutorPort
from src.backend.app.application.ports.conversation_archive import ConversationArchivePort
from src.backend.app.application.ports.llm import ChatModelPort
from .graph import build_graph
from .steps.progress import collecting


def orchestrator_budget(request_timeout_seconds: float) -> float:
    """Ngân sách thời gian của orchestrator trong một lượt: chừa một phần nhỏ của hạn request cho gatekeep/finalize/store."""
    return max(0.1, request_timeout_seconds - min(1.0, request_timeout_seconds / 10))


class LangGraphItineraryPlanner:
    """Hiện thực port `ItineraryPlanner` bằng graph LangGraph đã compile."""

    def __init__(self, graph: Any):
        self._graph = graph

    async def ainvoke(self, inputs: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._graph.ainvoke(inputs, config=config)

    async def astream(self, inputs: dict[str, Any], config: dict[str, Any] | None = None) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        with collecting():
            async for mode, payload in self._graph.astream(inputs, stream_mode=['values', 'custom'], config=config):
                yield ('state' if mode == 'values' else 'event', payload)

    def topology(self) -> dict[str, Any]:
        drawing = self._graph.get_graph()
        nodes = [node_id for node_id in drawing.nodes if node_id not in {"__start__", "__end__"}]
        edges = [
            {"source": edge.source, "target": edge.target, "conditional": edge.conditional}
            for edge in drawing.edges
            if edge.source != "__start__" and edge.target != "__end__"
        ]
        return {"nodes": nodes, "edges": edges}


class RuntimeAgentDependencies:
    def __init__(self, tools: ToolExecutorPort, store: ConversationStorePort,
                 llm: ChatModelPort | None = None, authorization: str | None = None,
                 *, owner: str | None = None, archive: ConversationArchivePort | None = None,
                 tool_timeout_seconds: float = 1.0,
                 llm_timeout_seconds: float = 2.0,
                 orchestrator_llm: ChatModelPort | None = None, orchestrator_budget_seconds: float = 10.0):
        self.orchestrator_llm = orchestrator_llm
        self.orchestrator_budget_seconds = orchestrator_budget_seconds
        self.tools = tools
        self.store = store
        self.llm = llm
        self.archive = archive
        self.cdp_user_id = owner
        # Chủ là user đã xác thực, không phải token: BFF làm mới access token mỗi ~9 phút và hội thoại
        # phải sống qua lần làm mới đó. Bearer không xác thực được thì cô lập theo hash của chính nó.
        if owner:
            self.owner = f"user:{owner}"
        else:
            self.owner = f"token:{sha256(authorization.encode()).hexdigest()}" if authorization else "anonymous"
        self.require_recommendations = authorization is not None
        self.tool_timeout_seconds = tool_timeout_seconds
        self.llm_timeout_seconds = llm_timeout_seconds

    def graph(self, checkpointer=None):
        return build_graph(checkpointer=checkpointer, tools=self.tools, llm=self.llm,
                           store=self.store, owner=self.owner,
                           archive=self.archive, cdp_user_id=self.cdp_user_id,
                           require_recommendations=self.require_recommendations,
                           tool_timeout_seconds=self.tool_timeout_seconds,
                           llm_timeout_seconds=self.llm_timeout_seconds,
                           orchestrator_llm=self.orchestrator_llm,
                           orchestrator_budget_seconds=self.orchestrator_budget_seconds)

    def planner(self) -> LangGraphItineraryPlanner:
        return LangGraphItineraryPlanner(self.graph())
