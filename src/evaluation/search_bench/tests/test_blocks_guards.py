"""06/10 — by_block / by_family / family_macro_ndcg của `aggregate`, Δ theo khối, guard Phase A (`guard_lines`, `sb guards`),
quy tắc "kết quả yếu" (`weak_grid`, `runner.weak_entries`, cache embed chỉ-đọc) và `sb compare --split` (lọc dev / test, file
phân chia dự phòng). Dòng per_query tự dựng — không Weaviate, không catalog, không git (khối rubric gắn sẵn / monkeypatch)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from evaluation.search_bench import devtest as DT, metrics as M, runner as R
from evaluation.search_bench.__main__ import app

cli = CliRunner()
K = 10


def row(qid: str, *, slice_: str = "s", block: str | None = None, family: str | None = None, ndcg: float | None = 0.5,
        recall: float | None = 0.5, **kw) -> dict:
    """Một dòng per_query đủ cột cho aggregate / aggregate_condensed / compare_rows (condensed = full)."""
    r = {"qid": qid, "slice": slice_, "expected_no_result": False, "top_ids": ["p1"], "top_scores": [0.9],
         f"recall@{K}": recall, f"ndcg@{K}": ndcg, f"mrr@{K}": 1.0, f"judged@{K}": 1.0, "recall@5": recall,
         "constraint_ok": 0, "constraint_n": 0, "filter_recall_loss": 0, "n_dup_parent": 0, "zero_result": False,
         "forbidden_hits": None, "forbidden_n": None, "direction_ok": None, "filter_pass_ok": None, "filter_pass_n": None,
         "parse_ok": None, "block": block, "family": family,
         "condensed_top_ids": ["p1"], "condensed_n": 1, "full_n": 1, f"condensed_recall@{K}": recall,
         f"condensed_ndcg@{K}": ndcg, f"condensed_mrr@{K}": 1.0, f"condensed_judged@{K}": 1.0, "condensed_recall@5": recall,
         "applied_filter": None, "latency_ms": 1.0, "extra": None}
    r.update(kw)
    return r


# ------------------------------------------------------------------ by_block / by_family
def test_aggregate_by_block_same_metrics_as_by_slice(cfg):
    rows = [row("a", block="v3", ndcg=1.0, recall=1.0, slice_="x"),
            row("b", block="v3", ndcg=0.5, recall=0.0, slice_="y", forbidden_hits=1, forbidden_n=4),
            row("c", block="v4", ndcg=0.2, recall=0.5, slice_="x", zero_result=True, top_ids=[])]
    agg = M.aggregate(rows, cfg.metrics)
    v3, v4 = agg["by_block"]["v3"], agg["by_block"]["v4"]
    assert set(v3) == set(agg["by_slice"]["x"])                       # cùng bộ khoá với by_slice
    assert v3[f"ndcg@{K}"] == pytest.approx(0.75) and v3[f"recall@{K}"] == pytest.approx(0.5) and v3["n"] == 2
    assert v3["forbidden_at_10"] == pytest.approx(0.25) and v3["zero_result"] == 0.0
    assert v4[f"ndcg@{K}"] == pytest.approx(0.2) and v4["zero_result"] == 1.0 and v4["n"] == 1
    # dòng cũ không có cột block → by_block rỗng, phần còn lại không đổi
    old = [{k: v for k, v in r.items() if k not in ("block", "family")} for r in rows]
    agg_old = M.aggregate(old, cfg.metrics)
    assert agg_old["by_block"] == {} and agg_old["overall"][f"ndcg@{K}"] == agg["overall"][f"ndcg@{K}"]


def test_by_family_and_family_macro_ndcg(cfg):
    rows = [row("q1", family="A", ndcg=1.0, recall=1.0), row("q2", family="A", ndcg=0.0, recall=0.5),   # họ A: 0.5
            row("q3", family="B", ndcg=0.9),                       # họ một câu → không vào by_family, là một họ trong macro
            row("q4", ndcg=0.3),                                   # không họ → họ riêng
            row("q5", ndcg=None, recall=None)]                     # không xác định → không vào macro
    agg = M.aggregate(rows, cfg.metrics)
    assert agg["by_family"] == {"A": {"n": 2, f"ndcg@{K}": 0.5, f"recall@{K}": 0.75, "qids": ["q1", "q2"]}}
    assert agg["overall"][f"family_macro_ndcg@{K}"] == pytest.approx((0.5 + 0.9 + 0.3) / 3)
    assert agg["overall"][f"ndcg@{K}"] == pytest.approx(2.2 / 4)   # trung bình thường vẫn như cũ
    # không có họ nào → macro = trung bình thường
    plain = [row("x", ndcg=0.2), row("y", ndcg=0.4)]
    assert M.aggregate(plain, cfg.metrics)["overall"][f"family_macro_ndcg@{K}"] == pytest.approx(0.3)


def test_condensed_aggregate_has_by_block(cfg):
    rows = [row("a", block="v3", ndcg=0.4), row("b", block="v4", ndcg=0.8)]
    cond = M.aggregate_condensed(rows, cfg.metrics)
    assert cond["mode"] == "condensed" and set(cond["by_block"]) == {"v3", "v4"}
    assert cond["by_block"]["v4"][f"ndcg@{K}"] == pytest.approx(0.8)


def test_group_delta_stats_pairs_only_defined():
    a = [row("a", block="v3", ndcg=0.5), row("b", block="v3", ndcg=None), row("c", block="v4", ndcg=0.2), row("d", ndcg=0.1)]
    b = [row("a", block="v3", ndcg=0.7), row("b", block="v3", ndcg=0.9), row("c", block="v4", ndcg=float("nan"))]
    out = M.group_delta_stats(a, b, f"ndcg@{K}", "block")
    assert out == {"v3": {"a": 0.5, "b": 0.7, "delta": pytest.approx(20.0), "n": 1}}     # b: A không xác định; c: NaN; d: không khối


def test_attach_query_meta_fills_missing_only(monkeypatch):
    monkeypatch.setattr(R, "rubric_v3_qids", lambda: frozenset({"c0001"}))
    rows = [{"qid": "c0001"}, {"qid": "c0700"}, {"qid": "c0002", "block": "v4", "family": "keep"}]
    gold = [M.GoldQuery(qid="c0001", text="t", slice="s", judgments={}, family="fam"),
            M.GoldQuery(qid="c0002", text="t", slice="s", judgments={}, family="other")]
    R.attach_query_meta(rows, gold)
    assert [(r["block"], r["family"]) for r in rows] == [("v3", "fam"), ("v4", None), ("v4", "keep")]


# ------------------------------------------------------------------ guard
PROPOSED = SimpleNamespace(forbidden_at_10_max=0.0, direction_accuracy_min=1.0, filter_pass_min=1.0, parse_accuracy_min=0.9,
                           constraint_precision_min=0.95, zero_result_in_catalog_max=0.02)


def test_shipped_guards_proposed_values(cfg):
    g = cfg.metrics.guards_proposed
    assert (g.forbidden_at_10_max, g.direction_accuracy_min, g.filter_pass_min, g.parse_accuracy_min, g.constraint_precision_min,
            g.zero_result_in_catalog_max) == (0.0, 1.0, 1.0, 0.9, 0.95, 0.02)


def test_guard_lines_on_synthetic_rows():
    rows = [
        row("q1", forbidden_hits=0, forbidden_n=10, direction_ok=1, filter_pass_ok=10, filter_pass_n=10,
            parse_ok=json.dumps({"taxonomy": True, "origin": True}), constraint_ok=10, constraint_n=10),
        row("q2", forbidden_hits=2, forbidden_n=10, direction_ok=0, filter_pass_ok=9, filter_pass_n=10,
            parse_ok=json.dumps({"taxonomy": False}), constraint_ok=9, constraint_n=10),
        row("q3", zero_result=True, top_ids=[]),                                 # trong catalog mà rỗng
        row("q4", expected_no_result=True, zero_result=False),                   # ngoài catalog vẫn có kết quả
    ]
    lines = {ln["name"]: ln for ln in M.guard_lines(rows, PROPOSED)}
    fb = lines["forbidden_at_10"]
    assert fb["value"] == pytest.approx(2 / 20) and fb["status"] == "FAIL" and fb["n"] == 2 and fb["bad"] == ["q2"]
    assert lines["forbidden_query_rate"]["value"] == 0.5 and lines["forbidden_query_rate"]["status"] == "-"
    assert lines["direction_accuracy"]["value"] == 0.5 and lines["direction_accuracy"]["status"] == "FAIL"
    assert lines["filter_pass_rate"]["value"] == pytest.approx(19 / 20) and lines["filter_pass_rate"]["bad"] == ["q2"]
    assert lines["constraint_precision"]["value"] == pytest.approx(0.95) and lines["constraint_precision"]["status"] == "PASS"
    zin = lines["zero_result_in_catalog"]
    assert zin["value"] == pytest.approx(1 / 3) and zin["status"] == "FAIL" and zin["bad"] == ["q3"] and zin["n"] == 3
    assert lines["zero_result_out_of_catalog"]["value"] == 0.0 and lines["zero_result_out_of_catalog"]["bad"] == ["q4"]
    assert lines["parse_accuracy.taxonomy"]["value"] == 0.5 and lines["parse_accuracy.taxonomy"]["status"] == "FAIL"
    assert lines["parse_accuracy.origin"]["value"] == 1.0 and lines["parse_accuracy.origin"]["status"] == "PASS"
    names = [ln["name"] for ln in M.guard_lines(rows, PROPOSED)]
    assert names.index("parse_accuracy.taxonomy") < names.index("parse_accuracy.origin")     # theo thứ tự PARSE_FIELDS


def test_guard_lines_undefined_is_na_and_pass_at_boundary():
    lines = {ln["name"]: ln for ln in M.guard_lines([row("q1"), row("q2")], PROPOSED)}
    for name in ("forbidden_at_10", "direction_accuracy", "filter_pass_rate", "constraint_precision"):
        assert lines[name]["value"] is None and lines[name]["status"] == "n/a" and lines[name]["n"] == 0
    assert not any(n.startswith("parse_accuracy.") for n in lines)
    assert lines["zero_result_in_catalog"]["status"] == "PASS"
    assert M.guard_status(1.0 - 1e-15, "min", 1.0) == "PASS" and M.guard_status(0.0, "max", 0.0) == "PASS"
    assert M.guard_status(0.5, None, None) == "-" and M.guard_status(None, "min", 1.0) == "n/a"


def _write_arm(run_id: str, arm: str, rows: list[dict], cfg, gold_version: str = "gold_v9"):
    agg = M.aggregate(rows, cfg.metrics)
    d = R.arm_dir(run_id, arm)
    res = {"arm": arm, "run_id": run_id, "gold_version": gold_version, "model": "e5-small", "text_variant": "T3+R",
           "overall": agg["overall"], "by_slice": agg["by_slice"], "n_queries": agg["n_queries"],
           "condensed": M.aggregate_condensed(rows, cfg.metrics), "needs_labels": []}
    (d / R.RESULTS).write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame(rows).to_parquet(d / R.PER_QUERY, index=False)


def test_cli_guards_reports_and_never_gates(cfg, home):
    bad = [row("q1", block="v3", forbidden_hits=1, forbidden_n=10), row("q2", block="v4", forbidden_hits=0, forbidden_n=10)]
    good = [row("q1", block="v3", forbidden_hits=0, forbidden_n=10), row("q2", block="v4", forbidden_hits=0, forbidden_n=10)]
    _write_arm("r1", "A", bad, cfg)
    _write_arm("r1", "B", good, cfg)
    res = cli.invoke(app, ["--run-id", "r1", "guards", "--arms", "A,B"])
    assert res.exit_code == 0, res.output
    assert "0.050 (n=2) FAIL" in res.output and "0.000 (n=2) PASS" in res.output
    assert "A · forbidden_at_10 trượt ở 1 câu: q1" in res.output
    assert cli.invoke(app, ["--run-id", "r1", "guards", "--arms", "A,ZZ"]).exit_code == 2
    assert cli.invoke(app, ["--run-id", "r1", "guards", "--arms", "A", "--split", "nope"]).exit_code == 2


# ------------------------------------------------------------------ weak results
def test_is_weak_and_weak_grid():
    assert M.is_weak(0.69, 0.10, 0.70, 0.06) and M.is_weak(0.80, 0.05, 0.70, 0.06) and not M.is_weak(0.80, 0.07, 0.70, 0.06)
    assert not M.is_weak(None, None, 0.70, 0.06)                      # rỗng: không phải "yếu", đếm riêng
    assert not M.is_weak(0.80, None, 0.70, 0.06) and M.is_weak(0.65, None, 0.70, 0.06)   # thiếu margin → chỉ xét topScore
    entries = [{"qid": "o1", "ooc": True, "top": 0.85, "margin": 0.04}, {"qid": "o2", "ooc": True, "top": None, "margin": None},
               {"qid": "i1", "ooc": False, "top": 0.88, "margin": 0.08}, {"qid": "i2", "ooc": False, "top": 0.84, "margin": 0.05},
               {"qid": "i3", "ooc": False, "top": None, "margin": None}, {"qid": "i4", "ooc": False, "top": 0.9, "margin": None}]
    g = M.weak_grid(entries, [0.70, 0.86], [0.0, 0.06])
    cells = {(c["top"], c["margin"]): (c["ooc_suppressed"], c["in_weak"]) for c in g["cells"]}
    assert cells == {(0.70, 0.0): (1, 0), (0.70, 0.06): (2, 1), (0.86, 0.0): (2, 1), (0.86, 0.06): (2, 1)}
    assert (g["n_ooc"], g["n_in"], g["n_ooc_empty"], g["n_in_empty"], g["n_no_margin"]) == (2, 4, 1, 1, 1)


def test_weak_entries_background_margin_and_text_key():
    docs = np.array([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]], dtype=np.float32)
    gold = {"q1": M.GoldQuery(qid="q1", text="  câu   một ", slice="s", judgments={}),
            "q2": M.GoldQuery(qid="q2", text="câu hai", slice="s", judgments={})}
    rows = [row("q1", top_scores=[0.7, 0.95], extra=json.dumps({"topScore": 0.97})),
            row("q2", top_scores=[0.8], expected_no_result=True, extra=json.dumps({"normalizedQuery": "cau  hai"})),
            row("q3", top_scores=[])]
    qv = {"câu một": np.array([2.0, 0.0], dtype=np.float32), "cau hai": np.array([0.0, 1.0], dtype=np.float32)}
    e1, e2, e3 = R.weak_entries(rows, gold, docs, qv)
    # q1: vector (1, 0) → cosine [1, 0, 0.6] → trung vị 0.6; top = max top_scores 0.95
    assert e1["text"] == "câu một" and e1["background"] == pytest.approx(0.6) and e1["top"] == pytest.approx(0.95)
    assert e1["margin"] == pytest.approx(0.35) and e1["diag_top"] == pytest.approx(0.97) and not e1["ooc"]
    # q2: khoá = normalizedQuery sau gộp khoảng trắng; vector (0, 1) → [0, 1, 0.8] → 0.8
    assert e2["text"] == "cau hai" and e2["background"] == pytest.approx(0.8) and e2["ooc"]
    assert e3["top"] is None and e3["margin"] is None and e3["background"] is None      # rỗng, không có trong gold
    d1 = R.weak_entries(rows[:1], gold, docs, qv, top_source="diagnostics")[0]
    assert d1["top"] == pytest.approx(0.97) and d1["margin"] == pytest.approx(0.37)


def test_query_vectors_from_cache_readonly(cfg, tmp_path):
    from evaluation.search_bench.embed import EmbeddingCache, cache_key, embedder_name
    p = tmp_path / "embeddings.sqlite"
    c = EmbeddingCache(p)
    name = embedder_name(cfg, "e5-small")                    # không nạp model
    v = np.arange(4, dtype=np.float32)
    c.put_many([(cache_key(name, "query", "khách sạn Huế"), name, "query", v),
                (cache_key(name, "document", "khách sạn Đà Lạt"), name, "document", v)])
    c.close()
    got = R.query_vectors_from_cache(cfg, "e5-small", ["khách sạn Huế", "khách sạn Đà Lạt", "khách sạn Huế"], cache_path=p)
    assert list(got) == ["khách sạn Huế"] and np.array_equal(got["khách sạn Huế"], v)    # document không phải query
    assert R.query_vectors_from_cache(cfg, "e5-small", ["x"], cache_path=tmp_path / "none.sqlite") == {}


# ------------------------------------------------------------------ dev/test split cho compare
def _split_file(d, version: str, assignment: dict[str, str]):
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"devtest@{version}.json"
    p.write_text(json.dumps({"gold_version": version, "assignment": assignment}), encoding="utf-8")
    return p


def test_resolve_split_explicit_version_and_fallback(tmp_path):
    sd = tmp_path / "splits"
    _split_file(sd, "gold_v3", {"q1": "dev", "q2": "test"})
    _split_file(sd, "gold_v4", {"q1": "dev", "q2": "test", "q3": "dev"})
    _split_file(sd, "gold_v10", {"q1": "dev"})                       # mới nhất nhưng không phủ q2
    data, p, note = R.resolve_split("gold_v3", {"q1", "q2"}, splits_dir=sd)
    assert p.name == "devtest@gold_v3.json" and note is None
    data, p, note = R.resolve_split("fixture:x", {"q1", "q2"}, splits_dir=sd)
    assert p.name == "devtest@gold_v4.json" and "chưa có file phân chia" in note    # v10 không phủ đủ → v4 (mới nhất phủ đủ)
    explicit = _split_file(tmp_path / "other", "gold_v99", {"q1": "test", "q2": "dev"})
    data, p, note = R.resolve_split("gold_v3", {"q1", "q2"}, split_file=explicit, splits_dir=sd)
    assert p == explicit and data["assignment"]["q1"] == "test" and note is None
    with pytest.raises(DT.DevTestError, match="--split-file"):
        R.resolve_split(None, {"q1", "q9"}, splits_dir=sd)
    with pytest.raises(DT.DevTestError, match="không thấy --split-file"):
        R.resolve_split("gold_v3", {"q1"}, split_file=tmp_path / "missing.json", splits_dir=sd)


def test_cli_compare_split_filters_both_arms(cfg, home, tmp_path, monkeypatch):
    sd = tmp_path / "splits"
    monkeypatch.setattr(DT, "SPLITS_DIR", sd)
    _split_file(sd, "gold_v9", {"q1": "dev", "q2": "dev", "q3": "test", "q4": "test"})
    a = [row(q, block=b, ndcg=0.5, recall=0.5) for q, b in (("q1", "v3"), ("q2", "v4"), ("q3", "v3"), ("q4", "v4"))]
    b = [row("q1", block="v3", ndcg=0.9, recall=0.9), row("q2", block="v4", ndcg=0.9, recall=0.9),
         row("q3", block="v3", ndcg=0.1, recall=0.1), row("q4", block="v4", ndcg=0.1, recall=0.1)]
    _write_arm("r1", "A", a, cfg)
    _write_arm("r1", "B", b, cfg)
    full = cli.invoke(app, ["--run-id", "r1", "compare", "A", "B"])
    assert full.exit_code == 0, full.output
    assert "split" not in full.output.split("\n")[0] and "theo khối rubric" in full.output
    dev = cli.invoke(app, ["--run-id", "r1", "compare", "A", "B", "--split", "dev"])
    assert dev.exit_code == 0, dev.output
    assert "split dev (devtest@gold_v9.json, 2 câu)" in dev.output and "+40.00" in dev.output and "-40.00" not in dev.output
    test = cli.invoke(app, ["--run-id", "r1", "compare", "A", "B", "--split", "test", "--condensed"])
    assert test.exit_code == 0, test.output
    assert "split test (devtest@gold_v9.json, 2 câu)" in test.output and "-40.00" in test.output and "+40.00" not in test.output
    # bảng theo khối trên phần test: mỗi khối 1 cặp
    assert "1 (cặp 1)" in test.output
    assert cli.invoke(app, ["--run-id", "r1", "compare", "A", "B", "--split", "nope"]).exit_code == 2


def test_cli_compare_split_fallback_note_for_untagged_gold(cfg, home, tmp_path, monkeypatch):
    sd = tmp_path / "splits"
    monkeypatch.setattr(DT, "SPLITS_DIR", sd)
    _split_file(sd, "gold_v9", {"q1": "dev", "q2": "test"})
    rows = [row("q1", block="v3"), row("q2", block="v4")]
    _write_arm("r1", "A", rows, cfg, gold_version="untagged")
    _write_arm("r1", "B", rows, cfg, gold_version="untagged")
    res = cli.invoke(app, ["--run-id", "r1", "compare", "A", "B", "--split", "dev"])
    assert res.exit_code == 0, res.output
    assert "chưa có file phân chia — dùng devtest@gold_v9.json" in res.output and "1 câu" in res.output
    other = _split_file(tmp_path / "x", "gold_v1", {"q1": "test", "q2": "test"})
    res = cli.invoke(app, ["--run-id", "r1", "compare", "A", "B", "--split", "test", "--split-file", str(other)])
    assert res.exit_code == 0 and "split test (devtest@gold_v1.json, 2 câu)" in res.output, res.output


def test_cli_weak_results_smoke(cfg, home, tmp_path, monkeypatch):
    from evaluation.search_bench import paths, vectors
    from evaluation.search_bench.embed import EmbeddingCache, cache_key, embedder_name
    gold_p = tmp_path / "gold.jsonl"
    gold_p.write_text("".join(json.dumps({"qid": q, "text": t, "slice": s, "judgments": {"d1": 2}}, ensure_ascii=False) + "\n"
                              for q, t, s in (("q1", "khách sạn Huế", "dest_type"), ("q2", "resort Bạc Liêu", "out_of_catalog"))),
                      encoding="utf-8")
    monkeypatch.setattr(paths, "GOLD_JSONL", gold_p)
    docs = np.array([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]], dtype=np.float32)
    vectors.write("jsonl", "T3+R", "e5-small", "document", ["d1", "d2", "d3"], docs,
                  extra={"cache_model": "intfloat/multilingual-e5-small"})
    c = EmbeddingCache(paths.cache_dir() / paths.EMBED_CACHE)
    name = embedder_name(cfg, "e5-small")
    c.put_many([(cache_key(name, "query", "khách sạn Huế"), name, "query", np.array([1.0, 0.0], dtype=np.float32)),
                (cache_key(name, "query", "resort Bạc Liêu"), name, "query", np.array([0.0, 1.0], dtype=np.float32))])
    c.close()
    _write_arm("r1", "A", [row("q1", top_scores=[0.95]), row("q2", top_scores=[0.82], expected_no_result=True)], cfg)
    res = cli.invoke(app, ["--run-id", "r1", "weak-results", "--arm", "A", "--top-grid", "0.7,0.9", "--margin-grid", "0,0.06"])
    assert res.exit_code == 0, res.output
    assert "vector truy vấn từ cache embed: 2/2 câu" in res.output and "model e5-small" in res.output
    # q2 (ngoài catalog): nền = trung vị [0, 1, 0.8] = 0.8 → margin 0.02 → bị chặn khi M = 0.06; q1: margin 0.35
    assert "0.020" in res.output and "1 · 0" in res.output
    bad = cli.invoke(app, ["--run-id", "r1", "weak-results", "--arm", "A", "--model", "e5-base"])
    assert bad.exit_code == 2                                           # chưa có vector document của e5-base
