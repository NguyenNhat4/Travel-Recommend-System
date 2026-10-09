"""LLM fallback có kiểm soát cho query plan của /search (đề xuất đã chốt `docs/prd/update/2026-10-06-search-llm-fallback-query-plan.md`;
kiến trúc search §5; contract 1.17.0 `diagnostics.queryPlan.llm` + `stageMs.llm`).

Ba chế độ (`SEARCH_LLM_FALLBACK`): `off` (mặc định — không dựng gì, response như 1.16.0), `shadow` (giả thuyết chạy nền, chỉ ghi
so sánh rule ↔ LLM, KHÔNG đổi kết quả), `on` (điền ô plan rule để trống, trong hạn `timeout_ms`; quá hạn / lỗi → plan rule).
Chỉ kích hoạt khi `plan.confidence < min_confidence` và câu không rỗng; tham số request luôn thắng (`domain/search/hypothesis`).

Cache theo câu đã chuẩn hoá (`cache_key` của q'), kèm khoá phụ là câu gốc đã gộp khoảng trắng — để bench / job prewarm phát lại
được kể cả khi bước chuẩn hoá (dựng từ catalog) cho q' hơi khác. LRU trong tiến trình + file JSONL tuỳ chọn (`path`) để bench
phát lại tất định không gọi API (`cache_only`). Gọi model trên thread pool có trần (`max_pending` lượt đang bay; single-flight theo
khoá); lượt quá hạn vẫn chạy tiếp và ghi cache khi xong, nên câu đó lần sau là hit. Log ứng dụng chỉ ghi tên trường / lý do /
thời gian, không ghi câu truy vấn (hop-dong-tich-hop-backend.md §8.6).
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import unicodedata
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

from src.backend.app.application.ports.query_hypothesis import QueryHypothesisPort
from src.backend.app.domain.search import (
    AMENITIES,
    NormalizedQuery,
    PlanFlags,
    PlanGazetteers,
    PlanParams,
    QueryPlan,
    build_query_plan,
)
from src.backend.app.domain.search.hypothesis import (
    CONTRACT_TAXONOMIES,
    HypothesisVocab,
    QueryHypothesis,
    merge_hypothesis,
    validate_hypothesis,
)

logger = logging.getLogger("uvicorn.error")

MODE_OFF, MODE_SHADOW, MODE_ON = "off", "shadow", "on"
MODES = (MODE_OFF, MODE_SHADOW, MODE_ON)
#: `queryPlan.llm.status`
STATUS_OK = "ok"                    # có giả thuyết (từ cache hoặc vừa gọi)
STATUS_EMPTY = "empty"              # model không cho giả thuyết (adapter trả None) — cũng được cache
STATUS_PENDING = "pending"          # shadow: đang chạy nền, so sánh chỉ ghi log
STATUS_TIMEOUT = "timeout"
STATUS_FAILED = "failed"            # model / mạng lỗi — `error` = tên lớp lỗi
STATUS_UNAVAILABLE = "unavailable"  # chế độ bật nhưng không có adapter (thiếu API key / SDK)
STATUS_CACHE_MISS = "cache_miss"    # cache_only và câu chưa có trong cache
STATUS_BUSY = "busy"                # đã đủ `max_pending` lượt đang bay
STATUSES = (STATUS_OK, STATUS_EMPTY, STATUS_PENDING, STATUS_TIMEOUT, STATUS_FAILED, STATUS_UNAVAILABLE, STATUS_CACHE_MISS,
            STATUS_BUSY)

_WS = re.compile(r"\s+")


def cache_key(text: str) -> str:
    """NFC, chữ thường, gộp khoảng trắng. Khoá chính dùng câu SAU chuẩn hoá (q': "KS ở NT" và "khách sạn ở Nha Trang" chung
    khoá); khoá phụ dùng câu gốc."""
    return _WS.sub(" ", unicodedata.normalize("NFC", text)).strip().lower()


def cache_keys(normalized_text: str, raw_query: str) -> tuple[str, ...]:
    """(khoá chính theo q', khoá phụ theo câu gốc nếu khác)."""
    main, raw = cache_key(normalized_text), cache_key(raw_query)
    return (main,) if raw == main or not raw else (main, raw)


# ------------------------------------------------------------------ cache
class HypothesisCache:
    """LRU `max_size` khoá → giả thuyết (None = model không cho giả thuyết; cũng được cache). `path`: file JSONL, nạp lúc
    dựng và ghi nối mỗi lượt mới — dòng `{"key", "aliases", "tag", "hypothesis"}`. `tag` (model + phiên bản prompt): khi đặt,
    chỉ nạp dòng cùng tag; None → nạp mọi dòng (dòng sau thắng dòng trước)."""

    def __init__(self, max_size: int = 10_000, path: str | Path | None = None, tag: str | None = None):
        self.max_size = max(1, int(max_size))
        self.path = Path(path) if path else None
        self.tag = tag
        self._data: OrderedDict[str, QueryHypothesis | None] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = self.misses = self.loaded = 0
        if self.path is not None and self.path.exists():
            self._load()

    def _load(self) -> None:
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict) or not isinstance(row.get("key"), str):
                    continue
                if self.tag is not None and row.get("tag") != self.tag:
                    continue
                h = row.get("hypothesis")
                hyp = QueryHypothesis.from_mapping(h) if isinstance(h, dict) else None
                for k in (row["key"], *(a for a in row.get("aliases") or () if isinstance(a, str))):
                    self._set(k, hyp)
                self.loaded += 1

    def _set(self, key: str, hyp: QueryHypothesis | None) -> None:
        self._data[key] = hyp
        self._data.move_to_end(key)
        while len(self._data) > self.max_size:
            self._data.popitem(last=False)

    def get(self, *keys: str) -> tuple[bool, QueryHypothesis | None]:
        """Khoá đầu tiên có mặt thắng."""
        with self._lock:
            for key in keys:
                if key in self._data:
                    self._data.move_to_end(key)
                    self.hits += 1
                    return True, self._data[key]
            self.misses += 1
            return False, None

    def has(self, *keys: str) -> bool:
        with self._lock:
            return any(k in self._data for k in keys)

    def __contains__(self, key: str) -> bool:
        return self.has(key)

    def put(self, keys: str | Iterable[str], hyp: QueryHypothesis | None, *, persist: bool = True) -> None:
        keys = (keys,) if isinstance(keys, str) else tuple(dict.fromkeys(keys))
        if not keys:
            return
        with self._lock:
            for k in keys:
                self._set(k, hyp)
            if persist and self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                row = {"key": keys[0], "aliases": list(keys[1:]), "tag": self.tag,
                       "hypothesis": hyp.as_dict() if hyp is not None else None}
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def __len__(self) -> int:
        return len(self._data)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"size": len(self._data), "hits": self.hits, "misses": self.misses, "loaded": self.loaded}


