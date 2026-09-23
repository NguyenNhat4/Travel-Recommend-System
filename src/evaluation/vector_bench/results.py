"""Phong bì kết quả chung (spec §1.4) + log ra console/file (§1.5)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import paths

log = logging.getLogger("vbench")

STATUSES = ("ok", "error", "skipped", "unsupported", "fail", "partial")


def setup_logging(run_id: str, verbose: bool = False) -> None:
    from rich.logging import RichHandler

    root = logging.getLogger("vbench")
    if root.handlers:
        return
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch = RichHandler(show_path=False, rich_tracebacks=True, markup=False)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.addHandler(ch)
    fh = logging.FileHandler(paths.run_dir(run_id) / "vbench.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    fh.setLevel(logging.DEBUG)
    root.addHandler(fh)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@lru_cache(maxsize=1)
def git_commit() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=paths.repo_root(), capture_output=True, text=True, timeout=5)
        sha = r.stdout.strip() or "unknown"
        d = subprocess.run(["git", "status", "--porcelain", "--", "src/evaluation/vector_bench"], cwd=paths.repo_root(),
                           capture_output=True, text=True, timeout=5)
        return sha + ("-dirty" if d.stdout.strip() else "")
    except Exception:
        return "unknown"


@lru_cache(maxsize=1)
def host_info() -> dict[str, Any]:
    ram_gb = None
    try:
        if os.name == "nt":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            ram_gb = round(m.ullTotalPhys / 2**30, 1)
        else:
            ram_gb = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
    except Exception:
        pass
    docker_v = None
    try:
        r = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True, timeout=10)
        docker_v = r.stdout.strip() or None
    except Exception:
        pass
    return {"cpu": platform.processor() or platform.machine(), "vcpus": os.cpu_count(), "ram_gb": ram_gb,
            "os": f"{platform.system()} {platform.release()} ({platform.version()})", "python": platform.python_version(),
            "docker": docker_v}


def sha256_file(p: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def dataset_info(scale: str) -> dict[str, Any]:
    d = paths.data_dir(scale, create=False)
    info: dict[str, Any] = {"scale": scale}
    meta_p = d / paths.EMBED_META
    stats_p = d / paths.STATS
    if meta_p.exists():
        m = json.loads(meta_p.read_text(encoding="utf-8"))
        info.update({"n": m.get("n"), "dim": m.get("dim"), "embed_model": m.get("model"), "embed_backend": m.get("backend"),
                     "vectors_sha256": m.get("vectors_sha256")})
    elif stats_p.exists():
        s = json.loads(stats_p.read_text(encoding="utf-8"))
        info.update({"n": s.get("n"), "dim": s.get("dim"), "embed_model": s.get("embed_model"), "vectors_sha256": s.get("vectors_sha256"),
                     "vectors_source": s.get("vectors")})
    return info


def write_result(run_id: str, engine: str, scale: str, step: str, *, status: str, metrics: dict[str, Any],
                 started_at: str, error: str | None = None, engine_version: str | None = None,
                 client_version: str | None = None, index_config: dict[str, Any] | None = None,
                 engine_limits: dict[str, Any] | None = None, extra: dict[str, Any] | None = None) -> Path:
    assert status in STATUSES, status
    doc = {
        "run_id": run_id, "engine": engine, "scale": scale, "step": step,
        "status": status, "error": error,
        "engine_version": engine_version, "client_version": client_version,
        "index_config": index_config,
        "dataset": dataset_info(scale) if scale != "-" else None,
        "host": host_info(),
        "engine_limits": engine_limits,
        "git_commit": git_commit(), "started_at": started_at, "finished_at": now_iso(),
        "metrics": metrics,
    }
    if extra:
        doc.update(extra)
    out = paths.step_dir(run_id, engine, scale) / f"{step}.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    log.info("ghi %s (status=%s)", out, status)
    return out


def read_result(run_id: str, engine: str, scale: str, step: str) -> dict[str, Any] | None:
    p = paths.step_dir(run_id, engine, scale, create=False) / f"{step}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _json_default(o: Any) -> Any:
    import numpy as np
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"không serialize được {type(o)}")


def dump_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
