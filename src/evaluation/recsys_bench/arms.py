"""Các "arm" được so trên cùng split: baseline và engine production. Mỗi arm trả danh sách productId đã xếp hạng.

Ba baseline bắt buộc của handbook §12: `random` (Day 1), `most_popular` theo **cửa sổ thời gian** và
`most_popular_in_destination` (30/09, Day 2 của lịch). Hai baseline popularity dùng đúng `Popularity.unit_scores` của
production (đếm purchase trong `POPULARITY_WINDOW_DAYS` ngày trước `as_of` — qua `OfflineEngine.popularity_at`, nên
không nhìn thấy purchase từ `as_of` trở đi) và cùng tập ứng viên với engine (`recommendable` và còn chỗ).
"""
from __future__ import annotations

import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter

import numpy as np

from src.backend.app.application.ports import UnitIndex
from src.backend.app.domain.recommendation.profile import MAX_REPEAT_PER_TRIP, local_today, trip_is_open

from .engine import POPULARITY_WINDOW_DAYS, OfflineEngine   # cửa sổ 90 ngày khai một chỗ, vào configHash (B3)
from .events import parse_ts, trip_ends_on


@dataclass
class Ranked:
    product_ids: list[str]
    latency_ms: float
    meta: dict = field(default_factory=dict)


class RandomArm:
    """Bốc ngẫu nhiên trong đúng tập ứng viên của engine (`recommendable` và còn chỗ), tất định theo (seed, khách)."""

    family = "random"

    def __init__(self, index: UnitIndex, seed: int):
        self.seed, self.key = seed, f"random-s{seed}"
        self._ids = [index.units[i].product_id for i in np.flatnonzero(index.mask(only_recommendable=True))]

    def recommend(self, cdp_user_id: str, as_of: datetime, k: int, events: list[dict]) -> Ranked:
        started = perf_counter()
        rng = np.random.default_rng([self.seed, zlib.crc32(cdp_user_id.encode("utf-8"))])
        picks = rng.choice(len(self._ids), size=min(k, len(self._ids)), replace=False) if self._ids else []
        return Ranked([self._ids[i] for i in picks], (perf_counter() - started) * 1000)


def trip_destination(index: UnitIndex, events: list[dict], as_of: datetime) -> str | None:
    """Điểm đến của chuyến **đang mở** (như engine: chưa kết thúc theo `usingDate`, hoặc không có `usingDate` và tuổi ≤
    `ACTIVE_TRIP_MAX_AGE_DAYS`; trẻ nhất) hoặc, nếu không có, chuyến gần nhất.

    Trip = `eventGroupId`, thiếu thì `_solo_<productId>` như `use_cases.py`; điểm đến = điểm đến xuất hiện nhiều nhất
    trong các event (đã quy về search unit) của chuyến đó. Không có event quy được → None (baseline lùi về toàn cục).
    """
    rows = []
    for e in events:
        unit = index.resolve(str(e.get("productId") or ""))
        if unit is None:
            continue
        days_ago = (as_of - parse_ts(e["timestamp"])).total_seconds() / 86400
        rows.append((days_ago, e, unit, e.get("eventGroupId") or f"_solo_{e['productId']}"))
    trips: dict[str, list[tuple[float, int]]] = defaultdict(list)     # sau cap lặp: điểm đến, như build_profile
    raw: dict[str, list[tuple[float, dict]]] = defaultdict(list)      # mọi event: tuổi, ngày kết thúc
    seen: Counter = Counter()
    for days_ago, e, unit, tid in sorted(rows, key=lambda r: -r[0]):     # cũ trước; mỗi (trip, unit) giữ MAX_REPEAT như build_profile
        raw[tid].append((days_ago, e))
        seen[(tid, unit)] += 1
        if seen[(tid, unit)] > MAX_REPEAT_PER_TRIP:
            continue
        trips[tid].append((days_ago, unit))
    if not trips:
        return None
    ages = {tid: min(d for d, _ in evs) for tid, evs in raw.items()}
    today = local_today(as_of)
    open_trips = [tid for tid, age in ages.items() if trip_is_open(age, trip_ends_on(e for _, e in raw[tid]), today)]
    booked = [tid for tid in open_trips if any(e.get("eventName") == "purchase" for _, e in raw[tid])]
    chosen = min(booked or open_trips or ages, key=lambda tid: ages[tid])   # chuyến đã đặt còn mở đứng trước (09/10)
    return Counter(str(index.destination[u]) for _, u in trips[chosen]).most_common(1)[0][0]


