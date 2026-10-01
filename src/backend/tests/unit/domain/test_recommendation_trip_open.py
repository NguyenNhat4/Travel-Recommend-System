"""FR-REC-02 (chốt 2026-10-02): trip đang mở = chưa kết thúc theo `usingDate`; không có `usingDate` thì theo tuổi event.
Chuyến đã đi xong không còn loại taxonomy / khoá điểm đến; chuyến sắp đi (mua từ lâu) vẫn là trip mở."""
from datetime import date

import numpy as np

from src.backend.app.domain.recommendation.profile import (ACTIVE_TRIP_MAX_AGE_DAYS, ENGINE_RULES_VERSION, ResolvedEvent,
                                                            build_profile, trip_is_open)

TODAY = date(2026, 9, 21)


def test_trip_is_open_rules():
    assert trip_is_open(5, None, TODAY) is True and trip_is_open(ACTIVE_TRIP_MAX_AGE_DAYS + 1, None, TODAY) is False
    assert trip_is_open(5, date(2026, 9, 20), TODAY) is False          # kết thúc hôm qua → không mở dù mới 5 ngày
    assert trip_is_open(5, date(2026, 9, 21), TODAY) is True           # kết thúc hôm nay vẫn mở (usingDate >= hôm nay)
    assert trip_is_open(300, date(2026, 10, 5), TODAY) is True         # mua từ lâu, sắp đi → mở
    assert trip_is_open(5, date(2026, 9, 20), None) is True            # không có today → luật cũ theo tuổi
    assert ENGINE_RULES_VERSION == "2026-10-02-trip-ended"


def _world():
    E = np.eye(3, dtype=np.float32)
    return E, np.array(["hotel", "flight", "attraction"]), np.array(["Nha Trang", "Nha Trang", "Đà Nẵng"])


def test_build_profile_uses_using_date_to_close_and_open_trips():
    E, tax, dest = _world()
    ended = [ResolvedEvent(0, "purchase", 5.0, "T1", "R1", date(2026, 9, 18))]          # mua 5 ngày trước, đã đi xong 18/09
    p = build_profile(ended, E, tax, dest, today=TODAY)
    assert p.trips["T1"].ends_on == date(2026, 9, 18) and p.trips["T1"].ended is True
    assert p.active_trip is None and p.strategy == "long_term"                      # không còn cross_vertical
    upcoming = [ResolvedEvent(0, "purchase", 120.0, "T2", "R1", date(2026, 10, 5))]   # mua 120 ngày trước, đi 05/10
    p2 = build_profile(upcoming, E, tax, dest, today=TODAY)
    assert p2.active_trip is not None and p2.active_trip.trip_id == "T2" and p2.strategy == "cross_vertical"
    assert p2.trips["T2"].ended is False
    # view lẻ không có usingDate: theo tuổi như cũ
    view = [ResolvedEvent(2, "product_view", 1.0, "_solo_A1", "A1")]
    p3 = build_profile(ended + view, E, tax, dest, today=TODAY)
    assert p3.active_trip.trip_id == "_solo_A1" and p3.strategy == "cold_start_content"
    # không truyền today → luật cũ (T1 mới 5 ngày vẫn mở)
    assert build_profile(ended, E, tax, dest).active_trip.trip_id == "T1"
