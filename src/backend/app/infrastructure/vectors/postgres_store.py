"""VectorStorePort đọc catalog từ PostgreSQL đã seed, thay cho bản giả `tests/fakes/in_memory_vector_store.py` đọc file.

Bản giả đọc `products.jsonl`; bản này đọc thẳng `cdp.products` JOIN `catalog.product_meta`
nên recsys chạy trên đúng dữ liệu mà `data_collection.seed` đã nạp, không cần file trung gian.

Hai điểm bám theo quy tắc repo:

* **Connection là `DATABASE_URL` (role `vota_app`), không phải `CDP_DATABASE_URL`.** `vota_app` được
  GRANT SELECT trên `cdp.products` đúng để dựng `catalog.*` từ nó (AGENTS.md §6.1, `db/init/01_vota.sql`).
  Event và profile thì `vota_app` không đọc được — phần đó đi qua `PostgresCdpReader`.
* **`is_search_unit` / `is_recommendable` lấy từ view `catalog.product_meta`, không tính lại trong Python.**
  PRODUCT_SCHEMA §4: view là nơi **duy nhất** định nghĩa vai trò sản phẩm; thêm ngoại lệ sau này chỉ sửa
  view là mọi nơi cùng đổi. (`InMemoryVectorStore` tự suy vì file JSONL không có view.)

Vector vẫn embed tại chỗ rồi cache ra .npy: `catalog.product_vectors` cố ý để trống ở tuần 1
(job `embed_products` của Search là việc tuần 2 — MOCK_DATA_SPEC §1).
"""
from __future__ import annotations

import hashlib
import logging
import os
from collections import defaultdict

import numpy as np

from src.backend.app.application.ports import EmbedderPort, UnitIndex
from src.backend.app.domain.catalog import Product, build_text

#: Đọc nguyên 13 trường CDP + ba cờ vai trò của view. `attributes` là JSONB nên psycopg trả dict sẵn.
_QUERY = """
SELECT p.product_id, p.name, p.taxonomy, p.destination, p.description, p.attributes,
       p.unit_price, p.currency, p.available, p.available_from, p.available_to, p.image_url,
       m.is_search_unit, m.is_recommendable, m.parent_product_id
FROM   cdp.products p
JOIN   catalog.product_meta m USING (product_id)
"""

logger = logging.getLogger("uvicorn.error")


class PostgresVectorStore:
    """Dựng `UnitIndex` từ database. Cùng interface với `InMemoryVectorStore` nên đổi qua lại được."""

    def __init__(self, database_url: str, embedder: EmbedderPort, cache_dir: str = ".embcache"):
        self.database_url, self.embedder, self.cache_dir = database_url, embedder, cache_dir

    def _rows(self) -> list[dict]:
        return read_catalog_rows(self.database_url)

    def load(self) -> UnitIndex:
        logger.info("startup.recsys.catalog.query.start")
        rows = self._rows()
        logger.info("startup.recsys.catalog.query.ready products=%d", len(rows))
        if not rows:
            raise RuntimeError(
                "cdp.products rỗng — chạy `make demo-db` (hoặc python -m data_collection.seed) trước khi mở backend."
            )

        units, texts, meta, parent_of = search_units(rows)

        os.makedirs(self.cache_dir, exist_ok=True)
        key = hashlib.md5((self.embedder.name + "\n".join(texts)).encode("utf-8")).hexdigest()[:12]
        path = os.path.join(self.cache_dir, f"units_{key}.npy")
        if os.path.exists(path):
            logger.info(
                "startup.recsys.embedding_cache.hit path=%s search_units=%d",
                path,
                len(texts),
            )
            embeddings = np.load(path)
        else:
            logger.info(
                "startup.recsys.embedding.compute.start model=%s search_units=%d",
                self.embedder.name,
                len(texts),
            )
            embeddings = self.embedder.embed_docs(texts)
            np.save(path, embeddings)
            logger.info("startup.recsys.embedding.compute.ready cache=%s", path)

        return UnitIndex(
            units=units,
            E=embeddings,
            taxonomy=np.array([p.taxonomy for p in units]),
            destination=np.array([p.destination for p in units]),
            available=np.array([p.available for p in units]),
            recommendable=np.array([bool(meta[p.product_id]["is_recommendable"]) for p in units]),
            parent_of=parent_of,
            model_version=f"{self.embedder.name}@{key}",
        )


def read_catalog_rows(database_url: str) -> list[dict]:
    """13 trường CDP + cờ vai trò của `catalog.product_meta`, qua `DATABASE_URL` (role vota_app)."""
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(_QUERY)
            return cur.fetchall()


def search_units(rows: list[dict]) -> tuple[list[Product], list[str], dict[str, dict], dict[str, str]]:
    """Search unit (sắp theo product_id) + text để embed. Dùng chung cho recsys và job embed_products."""
    products: dict[str, Product] = {}
    meta: dict[str, dict] = {}
    for row in rows:
        product = Product.from_cdp(
            {
                "productId": str(row["product_id"]),
                "name": row["name"],
                "taxonomy": row["taxonomy"],
                "destination": row["destination"],
                "description": row["description"],
                "attributes": row["attributes"] or {},
                # numeric(14,2) về Python là Decimal; ép float cho khớp Product và JSON response.
                "unitPrice": float(row["unit_price"]) if row["unit_price"] is not None else None,
                "currency": row["currency"],
                "available": row["available"],
                "availableFrom": row["available_from"],
                "availableTo": row["available_to"],
                "imageUrl": row["image_url"],
            }
        )
        products[product.product_id] = product
        meta[product.product_id] = row

    parent_of: dict[str, str] = {}
    children: dict[str, list[Product]] = defaultdict(list)
    for product_id, row in meta.items():
        parent = row["parent_product_id"]
        if parent:
            parent_of[product_id] = str(parent)
            children[str(parent)].append(products[product_id])

    units = [p for p in products.values() if meta[p.product_id]["is_search_unit"]]
    units.sort(key=lambda p: p.product_id)  # thứ tự cố định → cache key ổn định giữa các lần chạy
    texts = [build_text(p, children.get(p.product_id, [])) for p in units]
    return units, texts, meta, parent_of
