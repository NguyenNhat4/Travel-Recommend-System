"""BrowseEventRecorder that ships events to CDP in the background through a bounded queue.

Browse events are best-effort: when the queue is full or CDP fails, events are dropped and logged, never retried,
so a slow CDP cannot slow requests, grow memory without bound, or be hammered by retries.
"""
import asyncio
import logging

from src.backend.app.application.ports.cdp_client import BrowseEvent, CdpClient, CdpUnavailableError
from src.backend.app.core.request_context import current_request_id

logger = logging.getLogger(__name__)

MAX_BATCH = 100


class BackgroundCdpEventRecorder:
    def __init__(self, cdp: CdpClient, *, max_queue: int = 1000, shutdown_timeout: float = 2.0):
        self._cdp = cdp
        self._queue: asyncio.Queue[tuple[BrowseEvent, str | None]] = asyncio.Queue(maxsize=max_queue)
        self._shutdown_timeout = shutdown_timeout
        self._worker: asyncio.Task | None = None
        self.dropped = 0

    def record(self, event: BrowseEvent) -> None:
        # Capture the request ID now; the worker runs outside the request context.
        try:
            self._queue.put_nowait((event, current_request_id()))
        except asyncio.QueueFull:
            self._drop(1, "queue_full", current_request_id())

    def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run(), name="cdp-event-recorder")

    async def stop(self) -> None:
        if self._worker is None:
            return
        try:
            await asyncio.wait_for(self._queue.join(), timeout=self._shutdown_timeout)
        except TimeoutError:
            pass
        self._worker.cancel()
        try:
            await self._worker
        except asyncio.CancelledError:
            pass
        self._worker = None
        remaining = self._queue.qsize()
        if remaining:
            self._drop(remaining, "shutdown", None)

    async def _run(self) -> None:
        while True:
            batch = [await self._queue.get()]
            while len(batch) < MAX_BATCH and not self._queue.empty():
                batch.append(self._queue.get_nowait())
            try:
                for request_id, events in _group_by_request_id(batch):
                    await self._send(events, request_id)
            finally:
                for _ in batch:
                    self._queue.task_done()

    async def _send(self, events: list[BrowseEvent], request_id: str | None) -> None:
        try:
            await self._cdp.record_browse_events(events, request_id=request_id)
        except CdpUnavailableError as exc:
            self._drop(len(events), type(exc).__name__, request_id)
        except Exception:
            logger.exception("Unexpected error recording browse events requestId=%s", request_id)
            self.dropped += len(events)

    def _drop(self, count: int, reason: str, request_id: str | None) -> None:
        self.dropped += count
        # No cdpUserId or payload in logs (hop-dong-tich-hop-backend.md §8.6).
        logger.warning("Dropped %d browse event(s) reason=%s requestId=%s", count, reason, request_id)


def _group_by_request_id(batch: list[tuple[BrowseEvent, str | None]]) -> list[tuple[str | None, list[BrowseEvent]]]:
    groups: list[tuple[str | None, list[BrowseEvent]]] = []
    for event, request_id in batch:
        if groups and groups[-1][0] == request_id:
            groups[-1][1].append(event)
        else:
            groups.append((request_id, [event]))
    return groups
