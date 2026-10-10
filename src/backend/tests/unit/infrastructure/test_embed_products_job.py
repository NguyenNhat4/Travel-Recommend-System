"""Job index: chỉ embed phần đổi, dời object về id tất định, tạo collection theo loại index cấu hình, và nhúng song song
có giới hạn (P5)."""
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest

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
        model = embed_products.model_version("intfloat/multilingual-e5-small")
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
        return np.ones((len(texts), 384), dtype=np.float32)

    def close(self):
        pass


def test_job_moves_legacy_objects_to_deterministic_ids_and_uses_configured_index_type(monkeypatch):
    monkeypatch.setattr(embed_products, "PostgresCatalogReader",
                        lambda url: SimpleNamespace(load=lambda: _catalog(["P1", "P2"])))
    monkeypatch.setattr(embed_products, "WeaviateClient", _Weaviate)
    monkeypatch.setattr(embed_products, "build_embedder", lambda settings: _Embedder())
    _Weaviate.instances.clear()
    settings = SimpleNamespace(
        database_url="postgresql://unused", embed_model="intfloat/multilingual-e5-small", weaviate_url="http://weaviate.test",
        vector_collection="ProductE5Small", weaviate_vector_index_type="hfresh", weaviate_api_key="",
        weaviate_timeout_seconds=5.0, embed_dimension=384, search_bm25_k1=1.2, search_bm25_b=0.75,
    )

    report = embed_products.run(settings=settings)

    client = _Weaviate.instances[0]
    assert client.kwargs["vector_index_type"] == "hfresh"
    assert report["embedded"] == 1 and report["unchanged"] == 1 and report["deletedOrphans"] == 1
    assert [obj["id"] for obj in client.inserted] == [WeaviateClient.object_uuid("P1")]
    assert client.deleted == ["legacy-uuid", WeaviateClient.object_uuid("GONE")]


def test_detail_file_records_text_action_reason_and_vector_preview(monkeypatch, tmp_path):
    monkeypatch.setattr(embed_products, "PostgresCatalogReader",
                        lambda url: SimpleNamespace(load=lambda: _catalog(["P1", "P2", "P3"])))
    monkeypatch.setattr(embed_products, "WeaviateClient", _Weaviate)
    monkeypatch.setattr(embed_products, "build_embedder", lambda settings: _Embedder())
    settings = SimpleNamespace(
        database_url="postgresql://unused", embed_model="intfloat/multilingual-e5-small", weaviate_url="http://weaviate.test",
        vector_collection="ProductE5Small", weaviate_vector_index_type="hnsw", weaviate_api_key="",
        weaviate_timeout_seconds=5.0, embed_dimension=384, search_bm25_k1=1.2, search_bm25_b=0.75,
    )
    detail = tmp_path / "index_detail.jsonl"

    embed_products.run(settings=settings, detail_path=detail)

    rows = {row["productId"]: row for row in map(json.loads, detail.read_text(encoding="utf-8").splitlines())}
    assert (rows["P1"]["action"], rows["P1"]["reason"]) == ("embedded", "uuid")
    assert (rows["P2"]["action"], rows["P2"]["reason"]) == ("unchanged", None)
    assert (rows["P3"]["action"], rows["P3"]["reason"], rows["P3"]["text"]) == ("embedded", "new", "text P3")
    assert rows["P3"]["vector"] == {"dims": 384, "norm": round(384 ** 0.5, 6), "head": [1.0] * embed_products.PREVIEW_DIMS}
    assert "vector" not in rows["P2"]
    assert rows["GONE"] == {"productId": "GONE", "action": "deleted"}


# ---------------------------------------------------------------- --lexical-only (30/09): chỉ PATCH BM25, từ chối khi index lệch catalog
def _base_settings():
    return SimpleNamespace(
        database_url="postgresql://unused", embed_model="intfloat/multilingual-e5-small", weaviate_url="http://weaviate.test",
        vector_collection="ProductE5Small", weaviate_vector_index_type="hnsw", weaviate_api_key="",
        weaviate_timeout_seconds=5.0, embed_dimension=384, search_bm25_k1=1.2, search_bm25_b=0.75,
    )


class _NoEmbed:
    def __init__(self, *args, **kwargs):
        raise AssertionError("--lexical-only không được embed")


class _LexicalWeaviate(_Weaviate):
    """Index khớp catalog (P1, P2 ở uuid tất định, text hiện tại) nhưng object cũ chưa có property BM25."""

    def __init__(self, url, **kwargs):
        super().__init__(url, **kwargs)
        self.patched = []

    def fetch(self, *, include_vectors):
        model = embed_products.model_version("intfloat/multilingual-e5-small")
        return {pid: VectorMetadata(WeaviateClient.object_uuid(pid), pid, model, _digest(pid), lexical=(pid == "P2"))
                for pid in ("P1", "P2")}, {}

    def patch_properties(self, object_id, properties):
        self.patched.append((object_id, sorted(properties)))


def test_lexical_only_refuses_when_index_differs_from_catalog(monkeypatch):
    monkeypatch.setattr(embed_products, "PostgresCatalogReader",
                        lambda url: SimpleNamespace(load=lambda: _catalog(["P1", "P2"])))
    monkeypatch.setattr(embed_products, "WeaviateClient", _Weaviate)          # P1 ở uuid cũ (embed lại) + GONE mồ côi
    monkeypatch.setattr(embed_products, "build_embedder", lambda settings: _NoEmbed())
    _Weaviate.instances.clear()

    report = embed_products.run(settings=_base_settings(), lexical_only=True)

    assert report["lexicalOnly"] is True and "embedded 1" in report["refused"] and "deletedOrphans 1" in report["refused"]
    client = _Weaviate.instances[0]
    assert client.deleted == [] and client.inserted == []
    assert (report["embedded"], report["deletedOrphans"], report["missingLexical"]) == (1, 1, 1)


