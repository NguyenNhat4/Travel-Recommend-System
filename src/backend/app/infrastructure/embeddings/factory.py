"""Chọn adapter embedding theo `EMBED_PROVIDER` — dùng chung cho composition root, job index và công cụ vận hành.

`local` (mặc định, FR-SRC-02 chốt 06/10): `LocalE5Embedder` chạy `intfloat/multilingual-e5-small` trong tiến trình.
`cohere`: `CohereEmbedder` (`embed-multilingual-v3.0`) — đường lui, đi cùng collection `Product` 1024 chiều.
`modelVersion` của vector = `<EMBED_MODEL>:<TEXT_BUILDER_VERSION>`; query và document luôn cùng model, cùng text builder.
"""
from __future__ import annotations

from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION


def model_version(model_name: str) -> str:
    return f"{model_name}:{TEXT_BUILDER_VERSION}"


def embedding_model_version(settings) -> str:
    return model_version(settings.embed_model)


def build_embedder(settings, *, limiter=None):
    """Adapter theo `settings.embed_provider`. `limiter` (`CallLimiter`) chỉ có nghĩa với Cohere (job index)."""
    if settings.embed_provider == "local":
        from src.backend.app.infrastructure.embeddings.local_e5_embedder import LocalE5Embedder

        return LocalE5Embedder(
            settings.embed_model,
            revision=settings.embed_model_revision,
            dimension=settings.embed_dimension,
            threads=settings.embed_threads,
            batch_size=settings.embed_batch_size,
            max_length=settings.embed_max_length,
            cache_dir=settings.embed_cache_dir or None,
        )
    from src.backend.app.infrastructure.embeddings.cohere_embedder import CohereEmbedder

    return CohereEmbedder(
        settings.cohere_api_key,
        settings.embed_model,
        base_url=settings.cohere_base_url,
        dimension=settings.embed_dimension,
        timeout_seconds=settings.cohere_timeout_seconds,
        limiter=limiter,
    )
