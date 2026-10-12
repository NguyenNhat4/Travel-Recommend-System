from __future__ import annotations

import contextvars
import functools
import logging
from collections import Counter
from concurrent.futures import Executor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from src.backend.app.application.ports import CdpHistoryReader, UnitIndex, VectorSearchPort
from src.backend.app.application.ports.cdp_client import HISTORY_MAX_EVENTS, CdpUnavailableError
from src.backend.app.application.recommendation.cache import RecommendationCache, engine_version
from src.backend.app.application.search import hit
from src.backend.app.application.search.use_cases import StageTimer
from src.backend.app.core.logging_config import log_event
from src.backend.app.domain.recommendation import (Popularity, Purchase, ResolvedEvent, ScoreContext, build_profile, explain,
                                                   infer_origin, mmr_select, score_candidates)
from src.backend.app.domain.recommendation.profile import MAX_PER_DESTINATION, calibration_applies
from src.backend.app.domain.recommendation.profile import (
    EXPLORE_MAX_PER_DESTINATION, EXPLORE_TAXONOMIES, MAX_PER_VERTICAL, local_today, parse_using_date,
)

logger = logging.getLogger("uvicorn.error")


def _using_date(value):
    """`usingDate` của event CDP → `date` (một parser chung với harness bench: `profile.parse_using_date`)."""
    return parse_using_date(value)


_CALIBRATION_WARNED: set[str] = set()


def _warn_calibration_mismatch(model_version: str | None) -> None:
    """Ngưỡng F14c gắn với model + text builder đã calibrate; lệch thì dùng công thức cũ và cảnh báo một lần mỗi model."""
    key = str(model_version)
    if key not in _CALIBRATION_WARNED:
        _CALIBRATION_WARNED.add(key)
        log_event(logger, "recsys.next_trip_scoring.model_mismatch", "WARNING",
                  message=f"recommend.next_trip_scoring model={key} khác tag calibrate; dùng công thức 0,7/0,15/0,15")


def _cap_per_taxonomy(order: Iterable[int], taxonomy: Sequence, k: int, cap: int | None) -> list[int]:
    """Giữ thứ tự, tối đa `cap` món mỗi taxonomy, dừng khi đủ `k` món; `cap=None` là không giới hạn (harness eval).

    Cold-start "tối đa 2 mỗi taxonomy" (search-recommendation §4.8, chốt 2026-10-12): lượt mua chuyến bay dồn về tuyến
    nên không có trần thì 2 món đầu ở các điểm đến lớn đều là tuyến bay."""
    out: list[int] = []
    seen: Counter = Counter()
    for i in order:
        if len(out) >= k:
            break
        t = str(taxonomy[i])
        if cap is not None and seen[t] >= cap:
            continue
        seen[t] += 1
        out.append(i)
    return out


def _timed(fn: Callable[..., Any], *args, **kwargs) -> tuple[Any, float]:
    started = perf_counter()
    value = fn(*args, **kwargs)
    return value, perf_counter() - started


class _Pending:
    """Một lời gọi kho vector: có `executor` thì chạy ngay trên pool, không thì hoãn tới `result()` (tuần tự đúng thứ tự cũ).

    Mỗi lời gọi chạy trong bản sao context của request (`copy_context().run`), để log trong adapter vẫn mang request ID.
    `seconds` là thời gian của chính lời gọi, ghi vào `stageMs` sau khi có kết quả."""

    def __init__(self, name: str, executor: Executor | None, fn: Callable[..., Any], *args, **kwargs):
        self.name, self.seconds = name, 0.0
        self._call = functools.partial(_timed, fn, *args, **kwargs)
        self._future = executor.submit(contextvars.copy_context().run, self._call) if executor is not None else None

    def result(self) -> Any:
        value, self.seconds = self._future.result() if self._future is not None else self._call()
        return value


def _with_stages(result: dict, stages: StageTimer, events_read: int | None = None) -> dict:
    """Gắn thời gian từng bước (ms nguyên) và số event đã đọc vào `diagnostics` để đo trên log.

    Hai khoá này chỉ dành cho engine: `responses.recommendation_response` bỏ chúng khỏi payload (không đổi contract) và
    ghi vào log `recsys.recommend`."""
    diagnostics = result.setdefault("diagnostics", {})
    diagnostics["stageMs"] = stages.ms
    if events_read is not None:
        diagnostics["eventsRead"] = events_read
    return result


