"""Chặng bay của lịch trình (AC-AGT-02): luật chọn vé, tổng tiền và grounding (`domain/itinerary/flights.py`)."""
from src.backend.app.domain.itinerary import flights as rules
from src.backend.app.domain.itinerary.planning import (cost_breakdown, day_windows, price_plan, summary, totals,
                                                       validate_plan)

INTENT = {"destination": "Nha Trang", "origin": "Hà Nội", "startDate": "2026-10-15", "days": 3,
          "party": {"type": "FAMILY_WITH_KIDS", "adults": 2, "children": 1}, "budget": None, "interests": [], "pace": None}


def flight(pid, day, *, destination="Nha Trang", price=1_000_000, clock="09:00", nonstop=True, trip="oneWay",
           back=None, available=True, arrive=None, back_clock=None):
    attributes = {"level": "flight", "tripType": trip, "departureAt": f"{day}T{clock}:00+07:00",
                  "departureTimeLocal": clock, "airline": "VietJet Air", "flightNumber": f"VJ{pid}"}
    if arrive:
        attributes["arrivalAt"] = arrive if "T" in arrive else f"{day}T{arrive}:00+07:00"
    if nonstop:
        attributes["nonstop"] = True
    if back:
        attributes["returnDate"] = back
    if back and back_clock:
        attributes["returnFlight"] = {"departureAt": f"{back}T{back_clock}:00+07:00", "flightNumber": f"VJ{pid}R"}
    return {"productId": pid, "name": f"Chuyến {pid}", "taxonomy": "flight", "destination": destination,
            "unitPrice": price, "currency": "VND", "priceUnit": "PER_PERSON", "available": available,
            "availableFrom": day, "availableTo": day, "attributes": attributes}


def options(outbound=(), inbound=()):
    return {"status": None, "origin": "Hà Nội", "outbound": list(outbound), "return": list(inbound)}


def test_round_trip_matching_both_dates_wins_over_cheaper_one_way_pair():
    chosen, reason = rules.choose_flights(options(
        [flight("rt", "2026-10-15", price=3_000_000, trip="roundTrip", back="2026-10-17", nonstop=False),
         flight("o1", "2026-10-15", price=500_000)],
        [flight("b1", "2026-10-17", destination="Hà Nội", price=500_000)]), INTENT)
    assert reason is None
    assert [(leg["product"]["productId"], leg["direction"], leg["date"], leg["returnDate"]) for leg in chosen] == \
        [("rt", "ROUND_TRIP", "2026-10-15", "2026-10-17")]
    assert chosen[0]["passengers"] == 3


def test_round_trip_with_other_return_date_is_not_used():
    chosen, _ = rules.choose_flights(options(
        [flight("rt", "2026-10-15", trip="roundTrip", back="2026-10-20"), flight("o1", "2026-10-15")],
        [flight("b1", "2026-10-17", destination="Hà Nội")]), INTENT)
    assert [leg["direction"] for leg in chosen] == ["OUTBOUND", "RETURN"]


def test_nonstop_then_price_then_sensible_hour():
    outbound = [flight("stop", "2026-10-15", price=100_000, nonstop=False),
                flight("late", "2026-10-15", price=500_000, clock="20:00"),
                flight("early", "2026-10-15", price=500_000, clock="06:00"),
                flight("dear", "2026-10-15", price=900_000, clock="05:00")]
    inbound = [flight("back-early", "2026-10-17", destination="Hà Nội", clock="06:00"),
               flight("back-late", "2026-10-17", destination="Hà Nội", clock="21:00")]
    chosen, reason = rules.choose_flights(options(outbound, inbound), INTENT)
    assert reason is None
    assert [leg["product"]["productId"] for leg in chosen] == ["early", "back-late"]


def test_flights_on_other_days_unpriced_or_sold_out_are_skipped():
    chosen, reason = rules.choose_flights(options(
        [flight("wrong-day", "2026-10-16"), flight("no-price", "2026-10-15", price=None),
         flight("sold-out", "2026-10-15", available=False)]), INTENT)
    assert (chosen, reason) == ([], rules.NO_FLIGHT_ON_DATES)


