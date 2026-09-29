"""Part 3 — embedder giả: vector = RNG chuẩn gieo bằng sha256(input_type + text), đã normalise.

Cùng (input_type, text) → cùng vector; khác input_type → khác vector (để kiểm tra input_type của Part 12 chạy được).
`ignore_input_type=True` giả lập lỗi input_type không tới API — tên model thành `fake@noit` để không lẫn cache.
Chỉ để chạy thử khung, không dùng số đo từ vector giả để kết luận.
"""
from __future__ import annotations

import hashlib

import numpy as np

from .base import EmbedStats, InputType, check_input_type, l2_normalize


class FakeEmbedder:
    def __init__(self, dim: int, *, ignore_input_type: bool = False):
        self.dim = dim
        self.ignore_input_type = ignore_input_type
        self.name = "fake@noit" if ignore_input_type else "fake"
        self.stats = EmbedStats()

    def embed(self, texts: list[str], input_type: InputType) -> np.ndarray:
        check_input_type(input_type)
        salt = "" if self.ignore_input_type else input_type
        out = np.empty((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            seed = int.from_bytes(hashlib.sha256(f"{salt}\x1f{t}".encode("utf-8")).digest()[:8], "little")
            out[i] = np.random.default_rng(seed).standard_normal(self.dim)
        self.stats.n_calls += 1 if texts else 0
        return l2_normalize(out)