@dataclass(frozen=True)
class HypothesisOutcome:
    status: str
    hypothesis: QueryHypothesis | None = None
    cached: bool = False
    error: str | None = None


def _coerce(hyp: Any) -> QueryHypothesis | None:
    if hyp is None or isinstance(hyp, QueryHypothesis):
        return hyp
    return QueryHypothesis.from_mapping(hyp if isinstance(hyp, Mapping) else None)


def _hit_outcome(hyp: QueryHypothesis | None) -> HypothesisOutcome:
    return HypothesisOutcome(STATUS_OK if hyp is not None else STATUS_EMPTY, hyp, cached=True)


class CachedQueryHypothesizer:
    """Bọc một `QueryHypothesisPort` bằng cache + thread pool có trần. Dựng MỘT lần ở composition root và dùng lại qua các lần
    nạp catalog (cache và thread sống cùng nó). `inner = None` → chỉ đọc cache (`cache_only`, bench) hoặc `unavailable`."""

    def __init__(self, inner: QueryHypothesisPort | None, *, cache: HypothesisCache | None = None,
                 cache_only: bool = False, max_workers: int = 2, max_pending: int = 8):
        self.inner = inner
        self.version: str | None = getattr(inner, "version", None)
        self.cache = cache if cache is not None else HypothesisCache(tag=self.version)
        self.cache_only = cache_only
        self.max_pending = max(1, int(max_pending))
        self._pool = ThreadPoolExecutor(max_workers=max(1, int(max_workers)), thread_name_prefix="search-llm")
        self._inflight: dict[str, Future] = {}
        self._lock = threading.Lock()

    @property
    def can_call(self) -> bool:
        return self.inner is not None and not self.cache_only

    def miss_status(self) -> str:
        return STATUS_CACHE_MISS if self.cache_only or self.inner is not None else STATUS_UNAVAILABLE

    def peek(self, keys: tuple[str, ...]) -> tuple[bool, QueryHypothesis | None]:
        return self.cache.get(*keys)

    def _work(self, keys: tuple[str, ...], query: str, context_fn: Callable[[], Mapping[str, Any]]) -> QueryHypothesis | None:
        hyp = _coerce(self.inner.hypothesize(query, context_fn()))
        self.cache.put(keys, hyp)
        return hyp

    def submit(self, keys: tuple[str, ...], query: str, context_fn: Callable[[], Mapping[str, Any]]) -> Future | None:
        """Future của lượt gọi cho khoá chính (single-flight); None khi đã đủ `max_pending` lượt đang bay / pool đã đóng."""
        key = keys[0]
        with self._lock:
            fut = self._inflight.get(key)
            if fut is not None:
                return fut
            if len(self._inflight) >= self.max_pending:
                return None
            try:
                fut = self._pool.submit(self._work, keys, query, context_fn)
            except RuntimeError:   # pool đã đóng (shutdown)
                return None
            self._inflight[key] = fut
        fut.add_done_callback(lambda _f, k=key: self._done(k))
        return fut

    def _done(self, key: str) -> None:
        with self._lock:
            self._inflight.pop(key, None)

    def start(self, keys: tuple[str, ...], query: str,
              context_fn: Callable[[], Mapping[str, Any]]) -> HypothesisOutcome | Future:
        """Cache hit → `HypothesisOutcome` ngay; không gọi được → outcome lỗi; còn lại → Future đang chạy."""
        hit, hyp = self.cache.get(*keys)
        if hit:
            return _hit_outcome(hyp)
        if not self.can_call:
            return HypothesisOutcome(self.miss_status())
        fut = self.submit(keys, query, context_fn)
        return HypothesisOutcome(STATUS_BUSY) if fut is None else fut

    @staticmethod
    def wait(fut: Future, timeout_s: float) -> HypothesisOutcome:
        try:
            hyp = fut.result(timeout=max(0.0, timeout_s))
        except FutureTimeout:
            return HypothesisOutcome(STATUS_TIMEOUT)
        except Exception as exc:  # noqa: BLE001 — lỗi provider / mạng: giữ plan rule
            return HypothesisOutcome(STATUS_FAILED, error=type(exc).__name__)
        return HypothesisOutcome(STATUS_OK if hyp is not None else STATUS_EMPTY, hyp)

    def resolve(self, keys: tuple[str, ...], query: str, context_fn: Callable[[], Mapping[str, Any]],
                timeout_s: float) -> HypothesisOutcome:
        got = self.start(keys, query, context_fn)
        return got if isinstance(got, HypothesisOutcome) else self.wait(got, timeout_s)

    def hypothesize(self, query: str, context: Mapping[str, Any]) -> QueryHypothesis | None:
        """Hợp `QueryHypothesisPort`: cache theo `cache_key(query)` rồi gọi đồng bộ."""
        keys = (cache_key(query),)
        hit, hyp = self.cache.get(*keys)
        if hit:
            return hyp
        if not self.can_call:
            return None
        return self._work(keys, query, lambda: context)

    def close(self, *, wait: bool = False) -> None:
        self._pool.shutdown(wait=wait, cancel_futures=not wait)


