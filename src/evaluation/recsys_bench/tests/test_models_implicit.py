"""Scorer dùng `implicit` (spec recsys-algos-v1 §3, §6) — skip khi chưa cài; `cooc_trip(β=0) ≡ itemknn`, iALS/BPR tất định theo seed."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("implicit")
pytest.importorskip("scipy")

from src.evaluation.recsys_bench.models.base import Seeds  # noqa: E402
from src.evaluation.recsys_bench.models.cooc import CoocTrip  # noqa: E402
from src.evaluation.recsys_bench.models.knn_implicit import ItemKnn  # noqa: E402
from src.evaluation.recsys_bench.models.mf_implicit import Bpr, Ials  # noqa: E402

TOY = np.array([[1, 1, 0], [1, 1, 1], [1, 0, 1], [0, 1, 0]], dtype=np.uint8)


def _data(B=None, U=None):
    from scipy.sparse import csr_matrix
    ns = SimpleNamespace(B=B if B is not None else TOY, U=U if U is not None else TOY, n_items=(B if B is not None else TOY).shape[1])
    ns.csr_B = lambda: csr_matrix(ns.B.astype(np.float32))
    ns.csr_U = lambda: csr_matrix(ns.U.astype(np.float32))
    return ns


def test_itemknn_equals_cooc_beta0_when_k_plus_one_covers_all():
    data = _data()
    knn = ItemKnn(k=2)
    log = knn.fit(data)
    cooc = CoocTrip(beta=0.0, top_k=2)
    cooc.fit(data)
    for s in range(3):
        a, b = knn.row(s), cooc.row(s)
        assert a is not None and b is not None
        assert np.allclose(a, b, atol=1e-6), (s, a, b)
    assert log["params"] == {"k": 2, "K_fit": 3} and log["itemsWithNeighbour"] == 1.0 and log["implicitVersion"]
    seeds = Seeds(np.array([0]), np.array([1.0], dtype=np.float32), "short")
    ctx = SimpleNamespace(seeds=seeds)
    assert np.allclose(knn.score(ctx, np.array([0, 1, 2])), [0.0, 2 / 3, 2 / np.sqrt(6)], atol=1e-6)


def test_ials_and_bpr_deterministic_by_seed_and_shapes():
    rng = np.random.default_rng(3)
    U = (rng.random((20, 10)) < 0.35).astype(np.uint8)
    U[np.arange(10), np.arange(10)] = 1          # mọi item có ≥ 1 tương tác
    U[:, 0] = 1
    data = _data(U=U)
    a, b = Ials(factors=4, iterations=3, alpha=40, seed=1), Ials(factors=4, iterations=3, alpha=40, seed=1)
    la, lb = a.fit(data), b.fit(data)
    assert np.allclose(a.item_factors, b.item_factors) and la["params"]["alpha"] == 40 and la["itemFactorShape"] == [10, 4] and la["nRows"] == 20
    ctx = SimpleNamespace(user_row=0)
    s = a.score(ctx, np.array([0, 1, 2]))
    assert s.shape == (3,) and s.dtype == np.float32 and np.allclose(s, b.score(ctx, np.array([0, 1, 2])))
    assert a.score(SimpleNamespace(user_row=None), np.array([0, 1])).tolist() == [0.0, 0.0] and a.collab_part(ctx, np.array([0])) is None
    c, d = Bpr(factors=4, iterations=5, seed=2), Bpr(factors=4, iterations=5, seed=2)
    c.fit(data), d.fit(data)
    assert c.item_factors.shape == (10, 5) and np.allclose(c.item_factors, d.item_factors)      # factors + 1 cột bias
    assert c.score(ctx, np.array([0, 1, 2])).shape == (3,)
    with pytest.raises(ValueError, match="negatives"):
        Bpr(negatives="same_destination")
    other = Ials(factors=4, iterations=3, alpha=40, seed=9)
    other.fit(data)
    assert not np.allclose(other.item_factors, a.item_factors)
