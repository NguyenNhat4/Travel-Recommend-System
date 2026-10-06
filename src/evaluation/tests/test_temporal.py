from datetime import datetime, timezone

from src.backend.app.application.ports import UnitIndex
from src.backend.app.domain.catalog import Product
from src.evaluation.benchmark import leave_one_purchase_out, score_recommendations

import numpy as np


def make_index():
    units = [
        Product("a", "Hotel A", "hotel", "Nha Trang", "", unit_price=100, available=True),
        Product("b", "Ticket B", "attraction", "Nha Trang", "", unit_price=50, available=False),
        Product("c", "Flight C", "flight", "Đà Nẵng", "", unit_price=60, available=True),
    ]
    return UnitIndex(
        units=units,
        E=np.eye(3, dtype=np.float32),
        taxonomy=np.array([p.taxonomy for p in units]),
        destination=np.array([p.destination for p in units]),
        available=np.array([p.available for p in units]),
        recommendable=np.array([True, True, False]),
        parent_of={},
        model_version="test",
    )


def test_temporal_holdout_removes_only_latest_purchase_and_keeps_prior_events():
    events = [
        {"cdpUserId": "u1", "eventName": "purchase", "productId": "a", "timestamp": "2026-01-01T00:00:00Z"},
        {"cdpUserId": "u1", "eventName": "product_view", "productId": "b", "timestamp": "2026-01-02T00:00:00Z"},
        {"cdpUserId": "u1", "eventName": "purchase", "productId": "c", "timestamp": "2026-01-03T00:00:00Z"},
        {"cdpUserId": "u1", "eventName": "product_view", "productId": "a", "timestamp": "2026-01-04T00:00:00Z"},
        {"cdpUserId": "u2", "eventName": "product_view", "productId": "a", "timestamp": "2026-01-02T00:00:00Z"},
    ]

    split = leave_one_purchase_out(events, make_index())

    assert split.targets == {"u1": "c"}
    assert [event["eventName"] for event in split.train_by_user["u1"]] == ["purchase", "product_view"]
    assert len(split.train_events) == 3
    assert all(event.get("productId") != "c" for event in split.train_events)
    assert all(event["timestamp"] < "2026-01-03T00:00:00Z" for event in split.train_by_user["u1"])


def test_temporal_holdout_is_deterministic_for_same_timestamp_purchases():
    events = [
        {"cdpUserId": "u1", "eventName": "purchase", "productId": product_id, "timestamp": "2026-01-03T00:00:00Z"}
        for product_id in ("a", "c")
    ]

    first = leave_one_purchase_out(events, make_index())
    second = leave_one_purchase_out(events, make_index())

    assert first.targets == second.targets
    assert first.train_events == []


def test_temporal_holdout_resolves_variant_purchase_to_search_unit():
    index = make_index()
    index.parent_of["hotel-room"] = "a"
    events = [
        {"cdpUserId": "u1", "eventName": "purchase", "productId": "hotel-room", "timestamp": "2026-01-03T00:00:00Z"},
    ]

    split = leave_one_purchase_out(events, index)

    assert split.targets == {"u1": "a"}


def test_temporal_holdout_compares_timestamps_as_instants_across_offsets():
    events = [
        {"cdpUserId": "u1", "eventName": "purchase", "productId": "a", "timestamp": "2026-01-02T00:30:00Z"},
        {"cdpUserId": "u1", "eventName": "purchase", "productId": "c", "timestamp": "2026-01-02T01:00:00+02:00"},
    ]

    split = leave_one_purchase_out(events, make_index())

    assert split.targets == {"u1": "a"}


def test_benchmark_runs_all_methods_on_the_same_holdout():
    from src.evaluation.benchmark import run_benchmark

    events = [
        {"cdpUserId": "u1", "eventName": "product_view", "productId": "a", "timestamp": "2026-01-01T00:00:00Z"},
        {"cdpUserId": "u1", "eventName": "purchase", "productId": "b", "timestamp": "2026-01-02T00:00:00Z"},
        {"cdpUserId": "u2", "eventName": "product_view", "productId": "c", "timestamp": "2026-01-01T00:00:00Z"},
        {"cdpUserId": "u2", "eventName": "purchase", "productId": "a", "timestamp": "2026-01-02T00:00:00Z"},
    ]

    rows, split = run_benchmark(make_index(), events, k=20, seed=11)

    assert len(rows) == 10
    assert {row["key"] for row in rows} == {
        "random", "global_popularity", "destination_season_popularity", "structured_content",
        "multilingual_embedding", "item_item_cf", "implicit_als", "personalized_pagerank",
        "markov_sequence", "hybrid_contextual",
    }
    assert split.targets == {"u1": "b", "u2": "a"}
    assert all(0 <= row["availability_precision"] <= 1 for row in rows)


def test_ranking_metrics_measure_hit_cross_category_availability_and_coverage():
    index = make_index()
    results = {
        "u1": ["b", "a"],
    }
    targets = {"u1": "b"}
    taxonomy = {"u1": {"hotel"}}

    metrics = score_recommendations(results, targets, taxonomy, index, latencies_ms=[1, 2, 3, 4, 5])

    assert metrics["recall@10"] == 1.0
    assert metrics["recall@20"] == 1.0
    assert metrics["ndcg@10"] == 1.0
    assert metrics["cross_category_rate"] == 0.5
    assert metrics["availability_precision"] == 0.5
    assert metrics["catalog_coverage"] == 2 / 2
    assert metrics["p95_runtime_ms"] >= 4
    assert metrics["p99_runtime_ms"] == 4.96


def test_benchmark_rows_from_before_p99_are_detected_as_stale():
    from src.evaluation.benchmark import benchmark_rows_have_p99

    assert not benchmark_rows_have_p99([{"key": "random", "p95_runtime_ms": 1.2}])
    assert benchmark_rows_have_p99([{"key": "random", "p95_runtime_ms": 1.2, "p99_runtime_ms": 1.3}])