def test_lexical_only_patches_missing_bm25_without_embedding_or_deletes(monkeypatch):
    monkeypatch.setattr(embed_products, "PostgresCatalogReader",
                        lambda url: SimpleNamespace(load=lambda: _catalog(["P1", "P2"])))
    monkeypatch.setattr(embed_products, "WeaviateClient", _LexicalWeaviate)
    monkeypatch.setattr(embed_products, "build_embedder", lambda settings: _NoEmbed())
    _Weaviate.instances.clear()

    dry = embed_products.run(settings=_base_settings(), lexical_only=True, dry_run=True)
    assert dry["missingLexical"] == 1 and "refused" not in dry and _Weaviate.instances[-1].patched == []
    report = embed_products.run(settings=_base_settings(), lexical_only=True)

    client = _Weaviate.instances[-1]
    assert client.patched == [(WeaviateClient.object_uuid("P1"), ["nameAscii", "searchTextAscii"])]
    assert client.deleted == [] and client.inserted == []
    assert (report["embedded"], report["deletedOrphans"], report["backfilledLexical"]) == (0, 0, 1)


def test_main_exits_2_when_lexical_only_is_refused(monkeypatch, capsys):
    monkeypatch.setattr(embed_products, "run", lambda **kw: {"refused": "lệch", "lexicalOnly": kw["lexical_only"]})
    assert embed_products.main(["--lexical-only"]) == 2
    assert json.loads(capsys.readouterr().out)["lexicalOnly"] is True
    monkeypatch.setattr(embed_products, "run", lambda **kw: {"embedded": 0})
    assert embed_products.main(["--dry-run"]) == 0


# ---------------------------------------------------------------- ghi theo lô, lỗi giữa chừng, --force
def _settings():
    return SimpleNamespace(
        database_url="postgresql://unused", embed_model="intfloat/multilingual-e5-small", weaviate_url="http://weaviate.test",
        vector_collection="ProductE5Small", weaviate_vector_index_type="hnsw", weaviate_api_key="",
        weaviate_timeout_seconds=5.0, embed_dimension=384, search_bm25_k1=1.2, search_bm25_b=0.75,
    )


def _vector(text):
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
    return np.random.default_rng(seed).random(384).astype(np.float32)


class _Store:
    """Weaviate giả giữ object giữa các lần chạy."""

    objects: dict = {}

    def __init__(self, url, **kwargs):
        pass

    object_uuid = staticmethod(WeaviateClient.object_uuid)

    def ready(self):
        pass

    def ensure_collection(self):
        pass

    def fetch(self, *, include_vectors):
        return {obj["properties"]["productId"]: VectorMetadata(obj["id"], obj["properties"]["productId"],
                                                               obj["properties"]["modelVersion"],
                                                               obj["properties"]["textHash"])
                for obj in _Store.objects.values()}, {}

    def delete(self, ids):
        for uuid in ids:
            _Store.objects.pop(uuid, None)

    def insert(self, objects):
        for obj in objects:
            _Store.objects[obj["id"]] = obj

    def close(self):
        pass


class _CountingEmbedder:
    """e5 giả: đếm số lô, lỗi ở text trong `fail_on`."""

    fail_on: set = set()
    calls = 0

    def embed_docs(self, texts):
        type(self).calls += 1
        if type(self).fail_on & set(texts):
            raise RuntimeError("model lỗi")
        return np.stack([_vector(t) for t in texts])

    def close(self):
        pass


@pytest.fixture
def job(monkeypatch):
    ids = [f"P{i:03d}" for i in range(500)]
    monkeypatch.setattr(embed_products, "PostgresCatalogReader", lambda url: SimpleNamespace(load=lambda: _catalog(ids)))
    monkeypatch.setattr(embed_products, "WeaviateClient", _Store)
    monkeypatch.setattr(embed_products, "build_embedder", lambda settings: _CountingEmbedder())
    _Store.objects = {}
    _CountingEmbedder.fail_on, _CountingEmbedder.calls = set(), 0
    return ids


def test_index_writes_in_batches_of_96(job):
    report = embed_products.run(settings=_settings())
    assert (report["embedded"], _CountingEmbedder.calls, len(_Store.objects)) == (500, 6, 500)  # 500 / 96 → 6 lô
    assert {obj["properties"]["modelVersion"] for obj in _Store.objects.values()} == {
        embed_products.model_version("intfloat/multilingual-e5-small")}


def test_failed_batch_keeps_finished_batches_and_rerun_embeds_only_the_rest(job):
    _CountingEmbedder.fail_on = {"text P250"}  # lô thứ 3 (P192–P287)
    with pytest.raises(RuntimeError):
        embed_products.run(settings=_settings())
    kept = {obj["properties"]["productId"] for obj in _Store.objects.values()}
    assert "P250" not in kept and "P000" in kept and len(kept) == 192
    _CountingEmbedder.fail_on = set()
    report = embed_products.run(settings=_settings())
    assert report["embedded"] == 500 - len(kept)  # chỉ nhúng phần còn thiếu
    assert len(_Store.objects) == 500


def test_force_reembeds_unchanged_units(job):
    embed_products.run(settings=_settings())
    assert embed_products.run(settings=_settings())["embedded"] == 0
    assert embed_products.run(settings=_settings(), force=True)["embedded"] == 500
