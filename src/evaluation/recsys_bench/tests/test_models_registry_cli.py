"""R5/R6: registry yaml (inherit, select, requires, hash) và CLI `run --algos … --mode`, `regress`, `report`, `analyze` với scorer mới
— CliRunner + monkeypatch `data_source` như `test_arms_metrics.test_cli_freeze_and_split_file_gate` (không DB / Weaviate)."""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest
import yaml

from src.evaluation.recsys_bench.models.registry import (AlgosError, algos_hash, entry_reranks, lib_versions, load_algos, missing_libs,
                                                         select)

ALGOS_OK = {
    "version": 1,
    "common": {"matrix": {"cell": "binary", "events": ["purchase", "add_to_cart"], "include_views": False},
               "funnel": {"k": 20, "pool": "mask", "rerank": ["none", "mmr"], "pool_k": 200, "popular_k": 50}},
    "algos": {
        "content_profile": {"scorer": "content", "tier": 1},
        "pop_funnel": {"scorer": "pop_funnel", "tier": 1, "funnel": {"rerank": "none"}},
        "cooc_trip": {"scorer": "cooc_trip", "tier": 1, "beta": 5, "top_k": 50},
        "star_blend": {"scorer": "star_blend", "tier": 1, "beta": 5, "top_k": 50, "a": 0.5},
        "star_blend_a1": {"inherit": "star_blend", "a": 1.0, "expect_equal_to": "content_profile"},
        "ease": {"scorer": "ease", "tier": 1, "lam": 200},
        "rp3beta": {"scorer": "rp3beta", "tier": 2, "alpha": 1.0, "beta": 0.6, "top_k": 50},
        "needs_lib": {"scorer": "itemknn", "tier": 1, "k": 5, "requires": "nonexistent_lib_xyz", "status": "not_run"},
    },
}


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")   # giữ thứ tự yaml như file thật
    return p


def test_load_algos_inherit_select_requires_and_hash(tmp_path):
    cfg = load_algos(_write(tmp_path, "a.yaml", ALGOS_OK))
    a1 = cfg.algos["star_blend_a1"]
    assert a1.scorer == "star_blend" and a1.params == {"beta": 5, "top_k": 50, "a": 1.0} and a1.expect_equal_to == "content_profile" and a1.tier == 1
    assert cfg.algos["cooc_trip"].params == {"beta": 5, "top_k": 50} and cfg.algos["content_profile"].params == {}
    assert [s.name for s in select(cfg, None, 1)] == ["content_profile", "pop_funnel", "cooc_trip", "star_blend", "star_blend_a1", "ease"]
    assert entry_reranks(cfg.algos["pop_funnel"], ["none", "mmr"]) == ["none"] and entry_reranks(cfg.algos["pop_funnel"], ["mmr"]) == []
    assert entry_reranks(cfg.algos["ease"], ["mmr", "none"]) == ["mmr", "none"]
    assert "rp3beta" in [s.name for s in select(cfg, None, 2)] and "needs_lib" not in [s.name for s in select(cfg, None, 2)]
    assert [s.name for s in select(cfg, ["ease", "cooc_trip"])] == ["cooc_trip", "ease"]        # thứ tự yaml
    with pytest.raises(AlgosError, match="nope"):
        select(cfg, ["nope"])
    with pytest.raises(AlgosError, match="not_run"):
        select(cfg, ["needs_lib"])
    assert missing_libs([cfg.algos["needs_lib"]]) == {"needs_lib": ["nonexistent_lib_xyz"]} and missing_libs([cfg.algos["ease"]]) == {}
    specs = select(cfg, None, 1)
    h1 = algos_hash(cfg, specs, {"e": 1}, mode="funnel", reranks=["none"], pool=None, k=20, libs={})
    assert h1 == algos_hash(cfg, specs, {"e": 1}, mode="funnel", reranks=["none"], pool=None, k=20, libs={}) and len(h1) == 8
    assert h1 != algos_hash(cfg, specs, {"e": 1}, mode="raw", reranks=["none"], pool=None, k=20, libs={})
    assert h1 != algos_hash(cfg, specs, {"e": 2}, mode="funnel", reranks=["none"], pool=None, k=20, libs={})
    assert lib_versions()["numpy"]
    assert "cooc_trip" in cfg.resolved()["algos"] and cfg.resolved()["algos"]["star_blend_a1"]["params"]["a"] == 1.0


