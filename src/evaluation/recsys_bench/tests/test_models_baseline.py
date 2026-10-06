"""Day 5 A5 — `baseline_v1` + `regress --baseline`: dựng / ghi / so, luật FAIL theo số khách, phân khúc, canary, không so được, và
CLI đầu-cuối trên fixture (không DB / Weaviate). Không test nào ghi vào `frozen/` (luôn `--out` / `tmp_path`)."""
from __future__ import annotations

import json

import pytest

from src.evaluation.recsys_bench.analysis import LABELS
from src.evaluation.recsys_bench.models import baseline as BL
from src.evaluation.recsys_bench.paths import FROZEN_DIR
from src.evaluation.recsys_bench.tests.test_models_registry_cli import ALGOS_OK, _summary, _write, cli_env  # noqa: F401 — fixture

K = 20


def _ids(user: str, rank: int | None) -> list[str]:
    ids = [f"{user}-{j}" for j in range(K)]
    if rank is not None:
        ids[rank - 1] = f"T-{user}"
    return ids


def _run(ranks: dict[str, dict[str, int | None]], *, config="c1", limit=None, history=1, algo_of=None, run_id="r",
         users_test=None) -> tuple[dict, list[dict]]:
    """Run tổng hợp: `ranks[arm][user]` = hạng target (None = trượt). ids suy từ hạng ⟹ hạng đổi ⟹ ids đổi."""
    algo_of = algo_of or {}
    per_user, raw = [], []
    for arm, by_user in ranks.items():
        for u, r in by_user.items():
            per_user.append({"arm": arm, "user": u, "rank": r, "ids": _ids(u, r), "strategy": "cross_vertical", "poolTruncated": 0})
        hits = [r is not None and r <= 20 for r in by_user.values()]
        raw.append({"arm": arm, "family": arm, "recall@20": sum(hits) / len(hits), **({"algo": algo_of[arm]} if arm in algo_of else {})})
    n = len(next(iter(ranks.values())))
    summary = {"runId": run_id, "modelVersion": "m1", "configHash": config, "engineConfig": {"profile": {"ENGINE_RULES_VERSION": "v"}},
               "k": K, "vectors": "numpy", "vectorsMissing": 0, "searchUnits": 100, "recommendable": 80, "asOf": "2026-09-24T00:00:00+00:00",
               "limitUsers": limit, "usersEvaluated": n, "overrides": {},
               "split": {"kind": "llbo", "frozenSha256": "f" * 64, "eventsSha256": "e" * 64, "usersTest": users_test or n},
               "history": [{"gitDescribe": "abc"}] * history, "rawRows": raw, "rows": raw}
    return summary, per_user


def _users(n):
    return [f"u{i:04d}" for i in range(n)]


def _labels(users, slice_users=()):
    return {u: {lab: ("hot" if (lab == "strategy" and u in slice_users) else "other") for lab in LABELS} for u in users}


def _all_hit(users, rank=3):
    return {u: rank for u in users}


def test_build_check_roundtrip_pass_and_roles():
    users = _users(30)
    s, rows = _run({"engine": _all_hit(users), "most_popular_in_destination": _all_hit(users, 9), "cooc_trip": _all_hit(users, 5)})
    doc = BL.build(s, rows, _labels(users), note="mốc")
    assert {a: v["role"] for a, v in doc["arms"].items()} == {"engine": "primary", "most_popular_in_destination": "canary", "cooc_trip": "scorer"}
    assert doc["arms"]["engine"]["idsSha256"] == BL.ids_sha256({r["user"]: r for r in rows if r["arm"] == "engine"}, K)
    assert set(doc["labels"]) == set(users) and "strategy" in doc["segments"] and doc["fingerprint"]
    res = BL.check(doc, s, rows)
    assert res["status"] == "PASS" and res["exit"] == 0 and all(a["idsChanged"] == 0 for a in res["arms"].values())
    assert "PASS" in BL.markdown(res)
    assert BL.default_path(s) == FROZEN_DIR / "baseline_v1-llbo-asof20260924.json"


def test_primary_ids_change_fails_and_equality_pairs():
    users = _users(30)
    base_s, base_rows = _run({"engine": _all_hit(users), "content_profile+mmr": _all_hit(users)})
    doc = BL.build(base_s, base_rows, None, note="x")
    assert doc["idsEquality"] == [{"base": "content_profile+mmr", "ref": "engine", "n": 30, "equal": 30, "pass": True}]
    moved = _all_hit(users)
    moved[users[0]] = 4
    moved[users[1]] = None
    s, rows = _run({"engine": moved, "content_profile+mmr": _all_hit(users)})
    res = BL.check(doc, s, rows)
    assert res["status"] == "FAIL" and res["exit"] == 1
    assert res["arms"]["engine"]["idsChanged"] == 2 and res["arms"]["engine"]["verdict"] == "FAIL"
    assert [e["user"] for e in res["arms"]["engine"]["changedExamples"]] == users[:2]
    assert res["idsEquality"][0]["runEqual"] == 28 and res["idsEquality"][0]["verdict"] == "FAIL"


