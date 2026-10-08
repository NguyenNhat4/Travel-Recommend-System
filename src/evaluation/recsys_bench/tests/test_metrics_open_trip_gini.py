"""Day 4 R2 / R6 (01/10): Gini độ phủ, cross-category theo chuyến mở (hai biến thể), paired bootstrap, so cặp, report —
số tính tay trên `small_index()` (a hotel NT recommendable; b attraction NT recommendable, hết chỗ; c flight ĐN không
recommendable) và fixture `world` / `events` của conftest."""
from __future__ import annotations

import json

import numpy as np
import pytest

from src.evaluation.recsys_bench.arms import EngineArm, RandomArm
from src.evaluation.recsys_bench.bench import evaluate, open_trip_taxonomies
from src.evaluation.recsys_bench.ceiling import engine_view
from src.evaluation.recsys_bench.engine import OfflineEngine
from src.evaluation.recsys_bench.events import filter_events
from src.evaluation.recsys_bench.metrics import OPEN_TRIP_EMPTY, gini, paired_bootstrap, score
from src.evaluation.recsys_bench.splits import leave_last_booking_out
from src.evaluation.recsys_bench.tests.test_arms_metrics import AS_OF, small_index


def test_gini_hand_values():
    assert abs(gini([2, 1]) - 1 / 6) < 1e-12 and gini([1, 0]) == 0.5 and gini(np.array([1, 0])) == 0.5
    assert gini([5]) == 0.0 and gini([]) == 0.0 and gini([1, 1, 1, 1]) == 0.0 and gini([0, 0, 10]) > 0.6
    from src.evaluation.recsys_bench import sanity as S     # tên cũ vẫn dùng được
    assert S.gini is gini


def test_exposure_gini_counts_every_recommendable_unit_including_zero():
    idx = small_index()
    # recommendable = {a, b}; a xuất hiện 2 lần, b 1 lần → Gini([2, 1]) = 1/6
    m = score({"u1": ["a", "b"], "u2": ["a"]}, {"u1": "a", "u2": "a"}, {}, idx)
    assert abs(m["exposure_gini"] - 1 / 6) < 1e-12
    # chỉ a → [1, 0] → 0,5 (b không được gợi lần nào vẫn vào mẫu số)
    assert score({"u1": ["a"]}, {"u1": "a"}, {}, idx)["exposure_gini"] == 0.5
    # c không recommendable, x1 ngoài catalog → không có exposure trên tập recommendable → 0,0
    assert score({"u1": ["c", "x1"]}, {"u1": "a"}, {}, idx)["exposure_gini"] == 0.0
    assert score({}, {}, {}, idx)["exposure_gini"] == 0.0


def test_cross_category_open_trip_two_variants_and_denominators():
    idx = small_index()
    recs = {"u1": ["a", "b"], "u2": ["a"], "u3": ["a"]}
    targets = {"u1": "a", "u2": "a", "u3": "a"}
    open_trip = {"u1": {"hotel"}, "u2": None, "u3": set()}      # u1 mở + đã mua hotel; u2 không có chuyến mở; u3 mở chỉ view
    m = score(recs, targets, {}, idx, open_trip=open_trip)
    # biến thể 1 (mọi khách có chuyến mở): u1 → a hotel không cross, b attraction cross; u3 → a cross (tập đã mua rỗng) = 2/3
    assert abs(m["cross_category_open_trip"] - 2 / 3) < 1e-12 and m["users_open_trip"] == 2
    # biến thể 2 (chuyến mở đã mua ≥ 1 món): chỉ u1 → 1/2
    assert m["cross_category_open_trip_bought"] == 0.5 and m["users_open_trip_bought"] == 1
    # cột cũ không đổi nghĩa: bought = {} → mọi item cross; availability a=1, b=0 trên 4 item
    assert m["cross_category_rate"] == 1.0 and m["availability_precision"] == 0.75 and m["users"] == 3
    # không truyền open_trip / khách thiếu khoá → coi như không có chuyến mở; khoá luôn có mặt
    none = score(recs, targets, {}, idx)
    assert {k: none[k] for k in OPEN_TRIP_EMPTY} == OPEN_TRIP_EMPTY
    assert {k: score({}, {}, {}, idx)[k] for k in OPEN_TRIP_EMPTY} == OPEN_TRIP_EMPTY
    only_u2 = score(recs, targets, {}, idx, open_trip={"u2": None})
    assert {k: only_u2[k] for k in OPEN_TRIP_EMPTY} == OPEN_TRIP_EMPTY
    with pytest.raises(TypeError):          # keyword-only: không được truyền vị trí
        score(recs, targets, {}, idx, None, open_trip)      # noqa: B026


