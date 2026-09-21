"""Hồi quy cho seed_histories.py: quy tắc của file thiết kế DB (persona, chuyến đi, vòng đời tính từ event, cạnh lộn xộn)."""
import json
import re
import tempfile
import unittest
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from data_collection.seed import catalog_meta as cm
from data_collection.seed import seed_histories as sh

AS_OF = date(2026, 9, 20)
DESTS = ["Nha Trang", "Phú Quốc", "Đà Lạt", "Hà Nội"]
ORIGINS = ["Hà Nội", "TP. Hồ Chí Minh", "Đà Nẵng"]


def make_catalog():
    rows = []

    def add(pid, name, taxonomy, level=None, parent=None, price=1_000_000, dest="Nha Trang", ref=None, **attrs):
        a = {"level": level, "parentProductId": parent, **attrs}
        rows.append({"productId": pid, "name": name, "taxonomy": taxonomy, "destination": dest, "description": "mô tả", "unitPrice": price,
                     "currency": "VND", "available": price is not None, "availableFrom": None, "availableTo": None, "imageUrl": None,
                     "sourceRef": ref or f"booking:{pid}", "attributes": {k: v for k, v in a.items() if v is not None}})

    for d in DESTS:
        for i in range(12):
            h = f"h-{d}-{i}"
            add(h, f"Khách sạn {d} {i}", "hotel", "property", dest=d, price=500000, ref=f"vinpearl:hotel:{h}" if i < 2 else None)
            for j in range(3):
                add(f"r-{d}-{i}-{j}", f"Khách sạn {d} {i} - Phòng {j}", "hotel", "room", parent=h, price=800000 + 100000 * j, dest=d)
        for i in range(8):
            add(f"a-{d}-{i}", f"Điểm {d} {i}", "attraction", dest=d, price=200000 + 10000 * i)
        for i in range(4):
            add(f"c-{d}-{i}", f"Combo {d} {i}", "combo", dest=d, price=500000)
        if d in ("Nha Trang", "Phú Quốc"):
            add(f"g-{d}", f"Golf {d}", "golf", dest=d, price=1700000)
        for o in ORIGINS:
            if o != d:
                add(f"rt-{o}-{d}", f"Vé máy bay {o} - {d}", "flight", "route", dest=d, price=900000, originDestination=o)
                for k in range(2):
                    add(f"f-{o}-{d}-{k}", f"VN{k}: {o} - {d}", "flight", "flight", parent=f"rt-{o}-{d}", dest=d, price=900000 + k)
    return rows


def dump(res):
    return json.dumps({k: res[k] for k in ("profiles", "events", "users", "bookings", "booking_items")}, ensure_ascii=False, sort_keys=True)


class SeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = make_catalog()
        cls.res = sh.generate(cls.rows, AS_OF, seed=7, n_profiles=600)
        cls.by_id = {r["productId"]: r for r in cls.rows}
        cls.events = cls.res["events"]
        cls.profiles = {p["cdp_user_id"]: p for p in cls.res["profiles"]}

    def test_deterministic_and_seed_changes_result(self):
        again = sh.generate(self.rows, AS_OF, seed=7, n_profiles=600)
        self.assertEqual(dump(self.res), dump(again))
        self.assertNotEqual(dump(self.res), dump(sh.generate(self.rows, AS_OF, seed=8, n_profiles=600)))

    def test_profiles_ids_and_event_limits(self):
        self.assertEqual(len(self.profiles), 600)
        self.assertTrue(all(re.fullmatch(r"VP\d{7}", u) for u in self.profiles))
        per = Counter(e["cdp_user_id"] for e in self.events)
        persona = {p[0] for p in sh.PERSONAS}
        self.assertLessEqual(max(c for u, c in per.items() if u not in persona), 15)          # không ai quá 15 event
        self.assertEqual([e["event_id"] for e in self.events], list(range(1, len(self.events) + 1)))
        stamps = [e["timestamp"] for e in self.events]
        self.assertEqual(stamps, sorted(stamps))
        self.assertTrue(all(datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").date() <= AS_OF for t in stamps))  # không có event ở tương lai
        self.assertTrue(all(e["event_name"] in ("purchase", "add_to_cart", "product_view") for e in self.events))

    def test_lifecycle_is_computed_from_events(self):
        by_user = defaultdict(list)
        for e in self.events:
            by_user[e["cdp_user_id"]].append(e)
        for u, p in self.profiles.items():
            evs = by_user.get(u, [])
            buys = [e for e in evs if e["event_name"] == "purchase"]
            if len(evs) <= 2 or not buys:
                self.assertEqual(p["lifecycle_stage"], "new", u)
                continue
            days = (AS_OF - datetime.strptime(max(e["timestamp"] for e in buys), "%Y-%m-%dT%H:%M:%SZ").date()).days
            self.assertEqual(p["days_since_last_booking"], days)
            self.assertEqual(p["lifecycle_stage"], "active" if days <= 180 else "dormant" if days <= 365 else "churned", u)
            groups = {e["event_group_id"] or f"solo-{e['event_id']}" for e in buys}
            self.assertEqual(p["lifetime_order_count"], len(groups))
            self.assertEqual(p["purchased_verticals"], sorted({e["taxonomy"] for e in buys}))
        stages = Counter(p["lifecycle_stage"] for p in self.profiles.values())
        for stage, target in (("new", 0.25), ("active", 0.45), ("dormant", 0.20), ("churned", 0.10)):
            self.assertAlmostEqual(stages[stage] / 600, target, delta=0.05, msg=stage)

    def test_trips_have_one_destination_ordered_verticals_and_views_before_purchase(self):
        groups = defaultdict(list)
        for e in self.events:
            if e["event_name"] == "purchase" and e["event_group_id"] and e["product_id"] in self.by_id:
                groups[e["event_group_id"]].append(e)
        self.assertGreater(len(groups), 300)
        order = {"hotel": 0, "flight": 1, "attraction": 2, "combo": 2, "golf": 2}
        multi = 0
        for gid, g in groups.items():
            self.assertRegex(gid, r"^OFF\d{8}\d{3}$")
            self.assertEqual(len({self.by_id[e["product_id"]]["destination"] for e in g}), 1, gid)     # một chuyến, một điểm đến
            g.sort(key=lambda e: e["timestamp"])
            self.assertEqual([order[e["taxonomy"]] for e in g], sorted(order[e["taxonomy"]] for e in g), gid)  # hotel → flight → vé
            multi += len({e["taxonomy"] for e in g}) >= 2
            self.assertEqual(len({e["cdp_user_id"] for e in g}), 1)
            self.assertTrue(all(e["using_date"] for e in g))
        self.assertAlmostEqual(multi / len(groups), 0.65, delta=0.08)                                  # 65% chuyến có ≥ 2 loại
        views = defaultdict(list)
        for e in self.events:
            if e["event_name"] == "product_view":
                views[e["cdp_user_id"]].append(e["timestamp"])
        first_buy = {}
        for e in self.events:
            if e["event_name"] == "purchase":
                first_buy.setdefault(e["cdp_user_id"], e["timestamp"])
        # mỗi khách đã đặt chỗ có ít nhất một lần xem đứng trước lần đặt đầu tiên (product_view đi trước purchase)
        with_view_before = sum(1 for u, t in first_buy.items() if any(v <= t for v in views[u]))
        self.assertGreater(with_view_before / len(first_buy), 0.9)

    def test_messy_edges_and_tiers(self):
        n = len(self.events)
        self.assertAlmostEqual(sum(1 for p in self.profiles.values() if not p["email_optin"]) / 600, 0.05, delta=0.02)
        missing = sum(1 for e in self.events if e["product_id"] not in self.by_id)
        self.assertAlmostEqual(missing / n, 0.02, delta=0.01)                                            # event trỏ sản phẩm không tồn tại
        purchases = [e for e in self.events if e["event_name"] == "purchase"]
        no_group = sum(1 for e in purchases if e["event_group_id"] is None)
        self.assertAlmostEqual(no_group / len(purchases), 0.03, delta=0.01)                               # purchase thiếu group <= 4%
        self.assertLessEqual(no_group / len(purchases), 0.04)
        tiers = Counter(p["vinclub_tier"] for p in self.profiles.values())
        self.assertTrue(tiers["Member"] > tiers["Gold"] > tiers["Platinum"] >= tiers["Diamond"] > 0)
        self.assertLessEqual(len({p["home_city"] for p in self.profiles.values()}), 8)

    def test_persona_p1_upcoming_booking_is_consistent(self):
        p1 = [e for e in self.events if e["cdp_user_id"] == "VP0000001"]
        self.assertEqual(self.profiles["VP0000001"]["lifecycle_stage"], "active")
        self.assertEqual(self.profiles["VP0000001"]["vinclub_tier"], "Gold")
        b, = self.res["bookings"]
        it, = self.res["booking_items"]
        buys = [e for e in p1 if e["event_group_id"] == b["event_group_id"] and e["event_name"] == "purchase"]
        self.assertEqual(len(buys), 1)                                                                   # 1:1 với event purchase
        self.assertEqual((buys[0]["product_id"], buys[0]["using_date"], buys[0]["quantity"]), (it["product_id"], it["using_date"], it["quantity"]))
        self.assertEqual(it["booking_id"], b["booking_id"])
        self.assertEqual(it["line_total"], it["unit_price"] * it["quantity"])
        self.assertEqual(b["total_amount"], it["line_total"])
        room = self.by_id[it["product_id"]]
        self.assertEqual((room["taxonomy"], room["destination"], it["taxonomy"]), ("hotel", "Nha Trang", "hotel"))
        start = date.fromisoformat(it["using_date"])
        self.assertTrue(AS_OF < start <= AS_OF + timedelta(days=20))
        self.assertEqual(it["using_date_to"], (start + timedelta(days=it["quantity"])).isoformat())
        self.assertTrue(cm.open_nights(cm.room_calendar(room, AS_OF), AS_OF, start, it["quantity"]))     # các đêm trong cửa sổ và còn trống
        self.assertFalse(any(e["taxonomy"] == "flight" and e["event_group_id"] == b["event_group_id"] for e in p1))  # chưa có vé bay
        past_trips = {e["event_group_id"] for e in p1 if e["event_name"] == "purchase"} - {b["event_group_id"]}
        self.assertEqual(len(past_trips), 3)                                                              # 3 chuyến trước đó
        self.assertTrue(all(self.by_id[e["product_id"]]["destination"] == "Nha Trang" for e in p1 if e["event_name"] == "purchase"))
        self.assertRegex(b["reference_code"], r"^VOTA-\d{8}-[0-9A-F]{4}$")
        self.assertEqual(len(self.res["bookings"]), 1)                                                    # chỉ persona có chuyến sắp tới có đơn

    def test_other_personas_and_users(self):
        p2 = [e for e in self.events if e["cdp_user_id"] == "VP0000002"]
        self.assertEqual([e["event_name"] for e in p2], ["product_view", "product_view"])
        self.assertTrue(all((AS_OF - datetime.strptime(e["timestamp"], "%Y-%m-%dT%H:%M:%SZ").date()).days <= 7 for e in p2))
        self.assertEqual(self.profiles["VP0000002"]["lifecycle_stage"], "new")
        p3 = [e for e in self.events if e["cdp_user_id"] == "VP0000003" and e["event_name"] == "purchase"]
        self.assertEqual(len({e["event_group_id"] for e in p3}), 2)
        self.assertTrue(all(self.by_id[e["product_id"]]["destination"] == "Phú Quốc" for e in p3))
        self.assertEqual(self.profiles["VP0000003"]["lifecycle_stage"], "dormant")
        self.assertGreaterEqual(self.profiles["VP0000003"]["days_since_last_booking"], 181)
        self.assertEqual([e for e in self.events if e["cdp_user_id"] == "VP0000004"], [])
        self.assertEqual(self.profiles["VP0000004"]["lifecycle_stage"], "new")
        users = self.res["users"]
        self.assertEqual(len(users), 54)
        self.assertEqual([u["persona"] for u in users[:4]], ["P1_frequent", "P2_first_time", "P3_dormant", "P4_no_history"])
        self.assertTrue(all(u["password_hash"].startswith("$2b$10$") for u in users))
        self.assertTrue(all(u["email"].endswith(("@example.com", "@vota.demo")) for u in users))
        self.assertTrue(all(u["cdp_user_id"] in self.profiles for u in users))
        self.assertEqual(len({u["email"] for u in users}), 54)

    def test_popularity_is_heavy_tailed_and_only_bookable_products_are_bought(self):
        buys = [e for e in self.events if e["event_name"] == "purchase" and e["product_id"] in self.by_id]
        for e in buys:
            self.assertIsNotNone(self.by_id[e["product_id"]]["unitPrice"])                                # chỉ mua sản phẩm có giá
            self.assertNotEqual(self.by_id[e["product_id"]]["attributes"].get("level"), "property")      # không mua cha
            self.assertNotEqual(self.by_id[e["product_id"]]["attributes"].get("level"), "route")
        counts = sorted(Counter(e["product_id"] for e in buys).values(), reverse=True)
        top = sum(counts[:max(1, len(counts) // 10)]) / len(buys)
        self.assertGreater(top, 0.25)                                                                     # top 10% sản phẩm chiếm phần lớn

    def test_report_and_cli(self):
        text, m = sh.report(self.res, AS_OF, {"seed": 7, "max_events": 15})
        self.assertIn("Profile: **600**", text)
        self.assertIn("mỗi chuyến đúng một điểm đến: đạt", text)
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "products.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in self.rows) + "\n", encoding="utf-8")
            before = (d / "products.jsonl").read_bytes()
            self.assertEqual(sh.main(["--data-dir", str(d), "--as-of", "2026-09-20", "--seed", "7", "--profiles", "300"]), 0)
            self.assertEqual((d / "products.jsonl").read_bytes(), before)
            for name in ("cdp_profiles", "cdp_events", "app_users", "app_bookings", "app_booking_items"):
                self.assertTrue((d / "seed" / f"{name}.jsonl").exists(), name)
            self.assertEqual(len((d / "seed" / "cdp_profiles.jsonl").read_text(encoding="utf-8").strip().split("\n")), 300)
            self.assertTrue((d / "seed" / "seed_report.md").exists())


class RealCatalogSmoke(unittest.TestCase):
    @unittest.skipUnless(Path("data/products.jsonl").exists(), "không có catalog thật")
    def test_real_catalog_meets_the_schema_doc_targets(self):
        with open("data/products.jsonl", encoding="utf-8") as f:
            rows = [json.loads(l) for l in f if l.strip()]
        res = sh.generate(rows, AS_OF)
        n = len(res["events"])
        self.assertTrue(6000 <= n <= 8500, n)                                                             # ~7.000 event
        stages = Counter(p["lifecycle_stage"] for p in res["profiles"])
        for stage, target in (("new", 0.25), ("active", 0.45), ("dormant", 0.20), ("churned", 0.10)):
            self.assertAlmostEqual(stages[stage] / 2000, target, delta=0.03, msg=stage)
        self.assertEqual(len(res["profiles"]), 2000)
        self.assertEqual(len(res["users"]), 54)


if __name__ == "__main__":
    unittest.main()
