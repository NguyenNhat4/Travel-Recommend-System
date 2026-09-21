from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.application.ports import EmbedderPort, UnitIndex
from app.domain.search import exact_filter_score


def hit(index: UnitIndex, i: int, score: float, **extra) -> dict:
    p = index.units[i]
    return {"productId": p.product_id, "name": p.name, "taxonomy": p.taxonomy, "destination": p.destination,
            "unitPrice": p.unit_price, "imageUrl": p.image_url, "score": round(float(score), 4), **extra}


@dataclass
class SearchProducts:
    index: UnitIndex
    embedder: EmbedderPort
    cutoff: float
    max_limit: int = 50

    def __call__(self, q: str, *, taxonomy: str | None = None, destination: str | None = None,
                 limit: int = 20, offset: int = 0) -> dict:
        limit = min(limit, self.max_limit)
        qvec = self.embedder.embed_query(q)
        mask = self.index.mask(taxonomy, destination)
        out = exact_filter_score(self.index.E, qvec, mask, self.cutoff,
                                 {"taxonomy": self.index.taxonomy, "destination": self.index.destination})
        page = out.order[offset: offset + limit]
        return {
            "results": [hit(self.index, i, out.scores[i]) for i in page],
            "total": out.total, "limit": limit, "offset": offset,
            "topScore": round(float(out.scores[out.order[0]]), 4) if out.order else None, "cutoff": self.cutoff,
            "facets": out.facets,
            "diagnostics": {"searchMode": "EXACT_FILTER_SCORE", "approximate": False, "totalExact": True, "facetsExact": True,
                            "filteredCount": out.filtered_count, "relevantCount": out.total,
                            "modelVersion": self.index.model_version},
        }


@dataclass
class SimilarProducts:
    index: UnitIndex

    def __call__(self, product_id: str, k: int = 8, same_taxonomy: bool = True) -> list[dict]:
        i0 = self.index.resolve(product_id)
        if i0 is None:
            return []
        scores = self.index.E @ self.index.E[i0]
        m = self.index.mask(taxonomy=str(self.index.taxonomy[i0]) if same_taxonomy else None)
        m[i0] = False
        root = self.index.parent_of.get(product_id, product_id)
        for child, parent in self.index.parent_of.items():  # loại anh em cùng cha
            if parent == root and child in self.index.idx:
                m[self.index.idx[child]] = False
        order = [i for i in np.argsort(-scores) if m[i]][:k]
        return [hit(self.index, i, scores[i]) for i in order]
