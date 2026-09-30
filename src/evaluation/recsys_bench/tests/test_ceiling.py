"""B5: `engine_view` mô phỏng đúng profile / mask của engine trên bộ event dựng tay; `unreachable` nêu đúng lý do; ceiling tổng."""
from datetime import datetime, timezone

from src.evaluation.recsys_bench.arms import EngineArm
from src.evaluation.recsys_bench.bench import evaluate
from src.evaluation.recsys_bench.ceiling import REASONS, ceiling, ceiling_markdown, engine_view, unreachable
from src.evaluation.recsys_bench.engine import OfflineEngine
from src.evaluation.recsys_bench.events import filter_events
from src.evaluation.recsys_bench.splits import leave_last_booking_out

AS_OF = datetime(2026, 9, 24, tzinfo=timezone.utc)


def _split(world, events):
    kept, _ = filter_events(events, world["index"], AS_OF)
    return leave_last_booking_out(kept, world["index"])


def test_engine_view_matches_engine_diagnostics(world, events):
    """Điểm đến / taxonomy bị loại / strategy suy từ view phải trùng những gì RecommendForUser khai trong diagnostics."""
    index = world["index"]
    split = _split(world, events)
    engine = OfflineEngine(index, world["vectors"], split.train_purchases)
    for u in split.targets:
        view = engine_view(split.train_by_user[u], index, split.as_of_by_user[u])
        r = engine.recommend(u, split.as_of_by_user[u], 20, split.train_by_user[u])
        assert view.strategy == r["strategy"], u
        if r["strategy"] != "popular":
            assert view.destination == r["destination"] and sorted(view.excluded) == (r["diagnostics"].get("excludedVerticals") or []), u


def test_unreachable_reasons_on_fixture(world, events):
    index = world["index"]
    split = _split(world, events)
    views = {u: engine_view(split.train_by_user[u], index, split.as_of_by_user[u]) for u in split.targets}
    got = {u: unreachable(split.targets[u], views[u], index) for u in split.targets}
    # u5 mua lại G1 trong trip mở T6 (39 ngày) → đã mua + golf bị loại; VP0000001 đặt lại H1 đã mua trong P1a (trip mở là
    # view lẻ _solo_R1, không loại taxonomy); u1 target F1 cùng điểm đến với trip mở (view A1 Nha Trang); u2 không có trip mở
    assert got["u5"] == ["already_bought", "taxonomy_excluded"]
    assert got["VP0000001"] == ["already_bought"] and views["VP0000001"].active_is_solo
    assert got["u1"] == [] and got["u2"] == []
    assert views["u1"].active_trip == "_solo_A1" and views["u1"].destination == "Nha Trang" and views["u2"].active_trip is None
    # bản chính xác theo diagnostics engine: strategy popular → cold_start; điểm đến khác → destination_mismatch
    assert unreachable("F1", views["u1"], index, engine_meta={"strategy": "popular"}) == ["cold_start"]
    assert unreachable("F1", views["u1"], index, engine_meta={"strategy": "cross_vertical", "destination": "Phú Quốc",
                                                              "excludedVerticals": ["flight"]}) == ["taxonomy_excluded", "destination_mismatch"]
    # mask theo điểm đến rỗng → engine bỏ điều kiện điểm đến → không tính lệch điểm đến
    assert unreachable("F1", views["u1"], index, engine_meta={"strategy": "recent_activity", "destination": "Sao Hỏa",
                                                              "excludedVerticals": []}) == []
    # unit không có vector
    assert unreachable("F1", views["u1"], index, has_vector={"H1"}) == ["no_vector"]
    assert all(r in REASONS for reasons in got.values() for r in reasons)


def test_engine_view_caps_repeats_and_ignores_unresolvable(world):
    index = world["index"]
    rows = [{"cdpUserId": "z", "eventName": "purchase", "productId": "R1", "timestamp": f"2026-09-{d:02d}T00:00:00Z", "eventGroupId": "g"}
            for d in range(1, 8)] + [{"cdpUserId": "z", "eventName": "product_view", "productId": "ghost", "timestamp": "2026-09-10T00:00:00Z"}]
    view = engine_view(rows, index, AS_OF)
    assert view.trips["g"].n_events == 3 and view.n_events == 3 and "ghost" not in str(view.trips)
    assert view.active_trip == "g" and view.excluded == {"hotel"} and index.resolve("R1") in view.bought_units
    assert engine_view([], index, AS_OF).strategy == "popular"


def test_ceiling_aggregates_and_markdown(world, events):
    index = world["index"]
    split = _split(world, events)
    _, per_user = evaluate(EngineArm(OfflineEngine(index, world["vectors"], split.train_purchases)), split, index, k=20)
    rows = {r["user"]: r for r in per_user}
    views = {u: engine_view(split.train_by_user[u], index, split.as_of_by_user[u]) for u in split.targets}
    c = ceiling(rows, split, index, views, k=20)
    assert c["n"] == 4 and c["reachable"] == 2 and c["ceiling"] == 0.5 and c["approxAgree"] == 1.0
    assert c["reasonsMulti"] == {"already_bought": 2, "taxonomy_excluded": 1} and c["firstReason"] == {"already_bought": 2}
    assert c["recall@20_reachable"] >= c["recall@20"] and set(c["perUser"]) == set(split.targets)
    md = ceiling_markdown(c, mpd_recall=0.6)
    assert "ceiling < Recall@20 mpd" in md and "`already_bought` | 2 | 2" in md
    assert "không phải nút thắt" in ceiling_markdown(c, mpd_recall=0.4)
