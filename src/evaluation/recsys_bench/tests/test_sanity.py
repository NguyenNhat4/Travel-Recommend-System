"""B1 `sanity.py`: từng kiểm tra trên dữ liệu dựng tay — luật lifecycle của seed (ngày lịch VN), chuyến ≥ 2 vertical, một điểm đến,
cạnh lộn xộn, phổ biến (chỉ báo), tổng hợp + markdown; không cần DB."""
from datetime import datetime, timezone

from src.evaluation.recsys_bench import sanity as S

AS_OF = datetime(2026, 9, 22, tzinfo=timezone.utc)      # 07:00 ngày 22/09 giờ VN


def ev(user, name, pid, ts, gid=None, tax="hotel"):
    return {"cdpUserId": user, "eventName": name, "productId": pid, "timestamp": ts, "eventGroupId": gid, "taxonomy": tax}


def test_lifecycle_seed_rule_uses_vietnam_calendar_days():
    as_of_day = AS_OF.astimezone(S.VN).date()
    assert S.lifecycle_seed_rule([], as_of_day) == ("new", None)
    # 2026-09-18T20:00Z = 03:00 ngày 19/09 giờ VN → 3 ngày (như VP0000001 trong DB seed)
    assert S.lifecycle_seed_rule([ev("u", "purchase", "R1", "2026-09-18T20:00:00Z", "g")], as_of_day) == ("active", 3)
    assert S.lifecycle_seed_rule([ev("u", "purchase", "R1", "2026-03-26T10:00:00Z", "g")], as_of_day) == ("active", 180)
    assert S.lifecycle_seed_rule([ev("u", "purchase", "R1", "2026-03-25T10:00:00Z", "g")], as_of_day) == ("dormant", 181)
    assert S.lifecycle_seed_rule([ev("u", "purchase", "R1", "2025-09-21T10:00:00Z", "g")], as_of_day) == ("churned", 366)
    assert S.lifecycle_seed_rule([ev("u", "product_view", "R1", "2026-09-20T10:00:00Z")], as_of_day) == ("new", None)


def test_lifecycle_mix_and_recomputed(monkeypatch):
    consts = {"STAGE_MIX": {"new": 0.25, "active": 0.45, "dormant": 0.20, "churned": 0.10}, "STAGE_TOLERANCE": 0.05, "MULTI_VERTICAL_RATE": 0.65}
    profiles = ([{"cdpUserId": f"n{i}", "lifecycleStage": "new", "daysSinceLastBooking": None} for i in range(5)]
                + [{"cdpUserId": f"a{i}", "lifecycleStage": "active", "daysSinceLastBooking": 3} for i in range(9)]
                + [{"cdpUserId": f"d{i}", "lifecycleStage": "dormant", "daysSinceLastBooking": 182} for i in range(4)]
                + [{"cdpUserId": f"c{i}", "lifecycleStage": "churned", "daysSinceLastBooking": 366} for i in range(2)])
    mix = S.lifecycle_mix(profiles, consts)
    assert mix.ok is True and mix.values["n"] == 20 and abs(mix.values["shares"]["active"] - 0.45) < 1e-9
    assert S.lifecycle_mix(profiles[:5] + profiles[5:7], consts).ok is False          # 5 new / 2 active → lệch
    events = ([ev(f"a{i}", "purchase", "R1", "2026-09-18T20:00:00Z", "g") for i in range(9)]
              + [ev(f"d{i}", "purchase", "R1", "2026-03-24T10:00:00Z", "g") for i in range(4)]
              + [ev(f"c{i}", "purchase", "R1", "2025-09-21T10:00:00Z", "g") for i in range(2)]
              + [ev("n0", "product_view", "R1", "2026-09-20T10:00:00Z")])
    for p in profiles:          # cột seed còn lại: số trip có purchase, taxonomy đã mua
        p["lifetimeOrderCount"] = 0 if p["lifecycleStage"] == "new" else 1
        p["purchasedVerticals"] = [] if p["lifecycleStage"] == "new" else ["hotel"]
    rec = S.lifecycle_recomputed(profiles, events, AS_OF)
    assert rec.ok is True and rec.values["bad"] == {} and rec.values["asOfDay"] == "2026-09-22"
    profiles[5]["lifecycleStage"] = "dormant"
    profiles[6]["lifetimeOrderCount"] = 3
    profiles[7]["purchasedVerticals"] = ["golf"]
    bad = S.lifecycle_recomputed(profiles, events, AS_OF)
    assert bad.ok is False and bad.values["bad"] == {"lifecycleStage": 1, "lifetimeOrderCount": 1, "purchasedVerticals": 1}
    assert "a0 lifecycleStage: seed 'dormant' / tính lại 'active'" in bad.detail
    cover = S.profiles_cover_events(profiles, events + [ev("ghost", "purchase", "R1", "2026-09-01T00:00:00Z", "g")])
    assert cover.ok is False and cover.values["missing"] == ["ghost"] and S.profiles_cover_events(profiles, events).ok is True


