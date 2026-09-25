"""Port sinh vector cho văn bản sản phẩm và câu truy vấn."""
from __future__ import annotations

from typing import Protocol

import numpy as np


class EmbedderPort(Protocol):
    name: str

    def embed_docs(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, q: str) -> np.ndarray: ...
