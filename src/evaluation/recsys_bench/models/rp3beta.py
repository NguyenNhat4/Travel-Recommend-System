"""`rp3beta` — Tier 2 (spec `recsys-algos-v1.md` §5): `W = (P_iuᵀ P_ui)^α / deg(j)^β`, top-K theo hàng, diag 0. Thuần numpy."""
from __future__ import annotations

from time import perf_counter

import numpy as np

from . import because
from .base import TrainData, UserCtx
from .itemitem import neighbour_stats, row_from_topk, topk_rows
from .seeds import weighted_mean_rows


class Rp3Beta:
    name = "rp3beta"
    needs_vectors = False
    rows = "trip"

    def __init__(self, alpha: float = 1.0, beta: float = 0.6, top_k: int = 50):
        self.alpha, self.beta, self.top_k = float(alpha), float(beta), int(top_k)
        self.idx = self.val = None
        self.n_items = 0

    @staticmethod
    def transition(B: np.ndarray, alpha: float, beta: float) -> np.ndarray:
        Bf = np.asarray(B, dtype=np.float64)
        deg_u, deg_i = Bf.sum(axis=1), Bf.sum(axis=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            P_ui = np.where(deg_u[:, None] > 0, Bf / deg_u[:, None], 0.0)
            P_iu = np.where(deg_i[None, :] > 0, Bf / deg_i[None, :], 0.0)
            W = np.power(P_iu.T @ P_ui, alpha)
            W = np.where(deg_i[None, :] > 0, W / np.power(deg_i[None, :], beta), 0.0)
        np.fill_diagonal(W, 0.0)
        return W

    def fit(self, data: TrainData) -> dict:
        t0 = perf_counter()
        W = self.transition(data.B, self.alpha, self.beta)
        self.idx, self.val = topk_rows(W, W, self.top_k)
        self.n_items = data.n_items
        return {"params": {"alpha": self.alpha, "beta": self.beta, "topK": self.top_k}, "rows": "trip", "nRows": int(data.B.shape[0]),
                **neighbour_stats(W, self.idx, self.val), "fitSeconds": round(perf_counter() - t0, 3)}

    def row(self, s: int):
        return row_from_topk(self.idx, self.val, self.n_items, s)

    def score(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray:
        return weighted_mean_rows(self.row, ctx.seeds, cand)

    def collab_part(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray | None:
        return self.score(ctx, cand)

    def explain(self, ctx: UserCtx, items: np.ndarray) -> list[list[dict]]:
        """because[]: `c_e·T[e, x]/Z` theo event (spec §1.2), kind cooc; phần âm bị loại."""
        return because.from_rows(self.row, ctx.profile, items, kind="cooc")
