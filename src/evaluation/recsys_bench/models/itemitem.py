"""Hàm chung cho scorer item-item (spec `recsys-algos-v1.md` §1.1, §3, §5): co-occurrence, cosine × shrinkage, cắt top-K theo hàng.

Thuần numpy, float64 khi tính (I = 3.183 → 81 MB), lưu bảng láng giềng dạng `(I, K)` idx/val float32. Hoà khi cắt: `R` lớn hơn →
`co` lớn hơn → chỉ số item nhỏ hơn (`np.lexsort`, khoá cuối là khoá chính).
"""
from __future__ import annotations

import numpy as np


def cooccurrence(B: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """`C = BᵀB` (float64, diag = 0) và `n_i = Σ_t B[t, i]` (số hàng chứa i)."""
    Bf = np.asarray(B, dtype=np.float64)
    G = Bf.T @ Bf
    n = np.diag(G).copy()
    np.fill_diagonal(G, 0.0)
    return G, n


def cosine_shrink(G: np.ndarray, n: np.ndarray, beta: float) -> np.ndarray:
    """`R_C(i,j) = co_ij / √(n_i n_j) · co_ij / (co_ij + β)`; β = 0 → cosine thuần (= itemknn); cặp không đồng xuất hiện → 0."""
    denom = np.sqrt(np.outer(n, n))
    with np.errstate(divide="ignore", invalid="ignore"):
        R = np.where(denom > 0, G / denom, 0.0)
        if beta > 0:
            R = R * np.where(G > 0, G / (G + beta), 0.0)
    np.fill_diagonal(R, 0.0)
    return R


def topk_rows(R: np.ndarray, tie: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Với mỗi hàng i giữ ≤ k cột có `R` lớn nhất (> 0); hoà → `tie[i, j]` lớn hơn (thường là co_ij) → j nhỏ hơn.
    Trả `(idx int32 (I, k), val float32 (I, k))`, ô thừa `idx = -1`, `val = 0`."""
    n_items = R.shape[0]
    k = max(0, min(k, n_items - 1))
    idx = np.full((n_items, k), -1, dtype=np.int32)
    val = np.zeros((n_items, k), dtype=np.float32)
    cols = np.arange(n_items)
    for i in range(n_items):
        positive = np.flatnonzero(R[i] > 0)
        if positive.size == 0:
            continue
        order = positive[np.lexsort((cols[positive], -tie[i, positive], -R[i, positive]))][:k]
        idx[i, : order.size] = order
        val[i, : order.size] = R[i, order]
    return idx, val


def row_from_topk(idx: np.ndarray, val: np.ndarray, n_items: int, s: int) -> np.ndarray | None:
    """Hàng đầy đủ (I,) của seed s từ bảng (idx, val); None khi s không có láng giềng."""
    keep = idx[s] >= 0
    if not keep.any():
        return None
    row = np.zeros(n_items, dtype=np.float32)
    row[idx[s][keep]] = val[s][keep]
    return row


def neighbour_stats(G: np.ndarray, idx: np.ndarray, val: np.ndarray) -> dict:
    positive = val[idx >= 0]
    pct = {f"p{q}": float(np.percentile(positive, q)) for q in (50, 90, 99)} if positive.size else {}
    return {"nnzPairs": int(np.count_nonzero(G) // 2), "itemsWithNeighbour": float(np.mean((idx >= 0).any(axis=1))) if idx.size else 0.0,
            "neighboursPerItemMean": float(np.mean((idx >= 0).sum(axis=1))) if idx.size else 0.0, "valuePercentiles": pct}
