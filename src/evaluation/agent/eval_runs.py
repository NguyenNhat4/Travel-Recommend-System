"""Khởi chạy, dừng và đọc các lần chạy runner golden cho eval_app.py.

App không tự chạy graph: mỗi lần chạy là một tiến trình con `python -m src.evaluation.agent.golden` (cùng luật chấm
với CLI), ghi tiến độ ra `progress.jsonl` trong thư mục riêng của lần chạy. Thư mục mặc định `.logs/agent-eval/`
(gitignored); đặt `AGENT_EVAL_RUNS_DIR` để đổi, ví dụ trong test.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.evaluation.agent.golden import DEFAULT_DATASET, REPO_ROOT

# Tiến trình con do chính tiến trình Streamlit này mở; giữ Popen để poll() và tránh zombie còn "sống" với os.kill.
_PROCESSES: dict[int, subprocess.Popen] = {}


def runs_dir() -> Path:
    return Path(os.getenv("AGENT_EVAL_RUNS_DIR") or REPO_ROOT / ".logs/agent-eval")


@dataclass
class RunOptions:
    case_ids: list[str] | None = None   # None = cả bộ
    repeat: int = 1
    sweep: bool = False
    trace_project: str | None = None
    judge_model: str | None = None
    timeout: float = 90.0
    api_base_url: str = "http://127.0.0.1:8000"
    official_report: bool = False        # True: ghi biên bản vào src/evaluation/reports/ như chạy CLI
    dataset: str = DEFAULT_DATASET


def build_command(options: RunOptions, run_dir: Path) -> list[str]:
    command = [sys.executable, "-m", "src.evaluation.agent.golden", "--dataset", options.dataset,
               "--api-base-url", options.api_base_url, "--timeout", str(options.timeout),
               "--repeat", str(max(1, options.repeat)), "--progress-file", str(run_dir / "progress.jsonl")]
    if options.case_ids:
        command += ["--only", ",".join(options.case_ids)]
    if options.sweep:
        command.append("--sweep")
    if options.trace_project:
        command += ["--trace-project", options.trace_project]
    if options.judge_model:
        command += ["--judge-model", options.judge_model]
    if not options.official_report:
        command += ["--report-dir", str(run_dir)]
    return command


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, cwd=REPO_ROOT, timeout=10).stdout.strip()
    except Exception:
        return ""


def start_run(options: RunOptions) -> str:
    started = datetime.now()
    run_id = started.strftime("%Y%m%d-%H%M%S")
    run_dir = runs_dir() / run_id
    suffix = 1
    while run_dir.exists():
        suffix += 1
        run_dir = runs_dir() / f"{run_id}-{suffix}"
    run_dir.mkdir(parents=True)
    command = build_command(options, run_dir)
    log = (run_dir / "stdout.log").open("w", encoding="utf-8")
    process = subprocess.Popen(command, cwd=REPO_ROOT, stdout=log, stderr=subprocess.STDOUT,
                               env={**os.environ, "PYTHONUNBUFFERED": "1"}, start_new_session=True)
    log.close()
    _PROCESSES[process.pid] = process
    meta = {
        "runId": run_dir.name, "pid": process.pid, "startedAt": started.isoformat(timespec="seconds"),
        "commit": _git("rev-parse", "--short", "HEAD") or "unknown",
        # Tune thường chạy trên working tree chưa commit; ghi lại để không nhầm kết quả với commit sạch.
        "dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
        "options": options.__dict__, "command": command,
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir.name


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    if pid in _PROCESSES:
        return _PROCESSES[pid].poll() is None
    # Tiến trình của một phiên Streamlit trước (app đã khởi động lại): không còn Popen, dò /proc.
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        try:
            return stat.read_text().split(")")[-1].split()[0] != "Z"
        except OSError:
            return False
    return True


def stop_run(run_id: str) -> None:
    run_dir = runs_dir() / run_id
    meta = _read_meta(run_dir)
    pid = meta.get("pid")
    if _alive(pid):
        try:
            os.killpg(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    meta["stoppedAt"] = datetime.now().isoformat(timespec="seconds")
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_meta(run_dir: Path) -> dict[str, Any]:
    try:
        return json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def list_runs() -> list[str]:
    """Id các lần chạy, mới nhất trước."""
    root = runs_dir()
    if not root.exists():
        return []
    return sorted((p.name for p in root.iterdir() if (p / "meta.json").exists()), reverse=True)


# ------------------------------------------------------------------------------------------- view


RUNNING, DONE, STOPPED, FAILED = "running", "done", "stopped", "failed"
STATE_LABELS = {RUNNING: "đang chạy", DONE: "xong", STOPPED: "đã dừng", FAILED: "lỗi"}


@dataclass
class CaseView:
    case_id: str
    category: str = ""
    turns_planned: int = 0
    turns: list[dict[str, Any]] = field(default_factory=list)   # event turn_done, theo thứ tự (mọi lần lặp)
    finished: bool = False
    repetitions: int = 1

    @property
    def passed(self) -> bool | None:
        """None khi case chưa chạy xong. Lượt bị bỏ sau timeout tính là FAIL."""
        if not self.finished:
            return None
        return len(self.turns) == self.turns_planned * self.repetitions and all(t["passed"] for t in self.turns)


@dataclass
class RunView:
    run_id: str
    meta: dict[str, Any]
    state: str
    total_turns: int
    finished_turns: int
    current: dict[str, Any] | None           # turn_start chưa có turn_done tương ứng
    cases: dict[str, CaseView]
    done: dict[str, Any] | None
    error: str | None

    @property
    def passed_turns(self) -> int:
        return sum(1 for case in self.cases.values() for t in case.turns if t["passed"])

    @property
    def failed_turns(self) -> int:
        return sum(1 for case in self.cases.values() for t in case.turns if not t["passed"])

    def case_results(self) -> dict[str, bool]:
        """Case đã chạy xong → PASS/FAIL (case SWEEP-* gộp như case thường)."""
        return {cid: case.passed for cid, case in self.cases.items() if case.passed is not None}


def read_events(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "progress.jsonl"
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue  # dòng cuối có thể đang ghi dở
    return events


def load_run(run_id: str) -> RunView:
    run_dir = runs_dir() / run_id
    meta = _read_meta(run_dir)
    events = read_events(run_dir)
    cases: dict[str, CaseView] = {}
    total = finished = 0
    current = None
    done = None
    error = None
    repeat = 1
    for event in events:
        kind = event.get("event")
        if kind == "start":
            repeat = event.get("repeat", 1)
            total = event.get("turns", 0)
            for item in event.get("cases", []):
                cases[item["id"]] = CaseView(item["id"], item.get("category", ""), item.get("turns", 0),
                                             repetitions=repeat)
        elif kind == "sweep_start":
            total += event.get("turns", 0)
        elif kind == "turn_start":
            current = event
            case = cases.setdefault(event["caseId"], CaseView(event["caseId"], "sweep", event.get("turns", 0)))
            case.turns_planned = event.get("turns", case.turns_planned)
        elif kind == "turn_done":
            cases.setdefault(event["caseId"], CaseView(event["caseId"], "sweep", event.get("turns", 0)))
            cases[event["caseId"]].turns.append(event)
            finished += 1
            current = None
        elif kind == "case_done":
            case = cases.setdefault(event["caseId"], CaseView(event["caseId"], "sweep", event.get("turns", 0)))
            finished += event.get("turns", 0) - event.get("turnsRun", 0)   # lượt bị bỏ sau timeout
            if event.get("repetition", 1) >= case.repetitions:
                case.finished = True
        elif kind == "done":
            done = event
        elif kind == "failed":
            error = event.get("error")

    if done:
        state = DONE
    elif _alive(meta.get("pid")):
        state = RUNNING
    elif meta.get("stoppedAt"):
        state = STOPPED
    else:
        state = FAILED
        error = error or "Tiến trình kết thúc mà không ghi kết quả; xem stdout.log."
    if state != RUNNING:
        current = None
    return RunView(run_id, meta, state, total, finished, current, cases, done, error)


def stdout_tail(run_id: str, lines: int = 60) -> str:
    path = runs_dir() / run_id / "stdout.log"
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def active_run() -> str | None:
    """Lần chạy còn sống gần nhất; app chỉ cho chạy một lần một lúc để hai lần không tranh backend và LLM."""
    return next((run_id for run_id in list_runs() if _alive(_read_meta(runs_dir() / run_id).get("pid"))), None)


# ---------------------------------------------------------------------------------------- compare


REGRESSION, FIXED = "regression", "fixed"


def compare_runs(runs: list[RunView]) -> list[dict[str, Any]]:
    """Ma trận case × lần chạy (runs: mới nhất trước). Mỗi hàng: caseId, results {runId: True/False/None} và
    `change` so lần gần nhất có chạy case với lần trước đó có chạy case: hồi quy (PASS → FAIL) hoặc đã sửa."""
    case_ids: list[str] = []
    for run in runs:
        for case_id in run.case_results():
            if case_id not in case_ids:
                case_ids.append(case_id)
    rows = []
    for case_id in sorted(case_ids):
        results = {run.run_id: run.case_results().get(case_id) for run in runs}
        history = [value for value in results.values() if value is not None]
        change = None
        if len(history) >= 2 and history[0] != history[1]:
            change = FIXED if history[0] else REGRESSION
        rows.append({"caseId": case_id, "results": results, "change": change})
    return rows


def latest_results(runs: list[RunView]) -> dict[str, tuple[bool, str, str | None]]:
    """caseId → (PASS?, runId, finding đầu tiên nếu FAIL) theo lần chạy gần nhất có chạy xong case đó."""
    latest: dict[str, tuple[bool, str, str | None]] = {}
    for run in runs:
        for case_id, case in run.cases.items():
            if case_id in latest or case.passed is None:
                continue
            first = next((f for t in case.turns if not t["passed"] for f in t["findings"]), None)
            latest[case_id] = (case.passed, run.run_id, first)
    return latest
