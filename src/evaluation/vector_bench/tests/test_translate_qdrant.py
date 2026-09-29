"""Part 7 — dịch AST → Filter của Qdrant (so cấu trúc), không cần engine."""
from __future__ import annotations

import pytest
from qdrant_client import models as m

from evaluation.vector_bench.engines.base import StoreOptions
from evaluation.vector_bench.engines.qdrant import QdrantStore
from evaluation.vector_bench.filters import InvalidFilter


@pytest.fixture()
def store(cfg):
    return QdrantStore(cfg.engine("qdrant"), 1024, StoreOptions())


def test_none(store):
    assert store.translate(None) is None


def test_and_eq_in_range(store):
    f = store.translate({"and": [{"eq": ["destination", "Nha Trang"]}, {"in": ["taxonomy", ["hotel", "combo"]]},
                                 {"range": ["unit_price", {"lte": 500}]}, {"eq": ["available", True]}]})
    assert f == m.Filter(must=[
        m.FieldCondition(key="destination", match=m.MatchValue(value="Nha Trang")),
        m.FieldCondition(key="taxonomy", match=m.MatchAny(any=["hotel", "combo"])),
        m.FieldCondition(key="unit_price", range=m.Range(lte=500.0)),
        m.FieldCondition(key="available", match=m.MatchValue(value=True))])


def test_all_any_not(store):
    f = store.translate({"and": [{"all": ["amenity_ids", [3, 17]]}, {"not": {"any": ["amenity_ids", [5]]}}]})
    assert f == m.Filter(must=[
        m.Filter(must=[m.FieldCondition(key="amenity_ids", match=m.MatchValue(value=3)),
                       m.FieldCondition(key="amenity_ids", match=m.MatchValue(value=17))]),
        m.Filter(must_not=[m.FieldCondition(key="amenity_ids", match=m.MatchAny(any=[5]))])])


def test_or_geo_id(store):
    f = store.translate({"or": [{"geo": {"lat": 10.0, "lon": 106.0, "radius_m": 5000}}, {"id_in": ["abc"]}]})
    assert f == m.Filter(should=[
        m.FieldCondition(key="location", geo_radius=m.GeoRadius(center=m.GeoPoint(lat=10.0, lon=106.0), radius=5000.0)),
        m.HasIdCondition(has_id=["abc"])])


def test_single_condition_wrapped(store):
    assert store.translate({"eq": ["variant", "golf"]}) == m.Filter(must=[m.FieldCondition(key="variant",
                                                                                           match=m.MatchValue(value="golf"))])


def test_search_params(store):
    assert store.search_params({"mode": "exact"}) == m.SearchParams(exact=True)
    assert store.search_params({"mode": "ann"}) is None
    assert store.search_params({"mode": "ann", "hnsw_ef": 128}) == m.SearchParams(hnsw_ef=128)
    sp = store.search_params({"mode": "ann_acorn", "hnsw_ef": 64})
    assert sp.acorn.enable is True and sp.hnsw_ef == 64


def test_invalid(store):
    with pytest.raises(InvalidFilter):
        store.translate({"all": ["amenity_ids", []]})
