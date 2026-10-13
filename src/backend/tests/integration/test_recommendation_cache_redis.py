"""Cache gợi ý trên Redis thật (PRD architecture §4, 2026-10-12). Chạy: RUN_REDIS_INTEGRATION=1.

`RECOMMEND_CACHE_REDIS_URL` chọn Redis (mặc định DB 4 của Redis compose). Test chỉ ghi khoá có tiền tố riêng, có TTL, và dọn
khoá của mình; không dùng lệnh ảnh hưởng cả server (FLUSHDB, CLIENT PAUSE).
"""
import os
import threading
import time
import uuid

import pytest

from src.backend.app.application.ports.recommendation_cache import RecommendationCacheUnavailable
from src.backend.app.application.recommendation import CachePolicy, RecommendationCache
from src.backend.app.application.recommendation.cache import KEY_PREFIX, LOCK_PREFIX
from src.backend.app.infrastructure.persistence.redis_recommendation_cache import RedisRecommendationCacheStore

REDIS_URL = os.getenv("RECOMMEND_CACHE_REDIS_URL", "redis://:devpass@localhost:6379/4")

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REDIS_INTEGRATION") != "1", reason="set RUN_REDIS_INTEGRATION=1 to test against local Redis"
)


@pytest.fixture
def store():
    import redis

    s = RedisRecommendationCacheStore.from_url(REDIS_URL, timeout_seconds=1.0)
    suffix = f"it-{uuid.uuid4().hex}"
    yield s, suffix
    raw = redis.Redis.from_url(REDIS_URL)
    for key in raw.scan_iter(match=f"rec:v1:*{suffix}*"):
        raw.delete(key)
    raw.close()
    s.close()


def test_round_trip_has_ttl(store):
    import redis

    s, suffix = store
    key = KEY_PREFIX + suffix
    s.put(key, b'{"recommendations":[]}', 900)
    assert s.get(key) == b'{"recommendations":[]}'
    ttl = redis.Redis.from_url(REDIS_URL).ttl(key)
    assert 0 < ttl <= 900


def test_lock_is_exclusive_and_only_the_owner_unlocks(store):
    s, suffix = store
    lock = LOCK_PREFIX + suffix
    assert s.try_lock(lock, "a", 5_000) is True
    assert s.try_lock(lock, "b", 5_000) is False
    s.unlock(lock, "b")
    assert s.try_lock(lock, "b", 5_000) is False      # sai token không mở được
    s.unlock(lock, "a")
    assert s.try_lock(lock, "b", 5_000) is True


def test_single_flight_across_threads(store):
    s, suffix = store
    cache = RecommendationCache(s, CachePolicy(poll_seconds=(0.01, 0.05)))
    key = KEY_PREFIX + suffix
    computed, outcomes = [], []

    def compute():
        computed.append(1)
        time.sleep(0.3)
        return {"recommendations": [1], "diagnostics": {}}

    threads = [threading.Thread(target=lambda: outcomes.append(cache.get_or_compute(key, compute)[1])) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert len(computed) == 1 and sorted(outcomes) == ["miss", "wait_hit", "wait_hit"]


def test_unreachable_redis_fails_fast():
    s = RedisRecommendationCacheStore.from_url("redis://127.0.0.1:1/4")   # cổng không có ai nghe
    started = time.perf_counter()
    with pytest.raises(RecommendationCacheUnavailable):
        s.get(KEY_PREFIX + "x")
    assert time.perf_counter() - started < 0.5
    s.close()
