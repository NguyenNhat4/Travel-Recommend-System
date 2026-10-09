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


def is_unaccented(q: str, min_tokens: int = 3) -> bool:
    """Câu gõ **không dấu** (slice `no_diacritics` của gold): có chữ cái, bỏ dấu (kể cả đ → d) không đổi gì, và có ít nhất
    `min_tokens` token truy vấn không phải số. Câu ngắn kiểu thương hiệu ("VinWonders", "Sun World") không tính — chúng đi
    đường vớt BM25 bình thường. Tính trên câu **gốc**: bước chuẩn hoá đã trả dấu cho địa danh nên không dùng được câu sau nó."""
    s = unicodedata.normalize("NFC", q)
    if not any(ch.isalpha() for ch in s) or strip_accents(s) != s:
        return False
    return sum(not t.isdigit() for t in query_tokens(s)) >= min_tokens


def coverage(q_tokens: Iterable[str], name_tokens: set[str]) -> float:
    """Tỉ lệ token của truy vấn có mặt trong tên — truy vấn gần như là tên/thương hiệu thì cao.

    "VinWonders" vs "VinWonders Nha Trang" = 1.0; "khach san ca mau" vs "Hoa Mau Don Homestay" = 0.25.
    Không dùng độ hiếm (DF) của token: trên catalog thật "vinwonders" (4,9% tên) và "trang" (5,0%) không tách được.
    """
    q = list(q_tokens)
    return sum(t in name_tokens for t in q) / len(q) if q else 0.0
