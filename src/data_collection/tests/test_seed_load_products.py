"""Hồi quy cho catalog_meta.py và load_products.py theo MOCK_DATA_SPEC §2: cửa sổ 30 ngày, ngày bay, lịch khả dụng, giờ nhận/trả phòng."""
import json
import re
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from data_collection.seed import catalog_meta as cm
from data_collection.seed import config as C
from data_collection.seed import load_products as lc

AS_OF = date(2026, 9, 20)


def product(pid, name, taxonomy, level=None, parent=None, price=1000000, dest="Nha Trang", ref=None, src_from=None, src_to=None,
            available=None, **attrs):
    a = {"level": level, "parentProductId": parent, **attrs}
    return {"productId": pid, "name": name, "taxonomy": taxonomy, "destination": dest, "description": "mô tả", "unitPrice": price,
            "currency": "VND", "available": price is not None if available is None else available, "availableFrom": src_from, "availableTo": src_to, "imageUrl": None,
            "sourceRef": ref or f"booking:{taxonomy}:{pid}", "attributes": {k: v for k, v in a.items() if v is not None}}


def fixture():
    return [
        product("h1", "Khách sạn A", "hotel", "property", price=500000),
        product("r1", "Khách sạn A - Deluxe", "hotel", "room", parent="h1", price=800000),
        product("r2", "Khách sạn A - Suite", "hotel", "room", parent="h1", price=None),
        product("h2", "Khách sạn B (không phòng)", "hotel", "property", price=400000),
        product("rt", "Vé máy bay Hà Nội - Nha Trang", "flight", "route", price=900000),
        product("f1", "VN1: Hà Nội - Nha Trang", "flight", "flight", parent="rt", price=900000, datesSeen=["2026-09-01", "2026-10-05", "2026-10-06"],
                departureAt="2026-10-05T16:20:00+07:00", arrivalAt="2026-10-05T18:30:00+07:00"),
        product("f2", "VN2: Hà Nội - Nha Trang", "flight", "flight", parent="rt", price=950000, datesSeen=["2026-11-30"],
                departureAt="2026-11-30T23:00:00+07:00", arrivalAt="2026-12-01T01:10:00+07:00"),
        product("f3", "VN3: Hà Nội - Nha Trang", "flight", "flight", parent="rt", price=990000, src_from="2026-10-02", src_to="2026-10-02"),
        product("t1", "Vé A", "attraction", price=300000, src_from="2025-01-01", src_to="2026-09-30"),
        product("t2", "Điểm B chưa giá", "attraction", price=None, available=True),
        product("t3", "Vé hết hạn", "attraction", price=100000, src_from="2025-01-01", src_to="2026-09-15"),
        product("c1", "Combo C", "combo", price=500000, src_from="2026-12-01", src_to="2027-06-01"),
        product("g1", "Golf", "golf", price=1700000, src_from="2026-03-01", src_to="2026-10-31"),
    ]


