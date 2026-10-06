"""Incrementally index PostgreSQL catalog search units into Weaviate.

Run from repository root:
    python -m src.backend.jobs.embed_products
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from src.backend.app.core.config import get_settings
from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION
from src.backend.app.infrastructure.embeddings.factory import build_embedder
from src.backend.app.infrastructure.vectors.postgres_store import PostgresCatalogReader
from src.backend.app.infrastructure.vectors.weaviate_store import WeaviateClient, lexical_properties


def model_version(model_name: str) -> str:
    return f"{model_name}:{TEXT_BUILDER_VERSION}"


def foreign_models(existing: dict, model_name: str) -> list[str]:
    """Model khác đang có vector trong collection. Khác model thường khác số chiều (Cohere 1024, e5-small 384) và luôn khác
    không gian vector: ghi đè từng phần sẽ trộn hai không gian, Weaviate từ chối vector sai chiều giữa chừng. Job không tự
    xoá collection — dùng collection riêng (`WEAVIATE_COLLECTION`) cho model mới."""
    return sorted({obj.model_version.rsplit(":", 1)[0] for obj in existing.values() if obj.model_version} - {model_name})


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


PREVIEW_DIMS = 8


def vector_preview(vector) -> dict:
    values = np.asarray(vector, dtype=np.float64)
    return {"dims": int(values.size), "norm": round(float(np.linalg.norm(values)), 6),
            "head": [round(float(v), 6) for v in values[:PREVIEW_DIMS]]}


def write_detail(path: Path, catalog, desired: dict, reasons: dict, previews: dict, orphans: list,
                 orphans_deleted: bool) -> None:
    """Một dòng JSON mỗi search unit (text đem embed, hash, hành động, vài chiều đầu của vector) và mỗi vector mồ côi.

    Chỉ để người vận hành xem lại lượt index; không lưu cả vector để file không phình theo số chiều."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    units = {product.product_id: product for product in (catalog.units if catalog is not None else [])}
    with path.open("w", encoding="utf-8") as handle:
        for product_id, (text, digest, _name) in desired.items():
            product = units.get(product_id)
            if product_id not in reasons:
                action = "unchanged"
            elif product_id in previews:
                action = "embedded"
            else:
                action = "pending"  # dry-run hoặc lượt dừng giữa chừng: chưa ghi vector mới
            row = {"productId": product_id, "action": action, "reason": reasons.get(product_id),
                   "name": getattr(product, "name", None), "taxonomy": getattr(product, "taxonomy", None),
                   "destination": getattr(product, "destination", None), "textHash": digest,
                   "chars": len(text), "words": len(text.split()), "text": text}
            if product_id in previews:
                row["vector"] = previews[product_id]
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        for product_id in orphans:
            handle.write(json.dumps({"productId": product_id, "action": "deleted" if orphans_deleted else "orphan"},
                                    ensure_ascii=False) + "\n")


#: Số search unit mỗi lô ghi Weaviate: lô xong là ghi ngay, lỗi giữa chừng vẫn giữ phần đã ghi.
WRITE_BATCH = 96


def embed_batches(embedder, batches: list[list[str]], texts: dict[str, str], write) -> None:
    """Embed tuần tự từng lô (torch đã tự dùng nhiều luồng CPU trong mỗi lô) rồi ghi ngay. Lỗi ở một lô: phần đã ghi được
    giữ, chạy lại job chỉ nhúng phần còn thiếu."""
    for ids in batches:
        write(ids, embedder.embed_docs([texts[pid] for pid in ids]))


