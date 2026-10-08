"""Seed S và trọng số w_e của một khách — lấy từ `build_profile` của engine, không tự tính lại (spec `recsys-algos-v1.md` §0.3).

Mirror đúng bước resolve của `RecommendForUser.__call__` (`use_cases.py:113-124`): bỏ event ngoài catalog và event có unit chưa có
vector; `days_ago = max(0, (as_of − ts)/86400)`; trip = `eventGroupId` hoặc `_solo_<productId>`; `usingDate` qua `_using_date`. Khác
engine ở một điểm cố ý: `unit` là chỉ số **toàn cục** của `UnitIndex` (engine dùng chỉ số cục bộ `_LocalSpace`), nên `build_profile`
nhận `E_full` và `profile.bought_units` / `trip.events[*].unit` dùng thẳng với mask / E_full.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np

from src.backend.app.application.ports import UnitIndex
from src.backend.app.application.recommendation.use_cases import _ts, _using_date
from src.backend.app.domain.recommendation import profile as P
from src.backend.app.domain.recommendation.profile import Profile, ResolvedEvent, build_profile

from .base import Seeds, TrainData


def resolved_events(events: list[dict], index: UnitIndex, as_of: datetime, has_vec: np.ndarray) -> list[ResolvedEvent]:
    t0 = as_of.timestamp()
    out: list[ResolvedEvent] = []
    for e in events:
        pid = e.get("productId") or ""
        unit = index.resolve(pid)
        if unit is None or not has_vec[unit]:
            continue
        out.append(ResolvedEvent(unit=unit, event_name=e["eventName"], days_ago=max(0.0, (t0 - _ts(e["timestamp"])) / 86400),
                                 trip_id=e.get("eventGroupId") or f"_solo_{pid}", product_id=pid,
                                 using_date=_using_date(e.get("usingDate"))))
    return out


def profile_for(resolved: list[ResolvedEvent], data: TrainData, as_of: datetime) -> Profile:
    """`build_profile` của engine với E_full; `today = as_of.date()` như `use_cases.py:126` (`now.date()`, UTC)."""
    return build_profile(resolved, data.E, data.index.taxonomy, data.index.destination, today=as_of.date())


def seeds_for(profile: Profile) -> Seeds:
    """Nhánh mở: S = event của trip mở, `w_e = W_TYPE·2^(−d/H_SHORT)`; nhánh long: S = mọi event, nhân thêm `2^(−age_t/H_LONG)`
    (dạng `explain`, `profile.py:149-151`). Hằng đọc từ module `profile` lúc gọi để `--override` đi theo."""
    if not profile.trips:
        return Seeds(np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.float32), "none")
    if profile.active_trip is not None:
        sources, branch = [(1.0, profile.active_trip)], "short"
    else:
        sources, branch = [(2 ** (-t.age_days / P.H_LONG_DAYS), t) for t in profile.trips.values()], "long"
    units, weights = [], []
    for wt, trip in sources:
        for e in trip.events:
            units.append(e.unit)
            weights.append(wt * P.W_TYPE.get(e.event_name, 0.1) * 2 ** (-e.days_ago / P.H_SHORT_DAYS))
    return Seeds(np.asarray(units, dtype=np.int64), np.asarray(weights, dtype=np.float32), branch)


def weighted_mean_rows(table_lookup, seeds: Seeds, cand: np.ndarray) -> np.ndarray:
    """`collab(c) = Σ_s w_s · T[s, c] / Σ_s w_s` (spec §1.2): `table_lookup(unit) -> np.ndarray (I,)` trả hàng của seed trên toàn
    catalog (0 ngoài top-K). Seed không có láng giềng vẫn vào mẫu số; S rỗng → 0."""
    out = np.zeros(len(cand), dtype=np.float32)
    total = seeds.total
    if total <= 0:
        return out
    acc = np.zeros_like(out, dtype=np.float64)
    for unit, w in zip(seeds.units.tolist(), seeds.weights.tolist()):
        row = table_lookup(int(unit))
        if row is not None:
            acc += w * row[cand]
    return (acc / total).astype(np.float32)
