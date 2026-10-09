"""Profile `eval-v2` của seed_histories (05/10/2026): bộ dữ liệu đánh giá RecSys riêng — khách quay lại, bỏ giỏ, nhiều event hơn.
Seed demo (profile None) không đổi; hằng của config được khôi phục sau khi sinh."""
import unittest
from collections import defaultdict
from datetime import timedelta

from data_collection.seed import config as C, seed_histories as sh
from data_collection.tests.test_seed_histories import AS_OF, dump, make_catalog, ts

N = 600


def buyers_and_returning(res):
    trips = defaultdict(set)
    for e in res["events"]:
        if e["event_name"] == "purchase" and e["event_group_id"] and e["cdp_user_id"] not in sh.PERSONA_IDS:
            trips[e["cdp_user_id"]].add(e["event_group_id"])
    return len(trips), sum(1 for t in trips.values() if len(t) >= 2)


def abandoned_carts(res):
    """add_to_cart không có purchase cùng khách + sản phẩm trong 121 phút sau đó."""
    bought = defaultdict(list)
    for e in res["events"]:
        if e["event_name"] == "purchase":
            bought[(e["cdp_user_id"], e["product_id"])].append(ts(e["timestamp"]))
    window = timedelta(minutes=C.CART_BEFORE_PURCHASE_MIN[1] + 1)
    return [e for e in res["events"] if e["event_name"] == "add_to_cart" and not any(
        ts(e["timestamp"]) <= t <= ts(e["timestamp"]) + window for t in bought.get((e["cdp_user_id"], e["product_id"]), ()))]


class EvalProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = make_catalog()
        cls.demo = sh.generate(cls.rows, AS_OF, seed=7, n_profiles=N)
        cls.eval = sh.generate(cls.rows, AS_OF, seed=7, n_profiles=N, profile="eval-v2")

    def test_config_restored_and_demo_untouched(self):
        self.assertEqual(C.MAX_EVENTS_PER_USER, 15)
        self.assertEqual(C.ABANDONED_CART_RATE, 0.0)
        self.assertEqual(self.demo["profile"], None)
        self.assertEqual(dump(self.demo), dump(sh.generate(self.rows, AS_OF, seed=7, n_profiles=N)))

    def test_eval_is_deterministic(self):
        again = sh.generate(self.rows, AS_OF, seed=7, n_profiles=N, profile="eval-v2")
        self.assertEqual(dump(self.eval), dump(again))

    def test_more_returning_customers_than_demo(self):
        _, demo_ret = buyers_and_returning(self.demo)
        buyers, ret = buyers_and_returning(self.eval)
        self.assertGreater(ret, 2 * demo_ret)
        self.assertGreater(ret / buyers, 0.25)

    def test_abandoned_carts_have_no_group_and_are_not_bought(self):
        abandoned = abandoned_carts(self.eval)
        self.assertGreater(len(abandoned), 5 * max(1, len(abandoned_carts(self.demo))))
        self.assertTrue(all(e["event_group_id"] is None for e in abandoned))
        cart_users = {e["cdp_user_id"] for e in abandoned}
        self.assertFalse(cart_users & sh.PERSONA_IDS)            # persona giữ đúng khuôn demo

    def test_event_cap_and_stage_mix(self):
        per = defaultdict(int)
        for e in self.eval["events"]:
            per[e["cdp_user_id"]] += 1
        self.assertLessEqual(max(per.values()), C.PROFILES["eval-v2"]["MAX_EVENTS_PER_USER"])
        self.assertGreater(max(per.values()), C.MAX_EVENTS_PER_USER)
        self.assertEqual(len(self.eval["profiles"]), N)

    def test_personas_and_accounts_identical_to_demo(self):
        def persona_events(res):
            return [(e["cdp_user_id"], e["event_name"], e["product_id"], e["timestamp"]) for e in res["events"] if e["cdp_user_id"] in sh.PERSONA_IDS]
        self.assertEqual(persona_events(self.demo), persona_events(self.eval))
        self.assertEqual([u["email"] for u in self.demo["users"]], [u["email"] for u in self.eval["users"]])

    def test_unknown_profile_rejected(self):
        with self.assertRaises(SystemExit):
            sh.generate(self.rows, AS_OF, seed=7, n_profiles=50, profile="khong-co")


if __name__ == "__main__":
    unittest.main()
