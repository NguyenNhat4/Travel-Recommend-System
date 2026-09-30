"""Hai cách chia train/test cho harness, đều không để engine thấy dữ liệu từ mốc của khách trở đi.

- **Leave-last-booking-out (`llbo`)** — handbook §11–§12: khách có ≥ `min_purchases` purchase hợp lệ, giấu purchase
  cuối, `as_of` của khách = thời điểm purchase đó, train = event của khách có `timestamp < as_of` (event cùng thời
  điểm cũng bị loại). Khách chỉ 1 purchase không vào test. Phần chọn target và khoá tie-break port từ
  `origin/khoa/recsys-research@6b9b0af` (`src/evaluation/benchmark.py`: `_time_key`, `leave_one_purchase_out`).
- **Temporal (`temporal`)** — mốc `T` chung: train = mọi event `< T`; khách test = có ≥ 1 event train và ≥ 1 purchase
  hợp lệ `>= T`; target = purchase sớm nhất `>= T`; `as_of = T` cho mọi khách.

Target luôn quy về **search unit cha** (phòng → khách sạn, chuyến → tuyến) vì engine chỉ trả search unit.
Đầu vào là event đã qua `events.filter_events`.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from src.backend.app.application.ports import UnitIndex
from src.backend.app.domain.recommendation.profile import ACTIVE_TRIP_MAX_AGE_DAYS, MAX_REPEAT_PER_TRIP

from .events import PERSONA_IDS, parse_ts


@dataclass
class Split:
    kind: str
    targets: dict[str, str]                       # khách → productId search unit bị giấu
    target_events: dict[str, dict]                # khách → purchase gốc bị giấu
    as_of_by_user: dict[str, datetime]
    train_by_user: dict[str, list[dict]]          # chỉ khách test
    train_purchases: list[dict]                   # purchase hợp lệ của mọi khách — nguồn popularity (cắt theo as_of khi dùng)
    meta: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return {"kind": self.kind, **self.meta,
                "targets": {u: {"target": self.targets[u], "asOf": self.as_of_by_user[u].isoformat(),
                                "trainEvents": len(self.train_by_user[u])} for u in sorted(self.targets)}}


def _order_key(event: dict, position: int) -> tuple[datetime, str, int]:
    """Khoá tất định: thời điểm, rồi productId, rồi vị trí đầu vào (port `_time_key` của khoa)."""
    return parse_ts(event["timestamp"]), str(event.get("productId") or ""), position


def _by_user(events: list[dict]) -> dict[str, list[tuple[int, dict]]]:
    out: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for position, e in enumerate(events):
        if e.get("cdpUserId"):
            out[str(e["cdpUserId"])].append((position, e))
    return out


def _is_valid_purchase(e: dict, index: UnitIndex) -> bool:
    return e.get("eventName") == "purchase" and bool(e.get("productId")) and index.resolve(str(e["productId"])) is not None


def _unit_id(index: UnitIndex, product_id: str) -> str:
    return index.units[index.resolve(product_id)].product_id


def excluded_taxonomies(train: list[dict], index: UnitIndex, as_of: datetime) -> set[str]:
    """Mô phỏng category exclusion của engine: taxonomy đã mua trong trip đang mở (trip trẻ nhất, tuổi ≤ 60 ngày).

    Trip = `eventGroupId`, thiếu thì `_solo_<productId>` như `use_cases.py`; mỗi (trip, unit) chỉ giữ
    `MAX_REPEAT_PER_TRIP` event cũ nhất như `build_profile`. Không mô phỏng việc engine bỏ sản phẩm chưa có vector.
    Dùng để giải thích recall thấp "đúng thiết kế" khi target cùng loại với món đã mua trong chuyến đang mở.
    """
    rows = []
    for e in train:
        unit = index.resolve(str(e.get("productId") or ""))
        if unit is not None:
            rows.append(((as_of - parse_ts(e["timestamp"])).total_seconds() / 86400, e, unit))
    trips: dict[str, list[tuple[float, dict, int]]] = defaultdict(list)
    seen: Counter = Counter()
    for days_ago, e, unit in sorted(rows, key=lambda r: -r[0]):   # cũ trước, như build_profile
        trip = e.get("eventGroupId") or f"_solo_{e['productId']}"
        seen[(trip, unit)] += 1
        if seen[(trip, unit)] <= MAX_REPEAT_PER_TRIP:
            trips[trip].append((days_ago, e, unit))
    ages = {tid: min(d for d, _, _ in rows) for tid, rows in trips.items()}
    open_trips = [tid for tid, age in ages.items() if age <= ACTIVE_TRIP_MAX_AGE_DAYS]
    if not open_trips:
        return set()
    active = min(open_trips, key=lambda tid: ages[tid])
    return {str(index.taxonomy[u]) for _, e, u in trips[active] if e.get("eventName") == "purchase"}


def _meta_for_targets(split_targets: dict[str, str], train_by_user: dict[str, list[dict]],
                      as_of_by_user: dict[str, datetime], index: UnitIndex) -> dict:
    repeat = excluded = 0
    for user, target in split_targets.items():
        train = train_by_user[user]
        bought = {_unit_id(index, str(e["productId"])) for e in train if _is_valid_purchase(e, index)}
        repeat += target in bought
        excluded += str(index.taxonomy[index.idx[target]]) in excluded_taxonomies(train, index, as_of_by_user[user])
    return {
        "usersTest": len(split_targets),
        "personaInTest": sorted(set(split_targets) & PERSONA_IDS),
        "trainEventsOfTestUsers": sum(len(v) for v in train_by_user.values()),
        # target đã mua trước đó → engine loại bought_units nên không thể trúng
        "repeatTarget": repeat,
        # target cùng taxonomy với món đã mua trong trip đang mở → category exclusion loại
        "targetVerticalExcluded": excluded,
        "targetTaxonomy": dict(sorted(Counter(str(index.taxonomy[index.idx[t]]) for t in split_targets.values()).items())),
    }


def leave_last_booking_out(events: list[dict], index: UnitIndex, *, min_purchases: int = 2,
                           min_trips: int = 1) -> Split:
    """`min_trips=2` chọn khách như baseline trong seed (≥ 2 `eventGroupId` khác nhau)."""
    targets, target_events, as_of_by_user, train_by_user = {}, {}, {}, {}
    same_instant_dropped = 0
    for user, rows in _by_user(events).items():
        purchases = [(pos, e) for pos, e in rows if _is_valid_purchase(e, index)]
        if len(purchases) < min_purchases:
            continue
        if len({e.get("eventGroupId") for _, e in purchases if e.get("eventGroupId")}) < min_trips:
            continue
        position, target = max(purchases, key=lambda pe: _order_key(pe[1], pe[0]))
        as_of = parse_ts(target["timestamp"])
        train = [e for _, e in rows if parse_ts(e["timestamp"]) < as_of]
        same_instant_dropped += sum(1 for pos, e in rows if pos != position and parse_ts(e["timestamp"]) == as_of)
        targets[user] = _unit_id(index, str(target["productId"]))
        target_events[user], as_of_by_user[user], train_by_user[user] = target, as_of, train
    train_purchases = [e for e in events if _is_valid_purchase(e, index)]
    meta = {"minPurchases": min_purchases, "minTrips": min_trips, "usersTotal": len(_by_user(events)),
            "sameInstantDropped": same_instant_dropped,
            **_meta_for_targets(targets, train_by_user, as_of_by_user, index)}
    return Split("llbo", targets, target_events, as_of_by_user, train_by_user, train_purchases, meta)


def default_cutoff(events: list[dict], index: UnitIndex, quantile: float = 0.8) -> datetime:
    """Mốc T mặc định: phân vị `quantile` của thời điểm các purchase hợp lệ."""
    stamps = sorted(parse_ts(e["timestamp"]) for e in events if _is_valid_purchase(e, index))
    if not stamps:
        raise ValueError("không có purchase hợp lệ để chọn mốc T")
    return stamps[min(len(stamps) - 1, int(quantile * (len(stamps) - 1)))]


def temporal_split(events: list[dict], index: UnitIndex, *, cutoff: datetime | None = None,
                   quantile: float = 0.8) -> Split:
    T = cutoff or default_cutoff(events, index, quantile)
    targets, target_events, as_of_by_user, train_by_user = {}, {}, {}, {}
    cold = test_purchases = 0
    for user, rows in _by_user(events).items():
        train = [e for _, e in rows if parse_ts(e["timestamp"]) < T]
        later = sorted(((pos, e) for pos, e in rows if _is_valid_purchase(e, index) and parse_ts(e["timestamp"]) >= T),
                       key=lambda pe: _order_key(pe[1], pe[0]))
        if not later:
            continue
        if not train:
            cold += 1
            continue
        test_purchases += len(later)
        _, target = later[0]
        targets[user] = _unit_id(index, str(target["productId"]))
        target_events[user], as_of_by_user[user], train_by_user[user] = target, T, train
    train_purchases = [e for e in events if _is_valid_purchase(e, index)]
    meta = {"T": T.isoformat(), "quantile": None if cutoff else quantile, "usersTotal": len(_by_user(events)),
            "coldUsersExcluded": cold, "testPurchasesTotal": test_purchases,
            **_meta_for_targets(targets, train_by_user, as_of_by_user, index)}
    return Split("temporal", targets, target_events, as_of_by_user, train_by_user, train_purchases, meta)
