import httpx
import numpy as np
import pytest

from src.backend.app.infrastructure.embeddings.cohere_embedder import CohereEmbedder


def test_cohere_uses_document_and_query_input_types_and_normalizes():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content)
        seen.append(payload)
        vectors = [[3.0, 4.0] + [0.0] * 1022 for _ in payload["texts"]]
        return httpx.Response(200, json={"embeddings": {"float": vectors}})

    client = httpx.Client(base_url="https://cohere.test", transport=httpx.MockTransport(handler))
    embedder = CohereEmbedder("test-key", client=client)

    docs = embedder.embed_docs([f"doc {i}" for i in range(97)])
    query = embedder.embed_query("nha trang")

    assert docs.shape == (97, 1024)
    assert np.allclose(np.linalg.norm(docs, axis=1), 1.0)
    assert np.isclose(np.linalg.norm(query), 1.0)
    assert [call["input_type"] for call in seen] == ["search_document", "search_document", "search_query"]
    assert [len(call["texts"]) for call in seen] == [96, 1, 1]
    assert all(call["model"] == "embed-multilingual-v3.0" for call in seen)


def test_cohere_rejects_wrong_dimension():
    client = httpx.Client(
        base_url="https://cohere.test",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"embeddings": {"float": [[1.0, 2.0]]}})),
    )
    with pytest.raises(RuntimeError, match="expected .*1024"):
        CohereEmbedder("test-key", client=client).embed_query("query")
