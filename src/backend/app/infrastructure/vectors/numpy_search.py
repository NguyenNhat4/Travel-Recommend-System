"""`VectorSearchPort` quét toàn bộ ma trận trong RAM — cho fallback offline và test, không dùng ở runtime."""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from src.backend.app.application.ports import VectorHit


class NumpyVectorSearch:
    def __init__(self, product_ids: Sequence[str], embeddings: np.ndarray):
        self.ids = list(product_ids)
        self.E = np.asarray(embeddings, dtype=np.float32)
        self.dimension = int(self.E.shape[1])
        self.pos = {pid: i for i, pid in enumerate(self.ids)}

    def near_vector(self, vector: np.ndarray, allowed: Sequence[str] | None, limit: int,
                    *, with_vectors: bool = False) -> list[VectorHit]:
        scores = self.E @ np.asarray(vector, dtype=np.float32)
        if allowed is None:
            rows = np.arange(len(self.ids))
        else:
            rows = np.array([self.pos[p] for p in allowed if p in self.pos], dtype=int)
        if not len(rows) or limit <= 0:
            return []
        top = rows[np.argsort(-scores[rows], kind="stable")[:limit]]
        return [VectorHit(self.ids[i], float(scores[i]), self.E[i] if with_vectors else None) for i in top]

    def vectors(self, product_ids: Sequence[str]) -> dict[str, np.ndarray]:
        return {p: self.E[self.pos[p]] for p in product_ids if p in self.pos}
