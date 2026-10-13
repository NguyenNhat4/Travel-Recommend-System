"""Cache kết quả gợi ý (PRD architecture §4, chốt 2026-10-12): khoá theo dấu vân tay event, không trả kết quả cũ, chống tính
trùng, kho lỗi thì tính trực tiếp, đường lui khi CDP lỗi không bao giờ được ghi."""
from __future__ import annotations

import copy
import threading
from datetime import datetime, timedelta, timezone

import pytest

from src.backend.app.application.itinerary.contracts import valid
from src.backend.app.application.ports.cdp_client import CdpUnavailableError
from src.backend.app.application.recommendation import CachePolicy, RecommendForUser, RecommendationCache
from src.backend.app.application.recommendation.cache import KEY_PREFIX, LOCK_PREFIX, engine_version
from src.backend.app.application.recommendation.responses import ENGINE_ONLY_DIAGNOSTICS, recommendation_response
from src.backend.tests.fakes.recommendation_cache import InMemoryRecommendationCacheStore


class ListReader:
    """Reader CDP từ một danh sách sửa được (thêm event giữa hai lần gọi)."""

    def __init__(self, events, down=False):
        self.events, self.down, self.calls = list(events), down, 0

    def events_for_user(self, cdp_user_id):
        self.calls += 1
        if self.down:
            raise CdpUnavailableError("CDP history read failed")
        return sorted((e for e in self.events if e["cdpUserId"] == cdp_user_id), key=lambda e: e["timestamp"], reverse=True)

    def purchase_events(self, since_days=730):
        return [e for e in self.events if e["eventName"] == "purchase"]


class CountingVectors:
    def __init__(self, inner):
        self.inner, self.dimension, self.near = inner, inner.dimension, 0

    def vectors(self, ids):
        return self.inner.vectors(ids)

    def near_vector(self, *a, **kw):
        self.near += 1
        return self.inner.near_vector(*a, **kw)


def history(now):
    t = lambda days: (now - timedelta(days=days)).isoformat()  # noqa: E731
    return [{"cdpUserId": "U", "eventName": "product_view", "productId": "A1", "timestamp": t(6), "eventGroupId": "T1"},
            {"cdpUserId": "U", "eventName": "purchase", "productId": "R1", "timestamp": t(3), "usingDate": "2026-10-05",
             "eventGroupId": "T1"}]


@pytest.fixture
def world(services):
    live, now = services["recommend"], services["now"]
    store = InMemoryRecommendationCacheStore()
    reader = ListReader(history(now))
    vectors = CountingVectors(live.vectors)

    def engine(**kw):
        cdp = kw.pop("cdp", reader)
        popularity = kw.pop("popularity", live.popularity)
        params = {"cache": RecommendationCache(store), "catalog_version": "catalog-1", **kw}
        return RecommendForUser(live.index, vectors, cdp, popularity, **params)
    return {"store": store, "reader": reader, "vectors": vectors, "engine": engine, "now": now, "live": live}


def payload(result: dict) -> dict:
    out = copy.deepcopy(result)
    for key in (*ENGINE_ONLY_DIAGNOSTICS, "userVectorCacheHit"):
        out["diagnostics"].pop(key, None)
    return out


def test_miss_then_hit_computes_once_and_returns_the_same_payload(world):
    rec, now = world["engine"](), world["now"]
    first = rec("U", k=3, now=now)
    near_after_miss = world["vectors"].near
    second = rec("U", k=3, now=now)
    assert (first["diagnostics"]["cacheOutcome"], first["diagnostics"]["userVectorCacheHit"]) == ("miss", False)
    assert (second["diagnostics"]["cacheOutcome"], second["diagnostics"]["userVectorCacheHit"]) == ("hit", True)
    assert world["vectors"].near == near_after_miss > 0          # trúng cache thì không gọi kho vector
    assert payload(second) == payload(first)                     # JSON giữ nguyên kết quả
    assert "cache" in second["diagnostics"]["stageMs"] and "history" not in second["diagnostics"]["stageMs"]
    (key,) = world["store"].keys()
    assert key.startswith(KEY_PREFIX) and "U" not in key[len(KEY_PREFIX):]
    assert 0 < world["store"].ttl_of(key) <= 900


def test_a_new_purchase_changes_the_key_so_the_next_call_is_fresh(world):
    rec, now = world["engine"](), world["now"]
    before = rec("U", k=3, now=now)
    world["reader"].events.append({"cdpUserId": "U", "eventName": "purchase", "productId": "FL1",
                                   "timestamp": (now - timedelta(hours=1)).isoformat(), "usingDate": "2026-10-05",
                                   "eventGroupId": "T1"})
    after = rec("U", k=3, now=now)
    assert after["diagnostics"]["cacheOutcome"] == "miss"        # K1: không trả gợi ý của lịch sử cũ
    assert before["diagnostics"]["excludedVerticals"] == ["hotel"]
    assert after["diagnostics"]["excludedVerticals"] == ["flight", "hotel"]
    assert len(world["store"].keys()) == 2


def test_key_depends_on_k_destination_vietnam_day_and_engine_version(world):
    cache, events = RecommendationCache(world["store"]), history(world["now"])
    day = datetime(2026, 9, 21, 16, 59, 59, tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=7))).date()
    next_day = datetime(2026, 9, 21, 17, 0, 1, tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=7))).date()
    base = dict(engine_version="e1", cdp_user_id="U", k=4, destination=None, today=day, events=events)
    key = cache.key(**base)
    assert key == cache.key(**base)
    for change in ({"k": 3}, {"destination": "Nha Trang"}, {"today": next_day}, {"engine_version": "e2"},
                   {"events": events[:1]}, {"cdp_user_id": "V"}):
        assert cache.key(**{**base, **change}) != key, change
    assert RecommendationCache(world["store"], namespace="new-code").key(**base) != key


