import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import normalise as nm
from collectors.agoda_api import AgodaCollector, AgodaOptions, match_city, parse_prices, parse_static, slim_response
from collectors.common import Paths
from collectors.plan import select_destinations

V1 = select_destinations("@v1")

RESPONSE = {
    "hotelId": 65153,
    "hotelInfo": {"name": "Vinpearl Resort Nha Trang", "englishName": "Vinpearl Resort Nha Trang", "accommodationType": "Resort",
                  "starRating": {"value": 5.0},
                  "address": {"full": "Hon Tre Island, Nha Trang, Vietnam", "cityName": "Nha Trang", "areaName": "Hon Tre", "address": "Hon Tre Island"}},
    "mapParams": {"latlng": [12.2215, 109.2462]},
    "aboutHotel": {"hotelDesc": {"overview": "<b>Vinpearl Resort Nha Trang</b> in Nha Trang<br>Private beach resort."},
                   "featureGroups": [{"feature": [{"name": "Private beach", "available": True}, {"name": "Spa", "available": False}]}],
                   "reviewFacilityMentions": [{"text": "câu trích review của khách"}]},
    "mosaicInitData": {"images": [{"location": "//pix8.agoda.net/a.jpg"}, {"location": "//pix8.agoda.net/b.jpg"}]},
    "reviews": {"score": "8.7", "basedOn": "Based on <strong>8,596 reviews</strong>", "combinedReview": {"comments": ["Tên khách: tuyệt"]}},
    "currencyInfo": {"code": "USD"},
    "translations": {"x": "y"},
    "roomGridData": {"masterRooms": [
        {"id": 111, "name": "Deluxe Twin", "maxOccupancy": 2, "bedConfigurationSummary": {"title": "2 single beds"},
         "features": [{"title": "Room size: 32 m²/344 ft²"}, {"title": "Garden view"}], "images": ["//pix8.agoda.net/r1.jpg"],
         "rooms": [{"inclusivePrice": {"display": 120.5}, "currency": "USD", "ratePlanName": "Room only"},
                   {"inclusivePrice": {"display": 116.86}, "currency": "USD", "ratePlanName": "Bed & Breakfast", "isBreakfastIncluded": True}]},
        {"id": 222, "name": "Villa", "maxOccupancy": 4, "rooms": []},
    ]},
}


class MatchCityTest(unittest.TestCase):
    def test_sitemap_city_slugs(self):
        cases = {"halong-vn": "Hạ Long", "ho-chi-minh-city-vn": "TP. Hồ Chí Minh", "pleiku-gia-lai-vn": "Pleiku",
                 "phu-quoc-island-vn": "Phú Quốc", "can-tho-vn": "Cần Thơ", "cat-ba-island-vn": "Cát Bà",
                 "dong-hoi-quang-binh-vn": "Quảng Bình", "hanoi-vn": "Hà Nội", "vung-tau-vn": None, "gia-lam-vn": None}
        self.assertEqual({c: match_city(c, V1) for c in cases}, cases)


class ParseTest(unittest.TestCase):
    def test_static_prices_and_slim_raw(self):
        s = parse_static(RESPONSE)
        self.assertEqual((s["name"], s["starRating"], s["latitude"], s["reviewScore"], s["reviewCount"]),
                         ("Vinpearl Resort Nha Trang", 5.0, 12.2215, 8.7, 8596))
        self.assertEqual(s["facilities"], ["Private beach"])
        self.assertEqual(s["images"][0], "https://pix8.agoda.net/a.jpg")
        self.assertEqual(s["rooms"]["111"]["sizeM2"], 32.0)
        prices = parse_prices(RESPONSE)
        self.assertEqual(list(prices), ["111"])  # hạng không còn gói nào ngày đó = không có giá
        self.assertEqual((prices["111"]["price"], prices["111"]["ratePlan"]), (116.86, "Bed & Breakfast"))
        slim = json.dumps(slim_response(RESPONSE), ensure_ascii=False)
        self.assertNotIn("Tên khách", slim)          # review bị bỏ trước khi ghi raw
        self.assertNotIn("câu trích review", slim)
        self.assertNotIn("translations", slim)
        self.assertEqual(parse_prices(json.loads(slim)), prices)  # raw gọn vẫn parse lại được giá


class PlanTasksTest(unittest.TestCase):
    def test_breadth_first_then_refresh_near_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = Paths(Path(tmp)).ensure()
            c = AgodaCollector(paths, AgodaOptions(destinations=V1, days=3, refresh_near_days=1))
            c.state.db.execute("INSERT INTO prices VALUES (1, '2026-09-23', 'ok', '{}', '2026-01-01T00:00:00Z')")
            hotels = [("u1", "a", "nha-trang", "Nha Trang", 1), ("u2", "b", "nha-trang", "Nha Trang", 2)]
            tasks = c.plan_tasks(hotels, date(2026, 9, 23))
            # khách sạn 2 chưa có ngày nào → ngày đầu của nó đứng ngang hàng ngày thiếu đầu tiên của khách sạn 1
            self.assertEqual(tasks[:2], [(1, "2026-09-24"), (2, "2026-09-23")])
            self.assertEqual(tasks[-1], (1, "2026-09-23"))  # ngày gần đã cũ → làm mới sau cùng
            self.assertEqual(len(tasks), 6)
            c.state.close()


