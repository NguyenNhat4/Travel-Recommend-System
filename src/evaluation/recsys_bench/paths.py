"""Đường dẫn của harness: mọi file sinh ra nằm dưới `bench_out/recsys/` (đã gitignore), không commit."""
from __future__ import annotations

import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
FROZEN_DIR = PKG_DIR / "frozen"       # split đóng băng (B2, 01/10) — commit; bench_out/ thì không


def repo_root() -> Path:
    for p in (PKG_DIR, *PKG_DIR.parents):
        if (p / ".git").exists():   # worktree có `.git` là file, vẫn đúng
            return p
    raise RuntimeError(f"không tìm thấy gốc repo (.git) từ {PKG_DIR}")


def recsys_home() -> Path:
    """`RECSYS_HOME` nếu có (tương đối thì tính từ gốc repo), mặc định `bench_out/recsys`."""
    env = os.environ.get("RECSYS_HOME")
    home = Path(env) if env else repo_root() / "bench_out" / "recsys"
    return home if home.is_absolute() else repo_root() / home


def cache_dir() -> Path:
    return recsys_home() / "cache"


def run_dir(run_id: str) -> Path:
    return recsys_home() / "runs" / run_id
