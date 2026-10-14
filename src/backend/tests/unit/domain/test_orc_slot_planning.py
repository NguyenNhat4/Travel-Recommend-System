"""Real arithmetic and timing constraints; no model or catalog service needed."""

from copy import deepcopy

from src.backend.app.domain.itinerary.draft_validation import plan_slots
from src.backend.tests.fakes.orc_tools import product


def args(**fields):
    return {
        "destination": "Huế",
        "start_date": "2026-10-25",
        "days": 3,
        "adults": 3,
        "children": 0,
        "schedule": [
            {"day": 1, "morning": "p1", "afternoon": "p2"},
            {"day": 2, "morning": "p3", "afternoon": "p4"},
            {"day": 3, "morning": "p5", "afternoon": "p6"},
        ],
        "stays": [{"room_ref": "p7"}],
        **fields,
    }


def products():
    rows = {
        f"p{i}": product(
            str(i), price=100_000, durationMinutes=120, openingHours="08:00-22:00"
        )
        for i in range(1, 7)
    }
    rows["p7"] = product(
        "r",
        "hotel",
        price=900_000,
        unit="PER_NIGHT",
        parentProductId="h",
        priceAdults=2,
        maxOccupancy=2,
    )
    return rows


def codes(rows):
    return {r["code"] for r in rows}


def test_three_days_two_nights_total_people_rooms_and_cost_lines():
    result = plan_slots(args(children=1), products())
    assert result["violations"] == []
    assert result["nights"] == 2 and result["stays"][0]["rooms"] == 2
    assert result["stays"][0]["check_out"] == "2026-10-27"
    assert result["costs"]["estimated_total_vnd"] == 3_600_000 + 2_400_000
    assert sum(line["subtotal_vnd"] for line in result["costs"]["lines"]) == 6_000_000
    assert result["plan_days"][0]["activities"][1]["start_minute"] == 780


def test_one_day_without_stay_and_full_day_product_charged_once():
    rows = {"p1": product("day", durationMinutes=480, openingHours="08:00-18:00")}
    result = plan_slots(
        args(
            days=1, schedule=[{"day": 1, "morning": "p1", "afternoon": "p1"}], stays=[]
        ),
        rows,
    )
    assert result["violations"] == [] and len(result["plan_days"][0]["activities"]) == 1
    assert result["costs"]["estimated_total_vnd"] == 300_000 and result["nights"] == 0


def test_two_stays_split_nights_and_explicit_rooms():
    rows = products()
    rows["p8"] = product(
        "other",
        "hotel",
        price=500_000,
        unit="PER_NIGHT",
        parentProductId="other",
        priceAdults=3,
        maxOccupancy=3,
    )
    result = plan_slots(
        args(
            stays=[
                {"room_ref": "p7", "from_day": 1, "to_day": 2, "rooms": 3},
                {"room_ref": "p8", "from_day": 2, "to_day": 3},
            ]
        ),
        rows,
    )
    assert result["nights"] == 2 and [s["rooms"] for s in result["stays"]] == [3, 1]
    assert result["costs"]["known_subtotal_vnd"] == 1_800_000 + 2_700_000 + 500_000


def test_missing_price_never_becomes_zero_and_budget_is_warning_only():
    rows = products()
    rows["p2"]["unitPrice"] = None
    rows["p2"]["attributes"]["ticketed"] = True
    result = plan_slots(args(budget_vnd=1), rows)
    assert (
        result["costs"]["estimated_total_vnd"] is None
        and result["costs"]["over_by_vnd"] is None
    )
    assert result["costs"]["unpriced_refs"] == ["p2"] and "PRICE_UNKNOWN" in codes(
        result["warnings"]
    )
    result = plan_slots(args(budget_vnd=500_000), products())
    assert not result["violations"] and "OVER_TRIP_BUDGET" in codes(result["warnings"])


def test_unknown_price_capacity_uses_occupancy_with_warning_and_room_limit():
    rows = products()
    rows["p7"]["attributes"].pop("priceAdults")
    rows["p7"]["attributes"]["maxOccupancy"] = 8
    result = plan_slots(args(adults=8), rows)
    assert result["stays"][0]["rooms"] == 1 and "PRICE_CAPACITY_UNKNOWN" in codes(
        result["warnings"]
    )
    rows["p7"]["attributes"]["maxOccupancy"] = 1
    assert "TOO_MANY_ROOMS" in codes(plan_slots(args(adults=10), rows)["violations"])


