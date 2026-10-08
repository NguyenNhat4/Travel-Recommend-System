"""Profile `g6-pref-v1` của seed_histories (08/10/2026, MOCK_DATA_SPEC §4.3): mỗi khách thường có một chủ đề ẨN (biển / núi / thành phố)
và bốc điểm đến cùng chủ đề với xác suất THEME_PREF_RATE. Demo (profile None), eval-v2 và append-v1 không đổi một byte: ba sha vàng
dưới đây tính trên fixture `make_catalog()` TRƯỚC khi vá (commit 1b5af92); đổi fixture thì phải tính lại và ghi history."""
import hashlib
import unittest
from collections import Counter, defaultdict
from unittest.mock import patch

from data_collection.seed import config as C, seed_histories as sh
from data_collection.tests.test_seed_histories import AS_OF, DESTS, ORIGINS, dump, make_catalog

N = 600
GOLDEN = {   # sha256(dump(...)) với make_catalog(), seed 7, n_profiles 600 — tính trước khi vá g6
    "demo": "8055fc455c7a970f22d4d0dcbc41e9c321fc2edd584cf7716b488e244215a073",
    "eval-v2": "924e647581eeb5a3818e8c7c5b66f6c716c220906f51b9db5735bef88f24a8c6",
    "append-v1": "857fab8be1a325226e43c25807ce0660066bedef5be2e916043cc5912591a1ad",
}
# make_catalog() chỉ có 1 điểm đến núi (Đà Lạt) và 1 thành phố (Hà Nội): thêm mỗi chủ đề một điểm đến nữa cùng cấu trúc, và một
# điểm đến KHÔNG có nhãn (Quảng Ngãi) để kiểm đường bốc toàn cục. Không đụng make_catalog của các test khác.
EXTRA_DESTS = ["Đà Nẵng", "Sa Pa", "Huế", "Quảng Ngãi"]


def sha(res) -> str:
    return hashlib.sha256(dump(res).encode("utf-8")).hexdigest()


def make_theme_catalog():
    rows = make_catalog()

    def add(pid, name, taxonomy, level=None, parent=None, price=1_000_000, dest="Nha Trang", ref=None, **attrs):
        a = {"level": level, "parentProductId": parent, **attrs}
        rows.append({"productId": pid, "name": name, "taxonomy": taxonomy, "destination": dest, "description": "mô tả", "unitPrice": price,
                     "currency": "VND", "available": price is not None, "availableFrom": None, "availableTo": None, "imageUrl": None,
                     "sourceRef": ref or f"booking:{pid}", "attributes": {k: v for k, v in a.items() if v is not None}})

    for d in EXTRA_DESTS:
        for i in range(8):
            h = f"h-{d}-{i}"
            add(h, f"Khách sạn {d} {i}", "hotel", "property", dest=d, price=500000, ref=f"vinpearl:hotel:{h}" if i < 2 else None)
            for j in range(3):
                add(f"r-{d}-{i}-{j}", f"Khách sạn {d} {i} - Phòng {j}", "hotel", "room", parent=h, price=800000 + 100000 * j, dest=d)
        for i in range(5):
            add(f"a-{d}-{i}", f"Điểm {d} {i}", "attraction", dest=d, price=200000 + 10000 * i)
        for i in range(2):
            add(f"c-{d}-{i}", f"Combo {d} {i}", "combo", dest=d, price=500000)
        for o in ORIGINS:
            if o != d:
                add(f"rt-{o}-{d}", f"Vé máy bay {o} - {d}", "flight", "route", dest=d, price=900000, originDestination=o)
                for k in range(2):
                    add(f"f-{o}-{d}-{k}", f"VN{k}: {o} - {d}", "flight", "flight", parent=f"rt-{o}-{d}", dest=d, price=900000 + k)
    return rows


def theme_of_dest():
    return {d: t for t, ds in C.DEST_THEMES.items() for d in ds}


def trips_by_user(res):
    """{user: [destination của từng chuyến có event_group_id]} (khách thường, bỏ purchase trỏ sản phẩm không tồn tại)."""
    by_id = {r["productId"]: r for r in res["world"].by_id.values()}
    seen, out = set(), defaultdict(list)
    for e in res["events"]:
        if e["event_name"] != "purchase" or not e["event_group_id"] or e["event_group_id"] in seen or e["product_id"] not in by_id:
            continue
        if e["cdp_user_id"] in sh.PERSONA_IDS:
            continue
        seen.add(e["event_group_id"])
        out[e["cdp_user_id"]].append(by_id[e["product_id"]]["destination"])
    return out


class ThemeProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_rows = make_catalog()
        cls.rows = make_theme_catalog()
        cls.demo = sh.generate(cls.rows, AS_OF, seed=7, n_profiles=N)
        cls.g6 = sh.generate(cls.rows, AS_OF, seed=7, n_profiles=N, profile="g6-pref-v1")

    # ---- (a) demo không đổi byte; (b) eval-v2 / append-v1 không đổi byte, hằng khôi phục
    def test_demo_unchanged_golden_and_no_theme_stream(self):
        demo = sh.generate(self.base_rows, AS_OF, seed=7, n_profiles=N)
        self.assertEqual(sha(demo), GOLDEN["demo"])
        self.assertEqual(demo["themes"], {})
        self.assertEqual(dump(demo), dump(sh.generate(self.base_rows, AS_OF, seed=7, n_profiles=N, theme_pref=0.0)))
        self.assertEqual(self.demo["themes"], {})
        self.assertEqual(self.demo["profile"], None)

    def test_eval_v2_and_append_v1_unchanged_and_config_restored(self):
        for profile in ("eval-v2", "append-v1"):
            first = sh.generate(self.base_rows, AS_OF, seed=7, n_profiles=N, profile=profile)
            self.assertEqual(sha(first), GOLDEN[profile], profile)
            self.assertEqual(first["themes"], {})
            self.assertEqual(dump(first), dump(sh.generate(self.base_rows, AS_OF, seed=7, n_profiles=N, profile=profile)))
        self.assertEqual(C.THEME_PREF_RATE, 0.0)
        self.assertEqual(C.MAX_EVENTS_PER_USER, 15)
        self.assertEqual(C.ABANDONED_CART_RATE, 0.0)
        self.assertEqual(C.PROFILES["g6-pref-v1"]["THEME_PREF_RATE"], 0.8)
        self.assertEqual({k: v for k, v in C.PROFILES["g6-pref-v1"].items() if k != "THEME_PREF_RATE"}, C.PROFILES["append-v1"])

    def test_g6_with_rate_zero_equals_its_parent_append_v1(self):
        # g6-pref-v1 kế thừa append-v1; tắt sở thích (--theme-pref 0) thì output trùng byte append-v1 và không có stream chủ đề
        off = sh.generate(self.rows, AS_OF, seed=7, n_profiles=N, profile="g6-pref-v1", theme_pref=0.0)
        self.assertEqual(off["themes"], {})
        self.assertEqual(dump(off), dump(sh.generate(self.rows, AS_OF, seed=7, n_profiles=N, profile="append-v1")))
        self.assertNotEqual(dump(off), dump(self.g6))

    # ---- (c) tất định
    def test_g6_is_deterministic(self):
        again = sh.generate(self.rows, AS_OF, seed=7, n_profiles=N, profile="g6-pref-v1")
        self.assertEqual(dump(self.g6), dump(again))
        self.assertEqual(self.g6["themes"], again["themes"])
        self.assertEqual(self.g6["profile"], "g6-pref-v1")
        self.assertEqual(C.THEME_PREF_RATE, 0.0)

    # ---- (d) persona giống demo
    def test_persona_events_identical_to_demo(self):
        def persona_events(res):
            return [(e["cdp_user_id"], e["event_name"], e["product_id"], e["timestamp"]) for e in res["events"] if e["cdp_user_id"] in sh.PERSONA_IDS]
        self.assertEqual(persona_events(self.demo), persona_events(self.g6))
        self.assertEqual(self.demo["bookings"], self.g6["bookings"])
        self.assertEqual([u["email"] for u in self.demo["users"]], [u["email"] for u in self.g6["users"]])

    # ---- (e) khách có chủ đề bám chủ đề; khách không sở thích theo phân phối toàn cục
    def test_themed_users_follow_theme_and_none_users_follow_global(self):
        label = theme_of_dest()
        trips = trips_by_user(self.g6)
        themes = self.g6["themes"]
        same = total = 0
        none_dests: Counter = Counter()
        for user, dests in trips.items():
            theme = themes.get(user)
            if theme:
                total += len(dests)
                same += sum(label.get(d) == theme for d in dests)
            else:
                none_dests.update(dests)
        self.assertGreater(total, 300)
        self.assertGreaterEqual(same / total, 0.7)
        w = self.g6["world"]
        mass = {t: w.theme_mass[t] / w.dest_cum[-1] for t in w.theme_pools}
        n_none = sum(none_dests.values())
        self.assertGreater(n_none, 100)
        for theme, m in mass.items():
            share = sum(c for d, c in none_dests.items() if label.get(d) == theme) / n_none
            self.assertAlmostEqual(share, m, delta=0.1, msg=theme)
        # đối chiếu với demo (cùng fixture): khách không sở thích phân bố như demo theo chủ đề
        demo_dests: Counter = Counter(d for ds in trips_by_user(self.demo).values() for d in ds)
        n_demo = sum(demo_dests.values())
        for theme in mass:
            demo_share = sum(c for d, c in demo_dests.items() if label.get(d) == theme) / n_demo
            share = sum(c for d, c in none_dests.items() if label.get(d) == theme) / n_none
            self.assertAlmostEqual(share, demo_share, delta=0.1, msg=theme)
        # điểm đến không nhãn (Quảng Ngãi) vẫn tới được qua lần bốc toàn cục
        self.assertIn("Quảng Ngãi", {d for ds in trips.values() for d in ds})

    # ---- (f) themes chỉ chứa khách thường
    def test_themes_cover_exactly_generic_users(self):
        generic = {p["cdp_user_id"] for p in self.g6["profiles"]} - sh.PERSONA_IDS
        self.assertEqual(set(self.g6["themes"]), generic)
        self.assertFalse(set(self.g6["themes"]) & sh.PERSONA_IDS)
        values = Counter(self.g6["themes"].values())
        self.assertTrue(set(values) <= set(C.DEST_THEMES) | {None})
        self.assertAlmostEqual(values[None] / len(generic), C.THEME_NO_PREF_SHARE, delta=0.1)
        for theme in C.DEST_THEMES:
            self.assertGreater(values[theme], 0, theme)
        # DEST_THEMES: đúng 15 + 16 + 10 nhãn, không trùng giữa các chủ đề
        self.assertEqual([len(v) for v in C.DEST_THEMES.values()], [15, 16, 10])
        self.assertEqual(len(theme_of_dest()), 41)

    def test_world_theme_pools_use_catalog_weights(self):
        w = self.g6["world"]
        self.assertEqual(set(w.theme_pools), {"beach", "mountain", "city"})
        self.assertEqual(w.theme_pools["mountain"][0], ["Sa Pa", "Đà Lạt"])
        self.assertEqual(w.theme_pools["city"][0], ["Huế", "Hà Nội"])
        self.assertEqual(sorted(w.theme_pools["beach"][0]), ["Nha Trang", "Phú Quốc", "Đà Nẵng"])
        for theme, (names, cum) in w.theme_pools.items():
            self.assertEqual(len(names), len(cum))
            self.assertAlmostEqual(cum[-1], w.theme_mass[theme])
        self.assertEqual(sum(w.theme_mass.values()), w.dest_cum[-1] - sum(1 for r in self.rows if r["destination"] == "Quảng Ngãi"
                                                                            and w.meta[r["productId"]]["is_bookable"]))

    def test_catalog_without_theme_destinations_rejected_when_pref_on(self):
        # không điểm đến nào của catalog có nhãn → không thể gán chủ đề: dừng rõ ràng thay vì sinh bộ "có sở thích" rỗng
        with patch.object(C, "DEST_THEMES", {"beach": ["Nơi không có trong catalog"]}):
            with self.assertRaises(SystemExit):
                sh.generate(self.base_rows, AS_OF, seed=7, n_profiles=50, profile="g6-pref-v1")
        self.assertEqual(C.THEME_PREF_RATE, 0.0)
        self.assertEqual(DESTS, ["Nha Trang", "Phú Quốc", "Đà Lạt", "Hà Nội"])


if __name__ == "__main__":
    unittest.main()
