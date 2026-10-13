"""Đường đọc CDP của gợi ý tối đa 500 event mới nhất (hop-dong-tich-hop-cdp.md §6, cài 2026-10-12).

Adapter Postgres cắt bằng `LIMIT`; engine cắt thêm một lần cho adapter sau này. Đường `events=` (harness bench) không cắt,
để baseline đánh giá không đổi.
"""
from __future__ import annotations

from datetime import timedelta

from src.backend.app.application.ports.cdp_client import HISTORY_MAX_EVENTS
from src.backend.app.application.recommendation import RecommendForUser


class ManyEvents:
    """Reader trả nguyên danh sách, không cắt — như một adapter chưa có LIMIT."""

    def __init__(self, events):
        self.events = events

    def events_for_user(self, cdp_user_id):
        return list(self.events)

    def purchase_events(self, since_days=730):
        return []


def views(now, n):
    return [{"cdpUserId": "U", "eventName": "product_view", "productId": "A1",
             "timestamp": (now - timedelta(minutes=i + 1)).isoformat(), "eventGroupId": "T"} for i in range(n)]


def test_reader_path_reads_at_most_500_events(services):
    live, now = services["recommend"], services["now"]
    events = views(now, HISTORY_MAX_EVENTS + 20)
    rec = RecommendForUser(live.index, live.vectors, ManyEvents(events), live.popularity)
    assert HISTORY_MAX_EVENTS == 500
    assert rec("U", k=3, now=now)["diagnostics"]["eventsRead"] == 500


def test_injected_events_are_not_capped(services):
    live, now = services["recommend"], services["now"]
    events = views(now, HISTORY_MAX_EVENTS + 20)
    rec = RecommendForUser(live.index, live.vectors, ManyEvents([]), live.popularity)
    assert rec("U", k=3, now=now, events=events)["diagnostics"]["eventsRead"] == 520
