import unittest

from collectors.plan import Destination
from collectors.trip_combos import combo_routes, parse_combo_hotels, parse_flight_card

FLIGHT_HTML = """
<div class="fcc-card fcc-card--selected" role="button">
  <div class="fcc-segments">
    <div class="fcc-segment">
      <div class="fcc-segment-title">
        <div class="fcc-airline-logo-container"><img class="fcc-airline-logo" src="//pic.tripcdn.com/airline_logo/3x/vj.png" alt=""></div>
        <span class="fcc-segment-title-text">
          <span class="fcc-segment-date">15/10</span>
          <span class="fcc-segment-cabin" title="x">Hạng Phổ Thông</span>
          <span class="fcc-segment-duration">2g</span>
        </span>
      </div>
      <div class="fcc-flight-row"><div class="fcc-times">
        <div class="fcc-depart"><span class="fcc-time">15:15</span><span class="fcc-airport">SGN T1</span></div>
        <div class="fcc-arrive"><span class="fcc-time">17:15</span><span class="fcc-airport">HPH</span></div>
      </div></div>
    </div>
    <div class="fcc-segment">
      <div class="fcc-segment-title">
        <div class="fcc-airline-logo-container"><img class="fcc-airline-logo" src="//pic.tripcdn.com/airline_logo/3x/vj.png" alt=""></div>
        <span class="fcc-segment-title-text"><span class="fcc-segment-date">18/10</span></span>
      </div>
      <div class="fcc-flight-row"><div class="fcc-times">
        <div class="fcc-depart"><span class="fcc-time">17:50</span><span class="fcc-airport">HPH</span></div>
        <div class="fcc-arrive"><span class="fcc-time">19:50</span><span class="fcc-airport">SGN T1</span></div>
      </div></div>
    </div>
  </div>
</div>
"""

# Rút gọn từ HTML thật lấy qua browser 23/09/2026 (xem docstring collectors/trip_combos.py).
HOTEL_HTML = """
<div data-exposure-content="htl_recomd_type=0&HotelId=44319759&RoomId=2259690953&FltHotelPrice=3560500&show_more_icon=0" class="hotel-card-vs bg7">
  <div class="middle-info"><div class="poi">
    <div class="title-info"><span class="title"><span class="b fs4 mr4">Melia Vinpearl Hải Phòng Rivera</span></span>
      <i class="jji jji-star c5"></i><i class="jji jji-star c5"></i><i class="jji jji-star c5"></i><i class="jji jji-star c5"></i><i class="jji jji-star c5"></i>
    </div>
    <div class="position-info"><div class="mt8 fs1 c2">Trung tâm Hải Phòng/Chợ Sắt</div></div>
    <div class="mt8 dib mr8"><span class="dib com-score mr8"><span class="c7 b">9,3</span><span class="fs2 c7">/10</span></span>
      <span class="fs1 c2" data-analyze-aria-text="reviews_1">614 đánh giá</span></div>
  </div></div>
  <div class="df-room-type mt8 poi"><div class="room-info-box fs1"><div class="room-info-name">
    <div class="b category-name pt8 pb8"><span>Phòng Deluxe</span></div></div></div></div>
  <div class="right-info fs1"><div class="hotel-price"><div class="vs-price-content">
    <div class="origin-price-container"><div class="origin-price">
      <div class="origin-price-title"><span>Đặt riêng</span></div>
      <div class="origin-price-content">3.954.161<span class="price-currency">₫</span></div>
    </div></div>
    <div class="bundle-price"><div class="bundle-price-content">3.560.500<span class="price-currency">₫</span></div></div>
  </div></div></div>
</div>
"""

ORIGIN = Destination("TP. Hồ Chí Minh", "Ho Chi Minh City", None, None, ("SGN",))
DEST = Destination("Hải Phòng", "Hai Phong", None, None, ("HPH",), trip_hotel_city_id="6942")


