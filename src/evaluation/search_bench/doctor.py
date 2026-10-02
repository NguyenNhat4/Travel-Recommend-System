"""Part 0 — `sb doctor`: kiểm môi trường, mỗi dòng ✔ / ! / ✖ / · kèm hướng dẫn sửa. ✖ → exit 1.

Kiểm tra gọi mạng: Weaviate local (HTTP ready + meta) và một lượt `tokenize` của Cohere để xác nhận key (không tốn tiền
nhưng tính vào quota lượt gọi của key trial → ghi `cost.jsonl`; bỏ bằng `--skip-api`).
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from . import costlog, paths
from .config import SBenchConfig

OK, WARN, FAIL, INFO = "OK", "WARN", "FAIL", "INFO"
ICON = {OK: "✔", WARN: "!", FAIL: "✖", INFO: "·"}


@dataclass
class Check:
    name: str
    status: str
    detail: str
    hint: str = ""


def _version_tuple(v: str) -> tuple[int, ...]:
    out = []
    for part in v.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def version_at_least(v: str, minimum: str) -> bool:
    a, b = _version_tuple(v), _version_tuple(minimum)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) >= b + (0,) * (n - len(b))


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def _port_hint(port: int) -> str:
    base = "cd src && docker compose -f evaluation/search_bench/docker/compose.yml up -d --wait weaviate"
    if sys.platform == "win32":
        base += (f"; nếu container không bind được cổng {port}: `netsh int ipv4 show excludedportrange protocol=tcp` "
                 "rồi đặt SBENCH_WEAVIATE_HTTP_PORT / SBENCH_WEAVIATE_GRPC_PORT ngoài các dải bị giữ (và sửa weaviate.url / grpc_port)")
    return base


def check_docker() -> Check:
    exe = shutil.which("docker")
    if not exe:
        return Check("docker", FAIL, "không thấy lệnh docker", "cài/khởi động Docker Desktop")
    try:
        r = subprocess.run([exe, "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return Check("docker", FAIL, "docker info quá 15 s", "khởi động lại Docker Desktop")
    if r.returncode != 0 or not r.stdout.strip():
        return Check("docker", FAIL, (r.stderr or "daemon không trả lời").strip().splitlines()[-1][:160], "mở Docker Desktop")
    return Check("docker", OK, f"server {r.stdout.strip()}")


def weaviate_version(cfg: SBenchConfig) -> str | None:
    url = cfg.weaviate.url.rstrip("/")
    try:
        if httpx.get(f"{url}/v1/.well-known/ready", timeout=3).status_code != 200:
            return None
        return str(httpx.get(f"{url}/v1/meta", timeout=3).json().get("version"))
    except httpx.HTTPError:
        return None


def check_weaviate(cfg: SBenchConfig) -> tuple[list[Check], str | None]:
    u = urlparse(cfg.weaviate.url)
    host, port = u.hostname or "127.0.0.1", u.port or 80
    ver = weaviate_version(cfg)
    if ver is None:
        return [Check("weaviate", FAIL, f"{cfg.weaviate.url} chưa ready", _port_hint(port))], None
    out = []
    if version_at_least(ver, cfg.doctor.min_weaviate_version):
        out.append(Check("weaviate", OK, f"{cfg.weaviate.url} ready, version {ver}"))
    else:
        out.append(Check("weaviate", FAIL, f"version {ver} < {cfg.doctor.min_weaviate_version}",
                         f"image trong docker/compose.yml phải là {cfg.weaviate.image}"))
    grpc_ok = _port_open(host, cfg.weaviate.grpc_port)
    out.append(Check("weaviate gRPC", OK if grpc_ok else FAIL, f"{host}:{cfg.weaviate.grpc_port} {'mở' if grpc_ok else 'đóng'}",
                     "" if grpc_ok else _port_hint(cfg.weaviate.grpc_port)))
    return out, ver


def check_ascii_fold(cfg: SBenchConfig, server_version: str | None) -> Check:
    mode = cfg.weaviate.ascii_fold
    if mode == "shadow":
        return Check("ascii_fold", INFO, "shadow: property *_ascii do app fold, query cũng fold")
    try:
        from weaviate.classes.config import Configure
        client_ok = hasattr(Configure, "text_analyzer")
    except ImportError:
        client_ok = False
    server_ok = server_version is not None and version_at_least(server_version, "1.37")
    if client_ok and server_ok:
        return Check("ascii_fold", OK, "analyzer: text_analyzer(ascii_fold=True) trên name, embed_text")
    why = []
    if not client_ok:
        why.append("weaviate-client thiếu Configure.text_analyzer (cần ≥ 4.23)")
    if not server_ok:
        why.append(f"server {server_version or 'chưa chạy'} < 1.37")
    return Check("ascii_fold", FAIL, "analyzer không dùng được: " + "; ".join(why),
                 "nâng client/server, hoặc đặt weaviate.ascii_fold: shadow trong config/sbench.yaml")


def tokenize_probe(api_key: str, api_model: str) -> int:
    """Một lượt `tokenize` qua API (offline=False: SDK mặc định tải tokenizer rồi đếm local, không kiểm được key)."""
    import cohere
    with httpx.Client(timeout=15) as http:
        co = cohere.ClientV2(api_key=api_key, httpx_client=http)
        r = co.tokenize(text="xin chào", model=api_model, offline=False, request_options={"max_retries": 0})
    n = len(r.tokens)
    costlog.append(endpoint="tokenize", model=api_model, input_type=None, n_texts=1, n_tokens=n, usd=0.0, source="doctor")
    return n


def check_cohere(cfg: SBenchConfig, skip_api: bool) -> Check:
    key = os.environ.get("COHERE_API_KEY")
    if not key:
        return Check("COHERE_API_KEY", FAIL, "chưa có trong môi trường hay .env gốc repo", "thêm dòng COHERE_API_KEY=… vào .env ở gốc repo")
    if skip_api:
        return Check("COHERE_API_KEY", INFO, f"có ({len(key)} ký tự) — bỏ qua gọi thử (--skip-api)")
    api_model = cfg.model_cfg("cohere-v3").api_model
    try:
        n = tokenize_probe(key, api_model)
    except Exception as e:  # noqa: BLE001 — in lỗi của SDK, không in key
        msg = str(e).replace(key, "***")
        return Check("COHERE_API_KEY", FAIL, f"tokenize lỗi: {msg[:200]}", "kiểm key còn hạn / đúng tài khoản")
    return Check("COHERE_API_KEY", OK, f"hợp lệ — tokenize('xin chào', {api_model}) = {n} token")


def _count_lines(p: Path) -> int:
    with open(p, "rb") as fh:
        return sum(chunk.count(b"\n") for chunk in iter(lambda: fh.read(1 << 20), b""))


def check_catalog(cfg: SBenchConfig) -> list[Check]:
    out = []
    p = paths.resolve_repo_path(cfg.catalog.products_path)
    snap = paths.resolve_repo_path(cfg.catalog.snapshot_path)
    if p.exists():
        out.append(Check("products.jsonl", OK, f"{cfg.catalog.products_path}: {_count_lines(p)} dòng"))
    elif snap.exists():
        out.append(Check("products.jsonl", WARN, f"chưa bung; có snapshot {cfg.catalog.snapshot_path}",
                         "`sb catalog build --source jsonl` tự bung và kiểm checksum"))
    else:
        out.append(Check("products.jsonl", FAIL, "không có bản bung lẫn snapshot", "sửa catalog.products_path / snapshot_path"))
    s = paths.resolve_repo_path(cfg.catalog.sample_path)
    out.append(Check("sample", OK if s.exists() else WARN, f"{cfg.catalog.sample_path}: {_count_lines(s)} dòng" if s.exists()
                     else "không có file sample"))
    return out


def check_bge_m3() -> Check:
    """Model local (E2: e5-base, bge-m3, gte): cần transformers + torch (embed/local_hf.py — không dùng sentence-transformers
    vì scipy bị Application Control chặn trên máy dev 30/09); model trong cache HF thì embed offline được."""
    missing = [lib for lib in ("transformers", "torch") if importlib.util.find_spec(lib) is None]
    if missing:
        return Check("local models", WARN, f"thiếu {', '.join(missing)} (chỉ cần cho E2/P5)",
                     "pip install -r src/evaluation/search_bench/requirements-extra.txt")
    hub = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    cached = [m for m in ("intfloat/multilingual-e5-base", "BAAI/bge-m3") if (hub / ("models--" + m.replace("/", "--"))).exists()]
    return Check("local models", OK if cached else WARN,
                 f"trong cache HF: {', '.join(cached)}" if cached else "chưa tải e5-base / bge-m3 (tải khi chạy E2)")


def check_disk(cfg: SBenchConfig) -> Check:
    home = paths.sbench_home()
    probe = home if home.exists() else paths.repo_root()
    free_gb = shutil.disk_usage(probe).free / 1e9
    ok = free_gb >= cfg.doctor.min_free_gb
    return Check("disk", OK if ok else FAIL, f"{free_gb:.1f} GB trống tại {probe}",
                 "" if ok else f"cần ≥ {cfg.doctor.min_free_gb} GB")


def check_gold_tags() -> Check:
    try:
        r = subprocess.run(["git", "tag", "-l", "gold_v*"], cwd=paths.repo_root(), capture_output=True, text=True, timeout=5)
        tags = r.stdout.split()
    except (OSError, subprocess.TimeoutExpired):
        tags = []
    return Check("gold tags", INFO, ", ".join(tags) if tags else "chưa có gold_v* (bình thường trước ngày 4)")


def run_doctor(cfg: SBenchConfig, *, skip_api: bool = False) -> list[Check]:
    checks = [check_docker()]
    wv, ver = check_weaviate(cfg)
    checks += wv
    checks.append(check_ascii_fold(cfg, ver))
    checks.append(check_cohere(cfg, skip_api))
    checks += check_catalog(cfg)
    checks += [check_bge_m3(), check_disk(cfg), check_gold_tags()]
    return checks


def print_checks(checks: list[Check]) -> int:
    from rich.console import Console
    c = Console(soft_wrap=True)
    for ch in checks:
        color = {OK: "green", WARN: "yellow", FAIL: "red", INFO: "dim"}[ch.status]
        c.print(f"[{color}]{ICON[ch.status]}[/] {ch.name:<16} {ch.detail}", highlight=False)
        if ch.hint and ch.status in (WARN, FAIL):
            c.print(f"    → {ch.hint}", style="dim", highlight=False)
    return 1 if any(ch.status == FAIL for ch in checks) else 0
