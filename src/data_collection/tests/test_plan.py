import unittest

from collectors.geo import AIRPORTS, DESTINATION_ALIASES, DESTINATION_CENTERS, destination_in_text
from collectors.plan import CORE_DESTINATIONS, DEFAULT_BUDGET, DESTINATIONS, select_destinations


class PlanConfigTests(unittest.TestCase):
    def test_core_fifteen_are_unchanged_and_first(self):
        self.assertEqual(len(CORE_DESTINATIONS), 15)
        self.assertEqual(CORE_DESTINATIONS[0], "Nha Trang")
        self.assertEqual(CORE_DESTINATIONS[-1], "Phan Thiết")

    def test_every_destination_is_known_to_geo(self):
        for d in DESTINATIONS:
            self.assertIn(d.name, DESTINATION_ALIASES, f"{d.name}: thiếu alias trong geo.py")
            self.assertIn(d.name, DESTINATION_CENTERS, f"{d.name}: thiếu toạ độ tâm trong geo.py")

    def test_names_are_unique_and_sources_not_duplicated(self):
        names = [d.name for d in DESTINATIONS]
        self.assertEqual(len(names), len(set(names)))
        for field in ("agoda_city", "trip_city", "trip_hotel_city_id"):
            values = [getattr(d, field) for d in DESTINATIONS if getattr(d, field)]
            self.assertEqual(len(values), len(set(values)), f"{field} bị trùng giữa hai điểm đến")

    def test_airports_are_real_and_not_shared(self):
        seen = {}
        for d in DESTINATIONS:
            for code in d.airports:
                self.assertIn(code, AIRPORTS, f"{d.name}: sân bay {code} chưa có toạ độ")
                self.assertNotIn(code, seen, f"{code} gán cho cả {seen.get(code)} và {d.name}")
                seen[code] = d.name

    def test_trip_and_agoda_ids_have_expected_shape(self):
        for d in DESTINATIONS:
            if d.trip_city:
                self.assertRegex(d.trip_city, r"^[a-z0-9-]+-\d+$", d.name)
            if d.agoda_city:
                self.assertRegex(d.agoda_city, r"^[a-z0-9-]+-vn$", d.name)
            if d.trip_hotel_city_id:
                self.assertRegex(d.trip_hotel_city_id, r"^\d+$", d.name)
            self.assertTrue(d.booking_query.isascii() and d.booking_query.strip(), d.name)

    def test_trip_hotel_city_ids_are_verified_not_guessed(self):
        # Đúng quy ước "chỉ ghi ID ĐÃ KIỂM CHỨNG" của agoda_city/trip_city: 12 điểm đến đã xác minh qua browser
        # thật (23/09/2026, đợt 2 thêm Huế/Quy Nhơn/Hạ Long/Cần Thơ cho ưu tiên combo) — số này chỉ được TĂNG
        # khi có thêm xác minh thật, không suy đoán thêm.
        verified = {d.name for d in DESTINATIONS if d.trip_hotel_city_id}
        self.assertEqual(
            verified,
            {"Nha Trang", "Phú Quốc", "Đà Nẵng", "Hà Nội", "TP. Hồ Chí Minh", "Hải Phòng", "Đà Lạt", "Phan Thiết",
             "Huế", "Quy Nhơn", "Hạ Long", "Cần Thơ"},
        )

    def test_budget_has_conservative_trip_hotels_default(self):
        self.assertEqual(DEFAULT_BUDGET.trip_hotels, 15)
        self.assertLess(DEFAULT_BUDGET.trip_hotels, DEFAULT_BUDGET.agoda_hotels)
        self.assertLess(DEFAULT_BUDGET.trip_hotels, DEFAULT_BUDGET.booking_hotels)

    def test_expanded_plan_reaches_about_fifty_and_ascii_names_resolve(self):
        self.assertGreaterEqual(len(DESTINATIONS), 60)
        chosen = select_destinations("Ninh Binh,Can Tho,Vung Tau")  # tên không dấu vẫn chọn được
        self.assertEqual([d.name for d in chosen], ["Ninh Bình", "Vũng Tàu", "Cần Thơ"])
        with self.assertRaises(SystemExit):
            select_destinations("Nơi Không Tồn Tại")

    def test_group_tokens_split_core_new_and_extra_without_overlap(self):
        core, new, extra, deep, everything = (select_destinations(t) for t in ("@core", "@new", "@extra", "@deep", "@all"))
        self.assertEqual((len(core), len(extra), len(deep)), (15, 19, 8))
        self.assertEqual(len(core) + len(new) + len(extra), len(everything))
        names = [{d.name for d in g} for g in (core, new, extra)]
        self.assertFalse(names[0] & names[1] or names[0] & names[2] or names[1] & names[2])
        self.assertLessEqual({d.name for d in deep}, names[0])  # 8 thị trường lớn đều nằm trong 15 điểm gốc
        self.assertEqual([d.name for d in select_destinations("@core,Ninh Binh")][-1], "Ninh Bình")

    def test_extra_destinations_are_booking_only_and_never_guess_ids(self):
        for d in select_destinations("@extra"):
            self.assertIsNone(d.agoda_city, d.name)
            self.assertIsNone(d.trip_city, d.name)
            self.assertEqual(d.airports, (), d.name)

    def test_sub_destinations_own_their_names_and_parents_keep_theirs(self):
        self.assertEqual(destination_in_text("Thị trấn Cát Bà, Hải Phòng"), "Cát Bà")
        self.assertEqual(destination_in_text("Phong Nha, Bố Trạch, Quảng Bình"), "Phong Nha")
        self.assertEqual(destination_in_text("Đường Lê Lợi, Đồng Hới, Quảng Bình"), "Quảng Bình")
        self.assertEqual(destination_in_text("Lý Sơn, Quảng Ngãi"), "Lý Sơn")
        self.assertEqual(destination_in_text("Số 5 Trần Phú, Hải Phòng"), "Hải Phòng")

    def test_street_names_that_look_like_places_do_not_decide_the_destination(self):
        self.assertEqual(destination_in_text("694 Đường Hai Bà Trưng phường Cẩm Phô, tp Hội An, Quảng Nam"), "Hội An")
        self.assertEqual(destination_in_text("No. 60 Bien Hoa Street, Phu Ly Ward, Ninh Binh Province"), "Ninh Bình")
        self.assertEqual(destination_in_text("Số 1 Phố Huế, Hai Bà Trưng, Hà Nội"), "Hà Nội")
        self.assertEqual(destination_in_text("Đường Đà Nẵng, Ngô Quyền, Hải Phòng"), "Hải Phòng")
        # không cắt nhầm khi địa danh không phải tên đường
        self.assertEqual(destination_in_text("Phố cổ Hội An, Quảng Nam"), "Hội An")
        self.assertEqual(destination_in_text("Khu phố 3, Phú Quốc, Kiên Giang"), "Phú Quốc")
        self.assertEqual(destination_in_text("Hai Bà Trưng, Hà Nội"), "Hà Nội")

    def test_lai_chau_is_not_a_destination_because_it_steals_sa_pa_landmarks(self):
        self.assertNotIn("Lai Châu", {d.name for d in DESTINATIONS})
        self.assertIsNone(destination_in_text("Tam Đường, Lai Châu, Việt Nam"))  # nhãn lấy từ kế hoạch (Sa Pa), không từ địa chỉ

    def test_thanh_pho_is_not_treated_as_a_street_word(self):
        self.assertEqual(destination_in_text("Thành phố Hải Phòng"), "Hải Phòng")
        self.assertEqual(destination_in_text("12 Lê Lợi, Thành phố Đà Nẵng"), "Đà Nẵng")
        self.assertEqual(destination_in_text("Thành phố Hồ Chí Minh, Việt Nam"), "TP. Hồ Chí Minh")
        self.assertEqual(destination_in_text("Đường Hải Phòng, Thành phố Huế"), "Huế")  # đường Hải Phòng vẫn bị bỏ qua

    def test_dien_bien_phu_street_is_not_the_province_but_the_province_still_resolves(self):
        self.assertEqual(destination_in_text("135 Dien Bien Phu, 180000 Thành phố Hải Phòng, Việt Nam"), "Hải Phòng")
        self.assertEqual(destination_in_text("88 Điện Biên Phủ, Phường 25, Bình Thạnh, Hồ Chí Minh"), "TP. Hồ Chí Minh")
        self.assertEqual(destination_in_text("Phường Him Lam, Thành phố Điện Biên Phủ, Điện Biên"), "Điện Biên")
        self.assertEqual(destination_in_text("Điện Biên"), "Điện Biên")  # tên điểm đến trong kế hoạch vẫn tự nhận ra
        from collectors.geo import destination_radius_km
        self.assertGreaterEqual(destination_radius_km("Hà Tĩnh"), 50)  # resort ven biển cách thành phố 34–45 km

    def test_new_aliases_resolve_addresses_without_hijacking_big_cities(self):
        self.assertEqual(destination_in_text("Số 1 Trần Phú, Phường 1, Cà Mau"), "Cà Mau")
        self.assertEqual(destination_in_text("Thành phố Điện Biên Phủ, Điện Biên"), "Điện Biên")
        self.assertEqual(destination_in_text("Đường Nguyễn Huệ, Quận 1, Hồ Chí Minh"), "TP. Hồ Chí Minh")
        # Mộc Châu nằm trong tỉnh Sơn La: địa danh cụ thể thắng tên tỉnh
        self.assertEqual(destination_in_text("Mộc Châu, Sơn La"), "Mộc Châu")


if __name__ == "__main__":
    unittest.main()
