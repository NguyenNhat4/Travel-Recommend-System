"""Bản giả `RecommendationCacheStore` cho test offline: dict trong bộ nhớ, TTL theo đồng hồ tiêm, `SET NX` theo token.

`down = True` thì mọi lệnh ném `RecommendationCacheUnavailable` (như Redis chết hoặc ngắt mạch). `calls` ghi tên lệnh theo thứ
tự gọi. An toàn khi gọi từ nhiều thread.
"""
from __future__ import annotations

import threading
import time

from src.backend.app.application.ports.recommendation_cache import RecommendationCacheUnavailable


class InMemoryRecommendationCacheStore:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._values: dict[str, tuple[bytes, float]] = {}     # key → (giá trị, hết hạn lúc)
        self._locks: dict[str, tuple[str, float]] = {}        # khoá tính → (token, hết hạn lúc)
        self._mutex = threading.Lock()
        self.down = False
        self.calls: list[str] = []

    def _check(self, op: str) -> None:
        self.calls.append(op)
        if self.down:
            raise RecommendationCacheUnavailable(f"{op}: down")

    def get(self, key: str) -> bytes | None:
        with self._mutex:
            self._check("get")
            value = self._values.get(key)
            if value is None or value[1] <= self._clock():
                self._values.pop(key, None)
                return None
            return value[0]

    def put(self, key: str, value: bytes, ttl_seconds: int) -> None:
        assert ttl_seconds > 0, "mọi khoá phải có TTL (Redis noeviction)"
        with self._mutex:
            self._check("put")
            self._values[key] = (value, self._clock() + ttl_seconds)

    def try_lock(self, key: str, token: str, ttl_ms: int) -> bool:
        assert ttl_ms > 0
        with self._mutex:
            self._check("try_lock")
            held = self._locks.get(key)
            if held is not None and held[1] > self._clock():
                return False
            self._locks[key] = (token, self._clock() + ttl_ms / 1000)
            return True

    def unlock(self, key: str, token: str) -> None:
        with self._mutex:
            self._check("unlock")
            held = self._locks.get(key)
            if held is not None and held[0] == token:
                del self._locks[key]

    def ttl_of(self, key: str) -> float | None:
        value = self._values.get(key)
        return None if value is None else value[1] - self._clock()

    def keys(self) -> list[str]:
        return list(self._values)
