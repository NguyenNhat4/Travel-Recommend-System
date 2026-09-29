"""Quy tắc chốt fasttrack §6 trên bảng kết quả giả; thống kê P99 + CI; harness helpers."""
from __future__ import annotations

import numpy as np

from evaluation.vector_bench.fast_report import evaluate_rules
from evaluation.vector_bench.runners.perf import ci_overlap, latency_stats


def _row(g3="pass", a3=1.0, a1=0.97, p99=50.0, ci=(45.0, 55.0), a1_fail=False):
    return {"G3": {"status": g3}, "quality_catalog": {"A3": 1.0, "A1": 1.0},
            "quality_1m": {"A3": a3, "A1": a1, "a1_fail": a1_fail},
            "perf": {"B1": {"p99_ms": p99, "p99_ci95": list(ci)}}}


def test_rule2_pgvector_wins_when_it_passes(cfg):
    d = evaluate_rules(cfg, {"pgvector": _row(), "qdrant": _row(p99=10, ci=(9, 11)), "pgvectorscale": _row()}, True, "1m")
    assert d["winner"] == "pgvector" and d["rule_applied"] == 2


def test_rule3_pgvectorscale_when_pgvector_fails_b1(cfg):
    d = evaluate_rules(cfg, {"pgvector": _row(p99=250, ci=(240, 260)), "pgvectorscale": _row(), "qdrant": _row()}, True, "1m")
    assert d["winner"] == "pgvectorscale" and d["rule_applied"] == 3


def test_rule4_qdrant_when_both_postgres_fail(cfg):
    d = evaluate_rules(cfg, {"pgvector": _row(a1=0.8), "pgvectorscale": _row(a1=0.9, a1_fail=True), "qdrant": _row()}, True, "1m")
    assert d["winner"] == "qdrant" and d["rule_applied"] == 4


def test_rule1_exclusion_then_rule5(cfg):
    d = evaluate_rules(cfg, {"pgvector": _row(g3="fail"), "pgvectorscale": _row(a3=0.999), "qdrant": _row(p99=150, ci=(140, 160))},
                       True, "1m")
    assert set(d["excluded"]) == {"pgvector", "pgvectorscale"}
    assert d["winner"] == "pgvector" and d["rule_applied"] == 5


def test_lid_fail_forces_rule5(cfg):
    d = evaluate_rules(cfg, {"pgvector": _row(), "qdrant": _row()}, False, "1m")
    assert d["rule_applied"] == 5 and any("LID" in r for r in d["reasons"])


def test_blocked_data_forces_rule5_and_fake_catalog_undecided(cfg):
    d = evaluate_rules(cfg, {"pgvector": _row()}, None, "1m", block_reason="dữ liệu 1m là vector fake")
    assert d["rule_applied"] == 5 and d["winner"] == "pgvector"
    d = evaluate_rules(cfg, {"pgvector": _row()}, True, "1m", catalog_fake=True)
    assert d["undecided"] and d["winner"] is None


def test_unmeasured_higher_priority_engine_blocks_decision(cfg):
    # pgvectorscale chưa chạy: không được nhảy sang Qdrant (quy tắc 4) khi pgvector trượt
    d = evaluate_rules(cfg, {"pgvector": _row(p99=250, ci=(240, 260)), "qdrant": _row()}, True, "1m")
    assert d["undecided"] and d["winner"] is None and d["state"]["pgvectorscale"] == "unmeasured"
    # pgvector thiếu B1 (perf không chạy) → chưa chốt, không coi là trượt
    r = _row()
    r["perf"] = None
    d = evaluate_rules(cfg, {"pgvector": r, "pgvectorscale": _row(), "qdrant": _row()}, True, "1m")
    assert d["undecided"] and d["state"]["pgvector"] == "unmeasured"


def test_p99_ci_overlap_is_tie_and_goes_to_pgvector(cfg):
    d = evaluate_rules(cfg, {"pgvector": _row(p99=50, ci=(45, 58)), "qdrant": _row(p99=52, ci=(50, 60))}, True, "1m")
    assert d["p99_ties"]
    # pgvector trượt B1 sát ngưỡng, pgvectorscale đạt, CI chồng nhau → hoà → pgvector
    d = evaluate_rules(cfg, {"pgvector": _row(p99=101, ci=(93, 112)), "pgvectorscale": _row(p99=97, ci=(90, 104)),
                             "qdrant": _row()}, True, "1m")
    assert d["winner"] == "pgvector" and d["tie_override"]
    assert ci_overlap([1, 2], [3, 4]) is False and ci_overlap([1, 3], [2, 4]) is True


def test_latency_stats_timeouts_counted_in_percentile():
    lat = np.full(1000, 5.0)
    lat[-20:] = 1000.0                      # 2% timeout đã thay bằng giá trị = timeout
    s = latency_stats(lat, 1000.0, 20, 0, 200, 1)
    assert s["p99"] == 1000.0 and s["p50"] == 5.0
    assert s["timeout_rate"] == 0.02 and s["p99_ci95"][0] <= 1000.0 <= s["p99_ci95"][1] + 1e-9
