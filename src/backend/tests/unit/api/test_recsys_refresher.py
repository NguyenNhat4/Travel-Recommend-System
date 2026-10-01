"""Nạp lại engine recsys theo chu kỳ: lỗi thì giữ bản đang phục vụ, không tắt recsys (history 2026-09-24)."""
import asyncio
import threading
from types import SimpleNamespace

from src.backend.app.core.config import Settings
from src.backend.app.main import RecsysRefresher


class _Closable:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _services(units: int, embedder=None, store=None):
    return {
        "recsys_embedder": embedder or _Closable(),
        "recsys_vectors": _Closable(),
        "recsys_store": store or object(),
        "index": SimpleNamespace(units=[object()] * units, model_version="v"),
        "search": f"search-{units}",
        "similar": f"similar-{units}",
        "recommend": f"recommend-{units}",
    }


class _Build:
    """Bản giả build_recsys: mỗi lần gọi lấy kết quả kế tiếp; Exception thì raise."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def __call__(self, settings, embedder=None, vector_store=None):
        self.calls.append((embedder, vector_store))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _app():
    return SimpleNamespace(state=SimpleNamespace(index=None, search=None, similar=None, recommend=None))


def _settings(seconds=900.0):
    return SimpleNamespace(catalog_refresh_seconds=seconds)


def test_prewarm_runs_once_in_background_after_the_first_publish_and_shutdown_waits_for_it(caplog):
    import logging
    from src.backend.app.application.search.prewarm import PrewarmReport
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    app = _app()
    first = _services(3)
    build = _Build(first, _services(4))
    calls = []
    started = threading.Event()

    def fake_prewarm(settings, services, stop):
        seen_stop = stop.is_set()          # đọc trước khi báo "đã vào" để stop() của test không thể chen vào giữa
        started.set()
        calls.append((services, seen_stop))
        return PrewarmReport(queries=131, unique=131, embedded=131, skipped=0, batches=2, seconds=0.5)

    async def scenario():
        refresher = RecsysRefresher(app, SimpleNamespace(catalog_refresh_seconds=900.0, search_prewarm=True),
                                    build=build, prewarm=fake_prewarm)
        assert await refresher.reload() is True
        assert refresher._prewarm_task is not None
        assert await asyncio.to_thread(started.wait, 5)   # prewarm đã chạy trong thread trước khi shutdown (CI từng chen stop() vào trước)
        assert await refresher.reload() is True          # lần nạp lại không prewarm lần nữa
        refresher.stop()
        await refresher.wait_prewarm(5.0)
        refresher.close()
    asyncio.run(scenario())
    assert calls == [(first, False)]
    assert any("search.prewarm.done" in r.getMessage() and "embedded=131" in r.getMessage() for r in caplog.records)


def test_prewarm_failure_is_logged_and_never_breaks_startup(caplog):
    import logging
    caplog.set_level(logging.WARNING, logger="uvicorn.error")
    app = _app()
    build = _Build(_services(3))

    def broken(settings, services, stop):
        raise RuntimeError("Cohere 429")

    async def scenario():
        refresher = RecsysRefresher(app, SimpleNamespace(catalog_refresh_seconds=900.0, search_prewarm=True),
                                    build=build, prewarm=broken)
        assert await refresher.reload() is True
        await refresher.wait_prewarm(5.0)
    asyncio.run(scenario())
    assert app.state.search == "search-3"
    assert any("search.prewarm.failed" in r.getMessage() and "Cohere 429" in r.getMessage() for r in caplog.records)


def test_prewarm_is_off_when_settings_do_not_ask_for_it():
    app = _app()
    refresher = RecsysRefresher(app, _settings(), build=_Build(_services(3)))
    asyncio.run(refresher.reload())
    assert refresher._prewarm_task is None
    asyncio.run(refresher.wait_prewarm(0.1))          # không có task → trả về ngay


def test_failed_refresh_keeps_the_snapshot_being_served():
    app = _app()
    first = _services(3)
    build = _Build(first, RuntimeError("Postgres tạm thời không kết nối được"))
    refresher = RecsysRefresher(app, _settings(), build=build)

    assert asyncio.run(refresher.reload()) is True
    assert asyncio.run(refresher.reload()) is False

    assert app.state.search == "search-3" and app.state.recommend == "recommend-3"
    assert refresher.services is first


def test_refresh_publishes_new_prices_and_reuses_shared_clients():
    app = _app()
    first = _services(3)
    build = _Build(first, _services(4))
    refresher = RecsysRefresher(app, _settings(), build=build)

    asyncio.run(refresher.reload())
    asyncio.run(refresher.reload())

    assert app.state.search == "search-4" and len(app.state.index.units) == 4
    # Lần sau dùng lại client Cohere và kho Weaviate của lần đầu, không mở kết nối mới mỗi chu kỳ.
    assert build.calls == [(None, None), (first["recsys_embedder"], first["recsys_store"])]


def test_startup_failure_leaves_recsys_off_and_retries_before_the_full_interval():
    app = _app()
    build = _Build(RuntimeError("Weaviate chỉ có 0/3 search unit"), _services(3))
    # Chu kỳ 1 giờ: nếu vòng lặp chờ trọn chu kỳ thì test hết giờ trước khi recsys lên.
    refresher = RecsysRefresher(app, _settings(3600.0), build=build)

    async def scenario():
        assert await refresher.reload() is False
        assert app.state.search is None
        import src.backend.app.main as main
        original, main.RECSYS_RETRY_SECONDS = main.RECSYS_RETRY_SECONDS, 0.01
        try:
            task = asyncio.create_task(refresher.run())
            for _ in range(200):
                if refresher.services:
                    break
                await asyncio.sleep(0.01)
            refresher.stop()
            await asyncio.wait_for(task, 1)
        finally:
            main.RECSYS_RETRY_SECONDS = original

    asyncio.run(scenario())
    assert app.state.search == "search-3"


def test_catalog_is_rebuilt_after_every_successful_reload_only():
    # build_catalog giữ tham chiếu tới `similar`/`listing_units`: phải dựng lại mỗi lần có bản mới.
    app, seen = _app(), []
    build = _Build(_services(3), RuntimeError("tạm lỗi"), _services(4))
    refresher = RecsysRefresher(app, _settings(), build=build,
                                on_publish=lambda: seen.append(app.state.search))

    for _ in range(3):
        asyncio.run(refresher.reload())

    assert seen == ["search-3", "search-4"]


def test_close_releases_the_shared_clients():
    refresher = RecsysRefresher(_app(), _settings(), build=_Build(_services(1)))
    asyncio.run(refresher.reload())
    refresher.close()
    assert refresher.services["recsys_embedder"].closed and refresher.services["recsys_vectors"].closed


def test_real_settings_carry_the_refresh_interval():
    # Các test trên dùng SimpleNamespace; test này giữ Settings thật không mất trường mà run() đọc.
    assert Settings(catalog_refresh_seconds=60).catalog_refresh_seconds == 60
    assert Settings.model_fields["catalog_refresh_seconds"].default == 900.0
