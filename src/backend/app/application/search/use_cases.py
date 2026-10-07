from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field, replace
from time import perf_counter
from typing import Any

import numpy as np

from src.backend.app.application.ports import (
    EmbedderPort,
    LexicalHit,
    LexicalSearchPort,
    UnitIndex,
    VectorHit,
    VectorSearchPort,
)
from src.backend.app.core.logging_config import log_event
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
    entity_table,
    fold,
    hybrid_filter_score,
    place_table,
    is_unaccented,
    parse_vertical,
    query_tokens,
    revalidate,
    soft_star_order,
    tokens,
)
from src.backend.app.domain.search.fuzzy import FuzzyIndex

from .query_plan_llm import (
    MODE_OFF,
    MODES,
    CachedQueryHypothesizer,
    LlmPlanFallback,
    HypothesisRequest,
    build_vocab,
    cache_keys,
    hypothesis_context,
)

logger = logging.getLogger("uvicorn.error")

_WS = re.compile(r"\s+")


def canonical_query(text: str) -> str:
    """Gộp khoảng trắng — chuỗi duy nhất đi vào embed / BM25 và làm khoá cache vector truy vấn (không fold hoa/thường/dấu:
    model embed hai dạng đó khác nhau, không được gộp)."""
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
            "imageUrl": p.image_url, "rating": p.rating, "reviewCount": p.review_count,
            "score": normalized_score, **extra}


def scored(index: UnitIndex, i: int, score: float, **extra) -> dict:
    """Kết quả Search/Similar: `hit` cộng điểm đánh giá của catalog (`rating`/`reviewCount` tùy chọn trong ProductSummary),
    để thẻ sản phẩm trong lịch trình của trợ lý có điểm đánh giá. Recommendation vẫn dùng `hit` rút gọn. `extra`: trường
    thêm của Search (vd. `matchedChildren` của query plan)."""
    product = index.units[i]
    return hit(index, i, score, rating=product.rating, reviewCount=product.review_count, **extra)


def _plan_gazetteers(units, *, entities=None, destinations=None) -> PlanGazetteers:
    """Gazetteer cho query plan, dựng từ catalog đang phục vụ (như `QueryNormalizer`): tên unit chứa cue loại KHÁC taxonomy
    của nó ("Golf Valley Hotel" là hotel) để F4 không lọc nhầm; mã sân bay ↔ thành phố từ attributes tuyến bay
    (`originAirport(s)` / `destinationAirport(s)`, cùng cách bench dựng `vocab.json`).

    1.18.0: `entities` = `UnitAttributes.entities` → bảng entity chỉ giữ khoá có ít nhất một unit (entity không có sản phẩm
    không bao giờ gate); `destinations` = tập điểm đến catalog → bảng địa danh bỏ entry trỏ tới nơi catalog không có. None =
    bảng đầy đủ (debug app, test)."""
    brands: dict[str, str | None] = {}     # tên fold → taxonomy của unit (None khi hai unit cùng tên khác loại)
    iata: dict[str, str] = {}
    cities: set[str] = set()
    for p in units:
        found = parse_vertical(p.name).verticals
        if found and any(v != p.taxonomy for v in found):
            k = fold(p.name)
            brands[k] = p.taxonomy if brands.get(k, p.taxonomy) == p.taxonomy else None
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
    extra: dict = {}
    if entities is not None:
        present = set().union(*entities) if len(entities) else set()
        extra["entities"] = {alias: key for alias, key in entity_table().items() if key in present}
    if destinations is not None:
        extra["places"] = place_table(destinations)
    return PlanGazetteers(brand_names=tuple(sorted(brands)), iata=iata, flight_cities=tuple(sorted(cities)),
                          brand_taxonomy={k: v for k, v in brands.items() if v}, **extra)