def test_only_one_leg_found_is_shown_with_its_reason():
    chosen, reason = rules.choose_flights(options([flight("o1", "2026-10-15")]), INTENT)
    assert [leg["direction"] for leg in chosen] == ["OUTBOUND"]
    assert reason == rules.ONE_WAY_ONLY


def test_known_status_is_passed_through():
    assert rules.choose_flights({"status": rules.NO_ROUTE}, INTENT) == ([], rules.NO_ROUTE)


def test_skip_reasons():
    assert rules.skip_reason({**INTENT, "origin": None}, {}) == rules.NO_ORIGIN
    assert rules.skip_reason(INTENT, {"exclude_taxonomies": ["flight"]}) == rules.EXCLUDED
    assert rules.skip_reason({**INTENT, "origin": "nha trang"}, {}) == rules.SAME_CITY
    assert rules.skip_reason({**INTENT, "days": 1}, {}) == rules.DAY_TRIP
    assert rules.skip_reason({**INTENT, "days": 1}, {"require_flight": True}) is None
    assert rules.skip_reason(INTENT, {}) is None
    assert {rules.EXCLUDED, rules.DAY_TRIP, rules.SAME_CITY} == rules.SILENT_REASONS


def plan_with(legs):
    return {"days": [{"day": 1, "slots": []}, {"day": 2, "slots": []}, {"day": 3, "slots": []}],
            "flights": [{**leg, "product": summary(leg["product"])} for leg in legs],
            "estimatedTotal": None, "budgetStatus": "UNKNOWN", "currency": "VND", "bookableCount": len(legs)}


def test_ticket_price_times_passengers_counts_in_the_total_and_budget():
    legs, _ = rules.choose_flights(options([flight("o1", "2026-10-15", price=1_000_000)],
                                           [flight("b1", "2026-10-17", destination="Hà Nội", price=800_000)]), INTENT)
    plan = plan_with(legs)
    assert totals(plan, INTENT) == (5_400_000, "NO_BUDGET")
    # Vé không bị bỏ vì vượt ngân sách: lịch trình báo vượt.
    assert totals(plan, {**INTENT, "budget": 5_000_000}) == (5_400_000, "OVER_BUDGET")


def test_the_cost_breakdown_splits_the_total_into_flights_stays_and_activities():
    # "Ngân sách dự tính" (user-flow §4.2, chốt 2026-10-09): ba nhóm từ giá sản phẩm, cộng đúng bằng tổng.
    legs, _ = rules.choose_flights(options([flight("o1", "2026-10-15", price=1_000_000)],
                                           [flight("b1", "2026-10-17", destination="Hà Nội", price=800_000)]), INTENT)
    plan = plan_with(legs)
    hotel = {"productId": "h1", "name": "Venus", "taxonomy": "hotel", "unitPrice": 959_000, "priceUnit": "PER_NIGHT",
             "currency": "VND", "available": True, "attributes": {}}
    ticket = {"productId": "t1", "name": "Cáp Treo Hòn Thơm", "taxonomy": "attraction", "unitPrice": 850_000,
              "priceUnit": "PER_PERSON", "currency": "VND", "available": True, "attributes": {}}
    free = {"productId": "f1", "name": "Bãi Sao", "taxonomy": "attraction", "unitPrice": None, "currency": "VND",
            "available": True, "attributes": {"ticketed": False}}
    plan["stays"] = [{"product": hotel, "nights": 2, "fromNight": 1}]
    plan["days"][0]["slots"] = [{"product": ticket}, {"product": free}]
    price_plan(plan, INTENT)
    assert plan["costBreakdown"] == {"flights": 5_400_000, "stays": 1_918_000, "activities": 2_550_000}
    assert sum(plan["costBreakdown"].values()) == plan["estimatedTotal"]
    assert "total" not in validate_plan(plan, {}, {}, INTENT, {}, {})
    plan["costBreakdown"]["stays"] += 1
    assert "total" in validate_plan(plan, {}, {}, INTENT, {}, {})


