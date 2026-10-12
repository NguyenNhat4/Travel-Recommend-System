import hashlib
import logging
from types import SimpleNamespace

import httpx
import numpy as np
import pytest

from src.backend.app.domain.catalog import Product
from src.backend.app.infrastructure.vectors.postgres_store import CatalogUnits
from src.backend.app.infrastructure.vectors.weaviate_store import (
    WeaviateClient,
    WeaviateVectorSearch,
    WeaviateVectorStore,
    normalize_weaviate_url,
)


def _catalog(ids=("P1",)) -> CatalogUnits:
    units = [
        Product(
            product_id=pid,
            name=f"Resort {pid}",
            taxonomy="hotel",
            destination="Nha Trang",
            description="",
            attributes={"level": "property"},
            unit_price=None,
        )
        for pid in ids
    ]
    return CatalogUnits(
        units=units,
        texts=[_text(pid) for pid in ids],
        taxonomy=np.array(["hotel"] * len(ids)),
        destination=np.array(["Nha Trang"] * len(ids)),
        available=np.array([True] * len(ids)),
        recommendable=np.array([True] * len(ids)),
        parent_of={},
    )


def _text(product_id: str) -> str:
    return f"Resort {product_id} tại Nha Trang."


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _Reader:
    def __init__(self, ids=("P1",)):
        self.ids = ids

    def load(self):
        return _catalog(self.ids)


class _Obj:
    def __init__(self, product_id, distance=None, vector=None, model_version="v", text_hash=None, score=None):
        self.uuid = WeaviateClient.object_uuid(product_id)
        self.properties = {"productId": product_id, "modelVersion": model_version,
                           "textHash": text_hash if text_hash is not None else _hash(_text(product_id))}
        self.metadata = SimpleNamespace(distance=distance, score=score)
        self.vector = {"default": vector} if vector is not None else {}


class _Collection:
    def __init__(self, stored=None):
        self.calls = []
        # product_id -> object; mặc định chỉ có P1 với vector đúng model và đúng text.
        self.stored = {"P1": _Obj("P1", vector=[1.0, 0.0])} if stored is None else stored
        self.query = SimpleNamespace(near_vector=self._near_vector, fetch_objects=self._fetch_objects, bm25=self._bm25)

    def _near_vector(self, **kwargs):
        self.calls.append(("near_vector", kwargs))
        return SimpleNamespace(objects=[_Obj("P1", 0.25, [1.0, 0.0]), _Obj("P2", 0.5, [0.0, 1.0])])

    def _bm25(self, **kwargs):
        self.calls.append(("bm25", kwargs))
        return SimpleNamespace(objects=[_Obj("P2", vector=[0.0, 1.0], score=3.5), _Obj("P1", vector=[1.0, 0.0], score=1.0)])

    def _fetch_objects(self, **kwargs):
        self.calls.append(("fetch_objects", kwargs))
        return SimpleNamespace(objects=list(self.stored.values()))


def _search(collection):
    client = SimpleNamespace(collections=SimpleNamespace(get=lambda name: collection), close=lambda: None)
    return WeaviateVectorSearch(client, collection="Product", dimension=2)


def _store(collection, ids=("P1",)):
    store = WeaviateVectorStore("unused", _search(collection), expected_model_version="v")
    store.reader = _Reader(ids)
    return store


def test_weaviate_store_returns_metadata_index_without_downloading_vectors():
    collection = _Collection()
    store = _store(collection)

    index, search = store.load()

    assert [p.product_id for p in index.units] == ["P1"] and index.model_version == "v"
    assert search is store.search
    assert [name for name, _ in collection.calls] == ["fetch_objects"]
    assert collection.calls[0][1]["include_vector"] is False  # chỉ đọc modelVersion/textHash, không tải vector
    assert store.sync == {"searchUnits": 1, "missing": 0, "staleText": 0}


def test_vectors_with_metadata_reads_vector_and_hashes_over_grpc():
    collection = _Collection()
    got = _search(collection).vectors_with_metadata(["P1", "P1"])
    vector, meta = got["P1"]
    assert vector.dtype == np.float32 and vector.tolist() == [1.0, 0.0]
    assert (meta.model_version, meta.text_hash) == ("v", _hash(_text("P1")))
    (name, kwargs), = collection.calls
    assert name == "fetch_objects" and kwargs["include_vector"] is True and kwargs["limit"] == 1
    assert kwargs["return_properties"] == ["productId", "modelVersion", "textHash"]


