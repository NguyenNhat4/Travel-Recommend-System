"""Query plan của /search (kiến trúc Phase A, `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` §4–§6; spec §2.2
"QUERY PLAN"; contract 1.15.0 `diagnostics.queryPlan`): gom mọi hard constraint parse từ câu thành một giá trị có cấu trúc
để tầng application dựng mask filter-first, chứ không để vector quyết định phủ định / loại sản phẩm / chiều bay / giá.

Thứ tự parse: giá & sao (F6) → số khách (bỏ qua span đã thành số) → phủ định (F3, bỏ qua span đã thành số) → loại sản phẩm
(F4, bỏ cue trong scope phủ định) → tuyến bay (F5, chỉ câu vé máy bay) → điểm đến (F1, tái dùng `decide_destination`). Tham
số request luôn thắng giá trị suy ra. Mỗi họ một cờ (`PlanFlags`); cờ tắt thì vẫn parse để khai ở `queryPlan` nhưng không vào
mask và không đổi text BM25 — nhờ đó mọi cờ tắt ≡ hành vi cũ. Text đưa vào embed KHÔNG đổi (khoá cache vector); chỉ
`lexical_text` (BM25 + độ phủ vớt) bỏ các cụm đã thành filter.

Router confidence (kiến trúc §5, giai đoạn 3) chỉ là con số khai báo, tính tất định từ các tín hiệu parse (`fallback_reasons`);
PRD không cho gọi LLM ở thanh tìm kiếm nên không có nhánh fallback LLM nào ở đây. Thuần stdlib.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from .constraints import (
    AMBIGUOUS,
    POI_BRAND_CUES,
    SKIPPED_MULTI,
    STRONG,
    WEAK,
    FlightRoles,
    NegationParse,
    NumericParse,
    PartyParse,
    VerticalParse,
    parse_flight_roles,
    parse_negation,
    parse_numeric,
    parse_party,
    parse_vertical,
    remove_spans,
)
from .destination import SOURCE_PARAM, SOURCE_QUERY, DestinationDecision, decide_destination, is_flight_query
from .lexical import fold, tokens
from .normalize import DESTINATION_ALIASES, NormalizedQuery, find_phrases, spans

TAXONOMY_FLIGHT = "flight"
#: Họ filter suy từ câu (giá trị của `queryPlan.applied` và `queryPlan.emptyReason`).
APPLIED_TAXONOMY, APPLIED_ROUTE, APPLIED_MUST_NOT, APPLIED_PRICE, APPLIED_STAR = "taxonomy", "route", "mustNot", "price", "star"
APPLIED_PARTY = "party"
EMPTY_DESTINATION, EMPTY_PARAM = "destination", "param"
SKIPPED_NOT_FLIGHT = "not_flight"
#: Tín hiệu hạ router confidence (kiến trúc §5 "Khi nào gọi LLM?" — ở đây chỉ khai, không gọi gì), theo thứ tự khai báo.
REASON_UNRESOLVED = "unresolved_constraint"     # cụm sau cue phủ định / số tiền không map được, hoặc must-not tự mâu thuẫn
REASON_AMBIGUOUS_ROUTE = "ambiguous_route"      # câu bay có hai địa danh nhưng không rõ vai
REASON_MULTI_VERTICAL = "multi_vertical"        # câu nêu ≥ 2 loại sản phẩm
REASON_WEAK_TAXONOMY = "weak_taxonomy_cue"      # loại sản phẩm chỉ suy từ cue yếu ("nghỉ dưỡng", "phòng")
REASON_PARAM_CONFLICT = "param_conflict"        # tham số destination/taxonomy khác thứ câu nêu
REASON_LONG_MULTI = "long_multi_constraint"     # câu dài (≥ 12 token) và nêu ≥ 2 họ ràng buộc
_LONG_TOKENS, _LONG_FAMILIES = 12, 2
_REASON_PENALTY = 0.25


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
    adults: int | None = None        # travelContext.guests.adults
    children: int | None = None      # travelContext.guests.children


@dataclass(frozen=True)
class PlanFlags:
    """= cờ `SEARCH_*_FILTER`; False → họ đó chỉ parse để khai, không lọc."""
    destination: bool = False
    negation: bool = False
    taxonomy: bool = False
    route: bool = False
    numeric: bool = False
    taxonomy_strong_only: bool = False   # F4 chỉ lọc khi câu có cue loại MẠNH (`constraints.VERTICAL_CUE_STRENGTH`)
    party: bool = False                  # số khách suy từ câu → occupancy tối thiểu


@dataclass(frozen=True)
class PlanGazetteers:
    """Dựng một lần từ catalog đang phục vụ (`SearchProducts.__post_init__`), như `QueryNormalizer`."""
    brand_names: tuple[str, ...] = ()                      # tên (fold) chứa cue loại khác taxonomy của unit → F4 không tính cue
    brand_taxonomy: Mapping[str, str] = field(default_factory=dict)   # tên (fold) ở trên → taxonomy của unit (cue đúng loại vẫn tính)
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
    taxonomy_strength: str | None = None         # strong | weak — cue của taxonomy suy từ câu (None khi param / không có)
    must_not_taxonomies: tuple[str, ...] = ()    # "không lấy combo", "vé lẻ" → combo; cùng họ mustNot
    must_not_flags: tuple[str, ...] = ()         # "combo … không gồm vé máy bay" → includesFlight; cùng họ mustNot
    party_adults: int | None = None
    party_children: int | None = None
    party_total: int | None = None               # occupancy tối thiểu khi họ party đang áp
    party_source: str | None = None              # param | query | None
    confidence: float = 1.0                      # router confidence (kiến trúc §5), chỉ khai
    fallback_reasons: tuple[str, ...] = ()

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

    @property
    def party_active(self) -> bool:
        """Số khách vào mask: tham số request (travelContext.guests) luôn áp; suy từ câu chỉ khi cờ `party` bật."""
        return self.party_total is not None and (self.party_source == SOURCE_PARAM or APPLIED_PARTY in self.applied)

    def _must_not_kwargs(self) -> dict:
        kw: dict = {"exclude_amenities": self.must_not_amenities, "exclude_brands": self.must_not_brands}
        if self.must_not_taxonomies:     # chỉ khi có — kwargs của câu không phủ định loại sản phẩm giữ nguyên như trước
            kw["exclude_taxonomies"] = self.must_not_taxonomies
        if self.must_not_flags:
            kw["exclude_flags"] = self.must_not_flags
        return kw

    def mask_kwargs(self, *, destination: str | None) -> dict:
        """kwargs cho `UnitIndex.mask` (ngoài `destination`, do use case quyết định theo fallback)."""
        kw: dict = {"taxonomy": self.mask_taxonomy, "destination": destination, "only_available": self.available_only}
        if self.mask_origin:
            kw["origin_city"] = self.mask_origin
        if self.price_active:
            kw["price_min"], kw["price_max"] = self.price_min, self.price_max
        if self.star_active:
            kw["star_min"] = self.star_min
        if self.party_active:
            kw["min_occupancy"] = self.party_total
        if APPLIED_MUST_NOT in self.applied:
            kw.update(self._must_not_kwargs())
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
        if self.party_active:
            steps.append((APPLIED_PARTY, {"min_occupancy": self.party_total}))
        if APPLIED_MUST_NOT in self.applied:
            steps.append((APPLIED_MUST_NOT, self._must_not_kwargs()))
        return tuple(steps)

    # ------------------------------------------------------------------ khai báo
    def as_diagnostics(self, *, revalidated_drops: int = 0, empty_reason: str | None = None,
                       destination_fallback: bool = False, extended: bool = False) -> dict:
        """Khối `diagnostics.queryPlan` (contract 1.15.0): chỉ khoá có giá trị.

        `extended=True` thêm các khoá mới (taxonomy.strength, mustNot.taxonomies/flags, party, confidence, fallbackReasons);
        mặc định tắt để response giữ đúng khối 1.15.0 (schema `additionalProperties: false`) tới khi contract nâng bản."""
        out: dict = {}
        if self.taxonomy or self.taxonomy_skipped or self.taxonomy_candidates:
            tax: dict = {"value": self.taxonomy, "source": self.taxonomy_source or "none"}
            if self.taxonomy_skipped:
                tax["skipped"] = self.taxonomy_skipped
            if self.taxonomy_candidates:
                tax["candidates"] = list(self.taxonomy_candidates)
            if extended and self.taxonomy_strength:
                tax["strength"] = self.taxonomy_strength
            out["taxonomy"] = tax
        if self.route_source or self.route_skipped:
            route: dict = {"origin": self.route_origin, "destinationCity": self.route_destination,
                           "direction": self.route_direction, "source": self.route_source or "none"}
            if self.route_skipped:
                route["skipped"] = self.route_skipped
            out["route"] = route
        extra_must_not = extended and bool(self.must_not_taxonomies or self.must_not_flags)
        if self.must_not_amenities or self.must_not_brands or extra_must_not:
            must_not: dict = {"amenities": list(self.must_not_amenities), "brands": list(self.must_not_brands)}
            if extended and self.must_not_taxonomies:
                must_not["taxonomies"] = list(self.must_not_taxonomies)
            if extended and self.must_not_flags:
                must_not["flags"] = list(self.must_not_flags)
            out["mustNot"] = must_not
        if self.soft_dropped:
            out["softDropped"] = list(self.soft_dropped)
        if self.unresolved:
            out["unresolved"] = list(self.unresolved)
        if self.price_source:
            out["price"] = {"min": self.price_min, "max": self.price_max, "source": self.price_source}
        if self.star_source:
            out["star"] = {"min": self.star_min, "source": self.star_source}
        if extended and self.party_source:
            out["party"] = {"adults": self.party_adults, "children": self.party_children, "total": self.party_total,
                            "source": self.party_source}
        if self.applied:
            out["lexicalText"] = self.lexical_text
            out["applied"] = list(self.applied)
        if revalidated_drops:
            out["revalidatedDrops"] = revalidated_drops
        if empty_reason:
            out["emptyReason"] = empty_reason
        if self.ignored:
            out["ignored"] = list(self.ignored)
        if extended and (out or self.fallback_reasons):   # câu không parse ra gì → vẫn bỏ cả khối, như trước
            out["confidence"] = self.confidence
            if self.fallback_reasons:
                out["fallbackReasons"] = list(self.fallback_reasons)
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
            if self.must_not_taxonomies:
                hard["mustNotTaxonomies"] = list(self.must_not_taxonomies)
            if self.must_not_flags:
                hard["mustNotFlags"] = list(self.must_not_flags)
        if self.price_active:
            if self.price_min is not None:
                hard["priceMin"] = self.price_min
            if self.price_max is not None:
                hard["priceMax"] = self.price_max
            hard["priceSource"] = self.price_source
        if self.party_active:
            hard["minOccupancy"] = self.party_total
            hard["partySource"] = self.party_source
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


def _pick_party(parsed: PartyParse, params: PlanParams):
    """(adults, children, total, source): `travelContext.guests` của request thắng câu; tổng = người lớn + trẻ em (chỉ biết
    trẻ em thì không có tổng — không bịa số người lớn)."""
    if params.adults is not None or params.children is not None:
        total = params.adults + (params.children or 0) if params.adults is not None else None
        return params.adults, params.children, total, SOURCE_PARAM
    if parsed.adults is not None or parsed.children is not None or parsed.total is not None:
        return parsed.adults, parsed.children, parsed.total, SOURCE_QUERY
    return None, None, None, None


def _fallback_reasons(text: str, nq: NormalizedQuery | None, params: PlanParams, numeric: NumericParse,
                      negation: NegationParse, vertical: VerticalParse, *, must_not_conflict: bool, must_not_any: bool,
                      route_source: str | None, route_skipped: str | None, party_source: str | None) -> tuple[str, ...]:
    """Tín hiệu router confidence (kiến trúc §5), tất định, không gọi LLM."""
    reasons: list[str] = []
    if negation.unresolved or numeric.unresolved or must_not_conflict:
        reasons.append(REASON_UNRESOLVED)
    if route_skipped == AMBIGUOUS:
        reasons.append(REASON_AMBIGUOUS_ROUTE)
    if vertical.skipped == SKIPPED_MULTI:
        reasons.append(REASON_MULTI_VERTICAL)
    if not params.taxonomy and vertical.taxonomy and vertical.strength == WEAK:
        reasons.append(REASON_WEAK_TAXONOMY)
    named_places = {fold(d) for d in nq.destinations} if nq is not None else set()
    named_taxonomies = (vertical.taxonomy,) if vertical.taxonomy else vertical.verticals
    if (params.destination and named_places and fold(params.destination) not in named_places) \
            or (params.taxonomy and named_taxonomies and params.taxonomy not in named_taxonomies):
        reasons.append(REASON_PARAM_CONFLICT)
    families = sum((bool(vertical.verticals), bool(named_places), route_source == SOURCE_QUERY, must_not_any,
                    numeric.price_min is not None or numeric.price_max is not None, numeric.star_min is not None,
                    party_source == SOURCE_QUERY))
    if len(tokens(text)) >= _LONG_TOKENS and families >= _LONG_FAMILIES:
        reasons.append(REASON_LONG_MULTI)
    return tuple(reasons)


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

    # Số khách (kiến trúc §6 occupancy) — không lấy số trong span giá/sao
    party = parse_party(text, protected=tuple(numeric.spans)) if nq is not None else PartyParse()
    party_adults, party_children, party_total, party_source = _pick_party(party, params)
    if flags.party and party_source == SOURCE_QUERY and party_total is not None:
        applied.append(APPLIED_PARTY)
        consumed.extend(party.spans)

    # F3 — phủ định (scope không chạm span số) và F4 — loại sản phẩm (bỏ cue trong scope phủ định / trong tên thương hiệu).
    # Parse F4 trước khi chốt must-not loại sản phẩm: không bao giờ loại chính loại câu (hoặc tham số) đang hỏi.
    negation = parse_negation(text, protected=tuple(numeric.spans)) if nq is not None else NegationParse()
    vertical = (parse_vertical(text, excluded=tuple(negation.spans), brand_names=gaz.brand_names,
                               brand_taxonomy=gaz.brand_taxonomy) if nq is not None
                else VerticalParse())
    if params.taxonomy:
        taxonomy, taxonomy_source = params.taxonomy, SOURCE_PARAM
    elif vertical.taxonomy:
        taxonomy, taxonomy_source = vertical.taxonomy, SOURCE_QUERY
    else:
        taxonomy, taxonomy_source = None, None
    must_not_amenities = tuple(dict.fromkeys(m.key for m in negation.must_not))
    must_not_taxonomies = tuple(t for t in negation.must_not_taxonomies if t != taxonomy)
    must_not_conflict = len(must_not_taxonomies) < len(negation.must_not_taxonomies)
    must_not_flags = tuple(negation.must_not_flags)
    must_not_any = bool(must_not_amenities or negation.must_not_brands or must_not_taxonomies or must_not_flags)
    if flags.negation and must_not_any:
        applied.append(APPLIED_MUST_NOT)
    if flags.negation and negation.spans:   # cả cụm mềm "không nhất thiết phải có hồ bơi": bỏ khỏi BM25 để không thành từ khoá dương
        consumed.extend(negation.spans)

    if taxonomy_source == SOURCE_QUERY and flags.taxonomy \
            and (not flags.taxonomy_strong_only or vertical.strength == STRONG):
        applied.append(APPLIED_TAXONOMY)
        # tên điểm vui chơi (VinWonders, Safari, Grand World) là tên sản phẩm → giữ cho BM25 dù đã thành filter
        consumed.extend(sp for sp in vertical.spans if fold(text[sp[0]:sp[1]]) not in POI_BRAND_CUES)
    taxonomy_eff = taxonomy if (taxonomy_source == SOURCE_PARAM or APPLIED_TAXONOMY in applied) else params.taxonomy

    # F5 — tuyến bay: chỉ câu vé máy bay (taxonomy hiệu lực = flight hoặc cụm bay) hoặc khi có tham số origin
    # câu đã có MỘT loại khác flight (tham số, hoặc combo đứng đầu "combo vé máy bay và khách sạn Đà Lạt") không phải câu vé
    # máy bay dù chứa cụm bay: không parse tuyến, điểm đến lọc như câu thường (c0706)
    non_flight = taxonomy is not None and taxonomy != TAXONOMY_FLIGHT
    flight_context = taxonomy_eff == TAXONOMY_FLIGHT or (not non_flight and is_flight_query(raw_query, params.taxonomy))
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
    decision = decide_destination(nq, params.destination, taxonomy_eff, flags.destination, query=raw_query,
                                  flight=flight_context)
    if (decision.source is None and route_destination and APPLIED_ROUTE in applied):
        decision = DestinationDecision(route_destination, SOURCE_QUERY, None, decision.candidates)

    lexical_text = remove_spans(text, consumed) if consumed else text
    drop = frozenset(tokens(decision.value)) if decision.source == SOURCE_QUERY else frozenset()
    reasons = _fallback_reasons(text, nq, params, numeric, negation, vertical, must_not_conflict=must_not_conflict,
                                must_not_any=must_not_any, route_source=route_source, route_skipped=route_skipped,
                                party_source=party_source)

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
        taxonomy_strength=vertical.strength if taxonomy_source == SOURCE_QUERY else None,
        must_not_taxonomies=must_not_taxonomies, must_not_flags=must_not_flags,
        party_adults=party_adults, party_children=party_children, party_total=party_total, party_source=party_source,
        confidence=round(max(0.0, 1.0 - _REASON_PENALTY * len(reasons)), 2), fallback_reasons=reasons,
    )