# ------------------------------------------------------------------ context gửi model
def build_vocab(destinations: Iterable[str], gaz: PlanGazetteers) -> HypothesisVocab:
    return HypothesisVocab.build(destinations, gaz.flight_cities, gaz.iata)


def _amenity_hints() -> dict[str, str]:
    """khoá tiện ích → cụm ví dụ (đã fold) khách hay gõ — để model chọn đúng khoá."""
    return {a.key: ", ".join(a.query[:3]) for a in AMENITIES}


def hypothesis_context(nq: NormalizedQuery, raw_query: str, gaz: PlanGazetteers, vocab: HypothesisVocab) -> dict[str, Any]:
    """Tóm tắt plan rule (dựng KHÔNG tham số request, mọi cờ tắt — chỉ phụ thuộc câu + catalog, nên cùng khoá cache luôn cùng
    prompt) + từ vựng được phép."""
    base = build_query_plan(nq, raw_query, PlanParams(), PlanFlags(), gaz)
    rule: dict[str, Any] = {
        "taxonomy": base.taxonomy, "taxonomyCandidates": list(base.taxonomy_candidates),
        "taxonomySkipped": base.taxonomy_skipped, "destinations": list(nq.destinations),
        "routeOrigin": base.route_origin, "routeDestinationCity": base.route_destination,
        "routeSkipped": base.route_skipped, "mustNotAmenities": list(base.must_not_amenities),
        "mustNotTaxonomies": list(base.must_not_taxonomies), "unresolved": list(base.unresolved),
        "priceMin": base.price_min, "priceMax": base.price_max, "starMin": base.star_min,
        "partyTotal": base.party_total, "confidence": base.confidence,
        "fallbackReasons": list(base.fallback_reasons),
    }
    ctx: dict[str, Any] = {
        "rule": rule,
        "vocab": {"taxonomies": list(CONTRACT_TAXONOMIES), "destinations": sorted(vocab.destinations.values()),
                  "flightCities": sorted(vocab.flight_cities.values()), "amenities": _amenity_hints()},
    }
    if raw_query.strip() != nq.text.strip():
        ctx["rawQuery"] = raw_query
    return ctx


