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
from src.backend.app.infrastructure.vectors.weaviate_store import WeaviateClient, lexical_properties


def model_version(model_name: str) -> str:
    return f"{model_name}:{TEXT_BUILDER_VERSION}"


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run(*, dry_run: bool = False, backfill_lexical: bool = False) -> dict[str, int | str]:
    settings = get_settings()
    catalog = PostgresCatalogReader(settings.database_url).load()
    version = model_version(settings.embed_model)
    client = WeaviateClient(
        settings.weaviate_url,
        collection=settings.weaviate_collection,
        api_key=settings.weaviate_api_key,
        timeout_seconds=settings.weaviate_timeout_seconds,
        bm25_k1=settings.search_bm25_k1,
        bm25_b=settings.search_bm25_b,
    )
    try:
        client.ready()
        client.ensure_collection()
        existing, _ = client.fetch(include_vectors=False)
        desired = {
            product.product_id: (text, text_hash(text), product.name)
            for product, text in zip(catalog.units, catalog.texts, strict=True)
        }
        changed = [
            product_id
            for product_id, (_, digest, _name) in desired.items()
            if product_id not in existing
            or existing[product_id].text_hash != digest
            or existing[product_id].model_version != version
        ]
        orphans = sorted(set(existing) - set(desired))
        # Object index trước 25/09 chưa có property BM25: ghi thêm bằng PATCH, không gọi Cohere (chỉ khi được yêu cầu).
        stale_lexical = [
            product_id for product_id in desired
            if product_id in existing and product_id not in set(changed) and not existing[product_id].lexical
        ]
        report: dict[str, int | str] = {
            "modelVersion": version,
            "searchUnits": len(desired),
            "unchanged": len(desired) - len(changed),
            "embedded": len(changed),
            "deletedOrphans": len(orphans),
            "missingLexical": len(stale_lexical),
            "backfilledLexical": len(stale_lexical) if backfill_lexical else 0,
        }
        if dry_run or (not changed and not orphans and not (backfill_lexical and stale_lexical)):
            return report

        embedder = CohereEmbedder(
            settings.cohere_api_key,
            settings.embed_model,
            base_url=settings.cohere_base_url,
            dimension=settings.embed_dimension,
            timeout_seconds=settings.cohere_timeout_seconds,
        )
        try:
            # Embed and write one Cohere batch at a time so a rate-limit failure keeps finished work;
            # rerunning the job then only embeds what is still missing.
            step = CohereEmbedder.batch_size
            for start in range(0, len(changed), step):
                ids = changed[start : start + step]
                vectors = embedder.embed_docs([desired[product_id][0] for product_id in ids])
                client.delete([existing[product_id].uuid for product_id in ids if product_id in existing])
                client.insert([
                    {
                        "class": settings.weaviate_collection,
                        "id": client.object_uuid(product_id),
                        "properties": {
                            "productId": product_id,
                            "modelVersion": version,
                            "textHash": desired[product_id][1],
                            **lexical_properties(desired[product_id][2], desired[product_id][0]),
                        },
                        "vector": vector.tolist(),
                    }
                    for product_id, vector in zip(ids, vectors, strict=True)
                ])
                print(f"indexed {min(start + step, len(changed))}/{len(changed)}", flush=True)
        finally:
            embedder.close()

        if backfill_lexical:
            for done, product_id in enumerate(stale_lexical, 1):
                text, _digest, name = desired[product_id]
                client.patch_properties(existing[product_id].uuid, lexical_properties(name, text))
                if done % 200 == 0 or done == len(stale_lexical):
                    print(f"backfilled lexical {done}/{len(stale_lexical)}", flush=True)

        client.delete([existing[product_id].uuid for product_id in orphans])
        return report
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="chỉ đếm phần cần cập nhật, không gọi Cohere hoặc ghi Weaviate")
    parser.add_argument("--backfill-lexical", action="store_true",
                        help="ghi property BM25 (nameAscii/searchTextAscii) cho object đã index mà còn thiếu; không gọi Cohere")
    args = parser.parse_args(argv)
    print(json.dumps(run(dry_run=args.dry_run, backfill_lexical=args.backfill_lexical), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
