"""Query plan của /search (kiến trúc Phase A, `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` §4–§6; spec §2.2
"QUERY PLAN"; contract 1.15.0 `diagnostics.queryPlan`): gom mọi hard constraint parse từ câu thành một giá trị có cấu trúc
để tầng application dựng mask filter-first, chứ không để vector quyết định phủ định / loại sản phẩm / chiều bay / giá.

Thứ tự parse: giá & sao (F6) → phủ định (F3, bỏ qua span đã thành số) → loại sản phẩm (F4, bỏ cue trong scope phủ định)
→ tuyến bay (F5, chỉ câu vé máy bay) → điểm đến (F1, tái dùng `decide_destination`). Tham số request luôn thắng giá trị suy
ra. Mỗi họ một cờ (`PlanFlags`); cờ tắt thì vẫn parse để khai ở `queryPlan` nhưng không vào mask và không đổi text BM25 —
nhờ đó mọi cờ tắt ≡ hành vi cũ. Text đưa vào embed KHÔNG đổi (khoá cache vector); chỉ `lexical_text` (BM25 + độ phủ vớt) bỏ
các cụm đã thành filter. Thuần stdlib.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from .constraints import (
    FlightRoles,
    NegationParse,
    NumericParse,
    VerticalParse,
    parse_flight_roles,
    parse_negation,
    parse_numeric,
    parse_vertical,
    remove_spans,
)
from .destination import SOURCE_PARAM, SOURCE_QUERY, DestinationDecision, decide_destination, is_flight_query
from .lexical import fold, tokens
from .normalize import DESTINATION_ALIASES, NormalizedQuery, find_phrases, spans

TAXONOMY_FLIGHT = "flight"
#: Họ filter suy từ câu (giá trị của `queryPlan.applied` và `queryPlan.emptyReason`).
APPLIED_TAXONOMY, APPLIED_ROUTE, APPLIED_MUST_NOT, APPLIED_PRICE, APPLIED_STAR = "taxonomy", "route", "mustNot", "price", "star"
EMPTY_DESTINATION, EMPTY_PARAM = "destination", "param"
SKIPPED_NOT_FLIGHT = "not_flight"


@dataclass(frozen=True)
class PlanParams:
    """Tham số request (contract `SearchRequest`): luôn thắng giá trị parse từ câu."""
    taxonomy: str | None = None
    destination: str | None = None
    origin: str | None = None
    price_min: int | None = None
    price_max: int | None = None
    star_min: float | None = None
    available_only: bool = True


@dataclass(frozen=True)
class PlanFlags:
    """= cờ `SEARCH_*_FILTER`; False → họ đó chỉ parse để khai, không lọc."""
    destination: bool = False
    negation: bool = False
    taxonomy: bool = False
    route: bool = False
    numeric: bool = False


@dataclass(frozen=True)
class PlanGazetteers:
    """Dựng một lần từ catalog đang phục vụ (`SearchProducts.__post_init__`), như `QueryNormalizer`."""
    brand_names: tuple[str, ...] = ()                      # tên (fold) chứa cue loại khác taxonomy của unit → F4 không tính cue
    iata: Mapping[str, str] = field(default_factory=dict)  # mã sân bay VIẾT HOA → thành phố catalog (originCity/destinationCity)
    # Thành phố đi/đến của tuyến bay (`attributes.originCity/destinationCity`): nơi đi thường KHÔNG phải điểm đến du lịch của
    # catalog ("Hà Nội" chỉ là originCity) nên gazetteer điểm đến của QueryNormalizer không nhận ra — F5 tra thêm bảng này.
    flight_cities: tuple[str, ...] = ()

    def city_spans(self, text: str, known: tuple[tuple[int, int, str], ...]) -> tuple[tuple[int, int, str], ...]:
        """`known` (span điểm đến của normalizer) + span thành phố bay / alias ("sg", "hn") tìm thêm trong `text`, không chồng."""
        if not self.flight_cities:
            return known
        table = {fold(c): c for c in self.flight_cities}
        table.update({k: v for k, v in DESTINATION_ALIASES.items() if v in self.flight_cities})
        toks = spans(text)
        max_n = max(len(k.split()) for k in table)
        out = list(known)
        for i, n, key in find_phrases(toks, table.__contains__, max_n):
            start, end = toks[i][0], toks[i + n - 1][1]
            if not any(s < end and start < e for s, e, _ in out):
                out.append((start, end, table[key]))
        return tuple(sorted(out))


@dataclass(frozen=True)
class QueryPlan:
    destination: DestinationDecision
    taxonomy: str | None                 # giá trị parse/param (chỉ vào mask khi source=param hoặc "taxonomy" ∈ applied)
    taxonomy_source: str | None          # param | query | None
    taxonomy_skipped: str | None         # multi | brand | None
    taxonomy_candidates: tuple[str, ...]
    route_origin: str | None
    route_destination: str | None
    route_direction: str | None          # explicit | destination_only | origin_only | None
    route_source: str | None             # param | query | None
    route_skipped: str | None            # ambiguous | not_flight | None
    must_not_amenities: tuple[str, ...]
    must_not_brands: tuple[str, ...]
    soft_dropped: tuple[str, ...]
    unresolved: tuple[str, ...]
    price_min: int | None
    price_max: int | None
    price_source: str | None
    star_min: float | None
    star_source: str | None
    available_only: bool
    lexical_text: str
    drop_tokens: frozenset[str]
    applied: tuple[str, ...]             # họ suy từ câu THẬT SỰ áp (cờ bật + có giá trị)
    ignored: tuple[str, ...]             # tham số request bị bỏ qua vì sai ngữ cảnh

    # ------------------------------------------------------------------ giá trị hiệu lực cho mask
    @property
    def mask_taxonomy(self) -> str | None:
        if self.taxonomy_source == SOURCE_PARAM or APPLIED_TAXONOMY in self.applied:
            return self.taxonomy
        return None

    @property
    def mask_origin(self) -> str | None:
        return self.route_origin if (self.route_source == SOURCE_PARAM or APPLIED_ROUTE in self.applied) else None

    @property
    def price_active(self) -> bool:
        return self.price_source == SOURCE_PARAM or APPLIED_PRICE in self.applied

    @property
    def star_active(self) -> bool:
        return self.star_min is not None and (self.star_source == SOURCE_PARAM or APPLIED_STAR in self.applied)

    def mask_kwargs(self, *, destination: str | None) -> dict:
        """kwargs cho `UnitIndex.mask` (ngoài `destination`, do use case quyết định theo fallback)."""
        kw: dict = {"taxonomy": self.mask_taxonomy, "destination": destination, "only_available": self.available_only}
        if self.mask_origin:
            kw["origin_city"] = self.mask_origin
        if self.price_active:
            kw["price_min"], kw["price_max"] = self.price_min, self.price_max
        if self.star_active:
            kw["star_min"] = self.star_min
        if APPLIED_MUST_NOT in self.applied:
            kw["exclude_amenities"] = self.must_not_amenities
            kw["exclude_brands"] = self.must_not_brands
        return kw

    def families_in_order(self) -> tuple[tuple[str, dict], ...]:
        """(họ, kwargs cộng dồn) theo thứ tự áp — use case dò họ đầu tiên làm F rỗng (`emptyReason`)."""
        steps: list[tuple[str, dict]] = []
        if self.mask_taxonomy and self.taxonomy_source == SOURCE_QUERY:
            steps.append((APPLIED_TAXONOMY, {"taxonomy": self.mask_taxonomy}))
        if self.mask_origin:
            steps.append((APPLIED_ROUTE, {"origin_city": self.mask_origin}))
        if self.price_active:
            steps.append((APPLIED_PRICE, {"price_min": self.price_min, "price_max": self.price_max}))
        if self.star_active:
            steps.append((APPLIED_STAR, {"star_min": self.star_min}))
        if APPLIED_MUST_NOT in self.applied:
            steps.append((APPLIED_MUST_NOT, {"exclude_amenities": self.must_not_amenities,
                                             "exclude_brands": self.must_not_brands}))
        return tuple(steps)

    # ------------------------------------------------------------------ khai báo
    def as_diagnostics(self, *, revalidated_drops: int = 0, empty_reason: str | None = None,
                       destination_fallback: bool = False) -> dict:
        """Khối `diagnostics.queryPlan` (contract 1.15.0): chỉ khoá có giá trị."""
        out: dict = {}
        if self.taxonomy or self.taxonomy_skipped or self.taxonomy_candidates:
            tax: dict = {"value": self.taxonomy, "source": self.taxonomy_source or "none"}
            if self.taxonomy_skipped:
                tax["skipped"] = self.taxonomy_skipped
            if self.taxonomy_candidates:
                tax["candidates"] = list(self.taxonomy_candidates)
            out["taxonomy"] = tax
        if self.route_source or self.route_skipped:
            route: dict = {"origin": self.route_origin, "destinationCity": self.route_destination,
                           "direction": self.route_direction, "source": self.route_source or "none"}
            if self.route_skipped:
                route["skipped"] = self.route_skipped
            out["route"] = route
        if self.must_not_amenities or self.must_not_brands:
            out["mustNot"] = {"amenities": list(self.must_not_amenities), "brands": list(self.must_not_brands)}
        if self.soft_dropped:
            out["softDropped"] = list(self.soft_dropped)
        if self.unresolved:
            out["unresolved"] = list(self.unresolved)
        if self.price_source:
            out["price"] = {"min": self.price_min, "max": self.price_max, "source": self.price_source}
        if self.star_source:
            out["star"] = {"min": self.star_min, "source": self.star_source}
        if self.applied:
            out["lexicalText"] = self.lexical_text
            out["applied"] = list(self.applied)
        if revalidated_drops:
            out["revalidatedDrops"] = revalidated_drops
        if empty_reason:
            out["emptyReason"] = empty_reason
        if self.ignored:
            out["ignored"] = list(self.ignored)
        return out

    def applied_filters(self, *, destination_fallback: bool = False) -> dict | None:
        """Khối `appliedFilters` (contract C6): những gì ĐÃ lọc; None khi không có gì."""
        hard: dict = {}
        soft: dict = {}
        if self.mask_taxonomy:
            hard["taxonomy"] = self.mask_taxonomy
            if self.taxonomy_source == SOURCE_QUERY:   # tham số request thì như 1.14.0 (không thêm khoá)
                hard["taxonomySource"] = SOURCE_QUERY
        if self.destination.value and not destination_fallback:
            hard["destination"] = self.destination.value
            hard["destinationSource"] = self.destination.source
        if self.mask_origin:
            hard["origin"] = self.mask_origin
            hard["originSource"] = self.route_source
            if self.route_destination:
                hard["destinationCity"] = self.route_destination
        if APPLIED_MUST_NOT in self.applied:
            if self.must_not_amenities:
                hard["mustNotAmenities"] = list(self.must_not_amenities)
            if self.must_not_brands:
                hard["mustNotBrands"] = list(self.must_not_brands)
        if self.price_active:
            if self.price_min is not None:
                hard["priceMin"] = self.price_min
            if self.price_max is not None:
                hard["priceMax"] = self.price_max
            hard["priceSource"] = self.price_source
        if not self.available_only:
            hard["availableOnly"] = False
        if self.star_active:
            soft["starRatingMin"] = self.star_min
            soft["starRatingSource"] = self.star_source
        return {"hard": hard, "soft": soft} if hard or soft else None


def _pick_numeric(parsed: NumericParse, params: PlanParams):
    """(price_min, price_max, price_source, star_min, star_source): param thắng; câu chỉ khai — áp hay không do cờ (`applied`)."""
    price_min = price_max = star_min = None
    price_source = star_source = None
    if params.price_min is not None or params.price_max is not None:
        price_min, price_max, price_source = params.price_min, params.price_max, SOURCE_PARAM
    elif parsed.price_min is not None or parsed.price_max is not None:
        price_min, price_max, price_source = parsed.price_min, parsed.price_max, SOURCE_QUERY
    if params.star_min is not None:
        star_min, star_source = params.star_min, SOURCE_PARAM
    elif parsed.star_min is not None:
        star_min, star_source = parsed.star_min, SOURCE_QUERY
    return price_min, price_max, price_source, star_min, star_source


def build_query_plan(nq: NormalizedQuery | None, raw_query: str, params: PlanParams, flags: PlanFlags,
                     gaz: PlanGazetteers | None = None) -> QueryPlan:
    gaz = gaz or PlanGazetteers()
    text = nq.text if nq is not None else raw_query
    applied: list[str] = []
    ignored: list[str] = []
    consumed: list[tuple[int, int]] = []

    # F6 — giá / sao (chạy trước để "không quá 2 triệu", "không dưới 4 sao" không bị coi là phủ định)
    numeric = parse_numeric(text) if nq is not None else NumericParse()
    price_min, price_max, price_source, star_min, star_source = _pick_numeric(numeric, params)
    if flags.numeric and price_source == SOURCE_QUERY:
        applied.append(APPLIED_PRICE)
    if flags.numeric and star_source == SOURCE_QUERY:
        applied.append(APPLIED_STAR)
    if APPLIED_PRICE in applied or APPLIED_STAR in applied:
        consumed.extend(numeric.spans)

    # F3 — phủ định tiện ích (scope không chạm span số)
    negation = parse_negation(text, protected=tuple(numeric.spans)) if nq is not None else NegationParse()
    must_not_amenities = tuple(dict.fromkeys(m.key for m in negation.must_not))
    if flags.negation and (must_not_amenities or negation.must_not_brands):
        applied.append(APPLIED_MUST_NOT)
    if flags.negation and negation.spans:   # cả cụm mềm "không nhất thiết phải có hồ bơi": bỏ khỏi BM25 để không thành từ khoá dương
        consumed.extend(negation.spans)

    # F4 — loại sản phẩm (bỏ cue trong scope phủ định và cue nằm trong tên thương hiệu)
    vertical = (parse_vertical(text, excluded=tuple(negation.spans), brand_names=gaz.brand_names) if nq is not None
                else VerticalParse())
    if params.taxonomy:
        taxonomy, taxonomy_source = params.taxonomy, SOURCE_PARAM
    elif vertical.taxonomy:
        taxonomy, taxonomy_source = vertical.taxonomy, SOURCE_QUERY
        if flags.taxonomy:
            applied.append(APPLIED_TAXONOMY)
            consumed.extend(vertical.spans)
    else:
        taxonomy, taxonomy_source = None, None
    taxonomy_eff = taxonomy if (taxonomy_source == SOURCE_PARAM or APPLIED_TAXONOMY in applied) else params.taxonomy

    # F5 — tuyến bay: chỉ câu vé máy bay (taxonomy hiệu lực = flight hoặc cụm bay) hoặc khi có tham số origin
    flight_context = taxonomy_eff == TAXONOMY_FLIGHT or is_flight_query(raw_query, params.taxonomy)
    roles: FlightRoles | None = None
    route_origin = route_destination = route_direction = route_source = route_skipped = None
    if flight_context and nq is not None:
        roles = parse_flight_roles(text, gaz.city_spans(text, nq.destination_spans), gaz.iata, raw_text=raw_query)
    if params.origin:
        if flight_context:
            route_origin, route_source = params.origin, SOURCE_PARAM
            if roles is not None:
                route_destination, route_direction = roles.destination, roles.direction
        else:
            ignored.append("origin")
            route_skipped = SKIPPED_NOT_FLIGHT
    elif roles is not None and (roles.origin or roles.destination):
        route_origin, route_destination, route_direction = roles.origin, roles.destination, roles.direction
        route_skipped = roles.skipped
        route_source = SOURCE_QUERY
        if flags.route and (roles.origin or roles.destination):
            applied.append(APPLIED_ROUTE)
            consumed.extend(roles.spans)
    elif roles is not None and roles.skipped:
        route_skipped = roles.skipped

    # F1 — điểm đến (tái dùng luật 05/10); câu bay có vai trò đích rõ ràng → điểm đến = đích của tuyến
    decision = decide_destination(nq, params.destination, taxonomy_eff, flags.destination, query=raw_query)
    if (decision.source is None and route_destination and APPLIED_ROUTE in applied):
        decision = DestinationDecision(route_destination, SOURCE_QUERY, None, decision.candidates)

    lexical_text = remove_spans(text, consumed) if consumed else text
    drop = frozenset(tokens(decision.value)) if decision.source == SOURCE_QUERY else frozenset()

    return QueryPlan(
        destination=decision,
        taxonomy=taxonomy, taxonomy_source=taxonomy_source, taxonomy_skipped=vertical.skipped,
        taxonomy_candidates=tuple(vertical.verticals),
        route_origin=route_origin, route_destination=route_destination, route_direction=route_direction,
        route_source=route_source, route_skipped=route_skipped,
        must_not_amenities=must_not_amenities, must_not_brands=tuple(negation.must_not_brands),
        soft_dropped=tuple(negation.soft_dropped) + tuple(numeric.dropped),
        unresolved=tuple(negation.unresolved) + tuple(numeric.unresolved),
        price_min=price_min, price_max=price_max, price_source=price_source,
        star_min=star_min, star_source=star_source, available_only=params.available_only,
        lexical_text=lexical_text, drop_tokens=drop, applied=tuple(applied), ignored=tuple(ignored),
    )
