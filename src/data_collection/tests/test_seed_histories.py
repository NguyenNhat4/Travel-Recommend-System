"""Hồi quy cho seed_histories.py theo MOCK_DATA_SPEC §4–§5: khách, chuyến, event, cạnh lộn xộn, profile suy từ event, persona."""
import gzip
import json
import re
import tempfile
import unittest
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from data_collection.seed import catalog_meta as cm
from data_collection.seed import config as C
from data_collection.seed import seed_histories as sh
from data_collection.seed.seed_histories import demo_password_hash

from argon2 import PasswordHasher

AS_OF = date(2026, 9, 20)
N = 600
DESTS = ["Nha Trang", "Phú Quốc", "Đà Lạt", "Hà Nội"]
ORIGINS = ["Hà Nội", "TP. Hồ Chí Minh", "Đà Nẵng"]
PERSONAS = {p[0] for p in C.PERSONAS}
TZ_VN = timezone(timedelta(hours=7))


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
            for j in range(3):   # phòng Vinpearl không mang brand riêng: phải nhận brand từ property cha
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


def ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def local_day(s: str) -> date:
    return ts(s).astimezone(TZ_VN).date()


def dump(res):
    return json.dumps({k: res[k] for k in ("profiles", "events", "users", "bookings", "booking_items")}, ensure_ascii=False, sort_keys=True)


class SeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = make_catalog()
        cls.res = sh.generate(cls.rows, AS_OF, seed=7, n_profiles=N)
        cls.by_id = {r["productId"]: r for r in cls.rows}
        cls.events = cls.res["events"]
        cls.profiles = {p["cdp_user_id"]: p for p in cls.res["profiles"]}
        cls.generic = [e for e in cls.events if e["cdp_user_id"] not in PERSONAS]
        cls.buys = [e for e in cls.events if e["event_name"] == "purchase"]
        cls.groups = defaultdict(list)
        for e in cls.buys:
            if e["event_group_id"]:
                cls.groups[e["event_group_id"]].append(e)

    def test_deterministic_and_seed_changes_result(self):
        self.assertEqual(dump(self.res), dump(sh.generate(self.rows, AS_OF, seed=7, n_profiles=N)))
        self.assertNotEqual(dump(self.res), dump(sh.generate(self.rows, AS_OF, seed=8, n_profiles=N)))

    def test_sequential_ids_and_event_limits(self):
        self.assertEqual(sorted(self.profiles), [f"VP{i:07d}" for i in range(1, N + 1)])            # VP + 7 số, từ 0000001
        per = Counter(e["cdp_user_id"] for e in self.events)
        self.assertLessEqual(max(per.values()), C.MAX_EVENTS_PER_USER)                                # kể cả persona (verify.sql)
        self.assertEqual([e["event_id"] for e in self.events], list(range(1, len(self.events) + 1)))
        stamps = [e["timestamp"] for e in self.events]
        self.assertEqual(stamps, sorted(stamps))
        self.assertTrue(all(local_day(t) < AS_OF for t in stamps))                                    # không có event ở tương lai
        self.assertTrue(all(local_day(t) >= AS_OF - timedelta(days=C.HISTORY_DAYS) for t in stamps))  # trong 24 tháng
        self.assertEqual({e["event_name"] for e in self.events}, {"purchase", "add_to_cart", "product_view", "search"})
        for e in self.events:
            if e["event_name"] == "search":
                self.assertEqual((e["product_id"], e["taxonomy"], e["event_group_id"]), (None, None, None))

    def test_only_purchases_carry_group_id(self):
        self.assertTrue(all(e["event_group_id"] is None for e in self.events if e["event_name"] != "purchase"))
        for gid in self.groups:
            self.assertRegex(gid, r"^OFF\d{8}\d{3}$")

    def test_lifecycle_is_computed_from_events(self):
        by_user = defaultdict(list)
        for e in self.events:
            by_user[e["cdp_user_id"]].append(e)
        for u, p in self.profiles.items():
            buys = [e for e in by_user.get(u, []) if e["event_name"] == "purchase"]
            if not buys:                                                                              # 0 purchase → new
                self.assertEqual((p["lifecycle_stage"], p["days_since_last_booking"], p["lifetime_order_count"]), ("new", None, 0), u)
                continue
            days = (AS_OF - local_day(max(e["timestamp"] for e in buys))).days
            self.assertEqual(p["days_since_last_booking"], days)
            self.assertEqual(p["lifecycle_stage"], "active" if days <= 180 else "dormant" if days <= 365 else "churned", u)
            self.assertEqual(p["lifetime_order_count"], len({e["event_group_id"] for e in buys if e["event_group_id"]}))  # chỉ gid khác NULL
            self.assertEqual(p["purchased_verticals"], sorted({e["taxonomy"] for e in buys}))
        stages = Counter(p["lifecycle_stage"] for p in self.profiles.values())
        for stage, target in C.STAGE_MIX.items():
            self.assertAlmostEqual(stages[stage] / N, target, delta=C.STAGE_TOLERANCE, msg=stage)

    def test_trips_have_one_destination_and_checkout_order(self):
        self.assertGreater(len(self.groups), 300)
        multi = golf = 0
        for gid, g in self.groups.items():
            known = [e for e in g if e["product_id"] in self.by_id]
            self.assertLessEqual(len({self.by_id[e["product_id"]]["destination"] for e in known}), 1, gid)  # một chuyến, một điểm đến
            g = sorted(g, key=lambda e: e["timestamp"])
            order = [sh.CHECKOUT_ORDER[e["taxonomy"]] for e in g]
            self.assertEqual(order, sorted(order), gid)                                                     # hotel → flight → vé → golf
            self.assertEqual(len({e["cdp_user_id"] for e in g}), 1)
            multi += len({e["taxonomy"] for e in g}) >= 2
            golf += any(e["taxonomy"] == "golf" for e in g)
        self.assertAlmostEqual(multi / len(self.groups), C.MULTI_VERTICAL_RATE, delta=0.08)                # 65% chuyến có ≥ 2 loại
        self.assertAlmostEqual(golf / len(self.groups), C.GOLF_TRIP_RATE, delta=0.03)                       # 3% chuyến có golf

    def test_views_precede_purchases_within_seven_days(self):
        views = defaultdict(list)
        for e in self.generic:
            if e["event_name"] == "product_view":
                views[e["cdp_user_id"]].append(ts(e["timestamp"]))
        ok = 0
        generic_groups = [g for g in self.groups.values() if g[0]["cdp_user_id"] not in PERSONAS]
        for g in generic_groups:
            first = min(ts(e["timestamp"]) for e in g)
            ok += any(timedelta(0) < first - v <= timedelta(days=C.VIEW_LEAD_DAYS[1]) for v in views[g[0]["cdp_user_id"]])
        self.assertGreater(ok / len(generic_groups), 0.95)

    def test_using_dates_follow_lead_time_and_stay_in_the_past(self):
        latest = AS_OF - timedelta(days=C.LATEST_PAST_USING_DAYS)
        for gid, g in self.groups.items():
            if g[0]["cdp_user_id"] in PERSONAS:
                continue
            for e in g:
                self.assertLessEqual(date.fromisoformat(e["using_date"]), latest, gid)
            hotel = [e for e in g if e["taxonomy"] == "hotel"]
            if hotel:
                check_in = date.fromisoformat(hotel[0]["using_date"])
                self.assertTrue(C.LEAD_DAYS[0] <= (check_in - local_day(hotel[0]["timestamp"])).days <= C.LEAD_DAYS[1], gid)
                for e in g:
                    offset = 0 if e["taxonomy"] in ("hotel", "flight") else C.TICKET_DAY_OFFSET
                    self.assertEqual(date.fromisoformat(e["using_date"]), check_in + timedelta(days=offset), gid)  # vé = nhận phòng + 1

    def test_quantities_and_noisy_prices(self):
        for e in self.buys:
            lo, hi = C.QUANTITY[e["taxonomy"]]
            self.assertTrue(lo <= e["quantity"] <= hi, e)                                                   # hotel 1, flight 1–3, vé 2–4…
            self.assertEqual(e["unit_price"] % C.PRICE_ROUNDING, 0)                                        # làm tròn nghìn
            if e["product_id"] in self.by_id:
                base = self.by_id[e["product_id"]]["unitPrice"]
                self.assertTrue(base * (1 - C.PRICE_NOISE) - C.PRICE_ROUNDING / 2 <= e["unit_price"] <= base * (1 + C.PRICE_NOISE) + C.PRICE_ROUNDING / 2)
        prices = {(e["product_id"], e["unit_price"]) for e in self.buys if e["product_id"] in self.by_id}
        self.assertGreater(len(prices), len({p for p, _ in prices}))                                       # có nhiễu, không phải giá catalog cố định

    def test_search_and_add_to_cart_rates(self):
        trips = len([g for g in self.groups.values() if g[0]["cdp_user_id"] not in PERSONAS])
        names = Counter(e["event_name"] for e in self.generic)
        self.assertAlmostEqual(names["search"] / trips, C.SEARCH_TRIP_RATE, delta=0.07)                   # 30% chuyến có search
        generic_buys = sum(1 for e in self.generic if e["event_name"] == "purchase")
        self.assertAlmostEqual(names["add_to_cart"] / generic_buys, C.ADD_TO_CART_TRIP_RATE, delta=0.07)  # 40% chuyến, mọi mục

    def test_messy_edges(self):
        missing = [e for e in self.events if e["product_id"] is not None and e["product_id"] not in self.by_id]
        self.assertTrue(all(e["event_name"] == "purchase" and e["cdp_user_id"] not in PERSONAS for e in missing))
        self.assertAlmostEqual(len(missing) / len(self.buys), C.MESSY_PURCHASE_BAD_PRODUCT, delta=0.01)   # 2% purchase
        no_group = sum(1 for e in self.buys if e["event_group_id"] is None)
        self.assertAlmostEqual(no_group / len(self.buys), C.MESSY_DROP_GROUP, delta=0.01)                  # 3% purchase mất gid
        self.assertLessEqual(no_group / len(self.buys), 0.04)                                              # cổng verify.sql
        dests = defaultdict(set)
        for e in self.generic:
            if e["event_name"] == "product_view":
                dests[(e["cdp_user_id"], local_day(e["timestamp"]))].add(self.by_id[e["product_id"]]["destination"])
        two = {u for (u, _), ds in dests.items() if len(ds) >= 2}
        self.assertGreaterEqual(len(two), round(C.MESSY_TWO_DEST_VIEW_USERS * N))                         # 1% khách xem 2 điểm đến cùng ngày

    def test_profiles_optins_homes_and_tiers(self):
        generic = [p for u, p in self.profiles.items() if u not in PERSONAS]
        for flag, key in (("email_optin", "email"), ("sms_optin", "sms"), ("push_optin", "push")):
            self.assertAlmostEqual(sum(1 for p in generic if not p[flag]) / len(generic), C.OPTOUT_RATE[key], delta=0.025, msg=flag)
        self.assertTrue(all(self.profiles[u][f] for u in PERSONAS for f in ("email_optin", "sms_optin", "push_optin")))
        homes = Counter(p["home_city"] for p in generic)
        self.assertEqual(set(homes), set(C.HOME_CITIES))                                                   # 8 thành phố, có Vinh
        self.assertAlmostEqual(homes["Hà Nội"] / len(generic), 0.35, delta=0.05)
        tiers = Counter(p["vinclub_tier"] for p in self.profiles.values())
        self.assertTrue(tiers["Member"] > tiers["Gold"] > tiers["Platinum"] >= tiers["Diamond"] > 0)
        self.assertEqual(sh.World.origin("Vinh"), "Nghệ An")                                               # sân bay Vinh = nhãn Nghệ An

    def test_persona_p1_upcoming_booking_is_consistent(self):
        p1 = [e for e in self.events if e["cdp_user_id"] == "VP0000001"]
        self.assertEqual((self.profiles["VP0000001"]["lifecycle_stage"], self.profiles["VP0000001"]["vinclub_tier"]), ("active", "Gold"))
        b, = self.res["bookings"]
        it, = self.res["booking_items"]
        buys = [e for e in p1 if e["event_group_id"] == b["event_group_id"] and e["event_name"] == "purchase"]
        self.assertEqual(len(buys), 1)                                                                    # 1:1 với event purchase
        buy = buys[0]
        self.assertEqual((buy["product_id"], buy["using_date"], buy["quantity"], buy["unit_price"]),
                         (it["product_id"], it["using_date"], it["quantity"], it["unit_price"]))
        self.assertEqual(local_day(buy["timestamp"]), AS_OF - timedelta(days=C.P1["upcoming_purchase_days_ago"]))   # mua tại as_of − 3
        self.assertEqual(it["using_date"], (AS_OF + timedelta(days=12)).isoformat())                      # nhận phòng as_of + 12
        self.assertEqual((it["quantity"], it["using_date_to"]), (1, (AS_OF + timedelta(days=13)).isoformat()))  # 1 phòng, 1 đêm
        self.assertEqual((it["booking_id"], b["total_amount"], it["line_total"]), (b["booking_id"], it["unit_price"], it["unit_price"]))
        room = self.by_id[it["product_id"]]
        self.assertEqual((room["taxonomy"], room["destination"]), ("hotel", "Nha Trang"))
        self.assertTrue(cm.is_vinpearl(room, self.by_id))                                                  # phòng Vinpearl
        self.assertTrue(cm.open_nights(cm.room_calendar(room, AS_OF, self.by_id), AS_OF, AS_OF + timedelta(days=12), 1))
        self.assertFalse(any(e["taxonomy"] == "flight" for e in p1 if e["event_name"] == "purchase"))      # chưa có vé bay
        past = defaultdict(set)
        for e in p1:
            if e["event_name"] == "purchase" and e["event_group_id"] != b["event_group_id"]:
                past[e["event_group_id"]].add(e["taxonomy"])
        self.assertEqual(list(past.values()), [{"hotel", "attraction"}] * 3)                               # 3 chuyến hotel + attraction
        self.assertTrue(all(self.by_id[e["product_id"]]["destination"] == "Nha Trang" for e in p1 if e["product_id"]))
        self.assertRegex(b["reference_code"], r"^VOTA-%s-[0-9A-F]{4}$" % (AS_OF + timedelta(days=12)).strftime("%Y%m%d"))
        self.assertLessEqual(len(p1), C.MAX_EVENTS_PER_USER)

    def test_other_personas_and_users(self):
        p2 = [e for e in self.events if e["cdp_user_id"] == "VP0000002"]
        self.assertEqual([e["event_name"] for e in p2], ["product_view", "product_view"])
        self.assertEqual([local_day(e["timestamp"]) for e in p2], [AS_OF - timedelta(days=2), AS_OF - timedelta(days=1)])
        self.assertTrue(all(self.by_id[e["product_id"]]["destination"] == "Phú Quốc" for e in p2))
        self.assertEqual(self.profiles["VP0000002"]["lifecycle_stage"], "new")
        p3 = [e for e in self.events if e["cdp_user_id"] == "VP0000003" and e["event_name"] == "purchase"]
        self.assertEqual(len({e["event_group_id"] for e in p3}), 2)
        self.assertTrue(all(self.by_id[e["product_id"]]["destination"] == "Phú Quốc" for e in p3))
        self.assertEqual((self.profiles["VP0000003"]["lifecycle_stage"], self.profiles["VP0000003"]["days_since_last_booking"]), ("dormant", 190))
        self.assertEqual([e for e in self.events if e["cdp_user_id"] == "VP0000004"], [])
        self.assertEqual(self.profiles["VP0000004"]["lifecycle_stage"], "new")
        users = self.res["users"]
        self.assertEqual(len(users), len(C.PERSONAS) + C.TEST_USERS)
        self.assertEqual([u["persona"] for u in users[:4]], ["P1_frequent", "P2_first_time", "P3_dormant", "P4_no_history"])
        self.assertEqual((users[4]["email"], users[4]["cdp_user_id"], users[-1]["email"]), ("test01@vota.demo", "VP0000005", "test50@vota.demo"))
        self.assertTrue(all(u["password_hash"].startswith("$argon2id$v=19$m=19456,t=2,p=1$") for u in users))
        self.assertEqual(len({u["password_hash"] for u in users}), len(users))   # salt riêng từng user
        self.assertTrue(PasswordHasher().verify(users[0]["password_hash"], C.DEMO_PASSWORD))
        self.assertEqual(users[0]["password_hash"], demo_password_hash(users[0]["user_id"]))   # tái lập được
        self.assertTrue(all(u["cdp_user_id"] in self.profiles for u in users))
        self.assertEqual(len({u["email"] for u in users}), len(users))

    def test_popularity_is_heavy_tailed_and_only_bookable_products_are_bought(self):
        buys = [e for e in self.buys if e["product_id"] in self.by_id]
        for e in buys:
            self.assertIsNotNone(self.by_id[e["product_id"]]["unitPrice"])                                # chỉ mua sản phẩm có giá
            self.assertNotIn(self.by_id[e["product_id"]]["attributes"].get("level"), ("property", "route"))  # không mua cha
        counts = sorted(Counter(e["product_id"] for e in buys).values(), reverse=True)
        self.assertGreater(sum(counts[:max(1, len(counts) // 10)]) / len(buys), 0.25)                      # top 10% sản phẩm chiếm phần lớn

    def test_cap_never_drops_purchases(self):
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        evs = [{"event_name": n, "timestamp": t0 + timedelta(minutes=i)} for i, n in
               enumerate(["search"] * 3 + ["product_view"] * 6 + ["add_to_cart"] * 4 + ["purchase"] * 5)]
        kept = sh.cap_events(list(evs), 15)
        self.assertEqual(Counter(e["event_name"] for e in kept), Counter({"purchase": 5, "product_view": 6, "add_to_cart": 4}))
        kept = sh.cap_events(list(evs), 4)
        self.assertEqual(Counter(e["event_name"] for e in kept), Counter({"purchase": 5}))

    def test_report_and_cli(self):
        text, m = sh.report(self.res, AS_OF, {"seed": 7, "max_events": 15})
        self.assertIn(f"Profile: **{N}**", text)
        self.assertIn("mỗi chuyến đúng một điểm đến: đạt", text)
        self.assertTrue(0 < m["recall"] <= 1)
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


@unittest.skipUnless(C.DEFAULT_PRODUCTS_SNAPSHOT.exists(), "không có snapshot catalog")
class RealCatalogSmoke(unittest.TestCase):
    """Chạy trên snapshot thật (đọc gzip trong bộ nhớ) — các cổng của db/verify.sql và DoD #5 phải đạt ngay ở bước sinh."""

    @classmethod
    def setUpClass(cls):
        with gzip.open(C.DEFAULT_PRODUCTS_SNAPSHOT, "rt", encoding="utf-8") as f:
            cls.rows = [json.loads(line) for line in f if line.strip()]
        cls.res = sh.generate(cls.rows, AS_OF)

    def test_real_catalog_meets_the_verify_gates(self):
        res = self.res
        self.assertEqual(len(res["profiles"]), C.DEFAULT_USERS)
        self.assertTrue(6000 <= len(res["events"]) <= 8000, len(res["events"]))                         # verify: events 6000–8000
        self.assertLessEqual(max(Counter(e["cdp_user_id"] for e in res["events"]).values()), C.MAX_EVENTS_PER_USER)
        stages = Counter(p["lifecycle_stage"] for p in res["profiles"])
        for stage in ("active", "dormant"):                                                               # verify: 45±5, 20±5 trên cả 2.000
            self.assertAlmostEqual(stages[stage] / C.DEFAULT_USERS, C.STAGE_MIX[stage], delta=0.05, msg=stage)
        buys = [e for e in res["events"] if e["event_name"] == "purchase"]
        self.assertLessEqual(sum(1 for e in buys if e["event_group_id"] is None) / len(buys), 0.04)
        self.assertEqual(len(res["users"]), len(C.PERSONAS) + C.TEST_USERS)

    def test_p1_room_is_an_open_vinpearl_room(self):
        by_id = {r["productId"]: r for r in self.rows}
        it, = self.res["booking_items"]
        room = by_id[it["product_id"]]
        self.assertTrue(cm.is_vinpearl(room, by_id))
        self.assertEqual(room["destination"], "Nha Trang")
        self.assertTrue(cm.open_nights(cm.room_calendar(room, AS_OF, by_id), AS_OF, date.fromisoformat(it["using_date"]), 1))

    def test_baseline_recall_is_beatable_but_not_trivial(self):
        hits, totals = sh.recall_at_k(self.res)
        recall = sum(hits.values()) / sum(totals.values())
        self.assertTrue(0.05 < recall <= C.RECALL_CEILING, recall)                                       # DoD #5 (seed demo)


if __name__ == "__main__":
    unittest.main()
