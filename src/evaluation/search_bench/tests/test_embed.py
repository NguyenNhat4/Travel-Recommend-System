from __future__ import annotations

import hashlib

import numpy as np
import pytest

from evaluation.search_bench import embed as sembed
from evaluation.search_bench.embed.cache import CachedEmbedder, EmbeddingCache, cache_key
from evaluation.search_bench.embed.fake import FakeEmbedder


class Counting:
    """Embedder giả đếm số lần / số text được gọi thật."""

    def __init__(self, dim=8):
        self.dim, self.name, self.calls, self.texts = dim, "count-model", 0, []

    def embed(self, texts, input_type):
        self.calls += 1
        self.texts += list(texts)
        return FakeEmbedder(self.dim).embed(texts, input_type)


def test_cache_key_formula():
    assert cache_key("m", "document", "xin chào") == hashlib.sha1("m|document|xin chào".encode()).hexdigest()


def test_second_run_makes_zero_calls(tmp_path):
    inner = Counting()
    e = CachedEmbedder(inner, EmbeddingCache(tmp_path / "c.sqlite"))
    a = e.embed(["a", "b", "a"], "document")          # "a" trùng trong lượt → embed một lần
    assert inner.calls == 1 and inner.texts == ["a", "b"] and e.n_new == 2 and e.n_cached == 0
    b = e.embed(["a", "b"], "document")
    assert inner.calls == 1 and e.n_cached == 2
    np.testing.assert_allclose(a[[0, 1]], b)
    np.testing.assert_allclose(a[0], a[2])
    e.close()
    e2 = CachedEmbedder(Counting(), EmbeddingCache(tmp_path / "c.sqlite"))   # cache bền qua lần chạy sau
    e2.embed(["a", "b"], "document")
    assert e2.inner.calls == 0 and e2.n_cached == 2


def test_input_type_separates_cache(tmp_path):
    inner = Counting()
    e = CachedEmbedder(inner, EmbeddingCache(tmp_path / "c.sqlite"))
    d = e.embed(["resort"], "document")
    q = e.embed(["resort"], "query")
    assert inner.calls == 2 and not np.allclose(d, q)


def test_no_cache_bypasses_read_and_write(tmp_path):
    inner = Counting()
    cache = EmbeddingCache(tmp_path / "c.sqlite")
    e = CachedEmbedder(inner, cache, no_cache=True)
    e.embed(["x"], "document")
    e.embed(["x"], "document")
    assert inner.calls == 2 and cache.count() == 0


def test_fake_embedder():
    f = FakeEmbedder(16)
    v1, v2 = f.embed(["a"], "document"), f.embed(["a"], "document")
    np.testing.assert_array_equal(v1, v2)
    assert abs(float(np.linalg.norm(v1[0])) - 1.0) < 1e-5
    assert not np.allclose(f.embed(["a"], "query"), v1)
    noit = FakeEmbedder(16, ignore_input_type=True)
    np.testing.assert_array_equal(noit.embed(["a"], "query"), noit.embed(["a"], "document"))
    assert noit.name == "fake@noit" and f.name == "fake"
    with pytest.raises(ValueError):
        f.embed(["a"], "search_query")


def test_make_embedder_routes(cfg, home, monkeypatch):
    e = sembed.make_embedder(cfg, "fake")
    assert e.name == "fake" and e.dim == 1024
    e.close()
    local = sembed.make_embedder(cfg, "bge-m3")                 # model local: tạo lười, chưa nạp torch model
    assert local.name == "BAAI/bge-m3" and local.dim == 1024
    local.close()
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    with pytest.raises(sembed.EmbedderUnavailable, match="COHERE_API_KEY"):
        sembed.make_embedder(cfg, "cohere-v3")
    bedrock = cfg.model_copy(update={"embedding": cfg.embedding.model_copy(update={"provider": "bedrock"})})
    with pytest.raises(sembed.EmbedderUnavailable, match="bedrock"):
        sembed.make_embedder(bedrock, "cohere-v3")


def test_cached_vector_of_other_dim_is_a_miss(tmp_path):
    cache = EmbeddingCache(tmp_path / "c.sqlite")
    small = CachedEmbedder(FakeEmbedder(8), cache)
    small.embed(["a"], "document")
    big_inner = FakeEmbedder(16)
    big = CachedEmbedder(big_inner, cache)
    v = big.embed(["a"], "document")
    assert v.shape == (1, 16) and big.n_new == 1


def test_embedder_name_without_api(cfg, monkeypatch):
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    assert sembed.embedder_name(cfg, "cohere-v3") == "embed-multilingual-v3.0"
    assert sembed.embedder_name(cfg, "cohere-v4") == "embed-v4.0@d1024"
    assert sembed.embedder_name(cfg, "cohere-v3", embedding_type="int8") == "embed-multilingual-v3.0@int8"
    assert sembed.embedder_name(cfg, "fake", fake_ignore_input_type=True) == "fake@noit"
    with pytest.raises(sembed.EmbedderUnavailable, match="không có trong config"):
        sembed.embedder_name(cfg, "nope")


def test_vector_file_tag():
    from evaluation.search_bench import vectors
    assert vectors.tag_of("fake@noit") == "__noit"
    assert vectors.tag_of("embed-v4.0@d1024") == ""
    assert vectors.tag_of("embed-multilingual-v3.0@int8") == "__int8"
