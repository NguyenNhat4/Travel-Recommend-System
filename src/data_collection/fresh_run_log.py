"""Nhật ký một lượt của job cào mới, cho monitor đọc.

Mỗi lượt có thư mục `<CATALOG_RUN_ROOT>/<lượt>/` chứa:
  run.json      trạng thái, các bước (bắt đầu/kết thúc/giây/lỗi), số liệu, cấu hình đã dùng
  job.log       toàn bộ stdout/stderr của lượt, mỗi dòng có giờ
  raw/, interim/, products.jsonl, …   dữ liệu của lượt (giữ `runs.keep` lượt gần nhất)
Trong `<CATALOG_STATE_DIR>/`:
  running.json  lượt đang chạy + nhịp sống (heartbeat) 10 giây/lần — monitor dùng để biết lượt còn sống
  stop.request  monitor ghi để yêu cầu dừng; lượt đang chạy tự kiểm và dừng các tiến trình con của nó
  live_control.json  monitor ghi để tạm dừng / đổi delay từng nguồn khi lượt đang chạy (collectors/live_control.py);
                xoá đầu và cuối mỗi lượt
  runs.jsonl    tóm tắt mọi lượt, không bị xoá theo `runs.keep`

Dừng hoạt động qua file nên được cả khi monitor và lượt chạy nằm ở hai container khác nhau (cùng volume /data).
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import log
import pipeline_graph as graph
from collectors.live_control import FILE_NAME as LIVE_FILE

RUN_FILE = "run.json"
LOG_FILE = "job.log"
RUNNING_FILE = "running.json"
STOP_FILE = "stop.request"
HISTORY_FILE = "runs.jsonl"
HEARTBEAT_SECONDS = 10
RUN_PREFIXES = ("full-", "daily-", "index-")


class StopRequested(RuntimeError):
    """Người vận hành bấm Dừng trên monitor."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, data) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


# ---------------------------------------------------------------------------------------------------- log


class Tee:
    """Ghi đồng thời ra luồng gốc và job.log; mỗi dòng trong file có giờ địa phương ở đầu."""

    def __init__(self, stream, handle, lock: threading.Lock):
        self.stream, self.handle, self.lock = stream, handle, lock
        self._line_start = True

    def write(self, text: str) -> int:
        if not text:
            return 0
        with self.lock:
            try:
                self.stream.write(text)
            except (ValueError, OSError):
                pass
            out = []
            for chunk in text.splitlines(keepends=True):
                if self._line_start:
                    out.append(datetime.now().strftime("%H:%M:%S "))
                out.append(chunk)
                self._line_start = chunk.endswith("\n")
            try:
                self.handle.write("".join(out))
                self.handle.flush()
            except (ValueError, OSError):
                pass
        return len(text)

    def stream_only(self, text: str) -> None:
        """Chỉ ra luồng gốc (stdout container): dòng JSON của log.py. job.log không đổi."""
        with self.lock:
            try:
                self.stream.write(text)
                self.stream.flush()
            except (ValueError, OSError):
                pass

    def file_only(self, text: str) -> None:
        """Chỉ vào job.log (có giờ đầu dòng): bản text mà monitor đọc, tương ứng dòng JSON ở `stream_only`."""
        with self.lock:
            try:
                self.handle.write(datetime.now().strftime("%H:%M:%S ") + text)
                self.handle.flush()
            except (ValueError, OSError):
                pass

    def flush(self) -> None:
        try:
            self.stream.flush()
        except (ValueError, OSError):
            pass

    def isatty(self) -> bool:
        return False

    def __getattr__(self, name):
        return getattr(self.stream, name)


# ---------------------------------------------------------------------------------------------------- tiến trình con


