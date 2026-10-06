"""Incrementally index PostgreSQL catalog search units into Weaviate.

Run from repository root:
    python -m src.backend.jobs.embed_products [--dry-run]

Embedder theo `EMBED_PROVIDER` (FR-SRC-02): `local` (mặc định) chạy `intfloat/multilingual-e5-small` trên CPU của máy chạy
job, tiền tố `passage: ` do adapter ghép; `cohere` là đường lui. Ghi vào `WEAVIATE_COLLECTION` (mặc định `ProductE5` cho
local, `Product` cho Cohere). Job **từ chối** ghi (không embed, không xoá, mã thoát 2) khi collection đang giữ vector khác số
chiều `EMBED_DIMENSION`, hoặc vector của một model embedding khác — trừ khi có `--allow-model-change` (cùng số chiều, thay
dần vector cũ bằng vector model mới). Đổi model thì dựng collection mới song song, không ghi đè collection đang phục vụ.

CẢNH BÁO: job xoá mọi object không có trong catalog của `DATABASE_URL` đang trỏ. Đừng chạy với `.env` trỏ Weaviate Cloud
từ máy dev.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import numpy as np

from src.backend.app.core.config import get_settings
from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION
from src.backend.app.infrastructure.embeddings.cohere_embedder import CallLimiter, CohereEmbedder
from src.backend.app.infrastructure.embeddings.local_e5_embedder import LocalE5Embedder
from src.backend.app.infrastructure.vectors.postgres_store import PostgresCatalogReader
from src.backend.app.infrastructure.vectors.weaviate_store import WeaviateClient, lexical_properties


def model_version(model_name: str) -> str:
    """`<EMBED_MODEL>:<TEXT_BUILDER_VERSION>` — cùng công thức với `infrastructure/embeddings/factory.model_version`."""
    return f"{model_name}:{TEXT_BUILDER_VERSION}"


def embedding_model(version: str) -> str:
    """Phần model của `modelVersion`: đổi text builder thì embed lại bình thường, đổi model thì là không gian vector khác."""
    return version.rsplit(":", 1)[0] if ":" in version else version


#: Số text mỗi lần ghi Weaviate (và mỗi lần gọi Cohere). Model local tự chia nhỏ theo `EMBED_BATCH_SIZE` bên trong.
WRITE_BATCH = 96


def make_embedder(settings, limiter: CallLimiter):
    if settings.embed_provider == "local":
        return LocalE5Embedder(
            settings.embed_model,
            revision=settings.embed_model_revision,
            dimension=settings.embed_dimension,
            threads=settings.embed_threads,
            batch_size=settings.embed_batch_size,
            max_length=settings.embed_max_length,
            cache_dir=settings.embed_cache_dir or None,
        )
    return CohereEmbedder(
        settings.cohere_api_key,
        settings.embed_model,
        base_url=settings.cohere_base_url,
        dimension=settings.embed_dimension,
        timeout_seconds=settings.cohere_timeout_seconds,
        limiter=limiter,
    )


def collection_guard(existing: dict, version: str, stored_dimension: int | None, dimension: int,
                     allow_model_change: bool) -> str | None:
    """Lý do từ chối ghi (None = được ghi). Lệch số chiều: luôn từ chối — Weaviate không nhận vector khác chiều trong một
    collection, và trộn hai không gian vector làm cosine vô nghĩa. Model khác cùng chiều: từ chối trừ khi `allow_model_change`."""
    if stored_dimension is not None and stored_dimension != dimension:
        return (f"collection đang giữ vector {stored_dimension} chiều, EMBED_DIMENSION={dimension} — không ghi. "
                "Đổi model thì dùng collection mới (WEAVIATE_COLLECTION), không ghi đè collection đang phục vụ.")
    target = embedding_model(version)
    foreign = sorted({embedding_model(meta.model_version) for meta in existing.values()
                      if meta.model_version and embedding_model(meta.model_version) != target})
    if foreign and not allow_model_change:
        return (f"collection đang giữ vector của model khác {foreign} (job ghi {target}) — không ghi. Dùng collection mới, "
                "hoặc chạy lại với --allow-model-change nếu chủ đích thay toàn bộ vector trong collection này.")
    return None


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


PREVIEW_DIMS = 8


def vector_preview(vector) -> dict:
    values = np.asarray(vector, dtype=np.float64)
    return {"dims": int(values.size), "norm": round(float(np.linalg.norm(values)), 6),
            "head": [round(float(v), 6) for v in values[:PREVIEW_DIMS]]}


def write_detail(path: Path, catalog, desired: dict, reasons: dict, previews: dict, orphans: list,
                 orphans_deleted: bool) -> None:
    """Một dòng JSON mỗi search unit (text đưa vào embedder, hash, hành động, vài chiều đầu của vector) và mỗi vector mồ côi.

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


