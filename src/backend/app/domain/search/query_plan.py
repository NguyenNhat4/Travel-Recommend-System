"""Query plan của /search (kiến trúc Phase A, `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` §4–§6; spec §2.2
"QUERY PLAN"; contract 1.15.0 `diagnostics.queryPlan`): gom mọi hard constraint parse từ câu thành một giá trị có cấu trúc
để tầng application dựng mask filter-first, chứ không để vector quyết định phủ định / loại sản phẩm / chiều bay / giá.

Thứ tự parse: giá & sao (F6) → thời lượng (F7, bỏ qua span đã thành số) → số khách (bỏ qua span đã thành số) → phủ định (F3,
bỏ qua span đã thành số) → loại sản phẩm (F4, bỏ cue trong scope phủ định) → entity điểm vui chơi (vai trò gate / location, bỏ
cụm trong scope phủ định) → tuyến bay (F5, chỉ câu vé máy bay) → địa danh gazetteer (POI → điểm đến catalog) → điểm đến (F1,
tái dùng `decide_destination`). Tham số request luôn thắng giá trị suy ra. Mỗi họ một cờ (`PlanFlags`); với F1, F3–F6 và số
khách, cờ tắt thì vẫn parse để khai ở `queryPlan` nhưng không vào mask và không đổi text BM25 — nhờ đó mọi cờ tắt ≡ hành vi
cũ. Ba họ 1.18.0 (`duration`, `poi`, `entity`; spec `docs/spec/bench/tong-hop-chinh-sua-luong-search-ota.md`) đi xa hơn: cờ
tắt thì KHÔNG parse, không khai — response y hệt 1.17.0. Text đưa vào embed KHÔNG đổi (khoá cache vector); chỉ
`lexical_text` (BM25 + độ phủ vớt) bỏ các cụm đã thành filter.

Router confidence (kiến trúc §5, giai đoạn 3) chỉ là con số khai báo, tính tất định từ các tín hiệu parse (`fallback_reasons`);
PRD không cho gọi LLM ở thanh tìm kiếm nên không có nhánh fallback LLM nào ở đây. Thuần stdlib.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace

from ..catalog.stay_dates import StayDates
from .constraints import (
    AMBIGUOUS,
    HOTEL,
    POI_BRAND_CUES,
    SKIPPED_MULTI,
    STRONG,
    WEAK,
    DurationParse,
    FlightRoles,
    NegationParse,
    NumericParse,
    PartyParse,
    VerticalParse,
    parse_duration,
    parse_flight_roles,
    parse_negation,
    parse_numeric,
    parse_party,
    parse_vertical,
    remove_spans,
    vertical_cue_spans,
)
from .destination import SOURCE_PARAM, SOURCE_QUERY, DestinationDecision, decide_destination, is_flight_query
from .explain import Grams, explain_residual, has_content
from .gazetteer import ENTITY_TAXONOMIES, MAX_ALIAS_TOKENS, Place, entity_table, place_table
from .lexical import fold, tokens
from .normalize import DESTINATION_ALIASES, NormalizedQuery, find_phrases, spans

TAXONOMY_FLIGHT = "flight"
#: Họ filter suy từ câu (giá trị của `queryPlan.applied` và `queryPlan.emptyReason`).
APPLIED_TAXONOMY, APPLIED_ROUTE, APPLIED_MUST_NOT, APPLIED_PRICE, APPLIED_STAR = "taxonomy", "route", "mustNot", "price", "star"
APPLIED_PARTY = "party"
#: 1.18.0: `duration` chỉ tác động lên `lexical_text` (không vào mask → `emptyReason = duration` không bao giờ phát; khai trong
#: enum cho đủ họ); `entity` = gate cứng vào mask.
APPLIED_DURATION, APPLIED_ENTITY = "duration", "entity"
#: Vai trò entity (`queryPlan.entity.role`): gate = lọc chỉ còn attraction/combo có tên chứa entity; location = chỉ định vị.
ROLE_GATE, ROLE_LOCATION = "gate", "location"
ROLE_STAY = "stay"                     # thời lượng của câu lưu trú: chỉ khai, không lọc (plan 2026-10-13 §2.3)
ROLE_SOFT = "soft"                     # câu còn nội dung ngoài thời lượng: chỉ khai + bỏ cụm, không lọc (chốt 14/10)
EMPTY_UNEXPLAINED = "unexplained"      # residual chỉ là tên lạ / câu vô nghĩa (FR-SRC-04 chốt 13/10)
APPLIED_DATE = "date"          # travelContext.checkIn/checkOut — chỉ từ tham số request, không suy từ câu
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
    stay: StayDates | None = None    # travelContext.checkIn / checkOut (+ hôm nay giờ Việt Nam) — luôn áp khi có


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
    # 1.18.0 — tắt thì KHÔNG parse (không như các họ trên): response y hệt 1.17.0.
    duration: bool = False               # F7 "3 ngày 2 đêm" → bỏ cụm khỏi lexical_text, khai queryPlan.duration
    poi: bool = False                    # địa danh gazetteer ("Hồ Hoàn Kiếm") → điểm đến catalog vào F1
    entity: bool = False                 # điểm vui chơi (VinWonders…) → gate cứng attraction/combo có tên chứa entity
    # 1.30.0 (plan 2026-10-13) — tắt thì không có đường code mới chạy.
    duration_mask: bool = False          # thời lượng (cần `duration`) → vai trò gate lọc vé/combo; câu lưu trú → stay, không lọc
    embed_residual: bool = False         # dense embed câu đã bỏ span điều kiện; residual rỗng + gate thời lượng → chỉ-filter
    unexplained: bool = False            # residual chỉ là tên lạ / vô nghĩa → rỗng; cụm lạ khác → bỏ khỏi truy vấn


@dataclass(frozen=True)
class PlanGazetteers:
    """Dựng một lần từ catalog đang phục vụ (`SearchProducts.__post_init__`), như `QueryNormalizer`."""
    brand_names: tuple[str, ...] = ()                      # tên (fold) chứa cue loại khác taxonomy của unit → F4 không tính cue
    brand_taxonomy: Mapping[str, str] = field(default_factory=dict)   # tên (fold) ở trên → taxonomy của unit (cue đúng loại vẫn tính)
    iata: Mapping[str, str] = field(default_factory=dict)  # mã sân bay VIẾT HOA → thành phố catalog (originCity/destinationCity)
    # Thành phố đi/đến của tuyến bay (`attributes.originCity/destinationCity`): nơi đi thường KHÔNG phải điểm đến du lịch của
    # catalog ("Hà Nội" chỉ là originCity) nên gazetteer điểm đến của QueryNormalizer không nhận ra — F5 tra thêm bảng này.
    flight_cities: tuple[str, ...] = ()
    # 1.18.0 (`gazetteer.py`): alias (fold) → khoá entity điểm vui chơi; alias → `Place` có điểm đến catalog. Mặc định = bảng
    # đầy đủ (test domain không cần fixture); use case thu hẹp theo catalog: `place_table(destinations)` và chỉ khoá entity có
    # mặt trong `UnitAttributes.entities` (entity không có sản phẩm không bao giờ gate).
    entities: Mapping[str, str] = field(default_factory=entity_table)
    places: Mapping[str, Place] = field(default_factory=place_table)
    # 1.30.0: unigram/bigram của tên + mô tả catalog (`explain.Grams`) — cần cho cờ `unexplained`; None → luật không chạy.
    vocab: Grams | None = None

    def entity_spans(self, text: str) -> tuple[tuple[int, int], ...]:
        """Span ký tự của mọi alias entity trong câu (1.30.0: phần "đã hiểu" khi giải thích residual)."""
        if not self.entities:
            return ()
        toks = spans(text)
        return tuple((toks[i][0], toks[i + n - 1][1]) for i, n, _ in find_phrases(toks, self.entities.__contains__,
                                                                                    MAX_ALIAS_TOKENS))

    def entity_keys(self, text: str, excluded: Iterable[tuple[int, int]] = ()) -> tuple[str, ...]:
        """Khoá entity trong câu: khớp dài nhất trên token đã fold, thứ tự xuất hiện, không lặp; bỏ cụm nằm trong `excluded`
        (span phủ định — "không lấy VinWonders, vé Safari" → chỉ safari)."""
        if not self.entities:
            return ()
        toks = spans(text)
        ex = tuple(excluded)
        out: list[str] = []
        for i, n, key in find_phrases(toks, self.entities.__contains__, MAX_ALIAS_TOKENS):
            start, end = toks[i][0], toks[i + n - 1][1]
            if any(s < end and start < e for s, e in ex):
                continue
            k = self.entities[key]
            if k not in out:
                out.append(k)
        return tuple(out)

    def place_hits(self, text: str, known: tuple[tuple[int, int, str], ...],
                   excluded: Iterable[tuple[int, int]] = ()) -> tuple[tuple[int, int, Place], ...]:
        """Địa danh gazetteer trong câu → (bắt đầu, kết thúc, Place), theo thứ tự xuất hiện; bỏ cụm chồng span điểm đến mà bước
        chuẩn hoá đã nhận ("Phố cổ Hội An" đã có "Hội An") hoặc nằm trong `excluded` (phủ định)."""
        if not self.places:
            return ()
        toks = spans(text)
        taken = [(s, e) for s, e, _ in known] + list(excluded)
        out: list[tuple[int, int, Place]] = []
        for i, n, key in find_phrases(toks, self.places.__contains__, MAX_ALIAS_TOKENS):
            start, end = toks[i][0], toks[i + n - 1][1]
            if any(s < end and start < e for s, e in taken):
                continue
            out.append((start, end, self.places[key]))
        return tuple(out)

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
    stay: StayDates | None = None                # contract 1.19.0: bộ lọc ngày của request (nguồn luôn là `param`)
    # 1.18.0 — chỉ có giá trị khi cờ họ đó bật (tắt = mặc định, không khai)
    duration_days: int | None = None
    duration_nights: int | None = None
    duration_source: str | None = None           # query | None
    entity_keys: tuple[str, ...] = ()            # khoá entity trong câu (cả hai vai trò)
    entity_role: str | None = None               # gate | location | None
    location: Place | None = None                # địa danh gazetteer đầu tiên trong câu
    poi_destinations: tuple[str, ...] = ()       # điểm đến suy từ địa danh gazetteer (không phải tên thành phố trong câu)
    # 1.30.0 — chỉ có giá trị khi cờ tương ứng bật
    duration_role: str | None = None             # gate | stay | None (cờ duration_mask)
    dense_text: str | None = None                # câu đem embed khi khác câu đầy đủ (cờ embed_residual)
    filter_only: bool = False                    # residual rỗng + gate thời lượng → R = F, không cutoff
    unexplained: tuple[str, ...] = ()            # cụm khiến câu không có đáp án (emptyReason `unexplained`)
    unparsed: tuple[str, ...] = ()               # cụm lạ đã bỏ khỏi truy vấn

    @property
    def destination_via_poi(self) -> bool:
        """Điểm đến đang lọc đến từ địa danh gazetteer (→ `appliedFilters.hard.destinationSource = poi`). So với
        `poi_destinations` chứ không phải "không có trong nq.destinations": đích tuyến bay suy từ IATA ("HAN DAD") cũng không
        nằm trong `nq.destinations` nhưng không phải POI."""
        return self.destination.source == SOURCE_QUERY and self.destination.value in self.poi_destinations

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

    @property
    def date_active(self) -> bool:
        return self.stay is not None

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
        if self.date_active:
            kw["stay"] = self.stay
        if APPLIED_MUST_NOT in self.applied:
            kw.update(self._must_not_kwargs())
        if APPLIED_ENTITY in self.applied:
            kw["require_entities"] = self.entity_keys
        if self.duration_role == ROLE_GATE:
            kw["duration_days"], kw["duration_nights"] = self.duration_days, self.duration_nights
        return kw

    def families_in_order(self) -> tuple[tuple[str, dict], ...]:
        """(họ, kwargs cộng dồn) theo thứ tự áp — use case dò họ đầu tiên làm F rỗng (`emptyReason`).

        `entity` đứng ngay sau loại suy từ câu: tab Web gửi `taxonomy=hotel` cho câu VinWonders → mask gốc (hotel) chưa rỗng,
        bước entity làm rỗng → `emptyReason = entity` (không phải `param`). `duration` không có bước (không vào mask)."""
        steps: list[tuple[str, dict]] = []
        if self.mask_taxonomy and self.taxonomy_source == SOURCE_QUERY:
            steps.append((APPLIED_TAXONOMY, {"taxonomy": self.mask_taxonomy}))
        if APPLIED_ENTITY in self.applied:
            steps.append((APPLIED_ENTITY, {"require_entities": self.entity_keys}))
        if self.duration_role == ROLE_GATE:
            steps.append((APPLIED_DURATION, {"duration_days": self.duration_days, "duration_nights": self.duration_nights}))
        if self.mask_origin:
            steps.append((APPLIED_ROUTE, {"origin_city": self.mask_origin}))
        if self.price_active:
            steps.append((APPLIED_PRICE, {"price_min": self.price_min, "price_max": self.price_max}))
        if self.star_active:
            steps.append((APPLIED_STAR, {"star_min": self.star_min}))
        if self.party_active:
            steps.append((APPLIED_PARTY, {"min_occupancy": self.party_total}))
        if self.date_active:
            steps.append((APPLIED_DATE, {"stay": self.stay}))
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
        # 1.18.0: ba khối chỉ có giá trị khi cờ bật (tắt không parse) → có là khai, không cần `extended`
        if self.duration_source:
            out["duration"] = {"days": self.duration_days, "nights": self.duration_nights, "source": self.duration_source}
            if self.duration_role:
                out["duration"]["role"] = self.duration_role
        if self.entity_keys:
            out["entity"] = {"keys": list(self.entity_keys), "role": self.entity_role}
        if self.location is not None:
            out["location"] = {"key": self.location.key, "name": self.location.name, "kind": self.location.kind,
                               "destination": self.location.destination}
        if extended and self.stay is not None:
            out["date"] = {"checkIn": self.stay.check_in.isoformat(),
                           "checkOut": self.stay.check_out.isoformat() if self.stay.check_out else None,
                           "source": SOURCE_PARAM}
        if self.applied:
            out["lexicalText"] = self.lexical_text
            out["applied"] = list(self.applied)
        if self.dense_text is not None:
            out["denseText"] = self.dense_text
        if self.unexplained:
            out["unexplained"] = list(self.unexplained)
        if self.unparsed:
            out["unparsed"] = list(self.unparsed)
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
            hard["destinationSource"] = "poi" if self.destination_via_poi else self.destination.source
        if APPLIED_ENTITY in self.applied:
            hard["entity"] = list(self.entity_keys)
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
        if self.date_active:
            hard["checkIn"] = self.stay.check_in.isoformat()
            if self.stay.check_out is not None:
                hard["checkOut"] = self.stay.check_out.isoformat()
            hard["dateSource"] = SOURCE_PARAM
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


def _understood_spans(text, nq, gaz, numeric, party, duration, negation, roles, *,
                      names_are_content: bool = False) -> list[tuple[int, int]]:
    """Span "đã hiểu" của câu (1.30.0): số / số khách / thời lượng / phủ định / tuyến bay / điểm đến / địa danh / entity / mọi cue
    loại — tính cả khi cờ lọc của họ đó tắt (bench 14/10: "combo 3N2Đ" khi F7 tắt, "ks gần hồ gươm" khi POI tắt từng bị coi là
    chữ lạ → rỗng nhầm). `names_are_content`: tên điểm vui chơi / entity (VinWonders, Safari…) KHÔNG tính là điều kiện — dùng khi
    xét câu "chỉ có thời lượng" ("VinWonders 3 ngày 2 đêm" còn nội dung → không lọc cứng)."""
    duration_spans = duration.spans or parse_duration(text, protected=(*numeric.spans, *party.spans)).spans
    cond: list[tuple[int, int]] = [*numeric.spans, *party.spans, *duration_spans, *negation.spans,
                                   *((a, b) for a, b, _ in nq.destination_spans),
                                   *(sp for _, sp in vertical_cue_spans(text)
                                     if not (names_are_content and fold(text[sp[0]:sp[1]]) in POI_BRAND_CUES))]
    if roles is not None:
        cond.extend(roles.spans)
    cond.extend((s, e) for s, e, _ in gaz.place_hits(text, nq.destination_spans, excluded=tuple(negation.spans)))
    if not names_are_content:
        cond.extend(gaz.entity_spans(text))
    return cond


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

    # F7 — thời lượng (1.18.0): CHỈ parse khi cờ bật; số trong span giá ("2 triệu/đêm") và số khách không phải thời lượng.
    # Chỉ tiêu cụm khỏi câu BM25 (hotel "ngay … Chợ Đêm" không còn được vớt vì "ngay"/"dem"); không vào mask (catalog chưa có
    # trường thời lượng — P1). Dense vẫn dùng câu đầy đủ.
    duration = (parse_duration(text, protected=(*numeric.spans, *party.spans))
                if flags.duration and nq is not None else DurationParse())
    duration_source = SOURCE_QUERY if (duration.days is not None or duration.nights is not None) else None
    if duration_source:
        applied.append(APPLIED_DURATION)
        consumed.extend(duration.spans)

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

    # Entity điểm vui chơi (1.18.0, gate cứng): CHỈ khi cờ bật. Vai trò theo cue loại CỦA CÂU (tham số taxonomy của request —
    # tab Web — không đổi vai trò, chỉ giao với mask): câu không nêu loại, hoặc nêu attraction/combo → gate (chỉ giữ unit
    # attraction/combo có tên chứa entity); câu nêu loại khác (khách sạn/vé máy bay/golf — kể cả cue yếu "phòng gần Grand
    # World") hoặc ≥ 2 loại → location (entity chỉ định vị, c0697). Cụm entity không bị tiêu (là tên sản phẩm, BM25 cần).
    entity_keys: tuple[str, ...] = ()
    entity_role: str | None = None
    if flags.entity and nq is not None:
        entity_keys = gaz.entity_keys(text, excluded=tuple(negation.spans))
        if entity_keys:
            gate = vertical.skipped != SKIPPED_MULTI and (vertical.taxonomy is None or vertical.taxonomy in ENTITY_TAXONOMIES)
            entity_role = ROLE_GATE if gate else ROLE_LOCATION
            if gate:
                applied.append(APPLIED_ENTITY)

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

    # Địa danh gazetteer (1.18.0): CHỈ khi cờ bật. "Hồ Hoàn Kiếm" → Hà Nội được thêm vào danh sách địa danh của câu rồi đi qua
    # đúng luật F1 (một nơi → lọc với source = query, giữ FR-SRC-04 fallback + drop_tokens; ≥ 2 nơi → multi; câu bay → flight).
    # Bỏ cụm chồng span điểm đến normalizer đã nhận ("Phố cổ Hội An") và cụm trong scope phủ định. `_fallback_reasons` vẫn
    # nhận `nq` gốc → confidence và trigger LLM không đổi.
    location: Place | None = None
    poi_destinations: tuple[str, ...] = ()
    nq_dest = nq
    if flags.poi and nq is not None:
        hits = gaz.place_hits(text, nq.destination_spans, excluded=tuple(negation.spans))
        if hits:
            location = hits[0][2]
            poi_destinations = tuple(dict.fromkeys(p.destination for _, _, p in hits
                                                   if p.destination and p.destination not in nq.destinations))
            if poi_destinations:
                nq_dest = replace(nq, destinations=(*nq.destinations, *poi_destinations))

    # F1 — điểm đến (tái dùng luật 05/10); câu bay có vai trò đích rõ ràng → điểm đến = đích của tuyến
    decision = decide_destination(nq_dest, params.destination, taxonomy_eff, flags.destination, query=raw_query,
                                  flight=flight_context)
    if (decision.source is None and route_destination and APPLIED_ROUTE in applied):
        decision = DestinationDecision(route_destination, SOURCE_QUERY, None, decision.candidates)

    # 1.30.0 — vai trò thời lượng: câu có cue lưu trú ("khách sạn Đà Lạt 2 ngày 1 đêm") → stay (không lọc, khách sạn không có
    # thời lượng cố định); còn lại → gate (chỉ vé / combo đúng số ngày).
    duration_role = None
    if flags.duration_mask and duration_source:
        # Chốt 14/10 (bench gold_v7: gate cứng làm mất vé VinWonders không ghi số ngày ở "VinWonders 3 ngày 2 đêm"): chỉ lọc cứng
        # khi câu CHỈ có thời lượng (ngoài điểm đến, cue loại, số…); câu còn nội dung → soft (không lọc); câu lưu trú → stay.
        if HOTEL in vertical.verticals:
            duration_role = ROLE_STAY
        elif nq is not None and has_content(text, _understood_spans(text, nq, gaz, numeric, party, duration, negation,
                                                                     roles, names_are_content=True)):
            duration_role = ROLE_SOFT
        else:
            duration_role = ROLE_GATE

    unexplained: tuple[str, ...] = ()
    unparsed: tuple[str, ...] = ()
    dense_text: str | None = None
    filter_only = False
    if (flags.unexplained or flags.embed_residual) and nq is not None:
        # phần "điều kiện" của câu: số / số khách / thời lượng / phủ định / tuyến bay / điểm đến / địa danh / mọi cue loại
        cond = _understood_spans(text, nq, gaz, numeric, party, duration, negation, roles)
        unparsed_spans: tuple[tuple[int, int], ...] = ()
        if flags.unexplained and gaz.vocab is not None:
            # "có điều kiện" = có filter đang áp hoặc câu nêu điểm đến catalog (kể cả khi F1 tắt); cue loại một mình không tính
            # ("combo du lịch Cà Mau": Cà Mau không có trong catalog → câu không có đáp án)
            residual = explain_residual(text, cond, gaz.vocab,
                                        has_filters=bool(applied) or decision.value is not None or bool(nq.destinations))
            unexplained, unparsed, unparsed_spans = residual.unexplained, residual.unparsed, residual.unparsed_spans
            consumed.extend(unparsed_spans)
        if flags.embed_residual and not unexplained:
            if not has_content(text, (*cond, *unparsed_spans)):
                filter_only = duration_role == ROLE_GATE
            else:
                dense_spans = [*duration.spans, *unparsed_spans,
                               *(numeric.spans if (APPLIED_PRICE in applied or APPLIED_STAR in applied) else ()),
                               *(party.spans if APPLIED_PARTY in applied else ()),
                               *(negation.spans if flags.negation else ())]
                candidate = remove_spans(text, dense_spans) if dense_spans else text
                dense_text = candidate if candidate and candidate != text else None

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
        duration_days=duration.days, duration_nights=duration.nights, duration_source=duration_source,
        entity_keys=entity_keys, entity_role=entity_role, location=location, poi_destinations=poi_destinations,
        stay=params.stay,
        duration_role=duration_role, dense_text=dense_text, filter_only=filter_only,
        unexplained=unexplained, unparsed=unparsed,
    )
