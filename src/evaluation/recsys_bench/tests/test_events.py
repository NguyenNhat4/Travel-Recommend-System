from datetime import datetime, timezone

import pytest

from src.evaluation.recsys_bench.events import FutureEventError, filter_events, parse_ts

AS_OF = datetime(2026, 9, 24, tzinfo=timezone.utc)


def test_only_orphan_and_ungrouped_purchases_are_dropped(world, events):
    kept, report = filter_events(events, world["index"], AS_OF)
    assert report.total == 17 and report.purchase_total == 12
    assert report.purchase_orphan == 1 and report.purchase_missing_group == 1 and report.purchase_dropped == 2
    assert report.kept == len(kept) == 15
    dropped = [e for e in events if e not in kept]
    assert {(e["cdpUserId"], e["productId"]) for e in dropped} == {("u4", "ghost"), ("u4", "A1")}


def test_browse_and_search_without_group_are_kept(world, events):
    kept, report = filter_events(events, world["index"], AS_OF)
    ungrouped = [e for e in kept if e["eventName"] != "purchase" and not e["eventGroupId"]]
    assert len(ungrouped) == 5          # seed chỉ gắn gid cho purchase — không được loại
    assert report.browse_orphan == 1 and report.search_without_product == 1
    assert report.users_before == report.users_after == 6


def test_overlapping_orphan_without_group_counts_once(world, events):
    events.append({"cdpUserId": "u6", "eventName": "purchase", "productId": "ghost-3",
                   "timestamp": "2026-04-05T10:00:00Z", "eventGroupId": None})
    _, report = filter_events(events, world["index"], AS_OF)
    assert report.purchase_orphan == 2 and report.purchase_missing_group == 2 and report.purchase_dropped == 3


def test_event_at_or_after_as_of_is_rejected(world, events):
    events.append({"cdpUserId": "u1", "eventName": "product_view", "productId": "A1",
                   "timestamp": AS_OF.isoformat(), "eventGroupId": None})
    with pytest.raises(FutureEventError, match="as_of"):
        filter_events(events, world["index"], AS_OF)


def test_report_lines_state_rates_over_purchases(world, events):
    _, report = filter_events(events, world["index"], AS_OF)
    text = "\n".join(report.lines())
    assert "orphan 1 (8.3 %)" in text and "thiếu event_group_id 1 (8.3 %)" in text


def test_parse_ts_is_timezone_aware():
    assert parse_ts("2026-01-02T01:00:00+02:00") == parse_ts("2026-01-01T23:00:00Z")
    assert parse_ts("2026-01-01T00:00:00").tzinfo is not None
