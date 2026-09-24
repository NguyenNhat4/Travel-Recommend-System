"""RedisRateLimiter trên Redis thật (auth §9). Chạy: RUN_REDIS_INTEGRATION=1 (docker compose up -d redis)."""
import asyncio
import os
import uuid

import pytest

from src.backend.app.application.auth.errors import RateLimited
from src.backend.app.infrastructure.auth.rate_limiter import RedisRateLimiter
from src.backend.app.infrastructure.auth.revoked_tokens import RedisRevokedTokens

REDIS_URL = os.getenv("AUTH_REDIS_URL", "redis://:devpass@localhost:6379/1")

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REDIS_INTEGRATION") != "1", reason="set RUN_REDIS_INTEGRATION=1 to test against local Redis"
)


def test_lockout_and_reset_on_real_redis():
    import redis.asyncio as redis_asyncio

    async def scenario():
        client = redis_asyncio.from_url(REDIS_URL)
        limiter = RedisRateLimiter(client)
        key = f"it-{uuid.uuid4().hex}@vota.test"
        try:
            for _ in range(5):
                await limiter.check("login:email", key)
                await limiter.register_failure("login:email", key)
            with pytest.raises(RateLimited) as caught:
                await limiter.check("login:email", key)
            assert 890 <= caught.value.retry_after_seconds <= 900
            # Key trong Redis đã băm: không chứa email đọc được.
            assert not [k async for k in client.scan_iter(match=f"*{key}*")]
            await limiter.reset("login:email", key)
            await limiter.check("login:email", key)

            ip = f"198.51.100.{uuid.uuid4().int % 250}"
            for _ in range(5):
                await limiter.hit("register:ip", ip)
            with pytest.raises(RateLimited):
                await limiter.hit("register:ip", ip)
            await limiter.reset("register:ip", ip)
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_revoked_jti_on_real_redis():
    import redis.asyncio as redis_asyncio

    async def scenario():
        client = redis_asyncio.from_url(REDIS_URL)
        jti = uuid.uuid4().hex
        try:
            revoked = RedisRevokedTokens(client)
            assert not await revoked.is_revoked(jti)
            await client.set(f"jwt:revoked:{jti}", "1", ex=60)
            assert await revoked.is_revoked(jti)
        finally:
            await client.delete(f"jwt:revoked:{jti}")
            await client.aclose()

    asyncio.run(scenario())
