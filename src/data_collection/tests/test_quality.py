"""Offline regressions for source parsing, venue matching and catalog corrections."""
import copy
import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

import normalise as n
from collectors.agoda_hotels import parse_agoda_html
from collectors.venues import Venue, VenueMatcher


class QualityTests(unittest.TestCase):
    def test_agoda_reads_source_description_and_address_without_jsonld(self):
        html = '''<h1>Khách sạn thử nghiệm</h1>
        <span data-element-name="property-short-description">Khách sạn có hồ bơi và Wi-Fi.</span>
        <span data-selenium="hotel-address-map">15 Ng&amp;#244; Quyền, Hà Nội</span>
        <span data-element-name="cheapest-room-price-property-nav-bar" data-element-cheapest-room-price="1200000">1.200.000 ₫</span>'''
        p = parse_agoda_html(html, "https://www.agoda.com/vi-vn/test/hotel/hanoi-vn.html",
                             {"fetchedAt": "2026-09-15T00:00:00Z"})
        self.assertEqual(p["description"], "Khách sạn có hồ bơi và Wi-Fi.")
        self.assertIn("Ngô Quyền", p["address"]["street"])
        self.assertEqual(p["minPrice"], 1200000)
        self.assertEqual(p["crawledAt"], "2026-09-15T00:00:00Z")
        self.assertIsNone(p["latitude"])

    def test_agoda_keeps_missing_price_and_description_when_source_has_neither(self):
        p = parse_agoda_html("<h1>Test Hotel</h1>", "https://www.agoda.com/vi-vn/test/hotel/hanoi-vn.html")
        self.assertFalse(p["description"])
        self.assertIsNone(p["minPrice"])

    def test_booking_rooms_have_language_for_their_actual_description(self):
        prop, rooms = n.booking_hotel({"hotelId": 1, "name": "Khách sạn thử nghiệm", "descriptionShort": "Khách sạn nằm ở trung tâm thành phố.",
                                      "rooms": [{"roomId": "a", "name": "Phòng giường đôi hướng biển", "maxOccupancy": 2}]}, {})
        self.assertEqual(prop["attributes"]["descriptionLang"], "vi")
        self.assertEqual(rooms[0]["attributes"]["descriptionLang"], "vi")

    def test_trip_hotel_maps_to_product_schema_with_no_rooms(self):
        # trip_hotel() cố tình không trả rooms (chưa parse đủ giá gói phòng) — xem docstring collectors/trip_hotels.py.
        prop, rooms = n.trip_hotel({
            "hotelId": "999", "name": "Khách sạn thử nghiệm", "city": "Nha Trang", "province": "Khánh Hòa",
            "minPrice": 800000, "currency": "VND", "latitude": 12.24, "longitude": 109.19,
        }, {})
        self.assertEqual(prop["taxonomy"], "hotel")
        self.assertEqual(prop["attributes"]["level"], "property")
        self.assertEqual(prop["unitPrice"], 800000)
        self.assertEqual(prop["sourceRef"], "trip:hotel:999")
        self.assertEqual(rooms, [])

    def test_trip_combo_product_uses_flight_hotel_price_not_separate_price(self):
        c = n.trip_combo_product({
            "key": "combo:SGN-HPH:44319759", "fromCode": "SGN", "toCode": "HPH",
            "fromCity": "TP. Hồ Chí Minh", "toCity": "Hải Phòng", "destination": "Hải Phòng",
            "hotelName": "Melia Vinpearl Hải Phòng Rivera", "roomType": "Phòng Deluxe",
            "price": 3560500, "separatePrice": 3954161, "flight": {},
        })
        self.assertEqual(c["taxonomy"], "combo")
        self.assertEqual(c["unitPrice"], 3560500)
        self.assertEqual(c["attributes"]["comboKind"], "trip_real_flight_hotel")
        self.assertEqual(c["attributes"]["separatePrice"], 3954161)
        self.assertEqual(c["sourceRef"], "trip:combo:SGN-HPH:44319759")
        # Trang combo không có toạ độ khách sạn thật — phải có toạ độ tâm điểm đến, nếu không
        # drop_missing_coordinates() sẽ loại bỏ toàn bộ combo (bug thật đã gặp khi chạy staging 23/09/2026).
        self.assertIsNotNone(c["attributes"]["latitude"])
        self.assertIsNotNone(c["attributes"]["longitude"])
        self.assertEqual(c["attributes"]["locationPrecision"], "destination")

    def test_trip_combo_product_has_no_coordinates_for_unknown_destination(self):
        c = n.trip_combo_product({
            "key": "combo:XXX-YYY:1", "fromCity": "A", "toCity": "B", "destination": "Không tồn tại",
            "hotelName": "X", "roomType": "Y", "price": 100000, "flight": {},
        })
        self.assertIsNone(c["attributes"].get("latitude"))

    def test_trip_combo_product_requires_a_price(self):
        self.assertIsNone(n.trip_combo_product({"key": "combo:SGN-HPH:1", "hotelName": "X", "price": None}))

    def test_booking_attraction_falls_back_to_destination_center_coordinates(self):
        # booking_attraction_product() chưa từng lấy toạ độ thật (lỗ hổng có sẵn từ trước, không phải mới) —
        # phát hiện lúc sửa bug giá cho Ninh Bình/Cát Bà 23/09/2026: nếu không có fallback này,
        # drop_missing_coordinates() sẽ loại 100% sản phẩm từ nguồn này, y hệt bug combo trước đó.
        p = n.booking_attraction_product({
            "name": "Ninh Binh Day Tour: Hoa Lu, Trang An", "city": "Hà Nội", "price": 46, "currency": "USD",
            "productId": "abc123",
        }, {"USD": 23000})
        self.assertEqual(p["destination"], "Ninh Bình")
        self.assertIsNotNone(p["attributes"]["latitude"])
        self.assertIsNotNone(p["attributes"]["longitude"])
        self.assertEqual(p["attributes"]["locationPrecision"], "destination")
        self.assertEqual(p["unitPrice"], 46 * 23000)

    def test_audience_city_does_not_prevent_matching_actual_ticket_venue(self):
        venue = Venue("nam-hoi-an", "VinWonders Nam Hội An", "Hội An", aliases=["vinwonders nam hoi an"],
                      latitude=15.78878, longitude=108.410788, status="auto", source="osm:W1")
        name = "[Ưu Đãi Người Đà Nẵng] [Mua 2 Tặng 1] Vé vào cửa tiêu chuẩn"
        p = {"name": name, "destination": "Đà Nẵng", "attributes": {},
             "_meta": {"imageUrlSlug": "vinwonders-nam-hoi-an-ve-vao-cua"}}
        n.assign_venue_locations([p], [venue])
        self.assertEqual(p["destination"], "Hội An")
        self.assertEqual(p["attributes"]["latitude"], 15.78878)
        # Listing-only records may have an image URL but no imageUrlSlug field.
        listing = n.vinpearl_tour_product({"name": name, "tourCode": "TEST", "destinationName": "Quảng Nam",
                                          "images": ["https://example.org/tours/id_vinwonders-nam-hoi-an-ve-vao-cua.jpg"]}, date(2026, 9, 16))
        n.assign_venue_locations([listing], [venue])
        self.assertEqual(listing["attributes"]["venue"], venue.name)
        self.assertEqual(listing["attributes"]["latitude"], 15.78878)
        # A real venue name in brackets must still protect against a wrong island/city.
        wrong = Venue("grand-world-hanoi", "Mega Grand World Hà Nội", "Hà Nội", aliases=["grand world"])
        self.assertIsNone(VenueMatcher([wrong]).match(name="[Grand World Phú Quốc] Vé trải nghiệm")[0])

    def test_nearby_apartments_with_different_names_are_kept_separate(self):
        def hotel(pid, name, src):
            return {"productId": pid, "name": name, "destination": "Quy Nhơn", "attributes": {"latitude": 13.756, "longitude": 109.216},
                    "_meta": {"src": src}}
        a = hotel("a", "FLC Sea Tower Quy Nhon Apartment", "booking")
        b = hotel("b", "FLC Sea Tower - The Beach Quy Nhon", "agoda")
        self.assertEqual(len(n.cluster_hotels([a, b], 88)[0]), 2)
        b["name"] = a["name"]
        self.assertEqual(len(n.cluster_hotels([a, b], 88)[0]), 1)

    def test_destination_corrections_are_scoped_and_preserve_source_fields(self):
        p = {"sourceRef": "trip:attraction:1", "destination": "Đà Lạt", "name": "Mũi Kê Gà", "description": "Nội dung nguồn",
             "unitPrice": None, "attributes": {"latitude": 10.695261, "longitude": 107.99156}}
        untouched = copy.deepcopy(p)
        untouched["sourceRef"] = "trip:attraction:2"
        before = copy.deepcopy(untouched)
        self.assertEqual(n.apply_destination_overrides([p, untouched], {p["sourceRef"]: ("Phan Thiết", "source evidence")}), 1)
        self.assertEqual(untouched, before)
        self.assertEqual(p["attributes"]["originalDestination"], "Đà Lạt")
        self.assertEqual(p["description"], before["description"])
        self.assertIsNone(p["unitPrice"])
        self.assertEqual(p["attributes"]["latitude"], before["attributes"]["latitude"])

    def test_quality_report_is_read_only_and_updates_missing_fields(self):
        p = {"name": "Test", "taxonomy": "attraction", "destination": "Hà Nội", "sourceRef": "test:1", "unitPrice": None,
             "description": None, "attributes": {}}
        before = copy.deepcopy(p)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.csv"
            n.write_quality_review([p], path)
            with path.open(encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertIn("thiếu giá", rows[0]["issues"])
            self.assertIn("thiếu mô tả", rows[0]["issues"])
            self.assertEqual(p, before)

    def test_rule_based_filter_drops_non_tourism_places_but_keeps_real_attractions(self):
        for name, reason in (("Hanwha Life Việt Nam - SO Huế", "văn phòng bảo hiểm"),
                             ("Trung tâm tiêm chủng VNVC Thành Phố Vinh", "cơ sở y tế"),
                             ("Taxi Quy Nhơn Xanh", "hãng taxi / cho thuê xe"),
                             ("Xuân Tính Motorbike Rental - Cho Thuê Xe Máy Quy Nhơn", "hãng taxi / cho thuê xe"),
                             ("Ngân hàng Vietcombank Đà Nẵng", "ngân hàng"),
                             ("Đại lý Vé Nhà hát Đó", "đại lý / công ty lữ hành"),
                             ("Safari Cafe", "quán ăn / cà phê")):
            self.assertEqual(n.non_tourism_reason(name), reason, name)
        for name in ("Sun World Hạ Long", "Bãi biển Mỹ Khê", "Tháp Bà Ponagar", "Chợ đêm Đà Lạt", "Hội quán Phúc Kiến",
                     "Bảo tàng Hồ Chí Minh", "Vịnh Hạ Long", "Nhà thờ Đức Bà", "Phố cổ Hội An", "Hòn Thơm"):
            self.assertIsNone(n.non_tourism_reason(name), name)
        self.assertIsNone(n.non_tourism_reason(None))

    def test_hotel_granularity_flags_rooms_and_entire_places_only_with_evidence(self):
        def product(pid, name, level, parent=None, kind=None, desc=""):
            return {"productId": pid, "name": name, "taxonomy": "hotel", "description": desc,
                    "attributes": {"level": level, "parentProductId": parent, "propertyType": kind}}
        products = [
            product("h1", "Khách sạn Có Phòng", "property"), product("r1", "Khách sạn Có Phòng - Deluxe", "room", "h1"),
            product("h2", "Khách sạn Chỉ Agoda", "property"),
            product("h3", "Villa Biển Xanh", "property", kind="biệt thự"), product("h4", "Căn hộ Sea View", "property", kind="Căn hộ"),
            product("h5", "Căn hộ dịch vụ Sao", "property", kind="căn hộ dịch vụ"),
            product("h6", "Nhà Gỗ Đà Lạt", "property", desc="Cho thuê nguyên căn 3 phòng ngủ"),
            product("h7", "Villa Nhưng Là Khách Sạn", "property"),  # chỉ có tên "villa": không đủ bằng chứng
        ]
        n.annotate_hotel_granularity(products)
        by = {p["productId"]: p["attributes"] for p in products}
        self.assertTrue(by["h1"]["hasRoomRows"])
        self.assertFalse(by["h2"]["hasRoomRows"])
        self.assertNotIn("rentalUnit", by["h1"])
        self.assertEqual(by["h3"]["rentalUnit"], "entire_place")
        self.assertEqual(by["h4"]["rentalUnit"], "entire_place")
        self.assertNotIn("rentalUnit", by["h5"])
        self.assertEqual(by["h6"]["rentalUnit"], "entire_place")
        self.assertIn("nguyên căn", by["h6"]["rentalUnitEvidence"].lower().replace("nguyen can", "nguyên căn"))
        self.assertNotIn("rentalUnit", by["h7"])
        self.assertNotIn("hasRoomRows", by["r1"])  # chỉ ghi ở dòng cơ sở

    def test_location_warnings_are_dropped_with_their_children_but_vinpearl_is_kept(self):
        def product(pid, ref, warning=None, parent=None, level="property", taxonomy="hotel"):
            attrs = {"level": level, "parentProductId": parent, "latitude": 10.0, "longitude": 106.0}
            if warning:
                attrs["locationWarning"] = warning
            return {"productId": pid, "sourceRef": ref, "name": pid, "taxonomy": taxonomy, "destination": "X", "attributes": attrs}
        products = [
            product("h1", "booking:hotel:1", "cách tâm Hà Nội 629 km"),
            product("r1", "booking:hotel:1:room:a", parent="h1", level="room"),          # con không có cảnh báo riêng: vẫn bị xoá
            product("r2", "booking:hotel:1:room:b", "cách tâm Hà Nội 629 km", "h1", "room"),
            product("h2", "booking:hotel:2"),                                             # sạch: giữ
            product("r3", "booking:hotel:2:room:a", parent="h2", level="room"),
            product("a1", "trip:attraction:9", "cách tâm Pleiku 123 km", taxonomy="attraction", level=None),
            product("v1", "vinpearl:hotel:x", "trùng toạ độ với khách sạn Vinpearl khác"),  # Vinpearl luôn giữ
            {**product("v2", "booking:hotel:4139520", "cách tâm Biên Hòa 1071 km"), "name": "Meliá Vinpearl Phu Ly"},  # thương hiệu Vinpearl
        ]
        kept, removed = n.drop_location_warnings(products)
        self.assertEqual({p["productId"] for p in kept}, {"h2", "r3", "v1", "v2"})
        self.assertEqual({p["productId"] for p, _ in removed}, {"h1", "r1", "r2", "a1"})
        reasons = {p["productId"]: why for p, why in removed}
        self.assertIn("xa tâm điểm đến", reasons["h1"])
        self.assertIn("thuộc sản phẩm bị xoá", reasons["r1"])
        ids = {p["productId"] for p in kept}
        self.assertTrue(all(p["attributes"].get("parentProductId") in ids | {None} for p in kept))  # không có dòng mồ côi
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "excluded.csv"
            n.write_location_exclusions(removed, path)
            with path.open(encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual({r["sourceRef"] for r in rows}, {"booking:hotel:1", "booking:hotel:1:room:a",
                                                            "booking:hotel:1:room:b", "trip:attraction:9"})

    def test_missing_coordinates_and_orphans_are_dropped_with_children_but_vinpearl_is_kept(self):
        def product(pid, ref, lat=10.0, parent=None, level="property", name=None):
            return {"productId": pid, "sourceRef": ref, "name": name or pid, "taxonomy": "hotel", "destination": "X",
                    "attributes": {"level": level, "parentProductId": parent, "latitude": lat, "longitude": 106.0 if lat is not None else None}}
        products = [product("h1", "booking:hotel:1", lat=None), product("r1", "booking:hotel:1:r", parent="h1", level="room"),
                    product("h2", "booking:hotel:2"), product("r2", "booking:hotel:2:r", parent="h2", level="room"),
                    product("v1", "vinpearl:hotel:x", lat=None), product("o1", "booking:hotel:9:r", parent="gone", level="room")]
        kept, removed = n.drop_missing_coordinates(products)
        self.assertEqual({p["productId"] for p in kept}, {"h2", "r2", "v1", "o1"})
        self.assertEqual({p["productId"] for p, _ in removed}, {"h1", "r1"})
        kept, orphans = n.drop_orphans(kept)  # o1 mồ côi vì cha "gone" không tồn tại
        self.assertEqual({p["productId"] for p in kept}, {"h2", "r2", "v1"})
        self.assertEqual([p["productId"] for p, _ in orphans], ["o1"])

    def test_trip_flight_times_are_utc_and_become_vietnam_time(self):
        self.assertEqual(n._hhmm("2026-10-10T00:10:00.000Z"), "07:10")
        # chuyến bay sớm qua nửa đêm UTC: giờ và ngày đều phải sang ngày kế tiếp theo giờ Việt Nam
        self.assertEqual(n._hhmm("2026-10-04T23:45:00.000Z"), "06:45")
        self.assertEqual(n._ict_date("2026-10-04T23:45:00.000Z"), "2026-10-05")
        self.assertEqual(n._ict_iso("2026-10-04T23:45:00.000Z"), "2026-10-05T06:45:00+07:00")
        self.assertEqual(n._hhmm("2026-10-04T09:30:00"), "09:30")  # không có múi giờ: coi là giờ Việt Nam
        self.assertIsNone(n._hhmm(None))
        self.assertIsNone(n._ict_date("không phải ngày"))

    def test_trip_flights_are_available_with_dates_and_carry_no_extra_flags(self):
        record = {"fromCity": "Nha Trang", "toCity": "TP. Hồ Chí Minh", "fromCode": "nha", "toCode": "sgn",
                  "fromAirports": ["CXR"], "toAirports": ["SGN"], "crawledAt": "2026-09-19T05:37:38Z",
                  "url": "https://vn.trip.com/flights/x", "oneWay": {"lowPrice": 600000}, "flights": [
                      {"flightNumber": "VJ609", "airline": "VietJet Air", "airlineCode": "VJ", "from": "CXR", "to": "SGN",
                       "departureTime": "2026-10-04T23:45:00.000Z", "arrivalTime": "2026-10-05T00:55:00.000Z",
                       "durationMinutes": 70, "nonstop": True, "price": 665000},
                      {"flightNumber": "VJ609", "airline": "VietJet Air", "airlineCode": "VJ", "from": "CXR", "to": "SGN",
                       "departureTime": "2026-10-19T00:00:00.000Z", "arrivalTime": "2026-10-19T01:00:00.000Z",
                       "durationMinutes": 60, "nonstop": True, "price": 700000},
                      {"flightNumber": "VN1", "airline": "Vietnam Airlines", "from": "CXR", "to": "SGN",
                       "departureTime": "2026-10-10T13:55:00.000Z", "arrivalTime": "2026-10-10T15:00:00.000Z",
                       "durationMinutes": 65, "price": None}]}
        route, *flights = n.trip_route_products(record, 0)
        by = {f["attributes"]["flightNumber"]: f for f in flights}
        vj = by["VJ609"]
        self.assertTrue(vj["available"])
        self.assertEqual((vj["availableFrom"], vj["availableTo"]), ("2026-10-05", "2026-10-19"))
        self.assertEqual(vj["attributes"]["datesSeen"], ["2026-10-05", "2026-10-19"])
        self.assertEqual(vj["attributes"]["departureTimeLocal"], "06:45")
        self.assertEqual(vj["attributes"]["departureAt"], "2026-10-05T06:45:00+07:00")
        self.assertIn("(06:45)", vj["name"])
        self.assertIn("cất cánh 06:45", vj["description"])
        self.assertFalse(by["VN1"]["available"])  # không có giá thì không đánh dấu còn chuyến
        self.assertTrue(route["available"])
        self.assertEqual((route["availableFrom"], route["availableTo"]), ("2026-10-05", "2026-10-19"))
        for p in [route, *flights]:
            for extra in ("bookable", "priceKind", "availabilityStatus"):
                self.assertNotIn(extra, p["attributes"])

    def test_route_city_falls_back_to_the_airport_destination(self):
        record = {"fromCity": "Điện Biên Phủ", "toCity": "Hà Nội", "fromCode": "din", "toCode": "han",
                  "fromAirports": ["DIN"], "toAirports": ["HAN"], "crawledAt": "2026-09-19T05:37:38Z",
                  "url": "https://vn.trip.com/flights/x", "oneWay": {"lowPrice": 900000}, "flights": [
                      {"flightNumber": "VN1807", "airline": "Vietnam Airlines", "from": "DIN", "to": "HAN",
                       "departureTime": "2026-10-10T12:35:00.000Z", "arrivalTime": "2026-10-10T13:40:00.000Z",
                       "durationMinutes": 65, "price": 900000}]}
        route, flight = n.trip_route_products(record, 0)
        self.assertEqual(route["attributes"]["originCity"], "Điện Biên")  # khớp điểm đến của /destinations
        self.assertEqual(route["name"], "Vé máy bay Điện Biên - Hà Nội")
        self.assertIn("Điện Biên - Hà Nội", flight["name"])
        self.assertEqual(n._route_city("Vân Đồn", ["VDO"], "vdo"), "Vân Đồn")  # tên khớp alias thì giữ, không đổi theo sân bay
        self.assertEqual(n._route_city("Nơi lạ", ["XXX"], None), "Nơi lạ")

    def test_booking_tour_destination_ignores_departure_city(self):
        cases = {
            "From Hanoi: Sapa Trek, Cat Cat Village & Fansipan Summit Tour": "Sa Pa",
            "Pu Luong 2 Days 1 Night tour from Hanoi": "Thanh Hóa",
            "From Hanoi to Dien Bien Phu: 3 Day Adventure": "Điện Biên",
            "Hue to DMZ Vinh Moc Tunnels and Khe Sanh Base Tour": "Quảng Trị",
            "Hanoi: Ha Long Bay Day Cruise with Buffet, Kayak& Sunset Party": "Hạ Long",
            "Hanoi to Cat Ba: 2-Day Cat Ba National Park & Lan Ha Bay Tour": "Cát Bà",
            "From Saigon: Black Virgin Mountain, Cao Dai Temple & Cu Chi 1Day": "Tây Ninh",
            "Cai Rang Floating market 1 Day Tour from Ho Chi Minh City": "Cần Thơ",
            "Hanoi Imperial Citadel Tour": "Hà Nội",
            "Mekong Delta Discovery Day Tours": None,
        }
        for name, expected in cases.items():
            self.assertEqual(n.tour_destination(name), expected, name)
        # Tên không nêu nơi đến: giữ cách cũ (thành phố khởi hành từ `city`).
        p = n.booking_attraction_product({"name": "HCM: 2-Day Mekong Delta Floating Market", "city": "TP. Hồ Chí Minh",
                                          "price": 50, "currency": "USD", "productId": "x"}, {"USD": 26000})
        self.assertEqual(p["destination"], "TP. Hồ Chí Minh")
        p = n.booking_attraction_product({"name": "Pu Luong Trek from Hanoi", "city": "Hà Nội",
                                          "price": 50, "currency": "USD", "productId": "y"}, {"USD": 26000})
        self.assertEqual(p["destination"], "Thanh Hóa")

    def test_tuyen_quang_hotel_name_is_not_a_destination(self):
        self.assertEqual(n.normalise_destination("Vinpearl Onsen Resort Tuyên Quang"), "Tuyên Quang")

    def test_trip_attraction_without_price_is_kept_and_not_called_unticketed(self):
        base = {"poiId": 1, "name": "Cầu Vàng", "province": "Đà Nẵng", "latitude": 15.99, "longitude": 107.99,
                "introduction": "Cây cầu nổi tiếng " * 12, "crawledAt": "2026-09-19T00:00:00Z", "plan": {"destination": "Đà Nẵng"}}
        free = n.trip_attraction_product({**base, "price": None})
        paid = n.trip_attraction_product({**base, "poiId": 2, "price": 250000})
        self.assertNotIn("ticketed", free["attributes"])  # chưa rõ: không kết luận "không bán vé"
        self.assertIsNone(free["unitPrice"])
        self.assertTrue(free["available"])  # điểm có trên trip.com vẫn đưa vào demo dù chưa có giá
        self.assertTrue(paid["available"])
        self.assertTrue(paid["attributes"]["ticketed"])
        kept, removed = n.drop_unsellable([free, paid])
        self.assertEqual(removed, 0)  # điểm tham quan trip.com thiếu giá không bị coi là "không đặt được"
        self.assertEqual(len(kept), 2)
        # nhưng khách sạn thiếu giá vẫn bị loại như trước
        hotel = {"sourceRef": "agoda:hotel:x", "taxonomy": "hotel", "unitPrice": None, "attributes": {"level": "property"}}
        self.assertEqual(n.drop_unsellable([hotel])[1], 1)

    def test_room_price_outliers_are_dropped_but_suites_and_vinpearl_are_kept(self):
        def room(pid, price, name, ref=None, parent="h1"):
            return {"productId": pid, "sourceRef": ref or f"booking:hotel:1:room:{pid}", "name": name, "taxonomy": "hotel",
                    "destination": "X", "unitPrice": price, "attributes": {"level": "room", "parentProductId": parent}}
        rooms = [room("a", 900_000, "Khách sạn A - Phòng Superior"), room("b", 1_000_000, "Khách sạn A - Phòng Deluxe"),
                 room("c", 1_100_000, "Khách sạn A - Phòng Gia Đình"), room("d", 1_200_000, "Khách sạn A - Phòng Premier"),
                 room("e", 1_300_000, "Khách sạn A - Phòng Executive"),
                 room("bad", 132_000_000, "Khách sạn A - Phòng Giường Đôi Nhỏ"),
                 room("suite", 60_000_000, "Khách sạn A - Suite Hạng Tổng Thống"),
                 room("vin", 70_000_000, "Vinpearl Resort - Phòng Studio", ref="vinpearl:hotel:1:room:vin")]
        # khách sạn thứ hai chỉ có 2 hạng phòng: không đủ để so sánh nên không xoá dù chênh lệch lớn
        rooms += [room("x1", 800_000, "B - Phòng 1", parent="h2"), room("x2", 20_000_000, "B - Phòng 2", parent="h2")]
        kept, removed = n.drop_price_outliers(rooms)
        self.assertEqual([p["productId"] for p, _ in removed], ["bad"])
        self.assertIn("giá phòng bất thường", removed[0][1])
        self.assertEqual({p["productId"] for p in kept}, {"a", "b", "c", "d", "e", "suite", "vin", "x1", "x2"})

    def test_flights_without_image_get_the_airline_logo_routes_stay_empty(self):
        """12/10/2026: vé mang logo hãng (collectors/airlines.py); tuyến để ảnh thành phố đến do DB đặt."""
        products = [
            {"taxonomy": "flight", "attributes": {"level": "flight", "airline": "VietJet Air"}, "imageUrl": None},
            {"taxonomy": "flight", "attributes": {"level": "flight", "airline": "Hãng lạ"}, "imageUrl": None},
            {"taxonomy": "flight", "attributes": {"level": "flight", "airline": "Vietnam Airlines"}, "imageUrl": "giữ"},
            {"taxonomy": "flight", "attributes": {"level": "route", "airlines": ["VietJet Air"]}, "imageUrl": None},
        ]
        self.assertEqual(n.apply_airline_logos(products), 1)
        self.assertEqual([p["imageUrl"] for p in products],
                         ["https://pic.tripcdn.com/airline_logo/3x/vj.png", None, "giữ", None])

    def test_points_hidden_on_production_are_in_the_reviewed_exclusion_list(self):
        """22 điểm Trip không phải điểm tham quan đã ẩn trên production 12/10/2026: lượt cào sau không được bật lại."""
        excluded = n.load_excluded_products()
        for ref in ("trip:attraction:146226495", "trip:attraction:146505433", "trip:attraction:149736329"):
            self.assertIn(ref, excluded)
            self.assertTrue(excluded[ref].startswith("không phải sản phẩm du lịch"))


if __name__ == "__main__":
    unittest.main()
