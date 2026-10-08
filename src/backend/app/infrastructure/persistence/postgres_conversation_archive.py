"""PostgreSQL archive for authenticated itinerary conversations."""
from __future__ import annotations

import math
import uuid
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from src.backend.app.infrastructure.persistence.db_connection import connect_async


def _uuid(value: str) -> str | None:
    try:
        return str(uuid.UUID(value))
    except (TypeError, ValueError):
        return None


def _summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "conversationId": str(row["conversation_id"]),
        "title": (row.get("title") or "Cuộc trò chuyện mới")[:120],
        "status": row["status"],
        "createdAt": row["created_at"].isoformat(),
        "updatedAt": row["last_message_at"].isoformat(),
        "messageCount": row["message_count"],
    }


class PostgresConversationArchive:
    def __init__(self, database_url: str):
        self._database_url = database_url

    async def _connect(self):
        return await connect_async(self._database_url, row_factory=dict_row)

    async def record_turn(
        self, conversation_id: str, cdp_user_id: str, state: dict[str, Any]
    ) -> None:
        conversation_uuid = _uuid(conversation_id)
        if conversation_uuid is None:
            raise ValueError("conversation_id must be a UUID")
        request_id = str(state["request_id"])
        response = state["response"]
        status = "planned" if response.get("status") == "COMPLETED" else "open"
        async with await self._connect() as conn:
            async with conn.transaction():
                existing = await (
                    await conn.execute(
                        "SELECT cdp_user_id FROM app.conversations WHERE conversation_id = %s::uuid FOR UPDATE",
                        (conversation_uuid,),
                    )
                ).fetchone()
                if existing is not None and existing["cdp_user_id"] != cdp_user_id:
                    raise PermissionError("conversation belongs to another user")
                await conn.execute(
                    """
                    INSERT INTO app.conversations
                        (conversation_id, cdp_user_id, intent, status, last_message_at, expires_at)
                    VALUES (%s::uuid, %s, %s, %s, now(), now() + interval '24 hours')
                    ON CONFLICT (conversation_id) DO UPDATE SET
                        intent = EXCLUDED.intent,
                        status = EXCLUDED.status,
                        last_message_at = now(),
                        expires_at = now() + interval '24 hours'
                    """,
                    (conversation_uuid, cdp_user_id, Jsonb(state["intent"]), status),
                )
                messages = (
                    ("user", state.get("query") or "", {"requestId": request_id}),
                    ("assistant", state.get("answer") or "", {
                        "requestId": request_id,
                        "response": response,
                        "workingState": state["working_state"],
                    }),
                )
                for role, content, payload in messages:
                    if not content:
                        continue
                    await conn.execute(
                        """
                        INSERT INTO app.conversation_messages (conversation_id, role, content, payload)
                        SELECT %s::uuid, %s, %s, %s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM app.conversation_messages
                            WHERE conversation_id = %s::uuid AND role = %s
                              AND payload->>'requestId' = %s
                        )
                        """,
                        (conversation_uuid, role, content, Jsonb(payload),
                         conversation_uuid, role, request_id),
                    )

    async def restore(self, conversation_id: str, cdp_user_id: str) -> dict[str, Any] | None:
        conversation_uuid = _uuid(conversation_id)
        if conversation_uuid is None:
            return None
        async with await self._connect() as conn:
            row = await (
                await conn.execute(
                    """
                    SELECT m.payload->'workingState' AS working_state
                    FROM app.conversations c
                    JOIN app.conversation_messages m USING (conversation_id)
                    WHERE c.conversation_id = %s::uuid AND c.cdp_user_id = %s
                      AND m.role = 'assistant' AND m.payload ? 'workingState'
                    ORDER BY m.message_id DESC LIMIT 1
                    """,
                    (conversation_uuid, cdp_user_id),
                )
            ).fetchone()
        return row["working_state"] if row and isinstance(row["working_state"], dict) else None

    async def list_for_user(
        self, cdp_user_id: str, *, page: int, page_size: int
    ) -> dict[str, Any]:
        offset = (page - 1) * page_size
        async with await self._connect() as conn:
            total = (await (
                await conn.execute(
                    "SELECT count(*) AS count FROM app.conversations WHERE cdp_user_id = %s",
                    (cdp_user_id,),
                )
            ).fetchone())["count"]
            rows = await (
                await conn.execute(
                    """
                    SELECT c.conversation_id, c.status, c.created_at, c.last_message_at,
                           count(m.message_id)::int AS message_count,
                           coalesce((array_agg(m.content ORDER BY m.message_id)
                                     FILTER (WHERE m.role = 'user'))[1], '') AS title
                    FROM app.conversations c
                    LEFT JOIN app.conversation_messages m USING (conversation_id)
                    WHERE c.cdp_user_id = %s
                    GROUP BY c.conversation_id
                    ORDER BY c.last_message_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (cdp_user_id, page_size, offset),
                )
            ).fetchall()
        return {
            "data": [_summary(row) for row in rows],
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "totalItems": total,
                "totalPages": math.ceil(total / page_size) if total else 0,
            },
        }

    async def get_for_user(
        self, conversation_id: str, cdp_user_id: str
    ) -> dict[str, Any] | None:
        conversation_uuid = _uuid(conversation_id)
        if conversation_uuid is None:
            return None
        async with await self._connect() as conn:
            conversation = await (
                await conn.execute(
                    """
                    SELECT c.conversation_id, c.status, c.created_at, c.last_message_at,
                           count(m.message_id)::int AS message_count,
                           coalesce((array_agg(m.content ORDER BY m.message_id)
                                     FILTER (WHERE m.role = 'user'))[1], '') AS title
                    FROM app.conversations c
                    LEFT JOIN app.conversation_messages m USING (conversation_id)
                    WHERE c.conversation_id = %s::uuid AND c.cdp_user_id = %s
                    GROUP BY c.conversation_id
                    """,
                    (conversation_uuid, cdp_user_id),
                )
            ).fetchone()
            if conversation is None:
                return None
            rows = await (
                await conn.execute(
                    """
                    SELECT message_id, role, content, payload, created_at
                    FROM app.conversation_messages
                    WHERE conversation_id = %s::uuid AND role IN ('user', 'assistant')
                    ORDER BY message_id
                    """,
                    (conversation_uuid,),
                )
            ).fetchall()
        messages = []
        for row in rows:
            item = {
                "messageId": row["message_id"],
                "role": row["role"],
                "content": row["content"],
                "createdAt": row["created_at"].isoformat(),
            }
            response = (row["payload"] or {}).get("response")
            if isinstance(response, dict) and response.get("status") in {
                "COMPLETED", "NEEDS_CLARIFICATION", "NO_RESULTS", "FALLBACK",
            }:
                item["response"] = response
            messages.append(item)
        return {"conversation": _summary(conversation), "messages": messages}
