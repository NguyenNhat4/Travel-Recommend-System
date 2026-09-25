"""Cohere Embed v2 adapter for the fixed multilingual catalog model."""
from __future__ import annotations

import time

import httpx
import numpy as np


class CohereEmbedder:
    """EmbedderPort using Cohere `embed-multilingual-v3.0` (1024 dimensions).

    Search quality depends on using `search_document` for catalog text and
    `search_query` for user queries. Keeping both calls in one adapter prevents
    callers from accidentally swapping those input types.
    """

    batch_size = 96
    max_attempts = 6

    def __init__(
        self,
        api_key: str,
        model_name: str = "embed-multilingual-v3.0",
        *,
        base_url: str = "https://api.cohere.com",
        dimension: int = 1024,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ):
        if not api_key:
            raise RuntimeError("COHERE_API_KEY is required to embed catalog or search queries")
        self.name = model_name
        self.dimension = dimension
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}", "X-Client-Name": "vota-recsys"},
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    @staticmethod
    def _backoff_seconds(response: httpx.Response, attempt: int) -> float:
        """Honor Retry-After when Cohere sends it; otherwise back off up to 60s (rate limits are per minute)."""
        try:
            return min(float(response.headers["Retry-After"]), 120.0)
        except (KeyError, ValueError):
            return min(2.0 ** (attempt + 1), 60.0)

    def _request(self, texts: list[str], input_type: str) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        response: httpx.Response | None = None
        for attempt in range(self.max_attempts):
            response = self._client.post(
                "/v2/embed",
                json={
                    "model": self.name,
                    "texts": texts,
                    "input_type": input_type,
                    "embedding_types": ["float"],
                    "truncate": "END",
                },
            )
            if response.status_code not in {429, 500, 502, 503, 504}:
                break
            if attempt < self.max_attempts - 1:
                time.sleep(self._backoff_seconds(response, attempt))
        assert response is not None
        response.raise_for_status()
        vectors = np.asarray(response.json()["embeddings"]["float"], dtype=np.float32)
        if vectors.shape != (len(texts), self.dimension):
            raise RuntimeError(
                f"Cohere returned shape {vectors.shape}; expected ({len(texts)}, {self.dimension}) for {self.name}"
            )
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise RuntimeError("Cohere returned a zero-length embedding")
        return vectors / norms

    def embed_docs(self, texts: list[str]) -> np.ndarray:
        chunks = [
            self._request(texts[i : i + self.batch_size], "search_document")
            for i in range(0, len(texts), self.batch_size)
        ]
        return np.concatenate(chunks) if chunks else np.empty((0, self.dimension), dtype=np.float32)

    def embed_query(self, q: str) -> np.ndarray:
        return self._request([q], "search_query")[0]
