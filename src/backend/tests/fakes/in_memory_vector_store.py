"""`VectorStorePort` giả cho test offline: đọc products.jsonl, dựng text, embed, cache .npy.
Bản chạy thật là `infrastructure/vectors/weaviate_store.py`; cả hai trả `(UnitIndex, VectorSearchPort)`.
Kho vector ở đây là `NumpyVectorSearch` quét toàn bộ ma trận, nên test không cần Weaviate.

Thành phần combo (cờ `includesFlight` / `includesHotel` của `UnitAttributes`): đọc `combo_items.jsonl` cạnh products.jsonl
nếu có (cùng quy ước đầu ra của `parse_combos`, mà `load_products` / `fresh_catalog_db` cũng đọc) hoặc file truyền tường minh;
không có file → không combo nào có cờ. Chỉ dùng cho thuộc tính lọc — text (và cache vector) không đổi."""
from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict

import numpy as np

from src.backend.app.application.ports import EmbedderPort, UnitIndex, VectorSearchPort
from src.backend.app.domain.catalog import Product, UnitAttributes, build_text
from src.backend.app.infrastructure.vectors.numpy_search import NumpyVectorSearch
from src.backend.app.infrastructure.vectors.postgres_store import combo_kinds_of, combo_members_of


def read_combo_items(path: str) -> dict[str, list[dict]]:
    """combo_items.jsonl (mỗi dòng một thành phần: combo_product_id, position, item_kind, item_product_id, confidence, source…)
    → combo id → dòng theo position, cùng dạng `PostgresCatalogReader._combo_items`."""
    rows: dict[str, list[dict]] = defaultdict(list)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                it = json.loads(line)
                if it.get("combo_product_id") and it.get("item_kind"):
                    rows[str(it["combo_product_id"])].append({**it, "position": int(it.get("position") or 0)})
    return {pid: sorted(items, key=lambda it: it["position"]) for pid, items in rows.items()}


def read_combo_kinds(path: str) -> dict[str, list[str]]:
    """combo id → item_kind theo position (giữ cho test cũ)."""
    return combo_kinds_of(read_combo_items(path))


class InMemoryVectorStore:
    def __init__(self, products_path: str, embedder: EmbedderPort, cache_dir: str = ".embcache",
                 combo_items_path: str | None = None):
        self.products_path, self.embedder, self.cache_dir = products_path, embedder, cache_dir
        self.combo_items_path = combo_items_path or os.path.join(os.path.dirname(products_path), "combo_items.jsonl")

    def load(self) -> tuple[UnitIndex, VectorSearchPort]:
        products: dict[str, Product] = {}
        with open(self.products_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    p = Product.from_cdp(json.loads(line))
                    products[p.product_id] = p

        parent_of: dict[str, str] = {}
        children: dict[str, list[Product]] = defaultdict(list)
        for p in products.values():
            if p.parent_id:
                parent_of[p.product_id] = p.parent_id
                children[p.parent_id].append(p)

        units = [p for p in products.values() if p.is_search_unit]
        texts = [build_text(p, children.get(p.product_id, [])) for p in units]

        os.makedirs(self.cache_dir, exist_ok=True)
        key = hashlib.md5((self.embedder.name + "\n".join(texts)).encode()).hexdigest()[:12]
        path = os.path.join(self.cache_dir, f"units_{key}.npy")
        E = np.load(path) if os.path.exists(path) else self.embedder.embed_docs(texts)
        if not os.path.exists(path):
            np.save(path, E)

        combo_items = read_combo_items(self.combo_items_path)
        index = UnitIndex(
            units=units,
            taxonomy=np.array([p.taxonomy for p in units]),
            destination=np.array([p.destination for p in units]),
            available=np.array([p.available for p in units]),
            recommendable=np.array([p.is_bookable or any(c.is_bookable and c.available for c in children.get(p.product_id, [])) for p in units]),
            parent_of=parent_of, model_version=f"{self.embedder.name}@{key}",
            attrs=UnitAttributes.build(units, children, combo_kinds_of(combo_items)),
            combo_members=combo_members_of(combo_items),
        )
        # Văn bản BM25 như job index ghi lên Weaviate: tên (trọng số 2) + text đã dựng.
        return index, NumpyVectorSearch([p.product_id for p in units], E,
                                        texts=[f"{p.name} {p.name} {t}" for p, t in zip(units, texts)])
