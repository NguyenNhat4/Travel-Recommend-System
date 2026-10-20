"""Adapter Redis của cache gợi ý (2026-10-12): đổi lỗi Redis thành `RecommendationCacheUnavailable`, ngắt mạch 5 giây,
WARNING có giới hạn tần suất và không lộ URL/mật khẩu, tham số lệnh đúng (TTL, NX/PX, mở khoá theo token)."""
from __future__ import annotations

import logging

import pytest
import redis
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

from src.backend.app.application.ports.recommendation_cache import RecommendationCacheUnavailable
from src.backend.app.infrastructure.persistence import redis_recommendation_cache as module
from src.backend.app.infrastructure.persistence.redis_recommendation_cache import RedisRecommendationCacheStore


class FakeClient:
    def __init__(self):
        self.calls, self.fail_with, self.values, self.scripts = [], None, {}, []

    def _maybe_fail(self):
        if self.fail_with is not None:
            raise self.fail_with

    def get(self, key):
        self.calls.append(("get", key))
        self._maybe_fail()
        return self.values.get(key)

    def set(self, key, value, **kwargs):
        self.calls.append(("set", key, value, kwargs))
        self._maybe_fail()
        if kwargs.get("nx") and key in self.values:
            return None
        self.values[key] = value
        return True

    def register_script(self, source):
        self.scripts.append(source)

        def run(keys, args):
            self.calls.append(("unlock", keys, args))
            self._maybe_fail()
            if self.values.get(keys[0]) == args[0]:
                del self.values[keys[0]]
                return 1
            return 0
        return run

    def close(self):
        self.calls.append(("close",))


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def store_with(client=None, clock=None):
    client = client or FakeClient()
    return RedisRecommendationCacheStore(client, clock=clock or Clock()), client


def test_commands_carry_ttl_nx_px_and_token_checked_unlock():
    store, client = store_with()
    store.put("rec:v1:k", b"{}", 900)
    assert store.try_lock("rec:v1:lock:k", "t1", 30_000) is True
    assert store.try_lock("rec:v1:lock:k", "t2", 30_000) is False       # NX: người khác đang giữ
    store.unlock("rec:v1:lock:k", "t2")                                   # sai token: khoá còn nguyên
    assert client.values["rec:v1:lock:k"] == "t1"
    store.unlock("rec:v1:lock:k", "t1")
    assert "rec:v1:lock:k" not in client.values and store.get("rec:v1:k") == b"{}"
    assert client.calls[0] == ("set", "rec:v1:k", b"{}", {"ex": 900})
    assert client.calls[1] == ("set", "rec:v1:lock:k", "t1", {"nx": True, "px": 30_000})
    assert "redis.call('get', KEYS[1]) == ARGV[1]" in client.scripts[0]


@pytest.mark.parametrize("error", [RedisConnectionError("Error 111 connecting to redis://:devpass@10.0.0.9:6379"),
                                   RedisTimeoutError("Timeout reading from socket"), OSError("network down")])
def test_redis_errors_become_cache_unavailable(error):
    store, client = store_with()
    client.fail_with = error
    with pytest.raises(RecommendationCacheUnavailable):
        store.get("k")


def test_breaker_opens_for_five_seconds_then_tries_again():
    clock = Clock()
    store, client = store_with(clock=clock)
    client.fail_with = RedisTimeoutError("slow")
    with pytest.raises(RecommendationCacheUnavailable):
        store.get("k")
    client.fail_with = None
    calls = len(client.calls)
    clock.now = 4.9
    with pytest.raises(RecommendationCacheUnavailable, match="breaker_open"):
        store.get("k")
    assert len(client.calls) == calls                     # mạch đang ngắt: không chạm Redis
    clock.now = 5.1
    assert store.get("k") is None and len(client.calls) == calls + 1


def test_warning_is_rate_limited_and_never_leaks_the_url(caplog):
    clock = Clock()
    store, client = store_with(clock=clock)
    client.fail_with = RedisConnectionError("Error connecting to redis://:devpass@10.0.0.9:6379/4")
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        for t in (0.0, 6.0, 12.0, 70.0):                   # mỗi lần sau khi mạch mở lại
            clock.now = t
            with pytest.raises(RecommendationCacheUnavailable):
                store.get("k")
    events = [r for r in caplog.records if getattr(r, "event", None) == "recsys.cache.error"]
    assert [e.fields["suppressed"] for e in events] == [0, 2]
    assert events[0].fields == {"op": "get", "error_kind": "ConnectionError", "suppressed": 0}
    assert "devpass" not in caplog.text and "10.0.0.9" not in caplog.text


def test_from_url_uses_100ms_timeouts_without_retry(monkeypatch):
    seen = {}

    def from_url(url, **kwargs):
        seen.update(kwargs, url=url)
        return FakeClient()

    monkeypatch.setattr(redis.Redis, "from_url", staticmethod(from_url))
    store = module.RedisRecommendationCacheStore.from_url("redis://:pw@cache:6379/4")
    assert seen == {"url": "redis://:pw@cache:6379/4", "socket_timeout": 0.1, "socket_connect_timeout": 0.1,
                    "retry_on_timeout": False, "health_check_interval": 0}
    store.close()
