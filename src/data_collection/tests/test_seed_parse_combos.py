"""Hồi quy cho parse_combos.py: tách thành phần, nhận loại, map sang sản phẩm, priceBasis / nights / minPax."""
import json
import tempfile
import unittest
from pathlib import Path

from data_collection.seed import parse_combos as pc


def product(pid, name, taxonomy="attraction", destination="Nha Trang", level=None, venue=None, price=100000, parent=None,
            description="", ref=None, **attrs):
    a = {"venue": venue, "parentProductId": parent, "level": level, **attrs}
    return {"productId": pid, "name": name, "taxonomy": taxonomy, "destination": destination, "description": description,
            "attributes": {k: v for k, v in a.items() if v is not None}, "unitPrice": price, "currency": "VND", "available": True,
            "availableFrom": None, "availableTo": None, "imageUrl": None, "sourceRef": ref or f"vinpearl:{taxonomy}:{pid}"}


def catalog():
    return [
        product("t-std", "[VinWonders Nha Trang] - Vé vào cửa tiêu chuẩn", venue="VinWonders Nha Trang", price=1050000),
        product("t-bare", "VinWonders Nha Trang", venue="VinWonders Nha Trang", price=1050000),
        product("t-fast", "[VinWonders Nha Trang] - Fastpass Cáp Treo (01 chiều)", venue="VinWonders Nha Trang", price=150000),
        product("t-safari", "Vinpearl Safari Phú Quốc", destination="Phú Quốc", venue="Vinpearl Safari Phú Quốc", price=650000),
        product("h1", "Vinpearl Resort Nha Trang", taxonomy="hotel", level="property", price=2500000, ref="vinpearl:hotel:h1"),
        product("r1", "Vinpearl Resort Nha Trang - Deluxe Giường Đôi", taxonomy="hotel", level="room", parent="h1", price=3400000,
                roomName="Deluxe Giường Đôi", ref="vinpearl:hotel:h1:room:r1"),
        product("r2", "Vinpearl Resort Nha Trang - Suite", taxonomy="hotel", level="room", parent="h1", price=6000000,
                roomName="Suite", ref="vinpearl:hotel:h1:room:r2"),
    ]


