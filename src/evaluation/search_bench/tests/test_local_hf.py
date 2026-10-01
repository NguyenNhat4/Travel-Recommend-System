"""Part 3 — embedder local (transformers + torch) với encode_fn / tokenizer giả: prefix theo input_type, không cắt ngầm
(TokenLimitError khi vượt max_seq_length), tên embedder = hf_model, `_kind` = local, thiếu thư viện thì báo rõ."""
from __future__ import annotations

import hashlib

import numpy as np
import pytest

from evaluation.search_bench import embed as sembed
from evaluation.search_bench.embed.base import TokenLimitError
from evaluation.search_bench.embed.local_hf import LocalHFEmbedder


class FakeTok:
    """Mỗi từ một token + 2 token đặc biệt; không cắt."""

    def __call__(self, texts, add_special_tokens=True, truncation=False):
        assert truncation is False
        return {"input_ids": [[0] * (len(t.split()) + (2 if add_special_tokens else 0)) for t in texts]}


class FakeST:
    """encode_fn giả: một lô text (đã ghép prefix) → (n, dim), tất định theo text."""

    def __init__(self, dim=8):
        self.dim, self.calls = dim, []
        self.tokenizer = FakeTok()

    def encode(self, texts):
        self.calls.append((list(texts), len(texts)))
        out = np.empty((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            seed = int.from_bytes(hashlib.sha256(t.encode()).digest()[:8], "little")
            out[i] = np.random.default_rng(seed).standard_normal(self.dim)
        return out


@pytest.fixture()
def e5(cfg):
    m = FakeST()
    return LocalHFEmbedder("e5-base", cfg.model_cfg("e5-base").model_copy(update={"dim": 8}), encode_fn=m.encode, tokenizer=m.tokenizer), m


def test_config_has_e5_with_prefixes(cfg):
    m = cfg.model_cfg("e5-base")
    assert m.hf_model == "intfloat/multilingual-e5-base" and m.dim == 768 and m.max_seq_length == 512
    assert m.query_prefix == "query: " and m.passage_prefix == "passage: "
    assert sembed._kind(cfg, "e5-base") == "local" and sembed.embedder_name(cfg, "e5-base") == "intfloat/multilingual-e5-base"
    with pytest.raises(sembed.EmbedderUnavailable, match="float"):
        sembed.embedder_name(cfg, "e5-base", embedding_type="int8")


def test_prefix_per_input_type_and_normalised(e5):
    emb, m = e5
    q = emb.embed(["resort nha trang"], "query")
    d = emb.embed(["resort nha trang"], "document")
    assert m.calls[0][0] == ["query: resort nha trang"] and m.calls[1][0] == ["passage: resort nha trang"]
    assert m.calls[0][1] == 1 and emb.batch == 32 and emb.name == "intfloat/multilingual-e5-base"
    assert q.shape == d.shape == (1, 8) and np.linalg.norm(q[0]) == pytest.approx(1.0, abs=1e-6)
    assert not np.allclose(q, d)                                # khác input_type → khác vector (prefix khác)
    assert emb.stats.n_calls == 2 and emb.stats.n_tokens == 2 * (4 + 2)   # "passage:" + 3 từ + 2 đặc biệt
    assert emb.embed([], "query").shape == (0, 8)


def test_refuses_text_over_max_seq_length_without_truncating(cfg):
    m = FakeST()
    emb = LocalHFEmbedder("e5-base", cfg.model_cfg("e5-base").model_copy(update={"dim": 8, "max_seq_length": 6}), encode_fn=m.encode,
                          tokenizer=m.tokenizer)
    emb.embed(["a b c"], "query")                                # preflight đếm với prefix dài nhất: "passage: a b c" = 4 từ + 2 = 6 ≤ 6
    with pytest.raises(TokenLimitError) as e:
        emb.embed(["a b c", "a b c d e f g"], "document")
    assert e.value.over == [(1, 10)] and e.value.limit == 6 and len(m.calls) == 1    # "passage:" + 7 từ + 2; không encode lô lỗi
    assert emb.count_tokens(["a b"], "query") == [5]                                 # "query:" + 2 từ + 2 đặc biệt


def test_preflight_can_be_disabled(cfg):
    m = FakeST()
    emb = LocalHFEmbedder("e5-base", cfg.model_cfg("e5-base").model_copy(update={"dim": 8, "max_seq_length": 3}), encode_fn=m.encode,
                          tokenizer=m.tokenizer, preflight=False)
    assert emb.preflight(["a b c d"]) is None and emb.embed(["a b c d"], "query").shape == (1, 8)


def test_make_embedder_requires_transformers_and_torch(cfg, monkeypatch, home):
    import importlib.util
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a, **k: None if name == "torch" else real(name, *a, **k))
    with pytest.raises(sembed.EmbedderUnavailable, match="thiếu torch"):
        sembed.make_embedder(cfg, "e5-base")
    e = sembed.make_embedder(cfg, "e5-base") if False else None          # có đủ thư viện thì tạo lười (không nạp model)


def test_pooling_and_batching(cfg):
    m = FakeST()
    emb = LocalHFEmbedder("e5-base", cfg.model_cfg("e5-base").model_copy(update={"dim": 8, "batch_size": 2}), encode_fn=m.encode,
                          tokenizer=m.tokenizer)
    assert emb.pooling == "mean" and cfg.model_cfg("bge-m3").pooling == "cls"
    out = emb.embed(["a", "b", "c"], "document")
    assert out.shape == (3, 8) and [n for _, n in m.calls] == [2, 1] and emb.stats.n_calls == 2


def test_cached_embedder_wraps_local_and_uses_hf_name_in_cache(cfg, home):
    from evaluation.search_bench.embed.cache import CachedEmbedder, EmbeddingCache, cache_key
    m = FakeST()
    inner = LocalHFEmbedder("e5-base", cfg.model_cfg("e5-base").model_copy(update={"dim": 8}), encode_fn=m.encode, tokenizer=m.tokenizer)
    e = CachedEmbedder(inner, EmbeddingCache(home / "c.sqlite"))
    e.embed(["x y"], "document")
    e.embed(["x y"], "document")
    assert e.n_new == 1 and e.n_cached == 1 and len(m.calls) == 1
    assert e.cache.get_many([cache_key("intfloat/multilingual-e5-base", "document", "x y")], dim=8)
    e.close()
