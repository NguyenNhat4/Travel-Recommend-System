"""Port sinh vector cho văn bản sản phẩm và câu truy vấn."""
from __future__ import annotations

from typing import Protocol

import numpy as np


class EmbedderPort(Protocol):
    """Tuỳ chọn (duck-typing, use case kiểm bằng `getattr`): `embed_query_status(q) -> (vector, "hit" | "miss")` của adapter
    có cache (`application/search/query_cache.py`), `embed_queries(texts)` embed cả lô câu truy vấn (`input_type`
    search_query) cho prewarm."""
    name: str

    def embed_docs(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, q: str) -> np.ndarray: ...
