"""Bootstrap ghép cặp của `theme_study/paired_ci.py` (plan WP2.2) trên dữ liệu giả — không DB, không model, không network.

Ba điều phải đúng, vì cả khuyến nghị cuối dựa vào chúng:
1. Chênh lệch hằng số → CI bao quanh đúng chênh đó và không chứa 0.
2. Hai cấu hình giống nhau → chênh 0, CI chứa 0, `significant` False.
3. Ghép cặp phải hẹp hơn coi hai mẫu độc lập khi hai cấu hình tương quan mạnh (đây là lý do tồn tại của script).
"""
from __future__ import annotations

import json

import numpy as np
import pytest

from src.evaluation.recsys_bench.theme_study import paired_ci as PC


def rows_for(config, stratum, values, metric="hit@20", seed=None):
    return [{"config": config, "stratum": stratum, "seed": seed, "uid": f"u{i:04d}", metric: v}
            for i, v in enumerate(values)]


def test_constant_shift_gives_tight_interval_excluding_zero():
    base = np.random.default_rng(1).random(400)
    a = {f"u{i}": float(v) for i, v in enumerate(base)}
    b = {f"u{i}": float(v) + 0.1 for i, v in enumerate(base)}
    r = PC.paired_ci(a, b, boot=500)
    assert r["n"] == 400
    assert r["diff"] == pytest.approx(0.1, abs=1e-6)
    # Chênh là hằng số nên mọi lần rút cho đúng 0,1: CI co về một điểm.
    assert r["ci_lo"] == pytest.approx(0.1, abs=1e-6) and r["ci_hi"] == pytest.approx(0.1, abs=1e-6)
    assert r["significant"] and r["shareBootGt0"] == 1.0


def test_identical_configs_are_not_significant():
    base = np.random.default_rng(2).random(300)
    a = {f"u{i}": float(v) for i, v in enumerate(base)}
    r = PC.paired_ci(a, dict(a), boot=500)
    assert r["diff"] == 0.0 and r["nDiscordant"] == 0
    assert r["ci_lo"] == 0.0 and r["ci_hi"] == 0.0
    assert not r["significant"]


def test_paired_interval_is_narrower_than_independent_for_correlated_configs():
    """Hai cấu hình chấm cùng khách nên tương quan mạnh; phương sai của chênh lệch nhỏ hơn hẳn tổng hai phương sai."""
    rng = np.random.default_rng(3)
    user = rng.normal(0, 1.0, 500)                      # hiệu ứng khách: lớn, chung cho cả hai cấu hình
    a = {f"u{i}": float(user[i] + rng.normal(0, 0.05)) for i in range(500)}
    b = {f"u{i}": float(user[i] + 0.03 + rng.normal(0, 0.05)) for i in range(500)}
    r = PC.paired_ci(a, b, boot=2000)
    paired_width = r["ci_hi"] - r["ci_lo"]
    xa = np.array(list(a.values())); xb = np.array(list(b.values()))
    independent_width = 2 * 1.96 * float(np.sqrt(xa.var(ddof=1) / len(xa) + xb.var(ddof=1) / len(xb)))
    assert paired_width < independent_width / 5
    assert r["significant"], "chênh 0,03 với nhiễu 0,05 trên 500 khách phải phân biệt được khi ghép cặp"


def test_only_users_present_in_both_configs_are_compared():
    a = {"u1": 1.0, "u2": 0.0, "u3": 1.0}
    b = {"u2": 1.0, "u3": 1.0, "u9": 0.0}
    r = PC.paired_ci(a, b, boot=200)
    assert r["n"] == 2                                  # u2, u3
    assert r["diff"] == pytest.approx(0.5)


def test_no_overlap_returns_none():
    assert PC.paired_ci({"u1": 1.0}, {"u2": 1.0}, boot=100) is None