def test_no_cost_breakdown_when_a_price_is_unknown():
    plan = plan_with([])
    plan["stays"] = [{"product": {"productId": "h1", "taxonomy": "hotel", "unitPrice": None, "priceUnit": "PER_NIGHT",
                                  "attributes": {}}, "nights": 2, "fromNight": 1}]
    assert cost_breakdown(plan, INTENT) is None
    price_plan(plan, INTENT)
    assert plan["estimatedTotal"] is None and "costBreakdown" not in plan


def test_flights_are_grounded_against_the_looked_up_flights_only():
    out, back = flight("o1", "2026-10-15"), flight("b1", "2026-10-17", destination="Hà Nội")
    found = options([out], [back])
    legs, _ = rules.choose_flights(found, INTENT)
    plan = price_plan(plan_with(legs), INTENT)
    candidates = rules.flight_candidates(found)
    # Chặng về đến Hà Nội và bay ngày cuối: không vi phạm luật điểm đến của lịch trình.
    assert validate_plan(plan, {}, {}, INTENT, {}, candidates) == []
    assert validate_plan(plan, {}, {}, INTENT, {}, {}) == ["grounding"]
    plan["flights"][0]["product"]["unitPrice"] = 1
    assert "grounding" in validate_plan(plan, {}, {}, INTENT, {}, candidates)


def test_summary_keeps_the_flight_card_fields():
    kept = summary(flight("o1", "2026-10-15"))["attributes"]
    assert {"airline", "flightNumber", "departureAt", "departureTimeLocal", "nonstop", "tripType"} <= set(kept)
    assert "level" not in kept


# --- Xếp lịch theo giờ bay (AC-AGT-02, chốt 2026-10-07) ----------------------------------------------------------

def legs_for(outbound=(), inbound=()):
    legs, _ = rules.choose_flights(options(outbound, inbound), INTENT)
    return legs


def test_late_landing_leaves_the_first_day_with_only_the_transfer():
    # Bay 19:50, hạ cánh 21:05: + 90 phút là 22:35, không còn buổi nào trong ngày 1.
    windows = day_windows(INTENT, legs_for([flight("o1", "2026-10-15", clock="19:50", arrive="21:05")]))
    assert windows[1] == {"times": [], "full_day": False, "transfers": [("EVENING", "ARRIVAL")]}
    assert 2 not in windows and 3 not in windows


def test_morning_landing_keeps_the_afternoon_of_the_first_day():
    # Hạ cánh 09:30 + 90 phút = 11:00: buổi sáng (08:00) đã qua, buổi chiều (13:30) còn.
    windows = day_windows(INTENT, legs_for([flight("o1", "2026-10-15", clock="08:15", arrive="09:30")]))
    assert windows[1] == {"times": ["AFTERNOON"], "full_day": False, "transfers": [("MORNING", "ARRIVAL")]}


def test_evening_take_off_keeps_morning_and_afternoon_of_the_last_day_but_no_full_day():
    # Cất cánh 19:45 − 150 phút = 17:15: buổi chiều kết thúc 17:00 nên còn; buổi tối (đến 21:00) thì không.
    windows = day_windows(INTENT, legs_for(
        [flight("o1", "2026-10-15", clock="06:00", arrive="07:00")],
        [flight("b1", "2026-10-17", destination="Hà Nội", clock="19:45", arrive="21:00")]))
    assert windows[3] == {"times": ["MORNING", "AFTERNOON"], "full_day": False, "transfers": [("EVENING", "DEPARTURE")]}
    # Hạ cánh 07:00 + 90 phút = 08:30: buổi sáng bắt đầu 08:00 nên mất buổi sáng.
    assert windows[1]["times"] == ["AFTERNOON"]


def test_early_landing_does_not_limit_the_first_day():
    windows = day_windows(INTENT, legs_for([flight("o1", "2026-10-15", clock="05:00", arrive="06:15")]))
    assert windows[1] == {"times": ["MORNING", "AFTERNOON"], "full_day": True, "transfers": [("MORNING", "ARRIVAL")]}


