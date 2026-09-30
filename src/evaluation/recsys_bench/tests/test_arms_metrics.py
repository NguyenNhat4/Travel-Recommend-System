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
    assert m["recall@5"] == m["recall@10"] == m["recall@20"] == m["ndcg@5"] == m["ndcg@10"] == 1.0
    assert m["cross_category_rate"] == 0.5 and m["availability_precision"] == 0.5
    assert m["catalog_coverage"] == 1.0 and m["p99_runtime_ms"] == 4.96
    assert m["vertical_diversity@10"] == 1.0 and m["returned_mean"] == 2.0 and m["users"] == 1


def test_ndcg_discounts_by_rank_and_missing_target_scores_zero():
    m = score({"u1": ["a", "b"], "u2": ["a"]}, {"u1": "b", "u2": "c"}, {}, small_index())
    assert m["recall@10"] == 0.5 and abs(m["ndcg@10"] - 0.5 / np.log2(3)) < 1e-9
    assert abs(m["ndcg@5"] - m["ndcg@10"]) < 1e-12                       # target ở hạng 2 → trong top-5
    m6 = score({"u1": ["x1", "x2", "x3", "x4", "x5", "b"]}, {"u1": "b"}, {}, small_index())
    assert m6["ndcg@5"] == 0.0 and m6["recall@5"] == 0.0 and m6["recall@10"] == 1.0 and m6["ndcg@10"] > 0
    assert score({}, {}, {}, small_index())["ndcg@5"] == 0.0


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
    # B7: hàng theo khách mang top-k, productId gốc và hạng strict — u1 mua FL1 (chuyến con) nhưng target là tuyến F1
    u1 = next(r for r in per_user if r["user"] == "u1")
    direct = EngineArm(OfflineEngine(index, world["vectors"], split.train_purchases)).recommend(
        "u1", split.as_of_by_user["u1"], 20, split.train_by_user["u1"]).product_ids
    assert u1["ids"] == direct and len(u1["ids"]) == u1["returned"]         # đúng list arm trả, đúng thứ tự
    assert (u1["target"], u1["targetProductId"], u1["targetIsChild"]) == ("F1", "FL1", True)
    assert u1["rankStrict"] is None and (u1["rank"] is None or u1["ids"][u1["rank"] - 1] == "F1")
    u2 = next(r for r in per_user if r["user"] == "u2")
    assert u2["targetProductId"] == "A1" and u2["targetIsChild"] is False and u2["rankStrict"] == u2["rank"]
    table = markdown_table([random_row, engine_row])
    assert table.count("\n") == 3 and "random (2 seed)" in table and "| engine |" in table and "NDCG@5" in table


def test_engine_config_snapshot_and_hash(world, events):
    from src.evaluation.recsys_bench.engine import POPULARITY_WINDOW_DAYS, config_hash, engine_config
    from src.evaluation.recsys_bench.report import header, write_run
    index = world["index"]
    kept, _ = filter_events(events, index, AS_OF)
    split = leave_last_booking_out(kept, index)
    ev = OfflineEngine(index, world["vectors"], split.train_purchases)
    prod = OfflineEngine(index, world["vectors"], split.train_purchases, mode="prod")
    a, b = engine_config(ev), engine_config(prod)
    assert a["mode"] == "eval" and a["maxPerVertical"] is None and b["mode"] == "prod" and b["maxPerVertical"] == 2
    assert a["popularityWindowDays"] == POPULARITY_WINDOW_DAYS == 90 and a["purchaseLookbackDays"] == 730   # = chữ ký production
    assert {"W_TYPE", "ACTIVE_TRIP_MAX_AGE_DAYS", "DORMANT_AFTER_DAYS", "MAX_REPEAT_PER_TRIP", "MAX_PER_VERTICAL"} <= set(a["profile"])
    assert config_hash(a) == config_hash(engine_config(ev)) and config_hash(a) != config_hash(b) and len(config_hash(a)) == 8
    assert config_hash({"x": 1}) == config_hash({"x": 1}) != config_hash({"x": 2})
    line = header({"runId": "r", "asOf": "t", "modelVersion": "m", "configHash": config_hash(a), "configHashProd": config_hash(b),
                   "split": {"kind": "llbo", "frozenSha256": "abc123def456xyz"}, "vectors": "weaviate", "vectorsMissing": 3})
    assert "configHash" in line and "frozen abc123def456" in line and "thiếu 3" in line
    assert "KHÔNG đóng băng" in header({"split": {"kind": "llbo"}})


