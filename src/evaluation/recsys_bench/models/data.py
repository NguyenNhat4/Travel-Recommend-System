"""X_train và ma trận nhị phân trip × item / user × item (spec `recsys-algos-v1.md` §0.1–0.2).

- X_train dựng từ `kept` (mọi event đã lọc của `_prepared`), **không** từ `Split.train_purchases` (chứa purchase bị giấu). LLBO: khách
  test u chỉ giữ event `ts < as_of_u`, khách khác lấy hết; temporal: mọi event `ts < T`. Một ma trận toàn cục mỗi split.
- Map event → unit bằng đúng `UnitIndex.resolve` của engine; bỏ orphan và (như engine) unit chưa có vector trong kho.
- Ô = 1 nếu hàng có `purchase` hoặc `add_to_cart` (cấu hình `matrix.events`); view/search không vào ma trận.
- `assert_no_leak` chạy trong `run` (spec §9): mọi event của khách test trong X_train phải trước `as_of_u`.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

import numpy as np

from src.backend.app.application.ports import UnitIndex, VectorSearchPort

from ..engine import LeakageError
from ..events import parse_ts
from ..splits import Split
from .base import TrainData

DEFAULT_MATRIX = {"cell": "binary", "events": ["purchase", "add_to_cart"], "include_views": False}


def user_cutoffs(split: Split) -> tuple[dict[str, datetime], datetime | None]:
    """LLBO → (as_of theo khách test, None); temporal → ({}, T) vì mọi khách cùng mốc."""
    if split.kind == "temporal":
        cutoff = next(iter(split.as_of_by_user.values()), None)
        return {}, cutoff
    return dict(split.as_of_by_user), None


def x_train(kept: list[dict], split: Split) -> list[dict]:
    per_user, global_cut = user_cutoffs(split)
    out = []
    for e in kept:
        ts = parse_ts(e["timestamp"])
        if global_cut is not None and ts >= global_cut:
            continue
        cut = per_user.get(str(e.get("cdpUserId") or ""))
        if cut is not None and ts >= cut:
            continue
        out.append(e)
    return out


def full_vectors(index: UnitIndex, vector_search: VectorSearchPort | None) -> tuple[np.ndarray, np.ndarray]:
    """E_full (I, d) float32 theo thứ tự `index.units` + cờ có vector. Lấy qua `VectorSearchPort.vectors(ids)` — cùng nguồn với engine."""
    if vector_search is None:
        raise ValueError("--algos cần --vectors numpy|weaviate: mask chuẩn engine và scorer content cần vector của mọi unit")
    ids = [p.product_id for p in index.units]
    got = vector_search.vectors(ids)
    E = np.zeros((len(ids), int(vector_search.dimension)), dtype=np.float32)
    has = np.zeros(len(ids), dtype=bool)
    for i, pid in enumerate(ids):
        v = got.get(pid)
        if v is not None and np.asarray(v).size:
            E[i] = np.asarray(v, dtype=np.float32)
            has[i] = True
    return E, has


def build(kept: list[dict], split: Split, index: UnitIndex, vector_search: VectorSearchPort | None,
          matrix_cfg: dict | None = None) -> TrainData:
    cfg = {**DEFAULT_MATRIX, **(matrix_cfg or {})}
    in_matrix = set(cfg["events"]) | ({"product_view"} if cfg.get("include_views") else set())
    events = x_train(kept, split)
    E, has_vec = full_vectors(index, vector_search)
    trip_rows: dict[tuple[str, str], int] = {}
    user_rows: dict[str, int] = {}
    b_cells: set[tuple[int, int]] = set()
    u_cells: set[tuple[int, int]] = set()
    by_event: Counter = Counter()
    dropped_orphan = dropped_no_vec = dropped_no_gid = 0
    for e in events:
        name = str(e.get("eventName") or "")
        if name not in in_matrix:
            continue
        unit = index.resolve(str(e.get("productId") or ""))
        if unit is None:
            dropped_orphan += 1
            continue
        if not has_vec[unit]:
            dropped_no_vec += 1
            continue
        by_event[name] += 1
        user = str(e.get("cdpUserId") or "")
        urow = user_rows.setdefault(user, len(user_rows))
        u_cells.add((urow, unit))
        gid = e.get("eventGroupId")
        if not gid:
            dropped_no_gid += 1
            continue
        trow = trip_rows.setdefault((user, str(gid)), len(trip_rows))
        b_cells.add((trow, unit))
    n_items = len(index.units)
    B = np.zeros((len(trip_rows), n_items), dtype=np.uint8)
    U = np.zeros((len(user_rows), n_items), dtype=np.uint8)
    if b_cells:
        r, c = zip(*b_cells)
        B[list(r), list(c)] = 1
    if u_cells:
        r, c = zip(*u_cells)
        U[list(r), list(c)] = 1
    stats = {"events": sorted(in_matrix), "nEventsXTrain": len(events), "nTrips": len(trip_rows), "nUsers": len(user_rows), "nnzB": len(b_cells), "nnzU": len(u_cells),
             "droppedOrphan": dropped_orphan, "droppedNoVector": dropped_no_vec, "droppedNoGid": dropped_no_gid,
             "cellsByEvent": dict(by_event), "unitsWithVector": int(has_vec.sum()), "matrix": cfg}
    return TrainData(index=index, x_train=events, B=B, trip_rows=trip_rows, U=U, user_rows=user_rows, E=E, has_vec=has_vec,
                     product_ids=np.array([p.product_id for p in index.units], dtype=str), stats=stats)


def assert_no_leak(data: TrainData, split: Split) -> dict:
    """Ném `LeakageError` nếu X_train có event của khách test tại/sau `as_of_u`. Trả thống kê để ghi vào summary:
    `targetCellInTripRow` = số target có ô = 1 trong hàng trip của chính nó (mua lặp cùng unit **trước** as_of — hợp lệ, chỉ để biết)."""
    per_user, global_cut = user_cutoffs(split)
    for e in data.x_train:
        ts = parse_ts(e["timestamp"])
        user = str(e.get("cdpUserId") or "")
        cut = per_user.get(user, global_cut)
        if cut is not None and ts >= cut:
            raise LeakageError(f"X_train có event của {user} tại {e['timestamp']} ≥ as_of {cut.isoformat()} — rò rỉ target")
    repeat = 0
    for user, target in split.targets.items():
        gid = split.target_events[user].get("eventGroupId")
        row = data.trip_rows.get((user, str(gid))) if gid else None
        if row is not None and data.B[row, data.index.idx[target]]:
            repeat += 1
    return {"usersChecked": len(split.targets), "targetCellInTripRow": repeat}
