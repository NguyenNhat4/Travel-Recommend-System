"""Harness không để engine thấy dữ liệu từ as_of trở đi. Test (2) ghi lại vì sao chốt chặn phải nằm ở harness."""
from datetime import datetime, timedelta, timezone

import pytest

from src.backend.app.application.recommendation import RecommendForUser
from src.evaluation.recsys_bench.engine import LeakageError, OfflineCdpReader, OfflineEngine
from src.evaluation.recsys_bench.tests.conftest import ev

AS_OF = datetime(2026, 6, 3, 10, tzinfo=timezone.utc)
HISTORY = [ev("u1", "purchase", "R1", "2026-06-01T10:00:00Z", "T1"), ev("u1", "product_view", "A1", "2026-06-02T10:00:00Z")]


def engine_for(world, purchases=()):
    return OfflineEngine(world["index"], world["vectors"], list(purchases))


def test_future_event_is_rejected_by_the_harness(world):
    future = ev("u1", "product_view", "C1", "2026-06-05T10:00:00Z")
    with pytest.raises(LeakageError, match="as_of"):
        engine_for(world).recommend("u1", AS_OF, 5, [*HISTORY, future])


def test_engine_itself_does_not_drop_future_events(world):
    # Engine production kẹp days_ago về 0 thay vì loại event sau `now` → rò rỉ im lặng. Nếu test này đổi kết quả,
    # engine đã tự lọc — cập nhật harness và ghi history, đừng xoá test.
    engine = engine_for(world)
    direct = RecommendForUser(world["index"], world["vectors"], engine.reader_at(AS_OF), engine.popularity_at(AS_OF))
    future = ev("u1", "product_view", "A1", (AS_OF + timedelta(days=2)).isoformat())
    assert direct("u1", k=5, now=AS_OF, events=[future])["diagnostics"]["eventsUsed"] == 1


def test_engine_never_reads_cdp_history_offline(world):
    reader = OfflineCdpReader([], AS_OF)
    with pytest.raises(LeakageError):
        reader.events_for_user("u1")
    with pytest.raises(LeakageError):
        reader.all_events()
    response = engine_for(world).recommend("u1", AS_OF, 5, HISTORY)   # không ném: engine dùng events= truyền vào
    assert response["recommendations"] and response["diagnostics"]["eventsUsed"] == 2


def test_later_view_without_group_takes_over_the_open_trip(world):
    # Seed không gắn event_group_id cho view/cart → engine gom thành trip `_solo_<productId>`. Một view SAU purchase
    # thành trip đang mở (trẻ nhất) nên cross_vertical và category exclusion mất. Ghi lại hành vi engine
    # (Issue Day 1 trong docs/spec/bench/recsys-offline-eval.md), không sửa ở harness.
    only_purchase = engine_for(world).recommend("u1", AS_OF, 5, HISTORY[:1])
    with_later_view = engine_for(world).recommend("u1", AS_OF, 5, HISTORY)
    assert only_purchase["strategy"] == "cross_vertical"
    assert only_purchase["diagnostics"]["excludedVerticals"] == ["hotel"]
    assert with_later_view["strategy"] == "cold_start_content"
    assert with_later_view["diagnostics"]["excludedVerticals"] == []


def test_popularity_only_counts_purchases_before_as_of(world):
    before = ev("x", "purchase", "G1", "2026-05-10T10:00:00Z", "g1")
    at = ev("y", "purchase", "A1", AS_OF.isoformat(), "g2")
    after = ev("z", "purchase", "C1", "2026-06-20T10:00:00Z", "g3")
    index = world["index"]
    scores = engine_for(world, [after, at, before]).popularity_at(AS_OF).unit_scores()
    assert set(scores) == {index.resolve("G1")}


def test_purchase_window_is_measured_from_as_of_not_wall_clock():
    rows = [ev("x", "purchase", "G1", "2026-05-20T10:00:00Z", "g"), ev("y", "purchase", "A1", "2025-01-01T10:00:00Z", "h")]
    assert [e["productId"] for e in OfflineCdpReader(rows, AS_OF).purchase_events(since_days=30)] == ["G1"]


def test_same_input_same_output(world):
    engine = engine_for(world, HISTORY[:1])
    first = engine.recommend("u1", AS_OF, 5, HISTORY)
    second = engine.recommend("u1", AS_OF, 5, HISTORY)
    assert [r["productId"] for r in first["recommendations"]] == [r["productId"] for r in second["recommendations"]]


def test_eval_mode_drops_vertical_cap_and_prod_mode_keeps_it(world, events):
    """mode eval (mặc định): không cap 2 món / taxonomy nên có thể trả > 2 cùng loại; mode prod: đúng production."""
    from datetime import datetime, timezone

    from src.backend.app.domain.recommendation.profile import MAX_PER_VERTICAL
    from src.evaluation.recsys_bench.arms import EngineArm
    from src.evaluation.recsys_bench.engine import OfflineEngine
    from src.evaluation.recsys_bench.events import filter_events
    from src.evaluation.recsys_bench.splits import leave_last_booking_out
    index = world["index"]
    as_of = datetime(2026, 9, 24, tzinfo=timezone.utc)
    kept, _ = filter_events(events, index, as_of)
    split = leave_last_booking_out(kept, index)
    ev = OfflineEngine(index, world["vectors"], split.train_purchases)
    pr = OfflineEngine(index, world["vectors"], split.train_purchases, mode="prod")
    assert ev.mode == "eval" and EngineArm(ev).key == "engine" and EngineArm(pr).key == "engine_prod"
    for user in split.targets:
        a = ev.recommend(user, split.as_of_by_user[user], 20, split.train_by_user[user])
        b = pr.recommend(user, split.as_of_by_user[user], 20, split.train_by_user[user])
        from collections import Counter
        per_tax_prod = Counter(r["taxonomy"] for r in b["recommendations"])
        assert all(n <= MAX_PER_VERTICAL for n in per_tax_prod.values())
        assert len(a["recommendations"]) >= len(b["recommendations"])
    import pytest
    with pytest.raises(ValueError):
        OfflineEngine(index, world["vectors"], split.train_purchases, mode="x")