class MostPopularArm:
    """most-popular theo cửa sổ thời gian: điểm `Popularity.unit_scores(window_days=POPULARITY_WINDOW_DAYS)` tại `as_of`
    (chỉ purchase trước `as_of`), sắp giảm dần, hoà thì theo chỉ số unit; chỉ unit `recommendable` + còn chỗ."""

    family = key = "most_popular"

    def __init__(self, index: UnitIndex, engine: OfflineEngine, *, window_days: int = POPULARITY_WINDOW_DAYS):
        self.index, self.engine, self.window_days = index, engine, window_days
        self._mask = index.mask(only_recommendable=True)

    def _rank(self, scores: dict[int, float], k: int, exclude: set[str] = frozenset()) -> list[str]:
        ranked = sorted(((u, s) for u, s in scores.items() if self._mask[u]), key=lambda t: (-t[1], t[0]))
        out = []
        for u, _ in ranked:
            pid = self.index.units[u].product_id
            if pid not in exclude:
                out.append(pid)
            if len(out) >= k:
                break
        return out

    def recommend(self, cdp_user_id: str, as_of: datetime, k: int, events: list[dict]) -> Ranked:
        started = perf_counter()
        pop = self.engine.popularity_at(as_of)
        ids = self._rank(pop.unit_scores(window_days=self.window_days), k)
        return Ranked(ids, (perf_counter() - started) * 1000, {"strategy": self.key})


class MostPopularInDestinationArm(MostPopularArm):
    """most-popular-in-destination (handbook §12, baseline quan trọng nhất): điểm đến của chuyến đang mở (hoặc gần nhất)
    của khách → `unit_scores(destination=…)`; thiếu ứng viên thì bù bằng most-popular toàn cục (đánh dấu `fallback`)."""

    family = key = "most_popular_in_destination"

    def recommend(self, cdp_user_id: str, as_of: datetime, k: int, events: list[dict]) -> Ranked:
        started = perf_counter()
        pop = self.engine.popularity_at(as_of)
        dest = trip_destination(self.index, events, as_of)
        ids = self._rank(pop.unit_scores(destination=dest, window_days=self.window_days), k) if dest else []
        n_dest = len(ids)
        if len(ids) < k:
            ids += self._rank(pop.unit_scores(window_days=self.window_days), k - len(ids), exclude=set(ids))
        return Ranked(ids, (perf_counter() - started) * 1000,
                      {"strategy": self.key if dest and n_dest else "most_popular_fallback", "destination": dest,
                       "nInDestination": n_dest})


class EngineArm:
    """Engine production (`RecommendForUser`) qua `OfflineEngine`: `engine` = mode eval (đủ k món), `engine_prod` = đúng
    list production (cap 2 mỗi taxonomy) — báo cả hai để biết khách thật sự thấy gì."""

    mean_meta = ("exploreFilled",)    # số ô khám phá trung bình mỗi khách (FR-REC-02, 09/10) → `explore_filled` trong summary

    def __init__(self, engine: OfflineEngine):
        self.engine = engine
        self.family = self.key = "engine" if engine.mode == "eval" else "engine_prod"

    @staticmethod
    def _ranked(response: dict, latency: float, **extra) -> Ranked:
        diagnostics = response.get("diagnostics") or {}
        return Ranked([r["productId"] for r in response.get("recommendations", [])], latency, {
            "strategy": response.get("strategy"), "destination": response.get("destination"),
            "nextVertical": response.get("nextVertical"), "eventsUsed": diagnostics.get("eventsUsed"),
            "coldStart": diagnostics.get("coldStart"), "excludedVerticals": diagnostics.get("excludedVerticals"),
            "exploreFilled": int(diagnostics.get("exploreFilled") or 0), **extra,
        })

    def recommend(self, cdp_user_id: str, as_of: datetime, k: int, events: list[dict]) -> Ranked:
        started = perf_counter()
        response = self.engine.recommend(cdp_user_id, as_of, k, events)
        return self._ranked(response, (perf_counter() - started) * 1000)


class EngineNoMmrArm(EngineArm):
    """`engine_nommr` (B5 / B8, 01/10): cùng engine mode eval nhưng `mmr_select` thay bằng "lấy theo score" và k = `pool_k`
    (mặc định 200 = `candidate_k`) → list = **toàn bộ pool ứng viên** xếp theo score. `rank` của target trong list này
    (poolRank) tách "không vào pool" (lọc / ngoài top-K vector / không đủ phổ biến) khỏi "vào pool nhưng MMR đẩy xuống".
    Ô khám phá (09/10) không phải pool nên tắt ở arm này. Không phải số báo cáo; dùng cho 20 ca (B8) và ablation MMR (M7)."""

    family = key = "engine_nommr"

    def __init__(self, engine: OfflineEngine, *, pool_k: int | None = None):
        self.engine, self.pool_k = engine, pool_k or engine.candidate_k     # = candidate_k: pool đúng bằng pool của engine

    @staticmethod
    def _by_score(score, E, candidates, taxonomy, k, max_per_vertical=None):
        return sorted(candidates, key=lambda i: -float(score[i]))[:k]

    def recommend(self, cdp_user_id: str, as_of: datetime, k: int, events: list[dict]) -> Ranked:
        from unittest.mock import patch
        started = perf_counter()
        with patch("src.backend.app.application.recommendation.use_cases.mmr_select", self._by_score),                 patch("src.backend.app.application.recommendation.use_cases.explore_fill", lambda *a, **kw: []):
            response = self.engine.recommend(cdp_user_id, as_of, self.pool_k, events)
        return self._ranked(response, (perf_counter() - started) * 1000, poolK=self.pool_k)
