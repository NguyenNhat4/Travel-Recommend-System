"""Use cases đọc lịch sử hội thoại; danh tính luôn lấy từ AuthPrincipal ở biên HTTP."""
from __future__ import annotations

from src.backend.app.application.ports.conversation_archive import ConversationArchivePort


class ConversationHistory:
    def __init__(self, archive: ConversationArchivePort):
        self._archive = archive

    async def list(self, cdp_user_id: str, *, page: int, page_size: int) -> dict:
        return await self._archive.list_for_user(cdp_user_id, page=page, page_size=page_size)

    async def get(self, conversation_id: str, cdp_user_id: str) -> dict | None:
        return await self._archive.get_for_user(conversation_id, cdp_user_id)
