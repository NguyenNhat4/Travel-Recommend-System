import json
import unittest

from collectors.trip_hotels import (
    extract_anchored_json,
    parse_hotel_detail,
    parse_search_cards,
    scroll_done,
)


class ExtractAnchoredJsonTests(unittest.TestCase):
    def test_extracts_object_with_nested_braces_and_escaped_quotes(self):
        html = (
            '<script>window.x = {"a":1,"hotelDetailResponse":'
            '{"hotelBaseInfo":{"masterHotelId":123,'
            '"nameInfo":{"name":"Test \\"Hotel\\" {ABC}"}}},"b":2};</script>'
        )
        obj = extract_anchored_json(html, '"hotelDetailResponse":')
        self.assertIsNotNone(obj)
        self.assertEqual(obj["hotelBaseInfo"]["masterHotelId"], 123)
        self.assertIn("ABC", obj["hotelBaseInfo"]["nameInfo"]["name"])

    def test_missing_anchor_returns_none(self):
        self.assertIsNone(extract_anchored_json("<html>no data here</html>", '"hotelDetailResponse":'))

    def test_malformed_json_returns_none_instead_of_raising(self):
        html = '"hotelDetailResponse":{"a": ,}'
        self.assertIsNone(extract_anchored_json(html, '"hotelDetailResponse":'))

    def test_next_flight_chunks_preserve_unicode_and_escaped_strings(self):
        expected = {"hotelBaseInfo": {"name": 'Khách sạn "Biển"', "id": 123}}
        flight = 'a:["$",null,{"hotelDetailResponse":' + json.dumps(expected, ensure_ascii=False) + '}]'
        split = flight.index('hotelDetailResponse') + 8
        html = ''.join('<script>self.__next_f.push(' + json.dumps([1, part]) + ')</script>'
                       for part in (flight[:split], flight[split:]))
        self.assertEqual(extract_anchored_json(html, '"hotelDetailResponse":'), expected)

    def test_null_does_not_capture_unrelated_object(self):
        self.assertIsNone(extract_anchored_json(
            '"hotelDetailResponse":null,"unrelated":{"id":9}', '"hotelDetailResponse":'))


class ScrollDoneTests(unittest.TestCase):
    def test_stops_once_budget_reached(self):
        self.assertTrue(scroll_done(count=15, want=15, stalled=0))
        self.assertFalse(scroll_done(count=14, want=15, stalled=0))

    def test_stops_after_stall_limit_even_under_budget(self):
        self.assertTrue(scroll_done(count=3, want=15, stalled=3))
        self.assertFalse(scroll_done(count=3, want=15, stalled=2))


CARD_HTML = """
<div class="hotel-card" id="999">
  <div class="hotel-info"><div class="hotel-head"><div class="hotel-title">
    <a class="hotelName" href="/hotels/detail/?hotelId=999&cityId=1777">Khach San Test</a>
  </div></div>
  <div class="hotelStar" aria-label="Điểm đánh giá 4/5"></div>
  <div class="hotel-comment">8,5/10 Rất tốt 120 đánh giá</div>
  <div class="room-price">Ưu đãi -100.000₫ 900.000₫ 800.000₫ Tổng giá: 900.000₫ bao gồm thuế</div>
  </div>
  <img class="m-lazyImg__img" src="http://img/x.jpg">
</div>
"""