def run(*, dry_run: bool = False, backfill_lexical: bool = False, force: bool = False, settings=None,
        detail_path: Path | str | None = None, lexical_only: bool = False) -> dict[str, int | str | bool]:
    """`detail_path`: nếu có, ghi chi tiết từng sản phẩm (xem `write_detail`) kể cả khi job lỗi giữa chừng.
    `force`: nhúng lại mọi search unit dù text không đổi (chỉ để đo tốc độ).
    `lexical_only`: chỉ PATCH property BM25 còn thiếu; **từ chối** (không ghi gì, `report["refused"]`) khi catalog lệch
    index — có unit phải embed hoặc object mồ côi phải xoá — để một `DATABASE_URL` trỏ nhầm không xoá vector production."""
    started = time.monotonic()
    backfill_lexical = backfill_lexical or lexical_only
    settings = settings or get_settings()
    catalog = PostgresCatalogReader(settings.database_url).load()
    version = model_version(settings.embed_model)
    client = WeaviateClient(
        settings.weaviate_url,
        collection=settings.weaviate_collection,
        vector_index_type=settings.weaviate_vector_index_type,
        api_key=settings.weaviate_api_key,
        timeout_seconds=settings.weaviate_timeout_seconds,
        bm25_k1=settings.search_bm25_k1,
        bm25_b=settings.search_bm25_b,
    )
    desired: dict[str, tuple[str, str, str]] = {}
    reasons: dict[str, str] = {}
    previews: dict[str, dict] = {}
    orphans: list[str] = []
    orphans_deleted = False
    try:
        client.ready()
        client.ensure_collection()
        existing, _ = client.fetch(include_vectors=False)
        desired = {
            product.product_id: (text, text_hash(text), product.name)
            for product, text in zip(catalog.units, catalog.texts, strict=True)
        }
        for product_id, (_, digest, _name) in desired.items():
            old = existing.get(product_id)
            if old is None:
                reasons[product_id] = "new"
            elif old.text_hash != digest:
                reasons[product_id] = "text"
            elif old.model_version != version:
                reasons[product_id] = "model"
            elif old.uuid != client.object_uuid(product_id):
                reasons[product_id] = "uuid"
            elif force:
                reasons[product_id] = "force"
        changed = [product_id for product_id in desired if product_id in reasons]
        others = foreign_models(existing, settings.embed_model)
        if others:
            return {"modelVersion": version, "searchUnits": len(desired), "embedded": 0,
                    "refused": (f"collection {settings.weaviate_collection} đang chứa vector của {', '.join(others)}; "
                                f"không ghi vector {settings.embed_model} vào đó. Đặt WEAVIATE_COLLECTION sang collection riêng "
                                "(mặc định ProductE5Small).")}
        orphans = sorted(set(existing) - set(desired))
        # Object index trước 25/09 chưa có property BM25: ghi thêm bằng PATCH, không embed (chỉ khi được yêu cầu).
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
        if lexical_only:
            report["lexicalOnly"] = True
            if changed or orphans:
                report["refused"] = (f"--lexical-only: index lệch catalog (embedded {len(changed)}, deletedOrphans {len(orphans)}) "
                                     "— không ghi gì. Kiểm DATABASE_URL; muốn re-index thì chạy job đầy đủ có chủ đích.")
                return report
            if not dry_run:
                _patch_lexical(client, existing, desired, stale_lexical)
            return report
        if dry_run or (not changed and not orphans and not (backfill_lexical and stale_lexical)):
            return report

        embedder = build_embedder(settings)
        written = 0

        def write(ids: list[str], vectors) -> None:
            # Mỗi lô ghi ngay khi nhúng xong, nên lỗi giữa chừng vẫn giữ phần đã xong;
            # chạy lại job chỉ nhúng phần còn thiếu.
            nonlocal written
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
            if detail_path is not None:
                previews.update({product_id: vector_preview(vector) for product_id, vector in zip(ids, vectors)})
            written += len(ids)
            print(f"indexed {written}/{len(changed)}", flush=True)

        step = WRITE_BATCH
        batches = [changed[start : start + step] for start in range(0, len(changed), step)]
        try:
            embed_batches(embedder, batches, {pid: desired[pid][0] for pid in changed}, write)
        finally:
            embedder.close()
            report.update(seconds=round(time.monotonic() - started, 1))

        if backfill_lexical:
            _patch_lexical(client, existing, desired, stale_lexical)

        client.delete([existing[product_id].uuid for product_id in orphans])
        orphans_deleted = True
        return report
    finally:
        client.close()
        if detail_path is not None:
            write_detail(Path(detail_path), catalog, desired, reasons, previews, orphans, orphans_deleted)


def _patch_lexical(client, existing: dict, desired: dict, stale_lexical: list[str]) -> None:
    """Ghi property BM25 cho object đã index mà còn thiếu — giữ nguyên vector, không embed."""
    for done, product_id in enumerate(stale_lexical, 1):
        text, _digest, name = desired[product_id]
        client.patch_properties(existing[product_id].uuid, lexical_properties(name, text))
        if done % 200 == 0 or done == len(stale_lexical):
            print(f"backfilled lexical {done}/{len(stale_lexical)}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="chỉ đếm phần cần cập nhật, không embed hoặc ghi Weaviate")
    parser.add_argument("--backfill-lexical", action="store_true",
                        help="ghi property BM25 (nameAscii/searchTextAscii) cho object đã index mà còn thiếu; không embed")
    parser.add_argument("--force", action="store_true",
                        help="nhúng lại mọi search unit dù text không đổi (đo tốc độ; chỉ để đo)")
    parser.add_argument("--lexical-only", action="store_true",
                        help="chỉ PATCH property BM25 còn thiếu; từ chối (mã thoát 2) khi catalog lệch index — không embed, không xoá")
    args = parser.parse_args(argv)
    report = run(dry_run=args.dry_run, backfill_lexical=args.backfill_lexical, force=args.force, lexical_only=args.lexical_only)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report.get("refused") else 0


if __name__ == "__main__":
    raise SystemExit(main())