def _scorer_case(n, drop):
    users = _users(n)
    base = _all_hit(users)
    s0, r0 = _run({"cooc_trip": base})
    doc = BL.build(s0, r0, None, note="x")
    cur = dict(base)
    for u in users[:drop]:
        cur[u] = None
    s1, r1 = _run({"cooc_trip": cur})
    return doc, s1, r1


def test_scorer_metric_rule_needs_delta_users_and_p():
    doc, s, rows = _scorer_case(100, 2)                       # Δ −2 điểm nhưng chỉ 2 khách ròng < 3 → WARN
    res = BL.check(doc, s, rows)
    assert res["arms"]["cooc_trip"]["verdict"] == "WARN" and res["status"] == "WARN" and res["exit"] == 0
    doc, s, rows = _scorer_case(1000, 12)                     # Δ −1,2 điểm, 12 khách ròng, p ≈ 0 → FAIL
    res = BL.check(doc, s, rows)
    assert res["arms"]["cooc_trip"]["verdict"] == "FAIL" and res["exit"] == 1
    m = res["arms"]["cooc_trip"]["metrics"]["hit@20"]
    assert m["delta"] == pytest.approx(-1.2) and m["worse"] == 12 and m["better"] == 0 and m["pDrop"] < 0.05
    # 12 tụt + 10 tăng: ròng 2, Δ −0,2 → không FAIL
    users = _users(1000)
    base = {u: (None if i in range(12, 22) else 3) for i, u in enumerate(users)}
    s0, r0 = _run({"cooc_trip": base})
    doc = BL.build(s0, r0, None, note="x")
    cur = {u: (None if i < 12 else 3) for i, u in enumerate(users)}
    s1, r1 = _run({"cooc_trip": cur})
    res = BL.check(doc, s1, r1)
    assert res["arms"]["cooc_trip"]["verdict"] == "PASS", res["arms"]["cooc_trip"]
    # arm primary: metric chỉ báo, FAIL do ids
    users = _users(100)
    s0, r0 = _run({"engine": _all_hit(users)})
    doc = BL.build(s0, r0, None, note="x")
    s1, r1 = _run({"engine": {u: (None if i < 50 else 3) for i, u in enumerate(users)}})
    res = BL.check(doc, s1, r1)
    assert res["arms"]["engine"]["verdict"] == "FAIL" and "ids" in res["arms"]["engine"]["reasons"][0]


def test_slice_rule_n_and_users():
    users = _users(1000)
    for n_slice, drop, expect in ((25, 3, "FAIL"), (25, 1, "PASS"), (15, 3, "PASS")):
        hot = users[:n_slice]
        s0, r0 = _run({"cooc_trip": _all_hit(users)})
        doc = BL.build(s0, r0, _labels(users, hot), note="x")
        cur = _all_hit(users)
        for u in hot[:drop]:
            cur[u] = None
        s1, r1 = _run({"cooc_trip": cur})
        res = BL.check(doc, s1, r1)
        assert res["status"] == expect, (n_slice, drop, res["slices"], res["arms"]["cooc_trip"]["reasons"])
        if expect == "FAIL":
            assert res["slices"] == [{"label": "strategy", "value": "hot", "arm": "cooc_trip", "n": 25, "deltaHit20": pytest.approx(-12.0),
                                      "netUsersDrop": 3, "verdict": "FAIL"}]
            assert res["arms"]["cooc_trip"]["verdict"] == "PASS"   # toàn bộ chỉ −0,3 điểm


