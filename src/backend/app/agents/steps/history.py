"""Bounded, prompt-safe conversation history for multi-turn itinerary requests."""

from __future__ import annotations

from typing import Any

MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_MESSAGE_CHARS = 1_000
MAX_HISTORY_TOTAL_CHARS = 8_000
ALLOWED_HISTORY_ROLES = {"user", "assistant"}


def sanitize_conversation_history(value: Any) -> list[dict[str, str]]:
    """Keep only recent user/assistant text within fixed prompt and storage limits."""
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if not isinstance(item, dict) or item.get("role") not in ALLOWED_HISTORY_ROLES:
            continue
        content = item.get("content")
        if not isinstance(content, str):
            continue
        content = content.strip()[:MAX_HISTORY_MESSAGE_CHARS]
        if content:
            normalized.append({"role": item["role"], "content": content})

    kept: list[dict[str, str]] = []
    total_chars = 0
    for item in reversed(normalized[-MAX_HISTORY_MESSAGES:]):
        if total_chars + len(item["content"]) > MAX_HISTORY_TOTAL_CHARS:
            break
        kept.append(item)
        total_chars += len(item["content"])
    return list(reversed(kept))


def append_conversation_turn(history: Any, user_message: Any, assistant_message: Any) -> list[dict[str, str]]:
    """Append one real user turn and its assistant reply, then re-apply bounds."""
    current = sanitize_conversation_history(history)
    if not isinstance(user_message, str) or not user_message.strip():
        return current
    current.append({"role": "user", "content": user_message})
    if isinstance(assistant_message, str) and assistant_message.strip():
        current.append({"role": "assistant", "content": assistant_message})
    return sanitize_conversation_history(current)


def llm_context(state: dict[str, Any], *, intent: dict[str, Any] | None = None,
                constraints: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ngữ cảnh hội thoại chung cho MỌI lượt gọi LLM của graph.

    Lịch sử bị giới hạn (20 message, 8.000 ký tự), nên kèm bản tóm tắt chuyến đi đã chốt (`known_intent`,
    `known_constraints`) và sản phẩm đã cho xem: thông tin của lượt cũ vẫn còn dù message cũ bị cắt.
    `last_assistant_message` giúp hiểu câu trả lời ngắn ("1 ngày thôi", "chưa chốt ngày") là trả lời cho câu hỏi nào.
    Node truyền `intent`/`constraints` khi đã có bản mới hơn state (ví dụ điểm đến đã chuẩn hóa ở `tool`).
    """
    history = sanitize_conversation_history(state.get("conversation_history", []))
    last_assistant = next((item["content"] for item in reversed(history) if item["role"] == "assistant"), None)
    return {"conversation_history": history,
            "last_assistant_message": last_assistant,
            "known_intent": intent if intent is not None else state.get("intent", {}),
            "known_constraints": constraints if constraints is not None else state.get("constraints", {}),
            "previous_selection": state.get("previous_selection", [])}