def _ts(x) -> float:
    if isinstance(x, datetime):
        return x.timestamp()
    return datetime.fromisoformat(str(x).replace("Z", "+00:00")).timestamp()


def bought_units(index: UnitIndex, events: list[dict]) -> set[int]:
    """Unit coi là đã mua từ event CDP thô (FR-REC-02, chốt 09/10/2026): mọi purchase trong lịch sử, theo search unit
    (phòng → khách sạn, chuyến → tuyến), kể cả sản phẩm chưa có vector; rồi đóng một bậc qua combo ↔ thành phần
    (`UnitIndex.purchase_closure`). Harness bench (`recsys_bench/models/funnel.py`, `ceiling.py`) gọi cùng hàm này."""
    units = {index.resolve(str(e.get("productId") or "")) for e in events if e.get("eventName") == "purchase"}
    units.discard(None)
    return index.purchase_closure(units)


def explore_fill(index: UnitIndex, vectors: VectorSearchPort, u_long: np.ndarray, dest: str | None, bought: set[int],
                 taken: set[int], n: int, candidate_k: int = 50) -> list[tuple[int, np.ndarray]]:
    """Ô khám phá (FR-REC-02, chốt 09/10/2026): `n` món ở điểm đến khác `dest` cho các ô trống — recommendable, taxonomy ∈
    EXPLORE_TAXONOMIES, chưa mua (`bought` đã gồm closure combo), chưa có trong `taken` (chỉ số toàn cục), xếp theo
    cos(u_long, v) bằng một lượt `near_vector(u_long)` (chi phí của luật, đo ở latency SAU), tối đa EXPLORE_MAX_PER_DESTINATION
    món mỗi điểm đến. Trả [(chỉ số toàn cục, vector)] theo thứ tự chọn. Harness bench (`recsys_bench/models/funnel.py`) gọi
    đúng hàm này để arm content tái tạo list engine."""
    if n <= 0:
        return []
    m = index.mask(only_recommendable=True) & np.isin(index.taxonomy, list(EXPLORE_TAXONOMIES))
    if dest:
        m &= index.destination != dest
    m[sorted(bought)] = False
    if not m.any():
        return []
    out: list[tuple[int, np.ndarray]] = []
    chosen: set[int] = set()
    per_dest: dict[str, int] = {}
    for h in vectors.near_vector(u_long, index.allowed_ids(m), candidate_k, with_vectors=True):
        g = index.idx.get(h.product_id)
        if g is None or h.vector is None or not m[g] or g in taken or g in chosen:
            continue
        d = str(index.destination[g])
        if per_dest.get(d, 0) >= EXPLORE_MAX_PER_DESTINATION:
            continue
        per_dest[d] = per_dest.get(d, 0) + 1
        chosen.add(g)
        out.append((g, h.vector))
        if len(out) >= n:
            break
    return out


@dataclass
class BuildPopularity:
    """Job: từ CDP purchase events → Popularity. Chạy nightly (hoặc mỗi request khi mock nhỏ)."""
    index: UnitIndex
    cdp: CdpHistoryReader

    def __call__(self, now: datetime | None = None) -> Popularity:
        purchases = []
        for e in self.cdp.purchase_events():
            i = self.index.resolve(e["productId"])
            if i is None:
                continue
            purchases.append(Purchase(unit=i, destination=str(self.index.destination[i]), booked_at=_ts(e["timestamp"]),
                                      using_at=_ts(e["usingDate"]) if e.get("usingDate") else None))
        return Popularity(purchases, set(map(str, self.index.destination)), now=now)


