"""Nạp vector `.npy` đã embed sẵn (bộ vector của gói bàn giao 08/10) vào một collection Weaviate MỚI, đúng định dạng object
của `src/backend/jobs/embed_products.py` — để chạy backend local trên bản sao production mà không cài torch và không re-embed
(vector y hệt bộ đã đo offline, nên parity offline == HTTP đạt 60/60). Plan lane A1, `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md`.

Chạy từ gốc repo, env DATABASE_URL (catalog), WEAVIATE_URL, VECTOR_COLLECTION (bắt buộc bắt đầu bằng `ProductE5SmallProdcopy`
để không ghi nhầm vào collection của search bench hay production):

    python -m src.evaluation.recsys_bench.theme_study.load_npy_weaviate <prefix>      # <prefix>.npy + .ids.json + .meta.json

Kiểm sau khi nạp: `python -m src.backend.jobs.embed_products --dry-run` phải báo embedded 0 / unchanged = số search unit.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np

from src.backend.app.infrastructure.vectors.postgres_store import PostgresCatalogReader
from src.backend.app.infrastructure.vectors.weaviate_store import WeaviateClient, lexical_properties


def main(prefix: str) -> int:
    collection = os.environ["VECTOR_COLLECTION"]
    if not collection.startswith("ProductE5SmallProdcopy"):
        raise SystemExit("VECTOR_COLLECTION phải bắt đầu bằng ProductE5SmallProdcopy (collection riêng cho bản sao)")
    meta = json.load(open(prefix + ".meta.json", encoding="utf-8"))
    version = f"{meta['cache_model']}:{meta['text_builder_version']}"
    E = np.load(prefix + ".npy")
    ids = json.load(open(prefix + ".ids.json", encoding="utf-8"))
    pos = {pid: i for i, pid in enumerate(ids)}
    catalog = PostgresCatalogReader(os.environ["DATABASE_URL"]).load()
    objs, missing = [], []
    for product, text in zip(catalog.units, catalog.texts, strict=True):
        i = pos.get(product.product_id)
        if i is None:
            missing.append(product.product_id)
            continue
        objs.append({
            "class": collection, "id": WeaviateClient.object_uuid(product.product_id),
            "properties": {"productId": product.product_id, "modelVersion": version,
                           "textHash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                           **lexical_properties(product.name, text)},
            "vector": E[i].astype(float).tolist(),
        })
    if missing:
        raise SystemExit(f"{len(missing)} search unit không có vector trong {prefix}.npy, vd {missing[:3]}")
    client = WeaviateClient(os.environ["WEAVIATE_URL"], collection=collection, api_key=os.environ.get("WEAVIATE_API_KEY", ""))
    client.ready()
    client.ensure_collection()
    client.insert(objs, batch_size=200)
    print(json.dumps({"collection": collection, "modelVersion": version, "inserted": len(objs), "dim": int(E.shape[1])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
