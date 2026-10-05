"""Luật khớp và chia chỗ của gợi ý tức thì (FR-SRC-05, AC-SRC-02)."""
import unicodedata

from src.backend.app.domain.search import SUGGEST_GROUPS, SuggestEntry, fold, is_suggestable, match_tier, suggest


def E(group, label, weight=0.0):
    return SuggestEntry(group, label, weight=weight, product_id=None if group == "destination" else label)


CATALOG = [
    E("destination", "Hà Nội", 214), E("destination", "Hạ Long", 96), E("destination", "Nha Trang", 342),
    E("hotel", "Vinpearl Resort & Spa Hạ Long", 9), E("hotel", "Hà Nội Capital Garden Hotel", 2),
    E("hotel", "Vinpearl Resort Nha Trang", 8),
    E("attraction", "Đêm nhạc Ký ức Hà Nội", 5), E("attraction", "VinWonders Nha Trang", 7),
    E("golf", "Vinpearl Golf Hải Phòng", 3), E("combo", "Combo Hà Nội – Hạ Long 3N2Đ", 4),
    E("flight", "Vé máy bay Hà Nội - Cam Ranh", 99),
]


def labels(q, limit=8, entries=CATALOG):
    return [e.label for e in suggest(entries, q, limit)]


def test_query_needs_two_letters_or_digits():
    assert not is_suggestable("") and not is_suggestable("   ") and not is_suggestable("h")
    assert not is_suggestable(" h ") and not is_suggestable("--") and not is_suggestable("à")
    assert is_suggestable("ha") and is_suggestable("3n") and is_suggestable("h a")
    assert labels("h") == [] and labels("   ") == [] and labels("ha", limit=0) == []


def test_matching_ignores_accents_and_case():
    assert labels("ha")[:2] == ["Hà Nội", "Hạ Long"]
    assert labels("HÀ NỘI")[0] == "Hà Nội"
    assert labels(unicodedata.normalize("NFD", "hạ long"))[0] == "Hạ Long"   # dấu tổ hợp vẫn khớp


def test_tiers_prefer_name_start_then_word_start_then_any_order():
    def tier(q, label):
        folded = fold(q)
        return match_tier(folded, tuple(folded.split()), E("hotel", label))

    assert tier("ha", "Hà Nội Capital Garden Hotel") == 0
    assert tier("ha long", "Vinpearl Resort & Spa Hạ Long") == 1
    assert tier("long vinpearl", "Vinpearl Resort & Spa Hạ Long") == 2
    assert tier("ha", "Đêm nhạc") is None            # không khớp giữa từ: "ha" không phải "nhạc"
    assert tier("ha noi tokyo", "Hà Nội Capital Garden Hotel") is None
    # Trong một nhóm, khớp ở đầu tên đứng trước dù kém phổ biến hơn.
    assert labels("ha")[2:4] == ["Hà Nội Capital Garden Hotel", "Vinpearl Resort & Spa Hạ Long"]


def test_results_follow_group_order_and_never_include_flights():
    found = suggest(CATALOG, "ha", 8)
    groups = [e.group for e in found]
    assert groups == sorted(groups, key=SUGGEST_GROUPS.index)
    assert "flight" not in groups and "Vé máy bay Hà Nội - Cam Ranh" not in [e.label for e in found]
    assert {"destination", "hotel", "attraction", "golf", "combo"} == set(groups)


def test_limit_is_shared_round_robin_across_groups():
    many = [E("destination", f"Hà {i}", i) for i in range(6)] + [E("hotel", f"Hà khách sạn {i}", i) for i in range(6)]
    found = suggest(many + [E("combo", "Hà combo")], "ha", 5)
    assert [e.group for e in found] == ["destination", "destination", "hotel", "hotel", "combo"]
    assert [e.label for e in found[:2]] == ["Hà 5", "Hà 4"]            # cùng tier thì phổ biến hơn đứng trước
    # Chỉ một nhóm khớp thì nhóm đó dùng hết chỗ.
    assert len(suggest(many, "ha khach", 4)) == 4
    assert len(suggest(many, "ha", 100)) == 12


def test_no_match_returns_empty():
    assert labels("tokyo") == []