def test_engine_version_tracks_catalog_knobs_and_popularity_but_is_stable_across_instances(world):
    make = world["engine"]
    assert make()._engine_version == make()._engine_version is not None
    assert make(catalog_version="catalog-2")._engine_version != make()._engine_version
    assert make(candidate_k=50)._engine_version != make()._engine_version
    assert engine_version(make(popularity=None)) != engine_version(make())
    assert make(catalog_version=None).cache_enabled is False      # không biết phiên bản catalog thì không cache


def test_store_errors_fall_back_to_computing(world):
    world["store"].down = True
    result = world["engine"]()("U", k=3, now=world["now"])
    assert result["diagnostics"]["cacheOutcome"] == "error" and result["recommendations"]


def test_cdp_outage_never_touches_the_store(world):
    reader = ListReader([], down=True)
    result = world["engine"](cdp=reader)("U", k=3, now=world["now"])
    assert result["strategy"] == "popular" and world["store"].calls == []
    assert "userVectorCacheHit" not in result["diagnostics"]


def test_guests_and_injected_events_are_not_cached(world):
    rec, now = world["engine"](), world["now"]
    rec(None, k=3, now=now)
    rec("U", k=3, now=now, events=history(now))
    assert world["store"].calls == []


def test_oversized_results_are_not_stored(world):
    tiny = RecommendationCache(world["store"], CachePolicy(max_bytes=64))
    result = world["engine"](cache=tiny)("U", k=3, now=world["now"])
    assert result["diagnostics"]["cacheOutcome"] == "too_large" and world["store"].keys() == []


def test_mutating_a_hit_does_not_leak_into_the_next_hit(world):
    rec, now = world["engine"](), world["now"]
    rec("U", k=3, now=now)
    hit = rec("U", k=3, now=now)
    hit["recommendations"][0]["attributes"]["polluted"] = True
    hit["recommendations"].clear()
    again = rec("U", k=3, now=now)
    assert again["recommendations"] and "polluted" not in again["recommendations"][0]["attributes"]


def test_route_payload_matches_the_contract_on_miss_and_hit(world):
    rec = world["engine"]()
    miss = recommendation_response(rec, "U", k=3, destination=None)
    hit = recommendation_response(rec, "U", k=3, destination=None)
    assert valid("RecommendationResponse", miss) and valid("RecommendationResponse", hit)
    assert (miss["diagnostics"]["userVectorCacheHit"], hit["diagnostics"]["userVectorCacheHit"]) == (False, True)
    assert "cacheOutcome" not in hit["diagnostics"] and "stageMs" not in hit["diagnostics"]


def test_corrupt_value_counts_as_a_miss(world):
    rec, now = world["engine"](), world["now"]
    rec("U", k=3, now=now)
    (key,) = world["store"].keys()
    world["store"].put(key, b"{not json", 900)
    assert rec("U", k=3, now=now)["diagnostics"]["cacheOutcome"] == "miss"


# --- chống tính trùng (RecommendationCache trực tiếp) -----------------------------------------

def test_concurrent_requests_for_one_key_compute_once():
    store = InMemoryRecommendationCacheStore()
    cache = RecommendationCache(store, CachePolicy(poll_seconds=(0.005, 0.02)))
    started, release, computed = threading.Event(), threading.Event(), []

    def compute():
        computed.append(1)
        started.set()
        release.wait(5)
        return {"recommendations": [1], "diagnostics": {}}

    out = {}
    leader = threading.Thread(target=lambda: out.setdefault("leader", cache.get_or_compute(KEY_PREFIX + "k", compute)))
    leader.start()
    assert started.wait(5)
    follower = threading.Thread(target=lambda: out.setdefault("follower", cache.get_or_compute(KEY_PREFIX + "k", compute)))
    follower.start()
    release.set()
    leader.join(5)
    follower.join(5)
    assert len(computed) == 1
    assert out["leader"][1] == "miss" and out["follower"] == ({"recommendations": [1], "diagnostics": {}}, "wait_hit")


def test_a_failing_leader_releases_the_lock_for_the_next_request():
    store = InMemoryRecommendationCacheStore()
    cache = RecommendationCache(store)

    def boom():
        raise RuntimeError("weaviate down")

    with pytest.raises(RuntimeError):
        cache.get_or_compute(KEY_PREFIX + "k", boom)
    assert cache.get_or_compute(KEY_PREFIX + "k", lambda: {"diagnostics": {}})[1] == "miss"


def test_waiting_gives_up_after_the_budget_and_fills_the_cache():
    now = [0.0]
    store = InMemoryRecommendationCacheStore(clock=lambda: now[0])
    cache = RecommendationCache(store, CachePolicy(wait_seconds=1.0, lock_ttl_ms=30_000), clock=lambda: now[0],
                                sleep=lambda s: now.__setitem__(0, now[0] + s))
    assert store.try_lock(LOCK_PREFIX + "k", "someone-else", 30_000)     # người giữ khoá chết giữa chừng
    result, outcome = cache.get_or_compute(KEY_PREFIX + "k", lambda: {"recommendations": [], "diagnostics": {}})
    assert outcome == "wait_timeout" and now[0] >= 1.0
    assert cache.get_or_compute(KEY_PREFIX + "k", lambda: pytest.fail("phải trúng cache"))[1] == "hit"