def descendants(pid: int) -> list[int]:
    """PID mọi tiến trình con/cháu của `pid` (Linux /proc). Nơi khác trả rỗng."""
    children: dict[int, list[int]] = {}
    proc = Path("/proc")
    if not proc.is_dir():
        return []
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
            ppid = int(stat[stat.rindex(")") + 2:].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        children.setdefault(ppid, []).append(int(entry.name))
    out, stack = [], [pid]
    while stack:
        for child in children.get(stack.pop(), []):
            out.append(child)
            stack.append(child)
    return out


def terminate_children(grace: float = 10.0) -> int:
    """SIGTERM mọi tiến trình con (crawl.py, Chromium, driver Playwright), chờ `grace` giây rồi SIGKILL phần còn lại."""
    return _terminate(descendants(os.getpid()), grace)


def terminate_tree(pid: int, grace: float = 10.0) -> int:
    """Như terminate_children nhưng cho một tiến trình và mọi tiến trình con của nó (một nguồn crawl.py quá giờ, P4).
    Lấy danh sách con trước khi gửi tín hiệu: con của tiến trình đã chết bị chuyển cho init, không tìm lại được."""
    return _terminate([*descendants(pid), pid], grace)


def _terminate(pids: list[int], grace: float) -> int:
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline and any(_alive(p) for p in pids):
        time.sleep(0.2)
    for pid in pids:
        if _alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
    return len(pids)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        return stat[stat.rindex(")") + 2] != "Z"
    except (OSError, ValueError, IndexError):
        return True


# ---------------------------------------------------------------------------------------------------- lượt chạy


class RunRecorder:
    def __init__(self, run_dir: Path, state_dir: Path, *, run_id: str, mode: str, trigger: str, settings: dict):
        self.run_dir, self.state_dir = Path(run_dir), Path(state_dir)
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self._stop_thread = threading.Event()
        self._thread = None
        self._log_handle = None
        self._saved_streams = None
        self.data = {
            "id": run_id, "mode": mode, "trigger": trigger, "status": "running",
            "startedAt": now_iso(), "finishedAt": None, "seconds": None, "exitCode": None, "error": None,
            "host": socket.gethostname(), "pid": os.getpid(),
            "settings": {k: list(v) if isinstance(v, tuple) else v for k, v in settings.items()},
            "steps": [], "counts": {}, "sources": {},
        }
        self._t0 = time.monotonic()
        self._base_seconds = 0
        self._resume_at = None

    @classmethod
    def resume(cls, run_dir: Path, state_dir: Path, *, from_step: str, trigger: str) -> "RunRecorder":
        """Mở lại lượt đã kết thúc để chạy lại từ bước `from_step` (CP6 docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md).
        Giữ nguyên các bước cũ (bước chạy lại được thêm vào sau), ghi một mục `resumes` (lúc, từ bước, trạng thái / lỗi cũ)."""
        data = read_json(Path(run_dir) / RUN_FILE)
        if not isinstance(data, dict) or not data.get("id"):
            raise ValueError(f"Không đọc được {RUN_FILE} của lượt {Path(run_dir).name}")
        if data.get("status") == "running":
            raise ValueError("Lượt này đang chạy (hoặc chưa ghi kết thúc); không chạy lại được")
        rec = cls(run_dir, state_dir, run_id=data["id"], mode=data.get("mode") or "full",
                  trigger=data.get("trigger") or trigger, settings=data.get("settings") or {})
        keep = {k: v for k, v in data.items() if k not in ("status", "finishedAt", "exitCode", "error", "errorKind",
                                                              "host", "pid")}
        rec.data.update(keep)
        rec.data["resumes"] = list(data.get("resumes") or []) + [{
            "from": from_step, "at": now_iso(), "trigger": trigger, "previousStatus": data.get("status"),
            "previousError": data.get("error"), "previousSeconds": data.get("seconds")}]
        rec._base_seconds = data.get("seconds") or 0
        rec._resume_at = rec.data["resumes"][-1]["at"]
        return rec

    # -- vòng đời
    def start(self) -> "RunRecorder":
        self.run_dir.mkdir(parents=True, exist_ok=True)
        for stale in (self.state_dir / STOP_FILE, self.state_dir / LIVE_FILE):  # yêu cầu của lượt trước không áp cho lượt mới
            stale.unlink(missing_ok=True)
        self._log_handle = open(self.run_dir / LOG_FILE, "a", encoding="utf-8")
        lock = threading.Lock()
        self._saved_streams = (sys.stdout, sys.stderr)
        sys.stdout = Tee(sys.stdout, self._log_handle, lock)
        sys.stderr = Tee(sys.stderr, self._log_handle, lock)
        self._resumed = bool(self.data.get("resumes")) and self.data["resumes"][-1].get("at") == self._resume_at
        log.configure(run_id=self.data["id"], flow="resume" if self._resumed else self.data["mode"])
        self.save()
        self._thread = threading.Thread(target=self._heartbeat, name="run-heartbeat", daemon=True)
        self._thread.start()
        return self

    def finish(self, status: str, exit_code: int | None, error: str | None = None) -> None:
        self._stop_thread.set()
        if self._thread is not None:
            self._thread.join()
        with self.lock:
            self.data.update(status=status, exitCode=exit_code, error=(error or None) and error[:2000],
                             finishedAt=now_iso(), seconds=round(time.monotonic() - self._t0) + self._base_seconds)
            self.data["diskBytes"] = dir_bytes(self.run_dir)
            self.save(running=False)
        self._stop_thread.set()
        summary = {k: self.data.get(k) for k in ("id", "mode", "trigger", "status", "startedAt", "finishedAt",
                                                   "seconds", "exitCode", "error", "counts")}
        summary["steps"] = [{k: s.get(k) for k in ("name", "group", "status", "seconds")} for s in self.data["steps"]]
        try:
            with open(self.state_dir / HISTORY_FILE, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(summary, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass
        for path in (self.state_dir / RUNNING_FILE, self.state_dir / STOP_FILE, self.state_dir / LIVE_FILE):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        if self._saved_streams:
            sys.stdout.flush()
            sys.stdout, sys.stderr = self._saved_streams
            self._saved_streams = None
        log.configure(reset=True)
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None

    def save(self, running: bool = True) -> None:
        with self.lock:
            write_json(self.run_dir / RUN_FILE, self.data)
            if running:
                current = [s["name"] for s in self.data["steps"] if s["status"] == "running"]
                write_json(self.state_dir / RUNNING_FILE, {
                    "runId": self.data["id"], "mode": self.data["mode"], "trigger": self.data["trigger"],
                    "startedAt": self.data["startedAt"], "heartbeatAt": now_iso(), "pid": os.getpid(),
                    "host": self.data["host"], "steps": current, "stopRequested": self.stop_event.is_set()})

    def _heartbeat(self) -> None:
        while not self._stop_thread.wait(HEARTBEAT_SECONDS):
            request = read_json(self.state_dir / STOP_FILE)
            if request is not None and not self.stop_event.is_set() \
                    and request.get("runId") in (None, "", self.data["id"]):
                self.stop_event.set()
                log.say(f"catalog.stop.requested at={request.get('requestedAt')} — dừng các tiến trình con",
                        severity="WARNING")
                try:
                    killed = terminate_children()
                    log.say(f"catalog.stop.children killed={killed}", severity="WARNING", killed=killed)
                except Exception as exc:  # không để luồng nhịp sống chết vì lỗi dừng
                    log.say(f"catalog.stop.failed {type(exc).__name__}: {exc}", severity="ERROR")
            try:
                self.save()
            except OSError:
                pass

    def check_stop(self) -> None:
        if self.stop_event.is_set():
            raise StopRequested("Người vận hành đã dừng lượt này trên monitor")

    # -- bước và số liệu
    @contextmanager
    def step(self, name: str, group: str | None = None, label: str | None = None):
        self.check_stop()
        entry = {"name": name, "group": group, "label": label or name, "status": "running",
                 "startedAt": now_iso(), "finishedAt": None, "seconds": None, "detail": {}}
        started = time.monotonic()
        with self.lock:
            self.data["steps"].append(entry)
            self.save()
        src = graph.SOURCE_BY_STEP.get(name)
        source = src.key if src else (name.split(":", 1)[1] if name.startswith(graph.NORMALISE_SOURCE) else None)
        step_ctx = log.scope(step=name, source=source)
        step_ctx.__enter__()
        log.emit("step.start", f"catalog.step.start name={name}" + (f" group={group}" if group else ""),
                 group=group)
        try:
            yield entry["detail"]
        except BaseException as exc:
            # lỗi phân loại (pipeline_errors) mang trạng thái bước riêng, vd. BlockedError → "blocked"
            entry["status"] = "stopped" if (isinstance(exc, StopRequested) or self.stop_event.is_set()) \
                else getattr(exc, "step_status", "error")
            entry["error"] = f"{type(exc).__name__}: {exc}"[:1000]
            if getattr(exc, "kind", None):
                entry["errorKind"] = exc.kind
            raise
        else:
            if self.stop_event.is_set():
                entry["status"] = "stopped"
            elif entry["status"] == "running":
                entry["status"] = entry["detail"].pop("_status", "ok")
        finally:
            entry["finishedAt"] = now_iso()
            entry["seconds"] = round(time.monotonic() - started, 1)
            with self.lock:
                self.save()
            counts = {k: v for k, v in entry["detail"].items() if k in ("records", "rows", "total") and isinstance(v, int)}
            log.emit("step.end", f"catalog.step.done name={name} status={entry['status']} seconds={entry['seconds']}",
                     "ERROR" if entry["status"] in ("error", "failed", "timeout", "blocked") else
                     "WARNING" if entry["status"] == "stopped" else "INFO",
                     group=group, duration_ms=round(entry["seconds"] * 1000), status=entry["status"],
                     records=counts.get("records", counts.get("rows", counts.get("total"))),
                     error_kind=entry.get("errorKind"),
                     error={"type": entry["error"].split(":")[0], "message": entry["error"]} if entry.get("error") else None)
            step_ctx.__exit__(None, None, None)

    def set_counts(self, **counts) -> None:
        with self.lock:
            self.data["counts"].update(counts)
            self.save()

    def set_source(self, source: str, **info) -> None:
        with self.lock:
            self.data["sources"].setdefault(source, {}).update(info)
            self.save()


# ---------------------------------------------------------------------------------------------------- thư mục lượt


def dir_bytes(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def run_dirs(run_root: Path) -> list[Path]:
    """Thư mục lượt, mới nhất trước (tên có dấu thời gian UTC ngay sau mode)."""
    if not Path(run_root).is_dir():
        return []
    dirs = [p for p in Path(run_root).iterdir() if p.is_dir() and not p.is_symlink()
            and p.name.startswith(RUN_PREFIXES)]
    return sorted(dirs, key=lambda p: (p.name.split("-")[1] if "-" in p.name else "", p.name), reverse=True)


def prune_runs(run_root: Path, keep: int, *, protect: Path | None = None) -> list[str]:
    """Giữ `keep` lượt mới nhất (tính cả lượt `protect` đang chạy), xoá phần còn lại."""
    removed = []
    kept = 0
    for path in run_dirs(run_root):
        if protect is not None and path.resolve() == Path(protect).resolve():
            kept += 1
            continue
        if kept < keep:
            kept += 1
            continue
        shutil.rmtree(path, ignore_errors=True)
        removed.append(path.name)
    return removed
