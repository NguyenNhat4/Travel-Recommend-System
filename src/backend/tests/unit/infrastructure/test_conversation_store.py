import json

import pytest

from src.backend.app.infrastructure.persistence.conversation_store import RedisConversationStore


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.writes = []

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, *, ex):
        self.values[key] = value.encode()
        self.writes.append((key, json.loads(value), ex))


@pytest.mark.asyncio
async def test_redis_conversation_store_round_trips_and_isolates_owner():
    redis = FakeRedis()
    store = RedisConversationStore(redis, ttl_seconds=120)
    await store.save("conversation-1", {"intent": {"days": 3}}, "user:a")

    assert await store.load("conversation-1", "user:a") == {"intent": {"days": 3}}
    assert await store.load("conversation-1", "user:b") is None
    assert redis.writes[0][2] == 120


@pytest.mark.asyncio
async def test_redis_conversation_store_returns_none_without_id():
    assert await RedisConversationStore(FakeRedis()).load(None, "user:a") is None
