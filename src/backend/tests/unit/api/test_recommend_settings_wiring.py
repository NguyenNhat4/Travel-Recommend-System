"""Composition root nối pool `recsys-io` (RECOMMEND_IO_WORKERS) và cache gợi ý trên Redis (RECOMMEND_CACHE_REDIS_URL,
PRD architecture §4) vào `RecommendForUser` (main.build_recsys, main.build_recommendation_cache), 2026-10-12."""
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack

from src.backend.app.application.recommendation import RecommendationCache
from src.backend.app.core.config import Settings
from src.backend.app.main import build_recommendation_cache, build_recsys
from src.backend.tests.conftest import FakeEmbedder
from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore
from src.backend.tests.fakes.jsonl_cdp_reader import JsonlCdpReader
from src.backend.tests.fakes.recommendation_cache import InMemoryRecommendationCacheStore


class VersionedStore:
    """Store giả có `version` như WeaviateVectorStore (mã băm catalog + metadata vector)."""

    def __init__(self, inner, version):
        self.inner, self.version = inner, version

    def load(self):
        return self.inner.load()


def _recommend(data_dir, store=None, **kwargs):
    emb = FakeEmbedder()
    store = store or InMemoryVectorStore(str(data_dir / "products.jsonl"), emb, str(data_dir / ".embcache"))
    return build_recsys(Settings(_env_file=None), embedder=emb, vector_store=store,
                        cdp_reader=JsonlCdpReader(str(data_dir / "events.jsonl")), **kwargs)["recommend"]


def test_io_workers_default_and_bounds():
    assert Settings(_env_file=None).recommend_io_workers == 16
    assert Settings(_env_file=None, recommend_io_workers=0).recommend_io_workers == 0   # 0 = tuần tự (rollback)


def test_executor_reaches_the_engine(data_dir):
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert _recommend(data_dir, recommend_executor=pool).executor is pool
    assert _recommend(data_dir).executor is None


def test_cache_needs_a_catalog_version(data_dir, caplog):
    cache = RecommendationCache(InMemoryRecommendationCacheStore())
    inner = InMemoryVectorStore(str(data_dir / "products.jsonl"), FakeEmbedder(), str(data_dir / ".embcache"))
    versioned = _recommend(data_dir, VersionedStore(inner, "catalog-v1"), recommend_cache=cache)
    assert versioned.cache is cache and versioned.catalog_version == "catalog-v1" and versioned.cache_enabled
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        unversioned = _recommend(data_dir, recommend_cache=cache)          # store giả không có `version`
    assert unversioned.cache_enabled is False
    assert any(getattr(r, "event", None) == "recsys.cache.disabled" for r in caplog.records)


def test_cache_settings_defaults():
    s = Settings(_env_file=None)
    assert (s.recommend_cache_redis_url, s.recommend_cache_ttl_seconds, s.recommend_preload_vectors) == ("", 900, True)


def test_blank_url_disables_the_cache_and_production_warns(caplog):
    with ExitStack() as stack:
        assert build_recommendation_cache(Settings(_env_file=None), stack) is None
        with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
            assert build_recommendation_cache(Settings(_env_file=None, app_env="production"), stack) is None
    events = [r for r in caplog.records if getattr(r, "event", None) == "recsys.cache.disabled"]
    assert events and events[0].fields == {"reason": "no_redis_url"}


def test_url_builds_a_redis_cache_closed_with_the_app(monkeypatch):
    built = {}

    class FakeRedisStore:
        @classmethod
        def from_url(cls, url):
            built["url"] = url
            built["store"] = store = cls()
            return store

        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    from src.backend.app.infrastructure.persistence import redis_recommendation_cache
    monkeypatch.setattr(redis_recommendation_cache, "RedisRecommendationCacheStore", FakeRedisStore)
    settings = Settings(_env_file=None, recommend_cache_redis_url="redis://:pw@cache:6379/4",
                        recommend_cache_ttl_seconds=600)
    with ExitStack() as stack:
        cache = build_recommendation_cache(settings, stack)
        assert isinstance(cache, RecommendationCache) and cache.policy.ttl_seconds == 600 and cache.namespace
        assert built["url"] == "redis://:pw@cache:6379/4" and not built["store"].closed
    assert built["store"].closed
