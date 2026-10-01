"""`ease` — nghiệm đóng item × item (spec `recsys-algos-v1.md` §4): `P = (BᵀB + λI)⁻¹`, `B_ease = −P / diag(P)`, diag 0, giữ âm."""
from __future__ import annotations

from time import perf_counter

import numpy as np

from .base import TrainData, UserCtx
from .seeds import weighted_mean_rows


class Ease:
    name = "ease"
    needs_vectors = False
    rows = "trip"

    def __init__(self, lam: float = 200.0):
        self.lam = float(lam)
        self.W: np.ndarray | None = None

    @staticmethod
    def closed_form(B: np.ndarray, lam: float) -> tuple[np.ndarray, np.ndarray]:
        Bf = np.asarray(B, dtype=np.float64)
        G = Bf.T @ Bf
        diag_g = np.diag(G).copy()
        P = np.linalg.inv(G + lam * np.eye(G.shape[0]))
        W = -P / np.diag(P)[None, :]
        np.fill_diagonal(W, 0.0)
        return W, diag_g

    def fit(self, data: TrainData) -> dict:
        t0 = perf_counter()
        W, diag_g = self.closed_form(data.B, self.lam)
        self.W = W.astype(np.float32)
        return {"params": {"lam": self.lam}, "rows": "trip", "nRows": int(data.B.shape[0]), "nnzB": int(data.B.sum()),
                "maxDiagG": float(diag_g.max()) if diag_g.size else 0.0, "medianDiagG": float(np.median(diag_g)) if diag_g.size else 0.0,
                "itemsWithInteraction": int((diag_g > 0).sum()), "fitSeconds": round(perf_counter() - t0, 3)}

    def row(self, s: int) -> np.ndarray | None:
        assert self.W is not None, "gọi fit() trước"
        return self.W[s]

    def score(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray:
        return weighted_mean_rows(self.row, ctx.seeds, cand)

    def collab_part(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray | None:
        return self.score(ctx, cand)
