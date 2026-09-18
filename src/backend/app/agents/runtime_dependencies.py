"""Request-scoped runtime wiring. Credentials and models never enter graph state."""
from hashlib import sha256
from typing import Any

from src.backend.app.application.ports.itinerary_tools import ConversationStorePort, ToolExecutorPort
from .graph import build_graph


class RuntimeAgentDependencies:
    def __init__(self, tools: ToolExecutorPort, store: ConversationStorePort,
                 llm: Any | None = None, authorization: str | None = None):
        self.tools = tools
        self.store = store
        self.llm = llm
        self.owner = sha256(authorization.encode()).hexdigest() if authorization else "anonymous"
        self.require_recommendations = authorization is not None

    def graph(self, checkpointer=None):
        return build_graph(checkpointer=checkpointer, tools=self.tools, llm=self.llm,
                           store=self.store, owner=self.owner,
                           require_recommendations=self.require_recommendations)
