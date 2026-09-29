"""API tour Vinpearl gọi từ trong trang booking.vinpearl.com: header phải đi đúng tham số của BrowserSession.fetch_json."""
import asyncio
import tempfile
import unittest
from pathlib import Path

from collectors.common import BrowserOptions, BrowserSession, Paths
from collectors.vinpearl import API_HEADERS, VinpearlCollector, VinpearlOptions


class FakeSession(BrowserSession):
    def __init__(self):  # không mở Chromium; dùng đúng chữ ký fetch_json thật
        self.calls = []

    async def fetch_json(self, page, url, *, method="GET", body=None, headers=None):
        self.calls.append((page, url, headers))
        return 200, {"data": {"items": []}}


class VinpearlBrowserApiTests(unittest.TestCase):
    def test_tour_api_passes_headers_by_keyword_and_caches_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            collector = VinpearlCollector(Paths(Path(tmp)).ensure(),
                                          VinpearlOptions(browser=BrowserOptions(), delay=0, refresh=True))
            session = FakeSession()

            async def page():
                return "page"

            async def browser():
                return session

            collector._ensure_api_page, collector._browser = page, browser
            url = "https://booking-tour-api.vinpearl.com/api/frontend/tour?pageIndex=1&pageSize=100"
            data = asyncio.run(collector._browser_json("api-tour-list-1", url))
        self.assertEqual(data, {"data": {"items": []}})
        self.assertEqual(session.calls, [("page", url, API_HEADERS)])


if __name__ == "__main__":
    unittest.main()