class _Expecting:
    """Search giả có `expect` (như PreloadedVectorSearch): ghi lại tập vector cần có của mỗi lần nạp."""

    def __init__(self, inner):
        self.inner, self.expected = inner, []

    def metadata(self, ids):
        return self.inner.metadata(ids)

    def expect(self, desired_ids, stored):
        self.expected.append((sorted(desired_ids), {pid: (m.model_version, m.text_hash) for pid, m in stored.items()}))


def test_load_tells_a_preloading_search_what_to_expect_only_after_validation():
    ok = WeaviateVectorStore("unused", _Expecting(_search(_Collection())), expected_model_version="v")
    ok.reader = _Reader(("P1", "P2"))
    ok.load()
    assert ok.search.expected == [(["P1", "P2"], {"P1": ("v", _hash(_text("P1")))})]

    rejected = WeaviateVectorStore("unused", _Expecting(_search(_Collection(stored={}))), expected_model_version="v")
    rejected.reader = _Reader()
    with pytest.raises(RuntimeError):
        rejected.load()
    assert rejected.search.expected == []   # lần nạp lỗi không đổi bảng vector đang phục vụ


def test_weaviate_store_rejects_collection_without_current_vectors():
    with pytest.raises(RuntimeError, match="chỉ có 0/1 search unit"):
        _store(_Collection(stored={})).load()
    # Vector của model/text builder khác không dùng được cho truy vấn của model hiện tại.
    with pytest.raises(RuntimeError, match="chỉ có 0/1 search unit"):
        _store(_Collection(stored={"P1": _Obj("P1", model_version="old")})).load()


def test_weaviate_store_keeps_serving_when_some_vectors_are_missing_or_stale(caplog):
    # Job cào vừa thêm P3 và đổi text P2 nhưng chưa index xong: vẫn phục vụ đủ ba unit với giá mới.
    collection = _Collection(stored={"P1": _Obj("P1"), "P2": _Obj("P2", text_hash="old-text")})
    store = _store(collection, ids=("P1", "P2", "P3"))

    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        index, _ = store.load()

    assert [p.product_id for p in index.units] == ["P1", "P2", "P3"]
    assert store.sync == {"searchUnits": 3, "missing": 1, "staleText": 1}
    assert "recsys.vectors.out_of_sync" in caplog.text


def test_weaviate_store_rejects_when_fewer_than_half_have_current_vectors():
    with pytest.raises(RuntimeError, match="chỉ có 1/3 search unit"):
        _store(_Collection(stored={"P1": _Obj("P1")}), ids=("P1", "P2", "P3")).load()


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


def test_bm25_folds_query_and_returns_lexical_hits_with_vectors():
    collection = _Collection()
    hits = _search(collection).bm25("Đà Nẵng resort", ["P1", "P2"], 7, with_vectors=True)

    assert [(h.product_id, h.score) for h in hits] == [("P2", 3.5), ("P1", 1.0)]
    assert hits[0].vector.tolist() == [0.0, 1.0]
    kwargs = collection.calls[0][1]
    assert kwargs["query"] == "da nang resort"  # fold như lúc index
    assert kwargs["query_properties"] == ["nameAscii^2", "searchTextAscii"]
    assert kwargs["limit"] == 7 and kwargs["include_vector"] is True and kwargs["filters"] is not None


def test_bm25_skips_call_for_empty_query_or_empty_allowlist():
    collection = _Collection()
    search = _search(collection)
    assert search.bm25("&&&", None, 3) == []  # fold ra rỗng → không hỏi Weaviate
    assert search.bm25("resort", [], 3) == []
    assert collection.calls == []
    search.bm25("resort", None, 3)
    assert collection.calls[0][1]["filters"] is None


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
    WeaviateClient("http://unused", client=raw, bm25_k1=1.5, bm25_b=0.6).ensure_collection()
    payload = __import__("json").loads(requests[-1].content)
    assert payload["vectorizer"] == "none"
    assert payload["vectorIndexConfig"]["distance"] == "cosine"
    assert payload["vectorIndexType"] == "hnsw"
    # nhánh BM25 của hybrid: hai property text đã fold, tokenization word; stopwords none để không mất âm tiết Việt
    searchable = {p["name"]: p["tokenization"] for p in payload["properties"] if p["indexSearchable"]}
    assert searchable == {"nameAscii": "word", "searchTextAscii": "word"}
    assert payload["invertedIndexConfig"] == {"bm25": {"k1": 1.5, "b": 0.6}, "stopwords": {"preset": "none"}}


