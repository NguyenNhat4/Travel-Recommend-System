"""`star_blend` — semantic + co-occurrence (STAR, tầng retrieval; spec `recsys-algos-v1.md` §2).

`score = engine + w_short·(1−a)·(collab − short)` — tức thay hạng ngắn hạn `w_short·short` của engine bằng `w_short·[a·short + (1−a)·collab]`;
`short = E[c]@u` (u = vector trip mở) và `w_short = W_SHORT`, hoặc khi không có chuyến mở mà engine chấm F14c (PR-B 09/10)
`short = calibrated_similarity(E[c]@u_long)` và `w_short = W_NEXT_SHORT`. `engine` = `content.engine_score` (hàm điểm production, gồm
điểm xuất phát chuyến bay). `collab` của `cooc_trip` cùng seed/trọng số. `blend_scope = inner`. a = 1,0 → không cộng gì nên
`star_blend_a1` ≡ `content_profile` trùng từng bit (kiểm `expect_equal_to`).
"""
from __future__ import annotations

import numpy as np

from src.backend.app.domain.recommendation import profile as P

from . import because
from .base import TrainData, UserCtx
from .content import engine_score
from .cooc import CoocTrip


class StarBlend:
    name = "star_blend"
    needs_vectors = True
    rows = "trip"

    def __init__(self, a: float = 0.5, beta: float = 5.0, top_k: int = 50, blend_scope: str = "inner"):
        if blend_scope != "inner":
            raise ValueError(f"blend_scope={blend_scope!r}: tuần này chỉ 'inner' (outer là grid tuần sau)")
        if not 0.0 <= float(a) <= 1.0:
            raise ValueError("a phải trong [0, 1]")
        self.a, self.blend_scope = float(a), blend_scope
        self.cooc = CoocTrip(beta=beta, top_k=top_k)
        self.E: np.ndarray | None = None

    def fit(self, data: TrainData) -> dict:
        log = self.cooc.fit(data)
        self.E = data.E
        self.index = data.index
        return {**log, "params": {**log["params"], "a": self.a, "blendScope": self.blend_scope}}

    def score(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray:
        assert self.E is not None, "gọi fit() trước"
        profile = ctx.profile
        if not profile.trips:
            return np.zeros(len(cand), dtype=np.float32)
        score = engine_score(self.index, self.E, ctx, cand)
        if self.a == 1.0:
            return score
        u = profile.active_trip.vec if profile.active_trip is not None else profile.u_long
        cos = self.E[cand] @ u
        if profile.active_trip is None and ctx.next_trip_scoring:
            short, w = P.calibrated_similarity(cos), P.W_NEXT_SHORT
        else:
            short, w = cos, P.W_SHORT
        collab = self.cooc.score(ctx, cand)
        return (score + w * (1.0 - self.a) * (collab - short)).astype(np.float32, copy=False)

    def collab_part(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray | None:
        return self.cooc.score(ctx, cand)

    def explain(self, ctx: UserCtx, items: np.ndarray) -> list[list[dict]]:
        """because[]: `a·c_e·(E_e·E_x)/Z + (1−a)·c_e·T[e, x]/Z` (spec §2.3, Z = Σc — xấp xỉ); a = 1 trùng bit `content_profile`."""
        return because.star(ctx.profile, items, self.E, self.cooc.row, self.a)
