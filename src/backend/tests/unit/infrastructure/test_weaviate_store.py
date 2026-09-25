from types import SimpleNamespace

import httpx
import numpy as np
import pytest

from src.backend.app.domain.catalog import Product
from src.backend.app.infrastructure.vectors.postgres_store import CatalogUnits
from src.backend.app.infrastructure.vectors.weaviate_store import WeaviateClient, WeaviateVectorSearch, WeaviateVectorStore


def _catalog() -> CatalogUnits:
    product = Product(
        product_id="P1",
        name="Resort A",
        taxonomy="hotel",
        destination="Nha Trang",
        description="",
        attributes={"level": "property"},
        unit_price=None,
    )
    return CatalogUnits(
        units=[product],
        texts=["Resort A tại Nha Trang."],
        taxonomy=np.array(["hotel"]),
        destination=np.array(["Nha Trang"]),
        available=np.array([True]),
        recommendable=np.array([True]),
        parent_of={},
    )


class _Reader:
    def load(self):
        return _catalog()


class _Obj:
    def __init__(self, product_id, distance=None, vector=None):
        self.properties = {"productId": product_id}
        self.metadata = SimpleNamespace(distance=distance)
        self.vector = {"default": vector} if vector is not None else {}


class _Collection:
    def __init__(self, count=1):
        self.calls = []
        self.count = count
        self.query = SimpleNamespace(near_vector=self._near_vector, fetch_objects=self._fetch_objects)
        self.aggregate = SimpleNamespace(over_all=self._over_all)

    def _near_vector(self, **kwargs):
        self.calls.append(("near_vector", kwargs))
        return SimpleNamespace(objects=[_Obj("P1", 0.25, [1.0, 0.0]), _Obj("P2", 0.5, [0.0, 1.0])])

    def _fetch_objects(self, **kwargs):
        self.calls.append(("fetch_objects", kwargs))
        return SimpleNamespace(objects=[_Obj("P1", vector=[1.0, 0.0])])

    def _over_all(self, **kwargs):
        self.calls.append(("aggregate", kwargs))
        return SimpleNamespace(total_count=self.count)


def _search(collection):
    client = SimpleNamespace(collections=SimpleNamespace(get=lambda name: collection), close=lambda: None)
    return WeaviateVectorSearch(client, collection="Product", dimension=2)


def test_weaviate_store_returns_metadata_index_without_downloading_vectors():
    collection = _Collection(count=1)
    store = WeaviateVectorStore("unused", _search(collection), expected_model_version="v")
    store.reader = _Reader()

    index, search = store.load()

    assert [p.product_id for p in index.units] == ["P1"] and index.model_version == "v"
    assert search is store.search
    assert [name for name, _ in collection.calls] == ["aggregate"]  # không fetch vector lúc khởi động


def test_weaviate_store_fails_closed_when_vectors_missing_or_stale():
    store = WeaviateVectorStore("unused", _search(_Collection(count=0)), expected_model_version="v")
    store.reader = _Reader()
    with pytest.raises(RuntimeError, match="thiếu 1 search unit"):
        store.load()


def test_near_vector_scores_are_one_minus_distance_and_filter_by_object_id():
    collection = _Collection()
    hits = _search(collection).near_vector(np.array([1.0, 0.0]), ["P1", "P2"], 5, with_vectors=True)

    assert [(h.product_id, h.score) for h in hits] == [("P1", 0.75), ("P2", 0.5)]
    assert hits[0].vector.tolist() == [1.0, 0.0]
    kwargs = collection.calls[0][1]
    assert kwargs["limit"] == 5 and kwargs["include_vector"] is True and kwargs["filters"] is not None


def test_near_vector_skips_filter_for_whole_catalog_and_query_for_empty_allowlist():
    collection = _Collection()
    search = _search(collection)
    search.near_vector(np.array([1.0, 0.0]), None, 3)
    assert collection.calls[0][1]["filters"] is None
    assert search.near_vector(np.array([1.0, 0.0]), [], 3) == []
    assert len(collection.calls) == 1


def test_vectors_fetches_by_id():
    assert list(_search(_Collection()).vectors(["P1", "P1"])) == ["P1"]


def test_rest_fetch_pages_with_cursor():
    pages = [
        {"objects": [{"id": "u1", "properties": {"productId": "P1", "modelVersion": "v", "textHash": "h"}}]},
        {"objects": []},
    ]
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return httpx.Response(200, json=pages[len(seen) - 1])

    raw = httpx.Client(base_url="http://weaviate.test", transport=httpx.MockTransport(handler))
    metadata, vectors = WeaviateClient("http://unused", client=raw).fetch(include_vectors=False, page_size=1)
    assert list(metadata) == ["P1"] and vectors == {}
    assert "after" not in seen[0] and seen[1]["after"] == "u1"


def test_weaviate_client_creates_self_provided_cosine_collection():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(404)
        return httpx.Response(200, json={})

    raw = httpx.Client(base_url="http://weaviate.test", transport=httpx.MockTransport(handler))
    WeaviateClient("http://unused", client=raw).ensure_collection()
    payload = __import__("json").loads(requests[-1].content)
    assert payload["vectorizer"] == "none"
    assert payload["vectorIndexConfig"]["distance"] == "cosine"
