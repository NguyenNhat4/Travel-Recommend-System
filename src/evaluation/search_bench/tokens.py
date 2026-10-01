"""Part 2 — đếm token Cohere OFFLINE.

Tokenizer của model tải MỘT lần (`models.get(model).tokenizer_url` — một lượt gọi API, ghi cost.jsonl) vào
`cache/tokenizers/<model>.json`, sau đó đếm bằng thư viện `tokenizers`, tính cả token đặc biệt. Không bao giờ fallback
sang `co.tokenize` qua API: key trial chỉ 1.000 lượt/tháng, 2.897 text sẽ đốt sạch quota.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import numpy as np

from . import costlog, paths


class TokenizerUnavailable(RuntimeError):
    pass


def tokenizer_path(api_model: str) -> Path:
    return paths.cache_dir() / "tokenizers" / f"{api_model}.json"


def ensure_tokenizer(api_model: str | None, api_key: str | None) -> Path:
    if not api_model:
        raise TokenizerUnavailable("model không phải Cohere (không có api_model) — tokenizer offline chỉ có cho model Cohere")
    p = tokenizer_path(api_model)
    if p.exists():
        return p
    if not api_key:
        raise TokenizerUnavailable(f"chưa có {p} và không có COHERE_API_KEY để lấy tokenizer_url")
    import cohere
    from cohere.core.api_error import ApiError
    try:
        with httpx.Client(timeout=60) as http:
            co = cohere.ClientV2(api_key=api_key, httpx_client=http)
            try:
                url = co.models.get(api_model, request_options={"max_retries": 0}).tokenizer_url
            finally:
                costlog.append(endpoint="models.get", model=api_model, input_type=None, n_texts=0, n_tokens=0, usd=0.0)
            if not url:
                raise TokenizerUnavailable(f"Cohere không trả tokenizer_url cho {api_model}")
            r = http.get(url)
            r.raise_for_status()
    except (ApiError, httpx.HTTPError) as e:
        raise TokenizerUnavailable(f"không lấy được tokenizer {api_model}: {type(e).__name__} "
                                   f"{str(getattr(e, 'status_code', '') or '')}".strip()) from None
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_bytes(r.content)
    tmp.replace(p)
    return p


class TokenCounter:
    def __init__(self, tokenizer_file: Path):
        from tokenizers import Tokenizer
        self._tok = Tokenizer.from_file(str(tokenizer_file))
        # file tokenizer của Cohere bật padding BatchLongest: encode_batch sẽ đệm mọi text tới text dài nhất lô
        self._tok.no_padding()
        self._tok.no_truncation()

    def count(self, texts: list[str]) -> list[int]:
        return [len(e.ids) for e in self._tok.encode_batch(texts, add_special_tokens=True)]


def token_stats(counts: list[int]) -> dict:
    a = np.asarray(counts, dtype=np.int64)
    if not len(a):
        return {"n": 0, "p50": 0, "p90": 0, "p99": 0, "max": 0}
    return {"n": int(len(a)), "p50": float(np.percentile(a, 50)), "p90": float(np.percentile(a, 90)),
            "p99": float(np.percentile(a, 99)), "max": int(a.max())}


def gate(stats: dict, p99_max: int, hard_max: int) -> list[str]:
    """Lý do trượt gate (spec Part 2: p99 ≤ token_p99_max và max < token_hard_max); rỗng = qua."""
    why = []
    if stats["p99"] > p99_max:
        why.append(f"p99 {stats['p99']:.0f} > {p99_max}")
    if stats["max"] >= hard_max:
        why.append(f"max {stats['max']} ≥ {hard_max}")
    return why
