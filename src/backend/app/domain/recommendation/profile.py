"""User profile từ event + MMR + phân rã because[] — EMBEDDING_AND_ENGINES.md §6.2–6.4.
Thuần numpy. Event đã được resolve sang unit index (phòng/chuyến → cha) bởi tầng application."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

import numpy as np

W_TYPE = {"purchase": 1.0, "add_to_cart": 0.5, "product_view": 0.2, "search": 0.1}
H_SHORT_DAYS, H_LONG_DAYS = 30.0, 365.0
ACTIVE_TRIP_MAX_AGE_DAYS = 60
DORMANT_AFTER_DAYS = 180
MAX_REPEAT_PER_TRIP = 3
W_SHORT, W_POP, W_LONG = 0.6, 0.25, 0.15
MMR_LAMBDA, MAX_PER_VERTICAL = 0.7, 2


@dataclass
class ResolvedEvent:
    unit: int                 # index trong ma trận E
    event_name: str
    days_ago: float
    trip_id: str
    product_id: str           # id gốc trong event (có thể là phòng/chuyến)


@dataclass
class Trip:
    trip_id: str
    events: list[ResolvedEvent]
    vec: np.ndarray
    age_days: float
    purchased_taxonomies: set[str]
    destination: str


@dataclass
class Profile:
    trips: dict[str, Trip]
    u_long: np.ndarray
    active_trip: Trip | None
    n_events: int
    bought_units: set[int] = field(default_factory=set)

    @property
    def strategy(self) -> str:
        if self.active_trip is not None:
            if self.active_trip.purchased_taxonomies:
                return "cross_vertical"
            return "cold_start_content" if self.n_events < 3 else "recent_activity"
        if not self.trips:
            return "popular"
        return "dormant" if min(t.age_days for t in self.trips.values()) > DORMANT_AFTER_DAYS else "long_term"


def build_profile(events: list[ResolvedEvent], E: np.ndarray, taxonomy: np.ndarray, destination: np.ndarray) -> Profile:
    by_trip: dict[str, list[ResolvedEvent]] = defaultdict(list)
    seen: Counter = Counter()
    for e in sorted(events, key=lambda x: -x.days_ago):
        seen[(e.trip_id, e.unit)] += 1
        if seen[(e.trip_id, e.unit)] > MAX_REPEAT_PER_TRIP:
            continue
        by_trip[e.trip_id].append(e)

    trips: dict[str, Trip] = {}
    for tid, evs in by_trip.items():
        v = np.zeros(E.shape[1], dtype=np.float32)
        for e in evs:
            v += W_TYPE.get(e.event_name, 0.1) * 2 ** (-e.days_ago / H_SHORT_DAYS) * E[e.unit]
        n = np.linalg.norm(v)
        trips[tid] = Trip(
            trip_id=tid, events=evs, vec=v / n if n else v, age_days=min(e.days_ago for e in evs),
            purchased_taxonomies={str(taxonomy[e.unit]) for e in evs if e.event_name == "purchase"},
            destination=str(Counter(destination[e.unit] for e in evs).most_common(1)[0][0]),
        )

    if not trips:
        return Profile(trips={}, u_long=np.zeros(E.shape[1], dtype=np.float32), active_trip=None, n_events=0)

    u_long = sum(2 ** (-t.age_days / H_LONG_DAYS) * t.vec for t in trips.values())
    u_long = u_long / (np.linalg.norm(u_long) or 1)
    active = [t for t in trips.values() if t.age_days <= ACTIVE_TRIP_MAX_AGE_DAYS]
    active_trip = min(active, key=lambda t: t.age_days) if active else None
    bought = {e.unit for t in trips.values() for e in t.events if e.event_name == "purchase"}
    return Profile(trips=trips, u_long=u_long, active_trip=active_trip,
                   n_events=sum(len(t.events) for t in trips.values()), bought_units=bought)


def score_candidates(profile: Profile, E: np.ndarray, pop: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Trả (score, u) với u là vector dùng để giải thích."""
    u = profile.active_trip.vec if profile.active_trip is not None else profile.u_long
    s_short, s_long = E @ u, E @ profile.u_long
    return W_SHORT * s_short + W_POP * pop + W_LONG * s_long, u


def mmr_select(score: np.ndarray, E: np.ndarray, candidates: list[int], taxonomy: np.ndarray, k: int) -> list[int]:
    chosen: list[int] = []
    per_vertical: Counter = Counter()
    cand = list(candidates)
    while cand and len(chosen) < k:
        best, best_val = None, -1e9
        for i in cand:
            if per_vertical[str(taxonomy[i])] >= MAX_PER_VERTICAL:
                continue
            div = max((float(E[i] @ E[j]) for j in chosen), default=0.0)
            val = MMR_LAMBDA * float(score[i]) - (1 - MMR_LAMBDA) * div
            if val > best_val:
                best, best_val = i, val
        if best is None:
            break
        chosen.append(best)
        per_vertical[str(taxonomy[best])] += 1
        cand.remove(best)
    return chosen


def explain(profile: Profile, item: int, E: np.ndarray, min_share: float = 0.15, top: int = 3) -> list[dict]:
    """because[] = phân rã tuyến tính của u·v_item theo từng event."""
    src = [profile.active_trip] if profile.active_trip is not None else list(profile.trips.values())
    contribs = []
    Z = 0.0
    for t in src:
        wt = 1.0 if profile.active_trip is not None else 2 ** (-t.age_days / H_LONG_DAYS)
        for e in t.events:
            c = wt * W_TYPE.get(e.event_name, 0.1) * 2 ** (-e.days_ago / H_SHORT_DAYS)
            contribs.append((c, e))
            Z += c
    Z = Z or 1.0
    pos = [(c * float(E[e.unit] @ E[item]) / Z, e) for c, e in contribs]
    pos = [(c, e) for c, e in pos if c > 0]
    tot = sum(c for c, _ in pos) or 1.0
    out = sorted(({"unit": e.unit, "productId": e.product_id, "event": e.event_name, "daysAgo": int(e.days_ago),
                   "contribution": round(c / tot, 2)} for c, e in pos), key=lambda x: -x["contribution"])
    return [b for b in out if b["contribution"] >= min_share][:top]
