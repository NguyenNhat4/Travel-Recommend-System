"""User profile từ event + MMR + phân rã because[] — EMBEDDING_AND_ENGINES.md §6.2–6.4.
Thuần numpy. Event đã được resolve sang unit index (phòng/chuyến → cha) bởi tầng application."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import numpy as np

W_TYPE = {"purchase": 1.0, "add_to_cart": 0.5, "product_view": 0.2, "search": 0.1}
H_SHORT_DAYS, H_LONG_DAYS = 30.0, 365.0
#: Tham số N của FR-REC-02 (chốt 01/10): trip KHÔNG có `usingDate` (chỉ view / search) còn mở khi event gần nhất ≤ N ngày.
#: 60 → 14 đo trên temporal đóng băng (docs/spec/bench/recsys-offline-eval.md §4.14 v5: Recall@20 0,196 → 0,216, LLBO không
#: đổi; grid §4.13 với luật tuổi đơn thuần N = 14 cho 0,225); trip có `usingDate` không dùng N (xem `trip_is_open`).
ACTIVE_TRIP_MAX_AGE_DAYS = 14
DORMANT_AFTER_DAYS = 180
MAX_REPEAT_PER_TRIP = 3
#: Cap lặp chỉ đếm event yếu (view / search); purchase và add_to_cart luôn vào vector chuyến (P1 phần còn lại, 09/10/2026:
#: `docs/spec/bench/recsys-bam-so-thich-tong-hop.md` §3.D — không đổi số đo, đúng nghiệp vụ).
CAP_EXEMPT_EVENTS = ("purchase", "add_to_cart")
#: Chốt 2026-10-07 (docs/prd/update-archive/2026-10-06-recsys-trong-so-ngan-han-pho-bien.md): 0,6/0,25/0,15 → 0,7/0,15/0,15.
W_SHORT, W_POP, W_LONG = 0.7, 0.15, 0.15
MMR_LAMBDA, MAX_PER_VERTICAL = 0.7, 2
#: Ô khám phá khi có chuyến mở (FR-REC-02, chốt 09/10/2026, đề xuất `2026-10-08-recsys-o-kham-pha-khi-co-chuyen-mo`): ô còn trống
#: sau khi hết món tại X được lấp bằng món ở điểm đến khác, xếp theo cos(u_long, v), mỗi điểm đến 1 món, chỉ ba loại này.
EXPLORE_TAXONOMIES = ("hotel", "attraction", "combo")
EXPLORE_MAX_PER_DESTINATION = 1
#: Phiên bản luật của engine (không phải tham số): đổi khi hành vi đổi mà không có hằng nào đổi, để bench tách hai bộ số.
#: Từ 01/10/2026 (nhãn giữ "2026-10-02" để khớp configHash của bench): trip đang mở = chưa kết thúc theo `usingDate`
#: (FR-REC-02, spec §4.4–4.5); trước đó chỉ theo tuổi event.
#: 2026-10-09 (PR-A): độ tin cậy chuyến trong u_long (P2), purchase / cart không bị cap lặp, loại trừ combo ↔ thành phần đã
#: mua, ô khám phá khi có chuyến mở (hai luật sau ở tầng application nhưng đổi list nên đổi nhãn).
ENGINE_RULES_VERSION = "2026-10-09-p2-combo-explore"


@dataclass
class ResolvedEvent:
    unit: int                 # index trong ma trận E
    event_name: str
    days_ago: float
    trip_id: str
    product_id: str           # id gốc trong event (có thể là phòng/chuyến)
    using_date: date | None = None   # ngày sử dụng (purchase / add_to_cart); None với view / search


@dataclass
class Trip:
    trip_id: str
    events: list[ResolvedEvent]
    vec: np.ndarray
    age_days: float
    purchased_taxonomies: set[str]
    destination: str
    ends_on: date | None = None      # max(usingDate) của trip; None khi không event nào có ngày sử dụng
    ended: bool = False              # chuyến đã diễn ra xong (spec §4.3 tripFactor): ends_on < hôm nay
    #: Độ tin cậy của chuyến trong u_long (P2, 09/10/2026): min(1, Σ W_TYPE của event sau cap) — một lượt xem lẻ 0,2, một
    #: lần mua 1,0; chuyến không bị chuẩn hoá thành nặng bằng nhau nữa. Vector chuyến mở (`vec`) không nhân hệ số này.
    confidence: float = 1.0


#: Múi giờ của `usingDate` (ngày địa phương Việt Nam, như seed và `domain/booking`); không phải tham số xếp hạng
#: (`engine_config` của bench chỉ chụp hằng số/chuỗi nên không vào configHash).
CATALOG_TZ = timezone(timedelta(hours=7))


def local_today(now: datetime) -> date:
    """Ngày "hôm nay" để xét trip kết thúc: `now` đổi sang giờ Việt Nam rồi lấy ngày, khớp `usingDate` là ngày địa phương
    (lấy ngày UTC thì từ 00:00 tới 06:59 giờ VN chuyến hôm qua vẫn bị coi là mở). `now` thiếu múi giờ → coi là UTC."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(CATALOG_TZ).date()


