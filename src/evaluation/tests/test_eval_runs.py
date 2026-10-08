"""Unit test cho eval_runs.py: đọc tiến độ, trạng thái tiến trình, so sánh các lần chạy."""

import json
import sys
import time

import pytest

from src.evaluation.agent import eval_runs as er


@pytest.fixture(autouse=True)
def runs_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_EVAL_RUNS_DIR", str(tmp_path / "runs"))
    return tmp_path / "runs"


def _turn(case_id, turn, passed, turns=2, repetition=1, findings=None):
    return {"event": "turn_done", "caseId": case_id, "turn": turn, "turns": turns, "repetition": repetition,
            "message": f"câu {turn}", "status": "COMPLETED", "httpStatus": 200, "latencyMs": 10, "passed": passed,
            "findings": findings or ([] if passed else ["status sai"]), "reply": "ok"}


def _write_run(root, run_id, events, meta=None):
    run_dir = root / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(json.dumps({"runId": run_id, "pid": None, **(meta or {})}), encoding="utf-8")
    (run_dir / "progress.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return run_id


def _start(cases):
    return {"event": "start", "repeat": 1, "turns": sum(n for _, n in cases),
            "cases": [{"id": cid, "category": "c", "turns": n} for cid, n in cases]}


def _case_done(case_id, turns=2, run=None):
    return {"event": "case_done", "caseId": case_id, "repetition": 1, "turns": turns,
            "turnsRun": turns if run is None else run}


def test_finished_run_has_case_results_and_metrics(runs_home):
    events = [_start([("TC-01", 2), ("TC-02", 2)]), _turn("TC-01", 1, True), _turn("TC-01", 2, True),
              _case_done("TC-01"), _turn("TC-02", 1, True), _turn("TC-02", 2, False), _case_done("TC-02"),
              {"event": "done", "exitCode": 1, "totals": {"turns": 4, "passed": 3, "failed": 1}, "metrics": {}}]
    view = er.load_run(_write_run(runs_home, "r1", events))
    assert view.state == er.DONE
    assert (view.total_turns, view.finished_turns, view.passed_turns, view.failed_turns) == (4, 4, 3, 1)
    assert view.case_results() == {"TC-01": True, "TC-02": False}


def test_dead_process_without_done_is_failed_or_stopped(runs_home):
    events = [_start([("TC-01", 2)]), {"event": "turn_start", "caseId": "TC-01", "turn": 1, "turns": 2,
                                       "message": "câu 1"}]
    crashed = er.load_run(_write_run(runs_home, "r1", events))
    assert crashed.state == er.FAILED and "stdout.log" in crashed.error
    assert crashed.current is None
    stopped = er.load_run(_write_run(runs_home, "r2", events, {"stoppedAt": "2026-10-05T10:00:00"}))
    assert stopped.state == er.STOPPED
    assert stopped.cases["TC-01"].passed is None


def test_runner_error_event_is_shown(runs_home):
    view = er.load_run(_write_run(runs_home, "r1", [{"event": "failed", "error": "RuntimeError: thiếu key"}]))
    assert view.state == er.FAILED and view.error == "RuntimeError: thiếu key"


def test_turns_skipped_after_timeout_count_as_finished_and_fail_the_case(runs_home):
    events = [_start([("TC-01", 3)]), _turn("TC-01", 1, False, turns=3), _case_done("TC-01", turns=3, run=1)]
    view = er.load_run(_write_run(runs_home, "r1", events))
    assert view.finished_turns == 3
    assert view.case_results() == {"TC-01": False}


def test_partial_last_line_is_ignored(runs_home):
    run_id = _write_run(runs_home, "r1", [_start([("TC-01", 2)])])
    with (runs_home / run_id / "progress.jsonl").open("a") as handle:
        handle.write('{"event": "turn_do')
    assert er.load_run(run_id).total_turns == 2


def test_compare_flags_regressions_and_fixes_against_the_previous_run_of_each_case(runs_home):
    def run(run_id, results):
        events = [_start([(cid, 1) for cid in results])]
        for cid, ok in results.items():
            events += [_turn(cid, 1, ok, turns=1), _case_done(cid, turns=1)]
        return er.load_run(_write_run(runs_home, run_id, events + [{"event": "done", "metrics": {}}]))

    older = run("r1", {"TC-01": True, "TC-02": False, "TC-03": True})
    middle = run("r2", {"TC-01": True})              # chỉ chạy lại TC-01
    newest = run("r3", {"TC-02": True, "TC-03": False})
    rows = {row["caseId"]: row for row in er.compare_runs([newest, middle, older])}
    assert rows["TC-01"]["change"] is None
    assert rows["TC-02"]["change"] == er.FIXED
    assert rows["TC-03"]["change"] == er.REGRESSION
    assert rows["TC-01"]["results"] == {"r3": None, "r2": True, "r1": True}
    latest = er.latest_results([newest, middle, older])
    assert latest["TC-03"] == (False, "r3", "status sai")
    assert latest["TC-01"][:2] == (True, "r2")


def test_build_command_keeps_partial_runs_out_of_the_official_report(tmp_path):
    command = er.build_command(er.RunOptions(case_ids=["TC-01", "TC-04"], trace_project="p"), tmp_path)
    assert command[1:3] == ["-m", "src.evaluation.agent.golden"]
    assert command[command.index("--only") + 1] == "TC-01,TC-04"
    assert command[command.index("--report-dir") + 1] == str(tmp_path)
    assert command[command.index("--progress-file") + 1] == str(tmp_path / "progress.jsonl")
    official = er.build_command(er.RunOptions(official_report=True, sweep=True), tmp_path)
    assert "--report-dir" not in official and "--only" not in official and "--sweep" in official


def _wait(run_id, state, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        view = er.load_run(run_id)
        if view.state == state:
            return view
        time.sleep(0.1)
    raise AssertionError(f"{run_id} không tới trạng thái {state}: {er.load_run(run_id).state}")


def test_start_and_stop_a_real_subprocess(runs_home, monkeypatch):
    script = ("import json,sys,time; p=sys.argv[sys.argv.index('--progress-file')+1]; "
              "open(p,'a').write(json.dumps({'event':'start','turns':1,'cases':[]})+'\\n'); "
              "time.sleep(float(sys.argv[-1]))")
    monkeypatch.setattr(er, "build_command", lambda options, run_dir: [
        sys.executable, "-c", script, "--progress-file", str(run_dir / "progress.jsonl"), str(options.timeout)])
    run_id = er.start_run(er.RunOptions(timeout=30))
    assert er.active_run() == run_id
    deadline = time.time() + 10
    while er.load_run(run_id).total_turns != 1 and time.time() < deadline:  # đợi tiến trình con ghi event start
        time.sleep(0.05)
    assert er.load_run(run_id).state == er.RUNNING
    er.stop_run(run_id)
    assert _wait(run_id, er.STOPPED).total_turns == 1
    assert er.active_run() is None
    assert er.list_runs() == [run_id]
