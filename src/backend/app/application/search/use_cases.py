from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from time import perf_counter

import numpy as np

from src.backend.app.application.ports import (
    EmbedderPort,
    LexicalHit,
    LexicalSearchPort,
    UnitIndex,
    VectorHit,
    VectorSearchPort,
)
from src.backend.app.domain.search import (
    HybridConfig,
    NormalizedQuery,
    QueryNormalizer,
    SearchOutcome,
    candidate_filter_score,
    coverage,
    hybrid_filter_score,
    query_tokens,
    tokens,
)

logger = logging.getLogger("uvicorn.error")

_WS = re.compile(r"\s+")


def canonical_query(text: str) -> str:
    """Gộp khoảng trắng — chuỗi duy nhất đi vào embed / BM25 và làm khoá cache vector truy vấn (không fold hoa/thường/dấu:
    Cohere embed hai dạng đó khác nhau, không được gộp)."""
    return _WS.sub(" ", text).strip()


#: Khai báo ở diagnostics khi total/facets chỉ đếm trên top-K ứng viên (contract `[C4]`).
ANN_DIAGNOSTICS = {"searchMode": "ANN_CANDIDATE_SCORE", "approximate": True, "totalExact": False, "facetsExact": False}
#: /search hybrid (spec §2.4): R = dense ≥ cutoff ∪ phần vớt từ BM25; thứ tự theo RRF, score vẫn là cosine.
HYBRID_DIAGNOSTICS = {"searchMode": "HYBRID_CANDIDATE_SCORE", "approximate": True, "totalExact": False,
                      "facetsExact": False}


def _normalization_diagnostics(q: str, nq: NormalizedQuery) -> dict:
    """Trường tuỳ chọn của contract, chỉ có khi bước chuẩn hoá nhận ra hoặc đổi gì (EngineDiagnostics)."""
    out: dict = {}
    if nq.text != q:
        out["normalizedQuery"] = nq.text
    if nq.applied_aliases:
        out["appliedAliases"] = [{"from": a, "to": b} for a, b in nq.applied_aliases]
    if nq.corrections:
        out["corrections"] = [{"from": a, "to": b} for a, b in nq.corrections]
    if nq.party:
        out["party"] = nq.party
    return out


class StageTimer:
    """Thời gian từng bước của /search, khai ở `diagnostics.stageMs` (ms nguyên, contract 1.11.0).

    `lap(name)` ghi thời gian từ lần `lap` trước (hoặc từ lúc tạo) cho bước `name`. Bước không chạy thì không
    có khoá, nên `normalize` vắng khi tắt chuẩn hoá và `lexical` vắng ở chế độ dense-only. Cộng dồn bằng số thực,
    chỉ làm tròn **xuống** khi xuất, để tổng các bước luôn ≤ `latencyMs` mà route làm tròn trên tổng thời gian.
    """

    def __init__(self) -> None:
        self._seconds: dict[str, float] = {}
        self._last = perf_counter()

    def lap(self, name: str) -> None:
        now = perf_counter()
        self._seconds[name] = self._seconds.get(name, 0.0) + max(0.0, now - self._last)
        self._last = now

    @property
    def ms(self) -> dict[str, int]:
        return {name: int(seconds * 1000) for name, seconds in self._seconds.items()}


def hit(index: UnitIndex, i: int, score: float, **extra) -> dict:
    p = index.units[i]
    normalized_score = round(max(0.0, min(1.0, float(score))), 4)
    return {"productId": p.product_id, "name": p.name, "taxonomy": p.taxonomy, "destination": p.destination,
            "description": p.description, "attributes": p.attributes,
            "unitPrice": p.unit_price, "currency": p.currency, "priceUnit": p.price_unit,
            "available": p.available,
            "availableFrom": p.available_from.isoformat() if p.available_from else None,
            "availableTo": p.available_to.isoformat() if p.available_to else None,
            "imageUrl": p.image_url, "rating": p.rating, "reviewCount": p.review_count,
            "score": normalized_score, **extra}


