"""`VectorSearchPort` + `LexicalSearchPort` quét toàn bộ trong RAM — cho fallback offline và test, không dùng ở runtime.

BM25 ở đây là bản tối giản (Okapi, OR giữa các token, tên lặp hai lần để mô phỏng `nameAscii^2` của Weaviate)
để test được luồng hybrid mà không cần Weaviate; không phải để đo chất lượng.
"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

import numpy as np

from src.backend.app.application.ports import LexicalHit, VectorHit
from src.backend.app.domain.search import tokens


class NumpyVectorSearch:
    def __init__(self, product_ids: Sequence[str], embeddings: np.ndarray, texts: Sequence[str] | None = None):
        self.ids = list(product_ids)
        self.E = np.asarray(embeddings, dtype=np.float32)
        self.dimension = int(self.E.shape[1])
        self.pos = {pid: i for i, pid in enumerate(self.ids)}
        self._docs = [tokens(t) for t in texts] if texts is not None else None   # None → bm25() trả []
        self._df: Counter[str] = Counter()
        self._avgdl = 1.0
        if self._docs is not None:
            for doc in self._docs:
                self._df.update(set(doc))
            self._avgdl = sum(len(d) for d in self._docs) / max(1, len(self._docs))

    def _rows(self, allowed: Sequence[str] | None) -> np.ndarray:
        if allowed is None:
            return np.arange(len(self.ids))
        return np.array([self.pos[p] for p in allowed if p in self.pos], dtype=int)

    def near_vector(self, vector: np.ndarray, allowed: Sequence[str] | None, limit: int,
                    *, with_vectors: bool = False) -> list[VectorHit]:
        scores = self.E @ np.asarray(vector, dtype=np.float32)
        rows = self._rows(allowed)
        if not len(rows) or limit <= 0:
            return []
        top = rows[np.argsort(-scores[rows], kind="stable")[:limit]]
        return [VectorHit(self.ids[i], float(scores[i]), self.E[i] if with_vectors else None) for i in top]

    def bm25(self, query: str, allowed: Sequence[str] | None, limit: int,
             *, with_vectors: bool = False, k1: float = 1.2, b: float = 0.75) -> list[LexicalHit]:
        q = tokens(query)
        rows = self._rows(allowed)
        if self._docs is None or not q or limit <= 0 or not len(rows):
            return []
        n = len(self._docs)
        scored: list[tuple[float, int]] = []
        for i in rows:
            doc = self._docs[i]
            tf = Counter(doc)
            s = 0.0
            for t in q:
                if t in tf:
                    idf = math.log(1.0 + (n - self._df[t] + 0.5) / (self._df[t] + 0.5))
                    s += idf * tf[t] * (k1 + 1.0) / (tf[t] + k1 * (1.0 - b + b * len(doc) / self._avgdl))
            if s > 0.0:
                scored.append((s, int(i)))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [LexicalHit(self.ids[i], float(s), self.E[i] if with_vectors else None) for s, i in scored[:limit]]

    def vectors(self, product_ids: Sequence[str]) -> dict[str, np.ndarray]:
        return {p: self.E[self.pos[p]] for p in product_ids if p in self.pos}
