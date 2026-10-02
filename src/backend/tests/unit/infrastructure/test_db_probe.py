"""DatabaseProbe: cache theo TTL và phục hồi khi DB lên lại."""
import asyncio

from src.backend.app.application.errors import DatabaseUnavailableError
from src.backend.app.infrastructure.persistence import db_probe
from src.backend.app.infrastructure.persistence.db_probe import DatabaseProbe


class _Conn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def execute(self, sql):
        assert sql == "SELECT 1"


def test_result_is_cached_within_ttl_and_refreshed_after(monkeypatch) -> None:
    calls = []
    state = {"up": False}

    async def fake_connect(dsn, **kwargs):
        calls.append(dsn)
        if not state["up"]:
            raise DatabaseUnavailableError("down")
        return _Conn()

    monkeypatch.setattr(db_probe, "connect_async", fake_connect)
    now = [100.0]
    probe = DatabaseProbe("postgresql://x/y", ttl_seconds=5, clock=lambda: now[0])

    async def scenario() -> None:
        assert await probe.is_up() is False
        state["up"] = True
        assert await probe.is_up() is False  # còn trong TTL: dùng kết quả cũ, không ping lại
        assert len(calls) == 1
        now[0] += 6
        assert await probe.is_up() is True  # hết TTL: ping lại, thấy DB đã lên
        assert len(calls) == 2

    asyncio.run(scenario())


def test_concurrent_callers_share_one_ping(monkeypatch) -> None:
    calls = []

    async def fake_connect(dsn, **kwargs):
        calls.append(1)
        await asyncio.sleep(0.05)
        return _Conn()

    monkeypatch.setattr(db_probe, "connect_async", fake_connect)
    probe = DatabaseProbe("postgresql://x/y", ttl_seconds=5)

    async def scenario() -> None:
        results = await asyncio.gather(*(probe.is_up() for _ in range(10)))
        assert all(results) and len(calls) == 1

    asyncio.run(scenario())


def test_unexpected_errors_mean_down(monkeypatch) -> None:
    async def boom(dsn, **kwargs):
        raise RuntimeError("anything")

    monkeypatch.setattr(db_probe, "connect_async", boom)
    assert asyncio.run(DatabaseProbe("postgresql://x/y").is_up()) is False
