"""Dựng EmbedderPort e5-small (PRD FR-SRC-02) — dùng chung cho composition root (main.py) và job index (jobs/embed_products.py)."""
from __future__ import annotations

from src.backend.app.core.config import Settings
from src.backend.app.infrastructure.embeddings.local_e5_embedder import LocalE5Embedder


def build_embedder(settings: Settings) -> LocalE5Embedder:
    return LocalE5Embedder(
        settings.embed_model,
        revision=settings.embed_model_revision or None,
        dimension=settings.embed_dimension,
        device=settings.embed_device,
        batch_size=settings.embed_batch_size,
        max_tokens=settings.embed_max_tokens,
    )