class ParseComboTests(unittest.TestCase):
    def setUp(self):
        self.cat = pc.Catalog(catalog())

    def parse(self, name, description="", venue="VinWonders Nha Trang", destination="Nha Trang", **attrs):
        combo = product("c1", name, taxonomy="combo", destination=destination, venue=venue, description=description, **attrs)
        return combo, pc.parse_combo(combo, self.cat)

    def test_pg_trgm_similarity_matches_postgres_definition(self):
        self.assertEqual(pc.similarity("word", "word"), 1.0)
        self.assertEqual(pc.similarity("", "abc"), 0.0)
        # pg_trgm: similarity('word', 'two words') = 0.36363636
        self.assertAlmostEqual(pc.similarity("word", "two words"), 0.3636363636, places=6)
        self.assertGreater(pc.similarity("Thuỷ cung", "thuy cung"), 0.99)  # bỏ dấu trước khi so

    def test_kind_keywords_follow_spec_table_and_cable_car_is_ambiguous(self):
        self.assertEqual(pc.classify("Buffet sáng")[0], "meal")
        self.assertEqual(pc.classify("Xe đưa đón sân bay")[0], "transfer")
        self.assertEqual(pc.classify("Vé VinWonders")[0], "attraction")
        self.assertEqual(pc.classify("Voucher Ẩm thực")[0], "meal")
        self.assertEqual(pc.classify("Voucher Quà lưu niệm")[0], "other")
        self.assertEqual(pc.classify("Vé máy bay khứ hồi")[0], "flight")
        self.assertEqual(pc.classify("Green fee 18 hố")[0], "golf")
        self.assertEqual(pc.classify("Cáp treo"), ("attraction", True))
        self.assertEqual(pc.classify("Cáp treo đưa đón lên đảo"), ("transfer", True))
        self.assertEqual(pc.classify("Spa thư giãn")[0], "other")

    def test_name_is_split_and_promo_wrappers_are_dropped(self):
        _, items = self.parse("[VinWonders Nha Trang] - Combo Vé VinWonders + Dịch vụ Buffet Cao Cấp | TẶNG Fastpass Cáp Treo")
        self.assertEqual([i["item_kind"] for i in items], ["attraction", "meal", "other"])
        self.assertEqual([i["position"] for i in items], [1, 2, 3])
        self.assertTrue(all(i["source"] == "description_parse" and i["is_optional"] is False for i in items))
        _, items = self.parse("[VinWonders Vũ Yên] - Combo 03 khu: Vườn Thú + Khu Trò Chơi + Công Viên Nước", venue="VinWonders Vũ Yên")
        self.assertEqual([i["label"] for i in items], ["Vườn Thú", "Khu Trò Chơi", "Công Viên Nước"])  # "Combo 03 khu" chỉ là bao bì
        _, items = self.parse("[Times City] Combo vé vào cửa 2 khu: Thuỷ Cung & VinKE", venue="VinKE & Aquarium")
        self.assertEqual([i["label"] for i in items], ["Thuỷ Cung", "VinKE"])  # "vé vào cửa 2 khu" chỉ đếm số khu, không phải một vé

    def test_time_of_day_colon_does_not_split(self):
        _, items = self.parse("Combo Vé VinWonders sau 14:00 & Xe Buggy")
        self.assertIn("Vé VinWonders sau 14:00", [i["label"] for i in items])

    def test_quantity_and_unit(self):
        _, items = self.parse("Combo chèo thuyền Gondola (2 chiều) & Xông hơi Jjimjilbang tiêu chuẩn")
        self.assertEqual((items[0]["quantity"], items[0]["unit"]), (2.0, "vé"))
        _, items = self.parse("[Jumbo 10] - Combo 10 buổi Jjimjilbang tiêu chuẩn + TẶNG 02 buổi")
        self.assertEqual([(i["quantity"], i["unit"]) for i in items], [(10.0, "suất"), (2.0, "suất")])
        self.assertTrue(all(i["unit"] in pc.DDL_UNITS for i in items))

    def test_attraction_mapping_confidence_tiers(self):
        combo = product("c1", "x", taxonomy="combo", venue="Vinpearl Safari Phú Quốc", destination="Phú Quốc")
        pid, conf, _ = self.cat.map_attraction("Vinpearl Safari Phú Quốc", combo, "attraction", False)
        self.assertEqual((pid, conf), ("t-safari", 0.95))  # khớp đúng tên + đúng điểm đến
        combo = product("c2", "x", taxonomy="combo", venue="VinWonders Nha Trang", destination="Nha Trang")
        pid, conf, note = self.cat.map_attraction("Vé VinWonders", combo, "attraction", False)
        self.assertEqual((pid, conf), ("t-bare", 0.6))  # chỉ khớp địa điểm: chọn đúng vé chuẩn, không chọn fastpass
        self.assertIn("địa điểm", note)
        pid, conf, _ = self.cat.map_attraction("Cáp treo", combo, "attraction", True)
        self.assertEqual(conf, 0.6)  # mơ hồ không bao giờ vượt 0.6
        combo = product("c3", "x", taxonomy="combo", venue="Hội An", destination="Đà Lạt")
        self.assertEqual(self.cat.map_attraction("Vé VinWonders", combo, "attraction", False)[:2], (None, None))  # khác điểm đến: không map

    def test_spec_example_hotel_combo_maps_room_with_confidence_085(self):
        """Ví dụ trong spec: Combo 3N2Đ Vinpearl Resort Nha Trang + vé VinWonders, buffet sáng, xe đưa đón sân bay."""
        combo, items = self.parse("Combo 3N2Đ Vinpearl Resort Nha Trang + vé VinWonders, buffet sáng, xe đưa đón sân bay")
        kinds = [(i["item_kind"], i["item_product_id"], i["confidence"]) for i in items]
        self.assertEqual([k[0] for k in kinds], ["hotel", "attraction", "meal", "transfer"])
        self.assertEqual(kinds[0][1:], ("r1", 0.85))  # khớp resort, hạng phòng suy ra (rẻ nhất) → 0.85
        self.assertEqual(kinds[1][1], "t-bare")
        self.assertEqual([k[1] for k in kinds[2:]], [None, None])  # meal / transfer không có sản phẩm tương ứng
        attrs, evidence = pc.combo_attributes(combo | {"description": "3N2Đ, giá 3.000.000đ/khách, tối thiểu 2 khách"})
        self.assertEqual(attrs["nights"], 2)
        self.assertEqual(attrs["minPax"], 2)
        self.assertEqual(attrs["priceBasis"], "per_person")

    def test_every_combo_gets_at_least_one_item(self):
        _, items = self.parse("Combo ưu đãi đặc biệt")
        self.assertGreaterEqual(len(items), 1)
        _, items = self.parse("[Tag] Combo")
        self.assertEqual(len(items), 1)
        self.assertIsNone(items[0]["item_product_id"])

    def test_description_bullets_add_only_new_components_and_skip_policy_lines(self):
        desc = ("Mô tả chung\n\nBao gồm\n- Vé vào cửa VinWonders\n- Buffet trưa tại nhà hàng Biển\n"
                "- Vé không được hoàn, hủy hoặc quy đổi thành dịch vụ khác\n- Quý khách hàng cao dưới 100 cm được miễn phí\n"
                "- Phụ thu 30.000đ/vé")
        _, items = self.parse("Combo Vé VinWonders", description=desc)
        labels = [i["label"] for i in items]
        self.assertEqual(labels, ["Vé VinWonders", "Buffet trưa tại nhà hàng Biển"])  # vé trùng tên bị bỏ; điều khoản bị bỏ
        self.assertTrue(items[1]["evidence"].startswith("mô tả"))

    def test_price_basis_defaults_to_package_and_switches_on_evidence(self):
        base = product("c1", "Combo A", taxonomy="combo", description="Giá trọn gói cho nhóm", adultOriginalPrice=1.0, childPrice=0.0)
        self.assertEqual(pc.combo_attributes(base)[0], {"priceBasis": "per_package"})
        for text in ("Giá 500.000đ/khách", "giá 1.200.000/người", "Giá cho 1 người", "mỗi khách một vé", "Vé sử dụng trong ngày dành cho 01 người"):
            attrs, ev = pc.combo_attributes(base | {"description": text})
            self.assertEqual(attrs["priceBasis"], "per_person", text)
            self.assertIn("priceBasis", ev)
        gift = base | {"description": "Tặng 01 ảnh lưu niệm/ khách hàng"}  # quà tặng theo khách, không phải cơ sở tính giá
        self.assertEqual(pc.combo_attributes(gift)[0]["priceBasis"], "per_package")
        by_attr = product("c2", "Combo B", taxonomy="combo", adultOriginalPrice=1500000.0, childPrice=1000000.0)
        attrs, ev = pc.combo_attributes(by_attr)
        self.assertEqual(attrs["priceBasis"], "per_person")
        self.assertIn("childPrice", ev["priceBasis"])
        self.assertNotIn("nights", attrs)
        self.assertNotIn("minPax", attrs)

    def test_cli_writes_files_keeps_catalog_untouched_and_respects_manual_rows(self):
        rows = catalog() + [product("c1", "[VinWonders Nha Trang] - Combo Vé VinWonders + Buffet", taxonomy="combo", venue="VinWonders Nha Trang",
                                    description="Vé cho 1 người")]
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            catalog_path = d / "products.jsonl"
            catalog_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
            before = catalog_path.read_bytes()
            self.assertEqual(pc.main(["--data-dir", str(d)]), 0)
            self.assertEqual(catalog_path.read_bytes(), before)  # không sửa products.jsonl
            items = [json.loads(l) for l in (d / "combo_items.jsonl").read_text(encoding="utf-8").split("\n") if l.strip()]
            self.assertEqual({i["combo_product_id"] for i in items}, {"c1"})
            self.assertEqual(list(items[0]), pc.FIELDS)
            review = (d / "combo_items_review.csv").read_text(encoding="utf-8-sig")
            self.assertIn("Vé VinWonders", review)  # vé map 0.6 → vào hàng đợi soát tay
            self.assertNotIn(",meal,", review)  # meal không cần map nên không vào hàng đợi
            attrs = json.loads((d / "combo_attributes.json").read_text(encoding="utf-8"))
            self.assertEqual(attrs["c1"]["attributes"]["priceBasis"], "per_person")
            # sửa tay: dòng manual thay dòng parse và tồn tại qua lần chạy lại
            manual = {**items[0], "item_product_id": "t-std", "confidence": 1.0, "source": "manual"}
            (d / "combo_items_manual.jsonl").write_text(json.dumps(manual, ensure_ascii=False) + "\n", encoding="utf-8")
            pc.main(["--data-dir", str(d)])
            again = [json.loads(l) for l in (d / "combo_items.jsonl").read_text(encoding="utf-8").split("\n") if l.strip()]
            self.assertEqual(again[0]["item_product_id"], "t-std")
            self.assertEqual(again[0]["source"], "manual")
            self.assertNotIn("Vé VinWonders", (d / "combo_items_review.csv").read_text(encoding="utf-8-sig"))
            self.assertTrue(all(i["unit"] in pc.DDL_UNITS for i in again))

    def test_manual_unit_is_normalized_without_losing_mapping(self):
        item = {"combo_product_id": "c1", "position": 1, "label": "03 Games", "item_kind": "attraction",
                "item_product_id": "t-std", "quantity": 3.0, "unit": "trò", "is_optional": False,
                "source": "manual", "confidence": 1.0, "evidence": "đã duyệt tay"}
        got = pc.normalize_unit(item)
        self.assertEqual((got["unit"], got["item_product_id"], got["source"]), ("vé", "t-std", "manual"))
        self.assertIn("unit chuẩn hóa", got["evidence"])


if __name__ == "__main__":
    unittest.main()
