"""Vị trí dấu thanh kiểu cũ / kiểu mới (`domain/search/tone.py`; kiến trúc §3 "Chuẩn hoá dấu kiểu mới"): chỉ âm tiết mở
"oa" / "oe" / "uy" (không sau "q") đổi, giữ hoa thường; đoán kiểu của catalog theo đa số."""
import unicodedata

import pytest

from src.backend.app.domain.search.tone import detect_style, normalize_tone

PAIRS = [   # (kiểu mới, kiểu cũ)
    ("hoà", "hòa"),
    ("Khánh Hoà", "Khánh Hòa"),
    ("thuỷ", "thủy"),
    ("khoẻ", "khỏe"),
    ("HOÀ", "HÒA"),
    ("Thanh Hoá", "Thanh Hóa"),
    ("uỷ ban", "ủy ban"),
    ("oà", "òa"),
    ("tuỳ chọn", "tùy chọn"),
    ("xoè", "xòe"),
]


@pytest.mark.parametrize("new, old", PAIRS)
def test_convert_between_styles(new, old):
    assert normalize_tone(new, "old") == (old, 1)
    assert normalize_tone(old, "new") == (new, 1)
    assert normalize_tone(new, "new") == (new, 0) and normalize_tone(old, "old") == (old, 0)


@pytest.mark.parametrize("word", ["Hoàng", "khoảng", "toàn", "quý", "QUÝ", "Quỳnh", "ngoài", "khuya", "thuyền", "hoa",
                                  "Hoa Hồng", "hello world", "Vinpearl Resort", "2 triệu"])
def test_closed_syllables_and_qu_never_change(word):
    for style in ("old", "new"):
        assert normalize_tone(word, style) == (word, 0)


def test_sentence_counts_changes_and_returns_nfc():
    assert normalize_tone("Hoà Bình và Thủy Tiên", "old") == ("Hòa Bình và Thủy Tiên", 1)
    assert normalize_tone("Hoà Bình và Thủy Tiên", "new") == ("Hoà Bình và Thuỷ Tiên", 1)
    assert normalize_tone(unicodedata.normalize("NFD", "Khánh Hoà"), "old") == ("Khánh Hòa", 1)
    assert normalize_tone(unicodedata.normalize("NFD", "hoà"), None) == ("hoà", 0)        # không có kiểu → chỉ NFC


@pytest.mark.parametrize("texts, style", [
    (["Khánh Hòa", "Thủy Tiên Resort", "Hoà Bình"], "old"),
    (["Khánh Hoà", "Khách sạn Thuỷ Tiên", "Hòa Bình"], "new"),
    (["Hoàng Gia", "Nha Trang", "Quý Hotel"], None),           # không âm tiết nào thuộc diện
    (["hòa", "hoà"], None),                                     # hoà nhau
    ([], None),
])
def test_detect_style(texts, style):
    assert detect_style(texts) == style
