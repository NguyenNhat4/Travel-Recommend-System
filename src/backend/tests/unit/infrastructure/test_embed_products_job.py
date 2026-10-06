"""Job index: chỉ embed phần đổi, dời object về id tất định, tạo collection theo loại index cấu hình, và nhúng song song
có giới hạn (P5)."""
import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import httpx
import numpy as np
import pytest

from src.backend.app.domain.catalog import Product
from src.backend.app.infrastructure.embeddings.cohere_embedder import CallLimiter, CohereEmbedder
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

    def vector_dimension(self):
        return 1024

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
        database_url="postgresql://unused", embed_provider="cohere", embed_model="embed-multilingual-v3.0",
        weaviate_url="http://weaviate.test",
        weaviate_collection="Product", weaviate_vector_index_type="hfresh", weaviate_api_key="",
        weaviate_timeout_seconds=5.0, cohere_api_key="k", cohere_base_url="http://cohere.test",
        embed_dimension=1024, cohere_timeout_seconds=5.0, search_bm25_k1=1.2, search_bm25_b=0.75,
        cohere_embed_concurrency=1, cohere_calls_per_minute=0,
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
    monkeypatch.setattr(embed_products, "CohereEmbedder", _Embedder)
    settings = SimpleNamespace(
        database_url="postgresql://unused", embed_provider="cohere", embed_model="embed-multilingual-v3.0",
        weaviate_url="http://weaviate.test",
        weaviate_collection="Product", weaviate_vector_index_type="hnsw", weaviate_api_key="",
        weaviate_timeout_seconds=5.0, cohere_api_key="k", cohere_base_url="http://cohere.test",
        embed_dimension=1024, cohere_timeout_seconds=5.0, search_bm25_k1=1.2, search_bm25_b=0.75,
        cohere_embed_concurrency=1, cohere_calls_per_minute=0,
    )
    detail = tmp_path / "index_detail.jsonl"

    embed_products.run(settings=settings, detail_path=detail)

    rows = {row["productId"]: row for row in map(json.loads, detail.read_text(encoding="utf-8").splitlines())}
    assert (rows["P1"]["action"], rows["P1"]["reason"]) == ("embedded", "uuid")
    assert (rows["P2"]["action"], rows["P2"]["reason"]) == ("unchanged", None)
    assert (rows["P3"]["action"], rows["P3"]["reason"], rows["P3"]["text"]) == ("embedded", "new", "text P3")
    assert rows["P3"]["vector"] == {"dims": 1024, "norm": 32.0, "head": [1.0] * embed_products.PREVIEW_DIMS}
    assert "vector" not in rows["P2"]
    assert rows["GONE"] == {"productId": "GONE", "action": "deleted"}


# ---------------------------------------------------------------- --lexical-only (30/09): chỉ PATCH BM25, từ chối khi index lệch catalog
def _base_settings():
    return SimpleNamespace(
        database_url="postgresql://unused", embed_provider="cohere", embed_model="embed-multilingual-v3.0",
        weaviate_url="http://weaviate.test",
        weaviate_collection="Product", weaviate_vector_index_type="hnsw", weaviate_api_key="",
        weaviate_timeout_seconds=5.0, cohere_api_key="k", cohere_base_url="http://cohere.test",
        embed_dimension=1024, cohere_timeout_seconds=5.0, search_bm25_k1=1.2, search_bm25_b=0.75,
        cohere_embed_concurrency=1, cohere_calls_per_minute=0,
    )


class _NoCohere:
    def __init__(self, *args, **kwargs):
        raise AssertionError("--lexical-only không được gọi Cohere")


class _LexicalWeaviate(_Weaviate):
    """Index khớp catalog (P1, P2 ở uuid tất định, text hiện tại) nhưng object cũ chưa có property BM25."""

    def __init__(self, url, **kwargs):
        super().__init__(url, **kwargs)
        self.patched = []

    def fetch(self, *, include_vectors):
        model = embed_products.model_version("embed-multilingual-v3.0")
        return {pid: VectorMetadata(WeaviateClient.object_uuid(pid), pid, model, _digest(pid), lexical=(pid == "P2"))
                for pid in ("P1", "P2")}, {}

    def patch_properties(self, object_id, properties):
        self.patched.append((object_id, sorted(properties)))


