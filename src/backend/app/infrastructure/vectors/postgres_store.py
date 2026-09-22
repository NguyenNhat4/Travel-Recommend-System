"""VectorStorePort đọc catalog từ PostgreSQL đã seed, thay cho `InMemoryVectorStore` đọc file.

`in_memory_store.py` đọc `products.jsonl`; bản này đọc thẳng `cdp.products` JOIN `catalog.product_meta`
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


class PostgresVectorStore:
    """Dựng `UnitIndex` từ database. Cùng interface với `InMemoryVectorStore` nên đổi qua lại được."""

    def __init__(self, database_url: str, embedder: EmbedderPort, cache_dir: str = ".embcache"):
        self.database_url, self.embedder, self.cache_dir = database_url, embedder, cache_dir

    def _rows(self) -> list[dict]:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(_QUERY)
                return cur.fetchall()

    def load(self) -> UnitIndex:
        rows = self._rows()
        if not rows:
            raise RuntimeError(
                "cdp.products rỗng — chạy `make demo-db` (hoặc python -m data_collection.seed) trước khi mở backend."
            )

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

        os.makedirs(self.cache_dir, exist_ok=True)
        key = hashlib.md5((self.embedder.name + "\n".join(texts)).encode("utf-8")).hexdigest()[:12]
        path = os.path.join(self.cache_dir, f"units_{key}.npy")
        if os.path.exists(path):
            embeddings = np.load(path)
        else:
            embeddings = self.embedder.embed_docs(texts)
            np.save(path, embeddings)

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
