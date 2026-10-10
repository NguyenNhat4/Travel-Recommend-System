"""Toy tính tay cho scorer item-item (spec recsys-algos-v1 §1.3, §4, §5) và đẳng thức `star_blend_a1 ≡ content_profile`."""
from __future__ import annotations

import numpy as np
import pytest

from src.evaluation.recsys_bench.engine import OfflineEngine
from src.evaluation.recsys_bench.events import filter_events
from src.evaluation.recsys_bench.models.base import Seeds
from src.evaluation.recsys_bench.models.content import ContentProfile
from src.evaluation.recsys_bench.models.cooc import CoocTrip
from src.evaluation.recsys_bench.models.data import build
from src.evaluation.recsys_bench.models.ease import Ease
from src.evaluation.recsys_bench.models.funnel import AlgoArm, CtxCache, FunnelCfg
from src.evaluation.recsys_bench.models.itemitem import cooccurrence, cosine_shrink, row_from_topk, topk_rows
from src.evaluation.recsys_bench.models.rp3beta import Rp3Beta
from src.evaluation.recsys_bench.models.seeds import weighted_mean_rows
from src.evaluation.recsys_bench.models.star import StarBlend
from src.evaluation.recsys_bench.splits import leave_last_booking_out
from src.evaluation.recsys_bench.tests import synthetic_world as SW
from src.evaluation.recsys_bench.tests.test_arms_metrics import AS_OF

TOY = np.array([[1, 1, 0], [1, 1, 1], [1, 0, 1], [0, 1, 0]], dtype=np.uint8)     # 4 trip × 3 item (spec §1.3.1)


def test_cooccurrence_cosine_shrink_hand_values():
    G, n = cooccurrence(TOY)
    assert n.tolist() == [3, 3, 2] and G[0, 1] == 2 and G[0, 2] == 2 and G[1, 2] == 1 and np.diag(G).tolist() == [0, 0, 0]
    R = cosine_shrink(G, n, beta=5.0)
    assert np.allclose(R, R.T) and np.diag(R).tolist() == [0, 0, 0]
    assert abs(R[0, 1] - 2 / 3 * 2 / 7) < 1e-9 and abs(R[0, 1] - 0.1905) < 5e-4
    assert abs(R[0, 2] - 2 / np.sqrt(6) * 2 / 7) < 1e-9 and abs(R[0, 2] - 0.2333) < 5e-4
    assert abs(R[1, 2] - 1 / np.sqrt(6) * 1 / 6) < 1e-9 and abs(R[1, 2] - 0.0680) < 5e-4
    pure = cosine_shrink(G, n, beta=0.0)                                   # β = 0 → cosine thuần (= itemknn)
    assert abs(pure[0, 1] - 2 / 3) < 1e-12 and abs(pure[1, 2] - 1 / np.sqrt(6)) < 1e-12
    # item cô lập: thêm cột 0 → hàng/cột R = 0, không lỗi, không láng giềng
    B4 = np.hstack([TOY, np.zeros((4, 1), dtype=np.uint8)])
    G4, n4 = cooccurrence(B4)
    R4 = cosine_shrink(G4, n4, 5.0)
    assert n4[3] == 0 and R4[3].sum() == 0 and R4[:, 3].sum() == 0
    idx, val = topk_rows(R4, G4, 50)
    assert (idx[3] == -1).all() and row_from_topk(idx, val, 4, 3) is None


def test_topk_rows_cut_and_tiebreak_co_then_id():
    R = np.array([[0, 0.5, 0.5, 0.5, 0.1], [0.5, 0, 0, 0, 0], [0.5, 0, 0, 0, 0], [0.5, 0, 0, 0, 0], [0.1, 0, 0, 0, 0]])
    G = np.array([[0, 2, 3, 3, 1], [2, 0, 0, 0, 0], [3, 0, 0, 0, 0], [3, 0, 0, 0, 0], [1, 0, 0, 0, 0]], dtype=float)
    idx, val = topk_rows(R, G, 2)
    assert idx[0].tolist() == [2, 3] and np.allclose(val[0], [0.5, 0.5])      # hoà R → co lớn hơn (3) → id nhỏ hơn (2 trước 3)
    idx1, _ = topk_rows(R, G, 10)
    assert idx1.shape[1] == 4 and idx1[0].tolist() == [2, 3, 1, 4] and idx1[1].tolist() == [0, -1, -1, -1]   # k bị chặn ở I−1 = 4