def test_lexical_only_refuses_when_index_differs_from_catalog(monkeypatch):
    monkeypatch.setattr(embed_products, "PostgresCatalogReader",
                        lambda url: SimpleNamespace(load=lambda: _catalog(["P1", "P2"])))
    monkeypatch.setattr(embed_products, "WeaviateClient", _Weaviate)          # P1 ở uuid cũ (embed lại) + GONE mồ côi
    monkeypatch.setattr(embed_products, "CohereEmbedder", _NoCohere)
    _Weaviate.instances.clear()

    report = embed_products.run(settings=_base_settings(), lexical_only=True)

    assert report["lexicalOnly"] is True and "embedded 1" in report["refused"] and "deletedOrphans 1" in report["refused"]
    client = _Weaviate.instances[0]
    assert client.deleted == [] and client.inserted == []
    assert (report["embedded"], report["deletedOrphans"], report["missingLexical"]) == (1, 1, 1)


def test_lexical_only_patches_missing_bm25_without_cohere_or_deletes(monkeypatch):
    monkeypatch.setattr(embed_products, "PostgresCatalogReader",
                        lambda url: SimpleNamespace(load=lambda: _catalog(["P1", "P2"])))
    monkeypatch.setattr(embed_products, "WeaviateClient", _LexicalWeaviate)
    monkeypatch.setattr(embed_products, "CohereEmbedder", _NoCohere)
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


# ---------------------------------------------------------------- P5.2: nhúng song song (docs/plan/2026-09-29-index-cohere-song-song.md)
def _settings(concurrency, calls_per_minute=0):
    return SimpleNamespace(
        database_url="postgresql://unused", embed_provider="cohere", embed_model="embed-multilingual-v3.0",
        weaviate_url="http://weaviate.test",
        weaviate_collection="Product", weaviate_vector_index_type="hnsw", weaviate_api_key="",
        weaviate_timeout_seconds=5.0, cohere_api_key="k", cohere_base_url="http://cohere.test",
        embed_dimension=1024, cohere_timeout_seconds=5.0, search_bm25_k1=1.2, search_bm25_b=0.75,
        cohere_embed_concurrency=concurrency, cohere_calls_per_minute=calls_per_minute,
    )


def _vector(text):
    """Vector tất định theo text: so được kết quả song song với tuần tự."""
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
    return np.random.default_rng(seed).random(1024).astype(np.float32)


class _Store:
    """Weaviate giả giữ object giữa các lần chạy; ghi lại luồng nào gọi delete / insert."""

    objects: dict = {}
    writers: set = set()

    def __init__(self, url, **kwargs):
        pass

    object_uuid = staticmethod(WeaviateClient.object_uuid)

    def ready(self):
        pass

    def ensure_collection(self):
        pass

    def vector_dimension(self):
        return len(next(iter(_Store.objects.values()))["vector"]) if _Store.objects else None

    def fetch(self, *, include_vectors):
        return {obj["properties"]["productId"]: VectorMetadata(obj["id"], obj["properties"]["productId"],
                                                               obj["properties"]["modelVersion"],
                                                               obj["properties"]["textHash"])
                for obj in _Store.objects.values()}, {}

    def delete(self, ids):
        _Store.writers.add(threading.current_thread().name)
        for uuid in ids:
            _Store.objects.pop(uuid, None)

    def insert(self, objects):
        _Store.writers.add(threading.current_thread().name)
        for obj in objects:
            _Store.objects[obj["id"]] = obj

    def close(self):
        pass


class _SlowEmbedder:
    """Cohere giả: trễ `delay` giây mỗi lô, đếm số lô chạy cùng lúc, lỗi ở text trong `fail_on`."""

    batch_size = 96
    delay = 0.0
    fail_on: set = set()
    active = peak = calls = 0
    lock = threading.Lock()

    def __init__(self, *args, limiter=None, **kwargs):
        self.limiter = limiter

    def embed_docs(self, texts):
        if self.limiter is not None:
            self.limiter.acquire()
        cls = type(self)
        with cls.lock:
            cls.active += 1
            cls.calls += 1
            cls.peak = max(cls.peak, cls.active)
        try:
            time.sleep(cls.delay)
            if cls.fail_on & set(texts):
                raise httpx.HTTPStatusError("429", request=httpx.Request("POST", "http://cohere.test"),
                                            response=httpx.Response(429))
            return np.stack([_vector(t) for t in texts])
        finally:
            with cls.lock:
                cls.active -= 1

    def close(self):
        pass


@pytest.fixture
def parallel_job(monkeypatch):
    ids = [f"P{i:03d}" for i in range(500)]
    monkeypatch.setattr(embed_products, "PostgresCatalogReader", lambda url: SimpleNamespace(load=lambda: _catalog(ids)))
    monkeypatch.setattr(embed_products, "WeaviateClient", _Store)
    monkeypatch.setattr(embed_products, "CohereEmbedder", _SlowEmbedder)
    _Store.objects, _Store.writers = {}, set()
    _SlowEmbedder.delay, _SlowEmbedder.fail_on = 0.0, set()
    _SlowEmbedder.active = _SlowEmbedder.peak = _SlowEmbedder.calls = 0
    return ids


