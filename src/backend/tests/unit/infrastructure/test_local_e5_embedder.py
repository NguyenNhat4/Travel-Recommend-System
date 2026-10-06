"""e5-small local (PRD FR-SRC-02, chốt 06/10): tiền tố query/passage, normalize, cấu hình, không trộn model trong collection."""
from __future__ import annotations

import os
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError

from src.backend.app.core.config import Settings
from src.backend.app.infrastructure.embeddings.factory import build_embedder
from src.backend.app.infrastructure.embeddings.local_e5_embedder import LocalE5Embedder
from src.backend.app.infrastructure.vectors.weaviate_store import VectorMetadata
from src.backend.jobs import embed_products


class _Recorder:
    def __init__(self, dim=4):
        self.dim, self.batches = dim, []

    def __call__(self, texts):
        self.batches.append(list(texts))
        return np.full((len(texts), self.dim), 2.0, dtype=np.float32)


def test_docs_get_passage_prefix_and_queries_get_query_prefix():
    encode = _Recorder()
    embedder = LocalE5Embedder(dimension=4, encode_fn=encode)
    embedder.embed_docs(["Khách sạn A"])
    embedder.embed_query("khach san nha trang")
    embedder.embed_queries(["a", "b"])
    assert encode.batches == [["passage: Khách sạn A"], ["query: khach san nha trang"], ["query: a", "query: b"]]


def test_vectors_are_l2_normalised_and_batched():
    encode = _Recorder()
    vectors = LocalE5Embedder(dimension=4, batch_size=2, encode_fn=encode).embed_docs(["a", "b", "c"])
    assert [len(batch) for batch in encode.batches] == [2, 1]
    assert vectors.shape == (3, 4)
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), 1.0, rtol=1e-6)


def test_wrong_dimension_and_empty_input():
    with pytest.raises(RuntimeError, match="shape"):
        LocalE5Embedder(dimension=384, encode_fn=_Recorder(dim=4)).embed_docs(["a"])
    assert LocalE5Embedder(dimension=384, encode_fn=_Recorder()).embed_docs([]).shape == (0, 384)


def _settings(**env):
    return Settings(_env_file=None, **env)


def test_default_is_e5_small_and_other_dimensions_are_rejected():
    settings = _settings()
    assert (settings.embed_model, settings.embed_dimension) == ("intfloat/multilingual-e5-small", 384)
    assert settings.weaviate_collection == "Product"
    assert settings.search_cutoff == 0.84
    with pytest.raises(ValidationError, match="EMBED_DIMENSION"):
        _settings(embed_dimension=1024)
    with pytest.raises(ValidationError):
        _settings(embed_model="embed-multilingual-v3.0")  # Cohere đã bỏ (PRD 06/10)


def test_factory_builds_the_pinned_e5_small():
    embedder = build_embedder(_settings())
    assert isinstance(embedder, LocalE5Embedder)
    assert (embedder.name, embedder.revision, embedder.dimension) == (
        "intfloat/multilingual-e5-small", "614241f622f53c4eeff9890bdc4f31cfecc418b3", 384)


class _CohereCollection:
    """Collection còn vector Cohere: job e5 phải từ chối, không xoá, không ghi."""

    def __init__(self, url, **kwargs):
        self.writes = []

    object_uuid = staticmethod(embed_products.WeaviateClient.object_uuid)

    def ready(self):
        pass

    def ensure_collection(self):
        pass

    def fetch(self, *, include_vectors):
        old = embed_products.model_version("embed-multilingual-v3.0")
        return {"P1": VectorMetadata(self.object_uuid("P1"), "P1", old, "x")}, {}

    def delete(self, ids):
        self.writes.append(("delete", ids))

    def insert(self, objects):
        self.writes.append(("insert", objects))

    def close(self):
        pass


def test_index_job_refuses_to_write_e5_vectors_into_a_cohere_collection(monkeypatch):
    from src.backend.app.domain.catalog.models import Product
    from src.backend.app.infrastructure.vectors.postgres_store import CatalogUnits

    unit = Product(product_id="P1", name="P1", taxonomy="hotel", destination="Nha Trang", description="",
                   attributes={"level": "property"}, unit_price=None)
    catalog = CatalogUnits(units=[unit], texts=["text"], taxonomy=np.array(["hotel"]), destination=np.array(["Nha Trang"]),
                           available=np.array([True]), recommendable=np.array([True]), parent_of={})
    monkeypatch.setattr(embed_products, "PostgresCatalogReader", lambda url: SimpleNamespace(load=lambda: catalog))
    created = []
    monkeypatch.setattr(embed_products, "WeaviateClient", lambda url, **kw: created.append(_CohereCollection(url)) or created[-1])
    monkeypatch.setattr(embed_products, "build_embedder", lambda *a, **k: pytest.fail("không được embed"))
    report = embed_products.run(settings=_settings(weaviate_collection="Product"))
    assert "embed-multilingual-v3.0" in report["refused"]
    assert created[0].writes == []


@pytest.mark.skipif(os.environ.get("E5_SMOKE") != "1", reason="cần model e5-small trong cache HF; đặt E5_SMOKE=1 để chạy")
def test_real_model_ranks_the_matching_passage_first():
    embedder = build_embedder(_settings())
    docs = embedder.embed_docs(["Khách sạn gần biển Nha Trang có hồ bơi", "Vé máy bay Hà Nội đi TP. Hồ Chí Minh"])
    query = embedder.embed_query("khách sạn ven biển ở Nha Trang")
    assert docs.shape == (2, 384)
    assert float(docs[0] @ query) > float(docs[1] @ query)


def test_settings_from_environment_strings(monkeypatch):
    """Biến môi trường là chuỗi: `.env.example` đặt EMBED_DIMENSION=384 phải khởi động được."""
    monkeypatch.setenv("EMBED_MODEL", "intfloat/multilingual-e5-small")
    monkeypatch.setenv("EMBED_DIMENSION", "384")
    assert _settings().embed_dimension == 384
