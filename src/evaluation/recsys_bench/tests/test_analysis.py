"""B6–B8: nhãn khách, phân khúc (n cộng đúng), strict/lenient theo taxonomy, nguyên nhân 20 ca theo thứ tự ưu tiên."""
from datetime import datetime, timezone

from src.evaluation.recsys_bench.analysis import (CASE_REASONS, LABELS, case_reason, cases, cases_markdown, lifecycle_at,
                                                  segments, segments_markdown, strict_lenient, strict_markdown,
                                                  target_trip_kind, user_labels)
from src.evaluation.recsys_bench.arms import EngineArm, MostPopularInDestinationArm
from src.evaluation.recsys_bench.bench import evaluate
from src.evaluation.recsys_bench.ceiling import ceiling, engine_view
from src.evaluation.recsys_bench.engine import OfflineEngine
from src.evaluation.recsys_bench.events import filter_events, parse_ts
from src.evaluation.recsys_bench.splits import leave_last_booking_out

AS_OF = datetime(2026, 9, 24, tzinfo=timezone.utc)


def _world_rows(world, events):
    index = world["index"]
    kept, _ = filter_events(events, index, AS_OF)
    split = leave_last_booking_out(kept, index)
    engine = OfflineEngine(index, world["vectors"], split.train_purchases)
    rows = {}
    for arm in (EngineArm(engine), MostPopularInDestinationArm(index, engine)):
        _, per_user = evaluate(arm, split, index, k=20)
        rows[arm.key] = {r["user"]: r for r in per_user}
    views = {u: engine_view(split.train_by_user[u], index, split.as_of_by_user[u]) for u in split.targets}
    return index, split, rows, views


def test_lifecycle_from_train_purchases():
    ev = lambda d: {"eventName": "purchase", "timestamp": d}   # noqa: E731
    assert lifecycle_at([], AS_OF) == "new"
    assert lifecycle_at([{"eventName": "product_view", "timestamp": "2026-09-01T00:00:00Z"}], AS_OF) == "new"
    assert lifecycle_at([ev("2026-06-01T00:00:00Z")], AS_OF) == "active"
    assert lifecycle_at([ev("2025-12-01T00:00:00Z"), ev("2025-01-01T00:00:00Z")], AS_OF) == "dormant"
    assert lifecycle_at([ev("2025-01-01T00:00:00Z")], AS_OF) == "churned"


def test_labels_target_trip_and_segments_sum_to_users(world, events):
    index, split, rows, views = _world_rows(world, events)
    labels = user_labels(split, index, rows["engine"], views)
    assert set(labels) == set(split.targets) and all(set(labels[u]) == set(LABELS) for u in labels)
    # u1: target FL1 thuộc trip T1; từ 09/10 chuyến đã đặt T1 là trip mở (trước đó view lẻ _solo_A1 chiếm chỗ, I-3) → open;
    # u5: mua lại G1 trong trip T7 mới → new
    assert target_trip_kind(split, "u1", views["u1"]) == "open" and labels["u1"]["activeTripIsSolo"] is False
    assert target_trip_kind(split, "u5", views["u5"]) == "new" and labels["u5"]["strategy"] == "cross_vertical"
    assert labels["VP0000001"]["persona"] is True and labels["u2"]["lifecycleAtAsOf"] == "active"
    assert labels["u1"]["targetTaxonomy"] == "flight"
    seg = segments(rows, labels, k=20)
    for label in LABELS:
        assert sum(g["n"] for g in seg[label].values()) == len(split.targets), label
        for g in seg[label].values():
            assert g["noisy"] is True and set(g["arms"]) == set(rows)          # fixture nhỏ: mọi nhóm đều "ồn"
            for a in rows.values():
                pass
    md = segments_markdown(seg, ["engine", "most_popular_in_destination"], k=20)
    assert "**strategy**" in md and "ồn" in md and "hit@20 / NDCG@10" in md


