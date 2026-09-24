"""Đường dẫn chuẩn (spec §1.1): SBENCH_HOME, thư mục data theo dataset, cache dùng chung, tên file.

Gốc repo lấy từ `evaluation.vector_bench.paths` (dùng lại, không chép). Đường dẫn tương đối — trong config hay trong
`SBENCH_HOME` — tính từ gốc repo, không phụ thuộc thư mục đang đứng.
"""
from __future__ import annotations

import os
from pathlib import Path

from evaluation.vector_bench.paths import repo_root, resolve_repo_path

__all__ = ["repo_root", "resolve_repo_path"]

PKG_DIR = Path(__file__).resolve().parent
CONFIG_DIR = PKG_DIR / "config"
DEFAULT_CONFIG = CONFIG_DIR / "sbench.yaml"
ARMS_DIR = PKG_DIR / "arms"
GOLD_DIR = PKG_DIR / "gold"          # của Người A: drafts.txt, pool*.csv, gold.jsonl — commit
COMPOSE_FILE = PKG_DIR / "docker" / "compose.yml"

DATASETS = ("jsonl", "sample", "fake")      # jsonl = catalog thật; sample/fake nằm thư mục riêng để không đè

# tên file trong data_dir(dataset)
ITEMS = "items.parquet"
STATS = "stats.json"
AMENITY_VOCAB = "amenity_vocab.json"
AMENITY_FUZZY_HITS = "amenity_fuzzy_hits.csv"
VOCAB = "vocab.json"

# tên file trong cache_dir() — dùng chung mọi dataset
EMBED_CACHE = "embeddings.sqlite"
COST_LOG = "cost.jsonl"


def sbench_home() -> Path:
    env = os.environ.get("SBENCH_HOME")
    home = Path(env) if env else repo_root() / "bench_out" / "search"
    if not home.is_absolute():
        home = repo_root() / home
    return home.resolve()


def check_dataset(dataset: str) -> str:
    if dataset not in DATASETS:
        raise ValueError(f"dataset không hợp lệ: {dataset!r} (chọn {', '.join(DATASETS)})")
    return dataset


def data_dir(dataset: str = "jsonl", create: bool = True) -> Path:
    check_dataset(dataset)
    d = sbench_home() / "data"
    if dataset != "jsonl":
        d = d / f"_{dataset}"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir(create: bool = True) -> Path:
    d = sbench_home() / "cache"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def run_dir(run_id: str, create: bool = True) -> Path:
    d = sbench_home() / "runs" / run_id
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d
