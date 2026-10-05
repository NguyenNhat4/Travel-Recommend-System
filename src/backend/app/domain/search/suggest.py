"""Gợi ý tức thì khi gõ ở ô tìm kiếm (FR-SRC-05): khớp tiền tố theo từ trên tên đã fold, rồi chia đều theo nhóm.

Thuần stdlib, không điểm số ngữ nghĩa: đây là khớp chữ để người dùng thấy ngay catalog có gì, còn `/search` mới là
tìm theo nghĩa. Fold dùng chung `lexical.fold` nên "ha" khớp "Hà Nội", "Hạ Long".
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .lexical import fold

#: Thứ tự hiển thị: điểm đến trước, rồi sản phẩm theo taxonomy. Vé máy bay không có ở đây (chỉ tìm ở /flights).
SUGGEST_GROUPS: tuple[str, ...] = ("destination", "hotel", "attraction", "golf", "combo")
#: Ít hơn chừng này ký tự chữ/số thì không gợi ý: một ký tự khớp gần hết catalog.
MIN_QUERY_CHARS = 2


@dataclass
class SuggestEntry:
    """Một thứ có thể gợi ý. `group` là "destination" hoặc taxonomy; `weight` càng lớn càng đứng trước khi hoà."""
    group: str
    label: str
    weight: float = 0.0
    product_id: str | None = None
    destination: str | None = None
    folded: str = field(init=False, repr=False)
    tokens: tuple[str, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.folded = fold(self.label)
        self.tokens = tuple(self.folded.split())


def is_suggestable(q: str) -> bool:
    """Đủ 2 ký tự chữ hoặc số sau khi fold; khoảng trắng và dấu câu không tính."""
    return len(fold(q).replace(" ", "")) >= MIN_QUERY_CHARS


def match_tier(folded_query: str, query_tokens: tuple[str, ...], entry: SuggestEntry) -> int | None:
    """0: tên bắt đầu bằng truy vấn · 1: truy vấn khớp liền mạch từ đầu một từ · 2: mỗi token của truy vấn là tiền tố
    của một từ nào đó trong tên (không cần đúng thứ tự) · None: không khớp. Không khớp giữa từ ("ha" ≠ "nhạc")."""
    if entry.folded.startswith(folded_query):
        return 0
    if f" {folded_query}" in f" {entry.folded}":
        return 1
    if all(any(t.startswith(q) for t in entry.tokens) for q in query_tokens):
        return 2
    return None


def suggest(entries: Iterable[SuggestEntry], q: str, limit: int = 8) -> list[SuggestEntry]:
    """Tối đa `limit` gợi ý, xếp theo `SUGGEST_GROUPS`.

    Chia chỗ theo vòng: mỗi vòng mỗi nhóm lấy thêm một mục tốt nhất còn lại, đến khi đủ `limit` hoặc hết. Nhờ vậy
    một nhóm nhiều kết quả không đẩy các nhóm khác ra, mà khi chỉ một nhóm khớp thì nhóm đó vẫn dùng hết chỗ.
    """
    if limit <= 0 or not is_suggestable(q):
        return []
    folded_query = fold(q)
    query_tokens = tuple(folded_query.split())
    matched: dict[str, list[tuple[int, float, int, str, SuggestEntry]]] = {g: [] for g in SUGGEST_GROUPS}
    for entry in entries:
        bucket = matched.get(entry.group)
        if bucket is None:
            continue
        tier = match_tier(folded_query, query_tokens, entry)
        if tier is not None:
            bucket.append((tier, -entry.weight, len(entry.label), entry.label, entry))
    for bucket in matched.values():
        bucket.sort(key=lambda item: item[:4])

    taken = dict.fromkeys(SUGGEST_GROUPS, 0)
    total = 0
    progressed = True
    while total < limit and progressed:
        progressed = False
        for group in SUGGEST_GROUPS:
            if total < limit and taken[group] < len(matched[group]):
                taken[group] += 1
                total += 1
                progressed = True
    return [item[4] for group in SUGGEST_GROUPS for item in matched[group][:taken[group]]]