class _LocalSpace:
    """Ma trận vector nhỏ chỉ gồm các unit request này cần (event + ứng viên top-K), đánh số lại 0..m-1.

    Hàm domain (`build_profile`, `score_candidates`, `mmr_select`, `explain`) nhận `E` tra theo số unit;
    đưa chúng không gian cục bộ này thay cho toàn bộ catalog, nên công thức giữ nguyên.
    """

    def __init__(self, index: UnitIndex, dimension: int):
        self.index, self.dimension = index, dimension
        self.glob: list[int] = []
        self.local: dict[int, int] = {}
        self.rows: list[np.ndarray] = []

    def add(self, unit: int, vector: np.ndarray) -> int:
        if unit not in self.local:
            self.local[unit] = len(self.glob)
            self.glob.append(unit)
            self.rows.append(np.asarray(vector, dtype=np.float32))
        return self.local[unit]

    @property
    def E(self) -> np.ndarray:
        return np.vstack(self.rows) if self.rows else np.zeros((0, self.dimension), dtype=np.float32)

    @property
    def taxonomy(self) -> np.ndarray:
        return self.index.taxonomy[self.glob] if self.glob else np.array([], dtype=str)

    @property
    def destination(self) -> np.ndarray:
        return self.index.destination[self.glob] if self.glob else np.array([], dtype=str)

    @property
    def origin_city(self) -> np.ndarray:
        """Điểm xuất phát của route bay ("" với unit khác) — FR-REC-04, chốt 09/10."""
        return self.index.attrs.origin_city[self.glob] if self.glob else np.array([], dtype=object)


