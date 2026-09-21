"""Cấu hình đọc từ env. Không import gì ngoài stdlib/pydantic."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    products_path: str = os.getenv("PRODUCTS_PATH", "data/products.jsonl")
    events_path: str | None = os.getenv("EVENTS_PATH")  # JSONL cdp.events cho LocalCdpClient (mock); None = rỗng
    embed_model: str = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-base")  # đổi sau benchmark tuần 2
    embed_cache_dir: str = os.getenv("EMBED_CACHE_DIR", ".embcache")
    search_cutoff: float = float(os.getenv("SEARCH_CUTOFF", "0.80"))  # calibrate theo model — xem EMBEDDING_AND_ENGINES.md §4.4
    search_max_limit: int = 50
    recommend_candidate_k: int = 200


settings = Settings()
