"""`vb doctor` — kiểm tra máy trước khi đo (spec Part 0 P0.3). In bảng OK / WARN / FAIL; FAIL → mã thoát 1."""
from __future__ import annotations

import importlib
import importlib.metadata as md
import os
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import lifecycle, paths
from .config import VBenchConfig, read_env_file

REQUIRED_LIBS = [("numpy", "numpy"), ("pandas", "pandas"), ("pyarrow", "pyarrow"), ("scipy", "scipy"), ("yaml", "pyyaml"),
                 ("pydantic", "pydantic"), ("typer", "typer"), ("rich", "rich"), ("psycopg", "psycopg"), ("pgvector", "pgvector"),
                 ("qdrant_client", "qdrant-client"), ("docker", "docker"), ("mmh3", "mmh3"), ("pytest", "pytest")]
OPTIONAL_LIBS = [("sentence_transformers", "sentence-transformers"), ("torch", "torch")]


@dataclass
class Check:
    name: str
    status: str   # OK | WARN | FAIL | INFO
    detail: str


def _run(cmd: list[str], timeout: float = 30) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, f"không tìm thấy {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def _ver(dist: str) -> str:
    try:
        return md.version(dist)
    except md.PackageNotFoundError:
        return "?"


def _parse_size_gb(s: str) -> float:
    m = re.match(r"^\s*([\d.]+)\s*([kmgt]?)b?\s*$", s.lower())
    if not m:
        return 0.0
    mult = {"": 1 / 2**30, "k": 1 / 2**20, "m": 1 / 2**10, "g": 1, "t": 1024}[m.group(2)]
    return float(m.group(1)) * mult


def ensure_env_file() -> tuple[bool, str]:
    """Tạo docker/.env từ .env.example nếu thiếu; điền VBENCH_HOME tuyệt đối (dấu /)."""
    home = paths.vbench_home().as_posix()
    if not paths.DOCKER_ENV_FILE.exists():
        text = paths.DOCKER_ENV_EXAMPLE.read_text(encoding="utf-8")
        text = re.sub(r"^VBENCH_HOME=.*$", f"VBENCH_HOME={home}", text, flags=re.M)
        paths.DOCKER_ENV_FILE.write_text(text, encoding="utf-8")
        return True, f"tạo {paths.DOCKER_ENV_FILE} với VBENCH_HOME={home}"
    env = read_env_file()
    if env.get("VBENCH_HOME", "").startswith("<") or not env.get("VBENCH_HOME"):
        text = paths.DOCKER_ENV_FILE.read_text(encoding="utf-8")
        if re.search(r"^VBENCH_HOME=", text, flags=re.M):
            text = re.sub(r"^VBENCH_HOME=.*$", f"VBENCH_HOME={home}", text, flags=re.M)
        else:
            text = f"VBENCH_HOME={home}\n" + text
        paths.DOCKER_ENV_FILE.write_text(text, encoding="utf-8")
        return True, f"điền VBENCH_HOME={home} vào {paths.DOCKER_ENV_FILE}"
    return False, f"VBENCH_HOME={env['VBENCH_HOME']}"


