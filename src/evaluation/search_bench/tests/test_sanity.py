"""Part 12.2 — kiểm tra cứng (`sanity.py`): input_type, cache, count, gold append; embedder giả (`FakeEmbedder`,
`ignore_input_type=True` mô phỏng input_type không tới API — chính ca SANITY_FAIL của spec)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from evaluation.search_bench import sanity as S
from evaluation.search_bench.embed.cache import CachedEmbedder, EmbeddingCache
from evaluation.search_bench.embed.fake import FakeEmbedder
from evaluation.search_bench.gold_schema import read_gold_jsonl, write_gold_jsonl

FX = Path(__file__).parent / "fixtures" / "gold_small"


def test_input_type_check_catches_ignored_input_type():
    texts = ["resort nha trang", "vé máy bay đi Đà Nẵng", "khách sạn 5 sao"]
    ok = S.input_type_vectors_differ(FakeEmbedder(16), texts, min_gap=0.005, model="fake")
    bad = S.input_type_vectors_differ(FakeEmbedder(16, ignore_input_type=True), texts, min_gap=0.005, model="fake@noit")
    assert ok.ok is True and bad.ok is False and "cần > 0.005" in bad.detail
    assert S.input_type_vectors_differ(FakeEmbedder(16), [], min_gap=0.005, model="fake").ok is None


def test_cache_recheck_passes_on_consistent_cache_and_fails_on_stale(tmp_path):
    texts = [f"text {i}" for i in range(30)]
    cache = EmbeddingCache(tmp_path / "c.sqlite")
    cached = CachedEmbedder(FakeEmbedder(8), cache)
    cached.embed(texts, "query")
    fresh = CachedEmbedder(FakeEmbedder(8), EmbeddingCache(tmp_path / "other.sqlite"), no_cache=True)
    good = S.cache_recheck(cached, fresh, texts, n=20, seed=42, model="fake")
    assert good.ok is True and "20 text" in good.detail
    # cache "cũ": làm bẩn vector trong cache của một text được chọn
    from evaluation.search_bench.embed.cache import cache_key
    import random
    victim = random.Random(42).sample(texts, 20)[0]
    cache.put_many([(cache_key("fake", "query", victim), "fake", "query", -np.ones(8, dtype=np.float32) / np.sqrt(8))])
    bad = S.cache_recheck(cached, fresh, texts, n=20, seed=42, model="fake")
    assert bad.ok is False
    cached.close()
    fresh.close()


def test_collection_counts_and_summary():
    ok = S.collection_counts({"A": 26, "B": 26}, 26)
    bad = S.collection_counts({"A": 26, "B": 25}, 26)
    assert ok.ok and not bad.ok and "B=25" in bad.detail
    assert S.summary([ok, S.Check("x", None, "bỏ qua")]) == ("PASS", [])
    state, failed = S.summary([ok, bad])
    assert state == "SANITY_FAIL" and failed == [bad]


def test_gold_append_ok_skips_without_tags_and_checks_with_tag(tmp_path, monkeypatch):
    from evaluation.search_bench import holes as H
    g = tmp_path / "gold.jsonl"
    g.write_bytes((FX / "gold_expected.jsonl").read_bytes())
    monkeypatch.setattr(H, "list_gold_tags", lambda: [])
    assert S.gold_append_ok(g).ok is None
    monkeypatch.setattr(H, "list_gold_tags", lambda: ["gold_v1"])
    monkeypatch.setattr(H, "gold_at", lambda ref, path=None: read_gold_jsonl(FX / "gold_expected.jsonl"))
    assert S.gold_append_ok(g).ok is True
    recs = read_gold_jsonl(g)
    write_gold_jsonl([r.model_copy(update={"judgments": {**r.judgments, list(r.judgments)[0]: 0}}) if r.qid == "c9001" else r
                      for r in recs], g)
    bad = S.gold_append_ok(g)
    assert bad.ok is False and "vi phạm" in bad.detail
