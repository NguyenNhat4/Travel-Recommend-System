"""`RecommendationCacheStore` trên Redis dùng chung (Memorystore), chốt 2026-10-12.

PRD `docs/prd/architecture.md` §4: cache gợi ý ở DB index riêng, TTL 15 phút, mọi khoá có TTL (Redis `noeviction`), Redis lỗi
thì tính trực tiếp. `RECOMMEND_CACHE_REDIS_URL` (deployment-plan §2), để trống thì tắt cache.

- Client **đồng bộ**: route `/recommendations` là hàm sync chạy trong threadpool, tool của trợ lý chạy trên pool thread.
- `socket_timeout` và `socket_connect_timeout` 100 ms, không retry: Redis chậm hơn mức đó thì bỏ qua cache cho nhanh.
- Ngắt mạch 5 giây sau mỗi lỗi: lúc Redis chết, mỗi worker chỉ chịu tối đa một lần chờ 100 ms mỗi 5 giây.
- WARNING `recsys.cache.error` tối đa một lần mỗi 60 giây mỗi worker, chỉ ghi tên lệnh và kiểu lỗi (không ghi URL, khoá, mật
  khẩu), kèm số lỗi đã gộp.
- Mở khoá tính bằng Lua: chỉ xoá khi giá trị còn là token của mình.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from redis.exceptions import RedisError

from src.backend.app.application.ports.recommendation_cache import RecommendationCacheUnavailable
from src.backend.app.core.logging_config import log_event

logger = logging.getLogger("uvicorn.error")

_UNLOCK = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0"


class RedisRecommendationCacheStore:
    @classmethod
    def from_url(cls, url: str, *, timeout_seconds: float = 0.1, **kwargs) -> "RedisRecommendationCacheStore":
        import redis

        client = redis.Redis.from_url(url, socket_timeout=timeout_seconds, socket_connect_timeout=timeout_seconds,
                                      retry_on_timeout=False, health_check_interval=0)
        return cls(client, **kwargs)

    def __init__(self, client, *, breaker_seconds: float = 5.0, warn_every_seconds: float = 60.0,
                 clock: Callable[[], float] = time.monotonic):
        self._client = client
        self._unlock = client.register_script(_UNLOCK)
        self._breaker_seconds = breaker_seconds
        self._warn_every = warn_every_seconds
        self._clock = clock
        self._open_until = 0.0
        self._last_warning: float | None = None
        self._suppressed = 0
        self._mutex = threading.Lock()

    def get(self, key: str) -> bytes | None:
        return self._call("get", self._client.get, key)

    def put(self, key: str, value: bytes, ttl_seconds: int) -> None:
        self._call("set", self._client.set, key, value, ex=ttl_seconds)

    def try_lock(self, key: str, token: str, ttl_ms: int) -> bool:
        return bool(self._call("lock", self._client.set, key, token, nx=True, px=ttl_ms))

    def unlock(self, key: str, token: str) -> None:
        self._call("unlock", self._unlock, keys=[key], args=[token])

    def close(self) -> None:
        self._client.close()

    def _call(self, op: str, fn: Callable[..., Any], *args, **kwargs) -> Any:
        if self._clock() < self._open_until:
            raise RecommendationCacheUnavailable("breaker_open")
        try:
            return fn(*args, **kwargs)
        except (RedisError, OSError) as exc:
            self._trip(op, exc)
            raise RecommendationCacheUnavailable(f"{op}: {type(exc).__name__}") from exc

    def _trip(self, op: str, exc: BaseException) -> None:
        now = self._clock()
        with self._mutex:
            self._open_until = now + self._breaker_seconds
            if self._last_warning is not None and now - self._last_warning < self._warn_every:
                self._suppressed += 1
                return
            suppressed, self._suppressed, self._last_warning = self._suppressed, 0, now
        log_event(logger, "recsys.cache.error", "WARNING", op=op, error_kind=type(exc).__name__, suppressed=suppressed)