@dataclass
class SearchProducts:
    index: UnitIndex
    vectors: VectorSearchPort
    embedder: EmbedderPort
    cutoff: float
    max_limit: int = 50
    candidate_k: int = 200
    lexical: LexicalSearchPort | None = None   # nhánh BM25; cùng adapter Weaviate. None → dense-only (ANN)
    hybrid: HybridConfig | None = None
    lexical_candidate_k: int = 50
    normalize: bool = True                       # bước chuẩn hoá truy vấn (spec §2.2); False → đưa nguyên câu vào
    _name_tokens: list[set[str]] = field(default_factory=list, init=False, repr=False, compare=False)
    _normalizer: QueryNormalizer | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Token (đã fold) của tên từng search unit, tính một lần: dùng để xét độ phủ khi vớt hit BM25.
        if self.hybrid_on:
            self._name_tokens = [set(tokens(p.name)) for p in self.index.units]
        if self.normalize:   # từ vựng sửa chính tả + gazetteer lấy từ chính catalog đang chạy
            self._normalizer = QueryNormalizer(destinations=set(self.index.destination.tolist()),
                                               names=(p.name for p in self.index.units))

    @property
    def hybrid_on(self) -> bool:
        return self.lexical is not None and self.hybrid is not None

    def __call__(self, q: str, *, taxonomy: str | None = None, destination: str | None = None,
                 limit: int = 20, offset: int = 0) -> dict:
        limit = min(limit, self.max_limit)
        stages = StageTimer()
        nq = self._normalizer(q) if self._normalizer else None
        # embed, BM25 và độ phủ đều dùng câu đã chuẩn hoá + gộp khoảng trắng (= khoá cache); `q` gốc chỉ còn để đối chiếu
        text = canonical_query(nq.text if nq else q)
        if nq:
            stages.lap("normalize")
        qvec, embed_cache = self._embed(text)
        stages.lap("embed")
        mask = self.index.mask(taxonomy, destination)
        allowed = self.index.allowed_ids(mask)
        facet_fields = {"taxonomy": self.index.taxonomy, "destination": self.index.destination}
        dense = [h for h in self.vectors.near_vector(qvec, allowed, self.candidate_k) if h.product_id in self.index.idx]
        stages.lap("dense")
        if self.hybrid_on:
            out, diagnostics = self._hybrid(text, qvec, dense, allowed, int(mask.sum()), facet_fields, stages)
        else:
            out = candidate_filter_score([self.index.idx[h.product_id] for h in dense], [h.score for h in dense],
                                         self.cutoff, int(mask.sum()), facet_fields)
            stages.lap("fuse")
            diagnostics = dict(ANN_DIAGNOSTICS)
        if nq:
            diagnostics.update(_normalization_diagnostics(q, nq))
        if embed_cache:   # contract 1.12.0: chỉ khi embedder có cache (CachingQueryEmbedder)
            diagnostics["embedCache"] = embed_cache
        page = out.order[offset: offset + limit]
        results = [hit(self.index, i, out.scores[i]) for i in page]
        stages.lap("hydrate")
        stage_ms = stages.ms
        logger.debug("search.stage_ms %s", stage_ms)
        return {
            "results": results,
            "total": out.total, "limit": limit, "offset": offset,
            # Cosine cao nhất trong R: ở hybrid phần tử đầu là theo RRF, chưa chắc là cosine cao nhất.
            "topScore": round(max(0.0, min(1.0, max(float(out.scores[i]) for i in out.order))), 4) if out.order else None,
            "cutoff": self.cutoff,
            "facets": out.facets,
            "diagnostics": {**diagnostics,
                            "filteredCount": out.filtered_count, "relevantCount": out.total,
                            "modelVersion": self.index.model_version,
                            "stageMs": stage_ms},
        }

    def query_text(self, q: str) -> str:
        """Chuỗi thật sự gửi đi embed cho câu `q` (chuẩn hoá + gộp khoảng trắng) — khoá cache; prewarm dùng để nạp đúng khoá."""
        nq = self._normalizer(q) if self._normalizer else None
        return canonical_query(nq.text if nq else q)

    def _embed(self, text: str) -> tuple[np.ndarray, str | None]:
        """(vector, "hit" | "miss" | None): None khi embedder không có cache (bench, test, SEARCH_EMBED_CACHE=false)."""
        with_status = getattr(self.embedder, "embed_query_status", None)
        if with_status is None:
            return self.embedder.embed_query(text), None
        vec, status = with_status(text)
        return vec, status

    def _hybrid(self, q: str, qvec: np.ndarray, dense: list[VectorHit], allowed, filtered_count: int,
                facet_fields: dict, stages: StageTimer | None = None) -> tuple[SearchOutcome, dict]:
        try:
            lex: list[LexicalHit] = [h for h in self.lexical.bm25(q, allowed, self.lexical_candidate_k, with_vectors=True)
                                     if h.product_id in self.index.idx]
        except Exception as exc:  # nhánh lexical hỏng (collection chưa có property BM25…) → dense-only, không 500
            logger.warning("search.lexical.failed %s", exc)
            lex = []
        if stages is not None:
            stages.lap("lexical")
        qv = np.asarray(qvec, dtype=np.float32)
        qn = float(np.linalg.norm(qv)) or 1.0
        cosines = {self.index.idx[h.product_id]: float(h.score) for h in dense}
        for h in lex:  # hit chỉ có ở nhánh BM25: cosine tính từ vector kho trả về (cả hai đã chuẩn hoá L2)
            u = self.index.idx[h.product_id]
            if u not in cosines and h.vector is not None and len(h.vector):
                v = np.asarray(h.vector, dtype=np.float32)
                cosines[u] = float(v @ qv) / ((float(np.linalg.norm(v)) or 1.0) * qn)
        dense_rank = {self.index.idx[h.product_id]: r for r, h in enumerate(dense, 1)}
        lexical_rank = {self.index.idx[h.product_id]: r for r, h in enumerate(lex, 1)}
        q_tokens = query_tokens(q)
        cfg = self.hybrid
        out = hybrid_filter_score(
            cosines, dense_rank, lexical_rank,
            lambda u: coverage(q_tokens, self._name_tokens[u]) >= cfg.min_coverage,
            self.cutoff, cfg, filtered_count, facet_fields,
        )
        if stages is not None:
            stages.lap("fuse")
        diagnostics = {**HYBRID_DIAGNOSTICS, "fusion": "rrf", "rrfK": cfg.rrf_k, "lexicalK": cfg.lexical_k,
                       "lexicalCutoff": cfg.lexical_cutoff, "lexicalMinCoverage": cfg.min_coverage,
                       "lexicalCandidates": len(lex), "lexicalCount": len(out.lexical_only)}
        return out, diagnostics


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