def _snapshot():
    return {uuid: (obj["properties"], obj["vector"]) for uuid, obj in sorted(_Store.objects.items())}


def test_parallel_index_writes_exactly_what_sequential_writes(parallel_job):
    embed_products.run(settings=_settings(1))
    sequential = _snapshot()
    _Store.objects = {}
    report = embed_products.run(settings=_settings(4))
    assert _snapshot() == sequential
    assert len(sequential) == 500
    assert (report["embedded"], report["concurrency"], report["cohereCalls"]) == (500, 4, 6)  # 500 / 96 → 6 lô


def test_parallel_index_respects_concurrency_and_writes_only_from_the_calling_thread(parallel_job):
    _SlowEmbedder.delay = 0.05
    embed_products.run(settings=_settings(3))
    assert _SlowEmbedder.peak == 3
    assert _Store.writers == {threading.current_thread().name}


def test_failed_batch_keeps_finished_batches_and_rerun_embeds_only_the_rest(parallel_job):
    _SlowEmbedder.delay = 0.02
    _SlowEmbedder.fail_on = {"text P250"}  # lô thứ 3 (P192–P287)
    with pytest.raises(httpx.HTTPStatusError):
        embed_products.run(settings=_settings(2))
    kept = {obj["properties"]["productId"] for obj in _Store.objects.values()}
    assert "P250" not in kept and "P000" in kept and len(kept) < 500
    _SlowEmbedder.fail_on = set()
    report = embed_products.run(settings=_settings(2))
    assert report["embedded"] == 500 - len(kept)  # chỉ nhúng phần còn thiếu
    assert len(_Store.objects) == 500


def test_parallel_is_faster_than_sequential_with_slow_cohere(parallel_job, monkeypatch):
    ids = [f"P{i:03d}" for i in range(768)]  # 8 lô
    monkeypatch.setattr(embed_products, "PostgresCatalogReader", lambda url: SimpleNamespace(load=lambda: _catalog(ids)))
    _SlowEmbedder.delay = 0.3
    started = time.monotonic()
    embed_products.run(settings=_settings(1))
    sequential = time.monotonic() - started
    _Store.objects = {}
    started = time.monotonic()
    report = embed_products.run(settings=_settings(4))
    parallel = time.monotonic() - started
    assert sequential >= 2 * parallel, (sequential, parallel)
    assert report["seconds"] >= 0


def test_force_reembeds_unchanged_units(parallel_job):
    embed_products.run(settings=_settings(4))
    assert embed_products.run(settings=_settings(4))["embedded"] == 0
    assert embed_products.run(settings=_settings(4), force=True)["embedded"] == 500