class ParseSearchCardsTests(unittest.TestCase):
    def test_picks_final_price_not_the_discount_or_original_price(self):
        cards = parse_search_cards(CARD_HTML)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["listPrice"], 800000)

    def test_extracts_identity_and_rating_fields(self):
        cards = parse_search_cards(CARD_HTML)
        card = cards[0]
        self.assertEqual(card["hotelId"], "999")
        self.assertEqual(card["name"], "Khach San Test")
        self.assertEqual(card["starRating"], 4)
        self.assertEqual(card["reviewScore"], 8.5)
        self.assertEqual(card["reviewCount"], 120)
        self.assertEqual(card["image"], "http://img/x.jpg")

    def test_cards_without_a_detail_link_are_skipped(self):
        html = '<div class="hotel-card" id="1"><div class="hotel-title"></div></div>'
        self.assertEqual(parse_search_cards(html), [])

    def test_ssr_card_with_span_name_is_discovered(self):
        html = '<div class="hotel-card" id="10201344"><span class="hotelName">Ale Nha Trang Hotel</span></div>'
        cards = parse_search_cards(html)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["hotelId"], "10201344")
        self.assertEqual(cards[0]["name"], "Ale Nha Trang Hotel")

    def test_duplicate_hotel_ids_deduped(self):
        html = CARD_HTML + CARD_HTML
        self.assertEqual(len(parse_search_cards(html)), 1)


DETAIL_HTML = (
    '<script>window.x = {"hotelDetailResponse":{'
    '"hotelBaseInfo":{"masterHotelId":999,"nameInfo":{"name":"Khach San Test"},'
    '"hotelCategory":{"categoryName":"Khach san"},'
    '"positionInfo":{"cityName":"Nha Trang","mapCoordinate":[{"latitude":"12.24","longitude":"109.19"}]},'
    '"highlightsModule":{"highlightsItemList":[{"title":"Gan bien"}]}},'
    '"roomList":{"roomList":[{"key":"1","subRoomList":[{"roomToken":"a"}]}],'
    '"physicRoomMap":{"1":{"id":1,"name":"Deluxe","pictureInfo":[{"url":"http://img/1.jpg"}]}}}}};</script>'
)
CARD = {
    "hotelId": "999", "name": "Khach San Test", "starRating": 4, "reviewScore": 8.5,
    "reviewScoreScale": 10.0, "reviewCount": 120, "listPrice": 800000, "listCurrency": "VND",
    "image": "http://img/x.jpg",
}


class ParseHotelDetailTests(unittest.TestCase):
    def test_merges_card_and_detail_blob_fields(self):
        rec = parse_hotel_detail(
            DETAIL_HTML, "https://vn.trip.com/hotels/detail/?hotelId=999", CARD, "2026-09-23T00:00:00Z",
            checkin="2026-10-15", checkout="2026-10-16", adults=2,
        )
        self.assertIsNotNone(rec)
        self.assertEqual(rec["recordType"], "trip_hotel")
        self.assertEqual(rec["source"], "trip_hotels")
        self.assertEqual(rec["key"], "hotel:999")
        self.assertEqual(rec["name"], "Khach San Test")
        self.assertEqual(rec["latitude"], 12.24)
        self.assertEqual(rec["longitude"], 109.19)
        self.assertEqual(rec["rooms"][0]["name"], "Deluxe")
        self.assertEqual(rec["rooms"][0]["rateCount"], 1)
        # Không có giá gói phòng (getHotelRoomListOversea) trong blob nên fallback về giá thẻ danh sách.
        self.assertEqual(rec["minPrice"], 800000)
        self.assertEqual(rec["priceQuery"], {"checkin": "2026-10-15", "checkout": "2026-10-16", "adults": 2, "currency": "VND"})

    def test_falls_back_to_card_fields_when_detail_blob_missing(self):
        # Blob hotelDetailResponse biến mất khỏi DOM sau hydrate (xem docstring trip_hotels.py) — vẫn phải
        # cho ra bản ghi dùng được từ dữ liệu thẻ danh sách, không được trả None.
        rec = parse_hotel_detail("<html>không có blob</html>", "https://vn.trip.com/hotels/detail/?hotelId=999", CARD, "2026-09-23T00:00:00Z")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["name"], "Khach San Test")
        self.assertEqual(rec["minPrice"], 800000)
        self.assertEqual(rec["rooms"], [])

    def test_missing_name_and_id_returns_none(self):
        rec = parse_hotel_detail("<html></html>", "https://vn.trip.com/hotels/detail/", {}, "2026-09-23T00:00:00Z")
        self.assertIsNone(rec)


if __name__ == "__main__":
    unittest.main()