def test_ensure_collection_adds_missing_lexical_properties_to_existing_class():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"vectorizer": "none", "vectorIndexConfig": {"distance": "cosine"},
                                             "properties": [{"name": "productId"}, {"name": "nameAscii"}]})
        return httpx.Response(200, json={})

    raw = httpx.Client(base_url="http://weaviate.test", transport=httpx.MockTransport(handler))
    WeaviateClient("http://unused", client=raw).ensure_collection()
    posts = [r for r in requests if r.method == "POST"]
    assert [r.url.path for r in posts] == ["/v1/schema/Product/properties"]
    assert __import__("json").loads(posts[0].content)["name"] == "searchTextAscii"


def test_rest_fetch_marks_objects_that_already_have_lexical_properties():
    page = {"objects": [
        {"id": "u1", "properties": {"productId": "P1", "modelVersion": "v", "textHash": "h", "searchTextAscii": "resort a"}},
        {"id": "u2", "properties": {"productId": "P2", "modelVersion": "v", "textHash": "h"}},
    ]}
    raw = httpx.Client(base_url="http://weaviate.test", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=page)))
    metadata, _ = WeaviateClient("http://unused", client=raw).fetch(include_vectors=False)
    assert metadata["P1"].lexical is True and metadata["P2"].lexical is False


def test_patch_properties_merges_without_vector():
    seen = []
    raw = httpx.Client(base_url="http://weaviate.test",
                       transport=httpx.MockTransport(lambda r: (seen.append(r), httpx.Response(204))[1]))
    WeaviateClient("http://unused", client=raw).patch_properties("u1", {"nameAscii": "resort a"})
    assert seen[0].method == "PATCH" and seen[0].url.path == "/v1/objects/Product/u1"
    body = __import__("json").loads(seen[0].content)
    assert body["properties"] == {"nameAscii": "resort a"} and "vector" not in body


def test_weaviate_client_creates_collection_with_configured_index_type():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(404) if request.method == "GET" else httpx.Response(200, json={})

    raw = httpx.Client(base_url="http://weaviate.test", transport=httpx.MockTransport(handler))
    WeaviateClient("http://unused", vector_index_type="hfresh", client=raw).ensure_collection()
    assert __import__("json").loads(requests[-1].content)["vectorIndexType"] == "hfresh"


def test_existing_collection_with_other_index_type_is_kept_with_a_warning(caplog):
    # Loại index chỉ áp dụng khi tạo mới: cluster Cloud đang chạy hfresh vẫn index được dù cấu hình để hnsw.
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        # Class đã có đủ property BM25 nên ensure_collection chỉ GET, không POST thêm property.
        return httpx.Response(200, json={"vectorizer": "none", "vectorIndexType": "hfresh",
                                         "vectorIndexConfig": {"distance": "cosine"},
                                         "properties": [{"name": "productId"}, {"name": "nameAscii"},
                                                        {"name": "searchTextAscii"}]})

    raw = httpx.Client(base_url="http://weaviate.test", transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        WeaviateClient("http://unused", vector_index_type="hnsw", client=raw).ensure_collection()
    assert [request.method for request in requests] == ["GET"]
    assert "actual=hfresh configured=hnsw" in caplog.text


def test_weaviate_url_without_scheme_is_treated_as_cloud_https():
    assert normalize_weaviate_url("abc.c0.weaviate.cloud/") == "https://abc.c0.weaviate.cloud"
    assert normalize_weaviate_url(" http://localhost:8080 ") == "http://localhost:8080"
    with pytest.raises(ValueError):
        normalize_weaviate_url("ftp://weaviate.test")
    with pytest.raises(ValueError):
        normalize_weaviate_url("")
