import unittest
from datetime import date

from collectors.vinpearl import voucher_item
from collectors.vinpearl_bundles import hotel_info, merge_records, plan_routes
from normalise import vinpearl_bundle_product

LOCATIONS = [
    {"id": "han", "name": "Ha Noi ", "airportCode": "HAN", "isDomestic": True},
    {"id": "sgn", "name": "Ho Chi Minh", "airportCode": "SGN", "isDomestic": True},
    {"id": "cxr", "name": "Nha Trang", "airportCode": "CXR", "isDomestic": True},
    {"id": "na", "name": "Nghe An", "airportCode": "VII", "isDomestic": True},
    {"id": "ht", "name": "Ha Tinh", "airportCode": "VII", "isDomestic": True},
    {"id": "sin", "name": "Singapore", "airportCode": "SIN", "isDomestic": False},
]


def record(key="bundle:HAN:h1", route="HAN-cxr", prices=None, queried=None):
    return {"recordType": "vinpearl_bundle", "key": key, "route": route, "hotelId": "h1", "hotelCode": "VPLNTR",
            "hotelName": "Vinpearl Resort Nha Trang", "originAirport": "HAN", "originCity": "Hà Nội", "destinationAirport": "CXR",
            "address": "Đảo Hòn Tre, Nha Trang, Khánh Hòa", "latitude": 12.2, "longitude": 109.24, "starRating": 5.0,
            "nights": 1, "adults": 2, "pricesByDate": prices or {}, "pricePerPersonByDate": {}, "datesQueried": queried or [],
            "crawledAt": "2026-09-23T02:00:00Z"}


class PlanRoutesTest(unittest.TestCase):
    def test_each_origin_to_every_other_domestic_airport(self):
        routes = [(s["airportCode"], e["id"]) for s, e in plan_routes(LOCATIONS, ("HAN", "SGN"))]
        self.assertIn(("HAN", "sgn"), routes)
        self.assertIn(("SGN", "han"), routes)
        # hai location cùng sân bay VII là hai tuyến riêng; không có tuyến quốc tế, không có tuyến về chính mình
        self.assertEqual(sum(1 for s, e in routes if s == "HAN" and e in ("na", "ht")), 2)
        self.assertNotIn(("HAN", "han"), routes)
        self.assertFalse(any(e == "sin" for _, e in routes))
        self.assertEqual(len(routes), 8)

    def test_unknown_origin_is_skipped(self):
        self.assertEqual(plan_routes(LOCATIONS, ("DLI",)), [])


class MergeRecordsTest(unittest.TestCase):
    def test_requeried_day_takes_new_answer_and_past_days_drop(self):
        old = record(prices={"2026-09-22": 1, "2026-09-24": 100, "2026-09-25": 200}, queried=["2026-09-22", "2026-09-24", "2026-09-25"])
        new = record(prices={"2026-09-26": 300}, queried=["2026-09-24", "2026-09-26"])
        merged = merge_records([old], {new["key"]: new}, {"HAN-cxr": {"2026-09-24", "2026-09-26"}}, date(2026, 9, 23))
        self.assertEqual(len(merged), 1)
        # 24/09 hỏi lại mà không còn combo → bỏ; 25/09 không hỏi lại → giữ; 22/09 đã qua → bỏ
        self.assertEqual(merged[0]["pricesByDate"], {"2026-09-25": 200, "2026-09-26": 300})
        self.assertEqual(merged[0]["datesQueried"], ["2026-09-24", "2026-09-25", "2026-09-26"])

    def test_hotel_missing_this_run_keeps_unqueried_days_only(self):
        old = record(prices={"2026-09-24": 100, "2026-09-30": 150})
        merged = merge_records([old], {}, {"HAN-cxr": {"2026-09-24"}}, date(2026, 9, 23))
        self.assertEqual(merged[0]["pricesByDate"], {"2026-09-30": 150})


class BundleProductTest(unittest.TestCase):
    def test_one_row_per_origin_and_hotel_with_prices_by_date(self):
        p = vinpearl_bundle_product(record(prices={"2026-09-22": 50, "2026-09-25": 6_000_000, "2026-09-24": 5_500_000},
                                           queried=["2026-09-24", "2026-09-25"]), date(2026, 9, 23))
        self.assertEqual(p["taxonomy"], "combo")
        self.assertEqual(p["sourceRef"], "vinpearl:bundle:HAN:VPLNTR")
        self.assertEqual(p["unitPrice"], 5_500_000)  # ngày khởi hành sớm nhất chưa qua
        self.assertEqual((p["availableFrom"], p["availableTo"]), ("2026-09-24", "2026-09-25"))
        self.assertEqual(list(p["attributes"]["pricesByDate"]), ["2026-09-24", "2026-09-25"])
        self.assertTrue(p["available"])
        self.assertNotIn("5.500.000", p["description"])  # giá không vào text embedding
        # tên tách được thành phần bay + khách sạn cho parse_combos (cắt theo '+')
        self.assertIn(" + 1 đêm tại ", p["name"])

    def test_no_future_price_is_unavailable(self):
        p = vinpearl_bundle_product(record(prices={"2026-09-20": 1}), date(2026, 9, 23))
        self.assertFalse(p["available"])
        self.assertIsNone(p["unitPrice"])


class HotelInfoTest(unittest.TestCase):
    def test_reads_misspelled_longitude_and_static_images(self):
        info = hotel_info({"hotelId": "h1", "name": " Vinpearl ", "star": "5.0", "latitude": "12.2", "longtitude": "109.2",
                           "media": [{"order": 1, "url": "booking-static.vinpearl.com/hotels/b.jpg"},
                                     {"order": 0, "url": "booking-static.vinpearl.com/hotels/a b.jpg"}],
                           "reviewCount": "2098", "rating": "4.9"})
        self.assertEqual(info["longitude"], 109.2)
        self.assertEqual(info["images"][0], "https://booking-static.vinpearl.com/hotels/a%20b.jpg")
        self.assertEqual(info["reviewCount"], 2098)


class VoucherItemTest(unittest.TestCase):
    def test_voucher_maps_to_tour_list_shape(self):
        item = voucher_item({"id": "x", "skuCode": "VW00623", "name": "Combo VinWonders", "type": "7", "salePrice": "1500000.0",
                             "originalPrice": "1600000.0", "thumbImageUri": "booking-static.vinpearl.com/tours/a.jpg"})
        self.assertEqual((item["tourCode"], item["type"], item["adultSalePrice"]), ("VW00623", 7, 1_500_000.0))
        self.assertEqual(item["thumbImageView"], {"fileUri": "booking-static.vinpearl.com/tours/a.jpg"})


if __name__ == "__main__":
    unittest.main()
