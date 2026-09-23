"""Điều khiển container theo profile compose (spec Part 0 P0.2).

Chỉ tác động compose project `vbench` (fasttrack §2.3–2.4): không prune, không đụng container/volume của app.
Health check chạy từ phía host vì image không chắc có curl.
"""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import yaml

from . import paths
from .config import VBenchConfig, read_env_file

PROJECT = "vbench"


@dataclass
class Container:
    name: str
    service: str
    image: str
    status: str
    id: str


@lru_cache(maxsize=1)
def _compose_doc() -> dict[str, Any]:
    with open(paths.COMPOSE_FILE, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def compose_engines() -> list[str]:
    """Engine = profile có trong compose.yml."""
    profs: list[str] = []
    for svc in _compose_doc().get("services", {}).values():
        for p in svc.get("profiles", []):
            if p not in profs:
                profs.append(p)
    return profs


def services_of(engine: str) -> list[str]:
    out = [name for name, svc in _compose_doc().get("services", {}).items() if engine in svc.get("profiles", [])]
    if not out:
        raise KeyError(f"compose.yml không có profile '{engine}' (có: {compose_engines()})")
    return out


def compose_env(cfg: VBenchConfig, limits: tuple[float, str] | None = None, extra: dict[str, str] | None = None) -> dict[str, str]:
    """os.environ + docker/.env + VBENCH_HOME + giới hạn engine theo profile (hoặc `limits` truyền vào)."""
    env = dict(os.environ)
    env.update(read_env_file())
    env["VBENCH_HOME"] = paths.vbench_home().as_posix()
    if limits is None:
        lim = cfg.limits()
        limits = (lim.cpus, lim.mem)
    env["ENGINE_CPUS"] = str(limits[0])
    env["ENGINE_MEM"] = str(limits[1])
    if extra:
        env.update({k: str(v) for k, v in extra.items()})
    return env


def _compose(engine: str, *args: str, env: dict[str, str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose", "-p", PROJECT, "-f", str(paths.COMPOSE_FILE)]
    if paths.DOCKER_ENV_FILE.exists():
        cmd += ["--env-file", str(paths.DOCKER_ENV_FILE)]
    cmd += ["--profile", engine, *args]
    return subprocess.run(cmd, env=env, check=check, text=True, capture_output=capture, encoding="utf-8", errors="replace")


def _ensure_bind_dirs(engine: str) -> None:
    # bind mount backups/<engine> phải tồn tại trước khi up (Docker Desktop không tự tạo trên Windows)
    (paths.vbench_home() / "backups" / engine).mkdir(parents=True, exist_ok=True)


def up(cfg: VBenchConfig, engine: str, env: dict[str, str] | None = None) -> None:
    _ensure_bind_dirs(engine)
    _compose(engine, "up", "-d", *services_of(engine), env=env or compose_env(cfg))


def pull(cfg: VBenchConfig, engine: str, env: dict[str, str] | None = None) -> None:
    _compose(engine, "pull", *services_of(engine), env=env or compose_env(cfg))


def down(cfg: VBenchConfig, engine: str, volumes: bool = False, env: dict[str, str] | None = None) -> None:
    args = ["down"] + (["--volumes"] if volumes else [])
    _compose(engine, *args, env=env or compose_env(cfg))
    if volumes:
        # `down --volumes` chỉ xoá volume của service đang được down; xoá chắc chắn volume khai báo của chính profile này
        for vol in engine_volumes(engine):
            subprocess.run(["docker", "volume", "rm", "-f", f"{PROJECT}_{vol}"], capture_output=True, text=True)


def restart(cfg: VBenchConfig, engine: str, env: dict[str, str] | None = None) -> None:
    _compose(engine, "restart", *services_of(engine), env=env or compose_env(cfg))


def engine_volumes(engine: str) -> list[str]:
    """Named volume (không phải bind mount) của các service thuộc profile."""
    declared = set((_compose_doc().get("volumes") or {}).keys())
    out: list[str] = []
    for s in services_of(engine):
        for v in _compose_doc()["services"][s].get("volumes", []):
            src = str(v).split(":", 1)[0]
            if src in declared and src not in out:
                out.append(src)
    return out


def existing_volumes(engine: str) -> list[str]:
    names = [f"{PROJECT}_{v}" for v in engine_volumes(engine)]
    r = subprocess.run(["docker", "volume", "ls", "-q"], capture_output=True, text=True)
    have = set(r.stdout.split())
    return [n for n in names if n in have]


# ---------------------------------------------------------------- health
def _pg_ready(dsn: str) -> bool:
    import psycopg
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False


def _http_ok(url: str, expect_json_status: str | None = None) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def is_healthy(cfg: VBenchConfig, engine: str) -> bool:
    ec = cfg.engine(engine)
    if engine in ("pgvector", "pgvectorscale"):
        return _pg_ready(ec.get("dsn"))
    if engine == "qdrant":
        return _http_ok(ec.get("url").rstrip("/") + "/readyz")
    raise KeyError(f"chưa có health check cho engine '{engine}'")


def wait_healthy(cfg: VBenchConfig, engine: str, timeout_s: float) -> float:
    t0 = time.perf_counter()
    # Postgres image khởi động server tạm (initdb) rồi restart: cần 2 lần OK liên tiếp cách nhau 1 s
    ok_streak = 0
    while time.perf_counter() - t0 < timeout_s:
        if is_healthy(cfg, engine):
            ok_streak += 1
            if ok_streak >= 2:
                return time.perf_counter() - t0
        else:
            ok_streak = 0
        time.sleep(1.0)
    raise TimeoutError(f"{engine} chưa healthy sau {timeout_s:.0f} s")


# ---------------------------------------------------------------- docker SDK
@lru_cache(maxsize=1)
def docker_client():
    import docker
    return docker.from_env()


def containers(engine: str) -> list[Container]:
    cli = docker_client()
    out: list[Container] = []
    for svc in services_of(engine):
        for c in cli.containers.list(all=True, filters={"label": [f"com.docker.compose.project={PROJECT}", f"com.docker.compose.service={svc}"]}):
            image = c.attrs.get("Config", {}).get("Image") or (c.image.tags[0] if c.image.tags else c.image.short_id)
            out.append(Container(name=c.name, service=svc, image=image, status=c.status, id=c.id))
    return out


def mem_usage_bytes(stats: dict[str, Any]) -> int:
    """Giống `docker stats`: usage − inactive_file (cgroup v2) hoặc − cache (cgroup v1)."""
    ms = stats.get("memory_stats") or {}
    usage = int(ms.get("usage") or 0)
    st = ms.get("stats") or {}
    if "inactive_file" in st:
        usage -= int(st["inactive_file"])
    elif "total_inactive_file" in st:
        usage -= int(st["total_inactive_file"])
    elif "cache" in st:
        usage -= int(st["cache"])
    return max(usage, 0)


def cpu_percent(stats: dict[str, Any]) -> float:
    cs, ps = stats.get("cpu_stats") or {}, stats.get("precpu_stats") or {}
    try:
        cpu_delta = cs["cpu_usage"]["total_usage"] - ps["cpu_usage"]["total_usage"]
        sys_delta = cs["system_cpu_usage"] - ps["system_cpu_usage"]
        ncpu = cs.get("online_cpus") or len(cs["cpu_usage"].get("percpu_usage") or []) or 1
    except (KeyError, TypeError):
        return 0.0
    return (cpu_delta / sys_delta) * ncpu * 100.0 if sys_delta > 0 and cpu_delta >= 0 else 0.0


def stats(engine: str) -> dict[str, float]:
    """Ảnh chụp một lần: tổng RAM (byte) và CPU% của mọi container thuộc profile."""
    cli = docker_client()
    mem, cpu = 0, 0.0
    for c in containers(engine):
        if c.status != "running":
            continue
        s = cli.containers.get(c.id).stats(stream=False)
        mem += mem_usage_bytes(s)
        cpu += cpu_percent(s)
    return {"mem_bytes": mem, "cpu_pct": cpu}


def engine_versions(cfg: VBenchConfig, engine: str) -> dict[str, str]:
    """Phiên bản server/extension để in ở `engine status` và ghi vào kết quả."""
    ec = cfg.engine(engine)
    out: dict[str, str] = {}
    if engine in ("pgvector", "pgvectorscale"):
        import psycopg
        with psycopg.connect(ec.get("dsn"), connect_timeout=3) as conn:
            out["server"] = conn.execute("SHOW server_version").fetchone()[0]
            for ext in ("vector", "vectorscale"):
                row = conn.execute("SELECT extversion FROM pg_extension WHERE extname=%s", (ext,)).fetchone()
                if row:
                    out[ext] = row[0]
                else:
                    avail = conn.execute("SELECT default_version FROM pg_available_extensions WHERE name=%s", (ext,)).fetchone()
                    if avail:
                        out[ext] = f"{avail[0]} (available, chưa CREATE EXTENSION)"
    elif engine == "qdrant":
        import json
        import urllib.request
        with urllib.request.urlopen(ec.get("url").rstrip("/") + "/", timeout=3) as r:
            out["server"] = json.loads(r.read().decode()).get("version", "?")
    return out
