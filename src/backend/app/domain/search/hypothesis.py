"""Giả thuyết LLM cho query plan của /search (kiến trúc search §5 "Router confidence và LLM fallback"; đề xuất đã chốt
`docs/prd/update/2026-10-06-search-llm-fallback-query-plan.md`; contract 1.17.0 `diagnostics.queryPlan.llm`).

LLM chỉ trả một **giả thuyết có cấu trúc** (`QueryHypothesis`): loại sản phẩm, điểm đến, tuyến bay, phủ định, giá/sao, số khách —
không `productId`, không xếp hạng. Module này là phần thuần (stdlib), không gọi LLM:

1. `validate_hypothesis` — kiểm từng giá trị với từ vựng của catalog (`HypothesisVocab`): taxonomy ∈ enum contract, điểm đến /
   thành phố bay ∈ gazetteer catalog VÀ có mặt trong câu (không nhận địa danh LLM tự nghĩ ra), khoá tiện ích ∈
   `amenities.KEYS`, số trong khoảng hợp lý và câu có dấu hiệu tương ứng (chữ số, "sao", cue phủ định). Giá trị hỏng → `rejected`,
   không bao giờ thành filter.
2. `merge_hypothesis` — chỉ điền ô mà plan rule để trống; tham số request và giá trị rule luôn thắng (khác → `rejected`
   `param_set` / `rule_set`). Mỗi họ vẫn theo cờ của nó (`PlanFlags`): giá trị điền vào được khai ở `queryPlan` với
   `source = query` và chỉ vào mask khi cờ họ đó bật — y như giá trị rule parse ra. Riêng điểm đến: ô của plan nghĩa là "đang
   lọc", nên cờ `destination` tắt → `rejected flag_off`. `lexical_text` không đổi (không biết span của LLM → không cắt chữ khỏi
   BM25), router confidence / fallbackReasons giữ của rule.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from .amenities import KEYS as AMENITY_KEYS
from .destination import SOURCE_PARAM, SOURCE_QUERY, DestinationDecision, is_flight_query
from .lexical import fold, tokens
from .query_plan import (
    APPLIED_MUST_NOT,
    APPLIED_PARTY,
    APPLIED_PRICE,
    APPLIED_ROUTE,
    APPLIED_STAR,
    APPLIED_TAXONOMY,
    SKIPPED_NOT_FLIGHT,
    TAXONOMY_FLIGHT,
    PlanFlags,
    QueryPlan,
)

#: Enum `Taxonomy` của contract (`schemas/common.yaml`).
CONTRACT_TAXONOMIES: tuple[str, ...] = ("hotel", "flight", "attraction", "combo", "golf")
#: Giả thuyết tự chấm dưới mức này thì bỏ cả giả thuyết (`rejected: hypothesis/low_confidence`).
MIN_HYPOTHESIS_CONFIDENCE = 0.5
PRICE_LIMIT = 2_000_000_000          # VND; combo đắt nhất catalog cỡ trăm triệu
PARTY_LIMIT = 50

#: Tên trường trong `queryPlan.llm.accepted` / `rejected[].field`.
F_HYPOTHESIS, F_TAXONOMY, F_DESTINATION, F_ORIGIN, F_DESTINATION_CITY = (
    "hypothesis", "taxonomy", "destination", "origin", "destinationCity")
F_MUST_NOT_AMENITIES, F_MUST_NOT_TAXONOMIES, F_PRICE, F_STAR, F_PARTY = (
    "mustNotAmenities", "mustNotTaxonomies", "price", "star", "party")
#: Lý do trong `queryPlan.llm.rejected[].reason`.
R_INVALID, R_NOT_IN_CATALOG, R_NOT_IN_QUERY, R_NO_CUE, R_OUT_OF_RANGE = (
    "invalid_value", "not_in_catalog", "not_in_query", "no_cue", "out_of_range")
R_PARAM_SET, R_RULE_SET, R_FLAG_OFF, R_CONFLICT, R_MULTI_VERTICAL, R_NOT_FLIGHT, R_LOW_CONFIDENCE = (
    "param_set", "rule_set", "flag_off", "conflict", "multi_vertical", "not_flight", "low_confidence")

#: Dấu hiệu (token đã fold) bắt buộc phải có trong câu để nhận phủ định / sao / số khách từ LLM — chặn LLM suy diễn.
_NEGATION_TOKENS = frozenset({"khong", "ko", "kg", "tru", "chang", "khoi", "without", "except", "no", "non"})
_STAR_TOKENS = frozenset({"sao", "star", "stars"})
_NUMBER_WORDS = frozenset({"mot", "hai", "ba", "bon", "tu", "nam", "sau", "bay", "tam", "chin", "muoi", "doi", "cap",
                           "chong", "nguoi", "khach", "be", "con", "tre"})
_MONEY_TOKENS = frozenset({"trieu", "tr", "nghin", "ngan", "k", "vnd", "dong", "cu", "lit"})


@dataclass(frozen=True)
class QueryHypothesis:
    """Giả thuyết LLM — giá trị thô như model trả (chưa kiểm). `from_mapping` chịu được JSON lệch kiểu."""
    intent: Any = None
    confidence: Any = None
    destination: Any = None
    taxonomy: Any = None
    origin: Any = None
    destination_city: Any = None
    must_not_amenities: tuple = ()
    must_not_taxonomies: tuple = ()
    price_min: Any = None
    price_max: Any = None
    star_min: Any = None
    party_total: Any = None
    soft_preferences: tuple = ()
    unknown_slots: tuple = ()

    _LISTS = ("must_not_amenities", "must_not_taxonomies", "soft_preferences", "unknown_slots")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "QueryHypothesis":
        """Chỉ lấy khoá đã biết; danh sách → tuple (chuỗi đơn → tuple một phần tử); chuỗi rỗng → None."""
        data = data or {}
        kw: dict[str, Any] = {}
        for name in cls.__dataclass_fields__:
            if name not in data:
                continue
            v = data[name]
            if name in cls._LISTS:
                if v is None:
                    v = ()
                elif isinstance(v, (str, int, float)):
                    v = (v,)
                elif isinstance(v, Iterable) and not isinstance(v, Mapping):
                    v = tuple(x for x in v if x is not None and x != "")
                else:
                    v = (v,)
            elif isinstance(v, str) and not v.strip():
                v = None
            kw[name] = v
        return cls(**kw)

    def as_dict(self) -> dict[str, Any]:
        return {name: (list(getattr(self, name)) if name in self._LISTS else getattr(self, name))
                for name in self.__dataclass_fields__ if not name.startswith("_")}

    @property
    def empty(self) -> bool:
        return not any((self.destination, self.taxonomy, self.origin, self.destination_city, self.must_not_amenities,
                        self.must_not_taxonomies, self.price_min is not None, self.price_max is not None,
                        self.star_min is not None, self.party_total is not None))


@dataclass(frozen=True)
class HypothesisVocab:
    """Từ vựng được phép, dựng từ catalog đang phục vụ (cùng nguồn với gazetteer của query plan)."""
    destinations: Mapping[str, str] = field(default_factory=dict)     # fold → giá trị `destination` của catalog
    flight_cities: Mapping[str, str] = field(default_factory=dict)    # fold → `originCity` / `destinationCity` của tuyến
    iata: Mapping[str, str] = field(default_factory=dict)             # mã sân bay VIẾT HOA → thành phố
    taxonomies: frozenset[str] = frozenset(CONTRACT_TAXONOMIES)
    amenities: frozenset[str] = AMENITY_KEYS

    @classmethod
    def build(cls, destinations: Iterable[str], flight_cities: Iterable[str] = (),
              iata: Mapping[str, str] | None = None) -> "HypothesisVocab":
        return cls(destinations={fold(d): d for d in sorted({str(d) for d in destinations if d})},
                   flight_cities={fold(c): c for c in sorted({str(c) for c in flight_cities if c})},
                   iata=dict(iata or {}))


@dataclass(frozen=True)
class ValidHypothesis:
    """Giá trị đã qua kiểm catalog (chưa so với plan)."""
    taxonomy: str | None = None
    destination: str | None = None
    origin: str | None = None
    destination_city: str | None = None
    must_not_amenities: tuple[str, ...] = ()
    must_not_taxonomies: tuple[str, ...] = ()
    price_min: int | None = None
    price_max: int | None = None
    star_min: float | None = None
    party_total: int | None = None


Rejection = tuple[str, str]   # (trường, lý do)


def _compact(s: str) -> str:
    return fold(s).replace(" ", "")


def _number(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(float(v)) else None
    if isinstance(v, str):
        try:
            x = float(v.strip().replace("_", ""))
        except ValueError:
            return None
        return x if math.isfinite(x) else None
    return None


def _place(value: Any, table: Mapping[str, str], query_compact: str, iata_hits: frozenset[str]) -> tuple[str | None, str | None]:
    """(giá trị catalog, lý do loại). Phải có trong bảng catalog VÀ có mặt trong câu (so trên chuỗi fold bỏ khoảng trắng —
    "nhatrang" vẫn khớp "Nha Trang") hoặc là thành phố của một mã sân bay có trong câu."""
    if not isinstance(value, str) or not value.strip():
        return None, R_INVALID
    canon = table.get(fold(value))
    if canon is None:
        return None, R_NOT_IN_CATALOG
    if _compact(canon) not in query_compact and canon not in iata_hits:
        return None, R_NOT_IN_QUERY
    return canon, None


def validate_hypothesis(hyp: QueryHypothesis, vocab: HypothesisVocab, *, query: str,
                        raw_query: str = "") -> tuple[ValidHypothesis, list[Rejection]]:
    """Kiểm giả thuyết với catalog. `query` = câu đã chuẩn hoá (q'), `raw_query` = câu gốc (mã sân bay, chữ số)."""
    rejected: list[Rejection] = []
    conf = _number(hyp.confidence)
    if conf is not None and conf < MIN_HYPOTHESIS_CONFIDENCE:
        return ValidHypothesis(), [(F_HYPOTHESIS, R_LOW_CONFIDENCE)]
    text = f"{query} {raw_query}".strip()
    toks = set(tokens(text))
    query_compact = _compact(text)
    iata_hits = frozenset(vocab.iata[t] for t in {w.strip(".,;:!?()").upper() for w in raw_query.split()} if t in vocab.iata)
    out: dict[str, Any] = {}

    if hyp.taxonomy is not None:
        t = str(hyp.taxonomy).strip().lower() if isinstance(hyp.taxonomy, str) else None
        if t in vocab.taxonomies:
            out["taxonomy"] = t
        else:
            rejected.append((F_TAXONOMY, R_INVALID))

    for name, fname, table in (("destination", F_DESTINATION, vocab.destinations),
                               ("origin", F_ORIGIN, vocab.flight_cities),
                               ("destination_city", F_DESTINATION_CITY, vocab.flight_cities)):
        v = getattr(hyp, name)
        if v is None:
            continue
        canon, why = _place(v, table, query_compact, iata_hits)
        if canon is None:
            rejected.append((fname, why))
        else:
            out[name] = canon

    negation = bool(toks & _NEGATION_TOKENS)
    for name, fname, allowed in (("must_not_amenities", F_MUST_NOT_AMENITIES, vocab.amenities),
                                 ("must_not_taxonomies", F_MUST_NOT_TAXONOMIES, vocab.taxonomies)):
        values = getattr(hyp, name)
        if not values:
            continue
        good = tuple(dict.fromkeys(v for v in values if isinstance(v, str) and v in allowed))
        if len(good) < len(values):
            rejected.append((fname, R_INVALID))
        if good and not negation:
            rejected.append((fname, R_NO_CUE))
        elif good:
            out[name] = good

    if hyp.price_min is not None or hyp.price_max is not None:
        lo, hi = _number(hyp.price_min), _number(hyp.price_max)
        if (hyp.price_min is not None and lo is None) or (hyp.price_max is not None and hi is None):
            rejected.append((F_PRICE, R_INVALID))
        elif any(x is not None and not 0 <= x <= PRICE_LIMIT for x in (lo, hi)) or (lo is not None and hi is not None and lo > hi):
            rejected.append((F_PRICE, R_OUT_OF_RANGE))
        elif not (any(ch.isdigit() for ch in text) or toks & _MONEY_TOKENS):
            rejected.append((F_PRICE, R_NO_CUE))
        elif lo is not None or hi is not None:
            out["price_min"] = int(lo) if lo is not None else None
            out["price_max"] = int(hi) if hi is not None else None

    if hyp.star_min is not None:
        s = _number(hyp.star_min)
        if s is None:
            rejected.append((F_STAR, R_INVALID))
        elif not 1 <= s <= 5:
            rejected.append((F_STAR, R_OUT_OF_RANGE))
        elif not toks & _STAR_TOKENS:
            rejected.append((F_STAR, R_NO_CUE))
        else:
            out["star_min"] = float(s)

    if hyp.party_total is not None:
        n = _number(hyp.party_total)
        if n is None or n != int(n):
            rejected.append((F_PARTY, R_INVALID))
        elif not 1 <= n <= PARTY_LIMIT:
            rejected.append((F_PARTY, R_OUT_OF_RANGE))
        elif not (any(ch.isdigit() for ch in text) or toks & _NUMBER_WORDS):
            rejected.append((F_PARTY, R_NO_CUE))
        else:
            out["party_total"] = int(n)

    return ValidHypothesis(**out), rejected


def _flight_context(plan: QueryPlan, raw_query: str) -> bool:
    """Như `build_query_plan`: câu vé máy bay khi loại (khai hoặc tham số) là flight, hoặc chưa có loại nào và câu có cụm bay."""
    if plan.taxonomy is not None:
        return plan.taxonomy == TAXONOMY_FLIGHT
    return is_flight_query(raw_query, None)


def merge_hypothesis(plan: QueryPlan, valid: ValidHypothesis, flags: PlanFlags, *,
                     raw_query: str = "") -> tuple[QueryPlan, list[str], list[Rejection]]:
    """Điền giá trị đã kiểm vào ô plan rule để trống → (plan mới, trường đã nhận, trường bị loại kèm lý do).

    Giá trị trùng với rule / tham số thì bỏ qua lặng lẽ (không nhận, không loại). Thứ tự: loại sản phẩm (quyết định câu có là
    vé máy bay) → tuyến bay → điểm đến → phủ định → giá → sao → số khách."""
    accepted: list[str] = []
    rejected: list[Rejection] = []
    applied = list(plan.applied)
    upd: dict[str, Any] = {}

    def owner(source: str | None) -> str:
        return R_PARAM_SET if source == SOURCE_PARAM else R_RULE_SET

    # loại sản phẩm
    t = valid.taxonomy
    if t is not None and t != plan.taxonomy:
        if plan.taxonomy is not None:
            rejected.append((F_TAXONOMY, owner(plan.taxonomy_source)))
        elif plan.taxonomy_skipped == "multi":
            rejected.append((F_TAXONOMY, R_MULTI_VERTICAL))      # câu nêu ≥ 2 loại: không thu hẹp (slice cross_vertical)
        elif t in plan.must_not_taxonomies:
            rejected.append((F_TAXONOMY, R_CONFLICT))
        else:
            upd.update(taxonomy=t, taxonomy_source=SOURCE_QUERY, taxonomy_strength=None)
            accepted.append(F_TAXONOMY)
            if flags.taxonomy and APPLIED_TAXONOMY not in applied:
                applied.append(APPLIED_TAXONOMY)
    merged = replace(plan, **upd) if upd else plan
    flight = _flight_context(merged, raw_query)

    # tuyến bay (chỉ câu vé máy bay; tham số origin của request khoá cả tuyến)
    route_upd: dict[str, Any] = {}
    for value, fname, current, slot in ((valid.origin, F_ORIGIN, merged.route_origin, "route_origin"),
                                        (valid.destination_city, F_DESTINATION_CITY, merged.route_destination,
                                         "route_destination")):
        if value is None or value == current:
            continue
        if not flight or merged.route_skipped == SKIPPED_NOT_FLIGHT:
            rejected.append((fname, R_NOT_FLIGHT))
        elif merged.route_source == SOURCE_PARAM:
            rejected.append((fname, R_PARAM_SET))
        elif current is not None:
            rejected.append((fname, R_RULE_SET))
        else:
            route_upd[slot] = value
            accepted.append(fname)
    if route_upd:
        origin = route_upd.get("route_origin", merged.route_origin)
        dest = route_upd.get("route_destination", merged.route_destination)
        direction = "explicit" if origin and dest else ("destination_only" if dest else "origin_only")
        route_upd.update(route_source=SOURCE_QUERY, route_direction=direction, route_skipped=None)
        if flags.route and APPLIED_ROUTE not in applied:
            applied.append(APPLIED_ROUTE)
        merged = replace(merged, **route_upd)

    # điểm đến (câu thường); câu bay: đích của tuyến đang áp thành điểm đến — như build_query_plan
    decision = merged.destination
    d = valid.destination
    if d is not None and d != decision.value:
        if flight:
            rejected.append((F_DESTINATION, R_NOT_FLIGHT))
        elif decision.source is not None:
            rejected.append((F_DESTINATION, owner(decision.source)))
        elif not flags.destination:
            rejected.append((F_DESTINATION, R_FLAG_OFF))
        else:
            decision = DestinationDecision(d, SOURCE_QUERY, None, decision.candidates)
            accepted.append(F_DESTINATION)
    if (decision.source is None and merged.route_destination and APPLIED_ROUTE in applied
            and "route_destination" in route_upd):
        decision = DestinationDecision(merged.route_destination, SOURCE_QUERY, None, decision.candidates)
    if decision is not merged.destination:
        merged = replace(merged, destination=decision, drop_tokens=frozenset(tokens(decision.value)))

    # phủ định — chỉ thêm khoá mới; không loại chính loại câu đang hỏi
    must_not_upd: dict[str, Any] = {}
    new_amen = tuple(k for k in valid.must_not_amenities if k not in merged.must_not_amenities)
    if new_amen:
        must_not_upd["must_not_amenities"] = merged.must_not_amenities + new_amen
        accepted.append(F_MUST_NOT_AMENITIES)
    asked = {merged.taxonomy, *merged.taxonomy_candidates} - {None}
    new_tax = tuple(t for t in valid.must_not_taxonomies if t not in merged.must_not_taxonomies)
    if any(t in asked for t in new_tax):
        rejected.append((F_MUST_NOT_TAXONOMIES, R_CONFLICT))
        new_tax = tuple(t for t in new_tax if t not in asked)
    if new_tax:
        must_not_upd["must_not_taxonomies"] = merged.must_not_taxonomies + new_tax
        accepted.append(F_MUST_NOT_TAXONOMIES)
    if must_not_upd:
        if flags.negation and APPLIED_MUST_NOT not in applied:
            applied.append(APPLIED_MUST_NOT)
        merged = replace(merged, **must_not_upd)

    # giá / sao (F6)
    if valid.price_min is not None or valid.price_max is not None:
        if (valid.price_min, valid.price_max) != (merged.price_min, merged.price_max):
            if merged.price_source is not None:
                rejected.append((F_PRICE, owner(merged.price_source)))
            else:
                merged = replace(merged, price_min=valid.price_min, price_max=valid.price_max, price_source=SOURCE_QUERY)
                accepted.append(F_PRICE)
                if flags.numeric and APPLIED_PRICE not in applied:
                    applied.append(APPLIED_PRICE)
    if valid.star_min is not None and valid.star_min != merged.star_min:
        if merged.star_source is not None:
            rejected.append((F_STAR, owner(merged.star_source)))
        else:
            merged = replace(merged, star_min=valid.star_min, star_source=SOURCE_QUERY)
            accepted.append(F_STAR)
            if flags.numeric and APPLIED_STAR not in applied:
                applied.append(APPLIED_STAR)

    # số khách
    if valid.party_total is not None and valid.party_total != merged.party_total:
        if merged.party_source is not None:
            rejected.append((F_PARTY, owner(merged.party_source)))
        else:
            merged = replace(merged, party_total=valid.party_total, party_adults=None, party_children=None,
                             party_source=SOURCE_QUERY)
            accepted.append(F_PARTY)
            if flags.party and APPLIED_PARTY not in applied:
                applied.append(APPLIED_PARTY)

    if tuple(applied) != merged.applied:
        merged = replace(merged, applied=tuple(applied))
    return merged, accepted, rejected
