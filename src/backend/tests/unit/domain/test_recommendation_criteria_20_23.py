"""Tiêu chí 20–23 của hợp đồng search–recommendation (`docs/spec/hop-dong-tich-hop-search-recommendation.md`, mục
Recommendation): bốn lỗi "chạy được nhưng sai" — sai đơn vị thời gian của decay, quên chuẩn hoá vector khách, `tripFactor` không chạy.
Kiểm ở tầng domain (`build_profile`, `score_candidates`) với vector trực giao để đọc được trọng số từng event."""
from datetime import date, timedelta

import numpy as np
import pytest

from src.backend.app.domain.recommendation.profile import H_SHORT_DAYS, ResolvedEvent, build_profile, score_candidates

TODAY = date(2026, 10, 5)


def _weights(days_a: float, days_b: float) -> tuple[float, float]:
    """Hai event giống hệt (cùng loại, cùng trip) trên hai unit trực giao → thành phần của vector trip = trọng số sau decay
    (trước khi chuẩn hoá, tỉ lệ giữa hai thành phần không đổi)."""
    E = np.eye(2, dtype=np.float32)
    evs = [ResolvedEvent(0, "product_view", days_a, "T", "A"), ResolvedEvent(1, "product_view", days_b, "T", "B")]
    v = build_profile(evs, E, np.array(["hotel", "hotel"]), np.array(["Huế", "Huế"]), today=TODAY).trips["T"].vec
    return float(v[0]), float(v[1])


def test_20_decay_halves_every_30_days():
    newer, older = _weights(0.0, 30.0)
    assert H_SHORT_DAYS == 30.0
    assert newer / older == pytest.approx(2.0, abs=0.01)


def test_21_decay_is_measured_in_days_not_seconds():
    one_hour, one_day = _weights(1 / 24, 1.0)
    assert one_hour / one_day - 1 < 0.03            # Δt tính bằng giây sẽ cho chênh khổng lồ


def test_22_user_vectors_are_unit_norm():
    rng = np.random.default_rng(0)
    E = rng.normal(size=(6, 8)).astype(np.float32)
    E /= np.linalg.norm(E, axis=1, keepdims=True)
    tax = np.array(["hotel", "flight", "attraction", "hotel", "combo", "golf"])
    dest = np.array(["Huế", "Huế", "Huế", "Đà Lạt", "Đà Lạt", "Đà Lạt"])
    evs = [ResolvedEvent(0, "purchase", 40.0, "T1", "p0", TODAY - timedelta(days=30)),
           ResolvedEvent(1, "add_to_cart", 41.0, "T1", "p1"),
           ResolvedEvent(3, "product_view", 2.0, "_solo_p3", "p3"),
           ResolvedEvent(4, "search", 0.5, "_solo_p4", "p4")]
    p = build_profile(evs, E, tax, dest, today=TODAY)
    assert abs(float(np.linalg.norm(p.u_long)) - 1.0) < 1e-5
    for t in p.trips.values():
        assert abs(float(np.linalg.norm(t.vec)) - 1.0) < 1e-5
    _, u = score_candidates(p, E, np.zeros(len(E), dtype=np.float32))
    assert abs(float(np.linalg.norm(u)) - 1.0) < 1e-5     # vector dùng để chấm điểm (u_short của trip mở)


def test_23_ended_trip_gives_way_to_recent_view_destination():
    """Chuyến Nha Trang đã kết thúc 60 ngày trước + 1 view Đà Nẵng hôm qua → trip mở là Đà Nẵng, ứng viên Đà Nẵng xếp trên Nha Trang."""
    def unit(x, y):
        v = np.array([x, y], dtype=np.float32)
        return v / np.linalg.norm(v)
    E = np.stack([unit(1, 0), unit(0.9, 0.1),      # 0 khách sạn Nha Trang (đã mua), 1 điểm tham quan Nha Trang
                  unit(0, 1), unit(0.1, 0.9)])     # 2 khách sạn Đà Nẵng (đã xem), 3 điểm tham quan Đà Nẵng
    tax = np.array(["hotel", "attraction", "hotel", "attraction"])
    dest = np.array(["Nha Trang", "Nha Trang", "Đà Nẵng", "Đà Nẵng"])
    evs = [ResolvedEvent(0, "purchase", 65.0, "T-NT", "R0", TODAY - timedelta(days=60)),
           ResolvedEvent(2, "product_view", 1.0, "_solo_U2", "U2")]
    p = build_profile(evs, E, tax, dest, today=TODAY)
    assert p.trips["T-NT"].ended is True
    assert p.active_trip is not None and p.active_trip.destination == "Đà Nẵng"
    score, _ = score_candidates(p, E, np.zeros(len(E), dtype=np.float32))
    assert score[3] > score[1]                         # điểm tham quan Đà Nẵng > Nha Trang
    assert score[2] > score[0]
