"""Port chat model mà agent itinerary dùng.

Khớp phần giao diện LangChain mà `agents/nodes.py` và `agents/steps/tool_planning.py` gọi; adapter cụ thể nằm ở `infrastructure/llm/`.
"""
from __future__ import annotations

from typing import Any, Protocol


class ChatModelPort(Protocol):
    def with_structured_output(self, schema: Any) -> Any: ...
    def bind_tools(self, tools: list[dict[str, Any]]) -> Any: ...
