"""Đường dẫn chuẩn (spec §1.1): gốc repo, VBENCH_HOME, thư mục data/run, tên file.

Không phụ thuộc thư mục đang đứng: gốc repo = thư mục cha gần nhất chứa `.git`.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
CONFIG_DIR = PKG_DIR / "config"
DOCKER_DIR = PKG_DIR / "docker"
COMPOSE_FILE = DOCKER_DIR / "compose.yml"
DOCKER_ENV_FILE = DOCKER_DIR / ".env"
DOCKER_ENV_EXAMPLE = DOCKER_DIR / ".env.example"
DEFAULT_CONFIG = CONFIG_DIR / "vbench.yaml"

# Tên file chuẩn trong bench_out/data/<scale>/
ITEMS = "items.parquet"
AMENITY_VOCAB = "amenity_vocab.json"
STATS = "stats.json"
VECTORS = "vectors.npy"
EMBED_META = "embed_meta.json"
EMBED_HASHES = "embed_hashes.json"
QUERIES = "queries.jsonl"
QUERIES_STATS = "queries_stats.json"
QUERY_VECTORS = "query_vectors.npy"
QUERY_EMBED_META = "query_embed_meta.json"
GT = "gt.npz"
GATE_QUERIES = "gate_queries.jsonl"


@lru_cache(maxsize=1)
def repo_root() -> Path:
    for p in (PKG_DIR, *PKG_DIR.parents):
        if (p / ".git").exists():
            return p
    raise RuntimeError(f"không tìm thấy gốc repo (.git) từ {PKG_DIR}")


def src_dir() -> Path:
    return repo_root() / "src"


def vbench_home() -> Path:
    env = os.environ.get("VBENCH_HOME")
    home = Path(env) if env else repo_root() / "bench_out"
    if not home.is_absolute():
        home = repo_root() / home
    return home.resolve()


def data_dir(scale: str, create: bool = True) -> Path:
    d = vbench_home() / "data" / scale
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def run_dir(run_id: str, create: bool = True) -> Path:
    d = vbench_home() / "runs" / run_id
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def step_dir(run_id: str, engine: str, scale: str, create: bool = True) -> Path:
    d = run_dir(run_id, create=False) / engine / scale
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    d = vbench_home() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resolve_repo_path(p: str | Path) -> Path:
    """Đường dẫn tương đối trong config tính từ gốc repo."""
    p = Path(p)
    return p if p.is_absolute() else (repo_root() / p)
