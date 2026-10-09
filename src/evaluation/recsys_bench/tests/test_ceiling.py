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
    # u1: chuyến đã đặt T1 còn mở đứng trước view lẻ A1 đến sau (FR-REC-02, 09/10 — trước đó `_solo_A1`, lỗi I-3)
    assert views["u1"].active_trip == "T1" and views["u1"].destination == "Nha Trang" and views["u2"].active_trip is None
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
    rows = [{"cdpUserId": "z", "eventName": "purchase", "productId": "R1", "timestamp": f"2026-09-{d:02d}T00:00:00Z", "eventGroupId": "g", "usingDate": "2026-09-30"}
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


def test_engine_view_closes_trips_by_using_date_like_the_engine(world):
    """FR-REC-02 (02/10): trip có usingDate đã qua không còn mở; trip mua từ lâu nhưng usingDate ở tương lai vẫn mở — view
    phải trùng diagnostics engine."""
    from src.evaluation.recsys_bench.engine import OfflineEngine
    index = world["index"]
    as_of = datetime(2026, 9, 24, tzinfo=timezone.utc)
    rows = [{"cdpUserId": "z", "eventName": "purchase", "productId": "R1", "timestamp": "2026-09-19T00:00:00Z", "eventGroupId": "done",
             "usingDate": "2026-09-21"},
            {"cdpUserId": "z", "eventName": "purchase", "productId": "A1", "timestamp": "2026-05-01T00:00:00Z", "eventGroupId": "soon",
             "usingDate": "2026-10-10"}]
    view = engine_view(rows, index, as_of)
    assert view.trips["done"].ends_on.isoformat() == "2026-09-21" and view.active_trip == "soon"
    assert view.excluded == {"attraction"} and view.strategy == "cross_vertical"
    engine = OfflineEngine(index, world["vectors"], [e for e in rows], candidate_k=50)
    r = engine.recommend("z", as_of, 5, rows)
    assert r["strategy"] == "cross_vertical" and r["diagnostics"]["excludedVerticals"] == ["attraction"]
    # cả hai đã qua ngày sử dụng → không trip mở, long_term
    rows2 = [{**rows[1], "usingDate": "2026-05-20"}, rows[0]]
    assert engine_view(rows2, index, as_of).active_trip is None and engine.recommend("z", as_of, 5, rows2)["strategy"] == "long_term"


def test_engine_view_mirrors_cap_rule_and_local_today(world):
    """Review PR M6 (01/10): event bị cap lặp vẫn quyết định tuổi / ngày kết thúc / món đã mua; "hôm nay" theo giờ VN.
    engine_view, excluded_taxonomies và trip_destination phải cho cùng kết quả với diagnostics engine."""
    from src.evaluation.recsys_bench.arms import trip_destination
    from src.evaluation.recsys_bench.engine import OfflineEngine
    from src.evaluation.recsys_bench.splits import excluded_taxonomies
    index = world["index"]
    as_of = datetime(2026, 9, 23, 18, 30, tzinfo=timezone.utc)       # = 01:30 giờ VN 24/09 → hôm nay 24/09
    # 3 view R1 rồi purchase R1 (bị cap) với usingDate 24/09: chuyến còn mở đúng ngày cuối theo giờ VN
    rows = [{"cdpUserId": "z", "eventName": "product_view", "productId": "R1", "timestamp": f"2026-09-{d:02d}T00:00:00Z", "eventGroupId": "g"}
            for d in (10, 11, 12)] + \
           [{"cdpUserId": "z", "eventName": "purchase", "productId": "R1", "timestamp": "2026-09-13T00:00:00Z", "eventGroupId": "g",
             "usingDate": "2026-09-24"}]
    view = engine_view(rows, index, as_of)
    assert view.trips["g"].n_events == 3 and view.trips["g"].ends_on.isoformat() == "2026-09-24"
    assert view.active_trip == "g" and view.excluded == {"hotel"} and index.resolve("R1") in view.bought_units
    assert excluded_taxonomies(rows, index, as_of) == {"hotel"} and trip_destination(index, rows, as_of) == view.destination
    engine = OfflineEngine(index, world["vectors"], [rows[-1]], candidate_k=50)
    r = engine.recommend("z", as_of, 5, rows)
    assert r["strategy"] == "cross_vertical" and r["diagnostics"]["excludedVerticals"] == ["hotel"]
    # Cùng dữ liệu nhưng as_of 23/09 18:30 giờ VN (11:30Z) → hôm nay 23/09 vẫn mở; 24/09 17:00Z (00:00 VN 25/09) → đã xong
    assert engine_view(rows, index, datetime(2026, 9, 23, 11, 30, tzinfo=timezone.utc)).active_trip == "g"
    late = datetime(2026, 9, 24, 17, 0, tzinfo=timezone.utc)
    assert engine_view(rows, index, late).active_trip is None and excluded_taxonomies(rows, index, late) == set()
    assert engine.recommend("z", late, 5, rows)["strategy"] == "long_term"