def test_cli_freeze_and_split_file_gate(world, events, tmp_path, monkeypatch):
    """`split --freeze` ghi file, không đè file có sha khác; `run --split-file` khớp → header có frozen; lệch → mã 1."""
    pytest.importorskip("typer")
    import json as _json
    from types import SimpleNamespace
    from typer.testing import CliRunner

    from src.evaluation.recsys_bench import __main__ as cli, data_source
    index, vectors = world["index"], world["vectors"]
    monkeypatch.setenv("RECSYS_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(data_source, "load_events", lambda cut=None, refresh=False: [dict(e) for e in events])
    monkeypatch.setattr(data_source, "load_index", lambda mode="none": (index, vectors if mode != "none" else None))
    monkeypatch.setattr(data_source, "settings", lambda: SimpleNamespace(recommend_candidate_k=200))
    monkeypatch.setattr(data_source, "eval_cdp_url", lambda: "postgresql://x:y@localhost:5432/vota")
    monkeypatch.setattr(data_source, "dsn_label", lambda dsn: "localhost:5432/vota")
    runner = CliRunner()
    frozen = tmp_path / "split-llbo.json"
    r = runner.invoke(cli.app, ["split", "--kind", "llbo", "--freeze-path", str(frozen)])
    assert r.exit_code == 0, r.output
    saved = _json.loads(frozen.read_text(encoding="utf-8"))
    assert saved["dsnLabel"] == "localhost:5432/vota" and saved["canonical"]["targets"]["u1"]["target"] == "F1"
    # đè bằng split khác tham số → từ chối trừ --force
    r = runner.invoke(cli.app, ["split", "--kind", "llbo", "--min-trips", "2", "--freeze-path", str(frozen)])
    assert r.exit_code == 1 and "--force" in r.output and _json.loads(frozen.read_text(encoding="utf-8"))["sha256"] == saved["sha256"]
    r = runner.invoke(cli.app, ["run", "--arm", "random", "--split", "llbo", "--seeds", "1", "--split-file", str(frozen),
                               "--run-id", "t", "--limit-users", "2"])
    assert r.exit_code == 0, r.output
    assert "split khớp bản đóng băng" in r.output and f"frozen {saved['sha256'][:12]}" in r.output and "SUBSET 2/4" in r.output
    summary = _json.loads((tmp_path / "home" / "runs" / "t" / "summary.json").read_text(encoding="utf-8"))
    assert summary["split"]["frozenSha256"] == saved["sha256"] and summary["configHash"] and summary["limitUsers"] == 2
    assert list(summary)[:4] == ["runId", "modelVersion", "engineConfig", "configHash"]
    assert (tmp_path / "home" / "runs" / "t" / "per_user.jsonl").exists()
    # lệch tham số → mã 1, không chạy arm
    r = runner.invoke(cli.app, ["run", "--arm", "random", "--split", "llbo", "--min-trips", "2", "--split-file", str(frozen), "--run-id", "t2"])
    assert r.exit_code == 1 and "lệch bản đóng băng" in r.output and not (tmp_path / "home" / "runs" / "t2").exists()
    # file không phải bản đóng băng → mã 1, thông báo đỏ (không traceback)
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    r = runner.invoke(cli.app, ["run", "--arm", "random", "--split", "llbo", "--split-file", str(bad), "--run-id", "t3"])
    assert r.exit_code == 1 and "không phải file đóng băng" in r.output


def test_write_run_emits_per_user_jsonl_with_ids(tmp_path):
    from src.evaluation.recsys_bench.report import write_run
    import json as _json
    rows = [{"arm": "engine", "user": "u1", "ids": ["a", "b"], "rank": 2, "rankStrict": None}]
    d = write_run(tmp_path / "run", {"runId": "r"}, rows)
    lines = (d / "per_user.jsonl").read_text(encoding="utf-8").splitlines()
    assert _json.loads(lines[0])["ids"] == ["a", "b"] and (d / "per_user.csv").exists() and (d / "summary.json").exists()


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
