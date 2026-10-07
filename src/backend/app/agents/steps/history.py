"""Bounded, prompt-safe conversation history for multi-turn itinerary requests."""

from __future__ import annotations

from typing import Any

import yaml

from .messages import plain_links, strip_title
from .turn_notes import stage, trip_summary

MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_MESSAGE_CHARS = 1_000
MAX_HISTORY_TOTAL_CHARS = 8_000
#: Ghi chú lượt trợ lý (`turn_notes`) là một câu ngắn; dài hơn mức này thì cắt.
MAX_NOTE_CHARS = 300
#: Câu cuối của trợ lý ngắn hơn mức này (câu hỏi lại) được đưa nguyên văn cho LLM; dài hơn (lịch trình) thì dùng
#: ghi chú, để giá và cả bài diễn giải không lấn át câu mới nhất của người dùng.
MAX_VERBATIM_ASSISTANT_CHARS = 500
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
            entry = {"role": item["role"], "content": content}
            note = item.get("note")
            if item["role"] == "assistant" and isinstance(note, str) and note.strip():
                entry["note"] = note.strip()[:MAX_NOTE_CHARS]
            normalized.append(entry)

    kept: list[dict[str, str]] = []
    total_chars = 0
    for item in reversed(normalized[-MAX_HISTORY_MESSAGES:]):
        if total_chars + len(item["content"]) > MAX_HISTORY_TOTAL_CHARS:
            break
        kept.append(item)
        total_chars += len(item["content"])
    return list(reversed(kept))


def append_conversation_turn(history: Any, user_message: Any, assistant_message: Any,
                             note: str | None = None) -> list[dict[str, str]]:
    """Append one real user turn and its assistant reply, then re-apply bounds.

    `note` là ghi chú theo nghĩa của câu trả lời (`turn_notes.turn_note`), lưu kèm để lượt sau đưa cho LLM.
    """
    current = sanitize_conversation_history(history)
    if not isinstance(user_message, str) or not user_message.strip():
        return current
    current.append({"role": "user", "content": user_message})
    if isinstance(assistant_message, str) and assistant_message.strip():
        current.append({"role": "assistant", "content": assistant_message, **({"note": note} if note else {})})
    return sanitize_conversation_history(current)


def _title(text: str) -> str | None:
    """Dòng tiêu đề `**...**` của câu trợ lý, nếu có."""
    first = text.partition("\n")[0].strip()
    if first.startswith("**") and first.endswith("**") and len(first) > 4:
        return first.strip("*").strip()
    return None


def _assistant_line(item: dict[str, str]) -> str:
    """Câu trợ lý cũ như LLM thấy: ghi chú theo nghĩa; bản lưu trước khi có ghi chú thì dùng câu gọn hoặc tiêu đề."""
    if item.get("note"):
        return item["note"]
    text = plain_links(strip_title(item["content"]))
    if len(text) <= MAX_VERBATIM_ASSISTANT_CHARS:
        return text
    return _title(item["content"]) or text[:MAX_VERBATIM_ASSISTANT_CHARS]


def llm_context(state: dict[str, Any], *, intent: dict[str, Any] | None = None,
                constraints: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ngữ cảnh hội thoại chung cho MỌI lượt gọi LLM của graph, đã diễn giải sẵn thay cho bản dump thô.

    - `trip_so_far`: chuyến đi đã biết trong một dòng, kèm trường còn thiếu; `stage`: đã gửi lịch trình hay đang hỏi.
    - `conversation_history`: mỗi mục một khoá theo người nói — `user` nguyên văn, `assistant_did` là ghi chú theo
      nghĩa (`turn_notes`), không còn cả bài lịch trình kèm giá — thứ khiến LLM chép giá/khách sạn cũ thành ràng buộc mới.
    - `last_assistant_message`: câu cuối của trợ lý, nguyên văn khi ngắn (câu hỏi lại) để hiểu câu trả lời ngắn
      ("1 ngày thôi") là trả lời cho câu nào; lịch trình thì là ghi chú.
    - `known_constraints`, `previous_selection`: ràng buộc đã chốt và sản phẩm đã cho xem (id để loại/đổi món).
    Lịch sử bị giới hạn (20 message, 8.000 ký tự) nên phần tóm tắt giữ được thông tin của lượt cũ đã bị cắt.
    Node truyền `intent`/`constraints` khi đã có bản mới hơn state (ví dụ điểm đến đã chuẩn hóa ở `tool`).
    """
    raw = sanitize_conversation_history(state.get("conversation_history", []))
    # Mỗi mục một khoá theo người nói: cặp `role`/`content` phẳng làm LLM đọc nhầm ghi chú trợ lý thành lời người dùng.
    history = [{"assistant_did": _assistant_line(item)} if item["role"] == "assistant" else {"user": item["content"]}
               for item in raw]
    last = next((item for item in reversed(raw) if item["role"] == "assistant"), None)
    last_text = None
    if last is not None:
        verbatim = plain_links(strip_title(last["content"]))
        last_text = verbatim if len(verbatim) <= MAX_VERBATIM_ASSISTANT_CHARS else _assistant_line(last)
    return {"trip_so_far": trip_summary(state, intent),
            "stage": stage(state),
            "conversation_history": history,
            "last_assistant_message": last_text,
            "known_constraints": constraints if constraints is not None else state.get("constraints", {}),
            "previous_selection": state.get("previous_selection", [])}


class _PromptDumper(yaml.SafeDumper):
    """SafeDumper giữ nguyên thứ tự khoá và in chuỗi nhiều dòng dạng khối `|` cho dễ đọc."""


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_PromptDumper.add_representer(str, _represent_str)


def prompt_yaml(payload: dict[str, Any]) -> str:
    """Payload của message `human` gửi LLM dưới dạng YAML dễ đọc (tiếng Việt giữ nguyên, không escape).

    `SafeDumper` tự quote/thụt lề nội dung người dùng, nên một câu chat chứa `key:` hay xuống dòng
    không phá được cấu trúc payload.
    """
    return yaml.dump(payload, Dumper=_PromptDumper, allow_unicode=True, sort_keys=False,
                     default_flow_style=False, width=1_000_000)
