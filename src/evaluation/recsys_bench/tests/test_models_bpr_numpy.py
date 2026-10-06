"""Day 5 Phase C — `bpr_numpy` / `bpr_dest`: khởi tạo, một bước SGD tính tay, sampler global / cùng destination, fit tất định, và
đối chứng cấu trúc với `implicit` (không so đẳng thức metric — luồng RNG khác nhau)."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from src.evaluation.recsys_bench.events import filter_events
from src.evaluation.recsys_bench.models.bpr_numpy import BprNumpy, DestinationPools, init_factors, sample_negatives, sgd_step
from src.evaluation.recsys_bench.models.data import build
from src.evaluation.recsys_bench.splits import leave_last_booking_out
from src.evaluation.recsys_bench.tests import synthetic_world as SW


def test_init_factors_shape_zero_rows_bias_and_determinism():
    uc, ic = np.array([2, 0, 1]), np.array([1, 0, 3, 0])
    X, Y = init_factors(np.random.default_rng(5), 3, 4, 8, uc, ic)
    assert X.shape == (3, 9) and Y.shape == (4, 9) and X.dtype == np.float32
    assert np.all(X[:, 8] == 1.0) and np.all(X[1, :8] == 0) and np.all(Y[[1, 3]] == 0)
    assert np.abs(Y).max() <= 0.5 / 8 + 1e-7
    X2, Y2 = init_factors(np.random.default_rng(5), 3, 4, 8, uc, ic)
    assert np.array_equal(X, X2) and np.array_equal(Y, Y2)


def test_sgd_step_hand_computed():
    X = np.array([[0.5, 1.0]], dtype=np.float32)
    Y = np.array([[0.2, 0.0], [-0.1, 0.0]], dtype=np.float32)
    correct = sgd_step(X, Y, 0, 0, 1, lr=0.1, reg=0.0)          # x̂ = 0,15 > 0 → z = σ(−0,15) = 0,46257 < 0,5: đã xếp đúng
    assert correct
    np.testing.assert_allclose(Y[0], [0.223128, 0.046257], atol=1e-5)
    np.testing.assert_allclose(Y[1], [-0.123128, -0.046257], atol=1e-5)
    np.testing.assert_allclose(X[0], [0.513877, 1.0], atol=1e-5)  # cột bias user không đổi
    X = np.array([[1.0, 1.0]], dtype=np.float32)
    Y = np.array([[-2.0, 0.0], [2.0, 0.0]], dtype=np.float32)
    assert not sgd_step(X, Y, 0, 0, 1, lr=0.0, reg=0.0)            # x̂ = −4 → z ≈ 0,98: xếp sai


def test_sampler_global_follows_nnz_and_skips_liked():
    liked = np.zeros((3, 6), dtype=bool)
    users = np.array([0, 0, 0, 1, 2, 2])
    items = np.array([0, 1, 1, 1, 1, 4])                          # item 1 phổ biến; item 2, 3, 5 không có ô nnz
    liked[users, items] = True
    rng = np.random.default_rng(0)
    n = 20_000
    u = np.full(n, 1)
    neg, keep, fb = sample_negatives(rng, u, np.full(n, 1), liked, kind="global", itemids_nnz=items)
    assert set(np.unique(neg)) <= {0, 1, 4} and not fb.any()
    assert abs(np.mean(neg == 1) - 4 / 6) < 0.02                   # theo tần suất nnz
    assert not keep[neg == 1].any() and keep[neg != 1].all()       # user 1 đã thích item 1 → bỏ mẫu
    with pytest.raises(ValueError):
        sample_negatives(rng, u, u, liked, kind="nope", itemids_nnz=items)


def _synthetic_data():
    index, vs = SW.build_world()
    kept, _ = filter_events(SW.build_events(index), index, SW.AS_OF)
    split = leave_last_booking_out(kept, index)
    return index, build(kept, split, index, vs)


def test_sampler_same_destination_stays_in_destination_fallback_and_resample():
    index, data = _synthetic_data()
    liked = data.U.astype(bool)
    users, items = (a.astype(np.int64) for a in np.nonzero(data.U))
    pools = DestinationPools(index.destination, items, "uniform")
    assert pools.n_dest == 3 and set(pools.size.tolist()) == {20}
    rng = np.random.default_rng(1)
    idx = rng.integers(0, len(users), size=5000)
    neg, keep, fb = sample_negatives(rng, users[idx], items[idx], liked, kind="same_destination", itemids_nnz=items, dest_pools=pools,
                                     min_dest_items=20, max_resample=10)
    assert not fb.any() and np.all(index.destination[neg] == index.destination[items[idx]])
    assert not liked[users[idx][keep], neg[keep]].any()            # mẫu giữ lại không bao giờ là item đã thích
    assert keep.mean() > 0.95                                      # rút lại tránh gần hết va chạm
    neg2, keep2, fb2 = sample_negatives(rng, users[idx], items[idx], liked, kind="same_destination", itemids_nnz=items,
                                        dest_pools=pools, min_dest_items=25)
    assert fb2.all() and set(np.unique(neg2)) <= set(items.tolist())   # destination 20 unit < 25 → lùi global (theo nnz)
    pop = DestinationPools(index.destination, items, "pop")
    neg3 = pop.draw(rng, items[idx])
    assert np.all(index.destination[neg3] == index.destination[items[idx]]) and set(np.unique(neg3)) <= set(items.tolist())


def test_fit_deterministic_bias_and_zero_items():
    index, data = _synthetic_data()
    a = BprNumpy(factors=8, iterations=20, seed=3)
    log = a.fit(data)
    b = BprNumpy(factors=8, iterations=20, seed=3)
    b.fit(data)
    assert np.array_equal(a.item_factors, b.item_factors) and np.array_equal(a.user_factors, b.user_factors)
    c = BprNumpy(factors=8, iterations=20, seed=4)
    c.fit(data)
    assert not np.array_equal(a.item_factors, c.item_factors)
    assert np.all(a.user_factors[:, 8] == 1.0) and log["nnzU"] == int(data.U.sum()) and 0 < log["trainAucLastEpoch"] <= 1
    zero_items = np.flatnonzero(data.U.sum(axis=0) == 0)
    assert len(zero_items) and np.all(a.item_factors[zero_items] == 0)          # global: item chưa ai tương tác không bị rút
    d = BprNumpy(factors=8, iterations=20, seed=3, negatives="same_destination")
    dlog = d.fit(data)
    assert np.any(d.item_factors[zero_items] != 0)                                # cùng destination: có bị rút (khác implicit, có chủ đích)
    assert dlog["destStats"]["nDestinations"] == 3 and dlog["destStats"]["sharePositivesFallback"] == 0.0
    assert d.explain(None, np.array([1, 2])) == [[], []]
    with pytest.raises(ValueError):
        BprNumpy(negatives="same_vertical")
    with pytest.raises(ValueError):
        BprNumpy(dest_distribution="zipf")


def _block_matrix(seed=0):
    rng = np.random.default_rng(seed)
    U = np.zeros((40, 20), dtype=np.uint8)
    for u in range(40):
        own, other = (range(0, 10), range(10, 20)) if u < 20 else (range(10, 20), range(0, 10))
        U[u, rng.choice(list(own), 5, replace=False)] = 1
        if rng.random() < 0.2:
            U[u, rng.choice(list(other))] = 1
    return U


def _in_block_share(U, user_factors, item_factors):
    ok = 0
    for u in range(U.shape[0]):
        s = item_factors @ user_factors[u]
        own = np.arange(0, 10) if u < 20 else np.arange(10, 20)
        unliked_own = [i for i in own if not U[u, i]]
        ok += s[unliked_own].mean() > s[np.setdiff1d(np.arange(20), own)].mean()
    return ok / U.shape[0]


def test_numpy_bpr_learns_block_structure_like_implicit():
    U = _block_matrix()
    data = SimpleNamespace(U=U, index=SimpleNamespace(destination=np.array(["A"] * 10 + ["B"] * 10)))
    m = BprNumpy(factors=8, learning_rate=0.05, iterations=100, seed=1)
    log = m.fit(data)
    assert log["trainAucLastEpoch"] >= 0.9 and _in_block_share(U, m.user_factors, m.item_factors) >= 0.9
    pytest.importorskip("implicit")
    from scipy.sparse import csr_matrix

    from src.evaluation.recsys_bench.models.mf_implicit import Bpr
    data.csr_U = lambda: csr_matrix(U.astype(np.float32))
    b = Bpr(factors=8, learning_rate=0.05, iterations=100, seed=1)
    b.fit(data)
    assert _in_block_share(U, np.asarray(b.model.user_factors), np.asarray(b.model.item_factors)) >= 0.9
