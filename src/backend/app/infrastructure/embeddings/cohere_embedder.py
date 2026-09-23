"""EmbedderPort qua Cohere Embed API v2 (docs/prd/architecture.md §4–§5, FR-SRC-02).

Gọi REST bằng httpx thay vì SDK `cohere` để không thêm dependency. Bắt buộc phân biệt `input_type`:
`search_document` khi nạp, `search_query` khi truy vấn — dùng sai làm giảm chất lượng xếp hạng mà
không báo lỗi.
"""
from __future__ import annotations

import logging
import time

import httpx
import numpy as np

logger = logging.getLogger("uvicorn.error")

COHERE_EMBED_URL = "https://api.cohere.com/v2/embed"
#: Giới hạn số text mỗi request của Cohere Embed API.
MAX_TEXTS_PER_CALL = 96


class CohereEmbedder:
    def __init__(
        self,
        api_key: str,
        model: str = "embed-multilingual-v3.0",
        *,
        client: httpx.Client | None = None,
        max_retries: int = 5,
    ):
        if not api_key:
            raise RuntimeError("Thiếu COHERE_API_KEY.")
        self.name = model
        self._client = client or httpx.Client(timeout=60)
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._max_retries = max_retries

    def embed_docs(self, texts: list[str]) -> np.ndarray:
        chunks = [
            self._embed(texts[i : i + MAX_TEXTS_PER_CALL], "search_document")
            for i in range(0, len(texts), MAX_TEXTS_PER_CALL)
        ]
        return np.vstack(chunks) if chunks else np.zeros((0, 0), dtype=np.float32)

    def embed_query(self, q: str) -> np.ndarray:
        return self._embed([q], "search_query")[0]

    def _embed(self, texts: list[str], input_type: str) -> np.ndarray:
        body = {"model": self.name, "texts": texts, "input_type": input_type, "embedding_types": ["float"]}
        for attempt in range(self._max_retries + 1):
            response = self._client.post(COHERE_EMBED_URL, json=body, headers=self._headers)
            # 429: key trial bị giới hạn số lần gọi mỗi phút; chờ rồi thử lại thay vì bỏ cả job.
            if response.status_code == 429 and attempt < self._max_retries:
                wait = float(response.headers.get("Retry-After") or 2 ** (attempt + 2))
                logger.warning("cohere.embed.rate_limited wait=%.0fs attempt=%d", wait, attempt + 1)
                time.sleep(wait)
                continue
            response.raise_for_status()
            vectors = np.asarray(response.json()["embeddings"]["float"], dtype=np.float32)
            # Cohere v3 đã chuẩn hoá L2; chuẩn hoá lại để cosine ≈ inner product dù model đổi.
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            return vectors / np.where(norms == 0, 1, norms)
        raise RuntimeError("Cohere Embed API vẫn trả 429 sau khi thử lại.")