def test_bootstrap_is_reproducible_for_a_fixed_seed():
    a = {f"u{i}": float(i % 2) for i in range(200)}
    b = {f"u{i}": float((i // 2) % 2) for i in range(200)}
    assert PC.paired_ci(a, b, boot=500, seed=7) == PC.paired_ci(a, b, boot=500, seed=7)
    assert PC.paired_ci(a, b, boot=500, seed=7) != PC.paired_ci(a, b, boot=500, seed=8)


def test_index_splits_metrics_by_stratum_kind_and_drops_nulls():
    rows = [{"config": "A", "stratum": "llbo", "seed": None, "uid": "u1", "hit@20": 1.0, "ndcg@10": 0.5, "hit@4": 0.0},
            {"config": "A", "stratum": "syn_between", "seed": 42, "uid": "s1", "themePrec": 0.75},
            {"config": "A", "stratum": "syn_between", "seed": 42, "uid": "s2", "themePrec": None}]
    idx = PC.index(rows)
    assert idx[("A", "llbo", None, "hit@20")] == {"u1": 1.0}
    # Chỉ số không có trong dòng (ở đây destHit@20 — chỉ có khi eval_split nhận idx) thì không tạo khoá, không thành 0.
    assert set(k[3] for k in idx if k[1] == "llbo") == {"hit@20", "ndcg@10", "hit@4"}
    assert "destHit@20" in PC.SPLIT_METRICS and ("A", "llbo", None, "destHit@20") not in idx
    # themePrec None (khách không có điểm đến chấm được) bị bỏ, không thành 0.
    assert idx[("A", "syn_between", 42, "themePrec")] == {"s1": 0.75}
    assert ("A", "syn_between", 42, "hit@20") not in idx


def test_pooled_keeps_seeds_apart():
    rows = rows_for("A", "syn_between", [1.0, 1.0], metric="themePrec", seed=1) + \
        rows_for("A", "syn_between", [0.0, 0.0], metric="themePrec", seed=2)
    idx = PC.index(rows)
    p = PC.pooled(idx, "A", "syn_between", "themePrec")
    assert len(p) == 4 and set(p.values()) == {0.0, 1.0}


def test_seed_spread_reports_mean_and_sd_across_seeds():
    rows = rows_for("A", "syn_noisy_paired", [0.8, 0.8], metric="themePrec", seed=1) + \
        rows_for("A", "syn_noisy_paired", [0.6, 0.6], metric="themePrec", seed=2)
    out = PC.seed_spread(PC.index(rows))
    assert len(out) == 1
    assert out[0]["perSeed"] == [0.8, 0.6] and out[0]["mean"] == pytest.approx(0.7)
    assert out[0]["sd"] == pytest.approx(float(np.std([0.8, 0.6], ddof=1)), abs=1e-4)


def test_compare_emits_one_row_per_stratum_and_metric(tmp_path):
    rows = (rows_for("A", "llbo", [1.0, 0.0, 1.0]) + rows_for("B", "llbo", [1.0, 1.0, 1.0])
            + rows_for("A", "syn_between", [0.5, 0.25], metric="themePrec", seed=7)
            + rows_for("B", "syn_between", [1.0, 0.75], metric="themePrec", seed=7))
    # hit@20 có mặt, ndcg@10 / hit@4 không → chỉ ra dòng của chỉ số thực sự có dữ liệu.
    out = PC.compare(PC.index(rows), [("A", "B")], boot=200)
    got = {(r["stratum"], r["metric"]): r for r in out}
    assert set(got) == {("llbo", "hit@20"), ("syn_between", "themePrec")}
    assert got[("llbo", "hit@20")]["diff"] == pytest.approx(1 / 3, abs=1e-4)   # `diff` làm tròn 4 chữ số
    assert got[("syn_between", "themePrec")]["diff"] == pytest.approx(0.5)


def test_load_reads_several_jsonl_files(tmp_path):
    f1, f2 = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    f1.write_text("\n".join(json.dumps(r) for r in rows_for("A", "llbo", [1.0])) + "\n", encoding="utf-8")
    f2.write_text("\n".join(json.dumps(r) for r in rows_for("B", "llbo", [0.0])) + "\n\n", encoding="utf-8")
    assert [r["config"] for r in PC.load([str(f1), str(f2)])] == ["A", "B"]


def test_noise_effect_pairs_noisy_cohort_back_to_its_between_user():
    rows = [
        {"config": "A", "stratum": "syn_between", "seed": 7, "uid": "SYN7-bb0000", "themePrec": 0.75},
        {"config": "A", "stratum": "syn_between", "seed": 7, "uid": "SYN7-bb0001", "themePrec": 1.0},
        # cùng khách + nhiễu: baseUid trỏ về khách `between` tương ứng
        {"config": "A", "stratum": "syn_noisy_paired", "seed": 7, "uid": "SYN7-pb0000",
         "baseUid": "SYN7-bb0000", "themePrec": 0.5},
        {"config": "A", "stratum": "syn_noisy_paired", "seed": 7, "uid": "SYN7-pb0001",
         "baseUid": "SYN7-bb0001", "themePrec": 0.5},
        # khách của kịch bản `noisy` cũ không có baseUid → không được ghép
        {"config": "A", "stratum": "syn_noisy", "seed": 7, "uid": "SYN7-nb0000", "themePrec": 0.0},
    ]
    out = PC.noise_effect(rows, boot=200)
    assert len(out) == 1 and out[0]["n"] == 2
    assert out[0]["meanA"] == pytest.approx(0.875) and out[0]["meanB"] == pytest.approx(0.5)
    assert out[0]["diff"] == pytest.approx(-0.375)


def test_noise_effect_skips_users_whose_base_or_value_is_missing():
    rows = [
        {"config": "A", "stratum": "syn_between", "seed": 7, "uid": "b0", "themePrec": 1.0},
        {"config": "A", "stratum": "syn_between", "seed": 7, "uid": "b1", "themePrec": None},
        {"config": "A", "stratum": "syn_noisy_paired", "seed": 7, "uid": "p0", "baseUid": "b0", "themePrec": 0.5},
        {"config": "A", "stratum": "syn_noisy_paired", "seed": 7, "uid": "p1", "baseUid": "b1", "themePrec": 0.5},
        {"config": "A", "stratum": "syn_noisy_paired", "seed": 7, "uid": "p2", "baseUid": "b9", "themePrec": 0.5},
        {"config": "A", "stratum": "syn_noisy_paired", "seed": 7, "uid": "p3", "baseUid": "b0", "themePrec": None},
    ]
    out = PC.noise_effect(rows, boot=200)
    assert len(out) == 1 and out[0]["n"] == 1          # chỉ b0 ↔ p0


def test_noise_effect_keeps_seeds_apart():
    rows = []
    for seed, (bv, pv) in ((1, (1.0, 0.5)), (2, (0.5, 0.0))):
        rows += [{"config": "A", "stratum": "syn_between", "seed": seed, "uid": "b0", "themePrec": bv},
                 {"config": "A", "stratum": "syn_noisy_paired", "seed": seed, "uid": "p0", "baseUid": "b0",
                  "themePrec": pv}]
    out = PC.noise_effect(rows, boot=200)
    # uid trùng nhau giữa hai seed; nếu không tách seed thì chỉ còn 1 cặp.
    assert out[0]["n"] == 2 and out[0]["diff"] == pytest.approx(-0.5)
