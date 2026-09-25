import numpy as np

from src.backend.app.domain.search import HybridConfig, candidate_filter_score, hybrid_filter_score, rrf

FACETS = {"taxonomy": np.array(["hotel", "hotel", "attraction", "combo"])}
CFG = HybridConfig(lexical_k=10, lexical_cutoff=0.50)


def test_rrf_sums_over_legs_present():
    f = rrf({0: 1, 1: 2}, {1: 1, 2: 1}, k=60)
    assert f == {0: 1 / 61, 1: 1 / 62 + 1 / 61, 2: 1 / 61}


def test_dense_kept_above_cutoff_and_lexical_rescued_by_floor():
    cos = {0: 0.80, 1: 0.70, 2: 0.55, 3: 0.45}
    dense = {0: 1, 1: 2, 2: 3, 3: 4}
    lex = {2: 1, 3: 2}
    out = hybrid_filter_score(cos, dense, lex, lambda u: True, 0.62, CFG, 4, FACETS)
    assert set(out.order) == {0, 1, 2} and out.lexical_only == frozenset({2})  # 3: cosine 0.45 < lexicalCutoff
    assert out.total == 3 == sum(out.facets["taxonomy"].values()) and out.filtered_count == 4
    assert out.scores[2] == 0.55  # score vẫn là cosine, không phải điểm RRF
    assert out.order[0] == 2  # có mặt ở cả hai nhánh → RRF cao nhất dù cosine thấp hơn 0 và 1


def test_lexical_rank_and_admissibility_guards():
    cos = {0: 0.55, 1: 0.58}
    lex = {0: 1, 1: 11}
    assert hybrid_filter_score(cos, {}, lex, lambda u: True, 0.62, CFG, 2, FACETS).order == [0]  # rank 11 > lexicalK
    assert hybrid_filter_score(cos, {}, lex, lambda u: False, 0.62, CFG, 2, FACETS).order == []  # tên không hiếm
    assert hybrid_filter_score({}, {}, {0: 1}, lambda u: True, 0.62, CFG, 2, FACETS).order == []  # không có cosine


def test_lexical_k_zero_gives_candidate_filter_score_set():
    cos = {0: 0.9, 1: 0.7, 2: 0.3}
    a = hybrid_filter_score(cos, {0: 1, 1: 2, 2: 3}, {1: 1, 2: 2}, lambda u: True, 0.62,
                            HybridConfig(lexical_k=0), 3, FACETS)
    b = candidate_filter_score([0, 1, 2], [0.9, 0.7, 0.3], 0.62, 3, FACETS)
    assert set(a.order) == set(b.order) and a.facets == b.facets and a.lexical_only == frozenset()
    assert a.order == [1, 0]  # 1 có cả hai nhánh nên xếp trước 0 dù cosine thấp hơn
