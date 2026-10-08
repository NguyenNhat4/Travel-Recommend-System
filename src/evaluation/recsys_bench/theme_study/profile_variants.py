"""Biến thể cách dựng profile (bước 1, 08/10/2026) — chỉ dùng trong tiến trình đo, không đổi engine.

Dựa trên `domain.recommendation.profile.build_profile` (production) với ba công tắc độc lập:

- `cap_fix`    : giới hạn lặp giữ event MỚI nhất (production giữ 3 event CŨ nhất). Từ 09/10/2026 production cũng không bao giờ
                 bỏ purchase / add_to_cart khỏi vector (`CAP_EXEMPT_EVENTS`), nên công tắc này chỉ còn đổi thứ tự giữ.
- `confidence` : u_long cộng hướng của từng chuyến × độ tin cậy của chuyến `min(1, Σ W_TYPE)` thay vì mọi chuyến nặng như
                 nhau sau chuẩn hoá (một lượt xem lẻ 0,2; một lần mua 1,0). **Là production từ 09/10/2026 (PR-A, P2 đã ship)**
                 → mặc định bật; `confidence=False` = công thức trước 09/10 (`P0_legacy`).
- `session`    : gom các event không có eventGroupId (`_solo_<sản phẩm>`, mỗi sản phẩm xem là một "chuyến") thành phiên theo
                 điểm đến, cách nhau ≤ ACTIVE_TRIP_MAX_AGE_DAYS.

Viết lại 2026-10-08 (plan WP0.3, `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md`): bản cũ tính tuổi chuyến, `ends_on`,
`purchased_taxonomies` và `bought_units` trên event CÒN LẠI sau cap, tức luật trước `9b703ba`. Engine của nhánh này tính bốn
thứ đó trên MỌI event (dict `every` trong `build_profile`); cap chỉ giới hạn trọng số vector. Bản viết lại theo đúng engine,
nên khác biệt giữa P0 và P1/P2/P4 chỉ còn đúng ba công tắc trên.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

import numpy as np

from src.backend.app.domain.recommendation.profile import (
    ACTIVE_TRIP_MAX_AGE_DAYS, H_LONG_DAYS, H_SHORT_DAYS, MAX_REPEAT_PER_TRIP, W_TYPE, Profile, Trip, build_profile,
    trip_is_open,
)

STRONG = {"purchase", "add_to_cart"}     # = profile.CAP_EXEMPT_EVENTS


def _sessionize(events, destination):
    """Đổi trip_id của event lẻ (`_solo_…`) thành phiên theo điểm đến; event có eventGroupId giữ nguyên."""
    out, cur = [], {}
    for e in sorted(events, key=lambda x: -x.days_ago):          # cũ → mới
        if not e.trip_id.startswith("_solo_"):
            out.append(e)
            continue
        d = str(destination[e.unit])
        sid, last = cur.get(d, (None, None))
        if sid is None or last - e.days_ago > ACTIVE_TRIP_MAX_AGE_DAYS:
            sid = f"_sess_{d}_{len(out)}"
        cur[d] = (sid, e.days_ago)
        out.append(type(e)(**{**e.__dict__, "trip_id": sid}))
    return out


def _cap(events, cap_fix: bool):
    seen: Counter = Counter()
    kept = []
    order = sorted(events, key=lambda x: x.days_ago) if cap_fix else sorted(events, key=lambda x: -x.days_ago)
    for e in order:                                              # cap_fix: mới → cũ; production: cũ → mới
        if e.event_name in STRONG:                               # production 09/10: event mạnh không bị cap
            kept.append(e)
            continue
        seen[(e.trip_id, e.unit)] += 1
        if seen[(e.trip_id, e.unit)] > MAX_REPEAT_PER_TRIP:
            continue
        kept.append(e)
    return sorted(kept, key=lambda x: -x.days_ago)


def make_build_profile(cap_fix=False, confidence=True, session=False, force=False):
    """force=True: dùng bản viết lại kể cả khi mọi công tắc ở mức production (để kiểm tra khớp production)."""
    if not (cap_fix or session or force) and confidence:
        return build_profile

    def bp(events, E, taxonomy, destination, today: date | None = None) -> Profile:
        evs = _sessionize(events, destination) if session else list(events)
        by_trip: dict[str, list] = defaultdict(list)       # sau cap: trọng số vector, n_events, điểm đến, độ tin cậy
        every: dict[str, list] = defaultdict(list)         # mọi event: tuổi, ngày kết thúc, món đã mua (như build_profile)
        for e in sorted(evs, key=lambda x: -x.days_ago):
            every[e.trip_id].append(e)
        for e in _cap(evs, cap_fix):
            by_trip[e.trip_id].append(e)
        trips: dict[str, Trip] = {}
        conf: dict[str, float] = {}
        for tid, tev in by_trip.items():
            v = np.zeros(E.shape[1], dtype=np.float32)
            for e in tev:
                v += W_TYPE.get(e.event_name, 0.1) * 2 ** (-e.days_ago / H_SHORT_DAYS) * E[e.unit]
            n = np.linalg.norm(v)
            all_evs = every[tid]
            ends_on = max((e.using_date for e in all_evs if e.using_date is not None), default=None)
            trips[tid] = Trip(
                trip_id=tid, events=tev, vec=v / n if n else v, age_days=min(e.days_ago for e in all_evs),
                purchased_taxonomies={str(taxonomy[e.unit]) for e in all_evs if e.event_name == "purchase"},
                destination=str(Counter(destination[e.unit] for e in tev).most_common(1)[0][0]),
                ends_on=ends_on, ended=ends_on is not None and today is not None and ends_on < today,
            )
            # độ tin cậy theo tổng trọng số loại event, KHÔNG suy giảm (tuổi chuyến đã có ở hệ số H_LONG).
            # Tính trên event sau cap vì nó là hệ số của chính vector dựng từ các event đó (giữ đúng P2 đã đo 08/10).
            conf[tid] = min(1.0, sum(W_TYPE.get(e.event_name, 0.1) for e in tev))
        if not trips:
            return Profile(trips={}, u_long=np.zeros(E.shape[1], dtype=np.float32), active_trip=None, n_events=0)
        u_long = sum(2 ** (-t.age_days / H_LONG_DAYS) * (conf[t.trip_id] if confidence else 1.0) * t.vec
                     for t in trips.values())
        u_long = u_long / (np.linalg.norm(u_long) or 1)
        active = [t for t in trips.values() if trip_is_open(t.age_days, t.ends_on, today)]
        active_trip = min(active, key=lambda t: t.age_days) if active else None
        bought = {e.unit for tev in every.values() for e in tev if e.event_name == "purchase"}
        return Profile(trips=trips, u_long=u_long, active_trip=active_trip,
                       n_events=sum(len(t.events) for t in trips.values()), bought_units=bought)

    return bp


PROFILES = {
    "P0_prod": {},                                   # production hiện hành (từ 09/10 = P2 đã ship)
    "P0_legacy": {"confidence": False},              # production trước 09/10/2026 (mọi chuyến nặng như nhau)
    "P1_capFix": {"cap_fix": True},
    "P2_confidence": {"confidence": True},           # = P0_prod từ 09/10; giữ tên để lệnh cũ chạy được
    "P3_session": {"session": True},
    "P4_all": {"cap_fix": True, "confidence": True, "session": True},
}
