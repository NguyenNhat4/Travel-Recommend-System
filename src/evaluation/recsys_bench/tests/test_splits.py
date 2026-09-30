from datetime import datetime, timezone

from src.evaluation.recsys_bench.events import filter_events, parse_ts
from src.evaluation.recsys_bench.splits import default_cutoff, leave_last_booking_out, temporal_split

AS_OF = datetime(2026, 9, 24, tzinfo=timezone.utc)


def kept_events(world, events):
    return filter_events(events, world["index"], AS_OF)[0]


def test_llbo_hides_last_purchase_as_parent_unit(world, events):
    split = leave_last_booking_out(kept_events(world, events), world["index"])
    assert split.targets == {"u1": "F1", "u2": "A1", "u5": "G1", "VP0000001": "H1"}
    assert split.as_of_by_user["u1"] == parse_ts("2026-06-03T10:00:00Z")


def test_llbo_train_is_strictly_before_the_target(world, events):
    split = leave_last_booking_out(kept_events(world, events), world["index"])
    for user, as_of in split.as_of_by_user.items():
        assert all(parse_ts(e["timestamp"]) < as_of for e in split.train_by_user[user])
    names = sorted((e["eventName"], e["productId"]) for e in split.train_by_user["u1"])
    assert names == [("product_view", "A1"), ("purchase", "R1"), ("search", None)]   # view C1 sau target bị loại


def test_llbo_skips_single_purchase_and_dropped_purchases(world, events):
    split = leave_last_booking_out(kept_events(world, events), world["index"])
    assert "u3" not in split.targets and "u4" not in split.targets


def test_llbo_meta_explains_unreachable_targets(world, events):
    meta = leave_last_booking_out(kept_events(world, events), world["index"]).meta
    assert meta["usersTest"] == 4 and meta["personaInTest"] == ["VP0000001"]
    assert meta["repeatTarget"] == 2            # u5 mua lại G1, P1 đặt lại H1
    assert meta["targetVerticalExcluded"] == 1  # u5: golf đã mua trong trip mở 39 ngày trước
    assert meta["targetTaxonomy"] == {"attraction": 1, "flight": 1, "golf": 1, "hotel": 1}


def test_llbo_min_trips_matches_seed_baseline_selection(world, events):
    split = leave_last_booking_out(kept_events(world, events), world["index"], min_trips=2)
    assert set(split.targets) == {"u2", "u5", "VP0000001"}   # u1 chỉ có một event_group_id


def test_llbo_same_timestamp_purchases_are_deterministic(world):
    rows = [{"cdpUserId": "u9", "eventName": "purchase", "productId": pid, "timestamp": "2026-03-03T00:00:00Z",
             "eventGroupId": "g"} for pid in ("A1", "C1")]
    first = leave_last_booking_out(rows, world["index"])
    second = leave_last_booking_out(list(reversed(rows)), world["index"])
    assert first.targets == second.targets == {"u9": "C1"}
    assert first.train_by_user["u9"] == [] and first.meta["sameInstantDropped"] == 1


def test_train_purchases_include_every_valid_purchase(world, events):
    split = leave_last_booking_out(kept_events(world, events), world["index"])
    assert len(split.train_purchases) == 10      # 12 purchase − orphan − thiếu gid


def test_temporal_split_uses_one_cutoff(world, events):
    T = parse_ts("2026-05-01T00:00:00Z")
    split = temporal_split(kept_events(world, events), world["index"], cutoff=T)
    assert split.targets == {"u2": "A1", "u5": "G1", "VP0000001": "H1"}
    assert set(split.as_of_by_user.values()) == {T}
    assert split.meta["coldUsersExcluded"] == 1 and split.meta["testPurchasesTotal"] == 3   # u1 không có train
    assert all(parse_ts(e["timestamp"]) < T for rows in split.train_by_user.values() for e in rows)


def test_excluded_taxonomies_caps_repeats_like_the_engine(world):
    from src.evaluation.recsys_bench.tests.conftest import ev
    from src.evaluation.recsys_bench.splits import excluded_taxonomies

    as_of = parse_ts("2026-06-30T00:00:00Z")
    # Trip hotel mua 30 ngày trước; view A1 (không gid → `_solo_A1`) 4 lần, lần thứ 4 mới là 5 ngày trước.
    train = [ev("u", "purchase", "R1", "2026-05-31T00:00:00Z", "G"),
             *[ev("u", "product_view", "A1", ts) for ts in
               ("2026-05-21T00:00:00Z", "2026-05-26T00:00:00Z", "2026-05-27T00:00:00Z", "2026-06-25T00:00:00Z")]]
    # Engine bỏ lần xem thứ 4 → `_solo_A1` có tuổi 34 ngày, trip hotel (30 ngày) mới là trip đang mở.
    assert excluded_taxonomies(train, world["index"], as_of) == {"hotel"}
    from src.evaluation.recsys_bench.engine import OfflineEngine
    engine = OfflineEngine(world["index"], world["vectors"], [])
    assert engine.recommend("u", as_of, 5, train)["diagnostics"]["excludedVerticals"] == ["hotel"]


def test_default_cutoff_is_purchase_quantile(world, events):
    assert default_cutoff(kept_events(world, events), world["index"]) == parse_ts("2026-06-01T10:00:00Z")
