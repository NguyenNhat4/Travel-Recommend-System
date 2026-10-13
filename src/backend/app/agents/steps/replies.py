"""Nút gợi ý và câu chữ dùng chung của câu trả lời trò chuyện, khám phá (FR-AGT-06, AC-AGT-07).

`checked_suggestions` kiểm nút LLM đề xuất (tối đa 3, không lặp lượt trước, không trùng mẫu câu, có nút đi tiếp);
`conversation_templates` là nút dự phòng; `once_praise` bỏ cụm khen lặp; `about` rút phần mô tả catalog nói nơi đó là
gì. Orchestrator (`orchestration.py`), `clarify` (`conversation.py`) và `narrate` (`narration.py`) dùng chung.
"""
from __future__ import annotations

import re
import unicodedata

from src.backend.app.domain.itinerary.normalization import fold

from .consent import asks_for_plan
from .messages import message

MAX_SUGGESTION_CHARS = 60
MAX_SUGGESTIONS = 3
#: Số điểm đến của catalog đưa cho LLM để gợi ý nút (nhiều sản phẩm nhất trước).
CATALOG_HINT = 12
#: Mô tả catalog đưa cho LLM, đủ để kể nơi đó có gì hay trong 2–3 câu (chat thử 10/10: 360 ký tự cho câu quá cụt).
ABOUT_CHARS = 700
#: Cụm khen dễ bị lặp ở mọi dòng ("nhiều người ghé", "được khen nhiều"): mỗi câu trả lời giữ lần đầu, bỏ các lần sau
#: (so trên chuỗi đã `fold`, kèm dấu nối đứng trước).
_PRAISE = re.compile(r"(?:\s*[,;–-]\s*|\s+)(?:va |lai |cung )?(?:duoc (?:du khach |nhieu nguoi )?khen nhieu|"
                     r"(?:cung )?(?:duoc )?nhieu nguoi ghe(?: nhat(?: o day)?)?|ngay gan do|gia mem)")
#: Câu trong mô tả catalog chỉ chứa số liệu (giờ, địa chỉ, thời lượng): thẻ bên phải đã hiện, câu chat không nhắc lại.
_DATA_SENTENCE = re.compile(r"^\s*(?:gio mo cua|dia chi|thoi gian tham quan|loai hinh|dia diem|toi da|\d)")


def _pattern(text: str, destinations: list[str]) -> str:
    """Mẫu câu của một nút: bỏ tên điểm đến và chữ số, để "Hà Nội có gì?" và "Đà Nẵng có gì?" là cùng một mẫu."""
    key = f" {fold(text)} "
    for name in sorted(destinations, key=len, reverse=True):
        if fold(name):
            key = key.replace(f" {fold(name)} ", " _ ")
    return " ".join(re.sub(r"\d+", "#", key).split())


def checked_suggestions(proposed: list[str], previous: list[str], templates: list[str], *,
                        destinations: list[str], plan_chip: str | None = None,
                        avoid: list[str] | None = None) -> list[str]:
    """Tối đa 3 nút: bỏ nút rỗng, quá dài, lặp nút lượt trước, nhắc nơi bị chê (`avoid`) hoặc trùng mẫu câu với nút đã
    giữ (AC-AGT-07).

    `plan_chip` (nút đi tiếp: lập lịch, tiếp tục lập lịch) luôn có một chỗ khi chưa nút nào xin lập lịch. Thiếu nút thì
    bù bằng `templates` theo cùng luật.
    """
    seen_text = {fold(item) for item in previous}
    avoided = [fold(name) for name in avoid or [] if fold(name)]
    kept: list[str] = []
    patterns: set[str] = set()

    def add(text: str) -> None:
        clean = " ".join(str(text or "").split())
        if not clean or len(clean) > MAX_SUGGESTION_CHARS or fold(clean) in seen_text or len(kept) >= MAX_SUGGESTIONS:
            return
        if any(f" {name} " in f" {fold(clean)} " for name in avoided):
            return
        pattern = _pattern(clean, destinations)
        if pattern in patterns:
            return
        patterns.add(pattern)
        kept.append(clean)

    for item in proposed:
        add(item)
    if plan_chip and not any(asks_for_plan(item) for item in kept):
        if len(kept) >= MAX_SUGGESTIONS:
            dropped = kept.pop()
            patterns.discard(_pattern(dropped, destinations))
        seen_text.discard(fold(plan_chip))
        add(plan_chip)
        kept.sort(key=lambda item: not asks_for_plan(item))  # nút đi tiếp đứng đầu
    for item in templates:
        if len(kept) >= 2:
            break
        add(item)
    return kept


def conversation_templates(state: dict, supported: list[str] | None) -> list[str]:
    """Nút dự phòng của lượt trò chuyện, mỗi nút một hướng (xem một nơi, kiểu chuyến, để trợ lý chọn); nút lặp lượt trước
    bị `checked_suggestions` bỏ nên có dư để bù."""
    rejected = {fold(name) for name in state.get("rejected_destinations") or []}
    places = [name for name in (supported or []) if name and fold(name) not in rejected][:1]
    chips = [message(state, "chip_sights", destination=place) for place in places]
    return [*chips, message(state, "chip_beach"), message(state, "chip_pick"), message(state, "chip_cool")]


def about(product: dict) -> str:
    """Phần mô tả catalog nói nơi đó là gì: bỏ câu lặp tên và câu chỉ có số liệu, cắt ở ranh giới câu."""
    name = fold(product.get("name") or "")
    sentences = re.split(r"(?<=[.!?])\s+|\n+", product.get("description") or "")
    kept = [text.strip() for text in sentences
            if text.strip() and fold(text).rstrip(". ") != name and not _DATA_SENTENCE.match(fold(text))]
    result = ""
    for text in kept:
        if len(result) + len(text) > ABOUT_CHARS:
            break
        result = f"{result} {text}".strip()
    return result or (kept[0][:ABOUT_CHARS] if kept else "")


def _plain(text: str) -> str:
    """Chữ thường, bỏ dấu từng ký tự, đ → d; giữ nguyên độ dài (khác `fold`, vốn gộp dấu cách và ký hiệu)."""
    return "".join((unicodedata.normalize("NFD", char)[0] if char not in "đĐ" else "d").lower() for char in text)


def once_praise(text: str) -> str:
    """Mỗi cụm khen chung chỉ giữ lần xuất hiện đầu tiên trong câu trả lời (chat thử 10/10: "nhiều người ghé" ở mọi
    dòng). So trên chuỗi bỏ dấu từng ký tự (giữ độ dài, nên vị trí khớp chuỗi gốc)."""
    folded = _plain(text)
    seen: set[str] = set()
    cuts = []
    for match in _PRAISE.finditer(folded):
        phrase = match.group(0)
        key = "khen" if "khen" in phrase else "ghe" if "ghe" in phrase else "gan" if "gan do" in phrase else "gia"
        if key in seen:
            cuts.append(match.span())
        seen.add(key)
    for start, end in reversed(cuts):
        text = text[:start] + text[end:]
    # Bỏ cụm ở cuối câu có thể để lại "…:." hoặc ", ."
    text = re.sub(r"\s*[,;:–-]\s*([.!?])", r"\1", text)
    return "\n".join(line.rstrip() for line in text.split("\n"))
