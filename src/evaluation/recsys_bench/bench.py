"""Chạy một arm trên một split và gom chỉ số; nhiều seed của cùng họ arm được gộp thành trung bình ± độ lệch.

Day 4 R2 (01/10): hai cột cross-category theo **chuyến mở** cần biết, với từng khách, chuyến mở tại `as_of` và taxonomy đã mua
trong đó — lấy từ `ceiling.engine_view` (cùng luật `trip_is_open` / cap lặp / bỏ unit chưa có vector như engine). `run` tính
`views` một lần cho cả 6 arm và truyền vào; caller không truyền thì `evaluate` tự tính (giả định mọi unit đều có vector).
"""
from __future__ import annotations

from collections import Counter

import numpy as np

from src.backend.app.application.ports import UnitIndex

from .ceiling import EngineView, engine_view
from .events import PERSONA_IDS
from .metrics import purchased_taxonomies, rank_of, score
from .splits import Split


def open_trip_taxonomies(views: dict[str, EngineView]) -> dict[str, set[str] | None]:
    """Khách → taxonomy đã mua trong chuyến mở tại as_of (∅ nếu chuyến mở chưa mua gì); None nếu không có chuyến mở."""
    return {u: (set(v.excluded) if v.active_trip else None) for u, v in views.items()}


def evaluate(arm, split: Split, index: UnitIndex, k: int = 20,
             users: list[str] | None = None, *, views: dict[str, EngineView] | None = None) -> tuple[dict, list[dict]]:
    """Trả (hàng chỉ số của arm, bảng theo khách). Cùng tập khách, cùng as_of, cùng train cho mọi arm.
    `views`: `engine_view` của từng khách (tính một lần trong `run`); thiếu khách nào thì tính bù tại đây."""
    chosen = sorted(users if users is not None else split.targets)
    views = dict(views or {})
    for user in chosen:
        if user not in views:
            views[user] = engine_view(split.train_by_user[user], index, split.as_of_by_user[user])
    recommendations, latencies, per_user = {}, [], []
    strategies: Counter = Counter()
    for user in chosen:
        ranked = arm.recommend(user, split.as_of_by_user[user], k, split.train_by_user[user])
        recommendations[user] = ranked.product_ids
        latencies.append(ranked.latency_ms)
        if ranked.meta.get("strategy"):
            strategies[ranked.meta["strategy"]] += 1
        target = split.targets[user]
        original = str(split.target_events[user].get("productId") or "")     # purchase gốc: phòng / chuyến (con) hay unit
        per_user.append({"arm": arm.key, "user": user, "persona": user in PERSONA_IDS,
                         "asOf": split.as_of_by_user[user].isoformat(), "target": target,
                         "targetProductId": original, "targetIsChild": original != target,
                         "targetTaxonomy": str(index.taxonomy[index.idx[target]]),
                         "rank": rank_of(target, ranked.product_ids),            # lenient: unit cha (metric chính)
                         # strict: đúng productId đã mua (B7). Mọi arm chỉ trả search unit → targetIsChild=True (phòng /
                         # chuyến) luôn None; ngược lại == rank. Bảng strict/lenient chỉ có nghĩa ở độ mịn unit.
                         "rankStrict": rank_of(original, ranked.product_ids),
                         "returned": len(ranked.product_ids), "ids": list(ranked.product_ids),
                         "latencyMs": round(ranked.latency_ms, 2), **ranked.meta})
    bought = {u: purchased_taxonomies(split.train_by_user[u], index) for u in chosen}
    targets = {u: split.targets[u] for u in chosen}
    row = {"arm": arm.key, "family": arm.family, "split": split.kind,
           **score(recommendations, targets, bought, index, latencies,
                   open_trip=open_trip_taxonomies({u: views[u] for u in chosen}))}
    if strategies:
        row["strategies"] = dict(strategies.most_common())
    return row, per_user


def aggregate(rows: list[dict]) -> dict:
    """Gộp các hàng cùng họ (vd random 3 seed): số → trung bình, kèm `<khoá>_std`; `seeds` = số hàng gộp."""
    if len(rows) == 1:
        return dict(rows[0])
    out = {"arm": rows[0]["family"], "family": rows[0]["family"], "split": rows[0]["split"], "seeds": len(rows)}
    for key, value in rows[0].items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values = np.asarray([r[key] for r in rows], dtype=np.float64)
            out[key] = float(values.mean())
            out[f"{key}_std"] = float(values.std(ddof=0))
    return out