@dataclass
class RecommendForUser:
    index: UnitIndex
    vectors: VectorSearchPort
    cdp: CdpHistoryReader
    popularity: Popularity | None = None
    candidate_k: int = 200
    popular_k: int = 50   # ứng viên thêm theo popularity: W_POP đủ lớn để món phổ biến xa profile vẫn lọt top
    # Giới hạn món mỗi taxonomy sau MMR (spec §4.7, production = MAX_PER_VERTICAL). `None` chỉ dành cho harness đánh giá
    # offline (`src/evaluation/recsys_bench`, mode eval: k = 20 cần đủ 20 món); main.py không đổi giá trị này.
    max_per_vertical: int | None = MAX_PER_VERTICAL
    # Ô khám phá khi có chuyến mở (FR-REC-02, 09/10): ô còn trống sau món tại X được lấp bằng món ở điểm đến khác theo u_long.
    # Tắt bằng RECOMMEND_EXPLORE_FILL=false (Settings) khi cần rollback không redeploy; tắt = list y hệt trước PR-A.
    explore_fill: bool = True
    explore_candidate_k: int = 50   # top-K near_vector(u_long) cho ô khám phá; 1 món / điểm đến nên 50 là dư
    # Không có chuyến mở (FR-REC-04 / FR-REC-02, 09/10): công thức F14c khi `index.model_version` khớp tag calibrate, ngược lại
    # công thức cũ + WARNING; tối đa `max_per_destination` món / điểm đến (None = tắt; không áp khi request khoá `destination`).
    next_trip_scoring: bool = True
    max_per_destination: int | None = MAX_PER_DESTINATION
    # Pool cho các lượt kho vector độc lập (ANN ngắn hạn, ANN dài hạn, vector của món phổ biến) chạy song song; kết quả
    # ghép đúng thứ tự cũ nên output y hệt. None = tuần tự (harness bench, test, `RECOMMEND_IO_WORKERS=0`).
    executor: Executor | None = None
    # Cache kết quả trên kho dùng chung (Redis, PRD architecture §4, chốt 2026-10-12). Chỉ bật khi có cả cache lẫn phiên bản
    # catalog (`WeaviateVectorStore.version`); None = tính mỗi request như trước (harness bench, test, URL Redis trống).
    cache: RecommendationCache | None = None
    catalog_version: str | None = None
    _engine_version: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.cache is not None and self.catalog_version:
            self._engine_version = engine_version(self)   # một lần mỗi lần nạp lại (engine dựng mới mỗi 900 s)

    @property
    def cache_enabled(self) -> bool:
        return self.cache is not None and self._engine_version is not None

    def __call__(self, cdp_user_id: str | None, k: int = 5, now: datetime | None = None,
                 events: list[dict] | None = None, destination: str | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        stages = StageTimer()
        base = {"generatedAt": now.isoformat(), "modelVersion": self.index.model_version}
        try:
            # Đường đọc CDP tối đa 500 event (cdp §6); cắt cả ở đây cho adapter sau này (HttpCdpClient). Đường `events=`
            # (harness bench) giữ nguyên để baseline không đổi.
            raw = events if events is not None else (
                self.cdp.events_for_user(cdp_user_id)[:HISTORY_MAX_EVENTS] if cdp_user_id else [])
        except CdpUnavailableError as exc:
            # CDP sập/timeout vẫn trả 200 popular; chỉ lỗi CDP mới log WARNING, không log cdp_user_id
            # (hop-dong-tich-hop-cdp.md §6, §8).
            log_event(logger, "recsys.fallback", "WARNING", reason="cdp_unavailable",
                      message=f"recommend.cdp_unavailable reason={type(exc.__cause__ or exc).__name__}; fallback popular")
            stages.lap("cdp")
            result = {**base, **self._cold_start(k, now, destination)}
            stages.lap("coldStart")
            return _with_stages(result, stages)
        stages.lap("cdp")
        if not (self.cache_enabled and cdp_user_id and events is None):   # khách vãng lai và đường `events=` không cache
            return _with_stages(self._rank(raw, k, now, destination, base, stages), stages, events_read=len(raw))
        # Khoá có dấu vân tay của chính lịch sử vừa đọc: event mới cho khoá mới, không bao giờ trả kết quả của lịch sử cũ.
        # Frontend huỷ request thì thread này vẫn tính xong và ghi cache, để lần "Thử lại" trúng.
        key = self.cache.key(engine_version=self._engine_version, cdp_user_id=cdp_user_id, k=k, destination=destination,
                             today=local_today(now), events=raw)

        def compute() -> dict:
            stages.lap("cache")
            return self._rank(raw, k, now, destination, base, stages)

        result, outcome = self.cache.get_or_compute(key, compute)
        stages.lap("cache")
        diagnostics = result.setdefault("diagnostics", {})
        diagnostics["userVectorCacheHit"] = outcome in ("hit", "wait_hit")
        diagnostics["cacheOutcome"] = outcome
        return _with_stages(result, stages, events_read=len(raw))

    def _rank(self, raw: list[dict], k: int, now: datetime, destination: str | None, base: dict,
              stages: StageTimer) -> dict:
        """Xếp hạng trên lịch sử đã đọc. Gọi `build_profile`, `score_candidates`, `mmr_select`, `explore_fill` và
        `_LocalSpace` qua tên toàn cục của module: harness bench (`src/evaluation/recsys_bench`) thay chúng theo tên."""
        t0 = now.timestamp()
        idx = self.index
        units = {e.get("productId") or "": idx.resolve(e.get("productId") or "") for e in raw}
        stored = self.vectors.vectors(sorted({idx.units[i].product_id for i in units.values() if i is not None}))
        space = _LocalSpace(idx, self.vectors.dimension)
        resolved = []
        for e in raw:
            i = units[e.get("productId") or ""]
            if i is None or idx.units[i].product_id not in stored:  # ngoài catalog hoặc chưa index
                continue
            resolved.append(ResolvedEvent(unit=space.add(i, stored[idx.units[i].product_id]), event_name=e["eventName"],
                                          days_ago=max(0.0, (t0 - _ts(e["timestamp"])) / 86400),
                                          trip_id=e.get("eventGroupId") or f"_solo_{e['productId']}", product_id=e["productId"],
                                          using_date=_using_date(e.get("usingDate"))))
        # trip đang mở xét theo usingDate (FR-REC-02, 01/10/2026): "hôm nay" theo giờ Việt Nam vì usingDate là ngày địa phương
        profile = build_profile(resolved, space.E, space.taxonomy, space.destination, today=local_today(now))
        stages.lap("history")

        if not profile.trips:
            result = {**base, **self._cold_start(k, now, destination)}
            stages.lap("coldStart")
            return result

        # candidate mask
        if profile.active_trip is not None:
            t = profile.active_trip
            dest, done = destination or t.destination, t.purchased_taxonomies
            m = idx.mask(destination=dest, only_recommendable=True) & ~np.isin(idx.taxonomy, list(done))
            if not m.any() and destination is None:
                m = idx.mask(only_recommendable=True) & ~np.isin(idx.taxonomy, list(done))
        else:
            dest, done = destination, set()
            m = idx.mask(destination=dest, only_recommendable=True)
        # Không gợi lại món đã mua (mọi lần mua, theo search unit) + combo ↔ thành phần cùng lần mua (FR-REC-02, 09/10).
        # Tính từ event thô, không từ `profile.bought_units` (chỉ gồm event có vector): mua món chưa index vẫn phải loại.
        bought = bought_units(idx, raw)
        m[sorted(bought)] = False

        # Top-K ứng viên quanh cả vector ngắn hạn lẫn dài hạn: score_candidates trộn cả hai.
        allowed = idx.allowed_ids(m)
        u_short = profile.active_trip.vec if profile.active_trip is not None else profile.u_long
        queries = [u_short] if profile.active_trip is None else [u_short, profile.u_long]
        # Món phổ biến chỉ phụ thuộc `dest` và mask `m`, nên tính trước: lượt lấy vector của chúng chạy song song với ANN.
        pop_global = self.popularity.unit_scores(dest) if self.popularity else {}
        popular = [g for g in sorted(pop_global, key=lambda g: -pop_global[g]) if m[g]][: self.popular_k]
        ann = [_Pending(name, self.executor, self.vectors.near_vector, q, allowed, self.candidate_k, with_vectors=True)
               for name, q in zip(("annShort", "annLong"), queries)]
        # Chạy song song thì lấy vector cho mọi món phổ biến chưa có trong lịch sử (tập lớn hơn lượt tuần tự); vòng ghép bên
        # dưới kiểm `g in space.local` trước, nên món ANN đã thêm vẫn dùng vector của ANN và kết quả y hệt.
        early = (_Pending("popularVectors", self.executor, self.vectors.vectors,
                          [idx.units[g].product_id for g in popular if g not in space.local])
                 if self.executor is not None else None)
        cand: list[int] = []
        for task in ann:   # ghép đúng thứ tự cũ: ngắn hạn rồi dài hạn
            for h in task.result():
                if h.product_id in idx.idx and h.vector is not None:
                    local = space.add(idx.idx[h.product_id], h.vector)
                    if local not in cand:
                        cand.append(local)

        popular_vectors = early or _Pending("popularVectors", None, self.vectors.vectors,
                                            [idx.units[g].product_id for g in popular if g not in space.local])
        fetched = popular_vectors.result()
        for task in (*ann, popular_vectors):
            stages.record(task.name, task.seconds)
        for g in popular:
            vec = fetched.get(idx.units[g].product_id)
            if g in space.local or vec is not None:
                local = space.local[g] if g in space.local else space.add(g, vec)
                if local not in cand:
                    cand.append(local)
        stages.lap("candidates")
        pop = np.array([pop_global.get(g, 0.0) for g in space.glob], dtype=np.float32)
        E = space.E
        # FR-REC-04 (09/10): điểm xuất phát của chuyến bay khách xem / đặt gần nhất; route bay khác điểm xuất phát bị hạ / loại
        taxonomy, origin_city = space.taxonomy, space.origin_city
        context = ScoreContext(taxonomy=taxonomy, origin_city=origin_city,
                               origin=infer_origin(resolved, taxonomy, origin_city))
        calibrated = self.next_trip_scoring and calibration_applies(idx.model_version)
        if self.next_trip_scoring and not calibrated and profile.active_trip is None:
            _warn_calibration_mismatch(idx.model_version)
        score, _ = score_candidates(profile, E, pop, context, next_trip_scoring=calibrated)
        cand = sorted(cand, key=lambda j: -score[j])[: self.candidate_k]
        # điểm đến lấy tại thời điểm MMR: `_LocalSpace` lớn dần trong request (ứng viên thêm sau build_profile)
        cap_dest = self.max_per_destination if profile.active_trip is None and destination is None else None
        chosen = mmr_select(score, E, cand, space.taxonomy, k, max_per_vertical=self.max_per_vertical,
                            destination=space.destination if cap_dest else None, max_per_destination=cap_dest)
        stages.lap("rank")
        if not chosen:
            result = {**base, **self._cold_start(k, now, destination)}
            stages.lap("coldStart")
            return result

        # Ô khám phá (FR-REC-02, 09/10): chỉ khi có chuyến mở và còn ô trống; món tại X không bị thay, chiến lược và
        # nextVertical tính trên món tại X. Request khoá `destination` vẫn lấp (khách thấy cả hai, spec §4.7).
        explore: list[int] = []
        if self.explore_fill and profile.active_trip is not None and len(chosen) < k:
            picked = explore_fill(idx, self.vectors, profile.u_long, dest, bought, {space.glob[j] for j in chosen},
                                  k - len(chosen), self.explore_candidate_k)
            explore = [space.add(g, vec) for g, vec in picked]
            if explore:
                log_event(logger, "recsys.explore_fill", "INFO", filled=len(explore),
                          message=f"recommend.explore_fill filled={len(explore)}")
        stages.lap("explore")
        E = space.E   # space lớn thêm sau ô khám phá; `score` chỉ phủ ứng viên cũ nên món khám phá chấm bằng cos(u_long)

        recs = []
        for rank, j in enumerate(chosen, 1):
            recs.append(hit(idx, space.glob[j], score[j], rank=rank, because=self._because(profile, j, E, space)))
        for rank, j in enumerate(explore, len(chosen) + 1):
            recs.append(hit(idx, space.glob[j], float(E[j] @ profile.u_long), rank=rank,
                            because=self._because(profile, j, E, space, long_term=True)))
        result = {**base, "strategy": profile.strategy, "destination": dest,
                  "nextVertical": str(Counter(idx.taxonomy[space.glob[j]] for j in chosen).most_common(1)[0][0]) if chosen else None,
                  "recommendations": recs, "sections": [],
                  "diagnostics": {"eventsUsed": profile.n_events, "coldStart": profile.n_events < 3,
                                  "excludedVerticals": sorted(map(str, done)), "trips": len(profile.trips),
                                  "exploreFilled": len(explore)}}
        stages.lap("build")
        return result

    @staticmethod
    def _because(profile, j: int, E: np.ndarray, space: _LocalSpace, long_term: bool = False) -> list[dict]:
        idx = space.index
        return [{"productId": b["productId"], "productName": idx.units[space.glob[b["unit"]]].name, "event": b["event"],
                 "daysAgo": int(b["daysAgo"]), "contribution": b["contribution"]}
                for b in explain(profile, j, E, long_term=long_term)]

    # ---- khách mới: điểm đến của tháng + theo mùa; because[] rỗng, lý do ở section.reason
    def _cold_start(self, k: int, now: datetime, destination: str | None = None) -> dict:
        idx = self.index
        sections, flat, used = [], [], set()
        if destination:
            flat = [{**p, "rank": rank} for rank, p in enumerate(self._top_products(destination, k), 1)]
        elif self.popularity:
            groups = [("Điểm đến được đặt nhiều tháng %d" % now.month, self.popularity.top_destinations_month(k=3)),
                      ("Điểm đến phổ biến theo mùa", self.popularity.seasonal_destinations(k=3))]
            seen = set()
            for title, dests in groups:
                for d in dests:
                    if d["destination"] in seen:
                        continue
                    seen.add(d["destination"])
                    sections.append({"title": title, **d, "products": self._top_products(d["destination"], k)})
            per_taxonomy: Counter = Counter()  # danh sách phẳng ghép từ nhiều section cũng tối đa 2 món mỗi taxonomy
            for sec in sections:
                for p in sec["products"]:
                    if p["productId"] in used or len(flat) >= k:
                        continue
                    if self.max_per_vertical is not None and per_taxonomy[p["taxonomy"]] >= self.max_per_vertical:
                        continue
                    used.add(p["productId"]); per_taxonomy[p["taxonomy"]] += 1
                    flat.append({**p, "rank": len(flat) + 1})
        else:  # chưa có event → xếp theo reviewCount
            m = idx.mask(only_recommendable=True)
            order = sorted((i for i in range(len(idx.units)) if m[i]), key=lambda i: -(idx.units[i].attributes.get("reviewCount") or 0))
            chosen = _cap_per_taxonomy(order, idx.taxonomy, k, self.max_per_vertical)
            flat = [hit(idx, i, 0.0, rank=r, because=[]) for r, i in enumerate(chosen, 1)]
        return {"strategy": "popular", "destination": destination, "nextVertical": None, "sections": sections, "recommendations": flat,
                "diagnostics": {"eventsUsed": 0, "coldStart": True, "excludedVerticals": [],
                                "popularitySource": "events" if self.popularity else "reviewCount"}}

    def _top_products(self, destination: str, k: int) -> list[dict]:
        idx = self.index
        scores = self.popularity.unit_scores(destination) if self.popularity else {}
        m = idx.mask(destination=destination, only_recommendable=True)
        ranked = sorted((i for i in range(len(idx.units)) if m[i]),
                        key=lambda i: (-scores.get(i, 0.0), -(idx.units[i].attributes.get("reviewCount") or 0)))
        chosen = _cap_per_taxonomy(ranked, idx.taxonomy, k, self.max_per_vertical)
        return [hit(idx, i, scores.get(i, 0.0), because=[]) for i in chosen]
