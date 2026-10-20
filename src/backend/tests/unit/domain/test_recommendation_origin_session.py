"""FR-REC-02 / FR-REC-04 (chốt 2026-10-09, đề xuất `update-archive/2026-10-09-recsys-diem-xuat-phat-va-phien-xem.md`):
chuyến ảo gộp các lượt xem gần đây; chuyến bay sai điểm xuất phát bị hạ (có chuyến mở) hoặc loại (không có chuyến mở)."""
from datetime import date

import numpy as np

from src.backend.app.domain.recommendation.profile import (
    SESSION_TRIP_ID, W_ORIGIN, ResolvedEvent, ScoreContext, build_profile, infer_origin, score_candidates,
)

TODAY = date(2026, 10, 9)
E = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [0.6, 0.8, 0.0]], dtype=np.float32)
TAX = np.array(["hotel", "hotel", "flight", "flight"])
DEST = np.array(["Nha Trang", "Vũng Tàu", "Đà Nẵng", "Đà Nẵng"])
ORIGIN = np.array(["", "", "Hà Nội", "TP. Hồ Chí Minh"], dtype=object)


def view(unit, days, trip=None):
    return ResolvedEvent(unit, "product_view", days, trip or f"_solo_p{unit}_{days}", f"p{unit}")


def test_several_open_browse_trips_become_one_session_trip_at_the_most_viewed_destination():
    # 3 lượt xem Nha Trang (cũ hơn) và 1 lượt Vũng Tàu mới nhất: trước 09/10 khoá Vũng Tàu, nay khoá Nha Trang
    events = [view(0, 5), view(0, 4.5, "_solo_x"), view(0, 4, "_solo_y"), view(1, 1)]
    p = build_profile(events, E, TAX, DEST, today=TODAY)
    t = p.active_trip
    assert t.trip_id == SESSION_TRIP_ID and t.destination == "Nha Trang" and not t.purchased_taxonomies
    assert SESSION_TRIP_ID not in p.trips and p.n_events == 4 and len(t.events) == 4
    assert abs(float(np.linalg.norm(t.vec)) - 1.0) < 1e-6 and p.strategy == "recent_activity"


def test_single_browse_trip_and_booked_trip_are_unchanged():
    p = build_profile([view(1, 1)], E, TAX, DEST, today=TODAY)
    assert p.active_trip.trip_id.startswith("_solo_p1")
    booked = ResolvedEvent(0, "purchase", 10, "T1", "R1", date(2026, 10, 20))
    p2 = build_profile([booked, view(1, 1), view(1, 2, "_solo_z")], E, TAX, DEST, today=TODAY)
    assert p2.active_trip.trip_id == "T1"            # chuyến đã đặt vẫn đứng trước, không gộp lượt xem


def test_infer_origin_takes_newest_flight_event():
    events = [ResolvedEvent(2, "purchase", 50, "T", "F1"), view(3, 3), view(0, 1)]
    assert infer_origin(events, TAX, ORIGIN) == "TP. Hồ Chí Minh"
    assert infer_origin([view(0, 1)], TAX, ORIGIN) is None


def test_wrong_origin_flight_is_penalised_with_open_trip_and_masked_without():
    pop = np.zeros(4, dtype=np.float32)
    ctx = ScoreContext(taxonomy=TAX, origin_city=ORIGIN, origin="Hà Nội")
    open_p = build_profile([view(2, 1)], E, TAX, DEST, today=TODAY)
    base, _ = score_candidates(open_p, E, pop)
    s, _ = score_candidates(open_p, E, pop, ctx)
    np.testing.assert_allclose(s, base - W_ORIGIN * np.array([0, 0, 0, 1]), rtol=1e-6)
    closed_p = build_profile([ResolvedEvent(2, "purchase", 300, "T", "F1", date(2025, 12, 20))], E, TAX, DEST, today=TODAY)
    assert closed_p.active_trip is None
    s2, _ = score_candidates(closed_p, E, pop, ctx)
    assert s2[3] == -np.inf and np.isfinite(s2[:3]).all()
    s3, _ = score_candidates(closed_p, E, pop, ScoreContext(taxonomy=TAX, origin_city=ORIGIN, origin=None))
    assert np.isfinite(s3).all()                     # chưa có lịch sử chuyến bay → không áp dụng
