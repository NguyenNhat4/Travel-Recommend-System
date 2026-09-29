"""Part 3 — cache embedding sqlite: key = sha1(model|input_type|text) → vector float32.

`model` là `Embedder.name` (chuỗi model API kèm tuỳ chọn làm đổi vector), `input_type` là document | query. Mọi lệnh
embed đi qua `CachedEmbedder`; chạy lại cùng text không tốn lượt gọi. `no_cache=True` bỏ qua cả đọc lẫn ghi (đo RTT,
Part 9; kiểm tra cache_recheck, Part 12).
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .base import Embedder, EmbedBatchError, InputType, TokenLimitError, check_input_type

_CHUNK = 500


def cache_key(model: str, input_type: str, text: str) -> str:
    return hashlib.sha1(f"{model}|{input_type}|{text}".encode("utf-8")).hexdigest()


class EmbeddingCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._db = sqlite3.connect(str(path))
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS embeddings (key TEXT PRIMARY KEY, model TEXT NOT NULL, "
                         "input_type TEXT NOT NULL, dim INTEGER NOT NULL, vec BLOB NOT NULL, created_at TEXT NOT NULL)")
        self._db.commit()

    def get_many(self, keys: list[str], dim: int | None = None) -> dict[str, np.ndarray]:
        """Vector có trong cache; bản ghi hỏng hoặc khác `dim` mong đợi coi như chưa có (embed lại)."""
        out: dict[str, np.ndarray] = {}
        for i in range(0, len(keys), _CHUNK):
            chunk = keys[i:i + _CHUNK]
            q = f"SELECT key, dim, vec FROM embeddings WHERE key IN ({','.join('?' * len(chunk))})"
            for k, d, blob in self._db.execute(q, chunk):
                v = np.frombuffer(blob, dtype=np.float32)
                if v.shape[0] == d and (dim is None or d == dim):
                    out[k] = v
        return out

    def put_many(self, rows: list[tuple[str, str, str, np.ndarray]]) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._db.executemany(
            "INSERT OR REPLACE INTO embeddings (key, model, input_type, dim, vec, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            [(k, m, it, int(v.shape[0]), np.asarray(v, dtype=np.float32).tobytes(), now) for k, m, it, v in rows])
        self._db.commit()

    def count(self, model: str | None = None) -> int:
        if model is None:
            return self._db.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        return self._db.execute("SELECT COUNT(*) FROM embeddings WHERE model = ?", (model,)).fetchone()[0]

    def close(self) -> None:
        self._db.close()


class CachedEmbedder:
    """Bọc một Embedder: chỉ gọi embed cho text chưa có trong cache (khử trùng text trong cùng lượt), giữ thứ tự.

    Text thiếu được kiểm token trước (nếu inner có `preflight`) rồi gửi theo từng lô `inner.batch`, **ghi cache ngay sau
    mỗi lô** — lô sau lỗi thì các lô đã trả tiền vẫn còn, chạy lại chỉ embed phần còn thiếu. Lỗi của inner mang chỉ số
    trong danh sách con → đổi về chỉ số trong danh sách `texts` của người gọi trước khi ném ra.
    """

    def __init__(self, inner: Embedder, cache: EmbeddingCache, *, no_cache: bool = False):
        self.inner = inner
        self.cache = cache
        self.no_cache = no_cache
        self.name = inner.name
        self.dim = inner.dim
        self.n_new = 0
        self.n_cached = 0

    def embed(self, texts: list[str], input_type: InputType) -> np.ndarray:
        check_input_type(input_type)
        if self.no_cache:
            self.n_new += len(texts)
            return self.inner.embed(list(texts), input_type)
        keys = [cache_key(self.name, input_type, t) for t in texts]
        found = self.cache.get_many(list(dict.fromkeys(keys)), dim=self.dim)
        missing: dict[str, str] = {}
        first_pos: dict[str, int] = {}
        for i, (k, t) in enumerate(zip(keys, texts)):
            if k not in found and k not in missing:
                missing[k], first_pos[k] = t, i
        miss_keys = list(missing)
        miss_pos = [first_pos[k] for k in miss_keys]
        preflight = getattr(self.inner, "preflight", None)
        if preflight and miss_keys:
            try:
                preflight([missing[k] for k in miss_keys])
            except TokenLimitError as e:
                raise e.remap(miss_pos) from None
        step = getattr(self.inner, "batch", None) or max(len(miss_keys), 1)
        for s in range(0, len(miss_keys), step):
            chunk = miss_keys[s:s + step]
            try:
                vecs = self.inner.embed([missing[k] for k in chunk], input_type)
            except (EmbedBatchError, TokenLimitError) as e:
                raise e.remap(miss_pos[s:s + step]) from None
            self.cache.put_many([(k, self.name, input_type, v) for k, v in zip(chunk, vecs)])
            found.update(zip(chunk, vecs))
            self.n_new += len(chunk)
        self.n_cached += sum(1 for k in keys if k not in missing)
        return np.vstack([found[k] for k in keys]).astype(np.float32) if keys else np.zeros((0, self.dim), np.float32)

    @property
    def stats(self):
        return getattr(self.inner, "stats", None)

    def close(self) -> None:
        close = getattr(self.inner, "close", None)
        if close:
            close()
        self.cache.close()
