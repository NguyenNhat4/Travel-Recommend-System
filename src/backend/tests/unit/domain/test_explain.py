"""Bằng chứng theo cụm (giữ dấu, có thứ tự) và residual không giải thích được — plan 2026-10-13 §2.1, §2.6."""
import pytest

from src.backend.app.domain.search.explain import (
    GENERIC_WORDS,
    Grams,
    content,
    explain_residual,
    has_content,
    name_evidence,
    phrase_hit,
    tone_form,
    toks,
)
from src.backend.app.domain.search.normalize import QueryNormalizer

CATALOG = [
    "Thị trấn Hoàng Hôn - Sunset Town . Phú Quốc", "Sân Vận động Thống Nhất", "Nhà Văn hóa tỉnh Đồng Tháp",
    "Chợ Đêm Đà Lạt . chợ đêm sầm uất", "Khách sạn Sweet Lavender gần chợ đêm, gần biển, view đồi thông",
    "Sông Bằng", "VinWonders Nha Trang", "Khách sạn Mường Thanh trên đường Phạm Văn Đồng", "Resort yên tĩnh có hồ bơi riêng",
    "Cung văn hóa lao động hữu nghị Việt - Tiệp", "Khu di tích Nguyễn Sinh Sắc", "du lịch nghỉ dưỡng giá tốt",
]
VOCAB = Grams.build(CATALOG)


def _q(text):
    return content(toks(text))


def test_tone_form_unifies_tone_placement_and_case():
    assert tone_form("Hoà") == tone_form("hòa") == "hòa"
    assert tone_form("Trần") != tone_form("trấn")


@pytest.mark.parametrize("query,name,expected", [
    ("Trần Thị Mai", "Thị trấn Hoàng Hôn - Sunset Town", False),    # bỏ dấu thì khớp 2/3 — giữ dấu + thứ tự thì không
    ("Phạm Văn Đồng", "Sân Vận động Thống Nhất", False),
    ("Lê Văn Tám", "Trung tâm Văn hoá", False),
    ("Sông Bằng", "Sông Bằng", True),
    ("VinWonders", "VinWonders Nha Trang", True),
    ("vinwonders nha trang", "VinWonders Nha Trang", True),           # câu không dấu so ở dạng fold
    ("thi tran hoang hon", "Thị trấn Hoàng Hôn - Sunset Town", True),
    ("tran thi mai", "Thị trấn Hoàng Hôn - Sunset Town", False),      # fold nhưng thứ tự ngược → không có cặp nào
])
def test_name_evidence_needs_ordered_accent_aware_pair(query, name, expected):
    assert name_evidence(_q(query), Grams.build([name]), 0.6) is expected


def test_phrase_hit_on_description_keeps_descriptive_queries():
    text = Grams.build(["Khách sạn Sweet Lavender gần chợ đêm, gần biển"])
    assert phrase_hit(_q("khách sạn gần chợ đêm"), text)
    assert not phrase_hit(_q("Nguyễn Khắc Tiệp"), text)
    assert not phrase_hit([], text)


def test_content_drops_destination_tokens_but_never_everything():
    assert [t.folded for t in content(toks("chợ đêm Đà Lạt"), {"da", "lat"})] == ["cho", "dem"]
    assert [t.folded for t in content(toks("Đà Lạt"), {"da", "lat"})] == ["da", "lat"]


def _res(text, removed=(), has_filters=False):
    return explain_residual(text, removed, VOCAB, has_filters=has_filters)


@pytest.mark.parametrize("text", ["Nguyễn Khắc Tiệp", "Trọng Đăng Nguyễn Khắc Tiệp", "nguyen khac tiep", "Trần Thị Mai"])
def test_name_like_residual_is_unexplained(text):
    r = _res(text)
    assert r.empty and r.unexplained


def test_unexplained_ignores_removed_condition_spans():
    text = "khách sạn Nguyễn Khắc Tiệp"
    r = _res(text, removed=[(0, len("khách sạn"))], has_filters=True)
    assert r.unexplained == ("Nguyễn Khắc Tiệp",)


def test_name_plus_explained_part_drops_only_the_name():
    r = _res("Nguyễn Khắc Tiệp gần biển")
    assert not r.empty and r.unparsed == ("Nguyễn Khắc Tiệp",) and r.has_content


def test_nonsense_without_filters_is_unexplained_but_slang_with_filters_is_kept():
    assert _res("xkcd qwzt plorb").empty
    slang = _res("khách sạn rẻ bèo", removed=[(0, len("khách sạn"))], has_filters=True)
    assert not slang.empty


@pytest.mark.parametrize("text", ["Phạm Văn Đồng", "chợ đêm", "resort yên tĩnh có hồ bơi riêng", "Sông Bằng", "VinWonders"])
def test_explained_text_passes(text):
    r = _res(text)
    assert not r.empty and not r.unparsed


def test_unknown_place_with_only_generic_words_left_is_unexplained():
    r = _res("du lịch Cà Mau")
    assert r.empty and r.unexplained == ("Cà Mau",)
    assert {"du", "lich"} <= GENERIC_WORDS


def test_removed_span_breaks_adjacency():
    # cue "resort" ở giữa: "vinwonders" và "nha" không bị coi là một cặp lạ
    text = "VinWonders resort Nha Trang"
    start = text.index("resort")
    assert not _res(text, removed=[(start, start + len("resort"))]).unparsed


def test_has_content_skips_generic_and_removed():
    assert not has_content("tour 2 ngày 1 đêm", [(5, 17)])
    assert has_content("tour gần biển 2 ngày", [(14, 20)])


def test_accent_restore_longest_match_only_for_multi_syllable_phrases():
    n = QueryNormalizer(destinations=["Đà Lạt"], names=["Chợ Đêm Đà Lạt", "Thị trấn Hoàng Hôn"], restore=True)
    r = n("cho dem dalat")
    assert r.text == "chợ đêm Đà Lạt" and r.restored == ("chợ đêm",)
    assert n("nguyen khac tiep").text == "nguyen khac tiep"
    assert n("tran").restored == ()                          # âm tiết đơn không phục hồi
    assert n("Chợ đêm").restored == ()                       # câu có dấu không đụng
    assert QueryNormalizer(destinations=["Đà Lạt"], names=["Chợ Đêm Đà Lạt"])("cho dem").restored == ()   # cờ tắt
