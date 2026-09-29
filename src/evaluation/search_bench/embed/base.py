"""Part 3 — giao diện Embedder: embed(texts, input_type) → float32 (n, dim), đã L2-normalise."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np

InputType = Literal["document", "query"]
INPUT_TYPES: tuple[InputType, ...] = ("document", "query")


class Embedder(Protocol):
    name: str      # chuỗi model dùng trong khoá cache — gồm mọi tuỳ chọn làm đổi vector (@int8, @d1024, @noit)
    dim: int

    def embed(self, texts: list[str], input_type: InputType) -> np.ndarray: ...


@dataclass
class EmbedStats:
    n_calls: int = 0
    n_tokens: int = 0
    usd: float = 0.0


class EmbedBatchError(RuntimeError):
    """Một lượt gọi embed thất bại. `positions` = chỉ số (trong danh sách text của người gọi) của các text trong lô lỗi."""

    def __init__(self, positions: list[int], status: int | None, message: str):
        span = f"[{positions[0]}…{positions[-1]}]" if positions else "[]"
        super().__init__(f"lô {len(positions)} text {span} lỗi{f' HTTP {status}' if status else ''}: {message}")
        self.positions, self.status, self.message = positions, status, message

    def remap(self, pos: list[int]) -> "EmbedBatchError":
        return EmbedBatchError([pos[i] for i in self.positions], self.status, self.message)


class TokenLimitError(ValueError):
    """Text vượt giới hạn token (truncate=NONE). `over` = [(chỉ số trong danh sách của người gọi, số token)]."""

    def __init__(self, over: list[tuple[int, int]], limit: int):
        super().__init__(f"{len(over)} text vượt {limit} token (truncate=NONE) — sửa text builder; (vị trí, token): {over[:5]}")
        self.over, self.limit = over, limit

    def remap(self, pos: list[int]) -> "TokenLimitError":
        return TokenLimitError([(pos[i], c) for i, c in self.over], self.limit)


def l2_normalize(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    n = np.linalg.norm(x, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return x / n


def check_input_type(input_type: str) -> InputType:
    if input_type not in INPUT_TYPES:
        raise ValueError(f"input_type phải là document | query, gặp {input_type!r}")
    return input_type  # type: ignore[return-value]
