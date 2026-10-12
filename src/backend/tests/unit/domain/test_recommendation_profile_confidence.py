"""P2 — độ tin cậy chuyến trong u_long và purchase / add_to_cart không bị cap lặp (09/10/2026, PR-A; FR-REC-01).

Port từ `src/evaluation/recsys_bench/tests/test_profile_variants.py` (bản đo P2_confidence 08/10): một lượt xem lẻ nặng 0,2,
một lần mua 1,0, năm lượt xem cùng món 0,6 (cap 3 view) rồi clamp 1,0 khi đủ; u_long nghiêng về chuyến đã mua; vector
chuyến mở không đổi."""
from datetime import date

import numpy as np

from src.backend.app.domain.recommendation.profile import (
    CAP_EXEMPT_EVENTS, H_LONG_DAYS, MAX_REPEAT_PER_TRIP, ResolvedEvent, build_profile, explain,
)

TODAY = date(2026, 9, 21)


def _world():
    E = np.eye(4, dtype=np.float32)
    return E, np.array(["hotel", "flight", "attraction", "golf"]), np.array(["Nha Trang", "Nha Trang", "Phú Quốc", "Phú Quốc"])


def test_trip_confidence_is_capped_sum_of_event_weights():
    E, tax, dest = _world()
    p = build_profile([
        ResolvedEvent(0, "product_view", 100.0, "V", "H1"),                                   # 0,2
        ResolvedEvent(1, "purchase", 100.0, "B", "F1", date(2026, 6, 1)),                     # 1,0
        *[ResolvedEvent(2, "product_view", 100.0 - i, "W", "A1") for i in range(5)],          # cap 3 view → 3 × 0,2 = 0,6
        ResolvedEvent(3, "add_to_cart", 100.0, "C", "G1", date(2026, 6, 1)),                  # 0,5
        ResolvedEvent(3, "add_to_cart", 99.0, "C", "G1", date(2026, 6, 1)),                   # + 0,5 + 0,2 → clamp 1,0
        ResolvedEvent(3, "product_view", 98.0, "C", "G1"),
    ], E, tax, dest, today=TODAY)
    assert p.trips["V"].confidence == 0.2 and p.trips["B"].confidence == 1.0
    assert np.isclose(p.trips["W"].confidence, 0.6) and p.trips["C"].confidence == 1.0
    assert len(p.trips["W"].events) == MAX_REPEAT_PER_TRIP                                   # view vẫn bị cap 3


def test_u_long_leans_towards_bought_trip_not_single_view():
    """Cùng tuổi: một lượt xem lẻ (0,2) và một lần mua (1,0) → u_long gần vector chuyến mua hơn 5 lần theo đóng góp."""
    E, tax, dest = _world()
    p = build_profile([ResolvedEvent(0, "product_view", 50.0, "V", "H1"),
                       ResolvedEvent(1, "purchase", 50.0, "B", "F1", date(2026, 6, 1))], E, tax, dest, today=TODAY)
    assert p.active_trip is None
    assert np.isclose(p.u_long[1] / p.u_long[0], 5.0, rtol=1e-4)
    # trước P2 hai chuyến nặng bằng nhau sau chuẩn hoá (tỷ lệ 1,0)
    because = explain(p, 1, E)
    assert because[0]["productId"] == "F1" and because[0]["contribution"] > 0.8


def test_strong_events_are_not_dropped_by_repeat_cap():
    E, tax, dest = _world()
    views = [ResolvedEvent(0, "product_view", 10.0 - i * 0.1, "T", "R1") for i in range(MAX_REPEAT_PER_TRIP)]
    cart = ResolvedEvent(0, "add_to_cart", 2.0, "T", "R1", date(2026, 10, 2))
    buy = ResolvedEvent(0, "purchase", 1.0, "T", "R1", date(2026, 10, 2))
    p = build_profile(views + [cart, buy], E, tax, dest, today=TODAY)
    kept = [e.event_name for e in p.trips["T"].events]
    assert kept.count("product_view") == MAX_REPEAT_PER_TRIP and "add_to_cart" in kept and "purchase" in kept
    assert set(CAP_EXEMPT_EVENTS) == {"purchase", "add_to_cart"}
    # view thứ 4 cùng unit vẫn bị cap dù đứng sau purchase
    p2 = build_profile(views + [buy, ResolvedEvent(0, "product_view", 0.5, "T", "R1")], E, tax, dest, today=TODAY)
    assert [e.event_name for e in p2.trips["T"].events].count("product_view") == MAX_REPEAT_PER_TRIP


def test_open_trip_vector_and_strategy_unchanged_by_confidence():
    E, tax, dest = _world()
    evs = [ResolvedEvent(0, "product_view", 1.0, "T", "H1"), ResolvedEvent(1, "purchase", 60.0, "B", "F1", date(2026, 6, 1))]
    p = build_profile(evs, E, tax, dest, today=TODAY)
    assert p.active_trip is not None and p.active_trip.trip_id == "T" and p.strategy == "cold_start_content"
    assert np.allclose(p.active_trip.vec, E[0])                                              # vec chuyến không nhân confidence
    # explain theo chuyến mở không đổi; long_term=True phân rã theo u_long (có hệ số tuổi × confidence)
    assert [b["productId"] for b in explain(p, 0, E)] == ["H1"]
    lt = {b["productId"]: b["contribution"] for b in explain(p, 1, E, long_term=True)}
    assert lt == {"F1": 1.0}
    w_view, w_buy = 0.2 * 2 ** (-1.0 / H_LONG_DAYS), 1.0 * 2 ** (-60.0 / H_LONG_DAYS)
    assert np.isclose(p.u_long[1] / p.u_long[0], w_buy / w_view, rtol=1e-4)
