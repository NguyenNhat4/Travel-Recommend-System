"""Part 4 — top-k theo khối (nhiều khối, có mask) trùng vòng lặp ngây thơ; vector fp16 chia norm."""
from __future__ import annotations

import numpy as np

from evaluation.vector_bench.groundtruth import _same_topk, naive_topk, topk_exact


def test_chunked_topk_matches_naive_multi_chunk():
    rng = np.random.default_rng(1)
    v = rng.normal(size=(503, 32)).astype(np.float16)            # norm ≠ 1 → phải chia norm
    q = rng.normal(size=(9, 32)).astype(np.float16)
    masks = [None, rng.random(503) < 0.5, rng.random(503) < 0.02, np.zeros(503, bool), None, rng.random(503) < 0.9,
             rng.random(503) < 0.01, None, rng.random(503) < 0.3]
    rows, scores = topk_exact(v, q, k=20, chunk_rows=37, masks=masks)
    for i in range(len(q)):
        nr, ns = naive_topk(v, q[i], 20, masks[i])
        assert _same_topk(rows[i], scores[i], nr, ns), i
        if masks[i] is not None:
            got = rows[i][rows[i] >= 0]
            assert masks[i][got].all()                                # không trả dòng ngoài tập lọc
            assert len(got) == min(20, int(masks[i].sum()))           # trống thì −1 / NaN
    assert (rows[3] == -1).all() and np.isnan(scores[3]).all()


def test_scores_sorted_desc():
    rng = np.random.default_rng(2)
    v = rng.normal(size=(300, 16)).astype(np.float16)
    rows, scores = topk_exact(v, v[:5], k=10, chunk_rows=64)
    assert (np.diff(scores, axis=1) <= 1e-7).all()
    assert (rows[:, 0] == np.arange(5)).all()                         # chính nó đứng đầu
