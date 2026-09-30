from datetime import datetime, timezone

import numpy as np
import pytest

from src.backend.app.application.ports import UnitIndex
from src.backend.app.domain.catalog import Product
from src.evaluation.recsys_bench.arms import EngineArm, RandomArm
from src.evaluation.recsys_bench.bench import aggregate, evaluate
from src.evaluation.recsys_bench.data_source import derive_as_of
from src.evaluation.recsys_bench.engine import OfflineEngine
from src.evaluation.recsys_bench.events import filter_events
from src.evaluation.recsys_bench.metrics import score
from src.evaluation.recsys_bench.report import markdown_table
from src.evaluation.recsys_bench.splits import leave_last_booking_out

AS_OF = datetime(2026, 9, 24, tzinfo=timezone.utc)


def small_index():
    units = [Product("a", "Hotel A", "hotel", "Nha Trang", "", unit_price=100, available=True),
             Product("b", "Ticket B", "attraction", "Nha Trang", "", unit_price=50, available=False),
             Product("c", "Flight C", "flight", "Đà Nẵng", "", unit_price=60, available=True)]
    return UnitIndex(units=units, taxonomy=np.array([p.taxonomy for p in units]),
                     destination=np.array([p.destination for p in units]),
                     available=np.array([p.available for p in units]),
                     recommendable=np.array([True, True, False]), parent_of={}, model_version="test")


def test_metrics_match_ported_case_and_add_recall5_and_diversity():
    # Ca `test_ranking_metrics_measure_hit_cross_category_availability_and_coverage` của khoa/recsys-research.
    m = score({"u1": ["b", "a"]}, {"u1": "b"}, {"u1": {"hotel"}}, small_index(), latencies_ms=[1, 2, 3, 4, 5])
    assert m["recall@5"] == m["recall@10"] == m["recall@20"] == m["ndcg@10"] == 1.0
    assert m["cross_category_rate"] == 0.5 and m["availability_precision"] == 0.5
    assert m["catalog_coverage"] == 1.0 and m["p99_runtime_ms"] == 4.96
    assert m["vertical_diversity@10"] == 1.0 and m["returned_mean"] == 2.0 and m["users"] == 1


def test_ndcg_discounts_by_rank_and_missing_target_scores_zero():
    m = score({"u1": ["a", "b"], "u2": ["a"]}, {"u1": "b", "u2": "c"}, {}, small_index())
    assert m["recall@10"] == 0.5 and abs(m["ndcg@10"] - 0.5 / np.log2(3)) < 1e-9


def test_random_arm_is_deterministic_and_stays_in_engine_candidates(world):
    index = world["index"]
    allowed = {index.units[i].product_id for i in np.flatnonzero(index.mask(only_recommendable=True))}
    a = RandomArm(index, 42).recommend("u1", AS_OF, 3, [])
    b = RandomArm(index, 42).recommend("u1", AS_OF, 3, [])
    assert a.product_ids == b.product_ids and set(a.product_ids) <= allowed
    assert len(a.product_ids) == min(3, len(allowed)) and len(set(a.product_ids)) == len(a.product_ids)


def test_evaluate_random_and_engine_on_same_split(world, events):
    index = world["index"]
    kept, _ = filter_events(events, index, AS_OF)
    split = leave_last_booking_out(kept, index)
    seed_rows = [evaluate(RandomArm(index, s), split, index, k=20)[0] for s in (42, 43)]
    random_row = aggregate(seed_rows)
    assert random_row["seeds"] == 2 and random_row["users"] == 4 and "recall@20_std" in random_row
    engine_row, per_user = evaluate(EngineArm(OfflineEngine(index, world["vectors"], split.train_purchases)),
                                    split, index, k=20)
    assert engine_row["users"] == 4 and sum(engine_row["strategies"].values()) == 4
    assert {r["user"] for r in per_user} == set(split.targets)
    assert all(r["returned"] <= 20 for r in per_user)
    table = markdown_table([random_row, engine_row])
    assert table.count("\n") == 3 and "random (2 seed)" in table and "| engine |" in table


def test_derive_as_of_is_midnight_after_last_event(events):
    assert derive_as_of(events) == datetime(2026, 9, 22, tzinfo=timezone.utc)


def test_cli_parses_as_of_and_lists_commands():
    pytest.importorskip("typer")   # CLI cần src/evaluation/requirements.txt; phần còn lại của harness thì không
    from typer.testing import CliRunner

    from src.evaluation.recsys_bench.__main__ import _parse_as_of, app

    assert _parse_as_of("2026-09-24") == AS_OF
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("doctor", "load", "split", "run", "user"):
        assert command in result.output


def test_popularity_baselines_use_window_before_as_of_and_destination(world, events):
    from src.evaluation.recsys_bench.arms import MostPopularArm, MostPopularInDestinationArm, trip_destination
    index = world["index"]
    kept, _ = filter_events(events, index, AS_OF)
    split = leave_last_booking_out(kept, index)
    engine = OfflineEngine(index, None, split.train_purchases)          # popularity không cần vector
    allowed = {index.units[i].product_id for i in np.flatnonzero(index.mask(only_recommendable=True))}
    mp = MostPopularArm(index, engine)
    a = mp.recommend("u1", split.as_of_by_user["u1"], 3, split.train_by_user["u1"])
    b = mp.recommend("u1", split.as_of_by_user["u1"], 3, split.train_by_user["u1"])
    assert a.product_ids == b.product_ids and set(a.product_ids) <= allowed and len(set(a.product_ids)) == len(a.product_ids)
    assert a.meta == {"strategy": "most_popular"}
    # cửa sổ 90 ngày trước as_of của u1 (2026-06-03): purchase R1 (01/06), A1 của u2 (01/05), G1 ×2 (04–05) — không có
    # FL1 (target, = as_of) và không có gì sau đó; unit được mua nhiều nhất (G1) đứng đầu nếu recommendable
    pop = engine.popularity_at(split.as_of_by_user["u1"]).unit_scores(window_days=90)
    assert all(u < len(index.units) for u in pop) and max(pop.values()) == 1.0
    # destination: chuyến đang mở T1 của u1 → điểm đến của H1
    d = trip_destination(index, split.train_by_user["u1"], split.as_of_by_user["u1"])
    assert d == str(index.destination[index.resolve("R1")])
    mpd = MostPopularInDestinationArm(index, engine)
    r = mpd.recommend("u1", split.as_of_by_user["u1"], 3, split.train_by_user["u1"])
    assert r.meta["destination"] == d and set(r.product_ids) <= allowed and len(r.product_ids) == min(3, len(allowed))
    assert r.meta["strategy"] in ("most_popular_in_destination", "most_popular_fallback")
    # khách không có event quy được → lùi về toàn cục, không lỗi
    r0 = mpd.recommend("ghost", AS_OF, 3, [])
    assert r0.meta["destination"] is None and r0.meta["strategy"] == "most_popular_fallback" and r0.product_ids == mp.recommend("ghost", AS_OF, 3, []).product_ids
    row, per_user = evaluate(mpd, split, index, k=20)
    assert row["arm"] == "most_popular_in_destination" and row["users"] == 4 and all(r["returned"] <= 20 for r in per_user)