def test_not_comparable_canary_and_subset():
    users = _users(30)
    s0, r0 = _run({"engine": _all_hit(users), "most_popular_in_destination": _all_hit(users, 9)})
    doc = BL.build(s0, r0, None, note="x")
    s, rows = _run({"engine": _all_hit(users), "most_popular_in_destination": _all_hit(users, 9)}, config="c2")
    with pytest.raises(BL.NotComparable, match="configHash"):
        BL.check(doc, s, rows)
    s, rows = _run({"engine": _all_hit(users), "most_popular_in_destination": _all_hit(users, 9)})
    s["split"]["frozenSha256"] = "0" * 64
    with pytest.raises(BL.NotComparable, match="frozenSha256"):
        BL.check(doc, s, rows)
    s, rows = _run({"engine": _all_hit(users), "most_popular_in_destination": _all_hit(users, 9)})
    s["overrides"] = {"MMR_LAMBDA": 1.0}
    with pytest.raises(BL.NotComparable, match="override"):
        BL.check(doc, s, rows)
    s, rows = _run({"engine": _all_hit(users)})
    with pytest.raises(BL.NotComparable, match="thiếu arm"):
        BL.check(doc, s, rows)
    res = BL.check(doc, s, rows, allow_subset=True)
    assert res["status"] == "WARN" and any("thiếu" in w for w in res["warnings"])
    sub_users = users[:10]
    s, rows = _run({"engine": _all_hit(sub_users), "most_popular_in_destination": _all_hit(sub_users, 9)}, limit=10, users_test=30)
    with pytest.raises(BL.NotComparable, match="limitUsers"):
        BL.check(doc, s, rows)
    res = BL.check(doc, s, rows, allow_subset=True)
    assert res["status"] == "WARN" and res["arms"]["engine"]["n"] == 10
    # canary đổi → INCONCLUSIVE (mã 3), không FAIL
    canary = _all_hit(users, 9)
    canary[users[0]] = 2
    s, rows = _run({"engine": _all_hit(users), "most_popular_in_destination": canary})
    res = BL.check(doc, s, rows)
    assert res["status"] == "INCONCLUSIVE" and res["exit"] == 3
    # specHash của algo khác → không so được
    s0, r0 = _run({"cooc_trip": _all_hit(users)}, algo_of={"cooc_trip": "cooc_trip"})
    s0["algosConfig"] = {"common": {}, "algos": {"cooc_trip": {"scorer": "cooc_trip", "params": {"beta": 5}}}}
    doc = BL.build(s0, r0, None, note="x")
    s1, r1 = _run({"cooc_trip": _all_hit(users)}, algo_of={"cooc_trip": "cooc_trip"})
    s1["algosConfig"] = {"common": {}, "algos": {"cooc_trip": {"scorer": "cooc_trip", "params": {"beta": 9}}}}
    with pytest.raises(BL.NotComparable, match="specHash"):
        BL.check(doc, s1, r1)
    s1["algosConfig"]["algos"]["cooc_trip"]["params"]["beta"] = 5
    s1["algosConfig"]["algos"]["cooc_trip"]["estimate"] = {"fit": "1 s"}       # estimate không vào specHash
    assert BL.check(doc, s1, r1)["status"] == "PASS"


def test_build_refuses_bad_runs_and_write_policy(tmp_path):
    users = _users(5)
    with pytest.raises(BL.BaselineError, match="limitUsers"):
        BL.build(*_run({"engine": _all_hit(users)}, limit=5), None, note="x")
    s, rows = _run({"engine": _all_hit(users)})
    s["split"]["frozenSha256"] = None
    with pytest.raises(BL.BaselineError, match="split-file"):
        BL.build(s, rows, None, note="x")
    with pytest.raises(BL.BaselineError, match="lượt"):
        BL.build(*_run({"engine": _all_hit(users)}, history=2), None, note="x")
    assert BL.build(*_run({"engine": _all_hit(users)}, history=2), None, note="x", force=True)
    with pytest.raises(BL.BaselineError, match="note"):
        BL.build(*_run({"engine": _all_hit(users)}), None, note="  ")
    with pytest.raises(BL.BaselineError, match="không có trong run"):
        BL.build(*_run({"engine": _all_hit(users)}), None, note="x", arms=["ghost"])
    with pytest.raises(BL.BaselineError, match="role"):
        BL.build(*_run({"engine": _all_hit(users)}), None, note="x", roles={"engine": "boss"})
    doc = BL.build(*_run({"engine": _all_hit(users)}), None, note="x", with_ids=True)
    assert doc["arms"]["engine"]["perUser"][users[0]]["ids"] == _ids(users[0], 3)
    path = tmp_path / "b.json"
    assert BL.write(doc, path) == "written" and BL.load(path)["fingerprint"] == doc["fingerprint"]
    again = BL.build(*_run({"engine": _all_hit(users)}), None, note="ghi lại", with_ids=True)
    assert BL.write(again, path) == "unchanged"                                # cùng run → no-op dù note / createdAt khác
    other = BL.build(*_run({"engine": _all_hit(users, 4)}), None, note="x")
    with pytest.raises(BL.BaselineError, match="--force"):
        BL.write(other, path)
    assert BL.write(other, path, force=True) == "written"


