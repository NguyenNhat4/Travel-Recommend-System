"""FR-REC-02 (chốt 2026-10-01): trip đang mở = chưa kết thúc theo `usingDate`; không có `usingDate` thì theo tuổi event.
Chuyến đã đi xong không còn loại taxonomy / khoá điểm đến; chuyến sắp đi (mua từ lâu) vẫn là trip mở."""
from datetime import date, datetime, timezone

import numpy as np

from src.backend.app.domain.recommendation.profile import (ACTIVE_TRIP_MAX_AGE_DAYS, ENGINE_RULES_VERSION, ResolvedEvent,
                                                            build_profile, local_today, parse_using_date, trip_is_open)

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


def test_repeat_cap_does_not_shorten_trip_or_drop_purchases():
    """Cap `MAX_REPEAT_PER_TRIP` chỉ giới hạn trọng số vector: purchase thứ 4 cùng unit (bị cap) vẫn quyết định ngày kết thúc,
    tuổi trip và món đã mua (review PR M6, 01/10)."""
    E, tax, dest = _world()
    # 4 vé cùng chuyến bay (unit 1) mua cách nhau; vé cuối (mới nhất, bị cap) là chặng về 25/09 — chuyến chưa xong tại 21/09
    legs = [ResolvedEvent(1, "purchase", d, "T3", "F1", date(2026, 9, 15)) for d in (12.0, 11.0, 10.0)]
    back = [ResolvedEvent(1, "purchase", 2.0, "T3", "F1", date(2026, 9, 25))]
    p = build_profile(legs + back, E, tax, dest, today=TODAY)
    assert len(p.trips["T3"].events) == 3                                # vector vẫn chỉ gồm 3 event cũ nhất
    assert p.trips["T3"].ends_on == date(2026, 9, 25) and p.trips["T3"].age_days == 2.0
    assert p.active_trip is not None and p.active_trip.trip_id == "T3" and p.strategy == "cross_vertical"
    assert p.active_trip.purchased_taxonomies == {"flight"} and 1 in p.bought_units
    # 3 view rồi mới purchase cùng unit: purchase bị cap nhưng vẫn là món đã mua / taxonomy bị loại
    views = [ResolvedEvent(0, "product_view", d, "T4", "R1") for d in (6.0, 5.0, 4.0)]
    buy = [ResolvedEvent(0, "purchase", 3.0, "T4", "R1", date(2026, 10, 2))]
    p2 = build_profile(views + buy, E, tax, dest, today=TODAY)
    assert 0 in p2.bought_units and p2.active_trip.purchased_taxonomies == {"hotel"} and p2.strategy == "cross_vertical"


def test_local_today_and_parse_using_date():
    # 18:30 UTC 20/09 = 01:30 giờ VN 21/09 → hôm nay là 21/09 (ngày UTC vẫn là 20/09)
    assert local_today(datetime(2026, 9, 20, 18, 30, tzinfo=timezone.utc)) == date(2026, 9, 21)
    assert local_today(datetime(2026, 9, 20, 16, 59, tzinfo=timezone.utc)) == date(2026, 9, 20)
    assert local_today(datetime(2026, 9, 20, 18, 30)) == date(2026, 9, 21)           # naive → coi là UTC
    assert parse_using_date("2026-09-21") == date(2026, 9, 21)
    assert parse_using_date("2026-09-21T10:00:00+07:00") == date(2026, 9, 21)
    assert parse_using_date(None) is None and parse_using_date("") is None and parse_using_date("hôm qua") is None
    assert parse_using_date("2026-13-01") is None
    assert parse_using_date(20260921) == date(2026, 9, 21)      # số → chuỗi "20260921" là ISO dạng cơ bản, vẫn đọc được
