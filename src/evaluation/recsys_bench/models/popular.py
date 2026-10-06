"""`pop_funnel` — baseline "phổ biến trong destination" **đi qua funnel chung** (Day 5 A0; spec `recsys-algos-v1.md` §7).

Scorer trả 0 cho mọi ứng viên, nên `rank_none` xếp mask theo khoá phá hoà `(pop_D↓, item_id↑)`: cùng mask, cùng pool, cùng phá hoà với
mọi scorer khác. Khác `most_popular_in_destination` (arm harness) ở chỗ mask là mask engine (taxonomy đã mua trong trip mở bị loại,
đã mua bị loại). Dùng để kiểm "CF ≈ popularity" bằng CI: scorer cộng tác vs `pop_funnel` có CI chứa 0 ⟹ vế cộng tác không thêm gì
ngoài độ phổ biến. Chỉ chạy `rerank: none` (MMR trên điểm toàn 0 chỉ còn vế đa dạng — vô nghĩa).
"""
from __future__ import annotations

import numpy as np

from .base import TrainData, UserCtx


class PopFunnel:
    name = "pop_funnel"
    needs_vectors = False
    rows = "none"

    def __init__(self, **params):
        if params:
            raise ValueError(f"pop_funnel không nhận tham số: {sorted(params)}")

    def fit(self, data: TrainData) -> dict:
        return {"params": {}, "note": "không fit; điểm 0 → funnel xếp theo (pop_D↓, item_id↑)"}

    def score(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray:
        return np.zeros(len(cand), dtype=np.float32)

    def collab_part(self, ctx: UserCtx, cand: np.ndarray) -> np.ndarray | None:
        return None

    def explain(self, ctx: UserCtx, items: np.ndarray) -> list[list[dict]]:
        return [[] for _ in range(len(items))]
