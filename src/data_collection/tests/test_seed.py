"""Kiểm tra hồi quy offline cho `data_collection.seed` — không cần Postgres.

Chỉ chạm các hàm `build_*` thuần; phần `write_*` cần database nên để cho `db/verify*.sql`
(chạy trong lần seed thật) đảm nhiệm. Mỗi test kiểm **một bất biến đã có chỗ dựa trong spec
hoặc trong DDL**, và tên test nói rõ bất biến đó là gì.

Chạy từ `src/data_collection`:
    python -m unittest discover -s tests -t . -v
"""

from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

# Cho phép `import seed...` khi chạy với cwd = src/data_collection (quy ước của workstream này),
# đồng thời vẫn chạy được khi package được import là data_collection.seed.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from data_collection.seed import config, gen_products, load_products, parse_combos, seed_histories
from data_collection.seed.common import make_rng, stable_order_key, strip_accents, zipf_weights

AS_OF = dt.date(2026, 9, 20)
SEED = 42


class CatalogGenerationTests(unittest.TestCase):
    """`gen_products` phải ra đúng contract SCHEMA.md và đúng số lượng §1b."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = gen_products.build_catalog(SEED, AS_OF)
        cls.by_variant: dict[str, list[dict]] = {}
        for record in cls.catalog:
            level = record["attributes"].get("level")
            key = f"{record['taxonomy']}/{level}" if level else record["taxonomy"]
            cls.by_variant.setdefault(key, []).append(record)

    def test_every_record_has_exactly_the_thirteen_cdp_fields(self):
        expected = {
            "productId", "name", "taxonomy", "destination", "description", "attributes",
            "unitPrice", "currency", "available", "availableFrom", "availableTo",
            "imageUrl", "sourceRef",
        }
        for record in self.catalog:
            self.assertEqual(set(record), expected, record["sourceRef"])

    def test_same_seed_and_as_of_produce_byte_identical_catalog(self):
        self.assertEqual(self.catalog, gen_products.build_catalog(SEED, AS_OF))

    def test_different_seed_produces_different_catalog(self):
        self.assertNotEqual(self.catalog, gen_products.build_catalog(SEED + 1, AS_OF))

    def test_product_id_is_uuid5_of_source_ref_so_reruns_keep_foreign_keys(self):
        import uuid

        for record in self.catalog:
            expected = str(uuid.uuid5(uuid.NAMESPACE_URL, record["sourceRef"]))
            self.assertEqual(record["productId"], expected, record["sourceRef"])

    def test_source_ref_is_unique_because_the_column_has_a_unique_constraint(self):
        refs = [r["sourceRef"] for r in self.catalog]
        self.assertEqual(len(refs), len(set(refs)))

    def test_counts_match_spec_section_1b(self):
        self.assertEqual(len(self.by_variant["attraction"]), config.N_ATTRACTIONS)
        self.assertEqual(len(self.by_variant["golf"]), config.N_GOLF)
        self.assertEqual(len(self.by_variant["combo"]), config.N_COMBOS)
        self.assertEqual(len(self.by_variant["flight/route"]), config.N_FLIGHT_ROUTES)
        # 40 property + các bản gần trùng cố ý thêm vào.
        self.assertEqual(
            len(self.by_variant["hotel/property"]),
            config.N_HOTEL_PROPERTIES + config.CATALOG_NEAR_DUPLICATE_PAIRS,
        )
        rooms = len(self.by_variant["hotel/room"])
        self.assertGreaterEqual(rooms, config.N_HOTEL_PROPERTIES * config.ROOMS_PER_PROPERTY[0])
        self.assertLessEqual(rooms, config.N_HOTEL_PROPERTIES * config.ROOMS_PER_PROPERTY[1])

    def test_every_child_points_at_a_parent_that_exists(self):
        ids = {r["productId"] for r in self.catalog}
        children = [r for r in self.catalog if r["attributes"].get("parentProductId")]
        self.assertTrue(children)
        for child in children:
            self.assertIn(child["attributes"]["parentProductId"], ids, child["sourceRef"])

    def test_exactly_one_route_has_no_flights_so_the_open_question_has_an_example(self):
        routes = {r["productId"] for r in self.by_variant["flight/route"]}
        parents = {r["attributes"]["parentProductId"] for r in self.by_variant["flight/flight"]}
        self.assertEqual(len(routes - parents), config.CATALOG_EMPTY_ROUTES)

    def test_unticketed_attractions_have_no_price_and_match_the_configured_rate(self):
        attractions = self.by_variant["attraction"]
        unticketed = [a for a in attractions if a["attributes"].get("ticketed") is False]
        for record in unticketed:
            self.assertIsNone(record["unitPrice"], record["sourceRef"])
        rate = len(unticketed) / len(attractions)
        self.assertAlmostEqual(rate, config.ATTRACTION_UNTICKETED_RATE, delta=0.08)

    def test_only_unticketed_attractions_have_a_null_price(self):
        for record in self.catalog:
            if record["unitPrice"] is None:
                self.assertIs(record["attributes"].get("ticketed"), False, record["sourceRef"])

    def test_flight_destinations_are_travel_labels_that_have_hotels(self):
        """Nếu vé bay mang destination không có khách sạn, quy tắc 'mỗi chuyến một destination'
        sẽ ghép vé bay về Hà Nội vào chuyến đi Nha Trang."""
        hotel_destinations = {r["destination"] for r in self.by_variant["hotel/property"]}
        for record in self.by_variant["flight/flight"] + self.by_variant["flight/route"]:
            self.assertIn(record["destination"], hotel_destinations, record["sourceRef"])

    def test_anchor_destinations_have_a_vinpearl_property_with_rooms_for_the_personas(self):
        parents_with_rooms = {r["attributes"]["parentProductId"] for r in self.by_variant["hotel/room"]}
        for destination in config.ANCHOR_DESTINATIONS:
            matching = [
                p for p in self.by_variant["hotel/property"]
                if p["destination"] == destination
                and p["attributes"].get("brand") == "Vinpearl"
                and p["productId"] in parents_with_rooms
            ]
            self.assertTrue(matching, f"{destination} không có property Vinpearl có phòng")

    def test_combo_descriptions_name_real_products_in_the_same_destination(self):
        """parse_combos chỉ map được nếu description dùng đúng tên sản phẩm — bịa tên là hỏng bước sau."""
        rooms_by_destination: dict[str, set[str]] = {}
        for room in self.by_variant["hotel/room"]:
            rooms_by_destination.setdefault(room["destination"], set()).add(room["attributes"]["roomName"])
        for combo in self.by_variant["combo"]:
            names = rooms_by_destination.get(combo["destination"], set())
            self.assertTrue(
                any(name in combo["description"] for name in names),
                f"{combo['sourceRef']} không nhắc hạng phòng nào của {combo['destination']}",
            )

    def test_validate_rejects_attributes_that_would_break_the_product_meta_view(self):
        """Các cast trong view không có phòng vệ: một starRating kiểu chuỗi làm hỏng mọi truy vấn."""
        broken = [dict(self.catalog[0])]
        broken[0]["attributes"] = dict(broken[0]["attributes"], starRating="năm sao")
        with self.assertRaises(ValueError):
            gen_products._validate(broken)

    def test_validate_rejects_an_orphan_parent_reference(self):
        broken = [dict(self.catalog[0])]
        broken[0]["attributes"] = dict(
            broken[0]["attributes"], parentProductId="00000000-0000-0000-0000-000000000000"
        )
        with self.assertRaises(ValueError):
            gen_products._validate(broken)


class BookingWindowTests(unittest.TestCase):
    """Cửa sổ đặt chỗ 30 ngày — DATABASE_SCHEMA §1 mục 13."""

    def _record(self, **overrides):
        record = {
            "productId": "11111111-1111-5111-8111-111111111111",
            "taxonomy": "attraction",
            "attributes": {},
            "available": True,
            "availableFrom": None,
            "availableTo": None,
        }
        record.update(overrides)
        return record

    def test_missing_source_dates_take_the_whole_window(self):
        available, start, finish, _ = load_products.clip_window(self._record(), AS_OF)
        self.assertTrue(available)
        self.assertEqual(start, AS_OF)
        self.assertEqual(finish, AS_OF + dt.timedelta(days=config.WINDOW_DAYS - 1))

    def test_source_range_is_clipped_to_the_window_on_both_ends(self):
        record = self._record(availableFrom="2025-01-01", availableTo="2027-12-31")
        _, start, finish, extra = load_products.clip_window(record, AS_OF)
        self.assertEqual(start, AS_OF)
        self.assertEqual(finish, AS_OF + dt.timedelta(days=config.WINDOW_DAYS - 1))
        # Giá trị gốc phải giữ lại để lần nạp sau cuộn đúng cửa sổ.
        self.assertEqual(extra["sourceAvailableFrom"], "2025-01-01")
        self.assertEqual(extra["sourceAvailableTo"], "2027-12-31")

    def test_a_product_that_expired_before_the_window_becomes_unavailable(self):
        record = self._record(availableFrom="2020-01-01", availableTo="2020-02-01")
        available, start, finish, _ = load_products.clip_window(record, AS_OF)
        self.assertFalse(available)
        self.assertIsNone(start)
        self.assertIsNone(finish)

    def test_a_flight_collapses_to_a_single_day(self):
        record = self._record(
            taxonomy="flight", attributes={"level": "flight"},
            availableFrom="2026-09-25", availableTo="2026-10-22",
        )
        _, start, finish, _ = load_products.clip_window(record, AS_OF)
        self.assertEqual(start, finish)
        self.assertEqual(start, dt.date(2026, 9, 25))

    def test_a_flight_outside_the_window_is_moved_into_it_not_dropped(self):
        record = self._record(
            taxonomy="flight", attributes={"level": "flight"},
            availableFrom="2027-05-01", availableTo="2027-05-01",
        )
        _, start, finish, _ = load_products.clip_window(record, AS_OF)
        self.assertEqual(start, finish)
        self.assertGreaterEqual(start, AS_OF)
        self.assertLessEqual(start, AS_OF + dt.timedelta(days=config.WINDOW_DAYS - 1))

    def test_flight_placement_is_stable_across_processes(self):
        """Dùng crc32 chứ không phải hash(): hash() bị ngẫu nhiên hoá giữa các tiến trình."""
        self.assertEqual(stable_order_key("abc"), stable_order_key("abc"))
        self.assertNotEqual(stable_order_key("abc"), stable_order_key("abd"))


class AvailabilityCalendarTests(unittest.TestCase):
    """`attributes.availability` — verify.sql đòi đúng 30 ký tự cho MỌI level=room."""

    def _room(self, brand=None):
        attributes = {"level": "room"}
        if brand:
            attributes["brand"] = brand
        return {"taxonomy": "hotel", "attributes": attributes}

    def test_every_room_calendar_is_exactly_thirty_characters_of_ones_and_zeros(self):
        rng = make_rng(SEED, "calendar")
        for _ in range(50):
            calendar = load_products.build_calendar(rng, self._room(), AS_OF)
            self.assertEqual(len(calendar["calendar"]), config.WINDOW_DAYS)
            self.assertEqual(calendar["days"], config.WINDOW_DAYS)
            self.assertEqual(calendar["from"], AS_OF.isoformat())
            self.assertTrue(set(calendar["calendar"]) <= {"0", "1"})

    def test_room_occupancy_lands_in_the_configured_band(self):
        rng = make_rng(SEED, "calendar")
        rates = []
        for _ in range(60):
            calendar = load_products.build_calendar(rng, self._room(), AS_OF)["calendar"]
            rates.append(calendar.count("0") / len(calendar))
        mean = sum(rates) / len(rates)
        low, high = config.ROOM_OCCUPANCY_RANGE
        self.assertGreaterEqual(mean, low - 0.1)
        self.assertLessEqual(mean, high + 0.1)

    def test_products_without_a_calendar_key_are_the_ones_verify_expects(self):
        rng = make_rng(SEED, "calendar")
        for taxonomy, level in (("flight", "flight"), ("flight", "route"),
                                ("hotel", "property"), ("combo", None)):
            attributes = {"level": level} if level else {}
            record = {"taxonomy": taxonomy, "attributes": attributes}
            self.assertIsNone(load_products.build_calendar(rng, record, AS_OF), (taxonomy, level))

    def test_attractions_and_golf_get_a_calendar(self):
        rng = make_rng(SEED, "calendar")
        for taxonomy in ("attraction", "golf"):
            calendar = load_products.build_calendar(rng, {"taxonomy": taxonomy, "attributes": {}}, AS_OF)
            self.assertIsNotNone(calendar)
            self.assertEqual(len(calendar["calendar"]), config.WINDOW_DAYS)


class ComboAttributeTests(unittest.TestCase):
    """Regex cấp combo — MOCK_DATA_SPEC §2.3."""

    def test_compact_night_pattern(self):
        self.assertEqual(load_products.parse_combo_attributes("Combo 3N2Đ Nha Trang", "")["nights"], 2)
        self.assertEqual(load_products.parse_combo_attributes("Combo 4N3D Phú Quốc", "")["nights"], 3)

    def test_verbose_night_pattern(self):
        attributes = load_products.parse_combo_attributes("Combo nghỉ dưỡng", "Gói 3 ngày 2 đêm tại resort.")
        self.assertEqual(attributes["nights"], 2)

    def test_min_pax(self):
        attributes = load_products.parse_combo_attributes("Combo", "Áp dụng cho 4 khách.")
        self.assertEqual(attributes["minPax"], 4)

    def test_price_basis_defaults_to_per_package(self):
        self.assertEqual(load_products.parse_combo_attributes("Combo", "Gói nghỉ dưỡng.")["priceBasis"],
                         "per_package")

    def test_price_basis_switches_to_per_person_only_when_the_text_says_so(self):
        for text in ("Giá cho 1 khách.", "2.000.000đ/khách", "Giá mỗi khách", "price per person"):
            self.assertEqual(
                load_products.parse_combo_attributes("Combo", text)["priceBasis"], "per_person", text
            )


class ComboParserTests(unittest.TestCase):
    """Tách hạng mục và nhận loại — DATABASE_SCHEMA §9."""

    def test_splitting_drops_the_combo_title_and_keeps_the_items(self):
        items = parse_combos.split_items(
            "Combo 3N2Đ Nha Trang",
            "Combo 3N2Đ Nha Trang bao gồm: 2 đêm phòng Deluxe Ocean View + vé VinWonders Nha Trang + buffet sáng.",
        )
        self.assertEqual(len(items), 3)
        self.assertIn("2 đêm phòng Deluxe Ocean View", items[0])

    def test_keyword_classification_covers_every_kind(self):
        cases = {
            "2 đêm phòng Deluxe Ocean View": "hotel",
            "vé VinWonders Nha Trang": "attraction",
            "1 lượt chơi Vinpearl Golf": "golf",
            "vé máy bay khứ hồi": "flight",
            "buffet sáng": "meal",
            "xe đưa đón sân bay": "transfer",
            "voucher spa": "other",
        }
        for label, expected in cases.items():
            self.assertEqual(parse_combos.classify(label)[0], expected, label)

    def test_unknown_labels_fall_back_to_other_and_keep_the_label(self):
        kind, unit, _ = parse_combos.classify("một thứ gì đó rất lạ")
        self.assertEqual(kind, "other")
        self.assertEqual(unit, "suất")

    def test_cable_car_with_a_ticket_hint_is_an_attraction(self):
        kind, _, note = parse_combos.classify("vé cáp treo VinWonders")
        self.assertEqual(kind, "attraction")
        self.assertIsNone(note)

    def test_cable_car_with_a_transfer_hint_is_a_transfer(self):
        kind, _, note = parse_combos.classify("cáp treo đưa đón ra đảo")
        self.assertEqual(kind, "transfer")
        self.assertIsNone(note)

    def test_ambiguous_cable_car_records_both_readings_in_evidence(self):
        kind, _, note = parse_combos.classify("cáp treo")
        self.assertIsNotNone(note)
        self.assertIn("attraction", note)
        self.assertIn("transfer", note)

    def test_quantity_and_unit_are_read_from_the_label(self):
        self.assertEqual(parse_combos.extract_quantity("2 đêm phòng Deluxe", "đêm"), (2.0, "đêm"))
        self.assertEqual(parse_combos.extract_quantity("3 vé VinWonders", "vé"), (3.0, "vé"))
        self.assertEqual(parse_combos.extract_quantity("buffet sáng", "suất"), (1.0, "suất"))

    def test_unit_aliases_map_onto_the_five_values_the_check_constraint_allows(self):
        valid = {"đêm", "vé", "khách", "suất", "lượt"}
        self.assertEqual(parse_combos.extract_quantity("cho 2 người", "suất")[1], "khách")
        for label in ("2 ngày tham quan", "3 người lớn", "1 lượt golf"):
            self.assertIn(parse_combos.extract_quantity(label, "suất")[1], valid, label)

    def test_every_combo_yields_at_least_one_item_even_with_an_empty_description(self):
        """verify.sql 'every combo has items' không cho phép combo rỗng."""
        items = parse_combos.build_items({"name": "Combo lạ", "description": ""})
        self.assertGreaterEqual(len(items), 1)
        self.assertEqual(items[0]["item_kind"], "other")

    def test_kinds_without_a_matching_taxonomy_can_never_carry_a_product_id(self):
        """FK (item_product_id, item_kind) → products (product_id, taxonomy):
        không có sản phẩm nào có taxonomy 'meal'/'transfer'/'other'."""
        taxonomies = {"hotel", "flight", "attraction", "combo", "golf"}
        for kind in config.COMBO_KINDS_WITHOUT_PRODUCT:
            self.assertNotIn(kind, taxonomies)


class HistoryTests(unittest.TestCase):
    """Sinh chuyến và event — MOCK_DATA_SPEC §4 và các cổng của verify.sql."""

    @classmethod
    def setUpClass(cls):
        catalog = gen_products.build_catalog(SEED, AS_OF)
        # Dựng pool y như load_pool() nhưng từ catalog trong bộ nhớ: is_bookable = level ∉
        # {property, route} và ticketed ≠ false và unitPrice IS NOT NULL (PRODUCT_SCHEMA §4).
        rows = []
        for record in catalog:
            attributes = record["attributes"]
            level = attributes.get("level", "")
            bookable = (
                level not in ("property", "route")
                and attributes.get("ticketed", True)
                and record["unitPrice"] is not None
            )
            if not bookable or not record["available"]:
                continue
            available_from = (
                dt.date.fromisoformat(record["availableFrom"]) if record["availableFrom"] else AS_OF
            )
            available_to = (
                dt.date.fromisoformat(record["availableTo"])
                if record["availableTo"]
                else AS_OF + dt.timedelta(days=config.WINDOW_DAYS - 1)
            )
            rows.append(
                (record["productId"], record["taxonomy"], record["destination"], record["unitPrice"],
                 attributes.get("brand"), record["name"], level, available_from, available_to)
            )
        cls.pool = seed_histories.ProductPool(rows)
        cls.profiles, cls.events = seed_histories.build_histories(
            seed=SEED, as_of=AS_OF, pool=cls.pool, n_users=400, reserved={}
        )

    def test_user_ids_follow_the_vp_plus_seven_digits_format(self):
        self.assertEqual(seed_histories.user_id(1), "VP0000001")
        self.assertEqual(seed_histories.user_id(2000), "VP0002000")

    def test_lifecycle_stage_is_derived_from_the_last_purchase_not_assigned(self):
        self.assertEqual(seed_histories.derive_stage(None), "new")
        self.assertEqual(seed_histories.derive_stage(0), "active")
        self.assertEqual(seed_histories.derive_stage(config.STAGE_ACTIVE_MAX_DAYS), "active")
        self.assertEqual(seed_histories.derive_stage(config.STAGE_ACTIVE_MAX_DAYS + 1), "dormant")
        self.assertEqual(seed_histories.derive_stage(config.STAGE_DORMANT_MAX_DAYS), "dormant")
        self.assertEqual(seed_histories.derive_stage(config.STAGE_DORMANT_MAX_DAYS + 1), "churned")

    def test_no_user_exceeds_the_event_ceiling_verify_checks(self):
        counts: dict[str, int] = {}
        for event in self.events:
            counts[event["cdp_user_id"]] = counts.get(event["cdp_user_id"], 0) + 1
        self.assertLessEqual(max(counts.values()), config.MAX_EVENTS_PER_USER)

    def test_event_volume_scales_into_the_range_verify_requires(self):
        """verify.sql: events BETWEEN 6000 AND 8000 với 2.000 khách."""
        per_user = len(self.events) / 400
        projected = per_user * config.N_USERS
        low, high = config.TARGET_EVENT_RANGE
        self.assertGreater(projected, low * 0.8)
        self.assertLess(projected, high * 1.2)

    def test_each_trip_stays_within_one_destination(self):
        destination_by_product = {
            row[seed_histories.ProductPool.ID]: row[seed_histories.ProductPool.DESTINATION]
            for row in self.pool.rows
        }
        by_group: dict[str, set[str]] = {}
        for event in self.events:
            group = event["event_group_id"]
            destination = destination_by_product.get(event["product_id"])
            if group and destination:
                by_group.setdefault(group, set()).add(destination)
        bad = [g for g, destinations in by_group.items() if len(destinations) > 1]
        self.assertLessEqual(len(bad) / max(len(by_group), 1), 0.01)

    def test_future_purchases_fall_inside_the_products_own_booking_window(self):
        """verify.sql 'future purchases inside window'. Chuyến bay là ca chặt nhất: from = to."""
        window = {
            row[seed_histories.ProductPool.ID]: (
                row[seed_histories.ProductPool.FROM], row[seed_histories.ProductPool.TO]
            )
            for row in self.pool.rows
        }
        for event in self.events:
            if event["event_name"] != "purchase" or not event["using_date"]:
                continue
            if event["using_date"] <= AS_OF:
                continue  # event lịch sử không bị ràng buộc này
            bounds = window.get(event["product_id"])
            if bounds is None:
                continue
            start, finish = bounds
            self.assertGreaterEqual(event["using_date"], start)
            self.assertLessEqual(event["using_date"], finish)

    def test_a_purchase_always_carries_quantity_price_and_using_date(self):
        for event in self.events:
            if event["event_name"] == "purchase":
                self.assertIsNotNone(event["quantity"], event)
                self.assertGreater(event["quantity"], 0)
                self.assertIsNotNone(event["using_date"], event)

    def test_search_events_have_no_product_and_others_always_do(self):
        """CHECK events_product_required: event_name = 'search' OR product_id IS NOT NULL."""
        for event in self.events:
            if event["event_name"] == "search":
                self.assertIsNone(event["product_id"])
            else:
                self.assertIsNotNone(event["product_id"], event)

    def test_events_within_a_trip_are_ordered_view_then_cart_then_purchase(self):
        rank = {"search": 0, "product_view": 1, "add_to_cart": 2, "purchase": 3}
        by_group: dict[str, list[dict]] = {}
        for event in self.events:
            if event["event_group_id"]:
                by_group.setdefault(event["event_group_id"], []).append(event)
        for group, events in list(by_group.items())[:200]:
            purchases = [e for e in events if e["event_name"] == "purchase"]
            views = [e for e in events if e["event_name"] == "product_view"]
            if purchases and views:
                self.assertLessEqual(min(v["timestamp"] for v in views),
                                     max(p["timestamp"] for p in purchases), group)

    def test_popularity_follows_a_power_law_rather_than_being_uniform(self):
        """Dữ liệu ngẫu nhiên đều làm recommender hỏng trông vẫn ổn (handbook §6)."""
        counts: dict[str, int] = {}
        for event in self.events:
            if event["event_name"] == "purchase" and event["product_id"]:
                counts[event["product_id"]] = counts.get(event["product_id"], 0) + 1
        self.assertGreater(len(counts), 20)
        ranked = sorted(counts.values(), reverse=True)
        top_decile = sum(ranked[: max(len(ranked) // 10, 1)])
        self.assertGreater(top_decile / sum(ranked), 0.2)

    def test_zipf_weights_are_normalised_and_decreasing(self):
        weights = zipf_weights(10)
        self.assertAlmostEqual(float(weights.sum()), 1.0)
        for earlier, later in zip(weights, weights[1:]):
            self.assertGreater(earlier, later)

    def test_messy_edges_are_deterministic_and_skip_the_personas(self):
        events = [
            {"cdp_user_id": "VP0000001", "event_name": "purchase",
             "product_id": "keep-me", "event_group_id": "OFF1"},
            {"cdp_user_id": "VP0000999", "event_name": "purchase",
             "product_id": "may-break", "event_group_id": "OFF2"},
        ]
        other = [dict(e) for e in events]
        seed_histories.apply_messy_edges(make_rng(SEED, "messy_edges"), events, {"VP0000001"})
        seed_histories.apply_messy_edges(make_rng(SEED, "messy_edges"), other, {"VP0000001"})
        self.assertEqual(events, other)  # tất định
        self.assertEqual(events[0]["product_id"], "keep-me")  # persona không bị đụng
        self.assertEqual(events[0]["event_group_id"], "OFF1")


class TextHelperTests(unittest.TestCase):
    def test_vietnamese_accents_including_d_with_stroke_are_removed(self):
        self.assertEqual(strip_accents("Đà Nẵng"), "Da Nang")
        self.assertEqual(strip_accents("đêm"), "dem")
        self.assertEqual(strip_accents("Phú Quốc"), "Phu Quoc")


class BcryptSaltTests(unittest.TestCase):
    """Salt phải hợp lệ VÀ tất định — ghép chuỗi tuỳ ý vào gensalt() cho 'Invalid salt'."""

    def test_salt_encoding_is_twenty_two_characters_from_the_bcrypt_alphabet(self):
        from data_collection.seed.seed_app import _BCRYPT_ALPHABET, _bcrypt_b64

        encoded = _bcrypt_b64(bytes(range(16)))
        self.assertEqual(len(encoded), 22)
        self.assertTrue(set(encoded) <= set(_BCRYPT_ALPHABET))

    def test_hash_is_deterministic_and_verifies(self):
        try:
            import bcrypt
        except ImportError:  # pragma: no cover - chỉ khi chưa cài seed/requirements.txt
            self.skipTest("chưa cài bcrypt")
        from data_collection.seed.seed_app import hash_password

        first = hash_password(config.DEMO_PASSWORD, make_rng(SEED, "seed_app"))
        second = hash_password(config.DEMO_PASSWORD, make_rng(SEED, "seed_app"))
        self.assertEqual(first, second)
        self.assertTrue(bcrypt.checkpw(config.DEMO_PASSWORD.encode(), first.encode()))
        self.assertFalse(bcrypt.checkpw(b"sai-mat-khau", first.encode()))


class InsiderTests(unittest.TestCase):
    """§6 — TTL, opt-out và phễu kênh."""

    def test_no_channel_event_lands_after_the_opt_out_moment(self):
        """verify_insider.sql so với insider_profiles.updated_at, chính xác đến giây."""
        from data_collection.seed.common import at_time
        from data_collection.seed.seed_insider import build_channel_events

        rng = make_rng(SEED, "insider")
        opt_out_at = at_time(AS_OF - dt.timedelta(days=30), 12)
        for _ in range(60):
            rows = build_channel_events(
                rng, profile_id="p", as_of=AS_OF, opt_out_at=opt_out_at
            )
            for row in rows:
                self.assertLessEqual(row[4], opt_out_at)

    def test_nothing_follows_an_unsubscribe(self):
        from data_collection.seed.seed_insider import build_channel_events

        rng = make_rng(SEED, "insider")
        for _ in range(80):
            rows = build_channel_events(rng, profile_id="p", as_of=AS_OF, opt_out_at=None)
            types = [r[2] for r in rows]
            if "unsubscribe" in types:
                self.assertEqual(types.index("unsubscribe"), len(types) - 1)

    def test_channel_and_event_type_stay_inside_the_check_constraints(self):
        from data_collection.seed.seed_insider import build_channel_events

        rng = make_rng(SEED, "insider")
        channels = {"email", "push", "sms"}
        types = {"sent", "delivered", "open", "click", "bounce", "unsubscribe"}
        for _ in range(40):
            for row in build_channel_events(rng, profile_id="p", as_of=AS_OF, opt_out_at=None):
                self.assertIn(row[1], channels)
                self.assertIn(row[2], types)

    def test_profile_id_is_derived_from_the_cdp_user_id_so_reruns_are_stable(self):
        from data_collection.seed.seed_insider import profile_id_for

        self.assertEqual(profile_id_for("VP0000001"), profile_id_for("VP0000001"))
        self.assertNotEqual(profile_id_for("VP0000001"), profile_id_for("VP0000002"))


if __name__ == "__main__":
    unittest.main()
