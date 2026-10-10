"""Port lưu và đọc lịch sử hội thoại bền vững của Itinerary Assistant."""
from __future__ import annotations

from typing import Any, Protocol


class ConversationArchivePort(Protocol):
    async def record_turn(
        self, conversation_id: str, cdp_user_id: str, state: dict[str, Any]
    ) -> None: ...

    async def update_last_turn(
        self, conversation_id: str, cdp_user_id: str, state: dict[str, Any]
    ) -> None:
        """Ghi đè lịch (`response`, gộp theo khoá) và `working_state` của câu trả lời gần nhất, không thêm tin nhắn —
        lượt bấm thẻ phương án khách sạn (AC-AGT-04, chốt 2026-10-08)."""
        ...

    async def restore(self, conversation_id: str, cdp_user_id: str) -> dict[str, Any] | None:
        """`working_state` của câu trả lời gần nhất, kèm `response` của chính dòng đó ở khoá `lastResponse` (nếu có)."""
        ...

    async def list_for_user(
        self, cdp_user_id: str, *, page: int, page_size: int
    ) -> dict[str, Any]: ...

    async def get_for_user(
        self, conversation_id: str, cdp_user_id: str
    ) -> dict[str, Any] | None: ...
