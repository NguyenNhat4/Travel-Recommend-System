import asyncio
from datetime import datetime, timezone

from src.backend.app.application.ports.cdp_client import BrowseEvent, CdpUnavailableError
from src.backend.app.core import request_context
from src.backend.app.infrastructure.clients.cdp_event_dispatcher import BackgroundCdpEventRecorder


def event(i: int) -> BrowseEvent:
    return BrowseEvent(event_id=f"search:{i}", cdp_user_id="VP1", event_name="search",
                       timestamp=datetime(2026, 9, 16, tzinfo=timezone.utc), search_query=f"q{i}")


class FakeCdp:
    def __init__(self, fail=False, delay=0.0):
        self.calls = []
        self.fail = fail
        self.delay = delay

    async def record_browse_events(self, events, *, request_id=None):
        await asyncio.sleep(self.delay)
        self.calls.append(([e.event_id for e in events], request_id))
        if self.fail:
            raise CdpUnavailableError("down")


def record_as(recorder, request_id, *events):
    token = request_context._request_id.set(request_id)
    try:
        for e in events:
            recorder.record(e)
    finally:
        request_context._request_id.reset(token)


def test_record_does_not_wait_and_batches_by_request_id():
    async def main():
        cdp = FakeCdp()
        recorder = BackgroundCdpEventRecorder(cdp)
        recorder.start()
        record_as(recorder, "req-a", event(1), event(2))
        record_as(recorder, "req-b", event(3))
        assert cdp.calls == []  # nothing sent inline
        await recorder.stop()
        return cdp.calls, recorder.dropped

    calls, dropped = asyncio.run(main())
    assert calls == [(["search:1", "search:2"], "req-a"), (["search:3"], "req-b")]
    assert dropped == 0


def test_full_queue_drops_instead_of_blocking():
    async def main():
        recorder = BackgroundCdpEventRecorder(FakeCdp(), max_queue=2)
        record_as(recorder, "req", event(1), event(2), event(3))  # worker not started
        return recorder.dropped

    assert asyncio.run(main()) == 1


def test_cdp_failure_is_dropped_without_retry_and_worker_keeps_running():
    async def main():
        cdp = FakeCdp(fail=True)
        recorder = BackgroundCdpEventRecorder(cdp)
        recorder.start()
        record_as(recorder, "req-1", event(1))
        await asyncio.sleep(0.01)
        record_as(recorder, "req-2", event(2))
        await recorder.stop()
        return cdp.calls, recorder.dropped

    calls, dropped = asyncio.run(main())
    assert calls == [(["search:1"], "req-1"), (["search:2"], "req-2")]
    assert dropped == 2


def test_stop_gives_up_after_timeout_and_counts_leftovers():
    async def main():
        recorder = BackgroundCdpEventRecorder(FakeCdp(delay=1.0), shutdown_timeout=0.05)
        recorder.start()
        record_as(recorder, "req", event(1))
        await asyncio.sleep(0.01)
        record_as(recorder, "req", event(2))
        await recorder.stop()
        return recorder.dropped

    assert asyncio.run(main()) == 1
