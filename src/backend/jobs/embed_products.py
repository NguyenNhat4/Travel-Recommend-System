"""Incrementally index PostgreSQL catalog search units into Weaviate.

Run from repository root:
    python -m src.backend.jobs.embed_products
"""
from __future__ import annotations

import argparse
import hashlib
import json

from src.backend.app.core.config import get_settings
from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION
from src.backend.app.infrastructure.embeddings.cohere_embedder import CohereEmbedder
from src.backend.app.infrastructure.vectors.postgres_store import PostgresCatalogReader
from src.backend.app.infrastructure.vectors.weaviate_store import WeaviateClient


def model_version(model_name: str) -> str:
    return f"{model_name}:{TEXT_BUILDER_VERSION}"


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run(*, dry_run: bool = False) -> dict[str, int | str]:
    settings = get_settings()
    catalog = PostgresCatalogReader(settings.database_url).load()
    version = model_version(settings.embed_model)
    client = WeaviateClient(
        settings.weaviate_url,
        collection=settings.weaviate_collection,
        api_key=settings.weaviate_api_key,
        timeout_seconds=settings.weaviate_timeout_seconds,
    )
    try:
        client.ready()
        client.ensure_collection()
        existing, _ = client.fetch(include_vectors=False)
        desired = {
            product.product_id: (text, text_hash(text))
            for product, text in zip(catalog.units, catalog.texts, strict=True)
        }
        changed = [
            product_id
            for product_id, (_, digest) in desired.items()
            if product_id not in existing
            or existing[product_id].text_hash != digest
            or existing[product_id].model_version != version
        ]
        orphans = sorted(set(existing) - set(desired))
        report: dict[str, int | str] = {
            "modelVersion": version,
            "searchUnits": len(desired),
            "unchanged": len(desired) - len(changed),
            "embedded": len(changed),
            "deletedOrphans": len(orphans),
        }
        if dry_run or (not changed and not orphans):
            return report

        embedder = CohereEmbedder(
            settings.cohere_api_key,
            settings.embed_model,
            base_url=settings.cohere_base_url,
            dimension=settings.embed_dimension,
            timeout_seconds=settings.cohere_timeout_seconds,
        )
        try:
            vectors = embedder.embed_docs([desired[product_id][0] for product_id in changed])
        finally:
            embedder.close()

        stale_ids = [existing[product_id].uuid for product_id in changed if product_id in existing]
        stale_ids.extend(existing[product_id].uuid for product_id in orphans)
        client.delete(stale_ids)
        client.insert([
            {
                "class": settings.weaviate_collection,
                "id": client.object_uuid(product_id),
                "properties": {
                    "productId": product_id,
                    "modelVersion": version,
                    "textHash": desired[product_id][1],
                },
                "vector": vector.tolist(),
            }
            for product_id, vector in zip(changed, vectors, strict=True)
        ])
        return report
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="chỉ đếm phần cần cập nhật, không gọi Cohere hoặc ghi Weaviate")
    args = parser.parse_args(argv)
    print(json.dumps(run(dry_run=args.dry_run), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