class NormaliseAgodaTest(unittest.TestCase):
    def record(self):
        static = parse_static(RESPONSE)
        rooms = [{**room, "pricesByDate": {"2026-09-22": 99.0, "2026-09-24": 116.86}, "currency": "USD"} for room in static.pop("rooms").values()]
        return {"recordType": "agoda_api_hotel", "key": "hotel:vinpearl-resort-nha-trang:nha-trang", "slug": "vinpearl-resort-nha-trang",
                "citySlug": "nha-trang", "url": "https://www.agoda.com/vi-vn/vinpearl-resort-nha-trang/hotel/nha-trang-vn.html",
                "plan": {"destination": "Nha Trang"}, **static, "rooms": rooms, "datesQueried": ["2026-09-22", "2026-09-24"],
                "crawledAt": "2026-09-23T03:00:00Z"}

    def test_property_and_rooms_with_prices_by_date(self):
        prop, rooms = nm.agoda_api_hotel(self.record(), {"USD": 26000.0}, date(2026, 9, 23))
        self.assertEqual(prop["sourceRef"], "agoda:hotel:vinpearl-resort-nha-trang:nha-trang")  # trùng bản cào cũ → cùng productId
        self.assertEqual(prop["destination"], "Nha Trang")
        self.assertEqual(prop["unitPrice"], 3_038_000)  # 116,86 USD × 26.000, làm tròn nghìn; ngày đã qua bị bỏ
        self.assertEqual(len(rooms), 2)
        room = rooms[0]
        self.assertEqual(room["attributes"]["parentProductId"], prop["productId"])
        self.assertEqual(room["attributes"]["pricesByDate"], {"2026-09-24": 3_038_000})
        self.assertEqual(room["attributes"]["pricesByDateQueried"], ["2026-09-24"])
        self.assertTrue(room["sourceRef"].endswith(":room:111"))


class FresherPriceMergeTest(unittest.TestCase):
    def hotel(self, src, price, observed, ref):
        return nm.make_product(meta={"src": src}, name="Khách sạn A", taxonomy="hotel", destination="Nha Trang", description="mô tả",
                               attributes={"level": "property", "priceObservedAt": observed, "latitude": 12.2, "longitude": 109.2,
                                           "url": f"https://{src}/a"},
                               unitPrice=price, currency="VND", available=True, imageUrl=None, sourceRef=ref)

    def room(self, parent, src, price, ref):
        return nm.make_product(meta={"src": src, "roomName": "Deluxe"}, name="Khách sạn A - Deluxe", taxonomy="hotel", destination="Nha Trang",
                               description="phòng", attributes={"level": "room", "roomName": "Deluxe", "parentProductId": parent["productId"],
                                                                 "priceObservedAt": "x"},
                               unitPrice=price, currency="VND", available=True, imageUrl=None, sourceRef=ref)

    def test_newer_agoda_beats_older_booking(self):
        bk = self.hotel("booking", 1_000_000, "2026-09-16T10:00:00Z", "booking:hotel:a")
        ag = self.hotel("agoda", 1_200_000, "2026-09-23T03:00:00Z", "agoda:hotel:a:nha-trang")
        rooms_of = {bk["productId"]: [self.room(bk, "booking", 1_000_000, "booking:hotel:a:room:1")],
                    ag["productId"]: [self.room(ag, "agoda", 1_200_000, "agoda:hotel:a:nha-trang:room:9")]}
        out, rooms = nm.merge_hotel_cluster([bk, ag], rooms_of, 0)
        self.assertEqual(out["unitPrice"], 1_200_000)
        self.assertEqual(out["attributes"]["fieldSources"]["unitPrice"], "agoda.com")
        self.assertEqual([r["sourceRef"] for r in rooms], ["agoda:hotel:a:nha-trang:room:9"])
        self.assertEqual(out["attributes"]["otaPrices"], {"booking.com": 1_000_000, "agoda.com": 1_200_000})

    def test_same_day_keeps_booking_first(self):
        bk = self.hotel("booking", 1_000_000, "2026-09-23T10:00:00Z", "booking:hotel:a")
        ag = self.hotel("agoda", 1_200_000, "2026-09-23T03:00:00Z", "agoda:hotel:a:nha-trang")
        out, _ = nm.merge_hotel_cluster([bk, ag], {}, 0)
        self.assertEqual(out["unitPrice"], 1_000_000)


if __name__ == "__main__":
    unittest.main()
