"""VectorStorePort in-memory: đọc products.jsonl, dựng text, embed, cache .npy.
Bản pgvector sau này (pgvector_store.py) đọc catalog.product_vectors + catalog.product_meta và trả cùng UnitIndex."""
from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict

import numpy as np

from src.backend.app.application.ports import EmbedderPort, UnitIndex
from src.backend.app.domain.catalog import Product, build_text


class InMemoryVectorStore:
    def __init__(self, products_path: str, embedder: EmbedderPort, cache_dir: str = ".embcache"):
        self.products_path, self.embedder, self.cache_dir = products_path, embedder, cache_dir

    def load(self) -> UnitIndex:
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

        return UnitIndex(
            units=units, E=E,
            taxonomy=np.array([p.taxonomy for p in units]),
            destination=np.array([p.destination for p in units]),
            available=np.array([p.available for p in units]),
            recommendable=np.array([p.is_bookable or any(c.is_bookable and c.available for c in children.get(p.product_id, [])) for p in units]),
            parent_of=parent_of, model_version=f"{self.embedder.name}@{key}",
        )