def test_opening_hours_shift_inside_chosen_slot_without_moving_slot():
    rows = products()
    rows["p1"]["attributes"]["openingHours"] = "10:00-22:00"
    result = plan_slots(args(), rows)
    assert result["plan_days"][0]["activities"][0]["start_minute"] == 600
    rows["p1"]["attributes"]["openingHours"] = "13:00-22:00"
    value = args(schedule=[{"day": 1, "morning": "p1"}, {"day": 2}, {"day": 3}])
    result = plan_slots(value, rows)
    issue = next(i for i in result["violations"] if i["code"] == "SLOT_DOES_NOT_FIT")
    assert (
        "afternoon" in issue["fix_hint"]
        and result["plan_days"][0]["activities"][0]["product_ref"] == "p1"
    )


def test_airport_buffers_and_fixed_times_are_checked():
    rows = products()
    rows["p8"] = product(
        "out",
        "flight",
        originCity="Hà Nội",
        destinationCity="Huế",
        departureAt="2026-10-25T09:00:00+07:00",
        arrivalAt="2026-10-25T10:00:00+07:00",
    )
    rows["p9"] = product(
        "back",
        "flight",
        destination="Hà Nội",
        originCity="Huế",
        destinationCity="Hà Nội",
        departureAt="2026-10-27T16:00:00+07:00",
    )
    result = plan_slots(args(flights={"outbound": "p8", "return": "p9"}), rows)
    assert "SLOT_DOES_NOT_FIT" in codes(result["violations"])
    result = plan_slots(
        args(fixed_times=[{"day": 1, "slot": "morning", "start_minute": 420}]),
        products(),
    )
    assert "SLOT_DOES_NOT_FIT" in codes(result["violations"])


def test_savings_respect_party_price_basis_and_locked_refs():
    rows = products()
    candidates = deepcopy(rows)
    candidates["p8"] = product(
        "cheap",
        "hotel",
        price=800_000,
        unit="PER_NIGHT",
        parentProductId="h",
        priceAdults=1,
        maxOccupancy=1,
    )
    assert not plan_slots(args(), rows, candidates)[
        "savings"
    ]  # lower unit price costs more for the whole party
    candidates["p8"]["attributes"].update(priceAdults=3, maxOccupancy=3)
    savings = plan_slots(args(), rows, candidates)["savings"]
    assert savings[0]["save_vnd"] == 2_000_000
    assert plan_slots(args(locked_refs=["p7"]), rows, candidates)["savings"] == []
    assert "LOCKED_REF_MISSING" in codes(
        plan_slots(args(locked_refs=["p9"]), rows, candidates)["violations"]
    )


def test_unknown_duration_and_combo_are_disclosed_or_rejected():
    rows = products()
    rows["p1"]["attributes"].pop("durationMinutes")
    result = plan_slots(args(), rows)
    assert "TIMING_ESTIMATED" in codes(result["warnings"])
    rows["p1"]["taxonomy"] = "combo"
    assert "COMBO_OUTSIDE_PLAN" in codes(plan_slots(args(), rows)["violations"])


def test_suitable_slots_identify_impossible_show_and_full_day():
    from src.backend.app.domain.itinerary.draft_validation import suitable_slots

    assert (
        suitable_slots(product("show", durationMinutes=120, openingHours="17:00-18:30"))
        == []
    )
    assert suitable_slots(
        product("park", durationMinutes=480, openingHours="08:00-22:00")
    ) == ["all_day"]


def test_sparse_full_day_requires_orc_to_choose_more_when_candidates_exist():
    rows = {
        "p1": product("a", durationMinutes=120),
        "p2": product("b", durationMinutes=120),
    }
    value = args(days=1, schedule=[{"day": 1, "morning": "p1"}], stays=[])
    result = plan_slots(value, {"p1": rows["p1"]}, rows)
    assert "TOO_FEW_ACTIVITIES" in codes(result["violations"])
    assert len(result["plan_days"][0]["activities"]) == 1  # no automatic padding
    assert not plan_slots(value, {"p1": rows["p1"]})["violations"]
