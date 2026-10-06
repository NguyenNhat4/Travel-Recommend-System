"""Kênh fuzzy / alias (`domain/search/fuzzy.py`, kiến trúc §7 5C): trigram kiểu pg_trgm, so tên với cửa sổ token của câu."""
import random
from time import perf_counter

import numpy as np
import pytest

from src.backend.app.domain.search.fuzzy import FuzzyIndex, similarity, trigrams, window_similarity, word_trigrams

NAMES = [
    "Vinpearl Resort Nha Trang",          # 0
    "VinWonders Nha Trang",               # 1
    "Khách sạn B Nha Trang",              # 2
    "Resort Phú Quốc",                    # 3
    "",                                   # 4 — tên rỗng: không bao giờ khớp
    "Vinpearl Resort & Spa Hạ Long",      # 5
    "VinWonders Phú Quốc",                # 6
]


@pytest.fixture(scope="module")
def ix() -> FuzzyIndex:
    return FuzzyIndex.build(NAMES)


# --- trigram như pg_trgm
def test_word_trigrams_padded_like_pg_trgm():
    assert word_trigrams("cat") == {"  c", " ca", "cat", "at "}
    assert word_trigrams("a") == {"  a", " a "}
    assert trigrams("Đà Lạt") == word_trigrams("da") | word_trigrams("lat")   # fold: bỏ dấu, đ → d, chữ thường
    assert trigrams("") == frozenset() and trigrams("!!") == frozenset()


def test_similarity_is_jaccard_of_sets():
    assert similarity("Nha Trang", "nha trang") == 1.0
    assert similarity("", "nha trang") == 0.0
    a, b = trigrams("vinpearl"), trigrams("vinpeal")
    assert similarity("vinpearl", "vinpeal") == pytest.approx(len(a & b) / len(a | b))


# --- cửa sổ
def test_window_finds_misspelled_name_inside_long_query():
    q = "Vinpeal Resort Nha Trnag gia tot"
    name = "Vinpearl Resort Nha Trang"
    assert window_similarity(name, q) > similarity(name, q)        # phần thừa "gia tot" không kéo điểm xuống
    assert window_similarity(name, q) >= 0.6
    assert window_similarity(name, "khach san Vinpearl Resort Nha Trang") == 1.0    # tên đúng nằm giữa câu


def test_window_length_is_name_tokens_plus_minus_one():
    # tên 4 token; cửa sổ 3..5 token. Câu 2 token (< 4 − 1) → so với cả câu
    assert window_similarity("Vinpearl Resort Nha Trang", "nha trang") == pytest.approx(
        similarity("Vinpearl Resort Nha Trang", "nha trang"))
    # tên 1 token chỉ so với cửa sổ 1–2 token: khớp đúng một token của câu dài
    assert window_similarity("VinWonders", "ve vinwonders nha trang re") == 1.0
    assert window_similarity("x", "") == 0.0 and window_similarity("", "nha trang") == 0.0


# --- FuzzyIndex.search
def test_typo_name_ranks_first(ix):
    got = ix.search("Vinpeal Resort Nha Trnag gia tot", None, 3)
    assert got[0][0] == 0 and got[0][1] == pytest.approx(window_similarity(NAMES[0], "Vinpeal Resort Nha Trnag gia tot"))
    got = ix.search("vinwoder nha trang", None, 3)
    assert got[0][0] == 1 and got[0][1] >= 0.6


def test_results_sorted_desc_ties_by_index_and_in_unit_interval(ix):
    got = ix.search("resort nha trang phu quoc", None, 10)
    sims = [s for _, s in got]
    assert sims == sorted(sims, reverse=True) and all(0.0 < s <= 1.0 for s in sims)
    assert 4 not in [u for u, _ in got]                                           # tên rỗng
    for (u1, s1), (u2, s2) in zip(got, got[1:]):
        assert s1 > s2 or (s1 == s2 and u1 < u2)
    # "Nha Trang" khớp đúng cửa sổ "nha trang" → cũng 1.0; hoà → index nhỏ trước
    dup = FuzzyIndex.build(["VinWonders Nha Trang", "Nha Trang", "VinWonders Nha Trang", "Nha Trang Bay"])
    assert dup.search("vinwonders nha trang", None, 3) == [(0, 1.0), (1, 1.0), (2, 1.0)]


def test_allowed_mask_respected(ix):
    allowed = np.ones(len(NAMES), dtype=bool)
    allowed[0] = False
    got = ix.search("Vinpeal Resort Nha Trnag", allowed, 5)
    assert 0 not in [u for u, _ in got] and got
    assert ix.search("Vinpeal Resort Nha Trnag", np.zeros(len(NAMES), dtype=bool), 5) == []


def test_k_min_sim_and_empty_inputs(ix):
    assert len(ix.search("vinpearl vinwonders nha trang phu quoc", None, 2)) == 2
    assert ix.search("nha trang", None, 0) == [] and ix.search("", None, 5) == [] and ix.search("!!!", None, 5) == []
    assert all(s >= 0.6 for _, s in ix.search("resort nha trang", None, 10, min_sim=0.6))
    assert FuzzyIndex.build([]).search("nha trang", None, 5) == [] and len(FuzzyIndex.build([])) == 0
    assert len(ix) == len(NAMES)


def _brute(names, query, k):
    sims = [(i, window_similarity(n, query)) for i, n in enumerate(names)]
    return sorted([x for x in sims if x[1] > 0], key=lambda x: (-x[1], x[0]))[:k]


def _synthetic_names(n: int, seed: int = 7) -> list[str]:
    rng = random.Random(seed)
    heads = ["Vinpearl", "VinWonders", "Mường Thanh", "Khách sạn", "Resort", "Homestay", "Villa", "Combo", "Sân golf", "Vé"]
    mids = ["Beachfront", "Grand", "Luxury", "Ocean", "Riverside", "Central", "Garden", "Sunrise", "Palace", "Boutique"]
    places = ["Nha Trang", "Phú Quốc", "Đà Nẵng", "Hội An", "Hạ Long", "Đà Lạt", "Sa Pa", "Quy Nhơn", "Vũng Tàu", "Huế"]
    return [f"{rng.choice(heads)} {rng.choice(mids)} {rng.choice(places)} {rng.randint(1, 999)}" for _ in range(n)]


def test_matches_brute_force_within_shortlist():
    names = _synthetic_names(400)
    fx = FuzzyIndex.build(names)
    for q in ("vinpeal grand nha trnag", "khach san ocean da nang 12", "resort hoi an gia re", "villa sa pa"):
        assert fx.search(q, None, 10, shortlist=len(names)) == _brute(names, q, 10)


def test_speed_on_3000_names():
    names = _synthetic_names(3000)
    t0 = perf_counter()
    fx = FuzzyIndex.build(names)
    build_s = perf_counter() - t0
    queries = ["vinpeal grand nha trnag gia tot", "khach san gan bien da nang", "villa sa pa cho gia dinh",
               "muong thanh luxury ha long", "combo ve may bay phu quoc"]
    fx.search(queries[0], None, 50)   # khởi động cache trigram
    t0 = perf_counter()
    for q in queries * 4:
        fx.search(q, None, 50)
    per_query = (perf_counter() - t0) / (len(queries) * 4)
    assert per_query < 0.05, per_query
    assert build_s < 2.0, build_s