def test_real_http_client_is_shared_safely_across_threads():
    """Cohere giả qua HTTP thật (server local, nhiều luồng): một httpx.Client dùng chung cho các lô chạy song song."""
    seen, lock, active = [], threading.Lock(), [0, 0]

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            texts = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["texts"]
            with lock:
                active[0] += 1
                active[1] = max(active[1], active[0])
            time.sleep(0.05)
            with lock:
                active[0] -= 1
                seen.append(len(texts))
            body = json.dumps({"embeddings": {"float": [_vector(t).tolist() for t in texts]}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        embedder = CohereEmbedder("k", base_url=f"http://127.0.0.1:{server.server_address[1]}",
                                  limiter=CallLimiter(0))
        texts = {f"P{i}": f"text P{i}" for i in range(96 * 6)}
        batches = [list(texts)[i:i + 96] for i in range(0, len(texts), 96)]
        results = {}
        embed_products.embed_batches(embedder, batches, texts, 4,
                                     lambda ids, vectors: results.update(zip(ids, vectors)))
        embedder.close()
    finally:
        server.shutdown()
    assert seen.count(96) == 6 and active[1] > 1
    for pid, vector in results.items():
        expected = _vector(texts[pid])
        assert np.allclose(vector, expected / np.linalg.norm(expected), atol=1e-6)


# ---------------------------------------------------------------- FR-SRC-02 (06/10): provider local + chặn ghi lẫn model / số chiều
def _local_settings(collection="ProductE5", dimension=384):
    return SimpleNamespace(
        database_url="postgresql://unused", embed_provider="local", embed_model="intfloat/multilingual-e5-small",
        embed_model_revision="614241f622f53c4eeff9890bdc4f31cfecc418b3", embed_dimension=dimension, embed_threads=0,
        embed_batch_size=32, embed_max_length=512, embed_cache_dir="",
        weaviate_url="http://weaviate.test", weaviate_collection=collection, weaviate_vector_index_type="hfresh",
        weaviate_api_key="", weaviate_timeout_seconds=5.0, search_bm25_k1=1.2, search_bm25_b=0.75,
        cohere_api_key="", cohere_base_url="http://cohere.test", cohere_timeout_seconds=5.0,
        cohere_embed_concurrency=4, cohere_calls_per_minute=90,
    )


class _LocalEmbedder:
    """Model local giả (384 chiều): ghi lại tham số dựng, không tải gì."""

    built: list = []

    def __init__(self, model_name, **kwargs):
        _LocalEmbedder.built.append((model_name, kwargs))

    def embed_docs(self, texts):
        return np.full((len(texts), 384), 0.05, dtype=np.float32)

    def close(self):
        pass


def _store_with(objects_model: str | None, dimension: int):
    """Weaviate giả đang giữ P1, P2 của model `objects_model` (None = collection rỗng) với vector `dimension` chiều."""
    _Store.objects = {}
    if objects_model:
        for pid in ("P1", "P2"):
            uid = WeaviateClient.object_uuid(pid)
            _Store.objects[uid] = {"id": uid, "vector": [0.0] * dimension,
                                   "properties": {"productId": pid, "modelVersion": embed_products.model_version(objects_model),
                                                  "textHash": _digest(pid)}}


@pytest.fixture
def local_job(monkeypatch):
    monkeypatch.setattr(embed_products, "PostgresCatalogReader", lambda url: SimpleNamespace(load=lambda: _catalog(["P1", "P2"])))
    monkeypatch.setattr(embed_products, "WeaviateClient", _Store)
    monkeypatch.setattr(embed_products, "LocalE5Embedder", _LocalEmbedder)
    monkeypatch.setattr(embed_products, "CohereEmbedder", _NoCohere)
    _LocalEmbedder.built = []
    _Store.writers = set()


def test_local_provider_indexes_new_collection_with_e5_model_version_in_one_thread(local_job):
    _store_with(None, 0)
    report = embed_products.run(settings=_local_settings())
    assert (report["provider"], report["collection"], report["embedded"], report["concurrency"]) == ("local", "ProductE5", 2, 1)
    assert "cohereCalls" not in report and "refused" not in report
    assert report["modelVersion"] == "intfloat/multilingual-e5-small:catalog-text-v2"
    [(model, kwargs)] = _LocalEmbedder.built
    assert model == "intfloat/multilingual-e5-small"
    assert (kwargs["revision"], kwargs["dimension"], kwargs["batch_size"]) == ("614241f622f53c4eeff9890bdc4f31cfecc418b3", 384, 32)
    stored = {o["properties"]["productId"]: o for o in _Store.objects.values()}
    assert {o["properties"]["modelVersion"] for o in stored.values()} == {"intfloat/multilingual-e5-small:catalog-text-v2"}
    assert {len(o["vector"]) for o in stored.values()} == {384}


def test_job_refuses_to_write_e5_vectors_into_the_cohere_collection(local_job):
    _store_with("embed-multilingual-v3.0", 1024)   # WEAVIATE_COLLECTION=Product cũ còn trong .env
    before = dict(_Store.objects)
    for kw in ({}, {"dry_run": True}, {"allow_model_change": True}):
        report = embed_products.run(settings=_local_settings(collection="Product"), **kw)
        assert "1024 chiều" in report["refused"] and "EMBED_DIMENSION=384" in report["refused"]
    assert _Store.objects == before and _LocalEmbedder.built == [] and _Store.writers == set()


def test_job_refuses_other_model_with_same_dimension_unless_allowed(local_job):
    _store_with("other/e5-variant", 384)
    report = embed_products.run(settings=_local_settings())
    assert "model khác ['other/e5-variant']" in report["refused"] and _LocalEmbedder.built == []
    report = embed_products.run(settings=_local_settings(), allow_model_change=True)
    assert "refused" not in report and report["embedded"] == 2
    assert {o["properties"]["modelVersion"] for o in _Store.objects.values()} == {"intfloat/multilingual-e5-small:catalog-text-v2"}


def test_text_builder_change_alone_is_a_normal_reindex():
    meta = {"P1": VectorMetadata("u", "P1", "intfloat/multilingual-e5-small:catalog-text-v1", "h")}
    assert embed_products.collection_guard(meta, "intfloat/multilingual-e5-small:catalog-text-v2", 384, 384, False) is None


def test_main_passes_allow_model_change(monkeypatch):
    seen = {}
    monkeypatch.setattr(embed_products, "run", lambda **kw: seen.update(kw) or {"embedded": 0})
    assert embed_products.main(["--allow-model-change"]) == 0 and seen["allow_model_change"] is True
