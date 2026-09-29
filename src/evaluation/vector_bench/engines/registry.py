"""Tên engine → class. Import lười: worker chỉ import client của engine mình (docker research: 64 worker × qdrant_client ≈ 4,6 GB)."""
from __future__ import annotations

import importlib
from typing import Any

from ..config import VBenchConfig
from .base import StoreOptions

ENGINES: dict[str, str] = {
    "pgvector": "evaluation.vector_bench.engines.pgvector:PgVectorStore",
    "pgvectorscale": "evaluation.vector_bench.engines.pgvectorscale:PgVectorScaleStore",
    "qdrant": "evaluation.vector_bench.engines.qdrant:QdrantStore",
    "null": "evaluation.vector_bench.engines.null:NullStore",    # engine giả trả ngay — hiệu chỉnh harness (Part 11)
}


def engine_class(name: str) -> type:
    if name not in ENGINES:
        raise KeyError(f"engine '{name}' chưa có adapter (có: {sorted(ENGINES)})")
    mod, cls = ENGINES[name].split(":")
    return getattr(importlib.import_module(mod), cls)


def make_store(cfg: VBenchConfig, name: str, dim: int, opts: StoreOptions | None = None) -> Any:
    cls = engine_class(name)
    ec = cfg.engines.get(name)
    return cls(ec, dim, opts or StoreOptions())
