"""`because[]` cho scorer registry (Day 5 Phase B; FR-REC-03; spec `recsys-algos-v1.md` §1.2, §2.3, §6.1).

Mọi scorer phân rã điểm theo **event** của khách rồi đi chung một bước `finalize` y hệt `profile.explain` của engine: giữ phần dương,
chia tổng dương, làm tròn 2 chữ số, sắp giảm, lọc ≥ 0,15, lấy tối đa 3. Trọng số event `c_e` lấy từ `profile` bằng **đúng vòng lặp
của `profile.explain`** (float64, cùng thứ tự trip / event) — không dùng `Seeds.weights` float32 — để `star_blend` với a = 1 trùng
bit với `content_profile`:

| scorer | `raw_e(x)` | kind |
|---|---|---|
| content | `profile.explain` của engine (= `c_e·(E_e·E_x)/Z`, Z = Σc) | semantic |
| cooc_trip / itemknn / rp3beta / ease | `c_e·T[e, x]/Z` (T = hàng của scorer; ease giữ âm → bị loại) | cooc |
| star_blend | `a·c_e·(E_e·E_x)/Z + (1−a)·c_e·T[e, x]/Z` (bỏ W_SHORT: hằng dương, triệt tiêu khi chuẩn hoá; Z = Σc là xấp xỉ của spec §2.3) | semantic nếu vế a ≥ vế (1 − a), ngược lại cooc |
| ials | `implicit` `explain(userid, user_items, itemid)`: điểm theo item j đã tương tác → event gần nhất cùng unit (mọi trip) | latent |
| bpr* | không phân rã theo event → `[]` | — |

`contract_items` đổi sang dạng `BecauseItem` của contract (`productName` = tên unit cha như `use_cases.py:175-176`) + khoá `kind`
(chỉ trong harness, ngoài contract). `violations` kiểm ràng buộc contract (spec tích hợp search–rec §4.4): popular ⟹ [], coldStart ⟹ [],
dormant ⟹ có `daysAgo > 90` (90 của contract, không phải `DORMANT_AFTER_DAYS` 365 của engine — I-8).
"""
from __future__ import annotations

from typing import Callable

import numpy as np

from src.backend.app.application.ports import UnitIndex
from src.backend.app.domain.recommendation import profile as P
from src.backend.app.domain.recommendation.profile import Profile, ResolvedEvent

MIN_SHARE, TOP = 0.15, 3
CONTRACT_DORMANT_DAYS = 90
KINDS = ("semantic", "cooc", "latent")


def event_weights(profile: Profile) -> tuple[list[tuple[float, ResolvedEvent]], float]:
    """([(c_e, event)], Z) — chép vòng lặp đầu của `profile.explain` (hằng đọc lúc gọi để `--override` đi theo)."""
    src = [profile.active_trip] if profile.active_trip is not None else list(profile.trips.values())
    contribs: list[tuple[float, ResolvedEvent]] = []
    Z = 0.0
    for t in src:
        # 09/10 (P2): nhánh u_long nhân thêm độ tin cậy chuyến, đúng phân rã của u_long
        wt = 1.0 if profile.active_trip is not None else 2 ** (-t.age_days / P.H_LONG_DAYS) * t.confidence
        for e in t.events:
            c = wt * P.W_TYPE.get(e.event_name, 0.1) * 2 ** (-e.days_ago / P.H_SHORT_DAYS)
            contribs.append((c, e))
            Z += c
    return contribs, (Z or 1.0)


def finalize(raw: list[tuple[float, ResolvedEvent, str]], *, min_share: float = MIN_SHARE, top: int = TOP) -> list[dict]:
    """Bước cuối của `profile.explain`: giữ raw > 0, chia tổng dương, round 2, sắp giảm (ổn định), lọc ≥ min_share, cắt top."""
    pos = [(c, e, k) for c, e, k in raw if c > 0]
    tot = sum(c for c, _, _ in pos) or 1.0
    out = sorted(({"unit": e.unit, "productId": e.product_id, "event": e.event_name, "daysAgo": int(e.days_ago),
                   "contribution": round(c / tot, 2), "kind": k} for c, e, k in pos), key=lambda x: -x["contribution"])
    return [b for b in out if b["contribution"] >= min_share][:top]


