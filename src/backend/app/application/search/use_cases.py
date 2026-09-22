from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.backend.app.application.ports import EmbedderPort, UnitIndex
from src.backend.app.domain.search import exact_filter_score


def hit(index: UnitIndex, i: int, score: float, **extra) -> dict:
    p = index.units[i]
    normalized_score = round(max(0.0, min(1.0, float(score))), 4)
    return {"productId": p.product_id, "name": p.name, "taxonomy": p.taxonomy, "destination": p.destination,
            "description": p.description, "attributes": p.attributes,
            "unitPrice": p.unit_price, "currency": p.currency, "priceUnit": p.price_unit,
            "available": p.available,
            "availableFrom": p.available_from.isoformat() if p.available_from else None,
            "availableTo": p.available_to.isoformat() if p.available_to else None,
            "imageUrl": p.image_url, "score": normalized_score, **extra}


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