def embed_batches(embedder, batches: list[list[str]], texts: dict[str, str], concurrency: int, write) -> None:
    """Embed từng lô, tối đa `concurrency` lô cùng lúc (P5.2, docs/plan/2026-09-29-index-cohere-song-song.md; model local: 1).

    `write(ids, vectors)` luôn chạy ở luồng gọi hàm này (chỉ một luồng ghi Weaviate), theo thứ tự lô xong trước. Một lô lỗi
    hẳn: không gửi lô mới, chờ và ghi các lô đang chạy, rồi ném lại lỗi đầu tiên — phần đã ghi được giữ, chạy lại chỉ
    nhúng phần còn thiếu (như khi tuần tự)."""
    if concurrency <= 1:
        for ids in batches:
            write(ids, embedder.embed_docs([texts[pid] for pid in ids]))
        return
    queue = iter(batches)
    failure: BaseException | None = None
    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="embed") as pool:
        pending = {}

        def submit_next() -> None:
            ids = next(queue, None)
            if ids is not None:
                pending[pool.submit(embedder.embed_docs, [texts[pid] for pid in ids])] = ids
        for _ in range(concurrency):
            submit_next()
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                ids = pending.pop(future)
                try:
                    vectors = future.result()
                except BaseException as exc:  # giữ lỗi đầu tiên, vẫn ghi các lô đang chạy khác
                    failure = failure or exc
                    continue
                write(ids, vectors)
                if failure is None:
                    submit_next()
    if failure is not None:
        raise failure


def run(*, dry_run: bool = False, backfill_lexical: bool = False, force: bool = False, settings=None,
        detail_path: Path | str | None = None, lexical_only: bool = False,
        allow_model_change: bool = False) -> dict[str, int | str | bool]:
    """`detail_path`: nếu có, ghi chi tiết từng sản phẩm (xem `write_detail`) kể cả khi job lỗi giữa chừng.
    `force`: nhúng lại mọi search unit dù text không đổi (chỉ để đo tốc độ; với Cohere tốn quota).
    `allow_model_change`: cho ghi vector model hiện tại vào collection đang giữ vector model khác CÙNG số chiều
    (`collection_guard`); lệch số chiều thì luôn từ chối.
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
        embed_model=settings.embed_model,
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
        orphans = sorted(set(existing) - set(desired))
        # Object index trước 25/09 chưa có property BM25: ghi thêm bằng PATCH, không embed lại (chỉ khi được yêu cầu).
        stale_lexical = [
            product_id for product_id in desired
            if product_id in existing and product_id not in set(changed) and not existing[product_id].lexical
        ]
        report: dict[str, int | str] = {
            "provider": settings.embed_provider,
            "collection": settings.weaviate_collection,
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
        refused = collection_guard(existing, version, client.vector_dimension() if existing else None,
                                   settings.embed_dimension, allow_model_change)
        if refused:
            report["refused"] = refused
            return report
        if dry_run or (not changed and not orphans and not (backfill_lexical and stale_lexical)):
            return report

        # Cohere: mọi luồng của job dùng chung một limiter (trần lượt gọi mỗi phút, 429 làm mọi luồng cùng chờ).
        # Model local: một luồng — torch đã dùng các lõi (EMBED_THREADS), chạy song song chỉ tranh CPU.
        limiter = CallLimiter(settings.cohere_calls_per_minute)
        local = settings.embed_provider == "local"
        concurrency = 1 if local else settings.cohere_embed_concurrency
        embedder = make_embedder(settings, limiter)
        written = 0

        def write(ids: list[str], vectors) -> None:
            # Mỗi lô ghi ngay khi nhúng xong, nên lỗi giữa chừng (vd. 429 kéo dài) vẫn giữ phần đã xong;
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
            embed_batches(embedder, batches, {pid: desired[pid][0] for pid in changed}, concurrency, write)
        finally:
            embedder.close()
            report.update(concurrency=concurrency, seconds=round(time.monotonic() - started, 1))
            if not local:
                report.update(cohereCalls=limiter.calls, rateLimited=limiter.rate_limited)

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
    """Ghi property BM25 cho object đã index mà còn thiếu — giữ nguyên vector, không embed lại."""
    for done, product_id in enumerate(stale_lexical, 1):
        text, _digest, name = desired[product_id]
        client.patch_properties(existing[product_id].uuid, lexical_properties(name, text))
        if done % 200 == 0 or done == len(stale_lexical):
            print(f"backfilled lexical {done}/{len(stale_lexical)}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="chỉ đếm phần cần cập nhật, không embed hoặc ghi Weaviate")
    parser.add_argument("--backfill-lexical", action="store_true",
                        help="ghi property BM25 (nameAscii/searchTextAscii) cho object đã index mà còn thiếu; không embed lại")
    parser.add_argument("--force", action="store_true",
                        help="nhúng lại mọi search unit dù text không đổi (đo tốc độ; với Cohere tốn quota)")
    parser.add_argument("--allow-model-change", action="store_true",
                        help="cho ghi vào collection đang giữ vector của model khác CÙNG số chiều; lệch chiều luôn từ chối")
    parser.add_argument("--lexical-only", action="store_true",
                        help="chỉ PATCH property BM25 còn thiếu; từ chối (mã thoát 2) khi catalog lệch index — không embed, không xoá")
    args = parser.parse_args(argv)
    report = run(dry_run=args.dry_run, backfill_lexical=args.backfill_lexical, force=args.force, lexical_only=args.lexical_only,
                 allow_model_change=args.allow_model_change)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report.get("refused") else 0


if __name__ == "__main__":
    raise SystemExit(main())