def content(profile: Profile, items, E: np.ndarray) -> list[list[dict]]:
    """Engine nguyên văn (`profile.explain`) + kind semantic."""
    if not profile.trips:
        return [[] for _ in items]
    return [[{**b, "kind": "semantic"} for b in P.explain(profile, int(x), E)] for x in items]


def from_rows(row: Callable[[int], np.ndarray | None], profile: Profile, items, *, kind: str = "cooc") -> list[list[dict]]:
    """`raw_e(x) = c_e·T[e, x]/Z` với `T[e] = row(e.unit)` (None = seed không có láng giềng → đóng góp 0)."""
    if not profile.trips:
        return [[] for _ in items]
    contribs, Z = event_weights(profile)
    rows = {}
    for _, e in contribs:
        if e.unit not in rows:
            rows[e.unit] = row(int(e.unit))
    out = []
    for x in items:
        x = int(x)
        raw = [(c * float(rows[e.unit][x]) / Z, e, kind) for c, e in contribs if rows[e.unit] is not None]
        out.append(finalize(raw))
    return out


def star(profile: Profile, items, E: np.ndarray, row: Callable[[int], np.ndarray | None], a: float) -> list[list[dict]]:
    """`a·c_e·(E_e·E_x)/Z + (1−a)·c_e·T[e, x]/Z`; a = 1 → đúng biểu thức của engine (cộng 0,0 chính xác theo IEEE)."""
    if not profile.trips:
        return [[] for _ in items]
    contribs, Z = event_weights(profile)
    rows = {}
    for _, e in contribs:
        if e.unit not in rows:
            rows[e.unit] = row(int(e.unit)) if a < 1.0 else None
    out = []
    for x in items:
        x = int(x)
        raw = []
        for c, e in contribs:
            sem = c * float(E[e.unit] @ E[x]) / Z
            r = rows[e.unit]
            co = c * float(r[x]) / Z if r is not None else 0.0
            value = a * sem + (1.0 - a) * co if a < 1.0 else sem
            raw.append((value, e, "semantic" if a * sem >= (1.0 - a) * co else "cooc"))
        out.append(finalize(raw))
    return out


def latent(profile: Profile, items, item_scores: Callable[[int], list[tuple[int, float]]], events: tuple[str, ...]) -> tuple[list[list[dict]], int]:
    """ials: `item_scores(x)` = [(unit j đã tương tác, đóng góp)] (từ `implicit` explain); map j → event trên **mọi** trip của khách
    (iALS dựng vector user từ cả hàng user, không theo trip) có `unit == j` và `event ∈ events` (ô của ma trận), `daysAgo` nhỏ nhất.
    Trả (because, số đóng góp không map được — vd ô từ event không có vector)."""
    if not profile.trips:
        return [[] for _ in items], 0
    latest: dict[int, ResolvedEvent] = {}
    for t in profile.trips.values():
        for e in t.events:
            if e.event_name in events and (e.unit not in latest or e.days_ago < latest[e.unit].days_ago):
                latest[e.unit] = e
    out, unmapped = [], 0
    for x in items:
        raw = []
        for j, s in item_scores(int(x)):
            e = latest.get(int(j))
            if e is None:
                unmapped += 1
                continue
            raw.append((float(s), e, "latent"))
        out.append(finalize(raw))
    return out, unmapped


def contract_items(index: UnitIndex, because: list[dict]) -> list[dict]:
    """Dạng `BecauseItem` (productId, productName = tên unit cha, event, daysAgo, contribution) + `kind` (harness)."""
    return [{"productId": b["productId"], "productName": index.units[b["unit"]].name, "event": b["event"], "daysAgo": int(b["daysAgo"]),
             "contribution": b["contribution"], "kind": b.get("kind")} for b in because]


def violations(strategy: str, cold_start: bool, because: list[list[dict]]) -> list[str]:
    """Luật contract bị vi phạm bởi danh sách because của một khách (rỗng = đạt)."""
    any_because = any(bool(b) for b in because)
    out = []
    if strategy == "popular" and any_because:
        out.append("popular_has_because")
    if cold_start and any_because:
        out.append("cold_start_has_because")
    if strategy == "dormant" and not any(item["daysAgo"] > CONTRACT_DORMANT_DAYS for b in because for item in b):
        out.append("dormant_without_old_event")
    return out
