"""Read-only loading of the seeded catalog and CDP event snapshot."""
from __future__ import annotations

import os
from dataclasses import dataclass

from src.backend.app.application.ports import UnitIndex


@dataclass(frozen=True)
class EvaluationData:
    index: UnitIndex
    events: list[dict]
    source_label: str


def load_evaluation_data() -> EvaluationData:
    """Load the DB-backed search-unit catalog and events through existing adapters."""
    catalog_url = os.getenv("DATABASE_URL") or os.getenv("BACKEND_DATABASE_URL")
    cdp_url = os.getenv("CDP_DATABASE_URL") or os.getenv("BACKEND_CDP_DATABASE_URL")
    missing = [name for name, value in (("DATABASE_URL", catalog_url), ("CDP_DATABASE_URL", cdp_url)) if not value]
    if missing:
        raise RuntimeError(
            "Thiếu cấu hình read-only: " + ", ".join(missing)
            + ". Cấu hình DATABASE_URL và CDP_DATABASE_URL theo README của Evaluation."
        )

    from src.backend.app.infrastructure.cdp.postgres_cdp_reader import PostgresCdpReader
    from src.backend.app.infrastructure.embeddings.sentence_transformers_embedder import SentenceTransformersEmbedder
    from src.backend.app.infrastructure.vectors.postgres_store import PostgresVectorStore

    model_name = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-base")
    cache_dir = os.getenv("EMBED_CACHE_DIR", ".embcache")
    index = PostgresVectorStore(catalog_url, SentenceTransformersEmbedder(model_name), cache_dir).load()
    events = PostgresCdpReader(cdp_url).all_events()
    if not events:
        raise RuntimeError("CDP chưa có event để đánh giá. Nạp seed trước bằng `make demo-db`.")
    return EvaluationData(index=index, events=events, source_label="PostgreSQL local · seed tổng hợp")
