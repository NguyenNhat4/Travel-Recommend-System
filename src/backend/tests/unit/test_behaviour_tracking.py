import asyncio
from datetime import date, datetime, timezone

import pytest

from src.backend.app.application.tracking.behaviour import BehaviourTracker, CatalogProduct, ProductNotFoundError

NOW = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)
HOTEL = CatalogProduct(product_id="nt-h-01", taxonomy="hotel", unit_price=3400000)


class Recorder:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


class Catalog:
    async def find_product(self, product_id):
        return HOTEL if product_id == HOTEL.product_id else None


def tracker(recorder):
    return BehaviourTracker(recorder, Catalog(), clock=lambda: NOW, new_event_id=lambda name: f"{name}:1")


def test_product_view_takes_taxonomy_from_catalog():
    recorder = Recorder()
    asyncio.run(tracker(recorder).track_product_view("VP1", "nt-h-01"))
    [event] = recorder.events
    assert (event.event_id, event.event_name, event.taxonomy, event.timestamp) == ("product_view:1", "product_view",
                                                                                   "hotel", NOW)


def test_product_view_of_unknown_product_is_rejected_and_not_recorded():
    recorder = Recorder()
    with pytest.raises(ProductNotFoundError):
        asyncio.run(tracker(recorder).track_product_view("VP1", "nt-h-99"))
    assert recorder.events == []


@pytest.mark.parametrize("cdp_user_id, query, offset, recorded", [
    ("VP1", "  resort Nha Trang  ", 0, True),
    (None, "resort Nha Trang", 0, False),   # anonymous or Agent (no JWT)
    ("VP1", "resort Nha Trang", 20, False),  # next page is not a new search
    ("VP1", "   ", 0, False),
])
def test_search_rules(cdp_user_id, query, offset, recorded):
    recorder = Recorder()
    tracker(recorder).track_search(cdp_user_id, query, offset)
    assert [e.search_query for e in recorder.events] == (["resort Nha Trang"] if recorded else [])


def test_add_to_cart_uses_catalog_price():
    recorder = Recorder()
    tracker(recorder).track_add_to_cart("VP1", HOTEL, quantity=2, using_date=date(2026, 10, 2))
    [event] = recorder.events
    assert (event.unit_price, event.quantity, event.using_date) == (3400000, 2, date(2026, 10, 2))
