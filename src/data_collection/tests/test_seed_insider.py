"""Kiểm thử seed_insider.py theo MOCK_DATA_SPEC §6 bằng dữ liệu CDP tổng hợp (offline, không cần DB)."""
import json
import random
import re
import unittest
from datetime import date, datetime, timedelta, timezone

from data_collection.seed import config as C
from data_collection.seed import seed_insider as si

AS_OF = date(2026, 9, 20)
NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)
N = 500


def fake_inputs(n: int, seed: int = 1):
    rng = random.Random(seed)
    profiles, events, users = [], [], []
    eid = 0
    for i in range(1, n + 1):
        uid = f"VP{i:07d}"
        created = datetime(2024, 3, 1, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 900), seconds=rng.randint(0, 86000))
        allowed = rng.random()
        profiles.append({
            "cdp_user_id": uid, "lifecycle_stage": rng.choice(["new", "active", "dormant", "churned"]), "days_since_last_booking": None if i % 5 == 0 else i,
            "lifetime_order_count": i % 4, "vinclub_tier": "Member", "purchased_verticals": ["hotel"], "home_city": "Hà Nội", "last_destination": None if i % 3 == 0 else "Nha Trang",
            "email_optin": allowed < 0.9, "sms_optin": rng.random() < 0.5, "push_optin": rng.random() < 0.6,   # ~2% không kênh nào
            "created_at": si.fmt(created), "updated_at": si.fmt(created + timedelta(days=5))})
        if i <= 3:
            users.append({"cdp_user_id": uid, "email": f"persona{i}@example.com"})
        for _ in range(rng.randint(0, 6)):
            eid += 1
            name = rng.choice(["purchase", "product_view", "add_to_cart", "search"])
            t = NOW - timedelta(days=rng.uniform(0, 720), seconds=rng.randint(0, 80000))
            events.append({"event_id": eid, "cdp_user_id": uid, "event_name": name, "timestamp": si.fmt(t),
                           "product_id": None if name == "search" else "11111111-1111-1111-1111-111111111111",
                           "taxonomy": None if name == "search" else "hotel", "event_group_id": f"OFF{eid}" if name == "purchase" else None,
                           "quantity": 1 if name in ("purchase", "add_to_cart") else None, "unit_price": None, "using_date": None})
    events.append({"event_id": eid + 1, "cdp_user_id": "VP9999999", "event_name": "product_view", "timestamp": si.fmt(NOW - timedelta(days=1)),
                   "product_id": None, "taxonomy": None, "event_group_id": None, "quantity": None, "unit_price": None, "using_date": None})   # mồ côi: bị bỏ
    return profiles, events, users


class SeedInsiderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles, cls.events, cls.users = fake_inputs(N)
        cls.res = si.generate(cls.profiles, cls.events, AS_OF, seed=7, events_per_profile=10)
        cls.s = si.summary(cls.res, cls.profiles, AS_OF)
        cls.pid = {p["cdp_user_id"]: si.uid("profile", p["cdp_user_id"]) for p in cls.profiles}

    def test_one_insider_profile_per_cdp_profile(self):
        ids = [p["profile_id"] for p in self.res["insider_profiles"]]
        self.assertEqual(len(ids), len(self.profiles))
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual({p["partner_name"] for p in self.res["insider_profiles"]}, {"vota"})
        self.assertEqual(self.res["partners"][0]["request_token"], C.INSIDER_TOKEN_DEFAULT)
        self.assertLess(self.res["partners"][0]["created_at"], min(p["created_at"] for p in self.res["insider_profiles"]))  # partner có trước mọi profile
        self.assertTrue(all(r["partner_name"] == r["partner_name"].lower() for r in self.res["partners"]))

    def test_attributes_are_the_spec_subset_and_keep_nulls(self):
        attrs = [p["attributes"] for p in self.res["insider_profiles"]]
        self.assertTrue(all(set(a) == set(C.INSIDER_ATTRIBUTE_KEYS) for a in attrs))   # {vinclub_tier, home_city, last_destination, lifecycle_stage}
        self.assertTrue(any(a["last_destination"] is None for a in attrs))              # spec: null vẫn lưu

    def test_identifiers_three_current_rows_and_one_percent_history(self):
        cur = [i for i in self.res["identifiers"] if i["valid_to"] is None]
        per_profile = {}
        for i in cur:
            per_profile.setdefault(i["profile_id"], []).append(i["id_type"])
        self.assertTrue(all(sorted(v) == ["cdp_user_id", "email", "phone"] for v in per_profile.values()))
        self.assertEqual(len(per_profile), len(self.profiles))
        self.assertEqual((self.s["viol_dup_current_value"], self.s["viol_dup_current_type"], self.s["viol_identifier_range"]), (0, 0, 0))
        emails = {i["profile_id"]: i["id_value"] for i in cur if i["id_type"] == "email"}
        self.assertTrue(all(emails[self.pid[p["cdp_user_id"]]] == f"{p['cdp_user_id'].lower()}@example.com" for p in self.profiles))
        self.assertTrue(all(re.fullmatch(r"09\d{8}", i["id_value"]) for i in cur if i["id_type"] == "phone"))
        closed = [i for i in self.res["identifiers"] if i["valid_to"]]
        self.assertEqual(len(closed), round(C.EMAIL_HISTORY_RATE * N))                  # 1% profile có email cũ
        closed_at = si.fmt(NOW - timedelta(days=C.EMAIL_HISTORY_CLOSED_DAYS_AGO))
        for i in closed:
            self.assertEqual((i["id_type"], i["valid_to"]), ("email", closed_at))       # valid_to = as_of − 30
            self.assertLess(i["valid_from"], i["valid_to"])
            current = next(c for c in cur if c["profile_id"] == i["profile_id"] and c["id_type"] == "email")
            self.assertEqual(current["valid_from"], closed_at)                          # email mới mở đúng lúc email cũ đóng

    def test_events_follow_ttl_90_730(self):
        want = 0
        for e in self.events:
            if e["cdp_user_id"] == "VP9999999":
                continue
            ttl = C.TTL_PURCHASE_DAYS if e["event_name"] == "purchase" else C.TTL_OTHER_DAYS
            want += si.parse_ts(e["timestamp"]) + timedelta(days=ttl) > NOW
        self.assertEqual(len(self.res["insider_events"]), want)
        self.assertEqual(self.s["viol_events_expired"], 0)
        self.assertTrue(any(e["event_name"] == "purchase" for e in self.res["insider_events"]))
        self.assertTrue(any(e["event_name"] == "search" and e["event_params"] == {} for e in self.res["insider_events"]))
        self.assertTrue(all(e["received_at"] >= e["event_time"] for e in self.res["insider_events"]))

    def test_gdpr_rule(self):
        prof = {p["profile_id"]: p for p in self.res["insider_profiles"]}
        all_off = {self.pid[p["cdp_user_id"]] for p in self.profiles if not (p["email_optin"] or p["sms_optin"] or p["push_optin"])}
        self.assertGreater(len(all_off), 0)
        off = {k for k, p in prof.items() if not p["gdpr_optin"]}
        self.assertTrue(all_off <= off)                                                  # tắt cả 3 kênh → gdpr false
        self.assertAlmostEqual(len(off - all_off) / N, C.GDPR_RANDOM_OFF_RATE, delta=0.025)   # cộng 2% ngẫu nhiên
        earliest = si.fmt(NOW - timedelta(days=C.GDPR_OPTOUT_DAYS_AGO[1]))
        for k in off:                                                                    # opt-out = as_of − 0…180 ngày (hoặc ngay sau khi tạo)
            p = prof[k]
            self.assertTrue(p["created_at"] < p["updated_at"] <= si.fmt(NOW))
            self.assertTrue(p["updated_at"] >= earliest or p["updated_at"] <= si.fmt(si.parse_ts(p["created_at"]) + timedelta(days=1)))

    def test_channel_rules_hold(self):
        for k in ("viol_after_optout", "viol_channel_not_optin", "viol_before_created", "viol_after_unsub"):
            self.assertEqual(self.s[k], 0, k)
        self.assertGreater(self.s["gdpr_off"], 0)
        self.assertGreater(self.s["channel_by_type"].get("unsubscribe", 0), 0)
        ids = {r["campaign_id"] for r in self.res["channel_events"]}
        self.assertTrue(all(re.fullmatch(r"CMP-\d{6}-\d{2}", c) for c in ids))           # CMP-yyyymm-NN
        self.assertEqual(len({c for c, _, _ in si.campaigns(NOW)}), C.CAMPAIGN_COUNT)

    def test_no_rows_after_unsubscribe_on_any_channel(self):
        unsub = {}
        for r in self.res["channel_events"]:
            if r["event_type"] == "unsubscribe":
                unsub.setdefault(r["profile_id"], r["event_time"])
        self.assertGreater(len(unsub), 0)
        for r in self.res["channel_events"]:
            if r["profile_id"] in unsub:
                self.assertLessEqual(r["event_time"], unsub[r["profile_id"]])

    def test_funnel_rates_and_volume(self):
        s = self.s
        self.assertAlmostEqual(s["delivered_rate"], 0.97, delta=0.025)
        self.assertAlmostEqual(s["bounce_rate"], 0.02, delta=0.015)
        self.assertAlmostEqual(s["open_rate"], 0.35, delta=0.05)
        self.assertAlmostEqual(s["click_rate"], 0.08, delta=0.03)
        self.assertLess(s["unsub_rate"], 0.03)
        self.assertTrue(6.5 <= s["per_profile"] <= 11.5, s["per_profile"])
        first_open = {}                                                                  # mỗi click có open trước đó cùng message
        for r in self.res["channel_events"]:
            if r["event_type"] == "open":
                first_open.setdefault(r["metadata"]["messageId"], r["event_time"])
        for r in self.res["channel_events"]:
            if r["event_type"] == "click":
                self.assertLessEqual(first_open[r["metadata"]["messageId"]], r["event_time"])

    def test_deterministic_and_seed_sensitive(self):
        again = si.generate(self.profiles, self.events, AS_OF, seed=7, events_per_profile=10)
        self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(self.res, sort_keys=True))
        other = si.generate(self.profiles, self.events, AS_OF, seed=8, events_per_profile=10)
        self.assertNotEqual(json.dumps(other["channel_events"], sort_keys=True), json.dumps(self.res["channel_events"], sort_keys=True))

    def test_profile_without_any_optin_gets_no_channel_events(self):
        profiles = [dict(p, email_optin=False, sms_optin=False, push_optin=False) for p in self.profiles[:50]]
        res = si.generate(profiles, [], AS_OF, seed=3)
        self.assertEqual(res["channel_events"], [])
        self.assertEqual(len(res["insider_profiles"]), 50)
        self.assertTrue(all(not p["gdpr_optin"] for p in res["insider_profiles"]))


if __name__ == "__main__":
    unittest.main()
