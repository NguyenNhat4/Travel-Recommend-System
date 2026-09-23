"""Hồi quy cho api_sources.py (hộp thư đến, bộ đổi dạng, tải hàng loạt), quy tắc tọa độ API ưu tiên trong normalise.py, chế độ --api / auto /
pull của pipeline_demo.py và các route API của monitor.py.

Không gọi mạng thật, không cần token: Apify / SerpApi / Travelpayouts được thay bằng server giả trên 127.0.0.1. Các bản ghi kiểu API trong test dựng theo
TÊN TRƯỜNG ghi ở trang mô tả của actor (chưa kiểm với dữ liệu thật): test chứng minh mã của ta nhất quán, không chứng minh actor trả đúng tên trường đó."""
import contextlib
import io
import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import api_sources as api
import apify_source as ap
import monitor
import normalise as nm
import pipeline_demo as pd

RATES = {"USD": 26300.0}
CTX = {"fetchedAt": "2026-09-21T16:00:00Z", "destination": "Nha Trang", "checkin": "2026-10-20", "checkout": "2026-10-21", "adults": 2, "currency": "VND"}
REAL = Path(__file__).resolve().parents[1] / "data" / "interim"


def agoda_item(name="Khách sạn Biển Xanh Nha Trang", lat=12.2400, lng=109.1950, price=300000, url=None, **kw):
    item = {"property_id": 1, "name": name, "property_url": url or "https://www.agoda.com/vi-vn/bien-xanh-nha-trang/hotel/nha-trang-vn.html",
            "star_rating": 4, "description": "Khách sạn nhìn ra biển.", "address": "1 Trần Phú", "city": "Nha Trang", "area": "Lộc Thọ",
            "latitude": lat, "longitude": lng, "nightly_price": price, "currency": "VND", "review_score": 8.4, "review_count": 120,
            "facilities": ["Wi-Fi", {"name": "Hồ bơi"}], "image_url": "https://x/1.jpg", "gallery_urls": ["https://x/2.jpg", "https://x/1.jpg"]}
    item.update(kw)
    return item


def booking_item(name="Khách sạn Biển Xanh Nha Trang", price=500000, **kw):
    item = {"name": name, "stars": 4, "address": "1 Tran Phu", "rating": 8.1, "reviews": "1,234", "price": price, "priceDisplay": "x", "currency": "VND",
            "roomInfo": "Phòng Deluxe", "image": "https://x/b.jpg", "url": "https://www.booking.com/hotel/vn/bien-xanh.html", "hotelId": 777,
            "destination": "Nha Trang", "checkin": "2026-10-20", "checkout": "2026-10-22"}
    item.update(kw)
    return item


def booking_full_item(name="Khách sạn Biển Xanh Nha Trang", **kw):
    """Dạng đầu ra ĐÃ KIỂM VỚI JSON THẬT của voyager/booking-scraper (probe 5 khách sạn Nha Trang, 22/09/2026, xem data/demo/probe/).
    Ba điểm khác giả định ban đầu, xem docstring adapt_booking_full: currency chỉ là ký hiệu ("US$"), giá phòng nằm trong
    rooms[].options[].price (không phải rooms[].price), facilities của khách sạn là danh sách NHÓM lồng nhau."""
    item = {"url": "https://www.booking.com/hotel/vn/bien-xanh.vi.html", "name": name, "type": "Hotel", "description": "Nằm sát biển, có hồ bơi.", "stars": 4,
            "price": 100.0, "currency": "US$", "rating": 8.4, "reviews": 321, "checkInDate": "2026-10-20", "checkOutDate": "2026-10-22",
            "location": {"lat": "12.2451", "lng": "109.1953"}, "address": {"full": "1 Trần Phú, Nha Trang", "city": "Nha Trang", "country": "vn"},
            "image": "https://x/b.jpg", "images": ["https://x/b.jpg", "https://x/c.jpg"],
            "facilities": [{"name": "Great for your stay", "facilities": [{"name": "WiFi miễn phí", "id": 1}, {"name": "Hồ bơi", "id": 2}]},
                          {"name": "Chỗ đậu xe", "facilities": [{"name": "Chỗ đỗ xe", "id": 3}]}],
            "rooms": [{"id": 1001, "roomType": "Phòng Deluxe", "persons": 2, "bedTypes": [{"beds": ["1 giường đôi lớn"]}],
                       "facilities": ["Hướng biển"], "options": [{"price": 100.0, "currency": "US$", "persons": 2}]},
                      {"id": 1002, "roomType": "Suite gia đình", "persons": 4,
                       "bedTypes": [{"beds": ["1 giường đôi cực lớn"]}, {"beds": ["1 giường sofa"]}],
                       "facilities": [], "options": [{"price": 240.0, "currency": "US$", "persons": 4}, {"price": 220.0, "currency": "US$", "persons": 3}]},
                      {"id": 1003, "roomType": "Hết phòng", "persons": 2, "bedTypes": [], "facilities": [], "options": []}]}
    item.update(kw)
    return item