@dataclass(frozen=True)
class HypothesisRequest:
    """Một lượt hỏi model cho câu: khoá cache, câu gửi đi (q'), context, confidence của plan rule không tham số."""
    keys: tuple[str, ...]
    query: str
    context: dict[str, Any]
    confidence: float


# ------------------------------------------------------------------ fallback trong use case
@dataclass
class PendingFallback:
    plan: QueryPlan
    nq: NormalizedQuery
    raw_query: str
    flags: PlanFlags
    started: float
    got: Any = None            # HypothesisOutcome | Future | None


@dataclass
class LlmPlanFallback:
    """Hai pha để lượt gọi model chạy SONG SONG với embed: `begin` (sau khi dựng plan, trước embed) → `finish` (sau embed)."""
    mode: str
    min_confidence: float
    timeout_ms: int
    hypothesizer: CachedQueryHypothesizer | None
    vocab: HypothesisVocab
    gaz: PlanGazetteers
    stats: dict[str, int] = field(default_factory=dict)

    def triggered(self, plan: QueryPlan, nq: NormalizedQuery | None, raw_query: str) -> bool:
        return (self.mode != MODE_OFF and nq is not None and bool(raw_query.strip())
                and plan.confidence < self.min_confidence)

    def begin(self, plan: QueryPlan, nq: NormalizedQuery | None, raw_query: str, flags: PlanFlags) -> PendingFallback | None:
        if not self.triggered(plan, nq, raw_query):
            return None
        pending = PendingFallback(plan, nq, raw_query, flags, perf_counter())
        hyp = self.hypothesizer
        if hyp is None:
            return pending
        keys = cache_keys(nq.text, raw_query)
        ctx = lambda: hypothesis_context(nq, raw_query, self.gaz, self.vocab)  # noqa: E731 — tính trong thread gọi model
        if self.mode == MODE_ON:
            pending.got = hyp.start(keys, nq.text, ctx)
            return pending
        # shadow: chỉ đọc cache; miss → chạy nền, KHÔNG bao giờ chờ
        hit, cached = hyp.peek(keys)
        if hit:
            pending.got = _hit_outcome(cached)
        elif not hyp.can_call:
            pending.got = HypothesisOutcome(hyp.miss_status())
        else:
            fut = hyp.submit(keys, nq.text, ctx)
            if fut is None:
                pending.got = HypothesisOutcome(STATUS_BUSY)
            else:
                fut.add_done_callback(lambda f, p=pending: self._shadow_done(p, f))
                pending.got = HypothesisOutcome(STATUS_PENDING)
        return pending

    def compare(self, pending: PendingFallback, hyp: QueryHypothesis | None):
        """(plan đã trộn, accepted, rejected) — thuần, dùng cho cả `on` lẫn so sánh `shadow`."""
        if hyp is None:
            return pending.plan, [], []
        valid, rejected = validate_hypothesis(hyp, self.vocab, query=pending.nq.text, raw_query=pending.raw_query)
        merged, accepted, rejected_merge = merge_hypothesis(pending.plan, valid, pending.flags, raw_query=pending.raw_query)
        return merged, accepted, rejected + rejected_merge

    def finish(self, pending: PendingFallback) -> tuple[QueryPlan, dict]:
        got = pending.got
        if got is None:
            outcome = HypothesisOutcome(STATUS_UNAVAILABLE)
        elif isinstance(got, HypothesisOutcome):
            outcome = got
        else:   # Future của chế độ on: chờ phần hạn còn lại (lượt gọi đã chạy song song với embed)
            left = self.timeout_ms / 1000.0 - (perf_counter() - pending.started)
            outcome = CachedQueryHypothesizer.wait(got, left)
        plan = pending.plan
        accepted: list[str] = []
        rejected: list[tuple[str, str]] = []
        if outcome.status == STATUS_OK:
            merged, accepted, rejected = self.compare(pending, outcome.hypothesis)
            if self.mode == MODE_ON and accepted:
                plan = merged
        used = self.mode == MODE_ON and bool(accepted)
        block: dict[str, Any] = {"mode": self.mode, "used": used, "cached": outcome.cached, "status": outcome.status,
                                 "latencyMs": max(0, int((perf_counter() - pending.started) * 1000)),
                                 "accepted": accepted, "rejected": [{"field": f, "reason": r} for f, r in rejected]}
        if outcome.error:
            block["error"] = outcome.error
        self._count(outcome.status, used)
        logger.info("search.llm.%s status=%s cached=%s used=%s accepted=%s rejected=%s latency_ms=%d", self.mode,
                    outcome.status, outcome.cached, used, ",".join(accepted) or "-",
                    ",".join(f"{f}:{r}" for f, r in rejected) or "-", block["latencyMs"])
        return plan, block

    def _shadow_done(self, pending: PendingFallback, fut: Future) -> None:
        """Shadow, cache miss: so sánh khi lượt chạy nền xong — chỉ ghi log (tên trường / lý do, không ghi câu)."""
        outcome = CachedQueryHypothesizer.wait(fut, 0)
        accepted: list[str] = []
        rejected: list[tuple[str, str]] = []
        if outcome.status == STATUS_OK:
            try:
                _, accepted, rejected = self.compare(pending, outcome.hypothesis)
            except Exception as exc:  # noqa: BLE001 — log so sánh hỏng không được làm sập thread pool
                outcome = HypothesisOutcome(STATUS_FAILED, error=type(exc).__name__)
        logger.info("search.llm.shadow.done status=%s accepted=%s rejected=%s latency_ms=%d", outcome.status,
                    ",".join(accepted) or "-", ",".join(f"{f}:{r}" for f, r in rejected) or "-",
                    int((perf_counter() - pending.started) * 1000))

    def _count(self, status: str, used: bool) -> None:
        self.stats[status] = self.stats.get(status, 0) + 1
        if used:
            self.stats["used"] = self.stats.get("used", 0) + 1


