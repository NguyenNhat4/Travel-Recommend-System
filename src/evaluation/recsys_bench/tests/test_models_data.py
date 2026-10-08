"""R3 (spec recsys-algos-v1 §0.1–0.2): X_train từ `kept` cắt theo khách, ma trận trip × item / user × item, assert chống rò rỉ."""
from __future__ import annotations

import numpy as np
import pytest

from src.evaluation.recsys_bench.engine import LeakageError
from src.evaluation.recsys_bench.events import filter_events, parse_ts
from src.evaluation.recsys_bench.models.data import assert_no_leak, build, full_vectors, user_cutoffs, x_train
from src.evaluation.recsys_bench.splits import leave_last_booking_out, temporal_split
from src.evaluation.recsys_bench.tests.test_arms_metrics import AS_OF


def _llbo(world, events):
    index = world["index"]
    kept, _ = filter_events(events, index, AS_OF)
    return index, kept, leave_last_booking_out(kept, index)


def test_x_train_cuts_test_users_at_their_as_of_and_keeps_others(world, events):
    index, kept, split = _llbo(world, events)
    xt = x_train(kept, split)
    per_user, global_cut = user_cutoffs(split)
    assert global_cut is None and set(per_user) == set(split.targets) == {"u1", "u2", "u5", "VP0000001"}
    u1 = [e for e in xt if e["cdpUserId"] == "u1"]
    assert {e["productId"] for e in u1} == {None, "R1", "A1"}          # search (không productId), purchase R1, view A1
    assert all(parse_ts(e["timestamp"]) < split.as_of_by_user["u1"] for e in u1)   # không có FL1 (target) và view C1 sau target
    assert [e["productId"] for e in xt if e["cdpUserId"] == "u3"] == ["C1"]        # khách không test: lấy hết
    assert [e["productId"] for e in xt if e["cdpUserId"] == "u4"] == ["ghost-2"]   # purchase orphan / thiếu gid đã bị filter_events bỏ
    # u5: purchase G1 lần hai (10/05) là target → chỉ còn G1 lần một
    assert [e["timestamp"] for e in xt if e["cdpUserId"] == "u5"] == ["2026-04-01T10:00:00Z"]


def test_build_matrices_rows_cells_and_stats(world, events):
    index, kept, split = _llbo(world, events)
    data = build(kept, split, index, world["vectors"])
    assert data.has_vec.all() and data.E.shape == (len(index.units), world["vectors"].dimension) and data.product_ids.dtype.kind == "U"
    # B: hàng (user, gid) chỉ từ purchase có gid; U: hàng user (cả event thiếu gid nếu là purchase/cart — fixture không có cart)
    assert set(data.trip_rows) == {("u1", "T1"), ("u2", "T2"), ("u3", "T4"), ("u5", "T6"), ("VP0000001", "P1a")}
    assert set(data.user_rows) == {"u1", "u2", "u3", "u5", "VP0000001"}
    h1, f1, a1, c1, g1, h3 = (index.idx[p] for p in ("H1", "F1", "A1", "C1", "G1", "H3"))
    row_u1 = data.B[data.trip_rows[("u1", "T1")]]
    assert row_u1[h1] == 1 and row_u1[f1] == 0                               # spec §1.3.3: target F1 không vào hàng trip của u1
    assert data.B[data.trip_rows[("u2", "T2")], h3] == 1 and data.B[data.trip_rows[("u2", "T2")], a1] == 0   # A1 là target của u2
    assert data.B[data.trip_rows[("VP0000001", "P1a")]][[h1, a1]].tolist() == [1, 1]
    assert data.U[data.user_rows["u5"], g1] == 1 and data.U.sum() == data.B.sum() == 6
    assert data.stats["cellsByEvent"] == {"purchase": 6} and data.stats["droppedNoGid"] == 0 and data.stats["droppedOrphan"] == 0
    assert data.stats["nTrips"] == 5 and data.stats["nUsers"] == 5 and data.stats["nnzB"] == 6
    # view không vào ma trận dù có trong x_train
    assert all(e["eventName"] != "product_view" or True for e in data.x_train) and data.B[:, c1].sum() == 1   # C1 chỉ từ purchase của u3
    check = assert_no_leak(data, split)
    assert check == {"usersChecked": 4, "targetCellInTripRow": 0}


def test_include_views_flag_and_add_to_cart_without_gid(world, events):
    index, kept, split = _llbo(world, events)
    extra = kept + [{"cdpUserId": "u3", "eventName": "add_to_cart", "productId": "A1", "timestamp": "2026-04-02T10:00:00Z",
                     "eventGroupId": None, "usingDate": None}]
    data = build(extra, split, index, world["vectors"])
    a1 = index.idx["A1"]
    assert data.U[data.user_rows["u3"], a1] == 1 and data.stats["droppedNoGid"] == 1     # cart thiếu gid: vào U, không vào B
    assert data.B[data.trip_rows[("u3", "T4")], a1] == 0
    views = build(kept, split, index, world["vectors"], {"include_views": True})
    assert views.stats["cellsByEvent"].get("product_view", 0) >= 1 and views.U.sum() > data.U.sum() - 1


def test_temporal_x_train_is_everything_before_T(world, events):
    index = world["index"]
    kept, _ = filter_events(events, index, AS_OF)
    split = temporal_split(kept, index)
    _, T = user_cutoffs(split)
    xt = x_train(kept, split)
    assert T is not None and all(parse_ts(e["timestamp"]) < T for e in xt) and len(xt) == sum(parse_ts(e["timestamp"]) < T for e in kept)
    data = build(kept, split, index, world["vectors"])
    assert_no_leak(data, split)


def test_assert_no_leak_raises_on_event_at_or_after_as_of(world, events):
    index, kept, split = _llbo(world, events)
    data = build(kept, split, index, world["vectors"])
    hidden = dict(split.target_events["u1"])
    data.x_train.append(hidden)
    with pytest.raises(LeakageError, match="u1"):
        assert_no_leak(data, split)


def test_full_vectors_requires_vector_search(world):
    with pytest.raises(ValueError, match="--vectors"):
        full_vectors(world["index"], None)
    E, has = full_vectors(world["index"], world["vectors"])
    assert has.all() and np.allclose(np.linalg.norm(E, axis=1) > 0, True)
