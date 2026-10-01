"""B5 (01/10) — trần recall của engine: target có thể nằm trong mask ứng viên của `RecommendForUser` không?

Mô phỏng đúng các bộ lọc **cứng** của engine (`application/recommendation/use_cases.py`, `domain/recommendation/profile.py`):
- profile: event quy về search unit, mỗi (trip, unit) giữ `MAX_REPEAT_PER_TRIP` event cũ nhất, trip = `eventGroupId` hoặc
  `_solo_<productId>`; trip mở = trẻ nhất trong các trip `trip_is_open` (chưa kết thúc theo `usingDate`, hoặc không có
  `usingDate` và tuổi ≤ `ACTIVE_TRIP_MAX_AGE_DAYS` = 14; tuổi / ngày kết thúc / món đã mua xét trên mọi event, cap chỉ giới hạn
  trọng số vector); `bought_units` = mọi unit đã mua;
- mask: `recommendable` ∧ còn chỗ ∧ không phải unit đã mua; có trip mở thì thêm cùng điểm đến trip mở ∧ taxonomy chưa mua
  trong trip mở (mask theo điểm đến rỗng → bỏ điều kiện điểm đến, như engine);
- không có trip nào → engine đi `_cold_start` (popular theo điểm đến / mùa): tính là `cold_start`, không mô phỏng.

Không mô phỏng phần **mềm**: target phải lọt top-K vector hoặc top-50 phổ biến — phần đó đo bằng arm `engine_nommr` (pool
200 xếp theo score, không MMR). Hai bản: **chính xác** dùng `destination` / `excludedVerticals` / `strategy` engine trả về
trong `per_user.jsonl`; **xấp xỉ** chỉ dùng `engine_view` — tỉ lệ đồng thuận giữa hai bản báo trong `ceiling.json`.
Luật đọc (plan Day 3): ceiling < Recall@20 của most-popular-in-destination → lỗi thiết kế filter, không grid-search.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from src.backend.app.application.ports import UnitIndex
from src.backend.app.domain.recommendation.profile import DORMANT_AFTER_DAYS, MAX_REPEAT_PER_TRIP, local_today, trip_is_open

from .events import parse_ts, trip_ends_on
from .splits import Split

REASONS = ("cold_start", "not_recommendable", "not_available", "already_bought", "taxonomy_excluded", "destination_mismatch",
           "no_vector")


@dataclass
class TripView:
    trip_id: str
    age_days: float
    n_events: int
    purchased_taxonomies: set[str]
    destination: str
    units: set[int]
    solo: bool
    ends_on: object = None           # max(usingDate) trên mọi event của trip — trip đang mở xét theo đây (FR-REC-02, 01/10/2026)


@dataclass
class EngineView:
    """Những gì `build_profile` sẽ suy ra từ train của một khách tại `as_of`."""
    n_events: int
    trips: dict[str, TripView]
    active_trip: str | None
    bought_units: set[int] = field(default_factory=set)

    @property
    def destination(self) -> str | None:
        return self.trips[self.active_trip].destination if self.active_trip else None

    @property
    def excluded(self) -> set[str]:
        return set(self.trips[self.active_trip].purchased_taxonomies) if self.active_trip else set()

    @property
    def active_is_solo(self) -> bool:
        return bool(self.active_trip) and self.trips[self.active_trip].solo

    @property
    def strategy(self) -> str:   # như `Profile.strategy`
        if self.active_trip:
            if self.excluded:
                return "cross_vertical"
            return "cold_start_content" if self.n_events < 3 else "recent_activity"
        if not self.trips:
            return "popular"
        return "dormant" if min(t.age_days for t in self.trips.values()) > DORMANT_AFTER_DAYS else "long_term"


def engine_view(train: list[dict], index: UnitIndex, as_of: datetime, has_vector: set[str] | None = None) -> EngineView:
    """`has_vector`: productId của unit có vector; None = coi mọi unit đều có (run `vectorsMissing 0`)."""
    rows = []
    for e in train:
        pid = str(e.get("productId") or "")
        unit = index.resolve(pid)
        if unit is None or (has_vector is not None and index.units[unit].product_id not in has_vector):
            continue
        days = max(0.0, (as_of - parse_ts(e["timestamp"])).total_seconds() / 86400)
        rows.append((days, e, unit, e.get("eventGroupId") or f"_solo_{pid}"))
    seen: Counter = Counter()
    by_trip: dict[str, list] = defaultdict(list)      # sau cap lặp: n_events, điểm đến, units — như build_profile
    every: dict[str, list] = defaultdict(list)        # mọi event: tuổi, ngày kết thúc, món đã mua
    for days, e, unit, tid in sorted(rows, key=lambda r: -r[0]):      # cũ trước, như build_profile
        every[tid].append((days, e, unit))
        seen[(tid, unit)] += 1
        if seen[(tid, unit)] > MAX_REPEAT_PER_TRIP:
            continue
        by_trip[tid].append((days, e, unit))
    trips: dict[str, TripView] = {}
    bought: set[int] = set()
    for tid, evs in by_trip.items():
        all_evs = every[tid]
        purchased = {str(index.taxonomy[u]) for _, e, u in all_evs if e.get("eventName") == "purchase"}
        bought |= {u for _, e, u in all_evs if e.get("eventName") == "purchase"}
        trips[tid] = TripView(tid, min(d for d, _, _ in all_evs), len(evs), purchased,
                              str(Counter(str(index.destination[u]) for _, _, u in evs).most_common(1)[0][0]),
                              {u for _, _, u in evs}, tid.startswith("_solo_"), trip_ends_on(e for _, e, _ in all_evs))
    if not trips:
        return EngineView(0, {}, None)
    today = local_today(as_of)
    active = [t for t, v in trips.items() if trip_is_open(v.age_days, v.ends_on, today)]
    return EngineView(sum(v.n_events for v in trips.values()), trips,
                      min(active, key=lambda t: trips[t].age_days) if active else None, bought)


def unreachable(target: str, view: EngineView, index: UnitIndex, *, engine_meta: dict | None = None,
                has_vector: set[str] | None = None) -> list[str]:
    """Lý do target không thể vào mask ứng viên (rỗng = tới được). `engine_meta` (hàng `per_user` của arm engine:
    `strategy`, `destination`, `excludedVerticals`) → bản chính xác; None → xấp xỉ từ `view`."""
    t = index.idx[target]
    why: list[str] = []
    if engine_meta is not None:
        if engine_meta.get("strategy") == "popular":
            return ["cold_start"]
        dest, excl = engine_meta.get("destination"), set(engine_meta.get("excludedVerticals") or [])
    else:
        if not view.trips:
            return ["cold_start"]
        dest, excl = view.destination, view.excluded
    if has_vector is not None and index.units[t].product_id not in has_vector:
        why.append("no_vector")
    if not bool(index.recommendable[t]):
        why.append("not_recommendable")
    if not bool(index.available[t]):
        why.append("not_available")
    if t in view.bought_units:
        why.append("already_bought")
    if str(index.taxonomy[t]) in excl:
        why.append("taxonomy_excluded")
    if dest and str(index.destination[t]) != dest:
        m = index.mask(destination=dest, only_recommendable=True) & ~np.isin(index.taxonomy, sorted(excl))
        if m.any():                                   # engine chỉ bỏ điều kiện điểm đến khi mask theo điểm đến rỗng
            why.append("destination_mismatch")
    return why


def ceiling(rows_engine: dict[str, dict], split: Split, index: UnitIndex, views: dict[str, EngineView], *,
            k: int = 20, has_vector: set[str] | None = None) -> dict:
    """`rows_engine`: user → hàng `per_user` của arm engine (mode eval). Trả tổng hợp + `per_user` (lý do, trúng@k)."""
    per_user: dict[str, dict] = {}
    exact_multi: Counter = Counter()
    first: Counter = Counter()
    agree = hits = hits_reachable = reachable = 0
    users = sorted(u for u in split.targets if u in rows_engine)
    for u in users:
        row, view, target = rows_engine[u], views[u], split.targets[u]
        exact = unreachable(target, view, index, engine_meta=row, has_vector=has_vector)
        approx = unreachable(target, view, index, has_vector=has_vector)
        hit = row.get("rank") is not None and row["rank"] <= k
        agree += set(exact) == set(approx)
        hits += hit
        if not exact:
            reachable += 1
            hits_reachable += hit
        else:
            first[exact[0]] += 1
            for r in exact:
                exact_multi[r] += 1
        per_user[u] = {"unreachable": exact, "approx": approx, f"hit@{k}": bool(hit), "strategy": row.get("strategy"),
                       "activeTripIsSolo": view.active_is_solo}
    n = len(users)
    return {"k": k, "n": n, "reachable": reachable, "ceiling": reachable / n if n else 0.0,
            f"recall@{k}": hits / n if n else 0.0,
            f"recall@{k}_reachable": hits_reachable / reachable if reachable else 0.0,
            "reasonsMulti": dict(sorted(exact_multi.items())), "firstReason": dict(sorted(first.items())),
            "approxAgree": agree / n if n else 0.0, "perUser": per_user}


def ceiling_markdown(c: dict, *, mpd_recall: float | None = None) -> str:
    k = c["k"]
    lines = [f"| Chỉ số | Giá trị |", "|---|---:|",
             f"| Khách | {c['n']} |", f"| Target tới được mask ứng viên (ceiling) | **{c['ceiling']:.3f}** ({c['reachable']}/{c['n']}) |",
             f"| Recall@{k} engine | {c[f'recall@{k}']:.3f} |",
             f"| Recall@{k} trên khách tới được | {c[f'recall@{k}_reachable']:.3f} |",
             f"| Đồng thuận bản chính xác / xấp xỉ | {c['approxAgree']:.3f} |"]
    if mpd_recall is not None:
        verdict = "ceiling ≥ Recall@20 mpd → filter không phải nút thắt" if c["ceiling"] >= mpd_recall else \
            "**ceiling < Recall@20 mpd → lỗi thiết kế filter, không grid-search**"
        lines.append(f"| So với most_popular_in_destination Recall@{k} = {mpd_recall:.3f} | {verdict} |")
    lines += ["", "| Lý do không tới được (đa nhãn) | Khách | Là lý do đầu |", "|---|---:|---:|"]
    for r in REASONS:
        if c["reasonsMulti"].get(r):
            lines.append(f"| `{r}` | {c['reasonsMulti'][r]} | {c['firstReason'].get(r, 0)} |")
    return "\n".join(lines)
