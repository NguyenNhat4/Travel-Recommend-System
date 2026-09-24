"""Rate limit + lockout theo cửa sổ trượt (auth §9). Áp ở FastAPI, không ở BFF (§9.4).

`RedisRateLimiter` là bản chạy thật: key `rl:{scope}:{sha256(key)}` là sorted set các mốc thời gian,
`lockout:{scope}:{sha256(key)}` là dấu khoá có TTL. Băm key để Redis không chứa email/IP dạng đọc được.

`InMemoryRateLimiter` chỉ cho dev chạy không Redis và cho test: bộ đếm nằm trong một tiến trình,
nhiều worker uvicorn sẽ đếm riêng. Composition root từ chối dùng nó khi APP_ENV=production.
"""
from __future__ import annotations

import hashlib
import logging
import math
import time
import uuid
from collections import defaultdict

from src.backend.app.application.auth.errors import RateLimited
from src.backend.app.domain.auth.rate_limits import rule_for

logger = logging.getLogger(__name__)


def _hashed(key: str) -> str:
    return hashlib.sha256(key.strip().lower().encode("utf-8")).hexdigest()


class RedisRateLimiter:
    def __init__(self, redis, *, clock=time.time):
        self._r = redis
        self._clock = clock

    async def _count(self, scope: str, key: str, *, add: bool) -> int:
        rule = rule_for(scope)
        now = self._clock()
        rl_key = f"rl:{scope}:{_hashed(key)}"
        pipe = self._r.pipeline(transaction=True)
        pipe.zremrangebyscore(rl_key, 0, now - rule.window_seconds)
        if add:
            pipe.zadd(rl_key, {f"{now}:{uuid.uuid4().hex[:8]}": now})
            pipe.expire(rl_key, rule.window_seconds)
        pipe.zcard(rl_key)
        results = await pipe.execute()
        return int(results[-1])

    async def _raise_if_locked(self, scope: str, key: str) -> None:
        ttl = await self._r.ttl(f"lockout:{scope}:{_hashed(key)}")
        if ttl and ttl > 0:
            raise RateLimited(int(ttl))

    async def hit(self, scope: str, key: str) -> None:
        rule = rule_for(scope)
        if await self._count(scope, key, add=True) > rule.limit:
            logger.warning("auth.ratelimit.hit scope=%s key=%s", scope, _hashed(key)[:12])
            raise RateLimited(rule.window_seconds)

    async def check(self, scope: str, key: str) -> None:
        await self._raise_if_locked(scope, key)
        rule = rule_for(scope)
        if await self._count(scope, key, add=False) >= rule.limit:
            raise RateLimited(rule.lockout_seconds or rule.window_seconds)

    async def register_failure(self, scope: str, key: str) -> int:
        rule = rule_for(scope)
        count = await self._count(scope, key, add=True)
        if count >= rule.limit and rule.lockout_seconds:
            await self._r.set(f"lockout:{scope}:{_hashed(key)}", "1", ex=rule.lockout_seconds)
            logger.warning("auth.lockout scope=%s key=%s durationSeconds=%d",
                           scope, _hashed(key)[:12], rule.lockout_seconds)
        return count

    async def reset(self, scope: str, key: str) -> None:
        await self._r.delete(f"rl:{scope}:{_hashed(key)}", f"lockout:{scope}:{_hashed(key)}")


class InMemoryRateLimiter:
    """Cùng ngữ nghĩa với RedisRateLimiter, trong bộ nhớ một tiến trình."""

    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._locked_until: dict[str, float] = {}

    def _window(self, scope: str, key: str) -> list[float]:
        rule = rule_for(scope)
        now = self._clock()
        bucket = f"{scope}:{_hashed(key)}"
        self._hits[bucket] = [t for t in self._hits[bucket] if t > now - rule.window_seconds]
        return self._hits[bucket]

    async def hit(self, scope: str, key: str) -> None:
        window = self._window(scope, key)
        window.append(self._clock())
        rule = rule_for(scope)
        if len(window) > rule.limit:
            raise RateLimited(rule.window_seconds)

    async def check(self, scope: str, key: str) -> None:
        bucket = f"{scope}:{_hashed(key)}"
        remaining = self._locked_until.get(bucket, 0) - self._clock()
        if remaining > 0:
            raise RateLimited(math.ceil(remaining))
        rule = rule_for(scope)
        if len(self._window(scope, key)) >= rule.limit:
            raise RateLimited(rule.lockout_seconds or rule.window_seconds)

    async def register_failure(self, scope: str, key: str) -> int:
        window = self._window(scope, key)
        window.append(self._clock())
        rule = rule_for(scope)
        if len(window) >= rule.limit and rule.lockout_seconds:
            self._locked_until[f"{scope}:{_hashed(key)}"] = self._clock() + rule.lockout_seconds
        return len(window)

    async def reset(self, scope: str, key: str) -> None:
        bucket = f"{scope}:{_hashed(key)}"
        self._hits.pop(bucket, None)
        self._locked_until.pop(bucket, None)
