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


# --- nhánh fuzzy + trọng số (kiến trúc §7 5C, §8): mặc định phải y hệt bản hai nhánh
def _legacy_rrf(dense_rank, lexical_rank, k=60):
    out = {}
    for ranks in (dense_rank, lexical_rank):
        for u, r in ranks.items():
            out[u] = out.get(u, 0.0) + 1.0 / (k + r)
    return out


def _legacy_hybrid(cosines, dense_rank, lexical_rank, admissible, cutoff, cfg):
    kept_dense = {u for u, c in cosines.items() if c >= cutoff}
    kept_lex = {u for u, r in lexical_rank.items()
                if u not in kept_dense and r <= cfg.lexical_k and cosines.get(u, -1.0) >= cfg.lexical_cutoff and admissible(u)}
    fused = _legacy_rrf(dense_rank, lexical_rank, cfg.rrf_k)
    kept = kept_dense | kept_lex
    return sorted(kept, key=lambda u: (-fused.get(u, 0.0), -cosines[u], u)), kept_lex


def test_new_config_fields_default_off():
    cfg = HybridConfig()
    assert (cfg.fuzzy_k, cfg.fuzzy_candidate_k, cfg.fuzzy_min_sim) == (0, 50, 0.6)
    assert (cfg.dense_weight, cfg.lexical_weight, cfg.fuzzy_weight) == (1.0, 1.0, 1.0)


def test_default_weights_and_no_fuzzy_identical_to_legacy():
    rng = np.random.default_rng(3)
    facets = {"taxonomy": np.array(["hotel"] * 40)}
    for _ in range(200):
        n = 40
        cos = {int(u): float(c) for u, c in zip(rng.choice(n, 25, replace=False), rng.uniform(0.2, 0.95, 25))}
        dense_units = [u for u in cos if rng.random() < 0.7]
        dense = {u: r for r, u in enumerate(dense_units, 1)}
        lex_units = [int(u) for u in rng.choice(n, 15, replace=False)]
        lex = {u: r for r, u in enumerate(lex_units, 1)}
        adm = set(int(u) for u in rng.choice(n, 20, replace=False))
        cfg = HybridConfig(lexical_k=int(rng.integers(0, 15)), lexical_cutoff=float(rng.uniform(0.3, 0.7)))
        assert rrf(dense, lex, 60) == _legacy_rrf(dense, lex, 60)
        assert rrf(dense, lex, 60, fuzzy_rank=None, dense_weight=1.0, lexical_weight=1.0) == _legacy_rrf(dense, lex, 60)
        out = hybrid_filter_score(cos, dense, lex, lambda u: u in adm, 0.62, cfg, n, facets)
        order, kept_lex = _legacy_hybrid(cos, dense, lex, lambda u: u in adm, 0.62, cfg)
        assert out.order == order and out.lexical_only == frozenset(kept_lex) and out.fuzzy_only == frozenset()
        # fuzzy_k = 0 → rank fuzzy truyền vào cũng bị bỏ qua (kênh tắt)
        fz = {u: r for r, u in enumerate(range(n), 1)}
        off = hybrid_filter_score(cos, dense, lex, lambda u: u in adm, 0.62, cfg, n, facets, fuzzy_rank=fz)
        assert off.order == order and off.fuzzy_only == frozenset()


def test_rrf_third_list_and_weights():
    f = rrf({0: 1}, {1: 1}, k=60, fuzzy_rank={0: 2, 2: 1})
    assert f == {0: 1 / 61 + 1 / 62, 1: 1 / 61, 2: 1 / 61}
    w = rrf({0: 1}, {1: 1}, k=60, fuzzy_rank={2: 1}, dense_weight=2.0, lexical_weight=0.5, fuzzy_weight=0.0)
    assert w == {0: 2 / 61, 1: 0.5 / 61}                      # nhánh trọng số 0 bị bỏ hẳn


def test_fuzzy_rescue_admission_guards():
    cfg = HybridConfig(lexical_k=10, lexical_cutoff=0.50, fuzzy_k=3)
    cos = {0: 0.80, 1: 0.55, 2: 0.55, 3: 0.45, 4: 0.58, 5: 0.56}
    dense = {0: 1}
    lex = {5: 1}                                               # 5: có ở BM25 nhưng tên không đủ độ phủ
    fuzzy = {1: 1, 3: 2, 4: 4, 2: 3, 5: 2, 6: 1}               # 6: không có cosine → không vớt
    adm_fuzzy = {1, 3, 4, 5, 6}                                # 2: độ giống < fuzzy_min_sim
    out = hybrid_filter_score(cos, dense, lex, lambda u: False, 0.62, cfg, 7, {"taxonomy": np.array(["h"] * 7)},
                              fuzzy_rank=fuzzy, fuzzy_admissible=lambda u: u in adm_fuzzy)
    assert out.facets == {"taxonomy": {"h": 3}}
    # 1 vớt; 3 cosine < lexicalCutoff; 4 rank 4 > fuzzyK; 2 không admissible; 5 vớt nhờ fuzzy dù lexical không giữ; 6 thiếu cosine
    assert set(out.order) == {0, 1, 5} and out.fuzzy_only == frozenset({1, 5}) and out.lexical_only == frozenset()
    assert out.scores[1] == 0.55                               # score vẫn là cosine
    # thứ tự = RRF có trọng số trên mọi nhánh: 5 có lexical rank 1 + fuzzy rank 2 → đứng đầu
    assert out.order == [5, 0, 1]
    # fuzzy_admissible None = mọi unit đạt
    out2 = hybrid_filter_score(cos, dense, lex, lambda u: False, 0.62, cfg, 7, {}, fuzzy_rank=fuzzy)
    assert out2.fuzzy_only == frozenset({1, 2, 5})


def test_unit_kept_by_dense_or_lexical_is_not_fuzzy_only():
    cfg = HybridConfig(lexical_k=10, lexical_cutoff=0.50, fuzzy_k=10)
    cos = {0: 0.80, 1: 0.55}
    out = hybrid_filter_score(cos, {0: 1}, {1: 1}, lambda u: True, 0.62, cfg, 2, {}, fuzzy_rank={0: 1, 1: 2})
    assert out.fuzzy_only == frozenset() and out.lexical_only == frozenset({1})
    # fuzzy góp RRF cho unit đã có ở nhánh khác: 0 = 1/61 + 1/61, 1 = 1/61 + 1/62
    assert out.order == [0, 1]
    heavy = HybridConfig(lexical_k=10, lexical_cutoff=0.50, fuzzy_k=10, lexical_weight=3.0)
    assert hybrid_filter_score(cos, {0: 1}, {1: 1}, lambda u: True, 0.62, heavy, 2, {}, fuzzy_rank={0: 1, 1: 2}).order == [1, 0]
