import httpx
import numpy as np
import pytest

from src.backend.app.domain.catalog import Product
from src.backend.app.infrastructure.vectors.postgres_store import CatalogUnits
from src.backend.app.infrastructure.vectors.weaviate_store import WeaviateClient, WeaviateVectorStore


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


class _Client:
    def __init__(self, version="embed-multilingual-v3.0:catalog-text-v2", include=True):
        self.version, self.include = version, include

    def ready(self):
        pass

    def ensure_collection(self):
        pass

    def fetch(self, *, include_vectors):
        from src.backend.app.infrastructure.vectors.weaviate_store import VectorMetadata

        if not self.include:
            return {}, {}
        meta = {"P1": VectorMetadata("u1", "P1", self.version, "hash")}
        return meta, {"P1": np.ones(1024, dtype=np.float32)}


def test_weaviate_store_loads_vectors_in_postgres_catalog_order():
    client = _Client()
    store = WeaviateVectorStore("unused", client, expected_model_version=client.version)
    store.reader = _Reader()

    index = store.load()

    assert [p.product_id for p in index.units] == ["P1"]
    assert index.E.shape == (1, 1024)
    assert np.isclose(np.linalg.norm(index.E[0]), 1.0)


def test_weaviate_store_fails_closed_for_missing_or_stale_vectors():
    missing = WeaviateVectorStore("unused", _Client(include=False), expected_model_version="v")
    missing.reader = _Reader()
    with pytest.raises(RuntimeError, match="thiếu 1 search unit"):
        missing.load()

    stale = WeaviateVectorStore("unused", _Client(version="old"), expected_model_version="new")
    stale.reader = _Reader()
    with pytest.raises(RuntimeError, match="sai model/text version"):
        stale.load()


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
