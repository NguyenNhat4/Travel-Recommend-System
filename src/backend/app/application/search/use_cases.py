from __future__ import annotations

from dataclasses import dataclass

from src.backend.app.application.ports import EmbedderPort, UnitIndex, VectorSearchPort
from src.backend.app.domain.search import candidate_filter_score

#: Khai báo ở diagnostics khi total/facets chỉ đếm trên top-K ứng viên (contract `[C4]`).
ANN_DIAGNOSTICS = {"searchMode": "ANN_CANDIDATE_SCORE", "approximate": True, "totalExact": False, "facetsExact": False}


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
    vectors: VectorSearchPort
    embedder: EmbedderPort
    cutoff: float
    max_limit: int = 50
    candidate_k: int = 200

    def __call__(self, q: str, *, taxonomy: str | None = None, destination: str | None = None,
                 limit: int = 20, offset: int = 0) -> dict:
        limit = min(limit, self.max_limit)
        qvec = self.embedder.embed_query(q)
        mask = self.index.mask(taxonomy, destination)
        hits = [h for h in self.vectors.near_vector(qvec, self.index.allowed_ids(mask), self.candidate_k)
                if h.product_id in self.index.idx]
        out = candidate_filter_score([self.index.idx[h.product_id] for h in hits], [h.score for h in hits],
                                     self.cutoff, int(mask.sum()),
                                     {"taxonomy": self.index.taxonomy, "destination": self.index.destination})
        page = out.order[offset: offset + limit]
        return {
            "results": [hit(self.index, i, out.scores[i]) for i in page],
            "total": out.total, "limit": limit, "offset": offset,
            "topScore": round(float(out.scores[out.order[0]]), 4) if out.order else None, "cutoff": self.cutoff,
            "facets": out.facets,
            "diagnostics": {**ANN_DIAGNOSTICS,
                            "filteredCount": out.filtered_count, "relevantCount": out.total,
                            "modelVersion": self.index.model_version},
        }


@dataclass(frozen=True)
class SimilarLookup:
    """status: ok · not_in_index (id không phải search unit, cũng không có cha là search unit) · no_vector."""
    status: str
    anchor_id: str | None = None
    results: tuple[dict, ...] = ()


@dataclass
class SimilarProducts:
    index: UnitIndex
    vectors: VectorSearchPort

    def __call__(self, product_id: str, k: int = 8, same_taxonomy: bool = True) -> list[dict]:
        return list(self.lookup(product_id, k, same_taxonomy).results)

    def lookup(self, product_id: str, k: int = 8, same_taxonomy: bool = True) -> SimilarLookup:
        i0 = self.index.resolve(product_id)
        if i0 is None:
            return SimilarLookup("not_in_index")
        anchor_id = self.index.units[i0].product_id
        anchor = self.vectors.vectors([anchor_id]).get(anchor_id)
        if anchor is None:  # có trong catalog nhưng chưa index
            return SimilarLookup("no_vector", anchor_id)
        m = self.index.mask(taxonomy=str(self.index.taxonomy[i0]) if same_taxonomy else None)
        m[i0] = False
        root = self.index.parent_of.get(product_id, product_id)
        for child, parent in self.index.parent_of.items():  # loại anh em cùng cha
            if parent == root and child in self.index.idx:
                m[self.index.idx[child]] = False
        hits = self.vectors.near_vector(anchor, self.index.allowed_ids(m), k)
        return SimilarLookup("ok", anchor_id, tuple(
            hit(self.index, self.index.idx[h.product_id], h.score) for h in hits if h.product_id in self.index.idx))
