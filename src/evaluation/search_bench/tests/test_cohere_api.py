from __future__ import annotations

import logging
from types import SimpleNamespace

import httpx
import numpy as np
import pytest
from cohere.core.api_error import ApiError

from evaluation.search_bench import costlog
from evaluation.search_bench.embed.base import EmbedBatchError, TokenLimitError
from evaluation.search_bench.embed.cache import CachedEmbedder, EmbeddingCache
from evaluation.search_bench.embed.cohere_api import CohereEmbedder, Pacer

SECRET = "co-SECRET-key-0123456789"


class FakeClient:
    """Thay cohere.ClientV2: ghi lại kwargs, trả vector theo số text; `script` = chuỗi lỗi/None cho từng lượt gọi."""

    def __init__(self, dim=1024, script=None, tokens_per_text=7):
        self.dim, self.script, self.calls, self.tpt = dim, list(script or []), [], tokens_per_text

    def embed(self, **kw):
        self.calls.append(kw)
        if self.script:
            err = self.script.pop(0)
            if err is not None:
                raise err
        n = len(kw["texts"])
        rng = np.random.default_rng(len(self.calls))
        vals = rng.standard_normal((n, self.dim))
        emb = SimpleNamespace(float_=vals.tolist() if "float" in kw["embedding_types"] else None,
                              int8=np.clip(vals * 40, -128, 127).astype(int).tolist() if "int8" in kw["embedding_types"] else None)
        return SimpleNamespace(embeddings=emb, meta=SimpleNamespace(billed_units=SimpleNamespace(input_tokens=n * self.tpt)))


def make(cfg, client, model="cohere-v3", sleeps=None, **kw):
    sleeps = sleeps if sleeps is not None else []
    return CohereEmbedder(model, cfg.model_cfg(model), cfg.embedding, api_key=SECRET, client=client,
                          sleep=sleeps.append, clock=lambda: 0.0, **kw)


def test_batches_of_96_and_params(cfg, home):
    client = FakeClient()
    e = make(cfg, client)
    v = e.embed([f"t{i}" for i in range(97)], "document")
    assert v.shape == (97, 1024) and np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)
    assert [len(c["texts"]) for c in client.calls] == [96, 1]
    c = client.calls[0]
    assert c["model"] == "embed-multilingual-v3.0" and c["input_type"] == "search_document"
    assert c["truncate"] == "NONE" and c["embedding_types"] == ["float"] and c["request_options"] == {"max_retries": 0}
    assert "output_dimension" not in c
    e.embed(["q"], "query")
    assert client.calls[-1]["input_type"] == "search_query"
    assert e.stats.n_calls == 3 and e.stats.n_tokens == 98 * 7


def test_v4_output_dimension(cfg, home):
    client = FakeClient()
    e = make(cfg, client, model="cohere-v4")
    e.embed(["x"], "document")
    assert client.calls[0]["output_dimension"] == 1024 and client.calls[0]["model"] == "embed-v4.0"
    assert e.name == "embed-v4.0@d1024"


def test_int8_is_cast_to_float(cfg, home):
    e = make(cfg, FakeClient(), embedding_type="int8")
    v = e.embed(["x", "y"], "document")
    assert v.dtype == np.float32 and e.name == "embed-multilingual-v3.0@int8"


def test_retry_429_with_backoff(cfg, home):
    sleeps: list[float] = []
    client = FakeClient(script=[ApiError(status_code=429, body="rate"), ApiError(status_code=503, body="busy"), None])
    e = make(cfg, client, sleeps=sleeps)
    e.embed(["x"], "document")
    assert len(client.calls) == 3 and sleeps == [1, 2]
    rows = costlog.read()
    assert [r.get("failed", False) for r in rows] == [True, True, False]       # mọi lượt gọi HTTP đều được ghi
    assert [r.get("status") for r in rows[:2]] == [429, 503] and rows[-1]["attempts"] == 3


def test_retry_after_header_wins(cfg, home):
    sleeps: list[float] = []
    client = FakeClient(script=[ApiError(status_code=429, headers={"Retry-After": "7"}, body="rate"), None])
    make(cfg, client, sleeps=sleeps).embed(["x"], "document")
    assert sleeps == [7.0]


def test_transport_error_retried(cfg, home):
    sleeps: list[float] = []
    client = FakeClient(script=[httpx.ConnectTimeout("t"), None])
    make(cfg, client, sleeps=sleeps).embed(["x"], "document")
    assert len(client.calls) == 2 and sleeps == [1]


def test_400_not_retried_names_batch_and_hides_key(cfg, home):
    client = FakeClient(script=[None, ApiError(status_code=400, body=f"too many tokens (key {SECRET})")])
    with pytest.raises(EmbedBatchError) as ei:
        make(cfg, client).embed([f"t{i}" for i in range(100)], "document")
    assert ei.value.positions == list(range(96, 100)) and ei.value.status == 400
    assert len(client.calls) == 2 and SECRET not in str(ei.value)


def test_retries_use_every_backoff_then_give_up(cfg, home):
    n = cfg.embedding.retry.max_attempts                       # = số lần thử LẠI sau lượt đầu
    sleeps: list[float] = []
    ok = FakeClient(script=[ApiError(status_code=429, body="rate")] * n + [None])
    make(cfg, ok, sleeps=sleeps).embed(["x"], "document")
    assert len(ok.calls) == n + 1 and sleeps == cfg.embedding.retry.backoff_s     # đủ 6 mức: 1…32 s
    bad = FakeClient(script=[ApiError(status_code=429, body="rate")] * (n + 1))
    with pytest.raises(EmbedBatchError, match="429"):
        make(cfg, bad).embed(["x"], "document")
    assert len(bad.calls) == n + 1
    assert sum(1 for r in costlog.read() if r.get("failed")) == 2 * n + 1