def test_evaluate_computes_views_itself_and_matches_explicit_views(world, events):
    index = world["index"]
    kept, _ = filter_events(events, index, AS_OF)
    split = leave_last_booking_out(kept, index)
    views = {u: engine_view(split.train_by_user[u], index, split.as_of_by_user[u]) for u in split.targets}
    auto, _ = evaluate(RandomArm(index, 42), split, index, k=20)
    explicit, _ = evaluate(RandomArm(index, 42), split, index, k=20, views=views)
    strip = lambda row: {k: v for k, v in row.items() if not k.endswith("_runtime_ms")}     # noqa: E731 — thời gian đo khác nhau
    assert strip(auto) == strip(explicit)
    assert set(OPEN_TRIP_EMPTY) | {"exposure_gini"} <= set(auto)
    assert 0.0 <= auto["exposure_gini"] <= 1.0 and auto["users"] == 4
    # Chuyến mở tại as_of (luật M6): u1 → chuyến đã đặt T1 (hotel) đứng trước view lẻ A1 đến sau (FR-REC-02, 09/10; trước đó
    # view lẻ chiếm chỗ → ∅, lỗi I-3); u2 → T2 đã qua
    # usingDate và > 14 ngày → None; u5 → T6 (G1 01/04, usingDate 16/05 ≥ as_of 10/05) mở, đã mua golf; VP0000001 → view lẻ R1.
    ot = open_trip_taxonomies(views)
    assert ot["u1"] == {"hotel"} and ot["u2"] is None and ot["u5"] == {"golf"} and ot["VP0000001"] == set()
    assert auto["users_open_trip"] == 3 and auto["users_open_trip_bought"] == 2
    engine_row, _ = evaluate(EngineArm(OfflineEngine(index, world["vectors"], split.train_purchases)), split, index, k=20, views=views)
    assert (engine_row["users_open_trip"], engine_row["users_open_trip_bought"]) == (3, 2)   # mẫu số theo split, không theo arm


def test_paired_bootstrap_copy_matches_search_bench_semantics():
    a = {"u1": 1.0, "u2": 0.0, "u3": 1.0}
    same = paired_bootstrap(a, dict(a), n_boot=500, seed=1)
    assert same["delta"] == 0.0 and same["ci95"] == [0.0, 0.0] and same["n"] == 3 and same["n_dropped"] == 0
    better = paired_bootstrap(a, {"u1": 1.0, "u2": 1.0, "u3": 1.0}, n_boot=500, seed=1)
    assert abs(better["delta"] - 100 / 3) < 1e-9 and better["ci95"][0] >= 0.0 and better["n_dropped"] == 0
    dropped = paired_bootstrap(a, {"u1": 1.0, "u2": None, "u4": 1.0}, n_boot=50, seed=1)
    assert dropped["n"] == 1 and dropped["n_dropped"] == 3
    assert paired_bootstrap({}, {}, n_boot=10, seed=1)["delta"] is None


def test_compare_arms_hand_values_and_markdown():
    from src.evaluation.recsys_bench.compare import CompareError, compare_arms, compare_markdown
    rows = {"engine": {"u1": {"rank": 1}, "u2": {"rank": None}},
            "most_popular_in_destination": {"u1": {"rank": 3}, "u2": {"rank": 15}}}
    c = compare_arms(rows, "engine", "most_popular_in_destination", n_boot=200, seed=1)
    m = c["metrics"]
    assert c["n"] == 2 and c["usersOnlyOneArm"] == 0
    assert m["hit@20"]["base"] == 0.5 and m["hit@20"]["ref"] == 1.0 and m["hit@20"]["delta"] == -50.0
    # ref: u1 hạng 3 → 1/log2(4) = 0,5; u2 hạng 15 ngoài top-10 → 0 → NDCG@10 = NDCG@5 = 0,25. base: u1 hạng 1 → 1; u2 trượt → 0,5
    assert m["hit@5"]["delta"] == 0.0 and m["ndcg@10"]["base"] == 0.5 and m["ndcg@10"]["ref"] == 0.25 and m["ndcg@10"]["delta"] == 25.0
    assert m["ndcg@5"]["base"] == 0.5 and m["ndcg@5"]["ref"] == 0.25 and m["ndcg@5"]["delta"] == 25.0
    md = compare_markdown(c)
    assert "| hit@20 | 0.5000 | 1.0000 | -50.00 |" in md and "n = 2 khách" in md
    with pytest.raises(CompareError, match="random-s42"):
        compare_arms({"random-s42": {}}, "engine", "random-s42")