def test_trip_checks_and_messy_edges(world):
    index = world["index"]
    consts = {"STAGE_MIX": {}, "STAGE_TOLERANCE": 0.05, "MULTI_VERTICAL_RATE": 0.65}
    # 3 chuyến: T1 hotel+flight (2 vertical), T2 hotel+attraction, T3 chỉ hotel → 2/3 = 66,7 %
    events = [ev("u1", "purchase", "R1", "2026-06-01T10:00:00Z", "T1", "hotel"), ev("u1", "purchase", "FL1", "2026-06-02T10:00:00Z", "T1", "flight"),
              ev("u2", "purchase", "R1", "2026-05-01T10:00:00Z", "T2", "hotel"), ev("u2", "purchase", "A1", "2026-05-02T10:00:00Z", "T2", "attraction"),
              ev("u3", "purchase", "R3", "2026-04-01T10:00:00Z", "T3", "hotel"),
              ev("u4", "purchase", "ghost", "2026-04-02T10:00:00Z", "T5", "hotel"),          # orphan
              ev("u4", "purchase", "A1", "2026-04-03T10:00:00Z", None, "attraction")]        # thiếu gid
    mv = S.trips_multi_vertical(events, consts)
    assert mv.values == {"share": 0.5, "trips": 4, "multi": 2} and mv.ok is False     # 2/4 chuyến: 50 % lệch quá 5 điểm so với 65 %
    od = S.one_destination_per_trip(events, index)
    assert od.values["trips"] == 3 and od.values["multiDestination"] == 0 and od.ok is True   # T5 chỉ có orphan → không tính
    events2 = events + [ev("u3", "purchase", "A1", "2026-04-02T10:00:00Z", "T3", "attraction")]   # T3: Phú Quốc + Nha Trang
    assert S.one_destination_per_trip(events2, index).ok is False
    me = S.messy_edges(events, index)
    assert me.values["purchases"] == 7 and me.values["orphan"] == 1 and me.values["missingGid"] == 1 and me.ok is False   # 14 % ≫ 2 %
    many = [ev(f"x{i}", "purchase", "R1", "2026-01-01T00:00:00Z", f"g{i}") for i in range(93)]
    me2 = S.messy_edges(many + [ev("o", "purchase", "ghost", "2026-01-01T00:00:00Z", "go")] * 2
                        + [ev("m", "purchase", "A1", "2026-01-01T00:00:00Z", None)] * 3, index)
    assert me2.ok is True and abs(me2.values["orphanShare"] - 2 / 98) < 1e-9


def test_lifecycle_recomputed_checks_last_destination_when_index_given(world):
    index = world["index"]
    events = [ev("u", "purchase", "R3", "2026-09-01T00:00:00Z", "g1", "hotel"), ev("u", "purchase", "A1", "2026-09-10T00:00:00Z", "g2", "attraction")]
    good = {"cdpUserId": "u", "lifecycleStage": "active", "daysSinceLastBooking": 12, "lifetimeOrderCount": 2,
            "purchasedVerticals": ["attraction", "hotel"], "lastDestination": "Nha Trang"}
    assert S.lifecycle_recomputed([good], events, AS_OF, index).ok is True
    assert S.lifecycle_recomputed([{**good, "lastDestination": "Phú Quốc"}], events, AS_OF, index).values["bad"] == {"lastDestination": 1}
    assert S.lifecycle_recomputed([{**good, "lastDestination": "Phú Quốc"}], events, AS_OF).ok is True      # không có index → không kiểm


def test_popularity_golf_split_users_are_indicators(world, tmp_path):
    index = world["index"]
    events = [ev("u", "purchase", "R1", "2026-01-01T00:00:00Z", "g")] * 8 + [ev("u", "purchase", "A1", "2026-01-01T00:00:00Z", "g", "attraction")] * 2 \
        + [ev("u", "purchase", "G1", "2026-01-01T00:00:00Z", "g", "golf")] * 1 + [ev("u", "purchase", "C1", "2026-01-01T00:00:00Z", "g", "combo")]
    pop = S.popularity(events, index)
    assert pop.ok is None and pop.values["productsWithPurchase"] == 4 and abs(pop.values["top10Share"] - 8 / 12) < 1e-9
    assert 0 < pop.values["giniProduct"] < 1 and pop.values["zipfSlope"] is None       # < 10 sản phẩm → không hồi quy
    assert S.gini([1, 1, 1, 1]) == 0.0 and S.gini([0, 0, 10]) > 0.6 and S.zipf_slope([100 // (i + 1) for i in range(20)]) < -0.5
    g = S.golf_share(events)
    assert g.ok is None and abs(g.values["golf"] - 1 / 12) < 1e-9 and "hotel 66.7%" in g.detail
    (tmp_path / "split-llbo-x.json").write_text('{"canonical": {"targets": {"a": {}, "b": {}}}}', encoding="utf-8")
    (tmp_path / "split-bad.json").write_text("[]", encoding="utf-8")
    su = S.split_users(tmp_path)
    assert su.ok is None and su.values == {"split-bad.json": None, "split-llbo-x.json": 2}


def test_run_all_summary_markdown_and_seed_constants(world, monkeypatch):
    index = world["index"]
    consts = S.seed_constants()
    assert consts["STAGE_MIX"] == {"new": 0.25, "active": 0.45, "dormant": 0.20, "churned": 0.10} and consts["STAGE_TOLERANCE"] == 0.05
    assert consts["MULTI_VERTICAL_RATE"] == 0.65
    checks = S.run_all([], [], index, AS_OF, world.get("missing_dir") or __import__("pathlib").Path("does-not-exist"))
    s = S.summary(checks)
    assert s["pass"] is False and "lifecycle_mix" in s["hardFailed"] and "profiles_cover_events" in s["hardFailed"] and len(s["checks"]) == 9
    md = S.markdown(checks)
    assert "**FAIL**" in md and "chỉ báo" in md and "`popularity`" in md