def test_cli_baseline_and_regress_end_to_end(cli_env):
    env = cli_env
    before = sorted(p.name for p in FROZEN_DIR.iterdir())
    y = _write(env.tmp, "algos.yaml", ALGOS_OK)
    gate = ["run", "--algos", str(y), "--only", "content_profile", "--only", "star_blend_a1", "--only", "cooc_trip", "--arm", "engine",
            "--arm", "engine_nommr", "--arm", "most_popular_in_destination", "--split", "llbo", "--vectors", "numpy",
            "--split-file", str(env.frozen), "--funnel-pool", "engine"]
    assert env.runner.invoke(env.cli.app, gate + ["--run-id", "g1"]).exit_code == 0
    out = env.tmp / "baseline.json"
    r = env.runner.invoke(env.cli.app, ["baseline", "--run-id", "g1", "--note", "mốc test", "--out", str(out)])
    assert r.exit_code == 0 and "segments.json" in r.output and out.exists()        # chưa analyze → cảnh báo, không nhãn
    assert env.runner.invoke(env.cli.app, ["analyze", "--run-id", "g1"]).exit_code == 0
    r = env.runner.invoke(env.cli.app, ["baseline", "--run-id", "g1", "--note", "mốc test", "--out", str(out)])
    assert r.exit_code == 1 and "--force" in r.output                               # thêm nhãn phân khúc = đổi fingerprint
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert "labels" not in doc
    r = env.runner.invoke(env.cli.app, ["baseline", "--run-id", "g1", "--note", "mốc test", "--out", str(out), "--force"])
    assert r.exit_code == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["labels"] and doc["arms"]["engine"]["role"] == "primary" and doc["arms"]["cooc_trip"]["role"] == "scorer"
    assert doc["arms"]["most_popular_in_destination"]["role"] == "canary" and doc["meta"]["funnel"]["pool"] == "engine"
    assert {e["base"] for e in doc["idsEquality"]} >= {"content_profile+mmr", "content_profile", "star_blend_a1"}
    # chạy lại từ đầu → PASS (mã 0) và ghi regress-baseline.{json,md}
    assert env.runner.invoke(env.cli.app, gate + ["--run-id", "g2"]).exit_code == 0
    r = env.runner.invoke(env.cli.app, ["regress", "--run-id", "g2", "--baseline", str(out)])
    assert r.exit_code == 0 and "PASS" in r.output, r.output
    assert (env.home / "runs" / "g2" / "regress-baseline.md").exists()
    assert json.loads((env.home / "runs" / "g2" / "regress-baseline.json").read_text(encoding="utf-8"))["status"] == "PASS"
    # --override → configHash khác → mã 2
    assert env.runner.invoke(env.cli.app, gate + ["--run-id", "g3", "--override", "MMR_LAMBDA=1.0"]).exit_code == 0
    r = env.runner.invoke(env.cli.app, ["regress", "--run-id", "g3", "--baseline", str(out)])
    assert r.exit_code == 2 and "KHÔNG SO ĐƯỢC" in r.output
    # sửa ids một khách của engine trong run g2 → FAIL mã 1
    pu = env.home / "runs" / "g2" / "per_user.jsonl"
    lines = [json.loads(x) for x in pu.read_text(encoding="utf-8").splitlines() if x.strip()]
    target = next(x for x in lines if x["arm"] == "engine" and len(x["ids"]) >= 2)
    target["ids"] = list(reversed(target["ids"]))
    pu.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n", encoding="utf-8")
    r = env.runner.invoke(env.cli.app, ["regress", "--run-id", "g2", "--baseline", str(out)])
    assert r.exit_code == 1 and "FAIL" in r.output
    # baseline không có → mã 2; --k khác → mã 2; run subset không làm baseline được → mã 1
    assert env.runner.invoke(env.cli.app, ["regress", "--run-id", "g2", "--baseline", str(env.tmp / "none.json")]).exit_code == 2
    assert env.runner.invoke(env.cli.app, ["regress", "--run-id", "g2", "--baseline", str(out), "--k", "10"]).exit_code == 2
    assert env.runner.invoke(env.cli.app, gate + ["--run-id", "g4", "--limit-users", "2"]).exit_code == 0
    r = env.runner.invoke(env.cli.app, ["baseline", "--run-id", "g4", "--note", "x", "--out", str(env.tmp / "b4.json")])
    assert r.exit_code == 1 and "limitUsers" in r.output
    r = env.runner.invoke(env.cli.app, ["regress", "--run-id", "g4", "--baseline", str(out), "--allow-subset"])
    assert r.exit_code == 0 and "WARN" in r.output, r.output
    assert sorted(p.name for p in FROZEN_DIR.iterdir()) == before                   # không test nào ghi vào frozen/
