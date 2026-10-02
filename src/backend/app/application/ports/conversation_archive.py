"""Port lưu và đọc lịch sử hội thoại bền vững của Itinerary Assistant."""
from __future__ import annotations

from typing import Any, Protocol


class ConversationArchivePort(Protocol):
    async def record_turn(
        self, conversation_id: str, cdp_user_id: str, state: dict[str, Any]
    ) -> None: ...

    async def restore(self, conversation_id: str, cdp_user_id: str) -> dict[str, Any] | None: ...

    async def list_for_user(
        self, cdp_user_id: str, *, page: int, page_size: int
    ) -> dict[str, Any]: ...

    async def get_for_user(
        self, conversation_id: str, cdp_user_id: str
    ) -> dict[str, Any] | None: ...
