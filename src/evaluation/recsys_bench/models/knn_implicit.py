"""`itemknn` — `implicit.nearest_neighbours.CosineRecommender` trên ma trận trip × item (spec `recsys-algos-v1.md` §3).

= `cooc_trip` với β = 0 (ablation của shrinkage). `.similarity` của implicit chứa chính item nên fit với `K = k + 1` rồi bỏ đường chéo.
`implicit`/`scipy` import lười; thiếu lib → lỗi rõ ở `fit`, phần numpy của run vẫn chạy.
"""
from __future__ import annotations

from time import perf_counter

import numpy as np

from .base import TrainData, UserCtx
from .seeds import weighted_mean_rows


def require_implicit():
    try:
        import implicit  # noqa: F401
        import scipy  # noqa: F401
    except ImportError as exc:  # pragma: no cover - phụ thuộc môi trường
        raise RuntimeError("scorer cần `implicit` + `scipy` (pip install -r src/evaluation/requirements.txt)") from exc
    return implicit


class ItemKnn:
    name = "itemknn"
    needs_vectors = False
    rows = "trip"

    def __init__(self, k: int = 50):
        self.k = int(k)
        self.S = None
        self.n_items = 0

    def fit(self, data: TrainData) -> dict:
        implicit = require_implicit()
        from implicit.nearest_neighbours import CosineRecommender
        t0 = perf_counter()
        model = CosineRecommender(K=self.k + 1)
        model.fit(data.csr_B(), show_progress=False)
        S = model.similarity.tocsr().astype(np.float32)
        S.setdiag(0.0)
        S.eliminate_zeros()
        self.S, self.n_items = S, data.n_items
        per_row = np.diff(S.indptr)
        return {"params": {"k": self.k, "K_fit": self.k + 1}, "rows": "trip", "nRows": int(data.B.shape[0]), "nnzB": int(data.B.sum()),
                "nnzSimilarity": int(S.nnz), "itemsWithNeighbour": float(np.mean(per_row > 0)) if per_row.size else 0.0,
                "neighboursPerItemMean": float(per_row.mean()) if per_row.size else 0.0, "implicitVersion": implicit.__version__,
                "fitSeconds": round(perf_counter() - t0, 3)}

    def row(self, s: int) -> np.ndarray | None:
        assert self.S is not None, "gọi fit() trước"
        r = self.S.getrow(s)
        if r.nnz == 0:
            return None
        return np.asarray(r.todense()).ravel().astype(np.float32)

    def score(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray:
        return weighted_mean_rows(self.row, ctx.seeds, cand)

    def collab_part(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray | None:
        return self.score(ctx, cand)