def test_cost_log_rows(cfg, home):
    make(cfg, FakeClient(tokens_per_text=10)).embed(["a", "b"], "document")
    row = costlog.read()[-1]
    assert row["endpoint"] == "embed" and row["input_type"] == "search_document" and row["n_texts"] == 2
    assert row["n_tokens"] == 20 and row["usd"] == pytest.approx(20 / 1e6 * 0.10)
    assert SECRET not in (home / "cache" / "cost.jsonl").read_text(encoding="utf-8")


def test_preflight_rejects_long_text_before_api(cfg, home):
    class Counter:
        def count(self, texts):
            return [600 if "dài" in t else 10 for t in texts]
    client = FakeClient()
    e = make(cfg, client, token_counter=Counter(), token_hard_max=512)
    with pytest.raises(TokenLimitError) as ei:
        e.embed(["ngắn", "rất dài"], "document")
    assert ei.value.over == [(1, 600)] and client.calls == []


def test_pacer_waits_for_window():
    now = [0.0]
    sleeps: list[float] = []

    def sleep(s):
        sleeps.append(s)
        now[0] += s
    p = Pacer(100, clock=lambda: now[0], sleep=sleep)
    assert p.wait(96) == 0.0
    now[0] = 10.0
    assert p.wait(96) == pytest.approx(50.0)     # chờ tới khi lô đầu ra khỏi cửa sổ 60 s
    assert sleeps == [pytest.approx(50.0)]


def test_key_not_logged(cfg, home, caplog):
    caplog.set_level(logging.DEBUG)
    client = FakeClient(script=[ApiError(status_code=429, body="rate"), None])
    make(cfg, client).embed(["x"], "document")
    assert SECRET not in caplog.text


def test_limit_96_is_one_call_then_zero(cfg, home):
    """Spec Part 3 Done: `--model cohere-v3 --limit 96` gọi đúng 1 lượt, chạy lần 2 gọi 0 lượt."""
    client = FakeClient()
    texts = [f"t{i}" for i in range(96)]
    e = CachedEmbedder(make(cfg, client), EmbeddingCache(home / "c.sqlite"))
    e.embed(texts, "document")
    assert len(client.calls) == 1
    e2 = CachedEmbedder(make(cfg, client), EmbeddingCache(home / "c.sqlite"))
    e2.embed(texts, "document")
    assert len(client.calls) == 1 and e2.n_cached == 96


def test_paid_batches_survive_later_failure(cfg, home):
    texts = [f"t{i}" for i in range(250)]
    bad = FakeClient(script=[None, None, ApiError(status_code=400, body="boom")])
    e = CachedEmbedder(make(cfg, bad), EmbeddingCache(home / "c.sqlite"))
    with pytest.raises(EmbedBatchError) as ei:
        e.embed(texts, "document")
    assert ei.value.positions == list(range(192, 250))
    assert e.cache.count() == 192                              # hai lô đầu đã trả tiền → đã ở cache
    good = FakeClient()
    e2 = CachedEmbedder(make(cfg, good), EmbeddingCache(home / "c.sqlite"))
    e2.embed(texts, "document")
    assert [len(c["texts"]) for c in good.calls] == [58] and e2.n_cached == 192


def test_error_positions_are_caller_positions(cfg, home):
    texts = [f"t{i}" for i in range(250)]
    warm = CachedEmbedder(make(cfg, FakeClient()), EmbeddingCache(home / "c.sqlite"))
    warm.embed(texts[:96], "document")                          # cache ấm 96 text đầu
    bad = FakeClient(script=[ApiError(status_code=400, body="boom")])
    e = CachedEmbedder(make(cfg, bad), EmbeddingCache(home / "c.sqlite"))
    with pytest.raises(EmbedBatchError) as ei:
        e.embed(texts, "document")
    assert ei.value.positions == list(range(96, 192))           # đúng lô thật sự gửi đi, không phải 0…95

    class Counter:
        def count(self, ts):
            return [600 if t == "t150" else 10 for t in ts]
    e3 = CachedEmbedder(make(cfg, FakeClient(), token_counter=Counter(), token_hard_max=512), EmbeddingCache(home / "c.sqlite"))
    with pytest.raises(TokenLimitError) as ti:
        e3.embed(["dup"] * 3 + texts, "document")
    assert ti.value.over == [(153, 600)]                        # vị trí của "t150" trong danh sách người gọi


def test_pacer_token_budget():
    now = [0.0]
    sleeps: list[float] = []

    def sleep(s):
        sleeps.append(s)
        now[0] += s
    p = Pacer(2000, 90_000, clock=lambda: now[0], sleep=sleep)
    for _ in range(4):
        assert p.wait(96, 20_000) == 0.0          # 80k token trong cửa sổ
    now[0] = 5.0
    assert p.wait(96, 20_000) == pytest.approx(55.0)   # 100k > 90k → chờ lô đầu hết hạn
    assert p.wait(96, 200_000) == pytest.approx(60.0)  # lô to hơn giới hạn: chờ cửa sổ trống rồi vẫn gửi, không kẹt


def test_embed_passes_token_counts_to_pacer(cfg, home):
    class Counter:
        def count(self, texts):
            return [100] * len(texts)
    e = make(cfg, FakeClient(), token_counter=Counter(), token_hard_max=512)
    seen = []
    real = e.pacer.wait
    e.pacer.wait = lambda n, t=0: seen.append((n, t)) or real(n, t)
    e.embed([f"t{i}" for i in range(100)], "document")
    assert seen == [(96, 9600), (4, 400)]
