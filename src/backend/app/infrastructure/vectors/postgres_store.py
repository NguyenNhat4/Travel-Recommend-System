"""Đọc search unit từ PostgreSQL và dựng chỉ mục vector cục bộ.

Bản giả đọc `products.jsonl`; bản này đọc thẳng `cdp.products` JOIN `catalog.product_meta`
nên recsys chạy trên đúng dữ liệu mà `data_collection.seed` đã nạp, không cần file trung gian.

Hai điểm bám theo quy tắc repo:

* **Connection là `DATABASE_URL` (role `vota_app`), không phải `CDP_DATABASE_URL`.** `vota_app` được
  GRANT SELECT trên `cdp.products` đúng để dựng `catalog.*` từ nó (AGENTS.md §6.1, `db/init/01_vota.sql`).
  Event và profile thì `vota_app` không đọc được — phần đó đi qua `PostgresCdpReader`.
* **`is_search_unit` / `is_recommendable` lấy từ view `catalog.product_meta`, không tính lại trong Python.**
  PRODUCT_SCHEMA §4: view là nơi **duy nhất** định nghĩa vai trò sản phẩm; thêm ngoại lệ sau này chỉ sửa
  view là mọi nơi cùng đổi. (`InMemoryVectorStore` tự suy vì file JSONL không có view.)

`PostgresCatalogReader` là phần dùng chung cho job index Weaviate và adapter runtime. `PostgresVectorStore`
được giữ làm fallback/test offline (quét vector trong RAM qua `NumpyVectorSearch`); composition root mặc
định dùng embedder theo `EMBED_PROVIDER` (e5-small local, FR-SRC-02) + Weaviate theo PRD. Cache `.npy` khoá theo tên model +
text nên đổi model không đọc nhầm vector cũ; số chiều kiểm lúc nạp.
"""
from __future__ import annotations

import hashlib
import logging
import os
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from src.backend.app.application.ports import EmbedderPort, UnitIndex, VectorSearchPort
from src.backend.app.domain.catalog import Product, UnitAttributes, build_text
from src.backend.app.infrastructure.vectors.numpy_search import NumpyVectorSearch

#: Đọc nguyên 13 trường CDP + ba cờ vai trò của view. `attributes` là JSONB nên psycopg trả dict sẵn.
_QUERY = """
SELECT p.product_id, p.name, p.taxonomy, p.destination, p.description, p.attributes,
       p.unit_price, p.currency, p.available, p.available_from, p.available_to, p.image_url,
       m.is_search_unit, m.is_recommendable, m.parent_product_id
FROM   cdp.products p
JOIN   catalog.product_meta m USING (product_id)
"""

logger = logging.getLogger("uvicorn.error")

#: Thành phần combo: thứ tự + nhãn cho ô ROLLUP của text builder ("Gồm: vé VinWonders; buffet…"), `item_kind` cho cờ
#: `includesFlight` / `includesHotel` của `UnitAttributes` (cột có sẵn trong DDL; text builder không đọc nó → text không đổi).
_COMBO_QUERY = """
SELECT combo_product_id, position, label, item_kind
FROM   catalog.combo_items
ORDER  BY combo_product_id, position
"""


def combo_kinds_of(combo_items: dict[str, list[dict]]) -> dict[str, list[str]]:
    """combo product_id → `item_kind` các thành phần (theo position) — đầu vào cờ combo của `UnitAttributes.build`."""
    return {pid: [str(it["item_kind"]) for it in items if it.get("item_kind")] for pid, items in combo_items.items()}


@dataclass
class CatalogUnits:
    """Ảnh chụp catalog chưa gắn vector, dùng chung cho index job và runtime adapter."""

    units: list[Product]
    texts: list[str]
    taxonomy: np.ndarray
    destination: np.ndarray
    available: np.ndarray
    recommendable: np.ndarray
    parent_of: dict[str, str]
    attrs: UnitAttributes | None = None   # thuộc tính lọc Phase A, dựng kèm phòng/chuyến con

    def to_index(self, model_version: str) -> UnitIndex:
        return UnitIndex(
            units=self.units,
            taxonomy=self.taxonomy,
            destination=self.destination,
            available=self.available,
            recommendable=self.recommendable,
            parent_of=self.parent_of,
            model_version=model_version,
            attrs=self.attrs,
        )


class PostgresCatalogReader:
    """Đọc đúng catalog search unit qua role `vota_app`; không sinh hoặc lưu vector."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    def _rows(self) -> list[dict]:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute(_QUERY)
                return cur.fetchall()

    def _combo_items(self) -> dict[str, list[dict]]:
        import psycopg
        from psycopg.rows import dict_row

        items: dict[str, list[dict]] = defaultdict(list)
        with psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute(_COMBO_QUERY)
                for row in cur.fetchall():
                    items[str(row["combo_product_id"])].append(row)
        return items

    def load(self) -> CatalogUnits:
        logger.info("startup.recsys.catalog.query.start")
        rows = self._rows()
        logger.info("startup.recsys.catalog.query.ready products=%d", len(rows))
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
        combo_items = self._combo_items()
        texts = [
            build_text(
                p,
                children.get(p.product_id, []),
                combo_items=combo_items.get(p.product_id, []),
            )
            for p in units
        ]

        return CatalogUnits(
            units=units,
            texts=texts,
            taxonomy=np.array([p.taxonomy for p in units]),
            destination=np.array([p.destination for p in units]),
            available=np.array([p.available for p in units]),
            recommendable=np.array([bool(meta[p.product_id]["is_recommendable"]) for p in units]),
            parent_of=parent_of,
            attrs=UnitAttributes.build(units, children, combo_kinds_of(combo_items)),
        )


class PostgresVectorStore:
    """Fallback offline: embed catalog tại chỗ và cache `.npy`; production dùng Weaviate."""

    def __init__(self, database_url: str, embedder: EmbedderPort, cache_dir: str = ".embcache"):
        self.reader = PostgresCatalogReader(database_url)
        self.embedder, self.cache_dir = embedder, cache_dir

    def load(self) -> tuple[UnitIndex, VectorSearchPort]:
        catalog = self.reader.load()
        os.makedirs(self.cache_dir, exist_ok=True)
        key = hashlib.md5((self.embedder.name + "\n".join(catalog.texts)).encode("utf-8")).hexdigest()[:12]
        path = os.path.join(self.cache_dir, f"units_{key}.npy")
        if os.path.exists(path):
            logger.info(
                "startup.recsys.embedding_cache.hit path=%s search_units=%d",
                path,
                len(catalog.texts),
            )
            embeddings = np.load(path)
        else:
            logger.info(
                "startup.recsys.embedding.compute.start model=%s search_units=%d",
                self.embedder.name,
                len(catalog.texts),
            )
            embeddings = self.embedder.embed_docs(catalog.texts)
            np.save(path, embeddings)
            logger.info("startup.recsys.embedding.compute.ready cache=%s", path)

        dimension = getattr(self.embedder, "dimension", None)
        if embeddings.shape[0] != len(catalog.texts) or (dimension is not None and embeddings.shape[1] != dimension):
            raise RuntimeError(f"vector {embeddings.shape} lệch catalog ({len(catalog.texts)} unit, {dimension} chiều) — xoá {path}")
        index = catalog.to_index(f"{self.embedder.name}@{key}")
        return index, NumpyVectorSearch([p.product_id for p in catalog.units], embeddings)
