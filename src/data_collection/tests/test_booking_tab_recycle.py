"""Chromium từ chối tab khi thay tab định kỳ không được làm hỏng cả bước Booking (lượt local 07/10: "Failed to open a new tab"
đúng ở trang thứ `pages_before_recycle` khi chạy 1 tab)."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from collectors.booking_base import SitemapSource, _run_queue
from collectors.common import BlockBreaker, BrowserOptions, FetchResult, Paths, RawCache, StateDB


class FakePage:
    def __init__(self, context):
        self.context, self.closed = context, False

    async def close(self):
        self.closed = True
        self.context.pages.remove(self)

    def is_closed(self):
        return self.closed


class FakeContext:
    """Chromium giả: `broken` = từ chối mọi tab mới (như lỗi thật khi trình duyệt hỏng hoặc thiếu tài nguyên)."""

    def __init__(self, broken=False):
        self.pages, self.broken, self.dead = [], broken, False

    async def new_page(self):
        if self.broken or self.dead:
            raise RuntimeError('BrowserContext.new_page: Protocol error (Target.createTarget): Failed to open a new tab')
        page = FakePage(self)
        self.pages.append(page)
        return page

    def first_page(self):
        page = FakePage(self)
        self.pages.append(page)
        return page


class FakeSession:
    def __init__(self, context, restart_ok=True):
        self.context, self.restart_ok, self.restarts = context, restart_ok, 0

    async def fetch_html(self, page, url, *a, **k):
        if page.closed:
            raise RuntimeError('Target page, context or browser has been closed')
        return FetchResult(html='<h1>ok</h1>', final_url=url, title='ok', elapsed=0.0)

    async def restart(self):
        self.restarts += 1
        if not self.restart_ok:
            raise RuntimeError('không mở lại được')
        self.context = FakeContext()
        self.context.first_page()


class Source(SitemapSource):
    name = 'booking_hotels'

    def __init__(self, flaky=()):
        self.flaky = set(flaky)  # URL lỗi tạm thời ở lần mở đầu tiên

    def parse(self, html, url, meta):
        return {'name': url}

    def is_error_page(self, html):
        return False


class FlakySession(FakeSession):
    def __init__(self, context, flaky):
        super().__init__(context)
        self.flaky = set(flaky)

    async def fetch_html(self, page, url, *a, **k):
        if url in self.flaky:
            self.flaky.discard(url)
            raise TimeoutError('Page.goto: Timeout 60000ms exceeded')
        return await super().fetch_html(page, url, *a, **k)


class Limiter:
    async def wait(self, url):
        return None

    def penalise(self, url, seconds):
        return None


class Robots:
    async def allowed(self, url):
        return True


class Http:
    robots = Robots()


class Opts:
    concurrency, delay, max_attempts, full_cache = 1, 0.0, 3, False
    browser = replace(BrowserOptions(), pages_before_recycle=2)


class TabRecycleTests(unittest.TestCase):
    def run_queue(self, session, urls):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        paths = Paths(Path(tmp.name)).ensure()
        state = StateDB(paths)
        self.addCleanup(state.close)
        state.add_many('booking_hotels', [(u, i, {}) for i, u in enumerate(urls)])
        breaker = BlockBreaker(8)
        first = session.context.first_page()
        counts = asyncio.run(_run_queue(paths, Source(), Opts(), state, RawCache(paths, 'booking_hotels'), session,
                                        first, Limiter(), Http(), breaker, urls))
        return counts, breaker

    def test_recycling_tabs_keeps_the_queue_running(self):
        urls = [f'https://www.booking.com/hotel/vn/{n}.html' for n in range(7)]
        session = FakeSession(FakeContext())
        counts, breaker = self.run_queue(session, urls)
        self.assertEqual(counts.get('done'), 7)
        self.assertFalse(breaker.tripped)
        self.assertEqual(session.restarts, 0)

    def test_browser_that_refuses_tabs_is_restarted_once_and_the_queue_finishes(self):
        urls = [f'https://www.booking.com/hotel/vn/{n}.html' for n in range(5)]
        context = FakeContext()
        session = FakeSession(context)
        context.broken = True  # trình duyệt hỏng sau khi đã mở tab đầu
        counts, breaker = self.run_queue(session, urls)
        self.assertEqual((counts.get('done'), session.restarts, breaker.tripped), (5, 1, False))

    def test_retry_round_after_recycling_does_not_reuse_the_closed_first_tab(self):
        """Booking local 20:19 07/10: URL lỗi ở đầu lượt, thử lại cuối lượt sau khi tab đầu đã bị thay → 'has been closed'."""
        urls = [f'https://www.booking.com/hotel/vn/{n}.html' for n in range(6)]
        session = FlakySession(FakeContext(), flaky=[urls[0]])
        counts, breaker = self.run_queue(session, urls)
        self.assertEqual((counts.get('done'), counts.get('failed')), (6, None))
        self.assertFalse(breaker.tripped)

    def test_restart_failure_stops_quietly_and_keeps_unvisited_urls_pending(self):
        urls = [f'https://www.booking.com/hotel/vn/{n}.html' for n in range(5)]
        context = FakeContext()
        session = FakeSession(context, restart_ok=False)
        context.broken = True
        counts, breaker = self.run_queue(session, urls)  # không ném lỗi ra ngoài
        self.assertTrue(breaker.tripped)
        self.assertEqual(counts.get('done'), 2)
        self.assertEqual(counts.get('pending'), 3)


if __name__ == '__main__':
    unittest.main()