class ParseFlightCardTests(unittest.TestCase):
    def test_parses_outbound_and_inbound_segments(self):
        flight = parse_flight_card(FLIGHT_HTML)
        self.assertIsNotNone(flight)
        self.assertEqual(flight["outbound"]["departAirport"], "SGN T1")
        self.assertEqual(flight["outbound"]["arriveAirport"], "HPH")
        self.assertEqual(flight["outbound"]["airlineCode"], "VJ")
        self.assertEqual(flight["inbound"]["departAirport"], "HPH")
        self.assertEqual(flight["inbound"]["arriveAirport"], "SGN T1")

    def test_no_card_returns_none(self):
        self.assertIsNone(parse_flight_card("<html></html>"))


class ParseComboHotelsTests(unittest.TestCase):
    def test_reads_price_and_ids_from_data_exposure_content_not_display_text(self):
        flight = parse_flight_card(FLIGHT_HTML)
        recs = parse_combo_hotels(HOTEL_HTML, flight, ORIGIN, DEST, "https://vn.trip.com/packages/list?x=1", "2026-09-23T00:00:00Z")
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["hotelId"], "44319759")
        self.assertEqual(r["roomId"], "2259690953")
        self.assertEqual(r["price"], 3560500)  # giá combo/người, từ FltHotelPrice trong data-exposure-content

    def test_separate_price_parses_dot_thousand_separators_correctly(self):
        # first_int() một mình sẽ cắt ở dấu chấm đầu tiên ("3.954.161" -> 3) — phải dùng parse_price().
        recs = parse_combo_hotels(HOTEL_HTML, None, ORIGIN, DEST, "u", "t")
        self.assertEqual(recs[0]["separatePrice"], 3954161)

    def test_identity_and_rating_fields(self):
        recs = parse_combo_hotels(HOTEL_HTML, None, ORIGIN, DEST, "u", "t")
        r = recs[0]
        self.assertEqual(r["hotelName"], "Melia Vinpearl Hải Phòng Rivera")
        self.assertEqual(r["starRating"], 5)
        self.assertEqual(r["reviewScore"], 9.3)
        self.assertEqual(r["reviewCount"], 614)
        self.assertEqual(r["roomType"], "Phòng Deluxe")
        self.assertEqual(r["fromCode"], "SGN")
        self.assertEqual(r["toCode"], "HPH")
        self.assertEqual(r["key"], "combo:SGN-HPH:44319759")

    def test_cards_without_a_valid_exposure_attribute_are_skipped(self):
        html = '<div class="hotel-card-vs" data-exposure-content="nothing useful here"></div>'
        self.assertEqual(parse_combo_hotels(html, None, ORIGIN, DEST, "u", "t"), [])

    def test_duplicate_hotel_ids_deduped(self):
        recs = parse_combo_hotels(HOTEL_HTML + HOTEL_HTML, None, ORIGIN, DEST, "u", "t")
        self.assertEqual(len(recs), 1)


class ComboRoutesTests(unittest.TestCase):
    def test_only_pairs_hubs_with_destinations_that_have_both_airport_and_hotel_city_id(self):
        hub = Destination("Hà Nội", "Hanoi", None, None, ("HAN",))
        with_both = Destination("Nha Trang", "Nha Trang", None, None, ("CXR",), trip_hotel_city_id="1777")
        no_hotel_id = Destination("Huế", "Hue", None, None, ("HUI",))  # có sân bay, không có trip_hotel_city_id
        no_airport = Destination("Sa Pa", "Sa Pa", None, None, (), trip_hotel_city_id="123")
        routes = combo_routes((hub, with_both, no_hotel_id, no_airport))
        self.assertEqual(routes, [(hub, with_both)])

    def test_hub_never_paired_with_itself(self):
        hcm = Destination("TP. Hồ Chí Minh", "Ho Chi Minh City", None, None, ("SGN",), trip_hotel_city_id="301")
        hanoi = Destination("Hà Nội", "Hanoi", None, None, ("HAN",), trip_hotel_city_id="286")
        routes = combo_routes((hcm, hanoi))
        self.assertNotIn((hcm, hcm), routes)
        self.assertIn((hcm, hanoi), routes)
        self.assertIn((hanoi, hcm), routes)


if __name__ == "__main__":
    unittest.main()
