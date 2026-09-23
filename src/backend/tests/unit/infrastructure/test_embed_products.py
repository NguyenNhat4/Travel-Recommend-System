import json

import httpx
import numpy as np
import pytest

from src.backend.app.infrastructure.embeddings.cohere_embedder import MAX_TEXTS_PER_CALL, CohereEmbedder
from src.backend.app.infrastructure.vectors.embed_products import plan, text_hash
from src.backend.app.infrastructure.vectors.weaviate_store import StoredVector, WeaviateVectorStore, normalise_url

MODEL = "embed-multilingual-v3.0+text-v1"


def http(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# --- CohereEmbedder -------------------------------------------------------------------------------

def test_cohere_docs_use_search_document_and_batch_by_96():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, json={"embeddings": {"float": [[3.0, 4.0]] * len(body["texts"])}})

    vectors = CohereEmbedder("key", client=http(handler)).embed_docs([f"t{i}" for i in range(MAX_TEXTS_PER_CALL + 4)])

    assert [len(c["texts"]) for c in calls] == [MAX_TEXTS_PER_CALL, 4]
    assert {c["input_type"] for c in calls} == {"search_document"}
    assert vectors.shape == (MAX_TEXTS_PER_CALL + 4, 2)
    np.testing.assert_allclose(vectors[0], [0.6, 0.8])  # đã L2-normalise


def test_cohere_query_uses_search_query():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"embeddings": {"float": [[1.0, 0.0]]}})

    CohereEmbedder("key", client=http(handler)).embed_query("biển Nha Trang")
    assert seen["input_type"] == "search_query"


def test_cohere_retries_on_rate_limit(monkeypatch):
    monkeypatch.setattr("src.backend.app.infrastructure.embeddings.cohere_embedder.time.sleep", lambda _: None)
    replies = iter([httpx.Response(429, headers={"Retry-After": "1"}),
                    httpx.Response(200, json={"embeddings": {"float": [[1.0]]}})])
    vectors = CohereEmbedder("key", client=http(lambda request: next(replies))).embed_docs(["a"])
    assert vectors.shape == (1, 1)


def test_cohere_requires_api_key():
    with pytest.raises(RuntimeError, match="COHERE_API_KEY"):
        CohereEmbedder("")


# --- WeaviateVectorStore --------------------------------------------------------------------------

def test_normalise_url_adds_https_for_cloud_hostname():
    assert normalise_url('"abc.weaviate.cloud"') == "https://abc.weaviate.cloud"
    assert normalise_url("http://localhost:8080/") == "http://localhost:8080"


def test_ensure_collection_creates_bring_your_own_vector_schema():
    created = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(404)
        created.append(json.loads(request.content))
        return httpx.Response(200, json={})

    store = WeaviateVectorStore("http://w", "secret", client=http(handler))
    assert store.ensure_collection() is True
    schema = created[0]
    assert schema["class"] == "Product"
    assert schema["vectorizer"] == "none"
    assert schema["vectorIndexConfig"]["distance"] == "cosine"
    assert {p["name"] for p in schema["properties"]} == {"productId", "modelVersion", "textHash"}


def test_stored_pages_through_cursor():
    pages = {
        None: [{"id": f"id{i}", "properties": {"productId": f"p{i}", "modelVersion": MODEL, "textHash": "h"}}
               for i in range(500)],
        "id499": [{"id": "last", "properties": {"productId": "pz", "modelVersion": MODEL, "textHash": "h"}}],
    }

    def handler(request):
        assert request.headers["Authorization"] == "Bearer secret"
        return httpx.Response(200, json={"objects": pages[request.url.params.get("after")]})

    stored = WeaviateVectorStore("http://w", "secret", client=http(handler)).stored()
    assert len(stored) == 501
    assert stored["pz"].object_id == "last"


def test_upsert_raises_when_weaviate_rejects_an_object():
    def handler(request):
        return httpx.Response(200, json=[{"result": {"errors": {"error": [{"message": "bad vector"}]}}}])

    store = WeaviateVectorStore("http://w", client=http(handler))
    with pytest.raises(RuntimeError, match="từ chối 1 object"):
        store.upsert([{"productId": "p", "modelVersion": MODEL, "textHash": "h", "vector": [0.1]}])


# --- plan ------------------------------------------------------------------------------------------

def test_plan_embeds_only_changed_and_new_and_deletes_orphans():
    stored = {
        "same": StoredVector("o1", MODEL, text_hash("A")),
        "text-changed": StoredVector("o2", MODEL, text_hash("old")),
        "model-changed": StoredVector("o3", "other-model", text_hash("C")),
        "gone": StoredVector("o4", MODEL, text_hash("D")),
    }
    items = [("same", "A"), ("text-changed", "B"), ("model-changed", "C"), ("new", "E")]

    todo, orphans = plan(items, stored, MODEL)

    assert todo == [("text-changed", "B", "o2"), ("model-changed", "C", "o3"), ("new", "E", None)]
    assert orphans == ["o4"]
