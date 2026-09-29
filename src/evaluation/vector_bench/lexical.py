"""Chuẩn hoá văn bản dùng chung (spec P1.3, P3.4).

fold(s): NFC → lower → bỏ dấu (NFD, xoá combining mark) → đ→d → ký tự ngoài [a-z0-9] thành khoảng trắng → gộp khoảng trắng.
tokens(s): âm tiết đã fold, dài ≥ 2 — tương đương to_tsvector('simple', unaccent(lower(…))).
Kênh lexical (BM25) chưa làm ở fast-track; tokens() để sẵn cho Part 6b.
"""
from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def strip_accents(s: str) -> str:
    """Bỏ dấu, GIỮ hoa/thường (slice `khong_dau` của Part 3)."""
    s = unicodedata.normalize("NFD", unicodedata.normalize("NFC", s))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


def fold(s: str) -> str:
    s = strip_accents(unicodedata.normalize("NFC", s).lower())
    return " ".join(_NON_ALNUM.sub(" ", s).split())


def tokens(s: str) -> list[str]:
    return [t for t in fold(s).split() if len(t) >= 2]


def slug(s: str) -> str:
    return fold(s).replace(" ", "-")
