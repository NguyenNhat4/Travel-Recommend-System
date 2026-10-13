"""Làm ấm cache gợi ý sau đăng nhập (PRD architecture §4, chốt 2026-10-12): đúng request trang chủ (k=4, không
destination), chạy trên pool riêng, không bao giờ ném lỗi, bỏ trùng, có giới hạn, bỏ qua khi engine chưa nạp hoặc cache tắt."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.backend.app.application.recommendation import RecommendationCache, RecommendForUser, WarmRecommendations
from src.backend.tests.fakes.recommendation_cache import InMemoryRecommendationCacheStore


class ManualExecutor:
    """Giữ việc lại cho test tự chạy; `closed` giả lập pool đã đóng."""

    def __init__(self):
        self.jobs, self.closed = [], False

    def submit(self, fn, *args):
        if self.closed:
            raise RuntimeError("cannot schedule new futures after shutdown")
        self.jobs.append((fn, args))

    def run_all(self):
        jobs, self.jobs = self.jobs, []
        for fn, args in jobs:
            fn(*args)


class Engine:
    def __init__(self, cache_enabled=True, outcome="miss", error=None):
        self.cache_enabled, self.outcome, self.error, self.calls = cache_enabled, outcome, error, []

    def __call__(self, cdp_user_id, **kwargs):
        self.calls.append((cdp_user_id, kwargs))
        if self.error is not None:
            raise self.error
        return {"recommendations": [], "diagnostics": {"cacheOutcome": self.outcome}}


class Clock:
    def __init__(self, *times):
        self.times = list(times)

    def __call__(self):
        return self.times.pop(0)


def warm_events(caplog):
    return [(r.levelname, r.fields) for r in caplog.records if getattr(r, "event", None) == "recsys.cache.warm"]


@pytest.fixture(autouse=True)
def _info(caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")


def test_warms_the_home_request_on_the_pool_and_logs_the_cache_outcome(caplog):
    engine, pool = Engine(), ManualExecutor()
    warm = WarmRecommendations(lambda: engine, pool, clock=Clock(10.0, 12.5))
    warm("VP0000001")
    assert engine.calls == [] and len(pool.jobs) == 1               # đăng nhập không chờ lần tính
    pool.run_all()
    assert engine.calls == [("VP0000001", {"k": 4, "destination": None})]
    assert warm_events(caplog) == [("INFO", {"outcome": "miss", "duration_ms": 2500})]


def test_same_user_is_warmed_once_until_the_first_run_ends(caplog):
    engine, pool = Engine(), ManualExecutor()
    warm = WarmRecommendations(lambda: engine, pool)
    warm("VP0000001")
    warm("VP0000001")
    assert len(pool.jobs) == 1 and warm_events(caplog)[0][1] == {"outcome": "duplicate"}
    pool.run_all()
    warm("VP0000001")                                                 # lần đăng nhập sau được làm ấm lại
    assert len(pool.jobs) == 1


def test_pending_work_is_bounded(caplog):
    pool = ManualExecutor()
    warm = WarmRecommendations(Engine, pool, max_pending=2)
    for user in ("A", "B", "C"):
        warm(user)
    assert len(pool.jobs) == 2 and warm_events(caplog) == [("INFO", {"outcome": "busy"})]


def test_skips_without_user_engine_or_cache(caplog):
    pool = ManualExecutor()
    WarmRecommendations(lambda: None, pool)("VP0000001")
    WarmRecommendations(lambda: Engine(cache_enabled=False), pool)("VP0000001")
    WarmRecommendations(Engine, pool)(None)
    assert pool.jobs == []
    assert warm_events(caplog) == [("INFO", {"outcome": "no_engine"})]   # cache tắt: lúc nạp đã log, không log lại


def test_engine_error_is_a_warning_and_releases_the_user(caplog):
    engine, pool = Engine(error=TimeoutError("weaviate")), ManualExecutor()
    warm = WarmRecommendations(lambda: engine, pool, clock=Clock(1.0, 1.25))
    warm("VP0000001")
    pool.run_all()
    assert warm_events(caplog) == [("WARNING", {"outcome": "failed", "duration_ms": 250, "error_kind": "TimeoutError"})]
    warm("VP0000001")
    assert len(pool.jobs) == 1


def test_closed_pool_never_breaks_login(caplog):
    pool = ManualExecutor()
    pool.closed = True
    warm = WarmRecommendations(Engine, pool)
    warm("VP0000001")                                                 # không ném lỗi
    assert warm_events(caplog) == [("WARNING", {"outcome": "failed", "error_kind": "RuntimeError"})]
    pool.closed = False
    warm("VP0000001")                                                 # người dùng không kẹt ở trạng thái đang chờ
    assert len(pool.jobs) == 1


def test_runs_the_engine_serving_at_run_time():
    old, new, pool = Engine(), Engine(), ManualExecutor()
    serving = {"engine": old}
    warm = WarmRecommendations(lambda: serving["engine"], pool)
    warm("VP0000001")
    serving["engine"] = new                                           # RecsysRefresher nạp lại giữa chừng
    pool.run_all()
    assert old.calls == [] and len(new.calls) == 1


def test_home_request_after_warming_hits_the_cache(services):
    live = services["recommend"]
    engine = RecommendForUser(live.index, live.vectors, live.cdp, live.popularity,
                              cache=RecommendationCache(InMemoryRecommendationCacheStore()), catalog_version="catalog-1")
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="recsys-warm") as pool:
        WarmRecommendations(lambda: engine, pool)("P1")
    home = engine("P1", k=4, destination=None)                        # request trang chủ sau đăng nhập
    assert home["diagnostics"]["cacheOutcome"] == "hit" and home["recommendations"]
