"""Chuẩn hoá vị trí dấu thanh cho /search (kiến trúc `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` §3
"Chuẩn hoá dấu kiểu mới": `hoà → hòa` nếu catalog dùng `hòa`).

Tiếng Việt có hai cách đặt dấu thanh, và chúng chỉ khác nhau ở âm tiết MỞ (không phụ âm cuối) có vần "oa", "oe", "uy"
("uy" không đứng sau "q" — "quý" thì "qu" là phụ âm đầu): kiểu cũ đặt dấu ở nguyên âm đầu (hòa, khỏe, thủy), kiểu mới ở
nguyên âm sau (hoà, khoẻ, thuỷ). Có phụ âm cuối thì hai kiểu trùng nhau (hoàng, khoảng) — không bao giờ đổi. Hai cách viết
fold ra cùng một chuỗi nên BM25 không phân biệt, nhưng vector dense thì có: câu gõ kiểu mới gặp catalog kiểu cũ là hai chuỗi
khác nhau. `detect_style` đếm kiểu chiếm đa số trên tên catalog (tên sản phẩm + điểm đến), `normalize_tone` đưa câu về kiểu
đó. Làm theo từng từ `\\w+` trên NFC, giữ hoa thường; chỉ dời dấu thanh, không đổi chữ. Thuần stdlib.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

TONE_OLD, TONE_NEW = "old", "new"
#: Dấu thanh (dạng tổ hợp sau NFD): huyền, sắc, ngã, hỏi, nặng. Dấu mũ / trăng / móc KHÔNG phải dấu thanh.
_TONE_MARKS = frozenset("̣̀́̃̉")
_WORD = re.compile(r"\w+")
_PAIRS = frozenset({"oa", "oe", "uy"})
#: Phụ âm đầu hợp lệ (chữ thường, "" = không phụ âm đầu: "oà", "uỷ"). Không có "q": "qu" + "y" là "quý", dấu luôn ở "y".
_INITIALS = frozenset({"", "b", "c", "ch", "d", "đ", "g", "gh", "gi", "h", "k", "kh", "l", "m", "n", "ng", "ngh", "nh",
                       "p", "ph", "r", "s", "t", "th", "tr", "v", "x"})


def _letters(word: str) -> list[tuple[str, str]]:
    """[(chữ cái giữ dấu mũ/trăng/móc và hoa thường, dấu thanh hoặc "")] cho từng ký tự của từ NFC."""
    out = []
    for ch in word:
        d = unicodedata.normalize("NFD", ch)
        tone = "".join(m for m in d[1:] if m in _TONE_MARKS)
        base = unicodedata.normalize("NFC", d[0] + "".join(m for m in d[1:] if m not in _TONE_MARKS))
        out.append((base, tone))
    return out


def _ambiguous(letters: list[tuple[str, str]]) -> str | None:
    """Kiểu dấu ("old" | "new") của âm tiết mở "oa"/"oe"/"uy" có đúng một dấu thanh ở cặp cuối; None nếu không thuộc diện."""
    if len(letters) < 2:
        return None
    marked = [k for k, (_, tone) in enumerate(letters) if tone]
    if len(marked) != 1:
        return None
    base = "".join(b for b, _ in letters).lower()
    if base[-2:] not in _PAIRS or base[:-2] not in _INITIALS:
        return None
    if marked[0] == len(letters) - 2:
        return TONE_OLD
    if marked[0] == len(letters) - 1:
        return TONE_NEW
    return None


def _style_counts(texts: Iterable[str]) -> tuple[int, int]:
    old = new = 0
    for text in texts:
        for w in _WORD.findall(unicodedata.normalize("NFC", str(text))):
            style = _ambiguous(_letters(w))
            if style == TONE_OLD:
                old += 1
            elif style == TONE_NEW:
                new += 1
    return old, new


def detect_style(texts: Iterable[str]) -> str | None:
    """Kiểu dấu chiếm đa số trên các âm tiết thuộc diện trong `texts` (tên catalog, điểm đến); None khi không có bằng
    chứng hoặc hai kiểu hoà nhau — khi đó không đổi gì."""
    old, new = _style_counts(texts)
    if old > new:
        return TONE_OLD
    if new > old:
        return TONE_NEW
    return None


def normalize_tone(text: str, style: str | None) -> tuple[str, int]:
    """(text NFC với mọi âm tiết thuộc diện đã về `style`, số âm tiết đã đổi). `style` None → chỉ NFC."""
    text = unicodedata.normalize("NFC", text)
    if style not in (TONE_OLD, TONE_NEW):
        return text, 0
    changed = 0

    def repl(m: re.Match) -> str:
        nonlocal changed
        letters = _letters(m.group())
        current = _ambiguous(letters)
        if current is None or current == style:
            return m.group()
        first, second = len(letters) - 2, len(letters) - 1
        src, dst = (first, second) if style == TONE_NEW else (second, first)
        tone = letters[src][1]
        letters[src] = (letters[src][0], "")
        letters[dst] = (letters[dst][0], tone)
        changed += 1
        return unicodedata.normalize("NFC", "".join(b + t for b, t in letters))

    out = _WORD.sub(repl, text)
    return out, changed