def test_load_algos_rejects_bad_configs(tmp_path):
    bad_scorer = copy.deepcopy(ALGOS_OK)
    bad_scorer["algos"] = {"x": {"scorer": "nope"}}
    with pytest.raises(AlgosError, match="registry"):
        load_algos(_write(tmp_path, "b1.yaml", bad_scorer))
    cyc = {"version": 1, "algos": {"a": {"inherit": "b"}, "b": {"inherit": "a"}}}
    with pytest.raises(AlgosError, match="vòng"):
        load_algos(_write(tmp_path, "b2.yaml", cyc))
    with pytest.raises(AlgosError, match="extra"):
        load_algos(_write(tmp_path, "b3.yaml", {"version": 1, "algos": {"a": {"scorer": "ease"}}, "extra": 1}))
    with pytest.raises(AlgosError, match="pool"):
        load_algos(_write(tmp_path, "b4.yaml", {"version": 1, "common": {"funnel": {"pool": "all"}}, "algos": {"a": {"scorer": "ease"}}}))
    with pytest.raises(AlgosError, match="expect_equal_to"):
        load_algos(_write(tmp_path, "b5.yaml", {"version": 1, "algos": {"a": {"scorer": "ease", "expect_equal_to": "ghost"}}}))
    with pytest.raises(AlgosError, match="funnel.rerank"):
        load_algos(_write(tmp_path, "b6.yaml", {"version": 1, "algos": {"a": {"scorer": "ease", "funnel": {"rerank": "both"}}}}))
    with pytest.raises(AlgosError, match="không tìm thấy"):
        load_algos(tmp_path / "missing.yaml")


