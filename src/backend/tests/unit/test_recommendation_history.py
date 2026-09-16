import asyncio

from src.backend.app.application.ports.cdp_client import CdpUnavailableError
from src.backend.app.application.recommendation.history import load_history


class FakeCdp:
    def __init__(self, result):
        self.result = result
        self.kwargs = None

    async def list_events(self, cdp_user_id, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_returns_events_with_bounded_read():
    cdp = FakeCdp([])
    assert asyncio.run(load_history(cdp, "VP1")) == []
    assert cdp.kwargs["max_events"] == 500


def test_cdp_outage_returns_none_for_popular_fallback():
    assert asyncio.run(load_history(FakeCdp(CdpUnavailableError("down")), "VP1")) is None
