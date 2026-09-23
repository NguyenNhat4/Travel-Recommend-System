"""Job embed_products: search unit trong Postgres → Cohere → collection `Product` trên Weaviate.

Luồng nạp của docs/prd/architecture.md §5 và DATABASE_SCHEMA.md bước (5), FR-SRC-02:
đọc search unit (`is_search_unit = true`) qua `DATABASE_URL`, gọi Cohere với `input_type=search_document`,
ghi vector kèm `productId` / `modelVersion` / `textHash`. Chạy lại chỉ embed phần có text hoặc model đổi
và xoá vector mồ côi (data-model.md §5 mục 4). Job ghi kết quả ra stdout, không ghi nhật ký vào DB.

Chạy từ repo root (đọc `.env` ở gốc):
    python -m src.backend.app.infrastructure.vectors.embed_products [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import hashlib
import sys

from src.backend.app.core.config import get_settings
from src.backend.app.infrastructure.embeddings.cohere_embedder import CohereEmbedder
from src.backend.app.infrastructure.vectors.postgres_store import read_catalog_rows, search_units
from src.backend.app.infrastructure.vectors.weaviate_store import StoredVector, WeaviateVectorStore

#: Tăng khi đổi text builder (domain/catalog/text_builder.py) để job embed lại toàn bộ.
TEXT_BUILDER_VERSION = "text-v1"
EXPECTED_DIM = 1024


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plan(
    items: list[tuple[str, str]], stored: dict[str, StoredVector], model_version: str
) -> tuple[list[tuple[str, str, str | None]], list[str]]:
    """items: (productId, text). Trả (cần embed: productId, text, object_id cũ | None) và object_id mồ côi."""
    wanted = {product_id for product_id, _ in items}
    todo = []
    for product_id, text in items:
        old = stored.get(product_id)
        if old and old.model_version == model_version and old.text_hash == text_hash(text):
            continue
        todo.append((product_id, text, old.object_id if old else None))
    orphans = [v.object_id for product_id, v in stored.items() if product_id not in wanted]
    return todo, orphans


def run(dry_run: bool = False, limit: int | None = None) -> dict:
    settings = get_settings()
    units, texts, _, _ = search_units(read_catalog_rows(settings.database_url))
    if not units:
        raise RuntimeError("Không có search unit — chạy `make demo-db` trước.")
    items = [(p.product_id, t) for p, t in zip(units, texts)]
    model_version = f"{settings.embedding_model_name}+{TEXT_BUILDER_VERSION}"

    store = WeaviateVectorStore(settings.weaviate_url, settings.weaviate_api_key)
    exists = store.exists()
    created = not exists and not dry_run
    if created:
        store.ensure_collection()
    stored = store.stored() if exists else {}
    todo, orphans = plan(items, stored, model_version)
    current = len(items) - len(todo)
    if limit is not None:
        # --limit dùng để thử nhanh: không xoá gì vì tập đích không còn đầy đủ.
        todo, orphans = todo[:limit], []

    report = {
        "searchUnits": len(items),
        "alreadyCurrent": current,
        "toEmbed": len(todo),
        "orphansToDelete": len(orphans),
        "modelVersion": model_version,
        "collectionCreated": created,
        "dryRun": dry_run,
    }
    if dry_run or not (todo or orphans):
        return report

    embedder = CohereEmbedder(settings.cohere_api_key, settings.embedding_model_name)
    batch = 96 * 5
    for i in range(0, len(todo), batch):
        chunk = todo[i : i + batch]
        vectors = embedder.embed_docs([text for _, text, _ in chunk])
        if vectors.shape[1] != EXPECTED_DIM:
            raise RuntimeError(f"Vector {vectors.shape[1]} chiều, PRD yêu cầu {EXPECTED_DIM}.")
        store.upsert(
            [
                {
                    "productId": product_id,
                    "modelVersion": model_version,
                    "textHash": text_hash(text),
                    "vector": vector,
                    "object_id": object_id,
                }
                for (product_id, text, object_id), vector in zip(chunk, vectors)
            ]
        )
        print(f"embedded {min(i + batch, len(todo))}/{len(todo)}", file=sys.stderr, flush=True)
    store.delete(orphans)
    report["stored"] = len(store.stored())
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="Chỉ đếm việc cần làm, không gọi Cohere, không ghi Weaviate")
    parser.add_argument("--limit", type=int, help="Chỉ embed N search unit đầu (thử nhanh, không xoá mồ côi)")
    args = parser.parse_args(argv)
    for key, value in run(dry_run=args.dry_run, limit=args.limit).items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
