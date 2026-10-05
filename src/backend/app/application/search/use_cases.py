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
    EMPTY_DESTINATION,
    EMPTY_PARAM,
    SOURCE_PARAM,
    SOURCE_QUERY,
    HybridConfig,
    NormalizedQuery,
    PlanFlags,
    PlanGazetteers,
    PlanParams,
    QueryNormalizer,
    QueryPlan,
    SearchOutcome,
    build_query_plan,
    candidate_filter_score,
    coverage,
    fold,
    hybrid_filter_score,
    is_unaccented,
    parse_vertical,
    query_tokens,
    revalidate,
    soft_star_order,
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


#: `diagnostics.queryProfile` khi câu gõ không dấu và chế độ nới ngưỡng bật (SEARCH_NO_DIACRITICS_MODE=relax, contract 1.14.0).
PROFILE_NO_DIACRITICS = "no_diacritics"
#: `diagnostics.destinationFilter.fallback`: F sau khi lọc theo địa danh suy ra rỗng → đã chạy lại không lọc (FR-SRC-04).
FALLBACK_DROPPED_EMPTY = "dropped_empty"


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
            "imageUrl": p.image_url, "score": normalized_score, **extra}


def _plan_gazetteers(units) -> PlanGazetteers:
    """Gazetteer cho query plan, dựng từ catalog đang phục vụ (như `QueryNormalizer`): tên unit chứa cue loại KHÁC taxonomy
    của nó ("Golf Valley Hotel" là hotel) để F4 không lọc nhầm; mã sân bay ↔ thành phố từ attributes tuyến bay
    (`originAirport(s)` / `destinationAirport(s)`, cùng cách bench dựng `vocab.json`)."""
    brands: set[str] = set()
    iata: dict[str, str] = {}
    cities: set[str] = set()
    for p in units:
        found = parse_vertical(p.name).verticals
        if found and any(v != p.taxonomy for v in found):
            brands.add(fold(p.name))
        a = p.attributes or {}
        for code_k, city_k in (("originAirport", "originCity"), ("destinationAirport", "destinationCity")):
            code, city = a.get(code_k), a.get(city_k)
            if isinstance(city, str) and city:
                cities.add(city)
            if isinstance(code, str) and code.strip() and isinstance(city, str) and city:
                iata.setdefault(code.strip().upper(), city)
        for list_k, city_k in (("originAirports", "originCity"), ("destinationAirports", "destinationCity")):
            city = a.get(city_k)
            for code in a.get(list_k) or []:
                if isinstance(code, str) and code.strip() and isinstance(city, str) and city:
                    iata.setdefault(code.strip().upper(), city)
    return PlanGazetteers(brand_names=tuple(sorted(brands)), iata=iata, flight_cities=tuple(sorted(cities)))


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
    # FR-SRC-03 (05/10): lọc cứng theo địa danh suy ra từ câu (`domain/search/destination.py`); mặc định tắt cho tới khi bench
    # xác nhận. `dest_filter_fallback`: F rỗng sau khi lọc → chạy lại không lọc (FR-SRC-04) và khai `fallback`.
    dest_filter: bool = False
    dest_filter_fallback: bool = True
    # Câu gõ không dấu (slice `no_diacritics`): bộ ngưỡng vớt BM25 riêng (SEARCH_NO_DIACRITICS_MODE=relax) và cutoff dense riêng
    # (None = dùng cutoff chung). Chỉ câu `is_unaccented` (≥ `no_diacritics_min_tokens` token) mới dùng; câu có dấu không đổi gì.
    no_diacritics: HybridConfig | None = None
    no_diacritics_cutoff: float | None = None
    no_diacritics_min_tokens: int = 3
    # Query plan (kiến trúc Phase A, contract 1.15.0 `diagnostics.queryPlan`): mỗi họ hard filter suy từ câu một cờ, mặc định
    # tắt — tắt vẫn parse và khai. Tham số request tường minh (origin, giá, sao, availableOnly) luôn được áp theo contract.
    negation_filter: bool = False     # F3 "không có X" → loại unit có ghi nhận tiện ích X
    taxonomy_filter: bool = False     # F4 câu nêu đúng một loại sản phẩm → lọc taxonomy
    route_filter: bool = False        # F5 câu vé máy bay "từ A đến B" → lọc originCity của tuyến
    numeric_filter: bool = False      # F6 giá (hard) / sao (soft) suy từ câu
    _name_tokens: list[set[str]] = field(default_factory=list, init=False, repr=False, compare=False)
    _normalizer: QueryNormalizer | None = field(default=None, init=False, repr=False, compare=False)
    _gaz: PlanGazetteers = field(default_factory=PlanGazetteers, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Token (đã fold) của tên từng search unit, tính một lần: dùng để xét độ phủ khi vớt hit BM25.
        if self.hybrid_on:
            self._name_tokens = [set(tokens(p.name)) for p in self.index.units]
        if self.normalize:   # từ vựng sửa chính tả + gazetteer lấy từ chính catalog đang chạy
            self._normalizer = QueryNormalizer(destinations=set(self.index.destination.tolist()),
                                               names=(p.name for p in self.index.units))
            self._gaz = _plan_gazetteers(self.index.units)

    @property
    def hybrid_on(self) -> bool:
        return self.lexical is not None and self.hybrid is not None

    def __call__(self, q: str, *, taxonomy: str | None = None, destination: str | None = None, origin: str | None = None,
                 price_min: int | None = None, price_max: int | None = None, star_min: float | None = None,
                 available_only: bool = True, limit: int = 20, offset: int = 0,
                 derive_destination: bool | None = None, derive_plan: bool | None = None) -> dict:
        """`derive_destination` / `derive_plan`: ghi đè cờ `dest_filter` / bốn cờ query plan cho riêng lượt gọi (Agent);
        None = theo cấu hình. `origin`, `price_min/max`, `star_min`, `available_only` = tham số request (contract), luôn áp."""
        limit = min(limit, self.max_limit)
        stages = StageTimer()
        nq = self._normalizer(q) if self._normalizer else None
        # embed, BM25 và độ phủ đều dùng câu đã chuẩn hoá + gộp khoảng trắng (= khoá cache); `q` gốc chỉ còn để đối chiếu
        text = canonical_query(nq.text if nq else q)
        if nq:
            stages.lap("normalize")
        qvec, embed_cache = self._embed(text)
        stages.lap("embed")
        # Câu không dấu → bộ ngưỡng riêng (nếu bật); khoá cache và vector không đổi, chỉ cổng vớt / cutoff đổi.
        profile = self._profile(q)
        cfg = self.no_diacritics if profile and self.no_diacritics is not None else self.hybrid
        cutoff = self.no_diacritics_cutoff if profile and self.no_diacritics_cutoff is not None else self.cutoff
        derive = self.dest_filter if derive_destination is None else derive_destination
        flags = PlanFlags(destination=derive,
                          negation=self.negation_filter if derive_plan is None else derive_plan,
                          taxonomy=self.taxonomy_filter if derive_plan is None else derive_plan,
                          route=self.route_filter if derive_plan is None else derive_plan,
                          numeric=self.numeric_filter if derive_plan is None else derive_plan)
        params = PlanParams(taxonomy=taxonomy, destination=destination, origin=origin, price_min=price_min,
                            price_max=price_max, star_min=star_min, available_only=available_only)
        plan = build_query_plan(nq, q, params, flags, self._gaz)
        decision = plan.destination
        out, diagnostics, drops = self._retrieve(plan, text, qvec, decision.value, cfg, cutoff, stages)
        fallback = None
        if decision.source == SOURCE_QUERY and out.total == 0 and self.dest_filter_fallback:
            # FR-SRC-04: chỉ điểm đến suy ra được nới (gazetteer có thể suy sai); filter suy ra khác KHÔNG nới (kiến trúc §6).
            out, diagnostics, drops = self._retrieve(plan, text, qvec, None, cfg, cutoff, stages)
            fallback = FALLBACK_DROPPED_EMPTY
        empty_reason = (self._empty_reason(plan, None if fallback else decision.value)
                        if out.filtered_count == 0 else None)
        if nq:
            diagnostics.update(_normalization_diagnostics(q, nq))
            if nq.destinations:   # phát kể cả khi cờ tắt: bench đếm được tần suất filter sẽ kích hoạt
                diagnostics["derivedDestinations"] = list(nq.destinations)
            # contract 1.15.0: khối queryPlan phát kể cả khi mọi cờ tắt (bench đo độ chính xác parse); rỗng thì bỏ.
            query_plan = plan.as_diagnostics(revalidated_drops=drops, empty_reason=empty_reason)
            if query_plan:
                diagnostics["queryPlan"] = query_plan
        if derive:
            diagnostics["destinationFilter"] = decision.as_dict(fallback)
        if profile:
            diagnostics["queryProfile"] = profile
        if embed_cache:   # contract 1.12.0: chỉ khi embedder có cache (CachingQueryEmbedder)
            diagnostics["embedCache"] = embed_cache
        page = out.order[offset: offset + limit]
        results = [hit(self.index, i, out.scores[i]) for i in page]
        stages.lap("hydrate")
        stage_ms = stages.ms
        logger.debug("search.stage_ms %s", stage_ms)
        response = {
            "results": results,
            "total": out.total, "limit": limit, "offset": offset,
            # Cosine cao nhất trong R: ở hybrid phần tử đầu là theo RRF, chưa chắc là cosine cao nhất.
            "topScore": round(max(0.0, min(1.0, max(float(out.scores[i]) for i in out.order))), 4) if out.order else None,
            "cutoff": cutoff,   # cutoff hiệu lực cho câu này (khác `self.cutoff` chỉ ở profile không dấu)
            "facets": out.facets,
            "diagnostics": {**diagnostics,
                            "filteredCount": out.filtered_count, "relevantCount": out.total,
                            "modelVersion": self.index.model_version,
                            "stageMs": stage_ms},
        }
        # contract C6: phát khi F1 bật (như 1.14.0), khi request có tham số lọc mới, hoặc khi một họ suy từ câu đang áp —
        # request web hôm nay (chỉ taxonomy/destination, cờ tắt) không thêm khoá.
        explicit = (plan.price_source == SOURCE_PARAM or plan.star_source == SOURCE_PARAM
                    or plan.route_source == SOURCE_PARAM or not available_only)
        if derive or explicit or plan.applied:
            applied = plan.applied_filters(destination_fallback=fallback is not None)
            if applied:
                response["appliedFilters"] = applied
        return response

    def _profile(self, q: str) -> str | None:
        if (self.no_diacritics is None and self.no_diacritics_cutoff is None) or not is_unaccented(q, self.no_diacritics_min_tokens):
            return None
        return PROFILE_NO_DIACRITICS

    def _retrieve(self, plan: QueryPlan, text: str, qvec: np.ndarray, destination: str | None,
                  cfg: HybridConfig | None, cutoff: float, stages: StageTimer) -> tuple[SearchOutcome, dict, int]:
        """FILTER → TOP-K dense (→ BM25) → CUTOFF/FUSE → kiểm lại filter → sao soft, cho một bộ (mask, ngưỡng).

        `destination` tách khỏi plan vì lượt fallback (FR-SRC-04) chỉ bỏ điểm đến suy ra. Trả thêm số kết quả bị loại ở
        bước kiểm lại (`queryPlan.revalidatedDrops`, kỳ vọng 0)."""
        mask = self.index.mask(**plan.mask_kwargs(destination=destination))
        allowed = self.index.allowed_ids(mask)
        facet_fields = {"taxonomy": self.index.taxonomy, "destination": self.index.destination}
        dense = [h for h in self.vectors.near_vector(qvec, allowed, self.candidate_k) if h.product_id in self.index.idx]
        stages.lap("dense")
        # Địa danh đã thành filter thì không còn là bằng chứng độ phủ tên khi vớt hit BM25 ("sân golf ở Nha Trang" không
        # vớt "Vinpearl Resort Nha Trang" chỉ vì tên chứa "Nha Trang"); lượt fallback (destination None) không bỏ gì.
        drop = plan.drop_tokens if destination else frozenset()
        # BM25 và độ phủ dùng câu đã bỏ cụm thành filter (`lexical_text`); dense vẫn dùng `text` (khoá cache không đổi).
        lexical_text = canonical_query(plan.lexical_text)   # = `text` khi không cụm nào bị tiêu (mọi cờ tắt)
        if self.hybrid_on:
            out, diagnostics = self._hybrid(lexical_text, qvec, dense, allowed, int(mask.sum()), facet_fields, stages,
                                            cfg=cfg, cutoff=cutoff, drop_tokens=drop)
        else:
            out = candidate_filter_score([self.index.idx[h.product_id] for h in dense], [h.score for h in dense],
                                         cutoff, int(mask.sum()), facet_fields)
            stages.lap("fuse")
            diagnostics = dict(ANN_DIAGNOSTICS)
        # Kiến trúc Phase A §9: kiểm lại hard filter sau fusion (lưới an toàn, kỳ vọng không loại gì) rồi xếp sao soft
        # (unit không khai sao xuống sau, contract [C6]).
        order, drops = revalidate(out.order, mask)
        if plan.star_active:   # chỉ khi sao đang áp (param, hoặc câu + cờ numeric); parse ra mà cờ tắt thì không đổi thứ tự
            order = soft_star_order(order, self.index.star_known_ok(plan.star_min))
        if order != out.order:
            out.order = order
        return out, diagnostics, drops

    def _empty_reason(self, plan: QueryPlan, destination: str | None) -> str | None:
        """F = ∅ → họ filter đầu tiên (theo thứ tự áp) làm mask rỗng (`queryPlan.emptyReason`, contract 1.15.0).

        Filter suy từ câu KHÔNG được nới ngầm (kiến trúc Phase A §6): use case chỉ khai lý do để client gợi ý sửa câu."""
        base = {"taxonomy": plan.taxonomy if plan.taxonomy_source == SOURCE_PARAM else None,
                "destination": destination, "only_available": plan.available_only}
        if not self.index.mask(**base).any():
            return EMPTY_DESTINATION if destination else EMPTY_PARAM
        kw = dict(base)
        for family, extra in plan.families_in_order():
            kw.update(extra)
            if not self.index.mask(**kw).any():
                return family
        return None

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
                facet_fields: dict, stages: StageTimer | None = None, *, cfg: HybridConfig | None = None,
                cutoff: float | None = None, drop_tokens: frozenset[str] = frozenset()) -> tuple[SearchOutcome, dict]:
        """`cfg` / `cutoff`: bộ ngưỡng hiệu lực của câu (mặc định = cấu hình chung); `drop_tokens`: token bỏ khỏi độ phủ."""
        cfg = cfg if cfg is not None else self.hybrid
        cutoff = self.cutoff if cutoff is None else cutoff
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
        if drop_tokens:
            q_tokens = [t for t in q_tokens if t not in drop_tokens] or q_tokens   # câu chỉ có địa danh thì giữ nguyên
        out = hybrid_filter_score(
            cosines, dense_rank, lexical_rank,
            lambda u: coverage(q_tokens, self._name_tokens[u]) >= cfg.min_coverage,
            cutoff, cfg, filtered_count, facet_fields,
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
