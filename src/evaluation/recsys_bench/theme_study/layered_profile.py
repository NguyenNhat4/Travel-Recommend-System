"""Lớp profile của công thức OPH-L (plan `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` §3.2) — chỉ dùng trong tiến trình đo.

Bọc một `build_profile` nền (production hoặc `profile_variants`) rồi hậu xử lý `Profile` nó trả về, nên mọi công tắc tắt thì
trả **đúng đối tượng** của bản nền (parity V0p/V1p không phụ thuộc phép tính lại nào):

- `booked_first` (bậc O3, sửa I-3): `active_trip` = chuyến mở **có purchase** trẻ nhất; không có thì như production.
- `session_agg`  (bậc O4): khi không có chuyến đã đặt đang mở và có ≥ 2 chuyến mở chỉ-xem/giỏ, gộp chúng thành một chuyến ảo
                 `T_S` (vector suy giảm theo `h_session` × độ tin cậy, điểm đến = mode có trọng số). `|S| = 1` giữ chuyến thật.
- `dormant_hl_mult` (bậc N2): khách `P3_dormant` dựng lại `u_long` với half-life `H_LONG_DAYS × mult`.

Ngoài profile, hàm ghi vào `state` (một ô / request, engine chạy tuần tự): `ctx` của cấu hình (booked / session / none / cold),
`ctx0` và `segment` cố định cho mọi cấu hình (để phân tầng ghép cặp), `events` đã resolve (cho `origin.infer_origin` và cart).

Segment theo nhãn DDL (`db/vota_schema.sql:186`, AGENTS.md §6.4), suy từ event as-of, không đọc `cdp.profiles`:
P4_no_history (không chuyến) · P2_first_time (không purchase) · P3_dormant (có purchase, không chuyến mở, chuyến trẻ nhất
> `dormant_days`, chốt 365 ngày 09/10) · P1_frequent (còn lại).
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from src.backend.app.domain.recommendation.profile import H_LONG_DAYS, Profile, Trip, trip_is_open

#: Ngưỡng dormant đã chốt 09/10/2026 (đề xuất `docs/prd/update/2026-10-09-persona-trang-thai-cold-start-va-phong-cach-du-lich.md`).
DORMANT_DAYS = 365.0
SESSION_TRIP_ID = "_session_"


def trip_confidence(t: Trip) -> float:
    """Độ tin cậy P2 của chuyến (`Trip.confidence` của production từ PR-A 09/10; = `min(1, Σ W_TYPE)` trên event sau cap)."""
    return t.confidence


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n else v


def segment_of(p: Profile, ctx: str, dormant_days: float = DORMANT_DAYS) -> str:
    if not p.trips:
        return "P4_no_history"
    if not any(t.purchased_taxonomies for t in p.trips.values()):
        return "P2_first_time"
    if ctx == "none" and min(t.age_days for t in p.trips.values()) > dormant_days:
        return "P3_dormant"
    return "P1_frequent"


def _ctx(active: Trip | None, has_trips: bool) -> str:
    if not has_trips:
        return "cold"
    if active is None:
        return "none"
    return "booked" if active.purchased_taxonomies else "session"


def session_trip(trips: list[Trip], h_session: float, confidence: bool) -> Trip:
    """Chuyến ảo `T_S` từ các chuyến mở chỉ-xem / giỏ (plan §3.2)."""
    w = {t.trip_id: 2 ** (-t.age_days / h_session) * (trip_confidence(t) if confidence else 1.0) for t in trips}
    vec = _unit(sum(w[t.trip_id] * t.vec for t in trips).astype(np.float32))
    dest_w: dict[str, float] = defaultdict(float)
    for t in trips:
        dest_w[t.destination] += w[t.trip_id]
    youngest = min(trips, key=lambda t: t.age_days)
    # mode có trọng số; hoà thì lấy điểm đến của chuyến trẻ nhất (ổn định, không phụ thuộc thứ tự dict)
    top = max(dest_w.values())
    dest = youngest.destination if dest_w[youngest.destination] == top else sorted(d for d, v in dest_w.items() if v == top)[0]
    ends = [t.ends_on for t in trips if t.ends_on is not None]
    events = sorted((e for t in trips for e in t.events), key=lambda e: -e.days_ago)
    conf = min(1.0, sum(t.confidence for t in trips))
    return Trip(trip_id=SESSION_TRIP_ID, events=events, vec=vec, age_days=youngest.age_days, purchased_taxonomies=set(),
                destination=dest, ends_on=max(ends) if ends else None, ended=False, confidence=conf)


def make_layered_build_profile(base, state: dict, *, booked_first: bool = False, session_agg: bool = False,
                               h_session: float = 7.0, dormant_hl_mult: float = 1.0, dormant_days: float = DORMANT_DAYS,
                               confidence: bool = True):
    """`base`: build_profile nền. `confidence`: bản nền có nhân độ tin cậy vào `u_long` không (để N2 dựng lại cho khớp)."""

    def bp(events, E, taxonomy, destination, today=None) -> Profile:
        p = base(events, E, taxonomy, destination, today)
        state["events"] = list(events)
        state["ctx0"] = _ctx(p.active_trip, bool(p.trips))
        state["segment"] = segment_of(p, state["ctx0"], DORMANT_DAYS)
        if not p.trips:
            state["ctx"], state["profile"] = "cold", p
            return p
        open_ = [t for t in p.trips.values() if trip_is_open(t.age_days, t.ends_on, today)]
        booked = [t for t in open_ if t.purchased_taxonomies]
        browse = [t for t in open_ if not t.purchased_taxonomies]
        active = p.active_trip
        if (booked_first or session_agg) and booked:
            active = min(booked, key=lambda t: t.age_days)
        elif session_agg and len(browse) >= 2:
            active = session_trip(browse, h_session, confidence)
        ctx = _ctx(active, True)
        u_long = p.u_long
        seg_cfg = segment_of(p, ctx, dormant_days)
        if dormant_hl_mult != 1.0 and seg_cfg == "P3_dormant":
            h = H_LONG_DAYS * dormant_hl_mult
            u_long = _unit(sum(2 ** (-t.age_days / h) * (trip_confidence(t) if confidence else 1.0) * t.vec
                               for t in p.trips.values()).astype(np.float32))
        state["ctx"], state["segment_cfg"] = ctx, seg_cfg
        if active is p.active_trip and u_long is p.u_long:
            state["profile"] = p
            return p
        out = Profile(trips=p.trips, u_long=u_long, active_trip=active, n_events=p.n_events, bought_units=p.bought_units)
        state["profile"] = out
        return out

    return bp
