"""Cache vector truy vấn trong bộ nhớ (NFR-PERF-03: Cohere vượt ngân sách thì cache vector của truy vấn lặp lại).

`QueryEmbeddingCache` là LRU thread-safe có single-flight: nhiều request cùng câu chỉ một luồng gọi Cohere, các luồng còn
lại chờ (`threading.Event`) rồi dùng chung vector; leader lỗi thì follower tự gọi, khoá không bao giờ kẹt. Route `/search`
là `def` đồng bộ chạy trong threadpool và agent inprocess dùng `ThreadPoolExecutor`, nên khoá là `threading.Lock`, không
asyncio. Vector lưu float32 chỉ đọc (`writeable=False`) để không ai sửa nhầm bản trong cache.

`CachingQueryEmbedder` bọc một `EmbedderPort` (client Cohere dùng chung qua các lần nạp lại catalog, nên cache sống theo):
`embed_query_status` trả thêm "hit" / "miss" cho `diagnostics.embedCache` (contract 1.12.0), `embed_queries` nạp cả lô câu
còn thiếu (prewarm). Khoá = `(tên model, "search_query", câu)` với câu **đúng chuỗi gửi Cohere** (sau chuẩn hoá và gộp
khoảng trắng ở `SearchProducts.query_text`); không fold hoa/thường/dấu để không gộp hai câu Cohere embed khác nhau.
"""
from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Any, Callable, Hashable

import numpy as np

logger = logging.getLogger("uvicorn.error")

Key = tuple[str, str, str]


class _Inflight:
    __slots__ = ("event", "value")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.value: np.ndarray | None = None


class QueryEmbeddingCache:
    def __init__(self, max_entries: int = 10000, *, wait_timeout_s: float = 30.0):
        if max_entries < 1:
            raise ValueError("max_entries phải ≥ 1")
        self.max_entries = max_entries
        self.wait_timeout_s = wait_timeout_s
        self._lock = threading.Lock()
        self._data: OrderedDict[Hashable, np.ndarray] = OrderedDict()
        self._inflight: dict[Hashable, _Inflight] = {}
        self.hits = self.misses = self.coalesced = self.evictions = 0

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def __contains__(self, key: Hashable) -> bool:
        with self._lock:
            return key in self._data

    @staticmethod
    def _frozen(vec: Any) -> np.ndarray:
        arr = np.array(vec, dtype=np.float32, copy=True)
        arr.setflags(write=False)
        return arr

    def _put_locked(self, key: Hashable, vec: np.ndarray) -> None:
        self._data[key] = vec
        self._data.move_to_end(key)
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)
            self.evictions += 1

    def put(self, key: Hashable, vec: Any) -> None:
        arr = self._frozen(vec)
        with self._lock:
            self._put_locked(key, arr)

    def get(self, key: Hashable) -> np.ndarray | None:
        with self._lock:
            vec = self._data.get(key)
            if vec is not None:
                self._data.move_to_end(key)
                self.hits += 1
            return vec

    def get_or_compute(self, key: Hashable, fn: Callable[[], Any]) -> tuple[np.ndarray, str]:
        """(vector, "hit" | "miss"). Follower của single-flight nhận "hit" — request đó không gọi Cohere."""
        with self._lock:
            vec = self._data.get(key)
            if vec is not None:
                self._data.move_to_end(key)
                self.hits += 1
                return vec, "hit"
            inflight = self._inflight.get(key)
            leader = inflight is None
            if leader:
                inflight = self._inflight[key] = _Inflight()
                self.misses += 1
            else:
                self.coalesced += 1
        if leader:
            try:
                arr = self._frozen(fn())
                inflight.value = arr
                with self._lock:
                    self._put_locked(key, arr)
                return arr, "miss"
            finally:  # kể cả khi fn() ném: gỡ inflight và đánh thức follower để họ tự gọi
                with self._lock:
                    self._inflight.pop(key, None)
                inflight.event.set()
        if inflight.event.wait(self.wait_timeout_s) and inflight.value is not None:
            return inflight.value, "hit"
        # leader lỗi hoặc chờ quá lâu: tự gọi, không single-flight nữa (tránh kẹt theo dây chuyền)
        arr = self._frozen(fn())
        with self._lock:
            self._put_locked(key, arr)
            self.misses += 1
        return arr, "miss"

    def stats(self) -> dict[str, int | float]:
        with self._lock:
            looked = self.hits + self.misses + self.coalesced
            return {"hits": self.hits, "misses": self.misses, "coalesced": self.coalesced, "evictions": self.evictions,
                    "size": len(self._data), "ratio": round(self.hits / looked, 4) if looked else 0.0}

    def keys(self) -> list[Hashable]:
        with self._lock:
            return list(self._data)


class CachingQueryEmbedder:
    """`EmbedderPort` bọc cache quanh `embed_query`; `embed_docs` đi thẳng (text catalog không cache)."""

    def __init__(self, inner: Any, cache: QueryEmbeddingCache, *, log_every: int = 500):
        self.inner = inner
        self.cache = cache
        self.name = inner.name
        self.log_every = max(1, log_every)
        self._lookups = 0
        self._lookups_lock = threading.Lock()

    def key(self, text: str) -> Key:
        return (self.inner.name, "search_query", text)

    def embed_docs(self, texts: list[str]) -> np.ndarray:
        return self.inner.embed_docs(texts)

    def embed_query(self, q: str) -> np.ndarray:
        return self.embed_query_status(q)[0]

    def embed_query_status(self, q: str) -> tuple[np.ndarray, str]:
        vec, status = self.cache.get_or_compute(self.key(q), lambda: self.inner.embed_query(q))
        with self._lookups_lock:
            self._lookups += 1
            due = self._lookups % self.log_every == 0
        if due:
            logger.info("search.embed_cache %s", " ".join(f"{k}={v}" for k, v in self.cache.stats().items()))
        return vec, status

    def embed_queries(self, texts: list[str]) -> int:
        """Embed cả lô câu chưa có trong cache (prewarm); trả số câu vừa embed. Không log câu."""
        missing = [t for t in dict.fromkeys(texts) if self.key(t) not in self.cache]
        if not missing:
            return 0
        batch = getattr(self.inner, "embed_queries", None)
        vectors = batch(missing) if batch is not None else np.stack([self.inner.embed_query(t) for t in missing])
        if len(vectors) != len(missing):
            raise RuntimeError(f"embed_queries trả {len(vectors)} vector cho {len(missing)} câu")
        for text, vec in zip(missing, vectors, strict=True):
            self.cache.put(self.key(text), vec)
        return len(missing)

    def close(self) -> None:
        close = getattr(self.inner, "close", None)
        if close is not None:
            close()