def test_weighted_mean_rows_and_cooc_scorer_on_toy():
    class _Data:
        B = TOY; n_items = 3

    cooc = CoocTrip(beta=5.0, top_k=50)
    log = cooc.fit(_Data())
    assert log["nRows"] == 4 and log["nnzPairs"] == 3 and log["itemsWithNeighbour"] == 1.0 and log["params"] == {"beta": 5.0, "topK": 50}
    seeds = Seeds(np.array([0]), np.array([1.0], dtype=np.float32), "short")
    s = weighted_mean_rows(cooc.row, seeds, np.array([0, 1, 2]))
    assert np.allclose(s, [0.0, 2 / 3 * 2 / 7, 2 / np.sqrt(6) * 2 / 7], atol=1e-6)
    two = Seeds(np.array([0, 1]), np.array([1.0, 3.0], dtype=np.float32), "short")       # trung bình có trọng số, không max/tổng
    s2 = weighted_mean_rows(cooc.row, two, np.array([2]))
    assert abs(s2[0] - (1.0 * cooc.row(0)[2] + 3.0 * cooc.row(1)[2]) / 4.0) < 1e-6
    assert weighted_mean_rows(cooc.row, Seeds(np.zeros(0, int), np.zeros(0, np.float32), "none"), np.array([0, 1])).tolist() == [0, 0]
    lonely = Seeds(np.array([0]), np.array([1.0], dtype=np.float32), "short")
    cooc4 = CoocTrip(beta=5.0, top_k=50)
    cooc4.fit(type("D", (), {"B": np.hstack([TOY, np.zeros((4, 1), np.uint8)]), "n_items": 4})())
    assert weighted_mean_rows(cooc4.row, Seeds(np.array([3]), np.array([1.0], np.float32), "short"), np.array([0, 1, 2, 3])).sum() == 0
    assert weighted_mean_rows(cooc4.row, lonely, np.array([3]))[0] == 0


def test_ease_closed_form_diag_zero_and_row_permutation_invariant():
    W, diag_g = Ease.closed_form(TOY, lam=2.0)
    G = TOY.astype(float).T @ TOY.astype(float)
    P = np.linalg.inv(G + 2.0 * np.eye(3))
    expected = -P / np.diag(P)[None, :]
    np.fill_diagonal(expected, 0.0)
    assert np.allclose(W, expected, atol=1e-9) and np.diag(W).tolist() == [0, 0, 0] and diag_g.tolist() == [3, 3, 2]
    W2, _ = Ease.closed_form(TOY[[3, 1, 0, 2]], lam=2.0)
    assert np.allclose(W, W2, atol=1e-12)
    ease = Ease(lam=200.0)
    log = ease.fit(type("D", (), {"B": TOY, "n_items": 3})())
    assert log["maxDiagG"] == 3 and log["medianDiagG"] == 3 and log["itemsWithInteraction"] == 3
    assert ease.W.shape == (3, 3) and (np.abs(ease.W) < 0.02).all()            # λ ≫ G → B_ease ≈ G/λ


def test_rp3beta_transition_shape_nonneg_diag_zero():
    W = Rp3Beta.transition(TOY, alpha=1.0, beta=0.6)
    assert W.shape == (3, 3) and (W >= 0).all() and np.diag(W).tolist() == [0, 0, 0]
    r = Rp3Beta(top_k=50)
    log = r.fit(type("D", (), {"B": TOY, "n_items": 3})())
    assert log["params"]["beta"] == 0.6 and r.row(0) is not None


def test_star_blend_a1_equals_content_profile_all_knobs(world, events):
    index, vs = world["index"], world["vectors"]
    kept, _ = filter_events(events, index, AS_OF)
    split = leave_last_booking_out(kept, index)
    engine = OfflineEngine(index, vs, split.train_purchases)
    data = build(kept, split, index, vs)
    ctx = CtxCache(data, engine)
    content, star1, star5 = ContentProfile(), StarBlend(a=1.0), StarBlend(a=0.5)
    for s in (content, star1, star5):
        s.fit(data)
    for pool in ("engine", "mask"):
        for rerank in ("none", "mmr"):
            cfg = FunnelCfg(pool=pool, rerank=rerank)
            a, b = AlgoArm("content_profile", content, cfg, ctx, vs), AlgoArm("star_blend_a1", star1, cfg, ctx, vs)
            for u in split.targets:
                ra, rb = a.recommend(u, split.as_of_by_user[u], 20, split.train_by_user[u]), b.recommend(u, split.as_of_by_user[u], 20, split.train_by_user[u])
                assert ra.product_ids == rb.product_ids, (pool, rerank, u)
                assert "collabCoverage" in rb.meta and "collabCoverage" not in ra.meta
    u = "u1"
    c = ctx.get(u, split.as_of_by_user[u], split.train_by_user[u])
    cand = np.flatnonzero(index.mask(only_recommendable=True))
    assert np.array_equal(star1.score(c, cand), content.score(c, cand))        # a = 1 → bit-exact
    with pytest.raises(ValueError):
        StarBlend(blend_scope="outer")


def test_star_blend_on_synthetic_world_runs_and_collab_coverage_defined():
    index, vs = SW.build_world()
    events = SW.build_events(index)
    kept, _ = filter_events(events, index, SW.AS_OF)
    split = leave_last_booking_out(kept, index)
    engine = OfflineEngine(index, vs, split.train_purchases, candidate_k=10, popular_k=3)
    data = build(kept, split, index, vs)
    ctx = CtxCache(data, engine)
    star = StarBlend(a=0.5)
    log = star.fit(data)
    assert log["nRows"] == data.B.shape[0] and 0.0 <= log["itemsWithNeighbour"] <= 1.0
    arm = AlgoArm("star_blend", star, FunnelCfg(pool="mask", rerank="none", pool_k=10, popular_k=3), ctx, vs)
    covs = [arm.recommend(u, split.as_of_by_user[u], 20, split.train_by_user[u]).meta.get("collabCoverage") for u in split.targets]
    assert all(c is None or 0.0 <= c <= 1.0 for c in covs) and any(c is not None for c in covs)
