"""Part 8a — dịch filter giống pgvector; query vector `::vector`; GUC diskann validate miền; index SQL."""
from __future__ import annotations

import numpy as np
import pytest

from evaluation.vector_bench.config import IndexConfig
from evaluation.vector_bench.engines.base import StoreOptions
from evaluation.vector_bench.engines.pgvector import PgVectorStore
from evaluation.vector_bench.engines.pgvectorscale import PgVectorScaleStore


@pytest.fixture()
def store(cfg):
    return PgVectorScaleStore(cfg.engine("pgvectorscale"), 1024, StoreOptions())


def test_same_filter_translation_as_pgvector(cfg, store):
    f = {"and": [{"eq": ["destination", "Nha Trang"]}, {"all": ["amenity_ids", [3]]}, {"not": {"any": ["amenity_ids", [5]]}},
                 {"geo": {"lat": 12.0, "lon": 109.0, "radius_m": 3000}}, {"range": ["star_rating", {"gte": 4}]}]}
    assert store.translate(f) == PgVectorStore(cfg.engine("pgvector"), 1024).translate(f)


def test_query_uses_vector_cast_and_diskann_gucs(store):
    q = np.ones(1024, dtype=np.float16)
    sql, params, gucs = store.build_query(q, None, 10, {"mode": "ann", "query_search_list_size": 200, "query_rescore": 50})
    assert "::vector" in sql and "::halfvec" not in sql
    assert gucs == [("diskann.query_search_list_size", "200"), ("diskann.query_rescore", "50")]
    with pytest.raises(ValueError):
        store.build_query(q, None, 10, {"mode": "ann", "query_search_list_size": 20000})
    with pytest.raises(ValueError):
        store.build_query(q, None, 10, {"mode": "ann", "query_rescore": -1})


def test_index_sql(store):
    assert store.index_sql({}) == "CREATE INDEX items_diskann ON items USING diskann (embedding vector_cosine_ops)"
    assert store.index_sql({"num_neighbors": 50, "storage_layout": "memory_optimized"}) == (
        "CREATE INDEX items_diskann ON items USING diskann (embedding vector_cosine_ops) "
        "WITH (num_neighbors = 50, storage_layout = 'memory_optimized')")
    with pytest.raises(ValueError):
        store.index_sql({"m": 16})
    assert IndexConfig(name="diskann").params == {}