def write(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return path


def age(path: Path, seconds: float = 5) -> None:
    t = time.time() - seconds
    os.utime(path, (t, t))


class Numbers(unittest.TestCase):
    def test_num_parses_prices_and_counts(self):
        for raw, want in ((416, 416.0), ("1,234", 1234.0), ("US$416", 416.0), ("1.250.000 ₫", 1250000.0), ("1,234.56", 1234.56),
                          ("1.234,56", 1234.56), ("8,5", 8.5), (0, None), (None, None), ("", None), ("không có giá", None), (True, None)):
            with self.subTest(raw=raw):
                self.assertEqual(api._num(raw), want)


class Loading(unittest.TestCase):
    def test_load_items_accepts_every_shape(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            env = api.make_envelope("apify_agoda", [agoda_item()], {"destination": "Nha Trang"})
            cases = {"env.json": (env, "apify_agoda"), "list.json": ([agoda_item()], None), "data.json": ({"data": [agoda_item()], "success": True}, None),
                     "props.json": ({"properties": [{"name": "x"}], "search_parameters": {"q": "khách sạn Hà Nội"}}, None), "one.json": (agoda_item(), None)}
            for name, (obj, src) in cases.items():
                with self.subTest(name=name):
                    meta, items = api.load_items(write(t / name, obj))
                    self.assertEqual(len(items), 1)
                    self.assertEqual(meta.get("source"), src)
            meta, items = api.load_items(write(t / "a.jsonl", json.dumps(agoda_item()) + "\n\n" + json.dumps(agoda_item(name="B")) + "\n"))
            self.assertEqual(len(items), 2)
            self.assertEqual(api._context({"search_parameters": {"q": "khách sạn Hà Nội", "check_in_date": "2026-10-01"}}, t / "a.jsonl")["checkin"], "2026-10-01")

    def test_load_items_rejects_empty_and_broken(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            for name, body in (("e.json", "[]"), ("n.json", '{"items": []}'), ("s.json", '"chuỗi"'), ("b.json", '{"a": ')):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    api.load_items(write(t / name, body))

    def test_detect_source(self):
        def d(items, meta=None):
            return api.detect_source(meta or {}, items)
        self.assertEqual(d([agoda_item()]), "apify_agoda")
        self.assertEqual(d([booking_item()]), "apify_booking")
        self.assertEqual(d([{"name": "H", "gps_coordinates": {"latitude": 1, "longitude": 2}, "property_token": "t"}]), "serpapi_hotels")
        self.assertEqual(d([{"origin": "HAN", "airline": "VJ", "departure_at": "2026-10-01T10:00:00+07:00", "price": 1}]), "travelpayouts_flights")
        self.assertEqual(d([{"title": "Vé", "url": "https://www.klook.com/vi/activity/1-x/"}]), "apify_klook")
        self.assertIsNone(d([{"foo": 1}]))
        self.assertEqual(d([{"foo": 1}], {"source": "apify_booking"}), "apify_booking", "phong bì ghi rõ nguồn thì tin phong bì")
        self.assertIsNone(d([{"foo": 1}], {"source": "khong-co"}))


class Adapters(unittest.TestCase):
    def test_agoda_key_matches_scraped_key_for_every_url_shape(self):
        for url in ("https://www.agoda.com/vi-vn/bien-xanh-nha-trang/hotel/nha-trang-vn.html", "https://www.agoda.com/bien-xanh-nha-trang/hotel/nha-trang-vn.html?cid=1",
                    "https://www.agoda.com/en-us/bien-xanh-nha-trang/hotel/nha-trang-vn.html#x"):
            with self.subTest(url=url):
                r = api.adapt_agoda(agoda_item(url=url), CTX)
                self.assertEqual((r["slug"], r["citySlug"], r["key"]), ("bien-xanh-nha-trang", "nha-trang", "hotel:bien-xanh-nha-trang:nha-trang"))

    def test_agoda_fields(self):
        r = api.adapt_agoda(agoda_item(), CTX)
        self.assertEqual((r["minPrice"], r["currency"], r["latitude"], r["longitude"], r["starRating"], r["reviewCount"]), (300000.0, "VND", 12.24, 109.195, 4.0, 120))
        self.assertEqual(r["facilities"], ["Wi-Fi", "Hồ bơi"])
        self.assertEqual(r["images"], ["https://x/1.jpg", "https://x/2.jpg"], "ảnh trùng bị bỏ")
        self.assertEqual((r["source"], r["recordType"], r["transport"], r["crawledAt"]), ("agoda_hotels", "agoda_hotel", "apify", CTX["fetchedAt"]))
        self.assertEqual(r["priceQuery"], {"checkin": "2026-10-20", "checkout": "2026-10-21", "adults": 2, "currency": "VND"})
        self.assertIsNone(api.adapt_agoda({"property_url": "x"}, CTX), "thiếu tên thì bỏ")

    def test_agoda_without_url_falls_back_to_slug_of_name(self):
        r = api.adapt_agoda(agoda_item(url="", property_url=None), CTX)
        self.assertEqual(r["key"], "hotel:khach-san-bien-xanh-nha-trang:nha-trang")

    def test_booking_price_per_night_room_and_missing_coordinates(self):
        r = api.adapt_booking(booking_item(price=1000000), CTX)
        self.assertEqual((r["key"], r["minPrice"], r["reviewCount"], r["starRating"]), ("hotel:777", 500000.0, 1234, 4), "1.000.000 cho 2 đêm = 500.000/đêm")
        self.assertEqual((len(r["rooms"]), r["rooms"][0]["name"], r["rooms"][0]["minPrice"]), (1, "Phòng Deluxe", 500000.0))
        self.assertIsNone(r["latitude"])
        self.assertEqual(api.adapt_booking(booking_item(roomInfo={"name": "Suite"}), CTX)["rooms"][0]["name"], "Suite")
        self.assertEqual(api.adapt_booking(booking_item(roomInfo=None), CTX)["rooms"][0]["name"], "Phòng (giá dẫn đầu)")
        self.assertEqual(api.adapt_booking(booking_item(price=None), CTX)["rooms"], [], "không có giá thì không dựng phòng")

    def test_adapted_records_go_through_normalise(self):
        pa = nm.agoda_hotel(api.adapt_agoda(agoda_item(), CTX), RATES)
        self.assertEqual((pa["sourceRef"], pa["unitPrice"], pa["destination"], pa["attributes"]["locationSource"]),
                         ("agoda:hotel:bien-xanh-nha-trang:nha-trang", 300000, "Nha Trang", "agoda.com (API)"))
        self.assertTrue(pa["_meta"]["coordApi"])
        pb, rooms = nm.booking_hotel(api.adapt_booking(booking_item(price=1000000), CTX), RATES)
        self.assertEqual((pb["sourceRef"], pb["unitPrice"], len(rooms)), ("booking:hotel:777", 500000, 1))
        self.assertNotIn("latitude", pb["attributes"])
        self.assertFalse(pb["_meta"].get("coordApi"))

    @unittest.skipUnless((REAL / "agoda_hotels.jsonl").exists() and (REAL / "booking_hotels.jsonl").exists(), "cần dữ liệu thô đã cào")
    def test_api_record_of_a_real_hotel_gets_the_same_product_id_as_the_scraped_one(self):
        def first(name, pred):
            for line in (REAL / name).read_text(encoding="utf-8").split("\n"):
                if line.strip() and pred(r := json.loads(line)):
                    return r
        a = first("agoda_hotels.jsonl", lambda r: r.get("latitude") and r.get("minPrice"))
        item = agoda_item(name=a["name"], url=a["url"], lat=a["latitude"], lng=a["longitude"])
        rec = api.adapt_agoda(item, {**CTX, "destination": a["plan"]["destination"]})
        self.assertEqual(rec["key"], a["key"])
        self.assertEqual(nm.agoda_hotel(rec, RATES)["productId"], nm.agoda_hotel(a, RATES)["productId"])
        self.assertEqual([r["crawledAt"] for r in nm.latest_by_key([a, rec])], [CTX["fetchedAt"]], "bản API mới hơn thay bản cào cũ")
        b = first("booking_hotels.jsonl", lambda r: r.get("rooms") and r.get("hotelId"))
        brec = api.adapt_booking(booking_item(name=b["name"], url=b["url"], hotelId=b["hotelId"]), CTX)
        self.assertEqual(brec["key"], b["key"])
        self.assertEqual(nm.booking_hotel(brec, RATES)[0]["productId"], nm.booking_hotel(b, RATES)[0]["productId"])


class BookingFull(unittest.TestCase):
    """Actor Booking đầy đủ: toạ độ + mô tả + từng hạng phòng. Tên trường đã KIỂM với JSON thật (xem docstring adapt_booking_full)."""

    def test_detect_and_keys(self):
        self.assertEqual(api.detect_source({}, [booking_full_item()]), "apify_booking_full")
        self.assertEqual(api.detect_source({}, [booking_item()]), "apify_booking", "bản nhanh (không có mảng phòng) vẫn nhận đúng")
        self.assertEqual(api.adapt_booking_full(booking_full_item(), CTX)["key"], "hotel:bien-xanh", "không có hotelId thì lấy slug trong URL (bỏ .vi)")
        self.assertEqual(api.adapt_booking_full(booking_full_item(hotelId=555), CTX)["key"], "hotel:555")
        self.assertIsNone(api.adapt_booking_full({"url": "x"}, CTX))

    def test_currency_symbol_is_ignored_always_usd(self):
        """currency của actor chỉ là ký hiệu hiển thị ("US$", "₫"...), không phải mã ISO — bỏ qua hoàn toàn, luôn dùng USD (đúng giá trị ta gửi lên)."""
        for symbol in ("US$", "₫", None, "VND"):
            with self.subTest(symbol=symbol):
                r = api.adapt_booking_full(booking_full_item(currency=symbol), CTX)
                self.assertEqual(r["currency"], "USD")
                self.assertEqual(r["rooms"][0]["currency"], "USD")

    def test_room_price_comes_from_nested_options_not_a_direct_room_field(self):
        r = api.adapt_booking_full(booking_full_item(), CTX)
        self.assertEqual((r["priceQuery"]["checkin"], r["priceQuery"]["checkout"]), ("2026-10-20", "2026-10-22"))
        self.assertEqual([(x["name"], x["minPrice"], x["maxOccupancy"]) for x in r["rooms"]],
                         [("Phòng Deluxe", 50.0, 2), ("Suite gia đình", 110.0, 4), ("Hết phòng", None, 2)],
                         "giá = phương án rẻ nhất trong options[], chia cho 2 đêm; phòng không có options[] thì không có giá")
        self.assertEqual(r["rooms"][0]["bed"], "1 giường đôi lớn")
        self.assertEqual(r["rooms"][1]["bed"], "1 giường đôi cực lớn; 1 giường sofa", "gộp beds[] của mọi bedTypes[]")
        self.assertEqual(r["rooms"][2]["bed"], None)
        self.assertEqual(r["rooms"][0]["facilities"], ["Hướng biển"], "facilities của TỪNG PHÒNG vốn đã là danh sách phẳng, không lồng nhóm")

    def test_hotel_facilities_are_flattened_from_nested_groups(self):
        r = api.adapt_booking_full(booking_full_item(), CTX)
        self.assertEqual(r["facilities"], ["WiFi miễn phí", "Hồ bơi", "Chỗ đỗ xe"], "lấy tên tiện nghi thật trong facilities[].facilities[], không phải tên nhóm")
        no_sub = api.adapt_booking_full(booking_full_item(facilities=[{"name": "Nhóm trống", "facilities": []}]), CTX)
        self.assertEqual(no_sub["facilities"], ["Nhóm trống"], "nhóm không có mục con thì tạm dùng tên nhóm")

    def test_fields_and_fallbacks(self):
        r = api.adapt_booking_full(booking_full_item(), CTX)
        self.assertEqual((r["latitude"], r["longitude"], r["starRating"], r["reviewCount"], r["description"]), (12.2451, 109.1953, 4, 321, "Nằm sát biển, có hồ bơi."))
        self.assertEqual((r["address"]["street"], r["city"]), ("1 Trần Phú, Nha Trang", "Nha Trang"))
        flat = api.adapt_booking_full(booking_full_item(location=None, rooms=[], latitude="12.3", longitude=109.2, address="Chuỗi địa chỉ"), CTX)
        self.assertEqual((flat["latitude"], flat["longitude"], flat["address"]["street"], flat["minPrice"]), (12.3, 109.2, "Chuỗi địa chỉ", 50.0),
                         "toạ độ dạng latitude/longitude, địa chỉ dạng chuỗi, không có phòng thì lấy giá tổng (item.price) chia số đêm")

    def test_promo_banner_stripped_from_description(self):
        """Hồi quy phát hiện thật 22/09/2026: actor ghép banner 'Đăng nhập để mở khoá...' / 'Giảm giá Genius...' vào ĐẦU description
        (11/19 khách sạn thật dính, 0/400 ở bản cào HTML cũ) — phải lọc bỏ, giữ nguyên phần mô tả thật phía sau."""
        noisy = ("Đăng nhập để mở khóa mức giá dành riêng cho thành viên đối với các ngày bạn đã chọn tại X\n\n\n"
                "Giảm giá Genius tại chỗ nghỉ này tùy thuộc vào ngày đặt phòng, ngày lưu trú và các ưu đãi có sẵn khác.\n\n"
                "Tọa lạc ở Nha Trang, cách Bãi biển Nha Trang chưa đến 1 km, khách sạn cung cấp nhà hàng, Wi-Fi miễn phí.\n")
        r = api.adapt_booking_full(booking_full_item(description=noisy), CTX)
        self.assertEqual(r["description"], "Tọa lạc ở Nha Trang, cách Bãi biển Nha Trang chưa đến 1 km, khách sạn cung cấp nhà hàng, Wi-Fi miễn phí.")
        clean = api.adapt_booking_full(booking_full_item(description="Mô tả sạch, không có banner."), CTX)
        self.assertEqual(clean["description"], "Mô tả sạch, không có banner.", "mô tả đã sạch thì giữ nguyên")
        only_noise = api.adapt_booking_full(booking_full_item(description=noisy.split("\n\n")[0]), CTX)
        self.assertIsNone(only_noise["description"], "toàn bộ mô tả chỉ là banner thì bỏ trống, không giữ chuỗi rỗng")
        self.assertIsNone(api.adapt_booking_full(booking_full_item(description=None), CTX)["description"])

    def test_goes_through_normalise_with_rooms_coordinates_and_api_label(self):
        prop, rooms = nm.booking_hotel(api.adapt_booking_full(booking_full_item(), CTX), RATES)
        a = prop["attributes"]
        # 50.0 USD/đêm × 26300 = 1.315.000 VND (rẻ nhất, thắng cả Suite 110.0 USD → 2.893.000 VND)
        self.assertEqual((prop["sourceRef"], prop["unitPrice"], len(rooms), a["latitude"], a["locationSource"]),
                         ("booking:hotel:khach-san-bien-xanh-nha-trang", 1315000, 3, 12.2451, "booking.com (API)"))  # không có hotelId: sourceRef theo tên, như bản cào
        self.assertTrue(prop["_meta"]["coordApi"])
        self.assertEqual(sorted(r["unitPrice"] for r in rooms if r["unitPrice"] is not None), [1315000, 2893000])
        self.assertIsNone(next(r for r in rooms if r["name"].endswith("Hết phòng"))["unitPrice"])
        self.assertTrue(prop["description"])


class CoordinatePrecedence(unittest.TestCase):
    """API trả toạ độ thì thắng toạ độ đọc từ HTML; Vinpearl (chính chủ) vẫn đứng đầu; dữ liệu cào cũ không đổi hành vi."""

    @staticmethod
    def merged(agoda_rec, booking_rec):
        pa = nm.agoda_hotel(agoda_rec, RATES)
        pb, rooms = nm.booking_hotel(booking_rec, RATES)
        clusters, _ = nm.cluster_hotels([pb, pa], 88.0)
        assert len(clusters) == 1
        return nm.merge_hotel_cluster(clusters[0], {pb["productId"]: rooms}, 0)[0]["attributes"]

    def html_booking(self, lat, lng):
        r = api.adapt_booking(booking_item(price=500000), CTX)
        r.update(latitude=lat, longitude=lng)
        r.pop("transport")  # bản ghi cào bằng trình duyệt không có khoá transport
        return r

    def test_api_coordinates_win_and_disagreement_is_noted(self):
        a = self.merged(api.adapt_agoda(agoda_item(lat=12.2510, lng=109.1950), CTX), self.html_booking(12.2400, 109.1950))
        self.assertEqual((a["latitude"], a["locationSource"]), (12.2510, "agoda.com (API)"))
        self.assertRegex(a["locationNote"], r"booking\.com lệch 12\d\d m so với agoda\.com \(API\); dùng agoda\.com \(API\)")

    def test_agreeing_coordinates_carry_no_note(self):
        a = self.merged(api.adapt_agoda(agoda_item(lat=12.2401, lng=109.1950), CTX), self.html_booking(12.2400, 109.1950))
        self.assertEqual(a["locationSource"], "agoda.com (API)")
        self.assertNotIn("locationNote", a)

    def test_scraped_html_pair_keeps_the_old_rule(self):
        html_agoda = api.adapt_agoda(agoda_item(lat=12.2510), CTX)
        html_agoda.pop("transport")
        a = self.merged(html_agoda, self.html_booking(12.2400, 109.1950))
        self.assertEqual((a["latitude"], a["locationSource"]), (12.2400, "booking.com"), "không có API thì Booking (đứng đầu) vẫn thắng như cũ")

    def test_booking_api_without_coordinates_borrows_agoda_api(self):
        a = self.merged(api.adapt_agoda(agoda_item(), CTX), api.adapt_booking(booking_item(), CTX))
        self.assertEqual((a["latitude"], a["locationSource"], a["fieldSources"]["latitude"]), (12.24, "agoda.com (API)", "agoda.com (API)"))

    def test_vinpearl_own_coordinates_beat_api(self):
        vp = nm.make_product(meta={"src": "vinpearl", "plan": {}}, name="Vinpearl Resort Nha Trang", taxonomy="hotel", destination="Nha Trang", unitPrice=900000,
                             attributes={"level": "property", "latitude": 12.2000, "longitude": 109.2000, "locationSource": "vinpearl"}, sourceRef="vinpearl:hotel:1")
        ag = nm.agoda_hotel(api.adapt_agoda(agoda_item(name="Vinpearl Resort Nha Trang", lat=12.2001, lng=109.2001), CTX), RATES)
        out, _ = nm.merge_hotel_cluster([vp, ag], {}, 0)
        self.assertEqual((out["attributes"]["latitude"], out["attributes"]["locationSource"]), (12.2, "vinpearl"))


class ReviewScoreFallback(unittest.TestCase):
    """Bug thật 22/09/2026: vinpearl_hotel() không tự đặt reviewScore (chỉ tripAdvisorRating), và Vinpearl luôn là primary
    khi gộp cụm — nên trước fix, MỌI khách sạn Vinpearl đều có reviewScore=null dù Booking cùng cụm có điểm thật
    (vd. Vinpearl Hotel Bắc Ninh: bookingReviewScore=8.9 nhưng reviewScore=None). Giờ mượn từ OTA khác trong cụm trước,
    TripAdvisor của chính Vinpearl sau (thang 5, không trộn lẫn thang 10 của OTA)."""

    @staticmethod
    def vinpearl_primary(**attrs):
        return nm.make_product(meta={"src": "vinpearl", "plan": {}}, name="Vinpearl Resort Nha Trang", taxonomy="hotel",
                               destination="Nha Trang", unitPrice=900000,
                               attributes={"level": "property", "latitude": 12.2, "longitude": 109.2, **attrs},
                               sourceRef="vinpearl:hotel:1")

    def test_borrows_review_score_from_booking_in_the_same_cluster(self):
        vp = self.vinpearl_primary(tripAdvisorRating=4.9, tripAdvisorReviewCount=58)  # có TripAdvisor nhưng Booking phải thắng
        bk, _ = nm.booking_hotel(api.adapt_booking(booking_item(name="Vinpearl Resort Nha Trang"), CTX), RATES)
        out, _ = nm.merge_hotel_cluster([vp, bk], {}, 0)
        a = out["attributes"]
        self.assertEqual((a["reviewScore"], a["reviewScoreScale"], a["reviewCount"], a["fieldSources"]["reviewScore"]),
                         (8.1, 10.0, 1234, "booking.com"))

    def test_falls_back_to_own_tripadvisor_when_no_ota_match(self):
        vp = self.vinpearl_primary(tripAdvisorRating=4.9, tripAdvisorReviewCount=58)
        out, _ = nm.merge_hotel_cluster([vp], {}, 0)
        a = out["attributes"]
        self.assertEqual((a["reviewScore"], a["reviewScoreScale"], a["reviewCount"], a["fieldSources"]["reviewScore"]),
                         (4.9, 5.0, 58, "vinpearl (tripadvisor)"))

    def test_stays_null_without_any_review_evidence(self):
        vp = self.vinpearl_primary()
        out, _ = nm.merge_hotel_cluster([vp], {}, 0)
        self.assertIsNone(out["attributes"].get("reviewScore"))
        self.assertNotIn("reviewScore", out["attributes"].get("fieldSources", {}))


class Intake(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.root = Path(self._t.name)
        self.inbox, self.store = self.root / "inbox", self.root / "store"

    def tearDown(self):
        self._t.cleanup()

    def test_routes_every_kind_of_file_and_appends_to_store(self):
        write(self.inbox / "1-agoda.json", api.make_envelope("apify_agoda", [agoda_item(), {"foo": 1}, agoda_item(name="Khách sạn Hai")], {"destination": "Nha Trang"}))
        write(self.inbox / "2-booking.json", [booking_item()])
        write(self.inbox / "3-serp.json", {"properties": [{"name": "H", "gps_coordinates": {"latitude": 1, "longitude": 2}, "property_token": "t"}]})
        write(self.inbox / "4-la.json", [{"foo": 1}])
        write(self.inbox / "5-hong.json", '{"a": ')
        write(self.inbox / "6-jsonl.jsonl", json.dumps(agoda_item(name="Từ JSONL")) + "\n")
        for f in self.inbox.iterdir():
            age(f)
        write(self.inbox / "7-moi.json", [agoda_item()])                     # vừa ghi: chưa 'nằm yên'
        write(self.inbox / ".tmp-8.json", [agoda_item()])                     # file tạm của write_file_atomic
        age(self.inbox / ".tmp-8.json")
        res = {r["file"]: r for r in api.intake(self.inbox, self.store)}
        self.assertEqual({k: v["status"] for k, v in res.items()},
                         {"1-agoda.json": "done", "2-booking.json": "done", "3-serp.json": "pending", "4-la.json": "unrecognized", "5-hong.json": "failed",
                          "6-jsonl.jsonl": "done"})
        self.assertEqual((res["1-agoda.json"]["items"], res["1-agoda.json"]["mapped"], res["1-agoda.json"]["skipped"]), (3, 2, 1))
        self.assertIn("chờ bộ chuyển", res["3-serp.json"]["note"])
        ag = [json.loads(x) for x in (self.store / "interim" / "agoda_hotels.jsonl").read_text(encoding="utf-8").split("\n") if x]
        self.assertEqual(sorted(r["name"] for r in ag), sorted(["Khách sạn Biển Xanh Nha Trang", "Khách sạn Hai", "Từ JSONL"]))
        self.assertEqual(len((self.store / "interim" / "booking_hotels.jsonl").read_text(encoding="utf-8").split("\n")) - 1, 1)
        ov = api.inbox_overview(self.inbox)
        self.assertEqual((ov["counts"], sorted(w["file"] for w in ov["waiting"])),
                         ({"_processed": 3, "_pending": 1, "_unrecognized": 1, "_failed": 1}, ["7-moi.json"]))
        self.assertEqual(api.intake(self.inbox, self.store), [], "gọi lại: file mới vẫn chưa đủ tuổi, file cũ đã chuyển đi")
        age(self.inbox / "7-moi.json")
        self.assertEqual([r["file"] for r in api.intake(self.inbox, self.store)], ["7-moi.json"])

    def test_same_name_twice_never_overwrites_processed_copy(self):
        for _ in range(2):
            age(write(self.inbox / "x.json", [agoda_item()]))
            api.intake(self.inbox, self.store)
        self.assertEqual(len(list((self.inbox / "_processed").iterdir())), 2)

    def test_envelope_fetch_time_becomes_crawled_at_and_query_becomes_context(self):
        env = api.make_envelope("apify_agoda", [agoda_item()], {"destination": "Phú Quốc", "checkin": "2026-11-01", "checkout": "2026-11-03"})
        env["fetchedAt"] = "2026-09-21T01:02:03Z"
        age(write(self.inbox / "e.json", env))
        api.intake(self.inbox, self.store)
        r = json.loads((self.store / "interim" / "agoda_hotels.jsonl").read_text(encoding="utf-8").split("\n")[0])
        self.assertEqual((r["crawledAt"], r["plan"]["destination"]), ("2026-09-21T01:02:03Z", "Phú Quốc"))
        self.assertEqual((r["priceQuery"]["checkin"], r["priceQuery"]["checkout"]), ("2026-11-01", "2026-11-03"), "ngày hỏi lấy từ truy vấn ghi trong phong bì")

    def test_atomic_write_leaves_no_temp_file(self):
        api.write_file_atomic(self.inbox / "a.json", {"x": 1})
        self.assertEqual([p.name for p in self.inbox.iterdir()], ["a.json"])


class FakeApifyMulti(BaseHTTPRequestHandler):
    """Apify giả: mỗi POST /acts/.../runs tạo một run; input có 'FAIL' thì run thất bại; trả 3 mục kèm điểm đến của input."""
    lock = threading.Lock()
    calls: list = []
    runs: dict = {}
    active = 0
    peak = 0
    token = "tok-MULTI"

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        with FakeApifyMulti.lock:
            FakeApifyMulti.calls.append((self.path, dict(self.headers), body))
            if self.headers.get("Authorization") != f"Bearer {FakeApifyMulti.token}":
                return self._send(401, {"error": {"type": "x", "message": "token"}})
            rid = f"RUN{len(FakeApifyMulti.runs) + 1}"
            FakeApifyMulti.runs[rid] = body
            FakeApifyMulti.active += 1
            FakeApifyMulti.peak = max(FakeApifyMulti.peak, FakeApifyMulti.active)
        time.sleep(0.15)
        self._send(201, {"data": {"id": rid, "status": "RUNNING", "defaultDatasetId": "DS-" + rid}})

    def do_GET(self):
        rid = self.path.split("?")[0].rsplit("/", 1)[-1].replace("DS-", "") if "/actor-runs/" in self.path or "/items" not in self.path else self.path.split("/")[2].replace("DS-", "")
        inp = FakeApifyMulti.runs.get(rid, {})
        if "/items" in self.path:
            dest = inp.get("location") or (inp.get("destinations") or ["?"])[0]
            return self._send(200, [{"name": f"{dest} hotel {i}", "hotelId": i, "stars": 3, "priceDisplay": "1", "price": 100000} for i in range(3)])
        with FakeApifyMulti.lock:
            FakeApifyMulti.active -= 1
        failed = "FAIL" in json.dumps(inp)
        self._send(200, {"data": {"id": rid, "status": "FAILED" if failed else "SUCCEEDED", "defaultDatasetId": "DS-" + rid, "usageTotalUsd": 0.01,
                                  "statusMessage": "actor lỗi" if failed else ""}})


class FetchApify(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeApifyMulti)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        FakeApifyMulti.calls, FakeApifyMulti.runs, FakeApifyMulti.active, FakeApifyMulti.peak = [], {}, 0, 0
        self.client = ap.Apify(FakeApifyMulti.token, base=self.base, timeout=10)
        self._t = tempfile.TemporaryDirectory()
        self.inbox = Path(self._t.name) / "inbox"

    def tearDown(self):
        self._t.cleanup()

    def test_one_run_per_destination_in_parallel_with_split_budget_and_envelopes(self):
        opts = api.FetchOptions(destinations=["Nha Trang", "Phú Quốc", "Đà Nẵng", "Hà Nội"], max_items=7, max_usd=2.0, checkin="2026-10-20", checkout="2026-10-21", concurrency=4)
        events = []
        res = api.fetch_apify("apify-agoda", opts, self.inbox, client=self.client, on_event=events.append)
        self.assertEqual(sorted(r["destination"] for r in res), sorted(opts.destinations))
        self.assertTrue(all(r["items"] == 3 and r["file"] for r in res) and len(events) == 4)
        posts = [c for c in FakeApifyMulti.calls if c[0].startswith("/acts/agentx~agoda-hotels-scraper/runs")]
        self.assertEqual(len(posts), 4)
        for path, headers, body in posts:
            self.assertIn("maxTotalChargeUsd=0.5", path, "trần $2 chia đều cho 4 điểm đến")
            self.assertIn("maxItems=7", path)
            self.assertEqual(headers["Authorization"], "Bearer tok-MULTI")
            self.assertEqual((body["max_results"], body["check_in"]), (7, "2026-10-20"))
            self.assertTrue(body["location"].endswith(", Vietnam"))
        self.assertGreater(FakeApifyMulti.peak, 1, "các lượt phải chạy song song, không tuần tự")
        env = json.loads(next(self.inbox.glob("apify-agoda-nha-trang-*.json")).read_text(encoding="utf-8"))
        self.assertEqual((env["source"], env["query"]["destination"], env["costUsd"], len(env["items"])), ("apify_agoda", "Nha Trang", 0.01, 3))
        self.assertEqual(len(list(self.inbox.glob(".tmp-*"))), 0)

    def test_booking_input_shape(self):
        opts = api.FetchOptions(destinations=["Hội An"], max_items=5, max_usd=1.0, checkin="2026-10-20", checkout="2026-10-21", adults=3, currency="VND")
        api.fetch_apify("apify-booking", opts, self.inbox, client=self.client)
        body = FakeApifyMulti.calls[0][2]
        self.assertEqual((body["destinations"], body["maxResults"], body["adults"], body["currency"]), (["Hoi An, Vietnam"], 5, 3, "VND"))

    def test_booking_full_input_shape(self):
        opts = api.FetchOptions(destinations=["Phú Quốc"], max_items=9, max_usd=1.0, checkin="2026-10-20", checkout="2026-10-22", adults=2)
        api.fetch_apify("apify-booking-full", opts, self.inbox, client=self.client)
        path, _, body = FakeApifyMulti.calls[0]
        self.assertIn("/acts/voyager~booking-scraper/runs", path)
        self.assertEqual((body["search"], body["maxItems"], body["checkIn"], body["checkOut"], body["rooms"]), ("Phu Quoc, Vietnam", 9, "2026-10-20", "2026-10-22", 1))

    def test_one_failing_destination_does_not_stop_the_others(self):
        opts = api.FetchOptions(destinations=["Nha Trang", "FAIL City", "Huế"], max_items=3, max_usd=1.0, concurrency=1)
        res = {r["destination"]: r for r in api.fetch_apify("apify-agoda", opts, self.inbox, client=self.client)}
        self.assertIn("actor lỗi", res["FAIL City"]["error"])
        self.assertIsNone(res["FAIL City"]["file"])
        self.assertTrue(res["Nha Trang"]["file"] and res["Huế"]["file"])

    def test_limits_are_enforced_before_any_call(self):
        for kwargs in ({"destinations": []}, {"destinations": ["x"] * 71}, {"destinations": ["A"], "max_items": 0}, {"destinations": ["A"], "max_items": 501},
                       {"destinations": ["A"], "max_usd": 0}, {"destinations": ["A"], "max_usd": 5.5}, {"destinations": ["A; DROP"]}):
            with self.subTest(**kwargs), self.assertRaises(api.ApiError):
                api.fetch_apify("apify-agoda", api.FetchOptions(**kwargs), self.inbox, client=self.client)
        with self.assertRaisesRegex(api.ApiError, "quá nhỏ"):
            api.fetch_apify("apify-agoda", api.FetchOptions(destinations=["A", "B", "C", "D"], max_usd=0.05), self.inbox, client=self.client)
        self.assertEqual(FakeApifyMulti.calls, [])

    def test_estimate_cost(self):
        self.assertAlmostEqual(api.estimate_cost("apify-agoda", 15, 50)["usd"], 15 * (50 * 0.004 + 0.02))
        self.assertAlmostEqual(api.estimate_cost("apify-booking", 10, 100)["usd"], 1.8)
        self.assertEqual(api.estimate_cost("serpapi", 15, 0, pages=2)["usd"], 0.0)


class FakeHttp(BaseHTTPRequestHandler):
    """SerpApi + Travelpayouts giả."""
    calls: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        FakeHttp.calls.append((self.path, dict(self.headers)))
        body = {}
        if self.path.startswith("/search.json"):
            if "api_key=BAD" in self.path:
                body = {"error": "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"}
            elif "next_page_token=P2" in self.path:
                body = {"properties": [{"name": "trang 2", "gps_coordinates": {}}], "serpapi_pagination": {}}
            else:
                body = {"properties": [{"name": "trang 1", "gps_coordinates": {}}], "serpapi_pagination": {"next_page_token": "P2"}}
        elif self.path.startswith("/aviasales/v3/prices_for_dates"):
            body = {"success": True, "currency": "vnd", "data": [{"origin": "HAN", "destination": "SGN", "price": 1200000, "airline": "VJ",
                                                                   "departure_at": "2026-10-05T10:00:00+07:00"}]}
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class FetchOthers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeHttp)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        FakeHttp.calls = []
        self._t = tempfile.TemporaryDirectory()
        self.inbox = Path(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def test_serpapi_paginates_and_writes_envelope_with_search_context(self):
        opts = api.FetchOptions(destinations=["Nha Trang"], pages=2, checkin="2026-10-20", checkout="2026-10-21")
        res = api.fetch_serpapi(opts, self.inbox, api_key="KEY123", base=self.base)
        self.assertEqual((res[0]["items"], res[0]["error"]), (2, None))
        paths = [c[0] for c in FakeHttp.calls]
        self.assertIn("engine=google_hotels", paths[0])
        self.assertIn("check_in_date=2026-10-20", paths[0])
        self.assertIn("next_page_token=P2", paths[1])
        env = json.loads(next(self.inbox.glob("serpapi-*.json")).read_text(encoding="utf-8"))
        self.assertEqual((env["source"], env["query"]["destination"], [p["name"] for p in env["items"]]), ("serpapi_hotels", "Nha Trang", ["trang 1", "trang 2"]))

    def test_serpapi_error_is_recorded_and_key_is_redacted(self):
        res = api.fetch_serpapi(api.FetchOptions(destinations=["Nha Trang"]), self.inbox, api_key="BAD", base=self.base)
        self.assertIsNone(res[0]["file"])
        self.assertIn("Invalid API key", res[0]["error"])
        res = api.fetch_serpapi(api.FetchOptions(destinations=["Nha Trang"]), self.inbox, api_key="SECRETKEY", base="http://127.0.0.1:9")
        self.assertNotIn("SECRETKEY", res[0]["error"])

    def test_travelpayouts_uses_header_token_and_reports_bad_routes(self):
        opts = api.FetchOptions(destinations=["x"], routes=["HAN-SGN", "hanoi-saigon"], month="2026-10")
        res = api.fetch_travelpayouts(opts, self.inbox, token="TP-TOKEN", base=self.base)
        self.assertEqual([bool(r["file"]) for r in res], [True, False])
        self.assertIn("không hợp lệ", res[1]["error"])
        path, headers = FakeHttp.calls[0]
        self.assertEqual(headers["X-Access-Token"], "TP-TOKEN")
        self.assertNotIn("TP-TOKEN", path, "token không nằm trên URL")
        self.assertIn("origin=HAN", path)
        self.assertIn("departure_at=2026-10", path)
        env = json.loads(next(self.inbox.glob("travelpayouts-*.json")).read_text(encoding="utf-8"))
        self.assertEqual((env["source"], env["query"]["month"]), ("travelpayouts_flights", "2026-10"))

    def test_secrets_come_from_env_and_missing_ones_explain_how_to_fix(self):
        with mock.patch.object(ap, "load_env"), mock.patch.dict(os.environ, {"SERPAPI_KEY": "k"}, clear=False):
            os.environ.pop("APIFY_TOKEN", None)
            os.environ.pop("TRAVELPAYOUTS_TOKEN", None)
            self.assertEqual(api.token_status(), {"apify": False, "serpapi": True, "travelpayouts": False})
            with self.assertRaisesRegex(api.ApiError, r"APIFY_TOKEN.*\.env"):
                api.secret("APIFY_TOKEN")

    def test_unknown_kind(self):
        with self.assertRaisesRegex(api.ApiError, "không hỗ trợ"):
            api.fetch("google", api.FetchOptions(destinations=["A"]), self.inbox)


def synthetic_inbox(inbox: Path, price_factor: float = 1.0, tag: str = "a") -> None:
    """3 khách sạn Nha Trang có cả Agoda-API và Booking-API (Booking không toạ độ) + 1 khách sạn chỉ có Booking-API (sẽ bị loại vì thiếu toạ độ)."""
    hotels = [("Sunrise Beach Hotel", "sunrise-beach-hotel", 12.2451, 109.1953, 900000, 101), ("Golden Bay Resort", "golden-bay-resort", 12.2300, 109.1990, 1500000, 102),
              ("Lotus Garden Inn", "lotus-garden-inn", 12.2500, 109.1900, 400000, 103)]
    ag = [agoda_item(name=n, lat=lat, lng=lng, price=round(p * price_factor), url=f"https://www.agoda.com/vi-vn/{slug}/hotel/nha-trang-vn.html")
          for n, slug, lat, lng, p, _ in hotels]
    bk = [booking_item(name=n, price=round(p * 1.03 * price_factor), hotelId=hid, url=f"https://www.booking.com/hotel/vn/{slug}.html") for n, slug, _, _, p, hid in hotels]
    bk.append(booking_item(name="Khách sạn Không Có Toạ Độ Xyz", price=300000, hotelId=999, url="https://www.booking.com/hotel/vn/xyz.html"))
    q = {"destination": "Nha Trang", "checkin": "2026-10-20", "checkout": "2026-10-21", "adults": 2, "currency": "VND"}
    bk = [{**b, "checkout": "2026-10-21"} for b in bk]
    for name, src, items in ((f"agoda-{tag}.json", "apify_agoda", ag), (f"booking-{tag}.json", "apify_booking", bk)):
        api.write_file_atomic(inbox / name, api.make_envelope(src, items, q, 0.05))
        age(inbox / name)


class ApiPipeline(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.root = Path(self._t.name)
        self.env = mock.patch.dict(os.environ, {"VOTA_DATA_DIR": str(self.root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self._t.cleanup()

    def run_pd(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = pd.main(list(args))
        return code

    def state(self, run_id):
        return json.loads((self.root / "demo" / "runs" / run_id / "state.json").read_text(encoding="utf-8"))

    def products(self, run_id):
        return [json.loads(x) for x in (self.root / "demo" / "runs" / run_id / "products.jsonl").read_text(encoding="utf-8").split("\n") if x]

    def test_only_api_run_turns_dropped_files_into_catalog_rows(self):
        synthetic_inbox(self.root / "demo" / "inbox")
        code = self.run_pd("run", "--only-api", "--no-db", "--replay-delay-ms", "0", "--run-id", "20260921-100000-a1")
        st = self.state("20260921-100000-a1")
        self.assertEqual((code, st["status"]), (0, "succeeded"), st["log"][-4:])
        self.assertEqual([r["status"] for r in st["inbox"]["results"]], ["done", "done"])
        feeds = {k: (v["mode"], v["received"]) for k, v in st["feeds"].items() if v["total"]}
        self.assertEqual(feeds, {"api_agoda": ("api", 3), "api_booking": ("api", 4)})
        rows = self.products("20260921-100000-a1")
        props = [r for r in rows if r["attributes"].get("level") == "property"]
        self.assertEqual(sorted(p["name"] for p in props), ["Golden Bay Resort", "Lotus Garden Inn", "Sunrise Beach Hotel"])
        for p in props:
            a = p["attributes"]
            self.assertEqual((a["locationSource"], a["locationPrecision"], p["destination"]), ("agoda.com (API)", "exact", "Nha Trang"))
            self.assertIn("booking.com", a["otaPrices"])
            self.assertIn("agoda.com", a["otaPrices"])
            self.assertEqual(sorted(p), sorted(["attributes", "available", "availableFrom", "availableTo", "currency", "description", "destination", "imageUrl",
                                                "name", "productId", "sourceRef", "taxonomy", "unitPrice"]), "vẫn đúng 13 trường")
        self.assertEqual(sum(1 for r in rows if r["attributes"].get("level") == "room"), 3)
        self.assertTrue(any("thiếu toạ độ" in k for k in st["dropped"]), "khách sạn chỉ có Booking-API phải bị loại kèm lý do")
        self.assertNotIn("Khách sạn Không Có Toạ Độ Xyz", [r["name"] for r in rows])
        self.assertIsNone(st["changes"], "lượt đầu chưa có gì để so")

    def test_booking_full_alone_gives_rooms_coordinates_and_description_without_other_sources(self):
        q = {"destination": "Nha Trang", "checkin": "2026-10-20", "checkout": "2026-10-22", "adults": 2, "currency": "VND"}
        items = [booking_full_item(), booking_full_item(name="Lotus Garden Inn", url="https://www.booking.com/hotel/vn/lotus.html", hotelId=42,
                                                            location={"lat": 12.2500, "lng": 109.1900})]
        api.write_file_atomic(self.root / "demo" / "inbox" / "b.json", api.make_envelope("apify_booking_full", items, q))
        age(self.root / "demo" / "inbox" / "b.json")
        code = self.run_pd("run", "--only-api", "--no-db", "--replay-delay-ms", "0", "--run-id", "20260921-100000-bf")
        self.assertEqual(code, 0, self.state("20260921-100000-bf")["log"][-3:])
        rows = self.products("20260921-100000-bf")
        props = [r for r in rows if r["attributes"].get("level") == "property"]
        self.assertEqual(len(props), 2)
        self.assertEqual(len([r for r in rows if r["attributes"].get("level") == "room"]), 6, "mỗi khách sạn 2 hạng phòng có giá (hạng không giá bị loại)")
        for p in props:
            self.assertTrue(p["description"])
            self.assertEqual((p["attributes"]["locationSource"], p["attributes"]["locationPrecision"]), ("booking.com (API)", "exact"))
        cov = self.state("20260921-100000-bf")["coverage"]
        self.assertEqual((cov["hotel/property"]["fields"]["toạ độ"], cov["hotel/room"]["rows"]), (100, 6))

    def test_second_batch_refreshes_prices_and_reports_changes(self):
        inbox = self.root / "demo" / "inbox"
        synthetic_inbox(inbox)
        self.run_pd("run", "--only-api", "--no-db", "--replay-delay-ms", "0", "--run-id", "20260921-100000-a1")
        time.sleep(1.1)  # bản ghi mới phải có crawledAt lớn hơn
        synthetic_inbox(inbox, price_factor=1.10, tag="b")
        self.run_pd("run", "--only-api", "--no-db", "--replay-delay-ms", "0", "--run-id", "20260921-100100-a2")
        st = self.state("20260921-100100-a2")
        ch = st["changes"]
        self.assertEqual((ch["previousRun"], ch["previousRows"], ch["rows"], ch["new"], ch["removed"]), ("20260921-100000-a1", 6, 6, 0, 0))
        self.assertGreaterEqual(ch["priceChanged"], 3)
        self.assertTrue(all(e["after"] > e["before"] for e in ch["examples"]))
        old = {p["name"]: p["unitPrice"] for p in self.products("20260921-100000-a1") if p["attributes"].get("level") == "property"}
        new = {p["name"]: p["unitPrice"] for p in self.products("20260921-100100-a2") if p["attributes"].get("level") == "property"}
        self.assertTrue(all(new[n] > old[n] for n in old), "cùng mã sản phẩm, giá mới thay giá cũ (không sinh dòng trùng)")
        self.assertEqual(len(new), 3)

    def test_empty_inbox_and_store_fail_with_a_helpful_message(self):
        code = self.run_pd("run", "--only-api", "--no-db", "--replay-delay-ms", "0", "--run-id", "20260921-100000-a1")
        st = self.state("20260921-100000-a1")
        self.assertEqual((code, st["stages"][1]["status"]), (1, "failed"))
        self.assertRegex(st["stages"][1]["metrics"]["error"], "hộp thư đến và kho API đều trống")

    def test_default_run_never_touches_the_api_store(self):
        """Lượt mặc định (phát lại) phải giữ nguyên hành vi cũ: kho API chỉ vào khi có --api / --only-api."""
        synthetic_inbox(self.root / "demo" / "inbox")
        self.run_pd("run", "--only-api", "--no-db", "--replay-delay-ms", "0", "--run-id", "20260921-100000-a1")
        src = self.root / "data"
        write(src / "interim" / "agoda_hotels.jsonl", "")
        self.assertEqual(pd.select_feeds(src, [], None, store_dir=None)["api_agoda"], [])
        self.assertEqual(len(pd.select_feeds(src, [], None, store_dir=self.root / "demo" / "store", use_cache=False)["api_agoda"]), 3)

    def test_auto_processes_a_dropped_file_by_itself_and_ignores_an_empty_inbox(self):
        self.assertEqual(self.run_pd("auto", "--only-api", "--no-db", "--replay-delay-ms", "0", "--every", "0", "--max-cycles", "1"), 0)
        self.assertFalse((self.root / "demo" / "runs").exists(), "hộp thư trống thì không chạy gì")
        synthetic_inbox(self.root / "demo" / "inbox")
        self.assertEqual(self.run_pd("auto", "--only-api", "--no-db", "--replay-delay-ms", "0", "--every", "0", "--max-cycles", "1"), 0)
        runs = list((self.root / "demo" / "runs").iterdir())
        self.assertEqual(len(runs), 1)
        self.assertEqual(json.loads((runs[0] / "state.json").read_text(encoding="utf-8"))["status"], "succeeded")
        self.assertEqual(api.inbox_overview(self.root / "demo" / "inbox")["waiting"], [])

    def test_pull_fetches_then_runs_and_a_failed_fetch_skips_the_run(self):
        def fake_fetch(kind, opts, inbox, on_event=None, **kw):
            synthetic_inbox(inbox)
            on_event({"destination": "Nha Trang", "items": 3, "costUsd": 0.05, "file": "x", "error": None})
            return [{"destination": "Nha Trang", "items": 3, "costUsd": 0.05, "file": "x", "error": None}]
        with mock.patch.object(api, "fetch", fake_fetch):
            self.assertEqual(self.run_pd("pull", "apify-agoda", "--destinations", "Nha Trang", "--only-api", "--no-db", "--replay-delay-ms", "0",
                                         "--run-id", "20260921-100000-p1"), 0)
        self.assertEqual(self.state("20260921-100000-p1")["status"], "succeeded")
        fetch = json.loads((self.root / "demo" / "fetch.json").read_text(encoding="utf-8"))
        self.assertEqual((fetch["status"], fetch["done"], fetch["items"], fetch["costUsd"]), ("done", 1, 3, 0.05))
        with mock.patch.object(api, "fetch", side_effect=ap.ApifyError("hết credit")):
            self.assertEqual(self.run_pd("pull", "apify-agoda", "--only-api", "--no-db", "--run-id", "20260921-100100-p2"), 1)
        self.assertFalse((self.root / "demo" / "runs" / "20260921-100100-p2").exists(), "tải lỗi thì không tạo lượt xử lý")
        self.assertEqual(json.loads((self.root / "demo" / "fetch.json").read_text(encoding="utf-8"))["status"], "failed")

    def test_pull_does_not_lose_a_file_written_the_instant_before_processing(self):
        """Hồi quy lỗi thật gặp 22/09/2026: fetch xong rồi xử lý ngay trong cùng một giây → intake() coi file vừa ghi là 'chưa nằm yên' và bỏ qua,
        báo hộp thư trống dù file vẫn còn nguyên. fake_fetch KHÔNG age() file, đúng như write_file_atomic() thật ghi ra."""
        def fake_fetch(kind, opts, inbox, on_event=None, **kw):
            q = {"destination": "Nha Trang", "checkin": opts.checkin, "checkout": opts.checkout, "adults": 2, "currency": "USD"}
            api.write_file_atomic(inbox / "apify-booking-full-nha-trang.json", api.make_envelope("apify_booking_full", [booking_full_item()], q, 0.05))
            on_event({"destination": "Nha Trang", "items": 1, "costUsd": 0.05, "file": "x", "error": None})
            return [{"destination": "Nha Trang", "items": 1, "costUsd": 0.05, "file": "x", "error": None}]
        with mock.patch.object(api, "fetch", fake_fetch):
            code = self.run_pd("pull", "apify-booking-full", "--destinations", "Nha Trang", "--only-api", "--no-db", "--replay-delay-ms", "0",
                               "--run-id", "20260922-100000-race")
        st = self.state("20260922-100000-race")
        self.assertEqual((code, st["status"]), (0, "succeeded"), st["log"][-5:])
        self.assertEqual(st["stages"][1]["metrics"]["inboxRecords"], 1, "file vừa fetch xong phải được xử lý ngay trong cùng lượt pull, không bị bỏ sót")

    def test_fetch_without_token_says_where_to_put_it(self):
        with mock.patch.object(ap, "load_env"), mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("APIFY_TOKEN", None)
            buf = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(buf):
                code = pd.main(["fetch", "apify-agoda"])
        self.assertEqual(code, 1)
        self.assertRegex(buf.getvalue(), r"APIFY_TOKEN.*\.env")

    def test_intake_command_and_fetch_lock(self):
        synthetic_inbox(self.root / "demo" / "inbox")
        self.assertEqual(self.run_pd("intake"), 0)
        self.assertTrue((self.root / "demo" / "store" / "interim" / "agoda_hotels.jsonl").exists())
        write(self.root / "demo" / "fetch.json", {"status": "fetching", "pid": os.getppid()})
        self.assertEqual(self.run_pd("fetch", "apify-agoda"), 2, "đang có lượt tải khác thì từ chối")


class TokenAndProbe(unittest.TestCase):
    """save_env_var/clear_env_var (không bao giờ đụng .env thật của người dùng — luôn vá api.ENV_PATH vào file tạm) và probe_kind."""

    def test_save_creates_env_from_example_keeping_comments_and_other_keys(self):
        with tempfile.TemporaryDirectory() as t:
            tmp_env = Path(t) / ".env"
            with mock.patch.object(api, "ENV_PATH", tmp_env):
                api.save_env_var("APIFY_TOKEN", "abc123")
                text = tmp_env.read_text(encoding="utf-8")
                self.assertIn("APIFY_TOKEN=abc123", text)
                self.assertIn("SERPAPI_KEY=", text)          # khoá khác vẫn còn, vẫn trống
                self.assertIn("DEMO_DB_PASSWORD=postgres", text)  # dòng không thuộc ENV_KEYS được giữ nguyên
                self.assertIn("# Sao chép thành .env", text)  # chú thích từ .env.example được giữ
                self.assertTrue(oct(tmp_env.stat().st_mode)[-3:] in ("600", "700"))  # chỉ chủ sở hữu đọc/ghi được

    def test_save_replaces_existing_value_without_touching_other_lines(self):
        with tempfile.TemporaryDirectory() as t:
            tmp_env = Path(t) / ".env"
            tmp_env.write_text("# ghi chú riêng\nAPIFY_TOKEN=old\nKEEP_ME=1\nSERPAPI_KEY=already\nTRAVELPAYOUTS_TOKEN=\n", encoding="utf-8")
            with mock.patch.object(api, "ENV_PATH", tmp_env):
                api.save_env_var("APIFY_TOKEN", "new-value")
                lines = tmp_env.read_text(encoding="utf-8").split("\n")
                self.assertEqual(lines, ["# ghi chú riêng", "APIFY_TOKEN=new-value", "KEEP_ME=1", "SERPAPI_KEY=already", "TRAVELPAYOUTS_TOKEN=", ""])
                self.assertEqual(os.environ["APIFY_TOKEN"], "new-value")
                os.environ.pop("APIFY_TOKEN", None)

    def test_clear_empties_only_the_named_key(self):
        with tempfile.TemporaryDirectory() as t:
            tmp_env = Path(t) / ".env"
            tmp_env.write_text("APIFY_TOKEN=secret\nSERPAPI_KEY=other\nTRAVELPAYOUTS_TOKEN=\n", encoding="utf-8")
            with mock.patch.object(api, "ENV_PATH", tmp_env), mock.patch.dict(os.environ, {"APIFY_TOKEN": "secret"}):
                api.clear_env_var("APIFY_TOKEN")
                self.assertEqual(tmp_env.read_text(encoding="utf-8"), "APIFY_TOKEN=\nSERPAPI_KEY=other\nTRAVELPAYOUTS_TOKEN=\n")
                self.assertNotIn("APIFY_TOKEN", os.environ)

    def test_known_keys_missing_from_an_existing_env_are_appended_blank(self):
        """.env chưa có sẵn cả 3 khoá (vd. người dùng tự tạo tay) → sau khi lưu một khoá, các khoá còn lại được thêm vào (trống), để .env luôn tự mô tả đủ."""
        with tempfile.TemporaryDirectory() as t:
            tmp_env = Path(t) / ".env"
            tmp_env.write_text("APIFY_TOKEN=old\n", encoding="utf-8")
            with mock.patch.object(api, "ENV_PATH", tmp_env):
                api.save_env_var("APIFY_TOKEN", "new")
                text = tmp_env.read_text(encoding="utf-8")
                self.assertIn("APIFY_TOKEN=new", text)
                self.assertIn("SERPAPI_KEY=", text)
                self.assertIn("TRAVELPAYOUTS_TOKEN=", text)

    def test_save_and_clear_reject_unknown_keys_and_bad_values(self):
        with tempfile.TemporaryDirectory() as t:
            with mock.patch.object(api, "ENV_PATH", Path(t) / ".env"):
                for bad_key in ("DEMO_DB_PASSWORD", "PATH", "APIFY_TOKEN; rm -rf /"):
                    with self.subTest(bad_key=bad_key), self.assertRaises(api.ApiError):
                        api.save_env_var(bad_key, "x")
                    with self.subTest(bad_key=bad_key), self.assertRaises(api.ApiError):
                        api.clear_env_var(bad_key)
                for bad_value in ("", "   ", "a\nb", "x" * 400):
                    with self.subTest(bad_value=repr(bad_value)), self.assertRaises(api.ApiError):
                        api.save_env_var("APIFY_TOKEN", bad_value)
                self.assertFalse((Path(t) / ".env").exists(), "mọi lần bị từ chối đều không được ghi file")

    def test_save_error_message_never_contains_the_value(self):
        with tempfile.TemporaryDirectory() as t, mock.patch.object(api, "ENV_PATH", Path(t) / ".env"):
            try:
                api.save_env_var("APIFY_TOKEN", "a\nSECRET-LEAK\nb")
                self.fail("phải bị từ chối")
            except api.ApiError as e:
                self.assertNotIn("SECRET-LEAK", str(e))

    def test_probe_kind_builds_actor_input_and_reads_back_items(self):
        captured = {}

        def fake_probe(actor, input_, *, limit, max_usd, out_dir, client=None, on_status=None):
            captured.update(actor=actor, input_=input_, limit=limit, max_usd=max_usd)
            path = out_dir / "fake.json"
            api.write_file_atomic(path, {"actor": actor, "input": input_, "costUsd": 0.02, "items": [{"name": "A"}, {"name": "B"}]})
            return {"path": path, "count": 2, "costUsd": 0.02, "fields": [{"key": "name", "types": "str", "filledPct": 100, "example": "A"}]}

        with tempfile.TemporaryDirectory() as t, mock.patch.object(ap, "probe", fake_probe):
            res = api.probe_kind("apify-agoda", "Nha Trang", 5, 0.1, Path(t))
        self.assertEqual((res["kind"], res["actor"], res["count"], res["costUsd"]), ("apify-agoda", "agentx/agoda-hotels-scraper", 2, 0.02))
        self.assertEqual([i["name"] for i in res["items"]], ["A", "B"])
        self.assertEqual(captured["limit"], 5)
        self.assertTrue(captured["input_"]["location"].endswith(", Vietnam"))

    def test_probe_kind_rejects_non_apify_kind(self):
        with self.assertRaisesRegex(api.ApiError, "không xem thử được"):
            api.probe_kind("serpapi", "Nha Trang", 5, 0.1, Path("."))


@unittest.skipUnless(hasattr(os, "fork"), "cần fork() (Linux/macOS)")
class PidAlive(unittest.TestCase):
    """Hồi quy lỗi thật 22/09/2026: os.kill(pid, 0) vẫn thành công với tiến trình đã chết ở trạng thái zombie (chưa bị cha "nhận xác"),
    khiến giao diện báo "đang tải" mãi dù việc cào đã dừng hẳn. Dùng zombie THẬT (fork rồi không waitpid ngay), không giả lập."""

    def test_zombie_child_is_not_alive(self):
        pid = os.fork()
        if pid == 0:
            os._exit(0)  # tiến trình con: thoát ngay, thành zombie cho tới khi cha waitpid
        try:
            for _ in range(50):  # đợi con thật sự chuyển sang trạng thái Z (thường tức thì, nhưng chừa dư)
                if Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split(") ", 1)[1][0] == "Z":
                    break
                time.sleep(0.02)
            self.assertFalse(monitor.pid_alive(pid), "zombie không được coi là còn sống")
        finally:
            os.waitpid(pid, 0)  # dọn sạch: không để lại zombie thật sau khi test xong

    def test_real_running_process_is_alive_and_gone_process_is_not(self):
        pid = os.fork()
        if pid == 0:
            time.sleep(5)
            os._exit(0)
        try:
            self.assertTrue(monitor.pid_alive(pid))
        finally:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        self.assertFalse(monitor.pid_alive(pid))

    def test_pid_that_never_existed(self):
        self.assertFalse(monitor.pid_alive(2**30))


class MonitorSettings(unittest.TestCase):
    def test_save_and_clear_token_through_monitor(self):
        # has_secret()/token_status() gọi apify_source.load_env() nạp từ ROOT/.env THẬT (không đi qua api.ENV_PATH đã vá) — phải chặn nốt
        # cái này, nếu không test sẽ đọc nhầm .env thật của máy đang chạy (có thể đang có token thật, như sau khi người dùng vừa dán).
        with tempfile.TemporaryDirectory() as t, mock.patch.object(api, "ENV_PATH", Path(t) / ".env"), mock.patch.object(ap, "load_env"):
            m = monitor.Monitor(Path(t))
            self.assertEqual(m.save_token("APIFY_TOKEN", "  tok-abc  "), {"apify": True, "serpapi": False, "travelpayouts": False})
            self.assertEqual(m.clear_token("APIFY_TOKEN"), {"apify": False, "serpapi": False, "travelpayouts": False})
            with self.assertRaises(api.ApiError):
                m.save_token("NOT_A_REAL_KEY", "x")

    def test_run_probe_validates_and_clamps_before_calling_apify(self):
        with tempfile.TemporaryDirectory() as t:
            m = monitor.Monitor(Path(t))
            with mock.patch.object(api, "probe_kind") as pk:
                for bad in ("Nha Trang; DROP TABLE", "x" * 61):  # ký tự lạ / quá dài đều phải bị chặn trước khi gọi Apify
                    with self.subTest(bad=bad[:20]), self.assertRaises(ValueError):
                        m.run_probe("apify-agoda", bad, 5, 0.1)
            pk.assert_not_called()
            with mock.patch.object(api, "probe_kind", return_value={"ok": True}) as pk:
                out = m.run_probe("apify-agoda", "", 999, 999)  # điểm đến trống -> mặc định Nha Trang, không phải lỗi
                self.assertEqual(pk.call_args.args[:4], ("apify-agoda", "Nha Trang", 10, 0.5), "limit/maxUsd bị chặn ở trần an toàn")
                self.assertEqual(out, {"ok": True})


class MonitorApi(unittest.TestCase):
    def test_pull_validation_tokens_and_safe_command(self):
        with tempfile.TemporaryDirectory() as t:
            m = monitor.Monitor(Path(t))
            with mock.patch.object(api, "token_status", return_value={"apify": False, "serpapi": True, "travelpayouts": False}):
                with self.assertRaises(ValueError):
                    m.start_pull({"source": "rm -rf"})
                self.assertEqual(m.start_pull({"source": "apify-agoda"})[0], 400, "chưa có token thì không chạy")
                with mock.patch("subprocess.Popen") as popen:
                    for bad in ({"source": "serpapi", "destinations": "a; rm -rf /"}, {"source": "serpapi", "maxItems": "abc"}):
                        with self.subTest(bad=bad), self.assertRaises(ValueError):
                            m.start_pull(bad)
                    code, body = m.start_pull({"source": "serpapi", "destinations": "Nha Trang,Phú Quốc", "maxItems": 99999, "maxUsd": 99, "pages": 50})
                    self.assertEqual(code, 200)
                    argv = popen.call_args.args[0]
                    self.assertEqual(argv[2:4], ["pull", "serpapi"])
                    self.assertEqual(argv[argv.index("--max-items") + 1], "500", "trần cứng 500 mục/điểm đến")
                    self.assertEqual(argv[argv.index("--max-usd") + 1], "5.0", "trần cứng $5")
                    self.assertEqual(argv[argv.index("--pages") + 1], "5")
                    self.assertIn("--only-api", argv)
                    self.assertNotIn("--db-port", argv)
                    self.assertEqual(popen.call_args.kwargs["env"]["VOTA_DATA_DIR"], str(Path(t)))
                write(Path(t) / "demo" / "fetch.json", {"status": "fetching", "pid": os.getpid()})
                with mock.patch("subprocess.Popen") as popen:
                    self.assertEqual(m.start_pull({"source": "serpapi"})[0], 409)
                    popen.assert_not_called()

    def test_config_inbox_and_stale_fetch(self):
        with tempfile.TemporaryDirectory() as t:
            m = monitor.Monitor(Path(t))
            cfg = m.pipeline_config()
            self.assertEqual(set(cfg["tokens"]), {"apify", "serpapi", "travelpayouts"})
            self.assertEqual(len(cfg["defaultDestinations"]), 15)
            self.assertEqual(m.pipeline_inbox()["counts"]["_processed"], 0)
            self.assertEqual(m.pipeline_fetch(), {"status": "idle"})
            write(Path(t) / "demo" / "fetch.json", {"status": "fetching", "pid": 999999999})
            self.assertEqual((m.pipeline_fetch()["status"], m.pipeline_fetch()["stale"]), ("failed", True))


if __name__ == "__main__":
    unittest.main()
