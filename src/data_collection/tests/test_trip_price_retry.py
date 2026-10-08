"""Bước giá phòng Trip thử lại một lần các (khách sạn, ngày) chưa bắt được gói giá (lượt local 07/10: HTTP 200 nhưng 0 gói,
1/219 lượt làm cả bước `partial`)."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collectors import trip_live

PRICED = {'data': {'physicRoomMap': {'7': {'name': 'Deluxe'}},
                   'saleRoomMap': {'a': {'physicalRoomId': 7, 'priceInfo': {'price': 700000, 'currency': 'VND'}}}}}


class Response:
    url = 'https://vn.trip.com/restapi/soa2/x/getHotelRoomListOversea'
    status = 200

    async def json(self):
        return PRICED


class Navigation:
    status = 200

    async def text(self):
        return '<html></html>'


class Page:
    def __init__(self, browser):
        self.browser, self.handler = browser, None

    def on(self, event, handler):
        self.handler = handler

    def remove_listener(self, event, handler):
        self.handler = None

    async def route(self, *a, **k):
        return None

    async def goto(self, url, **k):
        self.browser.visits.append(url)
        if self.browser.visits.count(url) > self.browser.silent.get(url, 0):
            self.handler(Response())  # lần đầu của URL "im lặng": HTTP 200 nhưng không có gói giá
        return Navigation()

    async def evaluate(self, *a):
        return None

    async def close(self):
        return None


class Context:
    def __init__(self, browser):
        self.browser = browser

    async def new_page(self):
        return Page(self.browser)

    async def close(self):
        return None


class Browser:
    def __init__(self, silent):
        self.silent, self.visits = silent, []
        outer = self

        class Chromium:
            async def launch_persistent_context(self, **k):
                return Context(outer)

        self.chromium = Chromium()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def no_wait(*a, **k):
    await asyncio.sleep(0)


class TripPriceRetryTests(unittest.TestCase):
    def capture(self, silent_times):
        targets = [{'trip_hotel_id': '1', 'city_id': '1777'}]
        pairs = [('2026-10-21', '2026-10-22'), ('2026-11-06', '2026-11-07')]
        silent_url = trip_live.detail_url(targets[0], *pairs[0])
        browser = Browser({silent_url: silent_times})
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with patch.object(trip_live, 'async_playwright', lambda: browser), \
                patch.object(trip_live, 'next_start', no_wait), patch.object(trip_live, 'wait_for_prices', no_wait):
            results = asyncio.run(trip_live.capture_prices(targets, pairs, Path(tmp.name),
                                                           trip_live.LiveOptions(price_workers=1)))
        return {key: value[0] for key, value in results.items()}, browser.visits.count(silent_url)

    def test_missing_capture_is_retried_once_and_becomes_priced(self):
        statuses, visits = self.capture(silent_times=1)
        self.assertEqual(statuses, {('1', '2026-10-21'): 'priced', ('1', '2026-11-06'): 'priced'})
        self.assertEqual(visits, 2)

    def test_retry_is_only_once(self):
        statuses, visits = self.capture(silent_times=5)
        self.assertEqual(statuses[('1', '2026-10-21')], 'missing')
        self.assertEqual(visits, 2)


if __name__ == '__main__':
    unittest.main()