@pytest.fixture
def cli_env(world, events, tmp_path, monkeypatch):
    pytest.importorskip("typer")
    from typer.testing import CliRunner

    from src.evaluation.recsys_bench import __main__ as cli, data_source
    index, vectors = world["index"], world["vectors"]
    calls: list[str] = []
    monkeypatch.setenv("RECSYS_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(data_source, "load_events", lambda cut=None, refresh=False: calls.append("events") or [dict(e) for e in events])
    monkeypatch.setattr(data_source, "load_index", lambda mode="none": (index, vectors if mode != "none" else None))
    monkeypatch.setattr(data_source, "settings", lambda: SimpleNamespace(recommend_candidate_k=200))
    monkeypatch.setattr(data_source, "eval_cdp_url", lambda: "postgresql://x:y@localhost:5432/vota")
    monkeypatch.setattr(data_source, "dsn_label", lambda dsn: "localhost:5432/vota")
    runner = CliRunner()
    frozen = tmp_path / "split-llbo.json"
    assert runner.invoke(cli.app, ["split", "--kind", "llbo", "--freeze-path", str(frozen)]).exit_code == 0
    calls.clear()
    return SimpleNamespace(cli=cli, runner=runner, frozen=frozen, home=tmp_path / "home", tmp=tmp_path, calls=calls)


def _summary(env, run_id):
    return json.loads((env.home / "runs" / run_id / "summary.json").read_text(encoding="utf-8"))


def test_cli_algos_config_errors_exit_before_db(cli_env):
    env = cli_env
    bad = _write(env.tmp, "bad.yaml", {"version": 1, "algos": {"x": {"scorer": "nope"}}})
    r = env.runner.invoke(env.cli.app, ["run", "--algos", str(bad), "--split", "llbo", "--vectors", "numpy"])
    assert r.exit_code == 1 and "registry" in r.output and env.calls == []
    y = _write(env.tmp, "algos.yaml", ALGOS_OK)
    assert env.runner.invoke(env.cli.app, ["run", "--algos", str(y), "--only", "nope", "--split", "llbo", "--vectors", "numpy"]).exit_code == 1
    assert env.runner.invoke(env.cli.app, ["run", "--algos", str(y), "--mode", "both", "--split", "llbo", "--vectors", "numpy"]).exit_code == 1
    assert env.runner.invoke(env.cli.app, ["run", "--algos", str(y), "--funnel-rerank", "both", "--split", "llbo", "--vectors", "numpy"]).exit_code == 1
    r = env.runner.invoke(env.cli.app, ["run", "--algos", str(y), "--split", "llbo", "--vectors", "none"])
    assert r.exit_code == 1 and "--vectors" in r.output
    needs = copy.deepcopy(ALGOS_OK)
    needs["algos"]["needs_lib"]["status"] = "run"
    r = env.runner.invoke(env.cli.app, ["run", "--algos", str(_write(env.tmp, "needs.yaml", needs)), "--split", "llbo", "--vectors", "numpy"])
    assert r.exit_code == 1 and "thiếu thư viện" in r.output and env.calls == []


def test_cli_run_algos_gate_regress_report_analyze(cli_env):
    env = cli_env
    y = _write(env.tmp, "algos.yaml", ALGOS_OK)
    r = env.runner.invoke(env.cli.app, ["run", "--algos", str(y), "--arm", "engine", "--arm", "engine_nommr", "--arm", "most_popular_in_destination",
                                        "--split", "llbo", "--vectors", "numpy", "--split-file", str(env.frozen), "--run-id", "g", "--funnel-pool", "engine"])
    assert r.exit_code == 0, r.output
    s = _summary(env, "g")
    assert list(s)[:4] == ["runId", "modelVersion", "engineConfig", "configHash"]
    assert s["algosHash"] and s["algoMode"] == "funnel" and s["funnel"] == {"pool": "engine", "reranks": ["none", "mmr"]}
    arms = {row["arm"] for row in s["rows"]}
    assert {"engine", "engine_nommr", "most_popular_in_destination", "content_profile", "content_profile+mmr", "cooc_trip", "cooc_trip+mmr",
            "star_blend", "star_blend+mmr", "star_blend_a1", "star_blend_a1+mmr", "ease", "ease+mmr", "pop_funnel"} <= arms and "rp3beta" not in arms
    assert "pop_funnel+mmr" not in arms                                   # entry chỉ rerank none
    cooc = next(row for row in s["rows"] if row["arm"] == "cooc_trip")
    assert "collab_coverage" in cooc and cooc["fit_seconds"] >= 0 and cooc["funnel"]["pool"] == "engine" and cooc["algo"] == "cooc_trip"
    assert s["expectations"]["star_blend_a1"]["pass"] and s["expectations"]["star_blend_a1+mmr"]["pass"] and s["expectFailed"] == []
    assert s["fitLog"]["cooc_trip"][0]["nRows"] == 5 and s["leakCheck"] == {"usersChecked": 4, "targetCellInTripRow": 0} and s["libs"]["numpy"]
    assert s["matrixStats"]["nTrips"] == 5 and s["history"][0]["params"]["algos"] == str(y)
    assert "Collab cov." in r.output and "Fit s" in r.output
    # G1 / G2 trong-run
    assert env.runner.invoke(env.cli.app, ["regress", "--run-id", "g", "--base", "content_profile+mmr", "--ref", "engine"]).exit_code == 0
    assert env.runner.invoke(env.cli.app, ["regress", "--run-id", "g", "--base", "content_profile", "--ref", "engine_nommr", "--tie-tolerant"]).exit_code == 0
    assert env.runner.invoke(env.cli.app, ["regress", "--run-id", "g", "--base", "star_blend_a1+mmr", "--ref", "content_profile+mmr"]).exit_code == 0
    r = env.runner.invoke(env.cli.app, ["regress", "--run-id", "g", "--base", "ease", "--ref", "engine"])
    assert r.exit_code == 1 and "FAIL" in r.output and (env.home / "runs" / "g" / "regress-ease-vs-engine.json").exists()
    assert env.runner.invoke(env.cli.app, ["regress", "--run-id", "g", "--base", "nope", "--ref", "engine"]).exit_code == 1
    assert env.runner.invoke(env.cli.app, ["regress", "--run-id", "nope", "--base", "ease", "--ref", "engine"]).exit_code == 1
    # cùng run-id nhưng khác algosHash (mode raw) → từ chối gộp
    r = env.runner.invoke(env.cli.app, ["run", "--algos", str(y), "--only", "ease", "--split", "llbo", "--vectors", "numpy", "--split-file", str(env.frozen),
                                        "--run-id", "g", "--mode", "raw"])
    assert r.exit_code == 1 and "algosHash" in r.output
    # report gộp fit log; analyze có scorer mới trong phân khúc
    r = env.runner.invoke(env.cli.app, ["report", "--run-id", "g"])
    assert r.exit_code == 0 and "#### Fit log" in r.output and "expect_equal_to" in r.output and "Caveat LLBO" in r.output
    r = env.runner.invoke(env.cli.app, ["analyze", "--run-id", "g"])
    assert r.exit_code == 0, r.output
    assert "cooc_trip" in (env.home / "runs" / "g" / "segments.md").read_text(encoding="utf-8")


def test_cli_run_algos_raw_mode_and_expect_failure(cli_env):
    env = cli_env
    y = _write(env.tmp, "algos.yaml", ALGOS_OK)
    r = env.runner.invoke(env.cli.app, ["run", "--algos", str(y), "--only", "ease", "--only", "content_profile", "--split", "llbo", "--vectors", "numpy",
                                        "--split-file", str(env.frozen), "--run-id", "raw", "--mode", "raw", "--funnel-rerank", "none"])
    assert r.exit_code == 0, r.output
    s = _summary(env, "raw")
    assert s["algoMode"] == "raw" and s["funnel"] == {"pool": "mask", "reranks": ["none"]}
    assert {row["arm"] for row in s["rows"]} == {"content_profile", "ease"} and all(row["funnel"]["mode"] == "raw" for row in s["rows"])
    # run_id mặc định có algosHash
    r = env.runner.invoke(env.cli.app, ["run", "--algos", str(y), "--only", "ease", "--split", "llbo", "--vectors", "numpy", "--split-file", str(env.frozen)])
    assert r.exit_code == 0 and any(d.name.endswith(f"-{s['algosHash']}") or d.name.count("-") >= 3 for d in (env.home / "runs").iterdir())
    # expect_equal_to thất bại → mã 1, không có hàng của algo đó, run vẫn ghi
    fail = copy.deepcopy(ALGOS_OK)
    fail["algos"]["ease_vs_content"] = {"scorer": "ease", "lam": 200, "expect_equal_to": "content_profile"}
    r = env.runner.invoke(env.cli.app, ["run", "--algos", str(_write(env.tmp, "fail.yaml", fail)), "--only", "content_profile", "--only", "ease_vs_content",
                                        "--split", "llbo", "--vectors", "numpy", "--split-file", str(env.frozen), "--run-id", "f"])
    assert r.exit_code == 1 and "THẤT BẠI" in r.output
    s = _summary(env, "f")
    assert {row["arm"] for row in s["rows"]} == {"content_profile", "content_profile+mmr"}
    assert s["expectFailed"] and s["expectFailed"][0]["arm"].startswith("ease_vs_content")
    per_user = (env.home / "runs" / "f" / "per_user.jsonl").read_text(encoding="utf-8")
    assert "ease_vs_content" not in per_user
