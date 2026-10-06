"""Process supervision for CLI jobs. A timed-out worker must die before its lock can be reused."""
from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import log

from fresh_run_log import (HISTORY_FILE, LIVE_FILE, RUNNING_FILE, STOP_FILE, descendants,
                           read_json, write_json, _terminate)


def kill_worker(proc: subprocess.Popen, grace: float = 2, before_release=None) -> None:
    # Freeze the owner of the flock first. Children cannot keep writing after the owner releases it.
    try:
        os.kill(proc.pid, signal.SIGSTOP)
    except ProcessLookupError:
        pass
    _terminate(descendants(proc.pid), grace)
    try:
        if before_release:
            before_release()  # owner is frozen and still holds the run lock
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)  # includes browser grandchildren
        except ProcessLookupError:
            pass
        proc.wait()


def active_run(state: Path, runs: Path, pid: int) -> tuple[Path | None, dict]:
    running = read_json(state / RUNNING_FILE, {}) or {}
    if running.get('pid') != pid:
        return None, {}
    name = running.get('runId', '')
    if Path(name).name != name or not name:
        return None, {}
    path = runs / name / 'run.json'
    return path, read_json(path, {}) or {}


def finish_interrupted(state: Path, runs: Path, pid: int, reason: str, *, stopped=False, lock_held=False) -> None:
    if not lock_held:
        # After an unexpected exit another worker may already own the state directory.
        state.mkdir(parents=True, exist_ok=True)
        with (state / 'fresh_catalog.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            return finish_interrupted(state, runs, pid, reason, stopped=stopped, lock_held=True)
    path, data = active_run(state, runs, pid)
    if path is None or data.get('status') != 'running':
        return
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    for entry in data.get('steps', []):
        if entry.get('status') == 'running':
            entry.update(status='stopped' if stopped else 'timeout', finishedAt=now,
                         error=reason, errorKind='timeout')
    data.update(status='stopped' if stopped else 'failed', finishedAt=now,
                exitCode=5 if stopped else 3, error=reason, errorKind='timeout')
    write_json(path, data)
    with (state / HISTORY_FILE).open('a', encoding='utf-8') as fh:
        import json
        fh.write(json.dumps({k: data.get(k) for k in ('id', 'mode', 'status', 'finishedAt', 'exitCode', 'error')}) + '\n')
    for name in (RUNNING_FILE, STOP_FILE, LIVE_FILE):
        (state / name).unlink(missing_ok=True)


def supervise(command: list[str], state: Path, runs: Path, *, max_seconds: float,
              step_seconds: dict[str, float], stop_grace: float = 20, poll: float = 0.5) -> int:
    """Bound even cancellation-resistant coroutines, native calls and thread joins.

    State belongs to the worker PID: a rejected concurrent launch never modifies another run.
    Resume can reuse all committed DB rows, raw files and checkpoints after a forced stop.
    """
    started = time.monotonic()
    proc = subprocess.Popen(command, start_new_session=True)
    stop_seen = None
    try:
        while proc.poll() is None:
            _, data = active_run(state, runs, proc.pid)
            elapsed = time.monotonic() - started
            reason = 'Vượt hạn giờ toàn lượt (run.maxHours)' if elapsed >= max_seconds else None
            now = datetime.now(timezone.utc)
            for entry in data.get('steps', []):
                limit = step_seconds.get(entry.get('name', '').split(':')[0])
                if not limit or entry.get('status') != 'running':
                    continue
                try:
                    age = (now - datetime.fromisoformat(entry['startedAt'])).total_seconds()
                except (ValueError, KeyError):
                    continue
                if age > limit:
                    reason = f"Bước {entry['name']} vượt hạn {limit:g}s; dừng tiến trình để giải phóng khóa an toàn"
                    break
            request = read_json(state / STOP_FILE, {}) or {}
            requested = bool(data) and request.get('runId') in (None, '', data.get('id')) and bool(request)
            if requested:
                stop_seen = stop_seen or time.monotonic()
                if time.monotonic() - stop_seen >= stop_grace:
                    reason = 'Người vận hành dừng; tiến trình không thoát trong thời gian cho phép'
            if reason:
                kill_worker(proc, before_release=lambda: finish_interrupted(
                    state, runs, proc.pid, reason, stopped=requested, lock_held=True))
                log.emit('catalog.supervisor', f'catalog.supervisor: {reason}', 'ERROR', reason=reason)
                return 5 if requested else 3
            time.sleep(poll)
        if proc.returncode:
            finish_interrupted(state, runs, proc.pid, f'Tiến trình kết thúc bất thường: {proc.returncode}')
        return proc.returncode
    except BaseException:
        kill_worker(proc, before_release=lambda: finish_interrupted(
            state, runs, proc.pid, 'Tiến trình giám sát bị dừng', stopped=True, lock_held=True))
        raise
