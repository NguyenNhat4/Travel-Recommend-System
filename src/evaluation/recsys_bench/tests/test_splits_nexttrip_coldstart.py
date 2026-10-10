"""Split `nexttrip`, `coldstart` và nhãn `targetInOwnHistory` / `targetInOwnCart` (05/10, bộ eval-v2)."""
from __future__ import annotations

from src.evaluation.recsys_bench.events import filter_events
from src.evaluation.recsys_bench.splits import (cold_start_split, history_labels, leave_last_booking_out, next_trip_split,
                                                temporal_split)
from src.evaluation.recsys_bench.tests.conftest import ev
from src.evaluation.recsys_bench.tests.test_arms_metrics import AS_OF


def _kept(world, events):
    kept, _ = filter_events(events, world["index"], AS_OF)
    return kept


def test_next_trip_targets_first_item_of_trip_after_an_ended_trip(world):
    events = [
        # n1: chuyến 1 (đi 10/03) đã xong trước chuyến 2 (mua 01/05) → target = món đầu chuyến 2 (R3 → H3)
        ev("n1", "add_to_cart", "R3", "2026-03-20T10:00:00Z"),                       # bỏ giỏ H3 từ trước → tín hiệu hợp lệ
        ev("n1", "purchase", "R1", "2026-02-20T10:00:00Z", "A", using_date="2026-03-10"),
        ev("n1", "purchase", "FL1", "2026-02-20T10:02:00Z", "A", using_date="2026-03-10"),
        ev("n1", "product_view", "R3", "2026-04-30T10:00:00Z"),
        ev("n1", "purchase", "R3", "2026-05-01T10:00:00Z", "B", using_date="2026-05-20"),
        ev("n1", "purchase", "A1", "2026-05-01T10:02:00Z", "B", using_date="2026-05-21"),
        # n2: chuyến 2 mua khi chuyến 1 chưa đi (usingDate 10/06 ≥ 01/05) → không vào split
        ev("n2", "purchase", "R1", "2026-04-20T10:00:00Z", "C", using_date="2026-06-10"),
        ev("n2", "purchase", "C1", "2026-05-01T10:00:00Z", "D", using_date="2026-06-11"),
        # n3: chỉ 1 chuyến → không vào split
        ev("n3", "purchase", "R1", "2026-04-20T10:00:00Z", "E", using_date="2026-04-25"),
    ]
    sp = next_trip_split(_kept(world, events), world["index"])
    assert sp.kind == "nexttrip" and set(sp.targets) == {"n1"}
    assert sp.targets["n1"] == "H3" and sp.target_events["n1"]["eventGroupId"] == "B"
    assert sp.as_of_by_user["n1"].isoformat().startswith("2026-04-30T10:00")          # lúc bắt đầu duyệt chuyến B (view R3)
    assert {e["productId"] for e in sp.train_by_user["n1"]} == {"R1", "FL1", "R3"}     # bỏ giỏ cũ vào train, lượt xem chuyến mới thì không
    assert sp.meta["noEndedPreviousTrip"] == 1
    assert sp.meta["targetInOwnHistory"] == 1 and sp.meta["targetInOwnCart"] == 1      # do lần bỏ giỏ 20/03, không do lượt xem 30/04


def test_cold_start_targets_first_purchase_with_prior_events(world):
    events = [
        ev("c1", "search", None, "2026-05-01T09:00:00Z"),
        ev("c1", "product_view", "A1", "2026-05-01T09:30:00Z"),
        ev("c1", "add_to_cart", "R1", "2026-05-01T09:50:00Z"),
        ev("c1", "purchase", "R1", "2026-05-01T10:00:00Z", "T"),
        ev("c1", "purchase", "FL1", "2026-06-01T10:00:00Z", "U"),
        ev("c2", "purchase", "C1", "2026-05-01T10:00:00Z", "V"),          # không có event trước → loại
        ev("c3", "product_view", "A1", "2026-05-01T10:00:00Z"),          # chưa mua → không vào split
    ]
    sp = cold_start_split(_kept(world, events), world["index"])
    assert set(sp.targets) == {"c1"} and sp.targets["c1"] == "H1"
    assert len(sp.train_by_user["c1"]) == 3 and sp.meta["noPriorEvents"] == 1
    labels = history_labels(sp, world["index"])
    assert labels["c1"] == {"targetInOwnHistory": True, "targetInOwnCart": True, "targetViewed": False}
    assert sp.meta["targetInOwnCart"] == 1


def test_labels_do_not_change_frozen_sha_of_existing_splits(world, events):
    kept = _kept(world, events)
    llbo = leave_last_booking_out(kept, world["index"])
    temporal = temporal_split(kept, world["index"])
    for sp in (llbo, temporal):
        assert "targetInOwnHistory" not in sp.meta and "minEvents" not in sp.canonical()["params"]
        labels = history_labels(sp, world["index"])
        assert set(labels) == set(sp.targets)
    # u1 xem A1 sau target (C1 sau as_of) — chỉ event trước as_of được xét
    assert history_labels(llbo, world["index"])["u1"]["targetInOwnHistory"] is False