def test_report_columns_footnote_header_run_markdown_and_history_merge(tmp_path):
    from src.evaluation.recsys_bench.report import footnote, header, markdown_table, merge_run, read_run, run_markdown, write_run
    row = {"arm": "engine", "users": 4, "recall@20": 0.5, "exposure_gini": 0.3, "cross_category_open_trip": 0.6,
           "users_open_trip": 3, "cross_category_open_trip_bought": 0.5, "users_open_trip_bought": 2, "strategies": {"x": 4}}
    table = markdown_table([row, {"arm": "old", "recall@20": 0.1}])
    assert "| Gini |" in table and "Cross-cat chuyến mở, có mua" in table and "| 0.300 |" in table
    assert table.splitlines()[3].count("—") >= 3                              # run cũ thiếu khoá → "—"
    assert "3 (trong đó đã mua ≥ 1 món trong chuyến: 2)" in footnote([row]) and footnote([{"arm": "old"}]) == ""
    assert "git gold_v2-1-gabc" in header({"gitDescribe": "gold_v2-1-gabc", "split": {}}) and "git " not in header({"split": {}})
    summary = {"runId": "r", "asOf": "t", "modelVersion": "m", "configHash": "h", "k": 20, "searchUnits": 3, "recommendable": 2,
               "split": {"kind": "llbo", "usersTest": 4, "eventsSha256": "e" * 64, "frozenSha256": "f" * 64, "splitFile": "x.json"},
               "rows": [row], "gitDescribe": "g1", "openTripAssumesAllVectors": True}
    md = run_markdown(summary, {"Ceiling": "| a |\n"})
    assert md.startswith("### Run `r`") and "đóng băng `x.json`" in md and "#### Ceiling" in md and "giả định mọi unit" in md
    assert "- `engine` strategy:" in md and "Gini và Coverage" in md
    # history nối khi gộp arm; gitDescribe là của lượt mới
    d = tmp_path / "run"
    base = {"runId": "r", "modelVersion": "m", "configHash": "h", "asOf": "t", "split": {"kind": "llbo", "frozenSha256": "s1"},
            "rows": [{"arm": "engine"}], "rawRows": [], "gitDescribe": "g1", "history": [{"gitDescribe": "g1", "arms": ["engine"]}]}
    write_run(d, base, [{"arm": "engine", "user": "u1", "ids": []}])
    write_run(d, {**base, "rows": [{"arm": "random-s1"}], "gitDescribe": "g2", "history": [{"gitDescribe": "g2", "arms": ["random"]}]},
              [{"arm": "random-s1", "user": "u1", "ids": []}], merge=True)
    merged, _ = read_run(d)
    assert [h["gitDescribe"] for h in merged["history"]] == ["g1", "g2"] and merged["gitDescribe"] == "g2"
    assert "history" not in merge_run({"rows": []}, [], {"rows": []}, [])[0]        # run cũ không có history → không bịa


def test_cli_compare_and_report_from_run_dir(tmp_path, monkeypatch):
    pytest.importorskip("typer")
    from typer.testing import CliRunner

    from src.evaluation.recsys_bench import __main__ as cli
    monkeypatch.setenv("RECSYS_HOME", str(tmp_path / "home"))
    d = tmp_path / "home" / "runs" / "t"
    d.mkdir(parents=True)
    summary = {"runId": "t", "modelVersion": "m", "configHash": "h", "asOf": "a", "k": 20, "searchUnits": 3, "recommendable": 2,
               "split": {"kind": "llbo", "usersTest": 2, "frozenSha256": "f" * 64, "splitFile": "x"},
               "rows": [{"arm": "engine", "users": 2, "recall@20": 0.5, "exposure_gini": 0.1, "users_open_trip": 1, "users_open_trip_bought": 1},
                        {"arm": "most_popular_in_destination", "users": 2, "recall@20": 1.0}], "gitDescribe": "g"}
    (d / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    per_user = [{"arm": "engine", "user": "u1", "rank": 1}, {"arm": "engine", "user": "u2", "rank": None},
                {"arm": "most_popular_in_destination", "user": "u1", "rank": 3}, {"arm": "most_popular_in_destination", "user": "u2", "rank": 15}]
    (d / "per_user.jsonl").write_text("\n".join(json.dumps(r) for r in per_user), encoding="utf-8")
    (d / "ceiling.md").write_text("| ceiling |", encoding="utf-8")
    runner = CliRunner()
    r = runner.invoke(cli.app, ["compare", "--run-id", "t", "--n-boot", "100"])
    assert r.exit_code == 0, r.output
    assert (d / "compare-engine-vs-most_popular_in_destination.md").exists() and "| hit@20 |" in r.output
    saved = json.loads((d / "compare-engine-vs-most_popular_in_destination.json").read_text(encoding="utf-8"))
    assert saved["configHash"] == "h" and saved["metrics"]["hit@20"]["delta"] == -50.0
    assert runner.invoke(cli.app, ["compare", "--run-id", "t", "--ref", "random"]).exit_code == 1       # random là random-s<seed>
    assert runner.invoke(cli.app, ["compare", "--run-id", "nope"]).exit_code == 1
    out = tmp_path / "draft.md"
    r = runner.invoke(cli.app, ["report", "--run-id", "t", "--out", str(out)])
    assert r.exit_code == 0, r.output
    text = (d / "report.md").read_text(encoding="utf-8")
    assert text == out.read_text(encoding="utf-8").rstrip("\n") + "\n" or text.strip() == out.read_text(encoding="utf-8").strip()
    assert "#### Ceiling" in text and "#### So cặp engine-vs-most_popular_in_destination" in text and "git g" in text and "| Gini |" in text
    assert runner.invoke(cli.app, ["report", "--run-id", "nope"]).exit_code == 1
