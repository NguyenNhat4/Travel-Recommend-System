"""Day 5 (05/10): chia gold dev/test phân tầng theo slice (devtest.py) và regression gọn (regress.py) — không cần Weaviate."""
from __future__ import annotations

from collections import Counter

import pytest

from evaluation.search_bench import devtest as DT, regress as RG
from evaluation.search_bench.metrics import GoldQuery


def _gold(sizes: dict[str, int]) -> list[GoldQuery]:
    return [GoldQuery(qid=f"{s}{i:02d}", text=f"câu {s} {i}", slice=s, judgments={"p": 2})
            for s, n in sizes.items() for i in range(n)]


# ------------------------------------------------------------------ devtest
def test_split_is_stratified_balanced_and_deterministic():
    gold = _gold({"a": 10, "b": 7, "c": 3, "d": 1})
    one, two = DT.make_split(gold, seed=42), DT.make_split(gold, seed=42)
    assert one == two and set(one) == {g.qid for g in gold}
    per = Counter((g.slice, one[g.qid]) for g in gold)
    for s, n in {"a": 10, "b": 7, "c": 3, "d": 1}.items():
        assert abs(per[(s, "dev")] - per[(s, "test")]) <= 1            # mỗi slice chia gần đôi
    n = Counter(one.values())
    assert abs(n["dev"] - n["test"]) <= 1                              # tổng lệch ≤ 1 nhờ câu dư vào bên ít hơn
    assert DT.make_split(gold, seed=7) != one                          # seed khác → chia khác


def test_write_refuses_overwrite_and_filter_rows(tmp_path):
    gold = _gold({"a": 4, "b": 2})
    data = DT.build_file(gold, gold_version="gold_v9", gold_sha256="x" * 64, seed=1)
    assert data["n_dev"] + data["n_test"] == 6 and data["by_slice"]["a"] == {"dev": 2, "test": 2}
    p = DT.write(data, splits_dir=tmp_path)
    assert p.name == "devtest@gold_v9.json" and DT.load("gold_v9", splits_dir=tmp_path)["assignment"] == data["assignment"]
    with pytest.raises(DT.DevTestError, match="cố định"):
        DT.write(data, splits_dir=tmp_path)
    rows = [{"qid": g.qid} for g in gold]
    dev = DT.filter_rows(rows, data, "dev")
    assert {r["qid"] for r in dev} == {q for q, s in data["assignment"].items() if s == "dev"}
    assert DT.filter_rows(rows, data, "all") == rows
    with pytest.raises(DT.DevTestError, match="không có trong phân chia"):
        DT.filter_rows(rows + [{"qid": "moi"}], data, "test")


# ------------------------------------------------------------------ regress
TH = RG.Thresholds(metrics=("ndcg@10", "recall@10"), max_drop_overall=1.0, max_drop_slice=3.0, worst_n=5)


def _rows(vals: dict[str, tuple[str, float]]) -> list[dict]:
    return [{"qid": q, "slice": s, "top_ids": [f"{q}-{v}"], "ndcg@10": v, "recall@10": v} for q, (s, v) in vals.items()]


def _results(run_id="r1", arm="APP.x", gold="gold_v3", h="h1"):
    return {"arm": arm, "run_id": run_id, "resolved_config_hash": h, "model": "e5-small", "gold_version": gold,
            "gold_sha256": "g", "n_items": 3, "k": 10, "overall": {"ndcg@10": 0.5, "recall@10": 0.5},
            "by_slice": {"s1": {"ndcg@10": 0.5, "recall@10": 0.5, "n": 2}}}


BASE_ROWS = {"q1": ("s1", 0.8), "q2": ("s1", 0.6), "q3": ("s2", 0.4), "q4": ("s2", 0.2)}


def _baseline():
    return RG.make_baseline(_results(), _rows(BASE_ROWS), TH, items_sha256="i", note="mốc thử")


def test_baseline_against_itself_passes_with_zero_delta():
    base = _baseline()
    rep = RG.check(base, _results(run_id="r2"), _rows(BASE_ROWS), TH)
    assert rep["status"] == "PASS" and rep["n_top_ids_changed"] == 0
    assert all(ln["delta"] == pytest.approx(0.0) for ln in rep["lines"])


def test_drop_in_one_slice_fails_and_lists_worst_query():
    cur = dict(BASE_ROWS, q3=("s2", 0.3))                     # s2: −5 điểm (> 3), overall: −2,5 (> 1)
    rep = RG.check(_baseline(), _results(run_id="r2", h="h2"), _rows(cur), TH)
    assert rep["status"] == "FAIL" and any(f.startswith("s2 ndcg@10") for f in rep["failures"])
    assert rep["worst"][0]["qid"] == "q3" and rep["warnings"]       # config hash đổi → cảnh báo, không chặn


def test_split_qids_limit_comparison():
    cur = dict(BASE_ROWS, q3=("s2", 0.3))
    rep = RG.check(_baseline(), _results(run_id="r2"), _rows(cur), TH, qids={"q1", "q2"})
    assert rep["status"] == "PASS" and rep["n_queries"] == 2


def test_not_comparable_cases():
    with pytest.raises(RG.RegressError, match="gold khác"):
        RG.check(_baseline(), _results(gold="gold_v4"), _rows(BASE_ROWS), TH)
    with pytest.raises(RG.RegressError, match="arm khác"):
        RG.check(_baseline(), _results(arm="APP.y"), _rows(BASE_ROWS), TH)
    with pytest.raises(RG.RegressError, match="note"):
        RG.make_baseline(_results(), _rows(BASE_ROWS), TH, items_sha256="i", note=" ")
    with pytest.raises(RG.RegressError, match="gold_version"):
        RG.make_baseline(_results(gold=None), _rows(BASE_ROWS), TH, items_sha256="i", note="x")