def parse_using_date(value) -> date | None:
    """`usingDate` của event CDP (ISO date hoặc datetime) → `date`; thiếu / hỏng → None (không chặn request).
    Dùng chung cho tầng application và harness bench để hai bên đọc ngày giống hệt nhau."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def trip_is_open(age_days: float, ends_on: date | None, today: date | None) -> bool:
    """Trip đang mở (FR-REC-02, spec §4.4 bổ sung 01/10/2026): có `usingDate` → mở khi `max(usingDate) >= hôm nay`
    (chuyến chưa tới ngày sử dụng cuối, kể cả mua từ lâu); không có → mở khi event gần nhất cách ≤ ACTIVE_TRIP_MAX_AGE_DAYS.
    `usingDate` của event CDP là ngày bắt đầu sử dụng (check-in / ngày bay); CDP không có ngày trả phòng nên kỳ nghỉ nhiều
    đêm được coi là xong từ ngày sau check-in — muốn giữ trip mở suốt kỳ nghỉ cần thêm số đêm vào event (đề xuất PRD riêng)."""
    if ends_on is not None and today is not None:
        return ends_on >= today
    return age_days <= ACTIVE_TRIP_MAX_AGE_DAYS


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


def build_profile(events: list[ResolvedEvent], E: np.ndarray, taxonomy: np.ndarray, destination: np.ndarray,
                  today: date | None = None) -> Profile:
    """`today`: ngày của `now` để xét trip đã kết thúc theo `usingDate`; None → chỉ theo tuổi event (luật cũ)."""
    by_trip: dict[str, list[ResolvedEvent]] = defaultdict(list)       # sau cap lặp: trọng số vector, n_events, điểm đến
    every: dict[str, list[ResolvedEvent]] = defaultdict(list)         # mọi event: tuổi, ngày kết thúc, món đã mua
    seen: Counter = Counter()
    for e in sorted(events, key=lambda x: -x.days_ago):
        every[e.trip_id].append(e)
        if e.event_name not in CAP_EXEMPT_EVENTS:
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
        # Cap lặp chỉ giới hạn trọng số vector; event bị cap vẫn quyết định tuổi trip, ngày kết thúc và món đã mua
        # (một purchase thứ 4 cùng unit mang usingDate muộn nhất không được làm chuyến "kết thúc sớm").
        all_evs = every[tid]
        ends_on = max((e.using_date for e in all_evs if e.using_date is not None), default=None)
        trips[tid] = Trip(
            trip_id=tid, events=evs, vec=v / n if n else v, age_days=min(e.days_ago for e in all_evs),
            purchased_taxonomies={str(taxonomy[e.unit]) for e in all_evs if e.event_name == "purchase"},
            destination=str(Counter(destination[e.unit] for e in evs).most_common(1)[0][0]),
            ends_on=ends_on, ended=ends_on is not None and today is not None and ends_on < today,
            confidence=min(1.0, sum(W_TYPE.get(e.event_name, 0.1) for e in evs)),
        )

    if not trips:
        return Profile(trips={}, u_long=np.zeros(E.shape[1], dtype=np.float32), active_trip=None, n_events=0)

    u_long = sum(2 ** (-t.age_days / H_LONG_DAYS) * t.confidence * t.vec for t in trips.values())
    u_long = u_long / (np.linalg.norm(u_long) or 1)
    active = [t for t in trips.values() if trip_is_open(t.age_days, t.ends_on, today)]
    active_trip = min(active, key=lambda t: t.age_days) if active else None
    bought = {e.unit for evs in every.values() for e in evs if e.event_name == "purchase"}
    return Profile(trips=trips, u_long=u_long, active_trip=active_trip,
                   n_events=sum(len(t.events) for t in trips.values()), bought_units=bought)


def score_candidates(profile: Profile, E: np.ndarray, pop: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Trả (score, u) với u là vector dùng để giải thích."""
    u = profile.active_trip.vec if profile.active_trip is not None else profile.u_long
    s_short, s_long = E @ u, E @ profile.u_long
    return W_SHORT * s_short + W_POP * pop + W_LONG * s_long, u


def mmr_select(score: np.ndarray, E: np.ndarray, candidates: list[int], taxonomy: np.ndarray, k: int,
               max_per_vertical: int | None = MAX_PER_VERTICAL) -> list[int]:
    """MMR (λ = MMR_LAMBDA) + giới hạn cứng `max_per_vertical` món mỗi taxonomy; `None` = không giới hạn (chỉ cho đánh giá
    offline với k = 20 — 5 taxonomy × 2 không thể đủ 20; production giữ MAX_PER_VERTICAL)."""
    chosen: list[int] = []
    per_vertical: Counter = Counter()
    cand = list(candidates)
    while cand and len(chosen) < k:
        best, best_val = None, -1e9
        for i in cand:
            if max_per_vertical is not None and per_vertical[str(taxonomy[i])] >= max_per_vertical:
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


def explain(profile: Profile, item: int, E: np.ndarray, min_share: float = 0.15, top: int = 3,
            long_term: bool = False) -> list[dict]:
    """because[] = phân rã tuyến tính của u·v_item theo từng event. `long_term=True`: phân rã theo u_long dù đang có chuyến mở
    (món ở ô khám phá được chọn theo u_long nên lý do phải lấy từ mọi chuyến, không chỉ chuyến mở)."""
    use_long = long_term or profile.active_trip is None
    src = list(profile.trips.values()) if use_long else [profile.active_trip]
    contribs = []
    Z = 0.0
    for t in src:
        wt = 2 ** (-t.age_days / H_LONG_DAYS) * t.confidence if use_long else 1.0
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
