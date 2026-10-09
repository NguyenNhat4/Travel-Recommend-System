"""`cooc_trip` — co-occurrence theo chuyến, cosine × shrinkage, top-K theo hàng (spec `recsys-algos-v1.md` §1)."""
from __future__ import annotations

from time import perf_counter

import numpy as np

from . import because
from .base import TrainData, UserCtx
from .itemitem import cooccurrence, cosine_shrink, neighbour_stats, row_from_topk, topk_rows
from .seeds import weighted_mean_rows


class CoocTrip:
    name = "cooc_trip"
    needs_vectors = False
    rows = "trip"

    def __init__(self, beta: float = 5.0, top_k: int = 50):
        self.beta, self.top_k = float(beta), int(top_k)
        self.idx: np.ndarray | None = None
        self.val: np.ndarray | None = None
        self.n_items = 0

    def fit(self, data: TrainData) -> dict:
        t0 = perf_counter()
        G, n = cooccurrence(data.B)
        R = cosine_shrink(G, n, self.beta)
        self.idx, self.val = topk_rows(R, G, self.top_k)
        self.n_items = data.n_items
        return {"params": {"beta": self.beta, "topK": self.top_k}, "rows": "trip", "nRows": int(data.B.shape[0]),
                "nnzB": int(data.B.sum()), **neighbour_stats(G, self.idx, self.val), "fitSeconds": round(perf_counter() - t0, 3)}

    def row(self, s: int) -> np.ndarray | None:
        assert self.idx is not None, "gọi fit() trước"
        return row_from_topk(self.idx, self.val, self.n_items, s)

    def score(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray:
        return weighted_mean_rows(self.row, ctx.seeds, cand)

    def collab_part(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray | None:
        return self.score(ctx, cand)

    def explain(self, ctx: UserCtx, items: np.ndarray) -> list[list[dict]]:
        """because[]: `c_e·T[e, x]/Z` theo event (spec §1.2), kind cooc; phần âm bị loại."""
        return because.from_rows(self.row, ctx.profile, items, kind="cooc")
