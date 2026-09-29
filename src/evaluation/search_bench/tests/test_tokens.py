from __future__ import annotations

import pytest

from evaluation.search_bench import tokens


@pytest.fixture()
def tiny_tokenizer(tmp_path):
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    from tokenizers.processors import TemplateProcessing
    vocab = {"[UNK]": 0, "[CLS]": 1, "[SEP]": 2, "xin": 3, "chào": 4}
    tok = Tokenizer(WordLevel(vocab, unk_token="[UNK]"))
    tok.pre_tokenizer = Whitespace()
    tok.post_processor = TemplateProcessing(single="[CLS] $A [SEP]", special_tokens=[("[CLS]", 1), ("[SEP]", 2)])
    p = tmp_path / "tok.json"
    tok.save(str(p))
    return p


def test_counts_include_special_tokens(tiny_tokenizer):
    assert tokens.TokenCounter(tiny_tokenizer).count(["xin chào", "xin chào bạn"]) == [4, 5]


def test_padding_in_tokenizer_file_is_ignored(tiny_tokenizer, tmp_path):
    """File tokenizer của Cohere bật padding BatchLongest — không được làm mọi text dài bằng text dài nhất lô."""
    from tokenizers import Tokenizer
    tok = Tokenizer.from_file(str(tiny_tokenizer))
    tok.enable_padding(pad_id=0, pad_token="[UNK]")
    tok.enable_truncation(max_length=3)
    p = tmp_path / "padded.json"
    tok.save(str(p))
    assert tokens.TokenCounter(p).count(["xin", "xin chào xin chào"]) == [3, 6]


def test_cached_tokenizer_needs_no_network(home, monkeypatch, tiny_tokenizer):
    p = tokens.tokenizer_path("embed-multilingual-v3.0")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(tiny_tokenizer.read_bytes())
    import cohere
    monkeypatch.setattr(cohere, "ClientV2", lambda **kw: pytest.fail("không được gọi API khi đã có tokenizer"))
    assert tokens.ensure_tokenizer("embed-multilingual-v3.0", None) == p


def test_no_key_no_file(home):
    with pytest.raises(tokens.TokenizerUnavailable):
        tokens.ensure_tokenizer("embed-multilingual-v3.0", None)


def test_stats_and_gate():
    st = tokens.token_stats(list(range(1, 101)))
    assert st["max"] == 100 and st["p50"] == pytest.approx(50.5)
    assert tokens.gate(st, 450, 512) == []
    assert tokens.gate({"p99": 460.0, "max": 520}, 450, 512) == ["p99 460 > 450", "max 520 ≥ 512"]
    assert tokens.token_stats([])["n"] == 0


def test_non_cohere_model_never_calls_api(home, monkeypatch):
    import cohere
    monkeypatch.setattr(cohere, "ClientV2", lambda **kw: pytest.fail("không được gọi API cho model không phải Cohere"))
    with pytest.raises(tokens.TokenizerUnavailable, match="không phải Cohere"):
        tokens.ensure_tokenizer(None, "some-key")
