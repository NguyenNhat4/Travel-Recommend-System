"""Biến thể cách dựng profile (bước 1, 08/10/2026) — chỉ dùng trong tiến trình đo, không đổi engine.

Dựa trên `domain.recommendation.profile.build_profile` (production) với ba công tắc độc lập:

- `cap_fix`    : giới hạn lặp giữ event MỚI nhất, không bao giờ bỏ purchase / add_to_cart (production giữ 3 event CŨ nhất,
                 bất kể loại).
- `confidence` : u_long cộng hướng của từng chuyến × độ tin cậy của chuyến `min(1, Σ W_TYPE × suy giảm)` thay vì mọi chuyến
                 nặng như nhau sau chuẩn hoá (một lượt xem lẻ 0,2; một lần mua 1,0; năm lượt xem 1,0).
- `session`    : gom các event không có eventGroupId (`_solo_<sản phẩm>`, mỗi sản phẩm xem là một "chuyến") thành phiên theo
                 điểm đến, cách nhau ≤ ACTIVE_TRIP_MAX_AGE_DAYS.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

import numpy as np

from src.backend.app.domain.recommendation.profile import (
    ACTIVE_TRIP_MAX_AGE_DAYS, H_LONG_DAYS, H_SHORT_DAYS, MAX_REPEAT_PER_TRIP, W_TYPE, Profile, Trip, build_profile,
    trip_is_open,
)

STRONG = {"purchase", "add_to_cart"}


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
        if cap_fix and e.event_name in STRONG:
            kept.append(e)
            continue
        seen[(e.trip_id, e.unit)] += 1
        if seen[(e.trip_id, e.unit)] > MAX_REPEAT_PER_TRIP:
            continue
        kept.append(e)
    return sorted(kept, key=lambda x: -x.days_ago)


def make_build_profile(cap_fix=False, confidence=False, session=False, force=False):
    """force=True: dùng bản viết lại kể cả khi mọi công tắc tắt (để kiểm tra khớp production)."""
    if not (cap_fix or confidence or session or force):
        return build_profile

    def bp(events, E, taxonomy, destination, today: date | None = None) -> Profile:
        evs = _sessionize(events, destination) if session else list(events)
        by_trip: dict[str, list] = defaultdict(list)
        for e in _cap(evs, cap_fix):
            by_trip[e.trip_id].append(e)
        trips: dict[str, Trip] = {}
        conf: dict[str, float] = {}
        for tid, tev in by_trip.items():
            v = np.zeros(E.shape[1], dtype=np.float32)
            w_sum = 0.0
            for e in tev:
                w = W_TYPE.get(e.event_name, 0.1) * 2 ** (-e.days_ago / H_SHORT_DAYS)
                v += w * E[e.unit]
                w_sum += w
            n = np.linalg.norm(v)
            ends_on = max((e.using_date for e in tev if e.using_date is not None), default=None)
            trips[tid] = Trip(
                trip_id=tid, events=tev, vec=v / n if n else v, age_days=min(e.days_ago for e in tev),
                purchased_taxonomies={str(taxonomy[e.unit]) for e in tev if e.event_name == "purchase"},
                destination=str(Counter(destination[e.unit] for e in tev).most_common(1)[0][0]),
                ends_on=ends_on, ended=ends_on is not None and today is not None and ends_on < today,
            )
            # độ tin cậy theo tổng trọng số loại event, KHÔNG suy giảm (tuổi chuyến đã có ở hệ số H_LONG)
            conf[tid] = min(1.0, sum(W_TYPE.get(e.event_name, 0.1) for e in tev))
        if not trips:
            return Profile(trips={}, u_long=np.zeros(E.shape[1], dtype=np.float32), active_trip=None, n_events=0)
        u_long = sum(2 ** (-t.age_days / H_LONG_DAYS) * (conf[t.trip_id] if confidence else 1.0) * t.vec
                     for t in trips.values())
        u_long = u_long / (np.linalg.norm(u_long) or 1)
        active = [t for t in trips.values() if trip_is_open(t.age_days, t.ends_on, today)]
        active_trip = min(active, key=lambda t: t.age_days) if active else None
        bought = {e.unit for t in trips.values() for e in t.events if e.event_name == "purchase"}
        return Profile(trips=trips, u_long=u_long, active_trip=active_trip,
                       n_events=sum(len(t.events) for t in trips.values()), bought_units=bought)

    return bp


PROFILES = {
    "P0_prod": {},
    "P1_capFix": {"cap_fix": True},
    "P2_confidence": {"confidence": True},
    "P3_session": {"session": True},
    "P4_all": {"cap_fix": True, "confidence": True, "session": True},
}
