"""Adapter embedding local e5-small (FR-SRC-02, chốt 06/10): tiền tố query/passage, mean pooling theo mask, L2-normalize,
float32, chia lô — không tải model, không cần torch (tiêm `forward` giả)."""
import threading

import numpy as np
import pytest

from src.backend.app.infrastructure.embeddings import local_e5_embedder as mod
from src.backend.app.infrastructure.embeddings.local_e5_embedder import LocalE5Embedder, l2_normalize, mean_pool

DIM = 4
REV = "614241f622f53c4eeff9890bdc4f31cfecc418b3"


class FakeForward:
    """texts → (hidden (n, L, DIM), mask (n, L)). Text dài k ký tự (sau tiền tố) có k token; padding tới text dài nhất lô.

    Token đệm mang giá trị rác lớn để test bắt được pooling quên mask."""

    def __init__(self):
        self.batches: list[list[str]] = []

    def __call__(self, texts):
        self.batches.append(list(texts))
        n, length = len(texts), max(len(t) for t in texts)
        hidden = np.full((n, length, DIM), 1000.0, dtype=np.float32)
        mask = np.zeros((n, length), dtype=np.int64)
        for i, t in enumerate(texts):
            for j, ch in enumerate(t):
                hidden[i, j] = [ord(ch) % 7 + 1, j + 1, 1.0, float(len(t))]
            mask[i, : len(t)] = 1
        return hidden, mask


def _expected(text: str) -> np.ndarray:
    rows = np.array([[ord(ch) % 7 + 1, j + 1, 1.0, float(len(text))] for j, ch in enumerate(text)], dtype=np.float32)
    v = rows.mean(axis=0)
    return v / np.linalg.norm(v)


def _embedder(**kw) -> tuple[LocalE5Embedder, FakeForward]:
    fwd = FakeForward()
    return LocalE5Embedder("intfloat/multilingual-e5-small", revision=REV, dimension=DIM, forward=fwd, **kw), fwd


def test_query_and_passage_prefixes_are_added_by_the_adapter():
    emb, fwd = _embedder()
    emb.embed_query("resort Nha Trang")
    emb.embed_docs(["Vinpearl Resort", "Vé máy bay"])
    emb.embed_queries(["a", "b"])
    assert fwd.batches == [["query: resort Nha Trang"], ["passage: Vinpearl Resort", "passage: Vé máy bay"],
                           ["query: a", "query: b"]]


def test_mean_pooling_ignores_padding_and_output_is_l2_normalized_float32():
    emb, _ = _embedder()
    out = emb.embed_docs(["ab", "a much longer passage"])  # câu ngắn có nhiều token đệm "rác" = 1000
    assert out.dtype == np.float32 and out.shape == (2, DIM)
    np.testing.assert_allclose(np.linalg.norm(out, axis=1), 1.0, rtol=1e-6)
    np.testing.assert_allclose(out[0], _expected("passage: ab"), rtol=1e-6)
    np.testing.assert_allclose(out[1], _expected("passage: a much longer passage"), rtol=1e-6)
    q = emb.embed_query("ab")
    assert q.shape == (DIM,) and q.dtype == np.float32
    np.testing.assert_allclose(q, _expected("query: ab"), rtol=1e-6)


def test_docs_are_split_into_batches_and_keep_order():
    emb, fwd = _embedder(batch_size=3)
    texts = [f"t{i}" for i in range(8)]
    out = emb.embed_docs(texts)
    assert [len(b) for b in fwd.batches] == [3, 3, 2]
    for i, t in enumerate(texts):
        np.testing.assert_allclose(out[i], _expected("passage: " + t), rtol=1e-6)


def test_batching_does_not_change_vectors():
    texts = ["khách sạn", "resort biển có hồ bơi", "vé máy bay Hà Nội Phú Quốc", "x"]
    one, _ = _embedder(batch_size=1)
    many, _ = _embedder(batch_size=32)
    np.testing.assert_allclose(one.embed_docs(texts), many.embed_docs(texts), rtol=1e-6)


def test_empty_input_and_dimension_mismatch():
    emb, fwd = _embedder()
    assert emb.embed_docs([]).shape == (0, DIM) and fwd.batches == []
    wrong = LocalE5Embedder("m", revision=REV, dimension=DIM + 1, forward=FakeForward())
    with pytest.raises(RuntimeError, match="EMBED_DIMENSION"):
        wrong.embed_query("x")


def test_mean_pool_and_l2_normalize_match_the_bench_formulas():
    hidden = np.array([[[1, 2], [3, 4], [100, 100]]], dtype=np.float32)
    mask = np.array([[1, 1, 0]])
    np.testing.assert_allclose(mean_pool(hidden, mask), [[2.0, 3.0]])
    np.testing.assert_allclose(mean_pool(hidden, np.zeros((1, 3))), [[0.0, 0.0]])   # clamp 1e-9: không chia cho 0
    np.testing.assert_allclose(l2_normalize(np.array([[3.0, 4.0], [0.0, 0.0]])), [[0.6, 0.8], [0.0, 0.0]])


def test_revision_is_required():
    with pytest.raises(ValueError, match="EMBED_MODEL_REVISION"):
        LocalE5Embedder("intfloat/multilingual-e5-small", revision="")


def test_warmup_embeds_a_probe_query_without_loading_a_real_model():
    emb, fwd = _embedder()
    assert emb.warmup() >= 0
    assert fwd.batches == [["query: " + mod.PROBE_QUERY]]


def test_model_is_loaded_lazily_once_with_pinned_revision(monkeypatch):
    """`_load` gọi `from_pretrained` đúng một lần, với revision ghim và safetensors — kể cả khi nhiều luồng gọi cùng lúc."""
    calls = []

    class FakeTokenizer:
        pass

    class FakeModel:
        def eval(self):
            return self

        def to(self, device):
            calls.append(("to", device))
            return self

    class AutoTokenizer:
        @staticmethod
        def from_pretrained(name, **kw):
            calls.append(("tokenizer", name, kw["revision"]))
            return FakeTokenizer()

    class AutoModel:
        @staticmethod
        def from_pretrained(name, **kw):
            calls.append(("model", name, kw["revision"], kw["use_safetensors"]))
            return FakeModel()

    import sys
    import types

    fake_torch = types.SimpleNamespace(set_num_threads=lambda n: calls.append(("threads", n)), get_num_threads=lambda: 2)
    fake_transformers = types.SimpleNamespace(AutoTokenizer=AutoTokenizer, AutoModel=AutoModel)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    emb = LocalE5Embedder("intfloat/multilingual-e5-small", revision=REV, threads=3)
    threads = [threading.Thread(target=emb._load) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert calls == [("threads", 3), ("tokenizer", "intfloat/multilingual-e5-small", REV),
                     ("model", "intfloat/multilingual-e5-small", REV, True), ("to", "cpu")]


def test_missing_torch_gives_an_actionable_error(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "torch", None)   # import torch → ImportError
    emb = LocalE5Embedder("intfloat/multilingual-e5-small", revision=REV)
    with pytest.raises(RuntimeError, match="requirements-embed.txt"):
        emb.embed_query("x")
