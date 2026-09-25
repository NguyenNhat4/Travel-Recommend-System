"""Job index: chỉ embed phần đổi, dời object về id tất định, và tạo collection theo loại index cấu hình."""
import hashlib
from types import SimpleNamespace

import numpy as np

from src.backend.app.domain.catalog import Product
from src.backend.app.infrastructure.vectors.postgres_store import CatalogUnits
from src.backend.app.infrastructure.vectors.weaviate_store import VectorMetadata, WeaviateClient
from src.backend.jobs import embed_products


def _catalog(ids):
    units = [Product(product_id=pid, name=pid, taxonomy="hotel", destination="Nha Trang", description="",
                     attributes={"level": "property"}, unit_price=None) for pid in ids]
    return CatalogUnits(units=units, texts=[f"text {pid}" for pid in ids],
                        taxonomy=np.array(["hotel"] * len(ids)), destination=np.array(["Nha Trang"] * len(ids)),
                        available=np.array([True] * len(ids)), recommendable=np.array([True] * len(ids)),
                        parent_of={})


def _digest(pid):
    return hashlib.sha256(f"text {pid}".encode("utf-8")).hexdigest()


class _Weaviate:
    instances = []

    def __init__(self, url, **kwargs):
        self.kwargs = kwargs
        self.deleted, self.inserted = [], []
        _Weaviate.instances.append(self)

    object_uuid = staticmethod(WeaviateClient.object_uuid)

    def ready(self):
        pass

    def ensure_collection(self):
        pass

    def fetch(self, *, include_vectors):
        model = embed_products.model_version("embed-multilingual-v3.0")
        return {
            # Object cũ ghi ở uuid ngẫu nhiên: truy vấn lọc theo id tất định không thấy nó.
            "P1": VectorMetadata("legacy-uuid", "P1", model, _digest("P1")),
            "P2": VectorMetadata(WeaviateClient.object_uuid("P2"), "P2", model, _digest("P2")),
            "GONE": VectorMetadata(WeaviateClient.object_uuid("GONE"), "GONE", model, "x"),
        }, {}

    def delete(self, ids):
        self.deleted.extend(ids)

    def insert(self, objects):
        self.inserted.extend(objects)

    def close(self):
        pass


class _Embedder:
    batch_size = 96

    def __init__(self, *args, **kwargs):
        pass

    def embed_docs(self, texts):
        return np.ones((len(texts), 1024), dtype=np.float32)

    def close(self):
        pass


def test_job_moves_legacy_objects_to_deterministic_ids_and_uses_configured_index_type(monkeypatch):
    monkeypatch.setattr(embed_products, "PostgresCatalogReader",
                        lambda url: SimpleNamespace(load=lambda: _catalog(["P1", "P2"])))
    monkeypatch.setattr(embed_products, "WeaviateClient", _Weaviate)
    monkeypatch.setattr(embed_products, "CohereEmbedder", _Embedder)
    _Weaviate.instances.clear()
    settings = SimpleNamespace(
        database_url="postgresql://unused", embed_model="embed-multilingual-v3.0", weaviate_url="http://weaviate.test",
        weaviate_collection="Product", weaviate_vector_index_type="hfresh", weaviate_api_key="",
        weaviate_timeout_seconds=5.0, cohere_api_key="k", cohere_base_url="http://cohere.test",
        embed_dimension=1024, cohere_timeout_seconds=5.0,
    )

    report = embed_products.run(settings=settings)

    client = _Weaviate.instances[0]
    assert client.kwargs["vector_index_type"] == "hfresh"
    assert report["embedded"] == 1 and report["unchanged"] == 1 and report["deletedOrphans"] == 1
    assert [obj["id"] for obj in client.inserted] == [WeaviateClient.object_uuid("P1")]
    assert client.deleted == ["legacy-uuid", WeaviateClient.object_uuid("GONE")]