def test_round_trip_reads_the_return_take_off_from_return_flight():
    windows = day_windows(INTENT, legs_for([flight("rt", "2026-10-15", trip="roundTrip", back="2026-10-17",
                                                   clock="06:00", arrive="07:10", back_clock="12:00")]))
    # 12:00 − 150 phút = 09:30: không còn buổi nào trong ngày về.
    assert windows[3] == {"times": [], "full_day": False, "transfers": [("NOON", "DEPARTURE")]}


def test_landing_after_midnight_belongs_to_the_next_day():
    windows = day_windows(INTENT, legs_for([flight("o1", "2026-10-15", clock="23:00",
                                                   arrive="2026-10-16T00:30:00+07:00")]))
    assert windows[1] == {"times": [], "full_day": False, "transfers": []}
    assert windows[2]["transfers"] == [("MORNING", "ARRIVAL")]
    assert windows[2]["times"] == ["MORNING", "AFTERNOON"]  # 00:30 + 90 phút = 02:00, trước buổi sáng


def test_a_flight_without_times_does_not_limit_any_day():
    plain = flight("o1", "2026-10-15")
    plain["attributes"].pop("departureAt")
    plain["attributes"].pop("departureTimeLocal")
    assert day_windows(INTENT, legs_for([plain])) == {}
    assert day_windows(INTENT, []) == {}


def test_validate_plan_rejects_an_activity_scheduled_before_the_landing():
    from src.backend.app.domain.itinerary.planning import render_proposal
    late = flight("o1", "2026-10-15", clock="19:50", arrive="21:05")
    legs = legs_for([late])
    activity = {"productId": "a1", "name": "Bà Nà", "taxonomy": "attraction", "destination": "Nha Trang",
                "unitPrice": 100_000, "currency": "VND", "priceUnit": "PER_PERSON", "available": True, "attributes": {}}
    candidates, sources = {"a1": activity}, {"a1": "search"}
    proposal = {"stay_id": None, "slots": [{"day": 1, "time": "MORNING", "note_kind": "VISIT", "activity_type": None,
                                             "product_id": "a1"}]}
    plan = render_proposal(proposal, candidates, sources, INTENT)
    plan["flights"] = [{**leg, "product": summary(leg["product"])} for leg in legs]
    price_plan(plan, INTENT)
    found = rules.flight_candidates(options([late]))
    assert validate_plan(plan, candidates, sources, INTENT, {}, found) == ["schedule"]
    plan["days"][0]["slots"], plan["days"][1]["slots"] = [], plan["days"][0]["slots"]
    assert validate_plan(plan, candidates, sources, INTENT, {}, found) == []


def _located(product, lat, lng, origin=None):
    product["attributes"].update({"latitude": lat, "longitude": lng})
    if origin:
        product["attributes"].update({"originLatitude": origin[0], "originLongitude": origin[1]})
    return product


PQC, SGN = (10.169783, 103.99353), (10.8188, 106.652)


def test_airports_come_from_the_arrival_of_the_outbound_and_the_origin_of_the_return():
    going = {"product": _located(flight("o", "2026-10-15"), *PQC, origin=SGN), "direction": "OUTBOUND"}
    coming = {"product": _located(flight("b", "2026-10-17"), *SGN, origin=PQC), "direction": "RETURN"}
    assert rules.airports([going, coming]) == (PQC, PQC)


def test_a_round_trip_lands_and_leaves_at_the_same_airport():
    leg = {"product": _located(flight("rt", "2026-10-15", trip="roundTrip"), *PQC, origin=SGN), "direction": "ROUND_TRIP"}
    assert rules.airports([leg]) == (PQC, PQC)


def test_one_direction_only_is_used_for_both_ends():
    coming = {"product": _located(flight("b", "2026-10-17"), *SGN, origin=PQC), "direction": "RETURN"}
    assert rules.airports([coming]) == (PQC, PQC)


def test_no_flight_or_no_coordinates_gives_no_airport():
    assert rules.airports([]) == (None, None)
    assert rules.airports([{"product": flight("o", "2026-10-15"), "direction": "OUTBOUND"}]) == (None, None)
