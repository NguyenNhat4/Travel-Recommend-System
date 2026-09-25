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


@dataclass(frozen=True)
class LexicalHit:
    product_id: str
    score: float                       # điểm BM25 của kho — chỉ để xếp hạng trong nhánh lexical, không phải cosine
    vector: np.ndarray | None = None   # chỉ có khi gọi với with_vectors=True (để tính cosine ở app)


class LexicalSearchPort(Protocol):
    """Nhánh BM25 của /search (`HYBRID_CANDIDATE_SCORE`). Adapter tự fold dấu `query` như lúc index."""

    def bm25(self, query: str, allowed: Sequence[str] | None, limit: int,
             *, with_vectors: bool = False) -> list[LexicalHit]:
        """Top-`limit` theo BM25, chỉ trong `allowed` (None = không lọc), sắp giảm dần; `[]` khi query rỗng."""
        ...
