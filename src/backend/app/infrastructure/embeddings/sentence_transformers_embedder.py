from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("uvicorn.error")


class SentenceTransformersEmbedder:
    """EmbedderPort. e5 cần prefix query:/passage:; bge-m3 / gte không cần."""

    def __init__(self, model_name: str):
        logger.info("startup.recsys.embedding_model.load.start model=%s", model_name)
        from sentence_transformers import SentenceTransformer

        self.name = model_name
        self.model = SentenceTransformer(model_name)
        self._e5 = "e5" in model_name.lower()
        logger.info("startup.recsys.embedding_model.load.ready model=%s", model_name)

    def embed_docs(self, texts: list[str]) -> np.ndarray:
        if self._e5:
            texts = ["passage: " + t for t in texts]
        return self.model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True).astype(np.float32)

    def embed_query(self, q: str) -> np.ndarray:
        if self._e5:
            q = "query: " + q
        return self.model.encode([q], normalize_embeddings=True)[0].astype(np.float32)
