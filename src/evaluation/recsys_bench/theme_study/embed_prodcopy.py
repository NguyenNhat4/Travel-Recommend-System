"""Embed mọi search unit của DB local vota_prodcopy (bản sao catalog production) bằng đúng text builder + e5-small
(revision ghim) như job index production; ghi bộ npy theo định dạng recsys_bench.read_npy_vectors."""
import json
import sys
import time

import numpy as np

from src.backend.app.core.config import Settings
from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION
from src.backend.app.infrastructure.embeddings.local_e5_embedder import LocalE5Embedder
from src.backend.app.infrastructure.vectors.postgres_store import PostgresCatalogReader

dsn, prefix = sys.argv[1], sys.argv[2]
source = sys.argv[3] if len(sys.argv) > 3 else "vota_prodcopy"
s = Settings()
t0 = time.time()
cat = PostgresCatalogReader(dsn).load()
ids = [p.product_id for p in cat.units]
print(f"{len(ids)} search unit, đọc {time.time()-t0:.0f}s", flush=True)
emb = LocalE5Embedder(s.embed_model, revision=s.embed_model_revision, dimension=s.embed_dimension, batch_size=64)
E = np.asarray(emb.embed_docs(list(cat.texts)), dtype=np.float32)
E /= np.maximum(np.linalg.norm(E, axis=1, keepdims=True), 1e-12)
np.save(f"{prefix}.npy", E)
json.dump(ids, open(f"{prefix}.ids.json", "w"))
json.dump({"cache_model": s.embed_model, "revision": s.embed_model_revision, "text_builder_version": TEXT_BUILDER_VERSION,
           "dim": int(E.shape[1]), "source": source},
          open(f"{prefix}.meta.json", "w"), ensure_ascii=False)
print(f"xong {E.shape} {time.time()-t0:.0f}s", flush=True)
