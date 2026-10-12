"""`content_profile` — đúng công thức điểm của engine production (`profile.score_candidates`), chấm bằng scorer registry.

`score(c) = W_SHORT·(E[c]@u_short) + W_POP·pop_D[c] + W_LONG·(E[c]@u_long)` với `u_short = active_trip.vec` (có trip mở) hoặc `u_long`;
float32 cùng thứ tự phép tính với engine. Hằng đọc từ module `profile` lúc gọi để `--override` và `configHash` đi theo. Qua funnel
`pool: engine, rerank: mmr` arm này phải ra đúng top-20 của arm `engine` (gate G1, spec §9).
"""
from __future__ import annotations

import numpy as np

from src.backend.app.domain.recommendation import profile as P

from . import because
from .base import TrainData, UserCtx


def engine_score(index, E_full: np.ndarray, ctx: UserCtx, cand: np.ndarray) -> np.ndarray:
    """Điểm của engine production cho `cand` — gọi thẳng `profile.score_candidates` (09/10: + điểm xuất phát [F], + F14c khi không
    có chuyến mở [B]) để gương không lệch engine khi công thức đổi."""
    context = P.ScoreContext(taxonomy=index.taxonomy[cand], origin_city=index.attrs.origin_city[cand], origin=ctx.origin)
    score, _ = P.score_candidates(ctx.profile, E_full[cand], ctx.pop[cand], context, next_trip_scoring=ctx.next_trip_scoring)
    return score


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
        self.index = data.index
        return {"params": {}, "note": "không fit; hằng W_SHORT/W_POP/W_LONG/H_*/MMR_LAMBDA của profile.py (configHash)"}

    def score(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray:
        assert self.E is not None, "gọi fit() trước"
        profile = ctx.profile
        if not profile.trips:
            return np.zeros(len(cand), dtype=np.float32)
        return engine_score(self.index, self.E, ctx, cand)

    def collab_part(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray | None:
        return None

    def explain(self, ctx: UserCtx, items: np.ndarray) -> list[list[dict]]:
        """because[] của engine nguyên văn (`profile.explain`), kind semantic."""
        return because.content(ctx.profile, items, self.E)