def _image_of(svc: dict, env: dict[str, str]) -> str:
    img = svc["image"]

    def sub(m: re.Match) -> str:
        var, default = m.group(1), m.group(3) or ""
        return env.get(var) or default
    return re.sub(r"\$\{(\w+)(:-([^}]*))?\}", sub, img)


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def run_doctor(cfg: VBenchConfig) -> list[Check]:
    checks: list[Check] = []
    add = lambda n, s, d: checks.append(Check(n, s, d))  # noqa: E731

    # Python
    v = sys.version_info
    add("python", "OK" if v >= (3, 11) else "FAIL", f"{sys.version.split()[0]} ({sys.executable})")

    # thư viện: import thử (Windows Smart App Control có thể chặn DLL lần đầu → báo rõ)
    for mod, dist in REQUIRED_LIBS:
        try:
            importlib.import_module(mod)
            add(f"lib {dist}", "OK", _ver(dist))
        except Exception as e:  # noqa: BLE001
            add(f"lib {dist}", "FAIL", f"import lỗi: {e}")
    for mod, dist in OPTIONAL_LIBS:
        try:
            importlib.import_module(mod)
            add(f"lib {dist}", "OK", _ver(dist))
        except Exception as e:  # noqa: BLE001
            add(f"lib {dist}", "WARN", f"tuỳ chọn (Part 2 backend st): {e}")

    # docker + compose
    rc, out = _run(["docker", "version", "--format", "{{.Server.Version}}"])
    add("docker daemon", "OK" if rc == 0 else "FAIL", out.splitlines()[-1] if out else "")
    rc, out = _run(["docker", "compose", "version", "--short"])
    if rc == 0:
        m = re.match(r"v?(\d+)\.(\d+)", out.strip())
        ok = m and (int(m.group(1)), int(m.group(2))) >= (2, 20)
        add("docker compose", "OK" if ok else "FAIL", out.strip() + ("" if ok else " (cần ≥ 2.20)"))
    else:
        add("docker compose", "FAIL", out)
    rc, out = _run(["docker", "info", "--format", "{{.NCPU}} {{.MemTotal}}"])
    if rc == 0 and out:
        ncpu, mem = out.split()[:2]
        mem_gb = int(mem) / 2**30
        lim = cfg.limits()
        need = _parse_size_gb(lim.mem)
        st = "OK" if (mem_gb >= need and int(ncpu) >= lim.cpus) else "WARN"
        add("docker VM", st, f"{ncpu} CPU, {mem_gb:.1f} GB (engine_limits[{cfg.run.profile}] = {lim.cpus} CPU / {lim.mem}; "
                             f"fast = {cfg.fast.engine_limits.cpus} / {cfg.fast.engine_limits.mem})")

    # máy host
    from .results import host_info
    hi = host_info()
    ram = hi.get("ram_gb") or 0
    prof = cfg.run.profile
    home = paths.vbench_home()
    home.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(home).free / 2**30
    ram_warn = (prof == "full" and ram < 32) or (prof == "local" and ram < 16)
    add("host", "WARN" if ram_warn else "OK", f"{hi.get('vcpus')} vCPU, RAM {ram} GB, profile={prof}")
    disk_warn = prof == "full" and free_gb < 60
    add("disk VBENCH_HOME", "WARN" if disk_warn else "OK", f"trống {free_gb:.0f} GB tại {home}")

    # VBENCH_HOME + docker/.env
    try:
        probe = home / ".write_probe"
        probe.write_text("ok")
        probe.unlink()
        add("VBENCH_HOME", "OK" if home.is_absolute() else "FAIL", str(home))
    except OSError as e:
        add("VBENCH_HOME", "FAIL", f"không ghi được: {e}")
    changed, msg = ensure_env_file()
    add("docker/.env", "OK", msg)

    # image từng engine trong compose
    env = dict(read_env_file())
    doc = lifecycle._compose_doc()
    for eng in lifecycle.compose_engines():
        for svc_name in lifecycle.services_of(eng):
            img = _image_of(doc["services"][svc_name], env)
            rc, _ = _run(["docker", "image", "inspect", img])
            if rc == 0:
                add(f"image {eng}", "OK", f"{img} (có sẵn)")
            else:
                rc2, out2 = _run(["docker", "manifest", "inspect", img], timeout=60)
                add(f"image {eng}", "WARN" if rc2 == 0 else "FAIL", f"{img} ({'pull được, chưa pull' if rc2 == 0 else 'không pull được: ' + out2[:120]})")

    # client/server cùng minor (Qdrant)
    qtag = env.get("QDRANT_TAG", "v1.19.1").lstrip("v")
    qcli = _ver("qdrant-client")
    same = qtag.split(".")[:2] == qcli.split(".")[:2]
    add("qdrant client/server", "OK" if same else "WARN", f"client {qcli} · server {qtag}")

    # port
    port_keys = {"PGVECTOR_PORT": 55432, "PGVS_PORT": 55433, "QDRANT_HTTP_PORT": 56333, "QDRANT_GRPC_PORT": 56334}
    running = {c.name for e in lifecycle.compose_engines() for c in _safe_containers(e) if c.status == "running"}
    for k, default in port_keys.items():
        port = int(env.get(k, default))
        if _port_in_use(port):
            add(f"port {port}", "INFO" if running else "FAIL", "đang dùng bởi vbench" if running else "đang bị process khác chiếm")
        else:
            add(f"port {port}", "OK", "trống")

    # vm.max_map_count chỉ cần cho OpenSearch — fast-track không có profile opensearch
    if "opensearch" in lifecycle.compose_engines():
        add("vm.max_map_count", "WARN", "kiểm bằng: wsl -d docker-desktop sysctl vm.max_map_count (cần ≥ 262144)")
    else:
        add("vm.max_map_count", "INFO", "bỏ qua: compose không có profile opensearch")

    # cache model HF (tuỳ chọn)
    hf = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    mdir = hf / ("models--" + cfg.embedding.model.replace("/", "--"))
    add("HF model cache", "OK" if mdir.exists() else "WARN", f"{cfg.embedding.model}: {'có' if mdir.exists() else 'chưa tải'} ({mdir})")
    return checks


def _safe_containers(engine: str):
    try:
        return lifecycle.containers(engine)
    except Exception:
        return []


def print_checks(checks: list[Check]) -> int:
    from rich.console import Console
    from rich.table import Table

    t = Table(title="vbench doctor")
    t.add_column("kiểm tra")
    t.add_column("kết quả")
    t.add_column("chi tiết", overflow="fold")
    color = {"OK": "green", "WARN": "yellow", "FAIL": "red", "INFO": "cyan"}
    for c in checks:
        t.add_row(c.name, f"[{color[c.status]}]{c.status}[/]", c.detail)
    Console().print(t)
    return 1 if any(c.status == "FAIL" for c in checks) else 0
