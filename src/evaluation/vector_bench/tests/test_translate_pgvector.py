"""Part 5 — dịch AST → SQL pgvector (so chuỗi mẫu), không cần engine."""
from __future__ import annotations

import numpy as np
import pytest

from evaluation.vector_bench.engines.base import StoreOptions
from evaluation.vector_bench.engines.pgvector import PgVectorStore
from evaluation.vector_bench.filters import InvalidFilter


@pytest.fixture()
def store(cfg):
    return PgVectorStore(cfg.engine("pgvector"), 1024, StoreOptions())


def test_none(store):
    assert store.translate(None) == ("TRUE", [])


def test_eq_in_range(store):
    sql, p = store.translate({"and": [{"eq": ["destination", "Nha Trang"]}, {"in": ["taxonomy", ["hotel", "combo"]]},
                                      {"range": ["unit_price", {"gte": 100, "lte": 500}]}, {"eq": ["available", True]}]})
    assert sql == "(destination = %s AND taxonomy = ANY(%s) AND (unit_price >= %s AND unit_price <= %s) AND available = %s)"
    assert p == ["Nha Trang", ["hotel", "combo"], 100.0, 500.0, True]


def test_amenity_not_or(store):
    sql, p = store.translate({"or": [{"all": ["amenity_ids", [3, 17]]}, {"not": {"any": ["amenity_ids", [5]]}}]})
    assert sql == "(amenity_ids @> %s::smallint[] OR NOT (amenity_ids && %s::smallint[]))"
    assert p == [[3, 17], [5]]


def test_geo_bbox_and_haversine(store):
    sql, p = store.translate({"geo": {"lat": 10.0, "lon": 106.0, "radius_m": 1113.2}})
    assert sql == "(point(lon, lat) <@ box(point(%s, %s), point(%s, %s)) AND haversine_m(lat, lon, %s, %s) <= %s)"
    dlat = 1113.2 / 111_320.0
    dlon = 1113.2 / (111_320.0 * np.cos(np.radians(10.0)))
    assert p[:4] == pytest.approx([106.0 - dlon, 10.0 - dlat, 106.0 + dlon, 10.0 + dlat])
    assert p[4:] == [10.0, 106.0, 1113.2]


def test_id_in(store):
    assert store.translate({"id_in": ["a", "b"]}) == ("id = ANY(%s::uuid[])", [["a", "b"]])


def test_invalid_rejected(store):
    with pytest.raises(InvalidFilter):
        store.translate({"not": {"range": ["unit_price", {"lte": 1}]}})


def test_query_shapes(store):
    q = np.ones(1024, dtype=np.float16)
    sql, params, gucs = store.build_query(q, None, 10, {"mode": "exact"})
    assert sql.startswith("WITH f AS MATERIALIZED (SELECT id, embedding FROM items WHERE TRUE)")
    assert gucs == [] and params[-1] == 10
    sql, params, gucs = store.build_query(q, {"eq": ["destination", "X"]}, 10,
                                          {"mode": "ann", "ef_search": 100, "iterative_scan": "relaxed_order", "max_scan_tuples": 20000})
    assert "ORDER BY embedding <=> %s::halfvec LIMIT %s) SELECT id, 1 - d AS score FROM r ORDER BY d" in sql
    assert gucs == [("hnsw.ef_search", "100"), ("hnsw.iterative_scan", "relaxed_order"), ("hnsw.max_scan_tuples", "20000")]
    assert params[1] == "X"
    with pytest.raises(ValueError):
        store.build_query(q, None, 10, {"mode": "ann", "ef_search": 5000})
    with pytest.raises(ValueError):
        store.build_query(q, None, 10, {"mode": "ann", "iterative_scan": "bogus"})


def test_auto_routes_by_estimate(store):
    store.import_state({"auto_stats": {"n": 1000, "cells": [["A", "hotel", True, 900], ["B", "hotel", True, 100]],
                                       "variant": {"hotel_property": 1000}, "amenity": {"3": 50}, "price_quantiles": [1.0, 2.0],
                                       "price_nonnull": 1000, "star": {"4.0": 500}, "geo_sample": [[0.0, 0.0]]}})
    q = np.ones(1024, dtype=np.float16)
    qp = {"mode": "auto", "auto_exact_max": 200, "ef_search": 40, "iterative_scan": "relaxed_order"}
    assert store.routed_mode({"eq": ["destination", "B"]}, qp) == "exact"          # ước 100 ≤ 200
    assert store.routed_mode({"eq": ["destination", "A"]}, qp) == "ann"            # ước 900
    assert store.routed_mode({"and": [{"eq": ["destination", "A"]}, {"all": ["amenity_ids", [3]]}]}, qp) == "exact"  # 900·0,05
    sql, _, gucs = store.build_query(q, {"eq": ["destination", "B"]}, 10, qp)
    # auto → exact giữ GUC của cấu hình (không RESET/SET qua lại mỗi lần đổi nhánh)
    assert "count(*) OVER ()" in sql and gucs == [("hnsw.ef_search", "40"), ("hnsw.iterative_scan", "relaxed_order")]


def test_session_guc_cache_resets_on_close(store):
    store._session_gucs = {"hnsw.ef_search": "100"}
    store.close()
    assert store._session_gucs == {}