def _plan_diagnostics(plan: QueryPlan, flags: PlanFlags, *, revalidated_drops: int, empty_reason: str | None,
                      llm: dict | None = None) -> dict:
    """Khối `diagnostics.queryPlan` theo contract 1.16.0 (`as_diagnostics(extended=True)`).

    Khoá 1.16.0 gắn với một núm mới chỉ khai khi núm đó đang dùng cho câu: `taxonomy.strength` khi
    SEARCH_TAXONOMY_STRONG_ONLY bật; `party` khi request có travelContext.guests hoặc cờ party bật; `mustNot.taxonomies` /
    `mustNot.flags` khi cờ phủ định áp. Nhờ vậy mọi núm mới ở mặc định thì khối chỉ khác 1.15.0 ở `confidence` /
    `fallbackReasons` (luôn khai khi khối có mặt). Khoá 1.18.0 (`duration` / `entity` / `location`) không cần che ở đây:
    `build_query_plan` chỉ parse ba họ đó khi cờ bật, tắt thì field ở mặc định và `as_diagnostics` không phát."""
    hide: dict = {}
    if not flags.taxonomy_strong_only:
        hide["taxonomy_strength"] = None
    if not (flags.party or plan.party_source == SOURCE_PARAM):
        hide["party_source"] = None
    if not flags.negation:
        hide.update(must_not_taxonomies=(), must_not_flags=())
    shown = replace(plan, **hide) if hide else plan
    out = shown.as_diagnostics(revalidated_drops=revalidated_drops, empty_reason=empty_reason, extended=True)
    if llm is not None:   # contract 1.17.0: chỉ khi SEARCH_LLM_FALLBACK ≠ off và fallback kích hoạt cho câu này
        out["llm"] = llm
    return out


