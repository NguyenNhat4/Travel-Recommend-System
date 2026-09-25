"""Tải thêm kết quả tìm kiếm Booking: chỉ coi là "đủ" khi đủ số lượng hoặc đã hết kết quả, không phải khi bị gián đoạn."""
import asyncio
import unittest
from datetime import date
from types import SimpleNamespace

from collectors.booking_hotels import BookingHotels

CARD_HTML = ('<div data-testid="property-card"><a data-testid="title-link" href="/hotel/vn/x.vi.html">'
             '<div data-testid="title">X</div></a></div>')


class FakeLocator:
    def __init__(self, present, click):
        self._present = present
        self.first = SimpleNamespace(click=click)

    async def count(self):
        return 1 if self._present else 0


class FakePage:
    """Trang giả: mỗi lần bấm nút thêm `per_click` thẻ tới hết `total`; click_fails=True mô phỏng nút bị lớp phủ che."""

    def __init__(self, total, initial=20, per_click=20, click_fails=False):
        self.total, self.shown, self.per_click, self.click_fails = total, min(initial, total), per_click, click_fails
        self.clicks = 0
        self.mouse = SimpleNamespace(wheel=self._noop)
        self.keyboard = SimpleNamespace(press=self._noop)

    async def _noop(self, *a, **k):
        return None

    async def evaluate(self, script, arg=None):
        return self.shown

    async def wait_for_timeout(self, ms):
        return None

    async def content(self):
        return CARD_HTML * self.shown

    async def _click(self, timeout=None):
        self.clicks += 1
        if self.click_fails:
            raise TimeoutError("lớp phủ chặn con trỏ")
        self.shown = min(self.total, self.shown + self.per_click)

    def locator(self, selector):
        if "đăng nhập" in selector:
            return FakeLocator(False, self._click)
        return FakeLocator(self.shown < self.total, self._click)


def run(page, want):
    async def scenario():
        fast_calls = []

        async def set_fast(value):
            fast_calls.append(value)

        async def open_page(url, ready):
            return SimpleNamespace(html=CARD_HTML)

        async def wait(url):
            return None

        ctx = SimpleNamespace(session=SimpleNamespace(opts=SimpleNamespace(fast=True), set_fast=set_fast), open=open_page,
                              page=page, limiter=SimpleNamespace(wait=wait))
        html, complete = await BookingHotels(checkin=date(2026, 10, 15))._load_results(ctx, "Ha Long", want)
        return html, complete, fast_calls

    return asyncio.run(scenario())


class LoadResultsTests(unittest.TestCase):
    def test_enough_results_is_complete_and_restores_fast_mode(self):
        page = FakePage(total=300)
        _html, complete, fast_calls = run(page, 100)
        self.assertTrue(complete)
        self.assertGreaterEqual(page.shown, 100)
        self.assertEqual(fast_calls, [False, True])  # tắt --fast để tải thêm rồi bật lại như cũ

    def test_small_destination_that_runs_out_of_results_is_still_complete(self):
        page = FakePage(total=16)  # điểm đến chỉ có 16 kết quả: không có nút, cuộn không thêm thẻ
        html, complete, _ = run(page, 100)
        self.assertTrue(complete)
        self.assertEqual(html.count("property-card"), 16)

    def test_interrupted_loading_is_not_marked_complete(self):
        page = FakePage(total=300, click_fails=True)  # nút luôn bị che: chỉ có 20 thẻ đầu
        _html, complete, _ = run(page, 100)
        self.assertFalse(complete)  # trước đây coi là "xong" nên Hạ Long kẹt ở 16 khách sạn
        self.assertEqual(page.shown, 20)


if __name__ == "__main__":
    unittest.main()
