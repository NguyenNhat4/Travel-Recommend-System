"""Kiểm lịch orc phác (AC-AGT-02/04): không trần hai hoạt động, 0 đêm hợp lệ, vượt ngân sách chỉ là cảnh báo."""
from collections import Counter
from copy import deepcopy

from src.backend.app.domain.itinerary.draft_validation import check_draft, cost_mode
from src.backend.tests.fakes.orc_tools import product


def activity(ref, start, end, timing="estimate"):
    return {"product_ref": ref, "start_minute": start, "end_minute": end, "timing_source": timing,
            "assumption": "Ước tính 1 giờ" if timing == "estimate" else None}


def draft(*days, **fields):
    value = {"destination": "Huế", "start_date": "2026-10-24", "days": len(days), "adults": 2, "children": 0,
             "origin": None, "plan_days": [{"day_index": i + 1, "activities": list(acts)} for i, acts in enumerate(days)],
             "stays": [], "flights": [], "trip_budget_vnd": None, "free_only": False, "locked_refs": [],
             "optimize": "none"}
    return {**value, **fields}


def codes(issues):
    return {issue["code"] for issue in issues}


def test_day_trip_with_four_activities_has_zero_nights_and_no_cap():
    products = {f"p{i}": product(f"a{i}", openingHours="07:00-18:00") for i in range(4)}
    result = check_draft(draft([activity(f"p{i}", 480 + 120 * i, 570 + 120 * i) for i in range(4)]), products)
    assert result["feasibility"] == "provisional" and result["violations"] == []
    assert result["nights"] == 0 and len(result["plan_days"][0]["activities"]) == 4
    assert result["costs"]["estimated_total_vnd"] == 4 * 100_000 * 2


def test_g01_over_budget_is_a_warning_with_exact_amount():
    products = {"p1": product("a", price=1_150_000)}
    result = check_draft(draft([activity("p1", 480, 600)], trip_budget_vnd=2_000_000), products)
    assert result["feasibility"] != "infeasible"
    assert result["costs"] == {"known_subtotal_vnd": 2_300_000, "estimated_total_vnd": 2_300_000,
                               "unpriced_refs": [], "trip_budget_vnd": 2_000_000, "over_by_vnd": 300_000,
                               "budget_status": "over"}
    assert "OVER_TRIP_BUDGET" in codes(result["warnings"])


def test_g03_missing_price_is_unknown_not_free():
    products = {"p1": product("a", price=500_000), "p2": product("b", price=None)}
    result = check_draft(draft([activity("p1", 480, 540), activity("p2", 600, 660)], trip_budget_vnd=2_000_000),
                         products)
    costs = result["costs"]
    assert costs["known_subtotal_vnd"] == 1_000_000 and costs["estimated_total_vnd"] is None
    assert costs["over_by_vnd"] is None and costs["budget_status"] == "unknown" and costs["unpriced_refs"] == ["p2"]
    assert cost_mode(products["p2"]) == "unknown"


def test_g04_zero_budget_with_paid_item_is_over_not_unset():
    result = check_draft(draft([activity("p1", 480, 540)], trip_budget_vnd=0), {"p1": product("a")})
    assert result["costs"]["budget_status"] == "over" and result["costs"]["over_by_vnd"] == 200_000


def test_free_only_rejects_paid_and_unknown_price_but_accepts_evidence_of_free():
    products = {"p1": product("a", price=0), "p2": product("b", price=None, ticketed=False),
                "p3": product("c", price=None), "p4": product("d")}
    result = check_draft(draft([activity(f"p{i}", 360 + 90 * i, 420 + 90 * i) for i in range(1, 5)],
                               free_only=True), products)
    assert next(v for v in result["violations"] if v["code"] == "NOT_FREE")["refs"] == ["p3", "p4"]


def test_overlap_full_day_and_opening_hours_are_violations_not_silent_drops():
    products = {"p1": product("a", openingHours="08:00-17:00"), "p2": product("b", openingHours="08:00-17:00")}
    result = check_draft(draft([activity("p1", 480, 1020), activity("p2", 600, 1080)]), products)
    assert {"TIME_OVERLAP", "OUTSIDE_OPENING_HOURS"} <= codes(result["violations"])
    assert result["feasibility"] == "infeasible"
    assert [a["product_ref"] for a in result["plan_days"][0]["activities"]] == ["p1", "p2"]


def test_stay_nights_rooms_and_price_follow_catalog_basis():
    products = {"p1": product("a"), "h": product("room", "hotel", price=1_000_000, unit="PER_NIGHT", priceAdults=2)}
    value = draft([activity("p1", 600, 660)], [], adults=3,
                  stays=[{"product_ref": "h", "check_in": "2026-10-24", "check_out": "2026-10-26"}])
    result = check_draft(value, products)
    assert result["nights"] == 2
    assert result["costs"]["known_subtotal_vnd"] == 3 * 100_000 + 1_000_000 * 2 * 2


def test_flight_dates_and_airport_buffers():
    outbound = product("vn1", "flight", destination="Huế", price=1_000_000, originCity="Hà Nội",
                       destinationCity="Huế", departureAt="2026-10-24T07:45:00+07:00",
                       arrivalAt="2026-10-24T09:00:00+07:00")
    back = product("vn2", "flight", destination="Hà Nội", price=900_000, originCity="Huế", destinationCity="Hà Nội",
                   departureAt="2026-10-25T16:00:00+07:00")
    products = {"p1": product("a"), "p2": product("b"), "f1": outbound, "f2": back}
    flights = [{"product_ref": "f1", "role": "outbound"}, {"product_ref": "f2", "role": "return"}]
    tight = check_draft(draft([activity("p1", 600, 660)], [activity("p2", 720, 900)], origin="Hà Nội",
                              flights=flights), products)
    assert next(v for v in tight["violations"] if v["code"] == "AIRPORT_BUFFER")["refs"] == ["f1", "f2"]
    ok = check_draft(draft([activity("p1", 660, 720)], [activity("p2", 600, 660)], origin="Hà Nội",
                           flights=flights), products)
    assert ok["violations"] == []
    wrong_day = check_draft(draft([activity("p1", 660, 720)], [], [], origin="Hà Nội", flights=flights), products)
    assert "FLIGHT_DATE" in codes(wrong_day["violations"])


def test_optimisation_keeps_the_exact_products_and_locked_days():
    points = [(16.46, 107.59), (16.40, 107.70), (16.47, 107.60)]
    products = {f"p{i}": product(f"a{i}", latitude=lat, longitude=lng) for i, (lat, lng) in enumerate(points)}
    acts = [activity(f"p{i}", 480 + 120 * i, 540 + 120 * i) for i in range(3)]
    result = check_draft(draft(acts, optimize="reorder_within_day"), products)
    order = [a["product_ref"] for a in result["plan_days"][0]["activities"]]
    assert Counter(order) == Counter(["p0", "p1", "p2"]) and order != ["p0", "p1", "p2"]
    assert result["changes"] and [a["start_minute"] for a in result["plan_days"][0]["activities"]] == [480, 600, 720]
    locked = check_draft(draft(deepcopy(acts), optimize="reorder_within_day", locked_refs=["p1"]), products)
    assert [a["product_ref"] for a in locked["plan_days"][0]["activities"]] == ["p0", "p1", "p2"]
    assert "OPTIMIZATION_UNAVAILABLE" in codes(locked["warnings"])


def test_plan_without_any_product_is_not_a_plan():
    result = check_draft(draft([], []), {})
    assert result["feasibility"] == "infeasible" and codes(result["violations"]) == {"EMPTY_PLAN"}