def llm_log_fields(response: Mapping[str, Any]) -> dict[str, Any] | None:
    """Tóm tắt `queryPlan.llm` của một response để route gắn vào `filters` của `app.search_logs` (SEARCH_LOG_QUERIES):
    `{"llm": {mode, used, status, accepted, rejected}}`; None khi khối vắng."""
    block = ((response.get("diagnostics") or {}).get("queryPlan") or {}).get("llm")
    if not block:
        return None
    return {"llm": {k: block[k] for k in ("mode", "used", "status", "accepted", "rejected") if k in block}}


# ------------------------------------------------------------------ prewarm (job / bench)
@dataclass
class HypothesisPrewarmReport:
    queries: int = 0          # câu đầu vào (kể cả trùng)
    eligible: int = 0         # khoá khác nhau có confidence < ngưỡng (hoặc mọi câu khi include_all)
    called: int = 0           # vừa gọi model
    skipped: int = 0          # đã có trong cache
    empty: int = 0            # model không cho giả thuyết (vẫn cache)
    failed: int = 0
    seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {k: (v[:5] if k == "errors" else v) for k, v in self.__dict__.items()}


def prewarm_hypotheses(engine: Any, hypothesizer: CachedQueryHypothesizer, queries: Iterable[str], *,
                       min_confidence: float = 1.0, include_all: bool = False, force: bool = False,
                       per_minute: float = 0.0, stop: threading.Event | None = None,
                       progress: Callable[[str, str], None] | None = None) -> HypothesisPrewarmReport:
    """Gọi model ĐỒNG BỘ cho từng câu có plan rule `confidence < min_confidence` (mặc định 1.0 = mọi câu có ≥ 1 lý do; ngưỡng
    của request ≤ 1.0 nên cache phủ mọi cấu hình) rồi ghi cache (+ JSONL nếu cache có `path`). `engine` = `SearchProducts`
    (cần `llm_hypothesis_request`). `per_minute` > 0 → giãn nhịp gọi. `progress(key, status)` cho log của job."""
    report = HypothesisPrewarmReport()
    started = time.monotonic()
    seen: set[str] = set()
    gap = 60.0 / per_minute if per_minute and per_minute > 0 else 0.0
    last = 0.0
    for q in queries:
        report.queries += 1
        if stop is not None and stop.is_set():
            break
        req: HypothesisRequest | None = engine.llm_hypothesis_request(q)
        if req is None or req.keys[0] in seen or not (include_all or req.confidence < min_confidence):
            continue
        seen.add(req.keys[0])
        report.eligible += 1
        if not force and hypothesizer.cache.has(*req.keys):
            report.skipped += 1
            if progress:
                progress(req.keys[0], "cached")
            continue
        if hypothesizer.inner is None:
            report.failed += 1
            report.errors.append(f"{req.keys[0]}: no adapter")
            continue
        if gap:
            wait = last + gap - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            last = time.monotonic()
        try:
            hyp = _coerce(hypothesizer.inner.hypothesize(req.query, req.context))
        except Exception as exc:  # noqa: BLE001 — ghi lỗi, đi tiếp câu sau
            report.failed += 1
            report.errors.append(f"{req.keys[0]}: {type(exc).__name__}: {exc}"[:300])
            if progress:
                progress(req.keys[0], "failed")
            continue
        hypothesizer.cache.put(req.keys, hyp)
        report.called += 1
        report.empty += hyp is None
        if progress:
            progress(req.keys[0], "empty" if hyp is None else "ok")
    report.seconds = round(time.monotonic() - started, 1)
    return report
