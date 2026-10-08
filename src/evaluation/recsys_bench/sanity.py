"""B1 (01/10) — sanity của dữ liệu seed trước khi tin số đo (lịch 10 ngày Day 2 B, plan Day 3 Phase 2).

Mỗi kiểm tra là một `Check` như `search_bench/sanity.py`: `ok=None` = chỉ báo (không cổng). Kiểm tra **cứng** (hỏng → mọi số
sau đó đáng ngờ, `sanity` thoát mã 1):
- `lifecycle_mix` — `cdp.profiles.lifecycle_stage` theo STAGE_MIX 25/45/20/10 ± STAGE_TOLERANCE (hằng của seed);
- `lifecycle_recomputed` — stage và `days_since_last_booking` tính lại từ **mọi** purchase thô (kể cả orphan, như seed) theo
  ngày lịch VN và `as_of` suy ra từ DB phải trùng cột seed đã ghi (lệch cho phép 0);
- `trips_multi_vertical` — tỷ lệ chuyến (purchase cùng `eventGroupId`) có ≥ 2 taxonomy ≈ MULTI_VERTICAL_RATE ± 0,05;
- `one_destination_per_trip` — chuyến có purchase ở ≥ 2 điểm đến ≤ 1 % (nhiễu cố ý của seed);
- `messy_edges` — purchase orphan ≈ 2,0 % và thiếu `eventGroupId` ≈ 3,0 %, ± 0,5 điểm (seed_report).
Chỉ báo: `popularity` (top-10 % sản phẩm chiếm bao nhiêu % purchase — kỳ vọng ≈ 41 % trên seed 21/09; Gini theo sản phẩm
và theo search unit; độ dốc Zipf), `golf_share`, `split_users` (số khách test của bản đóng băng).
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from src.backend.app.application.ports import UnitIndex

from .events import parse_ts
from .metrics import gini   # chuyển sang metrics.py 01/10 (exposure_gini của score); giữ tên ở đây cho sanity / test cũ

VN = ZoneInfo("Asia/Ho_Chi_Minh")
STAGES = ("new", "active", "dormant", "churned")
EXPECTED_ORPHAN, EXPECTED_MISSING_GID, EDGE_TOL = 0.020, 0.030, 0.005
EXPECTED_TOP10_SHARE = 0.41
MULTI_VERTICAL_TOL, ONE_DESTINATION_MAX = 0.05, 0.01


def seed_constants() -> dict:
    """STAGE_MIX, STAGE_TOLERANCE, MULTI_VERTICAL_RATE từ `data_collection/seed/config.py` (nguồn duy nhất của các tỷ lệ)."""
    from src.data_collection.seed import config as C
    return {"STAGE_MIX": dict(C.STAGE_MIX), "STAGE_TOLERANCE": float(C.STAGE_TOLERANCE),
            "MULTI_VERTICAL_RATE": float(C.MULTI_VERTICAL_RATE)}


@dataclass
class Check:
    name: str
    ok: bool | None            # None = chỉ báo
    detail: str
    values: dict | None = None


def local_day(ts: str | datetime) -> date:
    return parse_ts(ts).astimezone(VN).date()


def lifecycle_seed_rule(user_events: list[dict], as_of_day: date) -> tuple[str, int | None]:
    """Đúng `seed_histories.lifecycle`: 0 purchase → new; ngày lịch VN kể từ purchase cuối: ≤ 180 active, ≤ 365 dormant."""
    buys = [e for e in user_events if e.get("eventName") == "purchase"]
    if not buys:
        return "new", None
    days = (as_of_day - max(local_day(e["timestamp"]) for e in buys)).days
    return ("active" if days <= 180 else "dormant" if days <= 365 else "churned"), days


def lifecycle_mix(profiles: list[dict], consts: dict) -> Check:
    n = len(profiles)
    shares = {s: sum(1 for p in profiles if p.get("lifecycleStage") == s) / n if n else 0.0 for s in STAGES}
    mix, tol = consts["STAGE_MIX"], consts["STAGE_TOLERANCE"]
    drift = {s: round(shares[s] - mix[s], 4) for s in STAGES}
    ok = n > 0 and all(abs(d) <= tol for d in drift.values())
    return Check("lifecycle_mix", ok, " · ".join(f"{s} {shares[s]:.1%} (đích {mix[s]:.0%})" for s in STAGES) + f" · n {n} · dung sai ±{tol:.0%}",
                 {"shares": shares, "drift": drift, "n": n})


def lifecycle_recomputed(profiles: list[dict], events: list[dict], as_of: datetime, index: UnitIndex | None = None) -> Check:
    """Tính lại từ **mọi** purchase thô như seed: `lifecycleStage`, `daysSinceLastBooking`, `lifetimeOrderCount` (số
    `eventGroupId` khác null có purchase), `purchasedVerticals` (taxonomy đã mua, sắp xếp) và — khi có `index` —
    `lastDestination` (điểm đến của purchase gần nhất còn trong catalog). Mọi cột phải trùng cột seed đã ghi."""
    by_user: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_user[str(e.get("cdpUserId"))].append(e)
    as_of_day = as_of.astimezone(VN).date()
    bad = Counter()
    examples = []
    for p in profiles:
        evs = by_user.get(p["cdpUserId"], [])
        stage, days = lifecycle_seed_rule(evs, as_of_day)
        buys = sorted((e for e in evs if e.get("eventName") == "purchase"), key=lambda e: parse_ts(e["timestamp"]), reverse=True)
        want = {"lifecycleStage": stage, "daysSinceLastBooking": days,
                "lifetimeOrderCount": len({e.get("eventGroupId") for e in buys if e.get("eventGroupId")}),
                "purchasedVerticals": sorted({str(e.get("taxonomy")) for e in buys if e.get("taxonomy")})}
        if index is not None:
            want["lastDestination"] = next((str(index.destination[index.resolve(str(e["productId"]))]) for e in buys
                                            if e.get("productId") and index.resolve(str(e["productId"])) is not None), None)
        for col, value in want.items():
            got = p.get(col)
            if col == "purchasedVerticals":
                got = sorted(got or [])
            if got != value:
                bad[col] += 1
                if len(examples) < 3:
                    examples.append(f"{p['cdpUserId']} {col}: seed {got!r} / tính lại {value!r}")
    ok = bool(profiles) and not bad
    return Check("lifecycle_recomputed", ok,
                 f"lệch so với cột seed: " + (", ".join(f"{c} {n}" for c, n in sorted(bad.items())) if bad else "0") +
                 f" trên {len(profiles)} profile · as_of (VN) {as_of_day.isoformat()}" + (f" · ví dụ {examples}" if examples else ""),
                 {"bad": dict(bad), "badStage": bad.get("lifecycleStage", 0), "badDays": bad.get("daysSinceLastBooking", 0),
                  "asOfDay": as_of_day.isoformat()})


def profiles_cover_events(profiles: list[dict], events: list[dict]) -> Check:
    """Mọi khách có event phải có profile (FK `cdp.events.cdp_user_id → cdp.profiles`); báo số profile không có event."""
    users_p = {p.get("cdpUserId") for p in profiles}
    users_e = {str(e.get("cdpUserId")) for e in events if e.get("cdpUserId")}
    missing = sorted(users_e - users_p)
    return Check("profiles_cover_events", bool(profiles) and not missing,
                 f"{len(profiles)} profile · {len(users_e)} khách có event · thiếu profile {len(missing)}" + (f" {missing[:3]}" if missing else "")
                 + f" · profile không có event {len(users_p - users_e)}",
                 {"profiles": len(profiles), "usersWithEvents": len(users_e), "missing": missing[:20], "noEvents": len(users_p - users_e)})


def _trips(events: list[dict]) -> dict[str, list[dict]]:
    trips: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        if e.get("eventName") == "purchase" and e.get("eventGroupId"):
            trips[str(e["eventGroupId"])].append(e)
    return trips


def trips_multi_vertical(events: list[dict], consts: dict) -> Check:
    trips = _trips(events)
    multi = sum(1 for evs in trips.values() if len({e.get("taxonomy") for e in evs if e.get("taxonomy")}) >= 2)
    share = multi / len(trips) if trips else 0.0
    want = consts["MULTI_VERTICAL_RATE"]
    return Check("trips_multi_vertical", bool(trips) and abs(share - want) <= MULTI_VERTICAL_TOL,
                 f"{share:.1%} chuyến có ≥ 2 taxonomy ({multi}/{len(trips)}; đích {want:.0%} ± {MULTI_VERTICAL_TOL:.0%})",
                 {"share": share, "trips": len(trips), "multi": multi})


def one_destination_per_trip(events: list[dict], index: UnitIndex) -> Check:
    trips = _trips(events)
    multi_dest = n = 0
    for evs in trips.values():
        dests = set()
        for e in evs:
            u = index.resolve(str(e.get("productId") or ""))
            if u is not None:
                dests.add(str(index.destination[u]))
        if dests:
            n += 1
            multi_dest += len(dests) > 1
    share = multi_dest / n if n else 0.0
    return Check("one_destination_per_trip", n > 0 and share <= ONE_DESTINATION_MAX,
                 f"{share:.2%} chuyến có purchase ở ≥ 2 điểm đến ({multi_dest}/{n}; tối đa {ONE_DESTINATION_MAX:.0%})",
                 {"share": share, "trips": n, "multiDestination": multi_dest})


def messy_edges(events: list[dict], index: UnitIndex) -> Check:
    buys = [e for e in events if e.get("eventName") == "purchase"]
    orphan = sum(1 for e in buys if index.resolve(str(e.get("productId") or "")) is None)
    no_gid = sum(1 for e in buys if not e.get("eventGroupId"))
    n = len(buys)
    po, pg = (orphan / n if n else 0.0), (no_gid / n if n else 0.0)
    ok = n > 0 and abs(po - EXPECTED_ORPHAN) <= EDGE_TOL and abs(pg - EXPECTED_MISSING_GID) <= EDGE_TOL
    return Check("messy_edges", ok, f"purchase {n}: orphan {orphan} ({po:.1%}, đích {EXPECTED_ORPHAN:.1%}) · thiếu eventGroupId {no_gid} "
                 f"({pg:.1%}, đích {EXPECTED_MISSING_GID:.1%}) · ± {EDGE_TOL:.1%}",
                 {"purchases": n, "orphan": orphan, "missingGid": no_gid, "orphanShare": po, "missingGidShare": pg})


def zipf_slope(counts: list[int]) -> float | None:
    """Độ dốc hồi quy log(count) ~ log(rank) trên các sản phẩm có ≥ 1 purchase (chỉ báo; seed dùng ZIPF_S 0,8)."""
    c = sorted((v for v in counts if v > 0), reverse=True)
    if len(c) < 10:
        return None
    x, y = np.log(np.arange(1, len(c) + 1)), np.log(np.asarray(c, dtype=float))
    return float(np.polyfit(x, y, 1)[0])


def popularity(events: list[dict], index: UnitIndex) -> Check:
    buys = [str(e.get("productId")) for e in events if e.get("eventName") == "purchase" and e.get("productId")]
    by_product = Counter(buys)
    units: Counter = Counter()
    for pid, c in by_product.items():
        u = index.resolve(pid)
        if u is not None:
            units[index.units[u].product_id] += c
    ranked = sorted(by_product.values(), reverse=True)
    top = max(1, math.ceil(len(ranked) * 0.10))
    share = sum(ranked[:top]) / len(buys) if buys else 0.0
    return Check("popularity", None,
                 f"top-10 % sản phẩm ({top}/{len(by_product)} có purchase) chiếm {share:.1%} purchase (kỳ vọng ≈ {EXPECTED_TOP10_SHARE:.0%}) · "
                 f"Gini sản phẩm {gini(list(by_product.values())):.3f} · Gini search unit {gini(list(units.values())):.3f} · "
                 f"Zipf slope {zipf_slope(list(by_product.values()))}",
                 {"top10Share": share, "productsWithPurchase": len(by_product), "giniProduct": gini(list(by_product.values())),
                  "giniUnit": gini(list(units.values())), "zipfSlope": zipf_slope(list(by_product.values()))})


def golf_share(events: list[dict]) -> Check:
    buys = [e for e in events if e.get("eventName") == "purchase"]
    tax = Counter(str(e.get("taxonomy")) for e in buys)
    n = len(buys)
    return Check("golf_share", None, " · ".join(f"{t} {c / n:.1%}" for t, c in tax.most_common()) if n else "không có purchase",
                 {t: c / n for t, c in tax.items()} if n else {})


def split_users(frozen_dir: Path) -> Check:
    found = {}
    for p in sorted(frozen_dir.glob("split-*.json")):
        try:
            found[p.name] = len(json.loads(p.read_text(encoding="utf-8"))["canonical"]["targets"])
        except (OSError, ValueError, KeyError, TypeError):
            found[p.name] = None
    return Check("split_users", None, " · ".join(f"{k}: {v} khách" for k, v in found.items()) or "chưa có bản đóng băng", found)


def run_all(profiles: list[dict], events: list[dict], index: UnitIndex, as_of: datetime, frozen_dir: Path) -> list[Check]:
    consts = seed_constants()
    return [profiles_cover_events(profiles, events), lifecycle_mix(profiles, consts), lifecycle_recomputed(profiles, events, as_of, index),
            trips_multi_vertical(events, consts), one_destination_per_trip(events, index), messy_edges(events, index),
            popularity(events, index), golf_share(events), split_users(frozen_dir)]


def summary(checks: list[Check]) -> dict:
    hard = [c for c in checks if c.ok is not None]
    return {"pass": all(c.ok for c in hard), "hardFailed": [c.name for c in hard if not c.ok],
            "checks": [asdict(c) for c in checks]}


def markdown(checks: list[Check]) -> str:
    lines = ["| Kiểm tra | Kết quả | Chi tiết |", "|---|---|---|"]
    for c in checks:
        status = "chỉ báo" if c.ok is None else ("PASS" if c.ok else "**FAIL**")
        lines.append(f"| `{c.name}` | {status} | {c.detail} |")
    return "\n".join(lines)
