"""Process-local conversation storage for development and tests."""

from copy import deepcopy
from time import monotonic
from typing import Any, Callable


class InMemoryConversationStore:
    def __init__(self, ttl_seconds: int = 86_400, clock: Callable[[], float] = monotonic):
        self.ttl_seconds, self.clock = ttl_seconds, clock
        self._items: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}

    async def load(self, conversation_id: str | None, owner: str = "anonymous") -> dict[str, Any] | None:
        if not conversation_id or (owner, conversation_id) not in self._items:
            return None
        created_at, value = self._items[(owner, conversation_id)]
        if self.clock() - created_at > self.ttl_seconds:
            self._items.pop((owner, conversation_id), None)
            return None
        return deepcopy(value)

    async def save(self, conversation_id: str, value: dict[str, Any], owner: str = "anonymous") -> None:
        self._items[(owner, conversation_id)] = (self.clock(), deepcopy(value))
