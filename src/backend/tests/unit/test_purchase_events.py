import asyncio
import logging
from datetime import date, datetime, timezone

import pytest

from src.backend.app.application.booking.purchase_events import commit_with_purchase_events
from src.backend.app.application.ports.cdp_client import CdpUnavailableError, PurchaseEvent

EVENTS = [PurchaseEvent(booking_item_id="bi-1", cdp_user_id="VP1", product_id="p1", taxonomy="hotel",
                        event_group_id="OFF1", quantity=1, unit_price=1.0, using_date=date(2026, 10, 1),
                        timestamp=datetime(2026, 9, 16, tzinfo=timezone.utc))]


class FakeCdp:
    def __init__(self, record_fails=False, cancel_fails=False):
        self.log = []
        self.record_fails = record_fails
        self.cancel_fails = cancel_fails

    async def record_purchases(self, events):
        self.log.append("record")
        if self.record_fails:
            raise CdpUnavailableError("down")

    async def cancel_purchases(self, events):
        self.log.append("cancel")
        if self.cancel_fails:
            raise CdpUnavailableError("down")


def test_records_before_commit():
    cdp, order = FakeCdp(), []

    async def commit():
        order.append(list(cdp.log))
        return "booking"

    assert asyncio.run(commit_with_purchase_events(cdp, EVENTS, commit)) == "booking"
    assert order == [["record"]]
    assert cdp.log == ["record"]


def test_cdp_failure_prevents_commit():
    committed = []

    async def commit():
        committed.append(True)

    with pytest.raises(CdpUnavailableError):
        asyncio.run(commit_with_purchase_events(FakeCdp(record_fails=True), EVENTS, commit))
    assert committed == []


def test_commit_failure_cancels_purchases_and_reraises():
    cdp = FakeCdp()

    async def commit():
        raise RuntimeError("db down")

    with pytest.raises(RuntimeError):
        asyncio.run(commit_with_purchase_events(cdp, EVENTS, commit))
    assert cdp.log == ["record", "cancel"]


def test_failed_compensation_is_logged_and_original_error_kept(caplog):
    async def commit():
        raise RuntimeError("db down")

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError):
        asyncio.run(commit_with_purchase_events(FakeCdp(cancel_fails=True), EVENTS, commit))
    assert "bi-1" in caplog.text
    assert "VP1" not in caplog.text