def test_strict_lenient_by_taxonomy(world, events):
    index, split, rows, views = _world_rows(world, events)
    sl = strict_lenient(rows, split, index, k=20)
    assert set(sl) == {"attraction", "flight", "golf", "hotel"} and sum(g["n"] for g in sl.values()) == 4
    assert sl["flight"]["nChild"] == 1 and sl["flight"]["arms"]["engine"]["strict"] == 0.0     # FL1 con của F1: strict = 0 theo cấu trúc
    assert sl["hotel"]["nChild"] == 1 and sl["attraction"]["nChild"] == 0
    for tax in ("attraction", "golf"):                                                       # target cấp unit: strict = lenient
        for a in rows:
            assert sl[tax]["arms"][a]["strict"] == sl[tax]["arms"][a]["lenient"] == sl[tax]["arms"][a]["strictUnitLevel"]
    assert sl["flight"]["arms"]["engine"]["strictUnitLevel"] is None
    assert "theo cấu trúc" in strict_markdown(sl, list(rows), k=20)


def test_case_reasons_follow_priority_and_cases_are_deterministic(world, events):
    index, split, rows, views = _world_rows(world, events)
    ceil = ceiling(rows["engine"], split, index, views, k=20)
    # u5: bị lọc (đã mua + golf) → filtered dù các lý do sau cũng đúng
    assert case_reason("u5", rows, ceil["perUser"], views, split, base="engine")[0] == "filtered"
    # u1: trip mở đã là chuyến chứa target (09/10, sửa I-3) nên không còn wrong_active_trip; engine không lấy được F1 vào list
    assert case_reason("u1", rows, ceil["perUser"], views, split, base="engine")[0] == "out_of_candidates"
    # u2: không trip mở, trả đủ 20 → không có engine_nommr → ranked_low; có nommr → pool_miss / mmr_demoted
    r2 = dict(rows["engine"]["u2"]); r2["returned"] = 20
    rows2 = {**rows, "engine": {**rows["engine"], "u2": r2}}
    assert case_reason("u2", rows2, ceil["perUser"], views, split, base="engine")[0] == "ranked_low"
    rows2["engine_nommr"] = {"u2": {"rank": 57}}
    assert case_reason("u2", rows2, ceil["perUser"], views, split, base="engine")[0] == "ranked_low"      # ngoài top-20 kể cả không MMR
    rows2["engine_nommr"] = {"u2": {"rank": 7}}
    assert case_reason("u2", rows2, ceil["perUser"], views, split, base="engine")[0] == "mmr_demoted"    # top-20 theo score, MMR đẩy ra
    rows2["engine_nommr"] = {"u2": {"rank": None}}
    assert case_reason("u2", rows2, ceil["perUser"], views, split, base="engine")[0] == "pool_miss"
    # returned < k → out_of_candidates (trước ranked_low)
    r2["returned"] = 3
    assert case_reason("u2", rows2, ceil["perUser"], views, split, base="engine")[0] == "out_of_candidates"
    # engine_prod: trúng ở eval nhưng không ở prod → vertical_cap, kể cả khi prod trả ít hơn k (cap luôn < 20)
    rows3 = {**rows2, "engine_prod": {"u2": {"rank": None, "returned": 7}}, "engine": {**rows2["engine"], "u2": {**r2, "rank": 4, "returned": 20}}}
    assert case_reason("u2", rows3, ceil["perUser"], views, split, base="engine_prod")[0] == "vertical_cap"
    # prod trượt cả ở eval: hết ứng viên đo trên list eval (không cap), không phải trên `returned` của prod
    rows4 = {**rows3, "engine": {**rows2["engine"], "u2": {**r2, "rank": None, "returned": 20}}}
    assert case_reason("u2", rows4, ceil["perUser"], views, split, base="engine_prod")[0] in ("pool_miss", "mmr_demoted", "ranked_low")
    # cases(): chỉ khách engine trượt & ref trúng; tất định; markdown có bảng
    c = cases(rows, ceil["perUser"], views, split, index, base="engine", ref="most_popular_in_destination", n=20, k=20)
    assert c["nUsers"] == 4 and c["nCandidates"] == len(c["cases"]) <= 4 and all(d["reason"] in CASE_REASONS for d in c["cases"])
    assert c == cases(rows, ceil["perUser"], views, split, index, base="engine", ref="most_popular_in_destination", n=20, k=20)
    md = cases_markdown(c)
    assert "Nguyên nhân" in md and str(c["nCandidates"]) in md
