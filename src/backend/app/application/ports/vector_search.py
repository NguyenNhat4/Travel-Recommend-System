"""Port truy vấn vector theo từng request: top-K gần nhất và lấy vector theo id.

Engine không giữ ma trận vector trong RAM; mỗi request hỏi kho vector (Weaviate) đúng phần nó cần
(docs/spec/hop-dong-tich-hop-search-recommendation.md §2.2, `ANN_CANDIDATE_SCORE`).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class VectorHit:
    product_id: str
    score: float                       # cosine, 1 − distance
    vector: np.ndarray | None = None   # chỉ có khi gọi với with_vectors=True


class VectorSearchPort(Protocol):
    dimension: int

    def near_vector(self, vector: np.ndarray, allowed: Sequence[str] | None, limit: int,
                    *, with_vectors: bool = False) -> list[VectorHit]:
        """Top-`limit` theo cosine, chỉ trong `allowed` (None = không lọc), sắp giảm dần."""
        ...

    def vectors(self, product_ids: Sequence[str]) -> dict[str, np.ndarray]:
        """Vector đã lưu của các id; id chưa được index thì vắng mặt trong kết quả."""
        ...