class MetaTests(unittest.TestCase):
    def test_roles_follow_the_schema_doc(self):
        m = cm.build_meta(fixture())
        self.assertFalse(m["h1"]["is_bookable"])                      # khách sạn cha không đặt trực tiếp
        self.assertTrue(m["r1"]["is_bookable"])
        self.assertFalse(m["r2"]["is_bookable"])                      # phòng chưa giá không đặt được
        self.assertTrue(m["h1"]["is_search_unit"] and m["h1"]["is_recommendable"])  # có ≥ 1 phòng đặt được
        self.assertFalse(m["h2"]["is_recommendable"])                 # không có phòng: tìm được, không được gợi ý
        self.assertFalse(m["rt"]["is_bookable"])
        self.assertFalse(m["f1"]["is_search_unit"])                   # chuyến bay dùng vector của tuyến cha
        self.assertTrue(m["t1"]["is_bookable"])
        self.assertFalse(m["t2"]["is_bookable"] or m["t2"]["is_recommendable"])  # điểm chưa giá
        self.assertEqual(m["r1"]["parent_product_id"], "h1")

    def test_window_and_calendars(self):
        self.assertEqual(cm.window(AS_OF), (date(2026, 9, 20), date(2026, 10, 19)))  # 30 đêm, gồm cả hôm nay
        r = fixture()[1]
        cal = cm.room_calendar(r, AS_OF)
        self.assertEqual(len(cal), 30)
        self.assertLessEqual(set(cal), {"0", "1"})
        self.assertEqual(cal, cm.room_calendar(r, AS_OF))              # xác định theo (productId, as_of)
        self.assertTrue(cm.open_nights("1110", AS_OF, date(2026, 9, 21), 2))
        self.assertFalse(cm.open_nights("1110", AS_OF, date(2026, 9, 22), 2))
        self.assertFalse(cm.open_nights("1111", AS_OF, date(2026, 9, 19), 1))    # trước cửa sổ


    def test_room_calendars_follow_spec(self):
        rooms = [product(f"x{i}", "x", "hotel", "room", parent="h1") for i in range(300)]
        vin_rooms = [product(f"v{i}", "x", "hotel", "room", parent="h1", brand="Vinpearl") for i in range(300)]
        cals = [cm.room_calendar(r, AS_OF) for r in rooms]
        vin = [cm.room_calendar(r, AS_OF) for r in vin_rooms]
        for c in cals + vin:                                           # mọi phòng kín 25–40% (Vinpearl chặn trên 40%)
            self.assertTrue(C.ROOM_CLOSED_SHARE[0] <= c.count("0") / 30 <= C.ROOM_CLOSED_CAP, c)
            self.assertTrue(all(len(run) <= C.ROOM_CLOSED_CLUSTER[1] for run in re.findall("0+", c)), c)   # cụm 1–4 đêm
        self.assertGreater(sum(c.count("0") for c in vin), sum(c.count("0") for c in cals))              # Vinpearl kín nhiều hơn
        weekend = [i for i in range(30) if (AS_OF + timedelta(days=i)).weekday() in (4, 5)]
        other = [i for i in range(30) if i not in weekend]

        def rate(idx):
            return sum(c[i] == "0" for c in cals for i in idx) / (len(cals) * len(idx))

        self.assertAlmostEqual(rate(weekend) / rate(other), C.ROOM_WEEKEND_MULT, delta=0.2)   # T6/T7 dễ kín ×1,5 mỗi đêm
        by_id = {"hv": product("hv", "Vinpearl Resort", "hotel", "property", ref="vinpearl:hotel:hv")}
        child = product("rv", "Vinpearl Resort - Deluxe", "hotel", "room", parent="hv")
        self.assertTrue(cm.is_vinpearl(child, by_id))                  # phòng nhận brand của property cha
        self.assertFalse(cm.is_vinpearl(child))

    def test_ticket_blackout_for_fifteen_percent(self):
        cals = [cm.ticket_calendar(f"t{i}", AS_OF) for i in range(2000)]
        closed = [c for c in cals if "0" in c]
        self.assertAlmostEqual(len(closed) / len(cals), C.TICKET_BLACKOUT_SHARE, delta=0.03)             # 15% sản phẩm
        self.assertTrue(all(C.TICKET_BLACKOUT_DAYS[0] <= c.count("0") <= C.TICKET_BLACKOUT_DAYS[1] for c in closed))  # 2–3 ngày
        self.assertEqual(cals[:50], [cm.ticket_calendar(f"t{i}", AS_OF) for i in range(50)])             # xác định


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.stats = lc.convert(fixture(), {"c1": {"attributes": {"priceBasis": "per_person", "nights": 2}}}, AS_OF)
        self.by = {r["product_id"]: r for r in self.rows}

    def test_clip_rules(self):
        lo, hi = date(2026, 9, 20), date(2026, 10, 19)
        self.assertEqual(lc.clip(None, None, lo, hi), ("2026-09-20", "2026-10-19"))                 # nguồn không có → cả cửa sổ
        self.assertEqual(lc.clip("2025-01-01", "2026-09-30", lo, hi), ("2026-09-20", "2026-09-30"))  # GREATEST / LEAST
        self.assertEqual(lc.clip("2026-12-01", "2027-06-01", lo, hi), ("2026-12-01", "2026-10-19"))  # from > to
        self.assertEqual(lc.clip("2026-10-01", "2026-12-01", lo, hi), ("2026-10-01", "2026-10-19"))

    def test_dense_real_room_calendar_overrides_fallback_but_sparse_samples_do_not(self):
        queried = [(AS_OF + timedelta(days=i)).isoformat() for i in range(30)]
        priced = {(AS_OF + timedelta(days=i)).isoformat(): 900000 for i in range(30) if i % 3}
        expected = "".join("0" if i % 3 == 0 else "1" for i in range(30))
        self.assertEqual(lc.real_room_calendar(priced, queried, AS_OF), expected)
        self.assertIsNone(lc.real_room_calendar(priced, queried[:25], AS_OF))
        self.assertIsNotNone(lc.real_room_calendar({}, queried[:26], AS_OF))
        self.assertIsNone(lc.real_room_calendar(priced, queried[:20] + [
            (AS_OF + timedelta(days=60 + i)).isoformat() for i in range(10)
        ], AS_OF))

        rows = fixture() + [product("r3", "Khách sạn A - Real", "hotel", "room", parent="h1", price=900000,
                                    pricesByDate=priced, pricesByDateQueried=queried)]
        converted, stats = lc.convert(rows, {}, AS_OF)
        by_id = {row["product_id"]: row for row in converted}
        self.assertEqual(by_id["r3"]["attributes"]["availability"]["calendar"], expected)
        self.assertEqual(stats["lịch khả dụng: hotel_room (dữ liệu thật)"], 1)

    def test_source_range_is_clipped_and_expired_rows_become_unavailable(self):
        self.assertEqual((self.by["t1"]["available_from"], self.by["t1"]["available_to"], self.by["t1"]["available"]), ("2026-09-20", "2026-09-30", True))
        self.assertEqual(self.by["t1"]["attributes"]["availability"],
                         {"from": "2026-09-20", "days": 30, "calendar": cm.ticket_calendar("t1", AS_OF)[:11] + "0" * 19})  # ngày sau khi hết bán đóng
        self.assertFalse(self.by["t3"]["available"])                  # hết hạn từ 15/09
        self.assertEqual((self.by["t3"]["available_from"], self.by["t3"]["available_to"]), (None, None))
        self.assertEqual((self.by["t3"]["attributes"]["sourceAvailableFrom"], self.by["t3"]["attributes"]["sourceAvailableTo"]),
                         ("2025-01-01", "2026-09-15"))
        self.assertEqual(self.by["t3"]["attributes"]["availability"]["calendar"], "0" * 30)
        self.assertFalse(self.by["c1"]["available"])                  # bắt đầu bán sau cửa sổ (from > to)
        self.assertEqual((self.by["c1"]["available_from"], self.by["c1"]["available_to"]), (None, None))
        self.assertEqual((self.by["g1"]["available_from"], self.by["g1"]["available_to"]), ("2026-09-20", "2026-10-19"))
        self.assertEqual((self.by["h1"]["available_from"], self.by["h1"]["available_to"]), ("2026-09-20", "2026-10-19"))
        self.assertTrue(self.by["t2"]["available"])                   # điểm chưa giá vẫn giữ available=true (quy ước demo)

    def test_flight_uses_real_date_in_window_else_mock_and_keeps_time_of_day(self):
        f1, f2 = self.by["f1"], self.by["f2"]
        self.assertEqual((f1["available_from"], f1["available_to"]), ("2026-10-05", "2026-10-05"))  # ngày thật sớm nhất trong cửa sổ
        self.assertEqual(f1["attributes"]["departureAt"], "2026-10-05T16:20:00+07:00")
        self.assertEqual(f2["available_from"], f2["available_to"])                                   # chuyến không có ngày thật: mock 1 ngày
        self.assertEqual(f2["available_from"], (AS_OF + timedelta(days=cm.stable_order_key("f2") % 30)).isoformat())  # as_of + crc32 % 30
        self.assertEqual(self.by["f3"]["available_from"], "2026-10-02")                              # sourceAvailableFrom trong cửa sổ
        d = f2["available_from"]
        self.assertEqual(f2["attributes"]["departureAt"], f"{d}T23:00:00+07:00")                    # giữ giờ
        self.assertTrue(f2["attributes"]["arrivalAt"].endswith("T01:10:00+07:00"))                   # giữ thời lượng, qua nửa đêm
        self.assertEqual(f2["attributes"]["arrivalAt"][:10], (date.fromisoformat(d) + timedelta(days=1)).isoformat())
        self.assertEqual(f2["attributes"]["datesSeen"], ["2026-11-30"])                              # ngày thật quan sát không bị sửa
        dates = sorted([f1["available_from"], f2["available_from"], self.by["f3"]["available_from"]])
        self.assertEqual((self.by["rt"]["available_from"], self.by["rt"]["available_to"]), (dates[0], dates[-1]))  # tuyến: khoảng của các chuyến con
        self.assertNotIn("availability", f1["attributes"])                                           # chuyến bay không có lịch

    def test_rooms_get_calendar_parents_do_not_and_combo_gets_attributes(self):
        self.assertEqual(self.by["r1"]["attributes"]["availability"],
                         {"from": "2026-09-20", "days": 30, "calendar": cm.room_calendar(fixture()[1], AS_OF)})
        self.assertEqual(set(self.by["g1"]["attributes"]["availability"]), {"from", "days", "calendar"})
        for pid in ("h1", "rt", "c1"):                                  # property, tuyến, combo: không có lịch
            self.assertNotIn("availability", self.by[pid]["attributes"])
        self.assertEqual((self.by["h1"]["attributes"]["checkInTime"], self.by["h1"]["attributes"]["checkOutTime"]),
                         (C.HOTEL_CHECK_IN, C.HOTEL_CHECK_OUT))         # giờ mặc định khi nguồn không có
        self.assertNotIn("checkInTime", self.by["r1"]["attributes"])
        self.assertEqual(self.by["c1"]["attributes"]["priceBasis"], "per_person")
        self.assertEqual(self.by["c1"]["attributes"]["nights"], 2)
        self.assertNotIn("nights", self.by["t1"]["attributes"])

    def test_columns_and_untouched_input(self):
        self.assertEqual(list(self.rows[0]), lc.COLUMNS)
        original = fixture()
        lc.convert(original, {}, AS_OF)
        self.assertEqual(original, fixture())                          # không sửa dữ liệu đầu vào

    def test_cli_writes_files_and_leaves_catalog_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "products.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in fixture()) + "\n", encoding="utf-8")
            (d / "combo_attributes.json").write_text(json.dumps({"c1": {"attributes": {"priceBasis": "per_package"}}}), encoding="utf-8")
            (d / "combo_items.jsonl").write_text('{"combo_product_id": "c1"}\n', encoding="utf-8")
            before = (d / "products.jsonl").read_bytes()
            self.assertEqual(lc.main(["--data-dir", str(d), "--as-of", "2026-09-20"]), 0)
            self.assertEqual((d / "products.jsonl").read_bytes(), before)
            out = [json.loads(l) for l in (d / "loader" / "cdp_products.jsonl").read_text(encoding="utf-8").split("\n") if l.strip()]
            self.assertEqual(len(out), len(fixture()))
            self.assertTrue((d / "loader" / "cdp_products.csv").exists() and (d / "loader" / "catalog_combo_items.jsonl").exists())
            self.assertIn("cửa sổ 2026-09-20", (d / "loader" / "loader_report.md").read_text(encoding="utf-8"))
            first = (d / "loader" / "cdp_products.jsonl").read_bytes()
            lc.main(["--data-dir", str(d), "--as-of", "2026-09-20"])
            self.assertEqual((d / "loader" / "cdp_products.jsonl").read_bytes(), first)  # chạy lại cho kết quả y hệt


if __name__ == "__main__":
    unittest.main()
