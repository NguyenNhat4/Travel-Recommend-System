"""Test metrics.py + paired bootstrap trên fixture tay (checklist ngày 2, Người A, việc 3).

- `fixtures/gold_small.jsonl`: 10 query nhãn giả trên 26 search unit của products-sample.jsonl (người dùng duyệt 24/09).
- `fixtures/run_small.json`: top_ids giả của hai arm A, B (B = A trừ q001, q007, q010).
Số kỳ vọng ghi cứng, tính tay độc lập (không gọi metrics.py) — phép tính ở comment. log2(rank + 1): hạng 1 → 1,
hạng 2 → 1,5849625, hạng 3 → 2, hạng 4 → 2,3219281, hạng 6 → 2,8073549, hạng 7 → 3, hạng 8 → 3,1699250.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.search_bench import catalog, metrics as M, paths
from evaluation.search_bench.store import filters as F

FX = Path(__file__).parent / "fixtures"
APPROX = dict(rel=0, abs=1e-12)


@pytest.fixture(scope="module")
def ctx_data(cfg, tmp_path_factory):
    import os
    old = os.environ.get("SBENCH_HOME")
    os.environ["SBENCH_HOME"] = str(tmp_path_factory.mktemp("sbench"))
    try:
        catalog.build_catalog(cfg, "sample")
        items = catalog.read_items("sample").set_index("product_id", drop=False)
        key_to_id = F.amenity_key_index(json.loads((paths.data_dir("sample") / paths.AMENITY_VOCAB).read_text(encoding="utf-8")))
    finally:
        if old is None:
            os.environ.pop("SBENCH_HOME", None)
        else:
            os.environ["SBENCH_HOME"] = old
    gold = M.load_gold(FX / "gold_small.jsonl")
    run = json.loads((FX / "run_small.json").read_text(encoding="utf-8"))
    return gold, run, M.EvalContext(cfg.metrics, items, key_to_id)


def rows_of(ctx_data, arm: str) -> list[dict]:
    gold, run, ctx = ctx_data
    ids = run["ids"]
    applied = run.get("applied_filter", {}).get(arm, {})
    return [M.evaluate_query(g, [ids[n] for n in run["arms"][arm][g.qid]], ctx, applied_filter=applied.get(g.qid)) for g in gold]


def by_qid(rows):
    return {r["qid"]: r for r in rows}


# ------------------------------------------------------------------ fixture hợp lệ
def test_fixture_is_valid_gold(ctx_data):
    gold, run, ctx = ctx_data
    assert [g.qid for g in gold] == [f"q{i:03d}" for i in range(1, 11)]
    assert all(p in ctx.items.index for g in gold for p in g.judgments)
    assert all(any(v == 2 for v in g.judgments.values()) for g in gold if not g.expected_no_result)
    assert set(run["arms"]["A"]) == set(run["arms"]["B"]) == {g.qid for g in gold}
    assert all(p in ctx.items.index for p in run["ids"].values())


# ------------------------------------------------------------------ 3 query tính tay (spec Part 8 "Done khi")
def test_hand_q001_normal(ctx_data):
    r = by_qid(rows_of(ctx_data, "A"))["q001"]
    # nhãn theo hạng: [0, 2, 0, 1, –, 2, –, –, –, –]; liên quan (rel ≥ 1) = {bay, beachfront, vinwonders, golf} → 4
    assert r["recall@10"] == pytest.approx(3 / 4, **APPROX)            # bay, vinwonders, beachfront
    assert r["recall@5"] == pytest.approx(2 / 4, **APPROX)             # bay (h2), vinwonders (h4)
    # DCG = 3/log2(3) + 1/log2(5) + 3/log2(7) = 1,8927893 + 0,4306766 + 1,0686216 = 3,3920874
    # IDCG (lý tưởng 2,2,1,1) = 3/1 + 3/log2(3) + 1/2 + 1/log2(5) = 5,8234658 → nDCG = 0,5824860
    assert r["ndcg@10"] == pytest.approx(0.5824860118811416, **APPROX)
    assert r["mrr@10"] == pytest.approx(1 / 2, **APPROX)               # nhãn 2 đầu tiên ở hạng 2
    assert r["judged@10"] == pytest.approx(5 / 10, **APPROX)           # hl_resort, bay, hontam, vinwonders, beachfront
    assert r["ranks_of_relevant"] == [2, 4, 6]


def test_hand_q004_recall5_vs_10_and_judged(ctx_data):
    r = by_qid(rows_of(ctx_data, "A"))["q004"]
    # 3 VinWonders (nhãn 2) ở hạng 2, 4, 7
    assert r["recall@10"] == pytest.approx(1.0, **APPROX)
    assert r["recall@5"] == pytest.approx(2 / 3, **APPROX)
    # DCG = 3/log2(3) + 3/log2(5) + 3/log2(8) = 1,8927893 + 1,2920297 + 1 = 4,1848189
    # IDCG = 3/1 + 3/log2(3) + 3/log2(4) = 6,3927893 → 0,6546155
    assert r["ndcg@10"] == pytest.approx(0.6546154994739984, **APPROX)
    assert r["mrr@10"] == pytest.approx(1 / 2, **APPROX)
    assert r["judged@10"] == pytest.approx(4 / 10, **APPROX)           # hontam (nhãn 0) + 3 VinWonders


def test_hand_q007_constraint_and_filter_loss(ctx_data):
    a, b = by_qid(rows_of(ctx_data, "A"))["q007"], by_qid(rows_of(ctx_data, "B"))["q007"]
    # filter (Phú Quốc ∧ kids_club ∧ giá ≤ 3tr) chỉ khớp Fiesta; A trả 5 kết quả → 1/5 thoả
    assert (a["constraint_ok"], a["constraint_n"]) == (1, 5)
    # A: [resort(1), fiesta(2), vinwonders(0), –, –]; DCG = 1 + 3/log2(3) = 2,8927893; IDCG = 3 + 1/log2(3) = 3,6309298
    assert a["ndcg@10"] == pytest.approx(0.7967075809905066, **APPROX)
    assert a["recall@10"] == pytest.approx(1.0, **APPROX) and a["mrr@10"] == pytest.approx(1 / 2, **APPROX)
    # B lọc cứng → chỉ còn Fiesta: thoả 1/1, resort (nhãn 1, giá 5tr) bị filter loại → filter_recall_loss = 1
    assert (b["constraint_ok"], b["constraint_n"]) == (1, 1)
    assert b["filter_recall_loss"] == 1 and a["filter_recall_loss"] == 0
    assert b["recall@10"] == pytest.approx(1 / 2, **APPROX)
    assert b["ndcg@10"] == pytest.approx(0.8262346571285599, **APPROX)   # 3 / 3,6309298


# ------------------------------------------------------------------ các nhánh còn lại
def test_branches(ctx_data):
    r = by_qid(rows_of(ctx_data, "A"))
    assert (r["q002"]["ndcg@10"], r["q002"]["mrr@10"], r["q002"]["recall@10"]) == (1.0, 1.0, 1.0)      # hoàn hảo
    assert (r["q003"]["recall@10"], r["q003"]["ndcg@10"], r["q003"]["mrr@10"]) == (0.0, 0.0, 0.0)      # 0 hợp lệ
    assert r["q005"]["judged@10"] == pytest.approx(2 / 4, **APPROX)                                      # 4 kết quả
    assert r["q005"]["ndcg@10"] == pytest.approx(0.7002755876478819, **APPROX)
    q6 = r["q006"]
    assert q6["zero_result"] and q6["judged@10"] is None and q6["recall@10"] == 0.0                     # 0 kết quả
    q9 = r["q009"]
    assert q9["zero_result"] and q9["recall@10"] is None and q9["ndcg@10"] is None and q9["mrr@10"] is None
    # q008: filter phủ định — bay, vinwonders, golf, hontam (không ghi nhận amenity) thoả; beachfront (có kids club),
    # hl_resort (Hạ Long) không → 4/6
    assert (r["q008"]["constraint_ok"], r["q008"]["constraint_n"]) == (4, 6)


def test_aggregate_arm_a(ctx_data, cfg):
    agg = M.aggregate(rows_of(ctx_data, "A"), cfg.metrics)
    o = agg["overall"]
    # recall@10 trên 9 query xác định (q009 bị loại): (0,75+1+0+1+2/3+0+1+1+1)/9
    assert o["recall@10"] == pytest.approx(0.7129629629629629, **APPROX)
    assert o["recall@5"] == pytest.approx(0.6481481481481481, **APPROX)     # (0,5+1+0+2/3+2/3+0+1+1+1)/9
    assert o["ndcg@10"] == pytest.approx(0.555104909681827, **APPROX)
    assert o["mrr@10"] == pytest.approx(4 / 9, **APPROX)                    # 0,5·7 + 1 + 0·… → 4/9
    assert o["judged@10"] == pytest.approx(3.4 / 8, **APPROX)               # q006, q009 không có kết quả → loại
    assert o["constraint_precision"] == pytest.approx(5 / 11, **APPROX)     # (1 + 4) / (5 + 6)
    assert o["filter_recall_loss"] == 0 and o["parent_dup_rate"] == 0.0
    assert o["zero_result_in_catalog"] == pytest.approx(1 / 9, **APPROX)    # q006
    assert o["zero_result_out_of_catalog"] == 1.0                            # q009
    assert agg["n_defined"] == {"recall@10": 9, "ndcg@10": 9, "mrr@10": 9, "judged@10": 8, "recall@5": 9}
    ds = agg["by_slice"]["dest_type"]                                        # q001 + q003
    assert ds["n"] == 2 and ds["recall@10"] == pytest.approx(0.375, **APPROX)
    assert ds["ndcg@10"] == pytest.approx(0.5824860118811416 / 2, **APPROX)


def test_retired_queries_are_skipped(tmp_path):
    lines = (FX / "gold_small.jsonl").read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0]) | {"status": "retired"}
    p = tmp_path / "g.jsonl"
    p.write_text("\n".join([json.dumps(first, ensure_ascii=False), *lines[1:]]), encoding="utf-8")
    assert len(M.load_gold(p)) == 9 and len(M.load_gold(p, include_retired=True)) == 10


# ------------------------------------------------------------------ bootstrap / so hai arm
def test_self_compare_is_zero_and_half(ctx_data, cfg):
    a = rows_of(ctx_data, "A")
    out = M.compare_rows(a, a, cfg.metrics, seed=cfg.run.seed)
    for m in ("recall@10", "ndcg@10"):
        assert out[m]["delta"] == 0.0 and out[m]["p_one_sided"] == 0.5 and out[m]["ci95"] == [0.0, 0.0]
        assert out[m]["n"] == 9 and out[m]["n_dropped"] == 1            # q009 không xác định → loại khỏi cặp
    assert out["verdict"] == "TIE"


def test_compare_a_vs_b(ctx_data, cfg):
    out = M.compare_rows(rows_of(ctx_data, "A"), rows_of(ctx_data, "B"), cfg.metrics, seed=cfg.run.seed)
    r, n = out["recall@10"], out["ndcg@10"]
    assert r["delta"] == pytest.approx((25 - 50) / 9, **APPROX)          # q001 +25, q007 −50 (điểm)
    # Δndcg (điểm): q001 +5,4171328, q007 +2,9527076, q010 +36,9070246 → tổng 45,2768651 / 9
    assert n["delta"] == pytest.approx(5.030762783728682, abs=1e-9)
    assert r["ci95"][0] <= r["delta"] <= r["ci95"][1] and n["ci95"][0] <= n["delta"] <= n["ci95"][1]
    assert out["slice_delta_ndcg"]["dest_type"] == pytest.approx(2.7085663984492747, abs=1e-9)
    assert out["slice_delta_ndcg"]["abbrev_typo"] == pytest.approx(36.907024642854, abs=1e-9)
    # win_rule theo đúng chữ spec: Δrecall < 2 → không WIN; |Δndcg| 5,03 ≥ 2 → không TIE → LOSE
    assert out["verdict"] == "LOSE"
    again = M.compare_rows(rows_of(ctx_data, "A"), rows_of(ctx_data, "B"), cfg.metrics, seed=cfg.run.seed)
    assert again["recall@10"] == r and again["ndcg@10"] == n            # cùng seed → cùng kết quả


def test_bootstrap_clear_improvement():
    a = {f"q{i}": 0.5 for i in range(20)}
    b = {f"q{i}": 0.5 + 0.05 * (1 + i % 3) for i in range(20)}              # mọi Δ > 0
    out = M.paired_bootstrap(a, b, n_boot=1000, seed=42)
    assert out["p_one_sided"] < 0.05 and out["ci95"][0] > 0
    assert out["delta"] == pytest.approx(sum(5 * (1 + i % 3) for i in range(20)) / 20, abs=1e-9)
    empty = M.paired_bootstrap({"q": None}, {"q": 0.5}, n_boot=10, seed=1)
    assert empty["delta"] is None and empty["n"] == 0 and empty["n_dropped"] == 1


def test_win_verdict_branches(cfg):
    rule = cfg.metrics.win_rule
    assert M.win_verdict({"delta": 3.0, "p_one_sided": 0.01}, {"delta": 2.5}, {"dest_type": -1.0}, rule)[0] == "WIN"
    assert M.win_verdict({"delta": 3.0, "p_one_sided": 0.01}, {"delta": 2.5}, {"no_diacritics": -4.0}, rule)[0] == "LOSE"
    assert M.win_verdict({"delta": 3.0, "p_one_sided": 0.2}, {"delta": 1.0}, {}, rule)[0] == "TIE"       # p không đạt
    assert M.win_verdict({"delta": 0.5, "p_one_sided": 0.3}, {"delta": -1.5}, {}, rule)[0] == "TIE"


# ------------------------------------------------------------------ hub_score, dup parent (danh sách tự dựng)
def test_hub_scores():
    # 2 query × top-2 trên 4 sản phẩm → kỳ vọng mỗi sản phẩm xuất hiện 2·2/4 = 1 lần; "a" xuất hiện 2 lần → 2,0
    hs = M.hub_scores([["a", "b"], ["a", "c"]], n_items=4, depth=2)
    assert hs == {"a": 2.0, "b": 1.0, "c": 1.0}
    assert M.hub_scores([], n_items=4, depth=2) == {}


def test_dup_parent_count():
    parent = {"r1": "H1", "r2": "H1", "r3": "H1", "r4": "H2", "p": None, "n1": float("nan"), "n2": float("nan"), "e": ""}
    assert M.dup_parent_count(["r1", "r2", "r3", "r4", "p"], parent, 10) == 2      # H1 có 3 → vượt 2
    assert M.dup_parent_count(["p", "n1", "n2", "e"], parent, 10) == 0             # NaN của parquet không phải cha
    assert M.dup_parent_count(["r1", "r2", "r3"], parent, 2) == 1                   # chỉ xét top-k