def _child_filter(plan: QueryPlan) -> dict:
    """kwargs của `UnitIndex.matched_children` cho các điều kiện cấp phòng/chuyến đang áp (giá, số khách); {} = không có."""
    kw: dict = {}
    if plan.price_active:
        kw.update(price_min=plan.price_min, price_max=plan.price_max)
    if plan.party_active:
        kw["min_occupancy"] = plan.party_total
    return kw


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
    # 06/10 (kiến trúc §3, §4, §6, §7 5C; contract 1.16.0): mặc định tắt — mọi núm ở mặc định ≡ response 1.15.0 (trừ
    # queryPlan.confidence / fallbackReasons). Kênh fuzzy và trọng số RRF nằm trong `HybridConfig` (fuzzy_k = 0 → tắt).
    tone_normalize: bool = False         # đưa vị trí dấu thanh của câu về kiểu đa số của catalog (hoà ↔ hòa), trước embed/BM25
    taxonomy_strong_only: bool = False   # F4 chỉ lọc khi câu có cue loại MẠNH ("khách sạn"), không lọc với cue yếu ("phòng")
    party_filter: bool = False           # số khách suy từ câu → sức chứa tối thiểu; travelContext.guests của request luôn áp
    # 07/10 (contract 1.18.0; spec docs/spec/bench/tong-hop-chinh-sua-luong-search-ota.md): tắt thì KHÔNG parse, không khai.
    duration_filter: bool = False        # F7 "3 ngày 2 đêm" → bỏ cụm khỏi câu BM25, khai queryPlan.duration (không lọc)
    poi_resolve: bool = False            # địa danh gazetteer ("Hồ Hoàn Kiếm" → Hà Nội) vào F1; hard.destinationSource = poi
    entity_filter: bool = False          # gate cứng: câu nêu điểm vui chơi → chỉ attraction/combo có tên chứa entity
    # LLM fallback của query plan (đề xuất đã chốt 2026-10-06-search-llm-fallback-query-plan; contract 1.17.0): off | shadow | on.
    # Chỉ khi plan rule có confidence < `llm_min_confidence`; `hypothesizer` = QueryHypothesisPort (bọc cache nếu chưa bọc).
    llm_fallback: str = MODE_OFF
    llm_min_confidence: float = 0.75
    llm_timeout_ms: int = 1500
    hypothesizer: Any = None
    _name_tokens: list[set[str]] = field(default_factory=list, init=False, repr=False, compare=False)
    _normalizer: QueryNormalizer | None = field(default=None, init=False, repr=False, compare=False)
    _gaz: PlanGazetteers = field(default_factory=PlanGazetteers, init=False, repr=False, compare=False)
    _fuzzy: FuzzyIndex | None = field(default=None, init=False, repr=False, compare=False)
    _llm: LlmPlanFallback | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.llm_fallback not in MODES:
            raise ValueError(f"llm_fallback phải là một trong {MODES}, nhận {self.llm_fallback!r}")
        # Token (đã fold) của tên từng search unit, tính một lần: dùng để xét độ phủ khi vớt hit BM25.
        if self.hybrid_on:
            self._name_tokens = [set(tokens(p.name)) for p in self.index.units]
        if self.normalize:   # từ vựng sửa chính tả + gazetteer lấy từ chính catalog đang chạy
            self._normalizer = QueryNormalizer(destinations=set(self.index.destination.tolist()),
                                               names=(p.name for p in self.index.units), tone=self.tone_normalize)
            self._gaz = _plan_gazetteers(self.index.units, entities=self.index.attrs.entities,
                                         destinations=set(self.index.destination.tolist()))
        if self.fuzzy_on:   # dựng chỉ mục trigram ngay lúc nạp catalog (luồng nạp lại), không để request đầu tiên trả giá
            self._fuzzy_index()
        if self.llm_fallback != MODE_OFF and self.normalize:   # off → không dựng gì: response như 1.16.0
            hyp = self.hypothesizer
            if hyp is not None and not isinstance(hyp, CachedQueryHypothesizer):
                hyp = CachedQueryHypothesizer(hyp)
            self._llm = LlmPlanFallback(self.llm_fallback, self.llm_min_confidence, self.llm_timeout_ms, hyp,
                                        build_vocab(set(self.index.destination.tolist()), self._gaz), self._gaz)

    @property
    def hybrid_on(self) -> bool:
        return self.lexical is not None and self.hybrid is not None

    @property
    def fuzzy_on(self) -> bool:
        """Kênh fuzzy chỉ chạy trong nhánh hybrid, khi bộ ngưỡng hiệu lực có `fuzzy_k > 0`."""
        return self.hybrid_on and any(c is not None and c.fuzzy_k > 0 for c in (self.hybrid, self.no_diacritics))

    def _fuzzy_index(self) -> FuzzyIndex:
        """Chỉ mục trigram trên tên search unit, dựng một lần (lười) — phần tử i ứng với `index.units[i]`."""
        fz = self._fuzzy
        if fz is None:
            fz = FuzzyIndex.build([p.name for p in self.index.units])
            self._fuzzy = fz
        return fz

    def __call__(self, q: str, *, taxonomy: str | None = None, destination: str | None = None, origin: str | None = None,
                 price_min: int | None = None, price_max: int | None = None, star_min: float | None = None,
                 available_only: bool = True, limit: int = 20, offset: int = 0,
                 derive_destination: bool | None = None, derive_plan: bool | None = None,
                 adults: int | None = None, children: int | None = None) -> dict:
        """`derive_destination` / `derive_plan`: ghi đè cờ `dest_filter` / tám cờ họ query plan (phủ định, loại, tuyến, số,
        số khách, thời lượng, địa danh gazetteer, entity) cho riêng lượt gọi (Agent); None = theo cấu hình. `origin`,
        `price_min/max`, `star_min`, `available_only`, `adults` / `children` (= travelContext.guests, contract 1.16.0) = tham
        số request, luôn áp."""
        limit = min(limit, self.max_limit)
        stages = StageTimer()
        nq = self._normalizer(q) if self._normalizer else None
        # embed, BM25 và độ phủ đều dùng câu đã chuẩn hoá + gộp khoảng trắng (= khoá cache); `q` gốc chỉ còn để đối chiếu
        text = canonical_query(nq.text if nq else q)
        if nq:
            stages.lap("normalize")
        derive = self.dest_filter if derive_destination is None else derive_destination
        flags = PlanFlags(destination=derive,
                          negation=self.negation_filter if derive_plan is None else derive_plan,
                          taxonomy=self.taxonomy_filter if derive_plan is None else derive_plan,
                          route=self.route_filter if derive_plan is None else derive_plan,
                          numeric=self.numeric_filter if derive_plan is None else derive_plan,
                          taxonomy_strong_only=self.taxonomy_strong_only,
                          party=self.party_filter if derive_plan is None else derive_plan,
                          duration=self.duration_filter if derive_plan is None else derive_plan,
                          poi=self.poi_resolve if derive_plan is None else derive_plan,
                          entity=self.entity_filter if derive_plan is None else derive_plan)
        params = PlanParams(taxonomy=taxonomy, destination=destination, origin=origin, price_min=price_min,
                            price_max=price_max, star_min=star_min, available_only=available_only,
                            adults=adults, children=children)
        plan = pending = llm_block = None
        if self._llm is not None and nq is not None and derive_plan is not False:
            # LLM fallback bật: dựng plan TRƯỚC embed để lượt gọi model (khi confidence thấp) chạy song song với embed
            plan = build_query_plan(nq, q, params, flags, self._gaz)
            pending = self._llm.begin(plan, nq, q, flags)
        qvec, embed_cache = self._embed(text)
        stages.lap("embed")
        # Câu không dấu → bộ ngưỡng riêng (nếu bật); khoá cache và vector không đổi, chỉ cổng vớt / cutoff đổi.
        profile = self._profile(q)
        cfg = self.no_diacritics if profile and self.no_diacritics is not None else self.hybrid
        cutoff = self.no_diacritics_cutoff if profile and self.no_diacritics_cutoff is not None else self.cutoff
        if plan is None:
            plan = build_query_plan(nq, q, params, flags, self._gaz)
        if pending is not None:
            plan, llm_block = self._llm.finish(pending)   # chờ phần hạn còn lại; on + nhận → plan đã trộn
            stages.lap("llm")
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
            # phát kể cả khi cờ tắt: bench đếm được tần suất filter sẽ kích hoạt. = nq.destinations, cộng điểm đến suy từ địa
            # danh gazetteer khi SEARCH_POI_RESOLVE bật (1.18.0) — `decide_destination` giữ nguyên candidates.
            if plan.destination.candidates:
                diagnostics["derivedDestinations"] = list(plan.destination.candidates)
            # contract 1.15.0: khối queryPlan phát kể cả khi mọi cờ tắt (bench đo độ chính xác parse); rỗng thì bỏ.
            query_plan = _plan_diagnostics(plan, flags, revalidated_drops=drops, empty_reason=empty_reason, llm=llm_block)
            if query_plan:
                diagnostics["queryPlan"] = query_plan
        if derive:
            diagnostics["destinationFilter"] = decision.as_dict(fallback)
        if profile:
            diagnostics["queryProfile"] = profile
        if embed_cache:   # contract 1.12.0: chỉ khi embedder có cache (CachingQueryEmbedder)
            diagnostics["embedCache"] = embed_cache
        page = out.order[offset: offset + limit]
        child_filter = _child_filter(plan)
        results = [scored(self.index, i, out.scores[i], **self._matched_children(i, child_filter)) for i in page]
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
                    or plan.route_source == SOURCE_PARAM or plan.party_source == SOURCE_PARAM or not available_only)
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
                                            cfg=cfg, cutoff=cutoff, drop_tokens=drop, mask=mask)
        else:
            out = candidate_filter_score([self.index.idx[h.product_id] for h in dense], [h.score for h in dense],
                                         cutoff, int(mask.sum()), facet_fields)
            stages.lap("fuse")
            diagnostics = dict(ANN_DIAGNOSTICS)
        # Kiến trúc Phase A §9: kiểm lại hard filter sau fusion (lưới an toàn, kỳ vọng không loại gì) rồi xếp sao soft
        # (unit không khai sao xuống sau, contract [C6]).
        order, drops = revalidate(out.order, mask)
        if plan.price_active and plan.party_active:
            # Kiến trúc §6 parent–child: mask xét giá và sức chứa ĐỘC LẬP trên unit + con (phòng 2 người rẻ + phòng 4 người
            # đắt vẫn qua cả hai) → unit có con phải có ít nhất một con thoả CẢ HAI; không thì loại, đếm vào revalidatedDrops.
            order, joint = self._joint_children(order, plan)
            drops += joint
        if drops:   # R đổi thành viên → đếm lại facets để giữ bất biến sum(facets.taxonomy) == total ([C4])
            out.facets = {name: dict(Counter(str(arr[u]) for u in order)) for name, arr in facet_fields.items()}
        if plan.star_active:   # chỉ khi sao đang áp (param, hoặc câu + cờ numeric); parse ra mà cờ tắt thì không đổi thứ tự
            order = soft_star_order(order, self.index.star_known_ok(plan.star_min))
        if order != out.order:
            out.order = order
        return out, diagnostics, drops

    def _joint_children(self, order: list[int], plan: QueryPlan) -> tuple[list[int], int]:
        """Giữ unit không có con (giá / sức chứa của chính nó đã qua mask) hoặc có ≥ 1 con thoả đồng thời giá + số khách."""
        children = self.index.attrs.children
        kw = _child_filter(plan)
        kept = [u for u in order if not children[u] or self.index.matched_children(u, limit=1, **kw)]
        return kept, len(order) - len(kept)

    def _matched_children(self, i: int, child_filter: dict) -> dict:
        """`matchedChildren` (contract 1.16.0) của một kết quả: chỉ khi lọc giá / số khách đang áp và có con thoả."""
        if not child_filter or not self.index.attrs.children[i]:
            return {}
        ids = self.index.matched_children(i, **child_filter)
        return {"matchedChildren": ids} if ids else {}

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

    def llm_hypothesis_request(self, q: str) -> HypothesisRequest | None:
        """Khoá cache, câu gửi model, context và confidence của plan rule cho câu `q` KHÔNG kèm tham số request — đúng khoá và
        prompt mà LLM fallback dùng lúc request; job prewarm (`jobs/prewarm_llm_hypotheses.py`) nạp cache bằng hàm này.
        None khi bước chuẩn hoá tắt (không có query plan) hoặc câu rỗng."""
        if self._normalizer is None or not q.strip():
            return None
        nq = self._normalizer(q)
        plan = build_query_plan(nq, q, PlanParams(), PlanFlags(), self._gaz)
        vocab = self._llm.vocab if self._llm is not None else build_vocab(set(self.index.destination.tolist()), self._gaz)
        return HypothesisRequest(cache_keys(nq.text, q), nq.text, hypothesis_context(nq, q, self._gaz, vocab),
                                 plan.confidence)

    def _embed(self, text: str) -> tuple[np.ndarray, str | None]:
        """(vector, "hit" | "miss" | None): None khi embedder không có cache (bench, test, SEARCH_EMBED_CACHE=false)."""
        with_status = getattr(self.embedder, "embed_query_status", None)
        try:
            if with_status is None:
                return self.embedder.embed_query(text), None
            vec, status = with_status(text)
        except Exception as exc:
            log_event(logger, "search.embed.failed", "ERROR", error_kind=type(exc).__name__)
            raise
        return vec, status

    def _hybrid(self, q: str, qvec: np.ndarray, dense: list[VectorHit], allowed, filtered_count: int,
                facet_fields: dict, stages: StageTimer | None = None, *, cfg: HybridConfig | None = None,
                cutoff: float | None = None, drop_tokens: frozenset[str] = frozenset(),
                mask: np.ndarray | None = None) -> tuple[SearchOutcome, dict]:
        """`cfg` / `cutoff`: bộ ngưỡng hiệu lực của câu (mặc định = cấu hình chung); `drop_tokens`: token bỏ khỏi độ phủ;
        `mask`: tập F (bool theo index unit) cho kênh fuzzy — None = toàn catalog."""
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
        fuzzy_rank = fuzzy_admissible = None
        if cfg.fuzzy_k > 0:
            fuzzy_rank, fuzzy_admissible = self._fuzzy_channel(q, qv, qn, mask, cfg, cosines)
            if stages is not None:
                stages.lap("fuzzy")
        q_tokens = query_tokens(q)
        if drop_tokens:
            q_tokens = [t for t in q_tokens if t not in drop_tokens] or q_tokens   # câu chỉ có địa danh thì giữ nguyên
        out = hybrid_filter_score(
            cosines, dense_rank, lexical_rank,
            lambda u: coverage(q_tokens, self._name_tokens[u]) >= cfg.min_coverage,
            cutoff, cfg, filtered_count, facet_fields,
            fuzzy_rank=fuzzy_rank, fuzzy_admissible=fuzzy_admissible,
        )
        if stages is not None:
            stages.lap("fuse")
        diagnostics = {**HYBRID_DIAGNOSTICS, "fusion": "rrf", "rrfK": cfg.rrf_k, "lexicalK": cfg.lexical_k,
                       "lexicalCutoff": cfg.lexical_cutoff, "lexicalMinCoverage": cfg.min_coverage,
                       "lexicalCandidates": len(lex), "lexicalCount": len(out.lexical_only)}
        if cfg.fuzzy_k > 0:   # contract 1.16.0: chỉ khi kênh fuzzy bật
            diagnostics["fuzzyCount"] = len(getattr(out, "fuzzy_only", ()))
        return out, diagnostics

    def _fuzzy_channel(self, q: str, qv: np.ndarray, qn: float, mask: np.ndarray | None, cfg: HybridConfig,
                       cosines: dict[int, float]):
        """Kênh fuzzy (kiến trúc §7 5C): top-`fuzzy_candidate_k` unit trong F theo độ giống tên ↔ đoạn của câu `q` (= câu BM25).

        Trả (rank, cổng vớt) cho `hybrid_filter_score`; danh sách chỉ gồm unit có độ giống ≥ `fuzzy_min_sim` (cả phần cộng RRF
        lẫn cổng vớt). Unit có thể được vớt (rank ≤
        `fuzzy_k`, đạt cổng) mà chưa có cosine (không ở dense lẫn BM25) được lấy vector từ kho để tính cosine — ghi thẳng vào
        `cosines`. Lỗi ở kênh này chỉ làm mất kênh (log), không 500 — như nhánh lexical."""
        try:
            # chỉ khớp ≥ ngưỡng mới vào danh sách kênh: khớp yếu ("khach san" ↔ mọi tên "Khách sạn …") không được cộng RRF
            # (bench 06/10: để cả top-50 vào RRF làm nDCG@10 −7,6 điểm và ngưỡng 0,6 / 0,75 cho kết quả y hệt)
            found = self._fuzzy_index().search(q, allowed=mask, k=cfg.fuzzy_candidate_k, min_sim=cfg.fuzzy_min_sim)
        except Exception as exc:  # noqa: BLE001
            logger.warning("search.fuzzy.failed %s", exc)
            return None, None
        if not found:
            return None, None
        rank = {u: r for r, (u, _) in enumerate(found, 1)}
        sim = dict(found)
        need = [u for u, r in rank.items() if u not in cosines and r <= cfg.fuzzy_k and sim[u] >= cfg.fuzzy_min_sim]
        if need:
            ids = [self.index.units[u].product_id for u in need]
            try:
                stored = self.vectors.vectors(ids)
            except Exception as exc:  # noqa: BLE001 — không lấy được vector → unit đó không được vớt (thiếu cosine)
                logger.warning("search.fuzzy.vectors.failed %s", exc)
                stored = {}
            for u, pid in zip(need, ids):
                v = stored.get(pid)
                if v is not None and len(v):
                    v = np.asarray(v, dtype=np.float32)
                    cosines[u] = float(v @ qv) / ((float(np.linalg.norm(v)) or 1.0) * qn)
        min_sim = cfg.fuzzy_min_sim
        return rank, (lambda u: sim.get(u, 0.0) >= min_sim)


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
            scored(self.index, self.index.idx[h.product_id], h.score) for h in hits if h.product_id in self.index.idx))
