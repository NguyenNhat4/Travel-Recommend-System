"""DatabaseProbe: cache theo TTL, phục hồi khi DB lên lại, gọi đồng thời chỉ ping một lần."""
import asyncio
import time

from src.backend.app.infrastructure.persistence.db_probe import DatabaseProbe


def test_result_is_cached_within_ttl_and_refreshed_after() -> None:
    calls = []
    state = {"up": False}

    def fake_select_one(dsn, timeout):
        calls.append(dsn)
        if not state["up"]:
            raise ConnectionError("down")

    now = [100.0]
    probe = DatabaseProbe("postgresql://x/y", cache_seconds=5, clock=lambda: now[0], select_one=fake_select_one)

    async def scenario() -> None:
        assert await probe.ok() is False
        state["up"] = True
        assert await probe.ok() is False  # còn trong TTL: dùng kết quả cũ, không ping lại
        assert len(calls) == 1
        now[0] += 6
        assert await probe.ok() is True  # hết TTL: ping lại, thấy DB đã lên
        assert len(calls) == 2

    asyncio.run(scenario())


def test_concurrent_callers_share_one_ping() -> None:
    calls = []

    def slow_select_one(dsn, timeout):
        calls.append(1)
        time.sleep(0.05)

    probe = DatabaseProbe("postgresql://x/y", cache_seconds=5, select_one=slow_select_one)

    async def scenario() -> None:
        results = await asyncio.gather(*(probe.ok() for _ in range(10)))
        assert all(results) and len(calls) == 1

    asyncio.run(scenario())


def test_unexpected_errors_mean_down() -> None:
    def boom(dsn, timeout):
        raise RuntimeError("anything")

    assert asyncio.run(DatabaseProbe("postgresql://x/y", select_one=boom).ok()) is False
