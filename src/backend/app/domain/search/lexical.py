"""Từ vựng cho nhánh lexical (BM25) của /search: fold dấu, token của truy vấn, độ phủ của tên trên truy vấn.

Thuần stdlib. `fold` chép nguyên từ `src/evaluation/vector_bench/lexical.py` (backend và bench không import
lẫn nhau) — đổi một nơi phải đổi cả hai: truy vấn và văn bản đã index phải fold cùng một cách.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

#: Từ chức năng (đã fold) không mang ý nghĩa tìm kiếm, bỏ khỏi mẫu số độ phủ.
STOPWORDS = frozenset({"o", "va", "cua", "cho", "tai", "gan", "den", "tu", "co", "la", "nhung", "cac", "mot",
                       "the", "and", "of", "in", "at"})


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", unicodedata.normalize("NFC", s))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


def fold(s: str) -> str:
    """NFC → chữ thường → bỏ dấu → đ→d → ký tự ngoài [a-z0-9] thành khoảng trắng → gộp khoảng trắng."""
    s = strip_accents(unicodedata.normalize("NFC", s).lower())
    return " ".join(_NON_ALNUM.sub(" ", s).split())


def tokens(s: str) -> list[str]:
    return fold(s).split()


def query_tokens(q: str, min_len: int = 2) -> list[str]:
    """Token của truy vấn đem đối chiếu với tên: đã fold, bỏ từ chức năng và token quá ngắn, giữ thứ tự, không lặp.

    Giữ token 2 ký tự vì địa danh tiếng Việt hay có âm tiết ngắn ("cà mau" → "ca mau", "bà nà" → "ba na").
    """
    return list(dict.fromkeys(t for t in tokens(q) if len(t) >= min_len and t not in STOPWORDS))


def coverage(q_tokens: Iterable[str], name_tokens: set[str]) -> float:
    """Tỉ lệ token của truy vấn có mặt trong tên — truy vấn gần như là tên/thương hiệu thì cao.

    "VinWonders" vs "VinWonders Nha Trang" = 1.0; "khach san ca mau" vs "Hoa Mau Don Homestay" = 0.25.
    Không dùng độ hiếm (DF) của token: trên catalog thật "vinwonders" (4,9% tên) và "trang" (5,0%) không tách được.
    """
    q = list(q_tokens)
    return sum(t in name_tokens for t in q) / len(q) if q else 0.0
