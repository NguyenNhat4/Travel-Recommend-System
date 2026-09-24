import unittest

from collectors.booking_attractions import BookingAttractions, _price_fragment
from collectors.booking_base import SitemapSource
from collectors.textutil import parse_price


class NeedsScrollBeforeReadTests(unittest.TestCase):
    def test_default_is_off_for_other_sources(self):
        # booking_hotels/agoda_hotels không cần cuộn — mặc định phải là False, đổi ở đây coi như phá nguồn khác.
        self.assertFalse(SitemapSource.needs_scroll_before_read)

    def test_booking_attractions_opts_in(self):
        # Khối giá lazy-load theo viewport, ready_selector không đợi tới đó (xem docstring collectors/booking_base.py).
        self.assertTrue(BookingAttractions.needs_scroll_before_read)


class PriceFragmentTests(unittest.TestCase):
    def test_extracts_usd_price_from_real_label_text(self):
        # Văn bản thật lấy từ trang booking.com 23/09/2026 (xem lịch sử hội thoại lúc sửa bug này) — trang trả
        # USD dù đã truyền selected_currency=VND trong URL, to_vnd() ở normalise.py lo phần đổi tiền.
        text = "Giá thấp nhất (US$235) lần đầu có vào 23 thg 9"
        frag = _price_fragment(text)
        self.assertEqual(frag, "US$235")
        price, currency = parse_price(frag, "VND")
        self.assertEqual(price, 235)
        self.assertEqual(currency, "USD")

    def test_empty_text_returns_empty_fragment(self):
        self.assertEqual(_price_fragment(""), "")
        self.assertEqual(_price_fragment(None), "")


if __name__ == "__main__":
    unittest.main()
