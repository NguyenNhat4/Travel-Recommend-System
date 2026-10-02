"""Mọi giá trị `Profile.strategy` engine trả ra đều phải thuộc enum `Strategy` của contract
(`schemas/common.yaml`); thiếu giá trị nào là response `/recommendations` của nhánh đó hỏng validate.
"""
from datetime import datetime, timedelta

import numpy as np
import pytest

from src.backend.app.application.itinerary.contracts import enum_values, valid
from src.backend.app.domain.recommendation.profile import DORMANT_AFTER_DAYS, Profile, Trip


def trip(trip_id: str, age_days: float, purchased: set[str] | None = None) -> Trip:
    return Trip(trip_id=trip_id, events=[], vec=np.zeros(4, dtype=np.float32), age_days=age_days,
                purchased_taxonomies=purchased or set(), destination="Nha Trang")


def profile(*trips: Trip, active: Trip | None = None, n_events: int = 0) -> Profile:
    return Profile(trips={t.trip_id: t for t in trips}, u_long=np.zeros(4, dtype=np.float32),
                   active_trip=active, n_events=n_events)


# Một Profile cho mỗi nhánh của Profile.strategy (profile.py).
_OPEN, _BOUGHT = trip("open", 5), trip("bought", 5, {"hotel"})
_RECENT, _OLD = trip("recent", DORMANT_AFTER_DAYS - 1), trip("old", DORMANT_AFTER_DAYS + 1)
BRANCHES = {
    "cross_vertical": profile(_BOUGHT, active=_BOUGHT, n_events=2),
    "cold_start_content": profile(_OPEN, active=_OPEN, n_events=2),
    "recent_activity": profile(_OPEN, active=_OPEN, n_events=3),
    "long_term": profile(_RECENT, _OLD, n_events=5),
    "dormant": profile(_OLD, n_events=5),
    "popular": profile(),
}


@pytest.mark.parametrize("expected", sorted(BRANCHES))
def test_every_profile_branch_is_a_contract_strategy(expected):
    strategy = BRANCHES[expected].strategy
    assert strategy == expected
    assert strategy in enum_values("Strategy")


def _events(now: datetime, *rows: tuple) -> list[dict]:
    out = []
    for name, pid, days, group, *using in rows:      # phần tử thứ 5 (tuỳ chọn): usingDate = now + N ngày
        e = {"eventName": name, "productId": pid, "eventGroupId": group,
             "timestamp": (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        if using:
            e["usingDate"] = (now + timedelta(days=using[0])).strftime("%Y-%m-%d")
        out.append(e)
    return out


@pytest.mark.parametrize("expected, rows", [
    # Chuyến đã đóng (không `usingDate`, quá ACTIVE_TRIP_MAX_AGE_DAYS = 14 ngày) nhưng chưa quá ngưỡng dormant.
    ("long_term", [("product_view", "A1", 100, "T9"), ("product_view", "G1", 100, "T9"),
                   ("purchase", "C1", 99, "T9")]),
    # Chuyến đang mở, mới một event, chưa mua.
    ("cold_start_content", [("product_view", "A1", 5, "T8")]),
    # FR-REC-02 (2026-10-02): mua 10 ngày trước nhưng usingDate đã qua 3 ngày → chuyến đã đi xong → không còn cross_vertical.
    ("long_term", [("purchase", "R1", 10, "T7", -3), ("product_view", "A1", 11, "T7"), ("product_view", "G1", 12, "T7")]),
    # Mua 120 ngày trước, usingDate còn 10 ngày nữa → chuyến sắp đi vẫn là trip mở → cross_vertical.
    ("cross_vertical", [("purchase", "R1", 120, "T6", 10), ("product_view", "A1", 121, "T6")]),
])
def test_engine_response_for_new_strategies_validates(services, expected, rows):
    now = services["now"]
    r = services["recommend"]("P9", k=3, now=now, events=_events(now, *rows))
    # Route bổ sung cdpUserId và latencyMs trước khi trả.
    body = {**r, "cdpUserId": "P9", "diagnostics": {**r["diagnostics"], "latencyMs": 0}}
    assert r["strategy"] == expected and r["recommendations"]
    assert valid("RecommendationResponse", body)
