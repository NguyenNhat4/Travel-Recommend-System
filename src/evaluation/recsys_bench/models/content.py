"""`content_profile` — đúng công thức điểm của engine production (`profile.score_candidates`), chấm bằng scorer registry.

`score(c) = W_SHORT·(E[c]@u_short) + W_POP·pop_D[c] + W_LONG·(E[c]@u_long)` với `u_short = active_trip.vec` (có trip mở) hoặc `u_long`;
float32 cùng thứ tự phép tính với engine. Hằng đọc từ module `profile` lúc gọi để `--override` và `configHash` đi theo. Qua funnel
`pool: engine, rerank: mmr` arm này phải ra đúng top-20 của arm `engine` (gate G1, spec §9).
"""
from __future__ import annotations

import numpy as np

from src.backend.app.domain.recommendation import profile as P

from .base import TrainData, UserCtx


class ContentProfile:
    name = "content"
    needs_vectors = True
    rows = "none"

    def __init__(self, **params):
        if params:
            raise ValueError(f"content_profile không nhận tham số (hằng nằm trong profile.py / --override): {sorted(params)}")
        self.E: np.ndarray | None = None

    def fit(self, data: TrainData) -> dict:
        self.E = data.E
        return {"params": {}, "note": "không fit; hằng W_SHORT/W_POP/W_LONG/H_*/MMR_LAMBDA của profile.py (configHash)"}

    def score(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray:
        assert self.E is not None, "gọi fit() trước"
        profile = ctx.profile
        if not profile.trips:
            return np.zeros(len(cand), dtype=np.float32)
        u = profile.active_trip.vec if profile.active_trip is not None else profile.u_long
        E = self.E[cand]
        s_short, s_long = E @ u, E @ profile.u_long
        return P.W_SHORT * s_short + P.W_POP * ctx.pop[cand] + P.W_LONG * s_long

    def collab_part(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray | None:
        return None
