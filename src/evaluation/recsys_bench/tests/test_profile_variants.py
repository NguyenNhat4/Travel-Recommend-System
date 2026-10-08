"""FR-REC-02 / AC-REC-02: purchase must survive repeated views in a trip.

Production regression is strict xfail until the engine is fixed. P1/P4 are
experimental implementations; passing them does not mean production is fixed.
"""
from datetime import date

import numpy as np
import pytest

from src.backend.app.domain.recommendation.profile import ResolvedEvent, build_profile
from src.evaluation.recsys_bench.theme_study.profile_variants import make_build_profile


TODAY = date(2026, 10, 8)
USING_DATE = date(2026, 10, 20)


def event(name, days, using_date=None):
    return ResolvedEvent(0, name, days, "trip-1", "hotel-1", using_date)


def build(builder, events):
    return builder(events, np.array([[1.0, 0.0]], dtype=np.float32),
                   np.array(["hotel"]), np.array(["Đà Nẵng"]), today=TODAY)


@pytest.mark.parametrize("builder", [
    pytest.param(build_profile, id="production-known-bug", marks=pytest.mark.xfail(
        strict=True, reason="Production drops purchase after three earlier views")),
    pytest.param(make_build_profile(cap_fix=True), id="P1"),
    pytest.param(make_build_profile(cap_fix=True, confidence=True, session=True), id="P4"),
])
@pytest.mark.parametrize("reverse_input", [False, True], ids=["oldest-first", "newest-first"])
def test_purchase_survives_three_views_with_trip_state(builder, reverse_input):
    # All events are older than the view-only 14-day window: only usingDate
    # can keep this purchased trip open.
    events = [event("product_view", d) for d in (24, 23, 22)]
    purchase = event("purchase", 21, USING_DATE)
    events.append(purchase)
    if reverse_input:
        events.reverse()
    profile = build(builder, events)
    trip = profile.trips["trip-1"]
    assert purchase in trip.events
    assert profile.bought_units == {0}
    assert trip.purchased_taxonomies == {"hotel"}
    assert trip.ends_on == USING_DATE
    assert not trip.ended
    assert profile.active_trip is trip
    assert profile.strategy == "cross_vertical"


@pytest.mark.parametrize("strong_first", [False, True])
def test_cap_fix_preserves_cart_and_purchase_and_caps_only_weak_events(strong_first):
    weak = [event("product_view", d) for d in (30, 29, 28, 27, 26, 25)]
    strong_days = (40, 39) if strong_first else (24, 23)
    cart = event("add_to_cart", strong_days[0], USING_DATE)
    purchase = event("purchase", strong_days[1], USING_DATE)
    profile = build(make_build_profile(cap_fix=True), [purchase, *weak, cart])
    retained = profile.trips["trip-1"].events
    assert cart in retained and purchase in retained
    assert sorted(e.days_ago for e in retained if e.event_name == "product_view") == [25, 26, 27]
    assert profile.n_events == 5
    assert profile.bought_units == {0}
    assert profile.trips["trip-1"].ends_on == USING_DATE


def test_cart_alone_keeps_using_date_without_marking_product_as_purchased():
    events = [event("product_view", d) for d in (24, 23, 22)]
    cart = event("add_to_cart", 21, USING_DATE)
    profile = build(make_build_profile(cap_fix=True), [*events, cart])
    trip = profile.trips["trip-1"]
    assert cart in trip.events
    assert trip.ends_on == USING_DATE
    assert profile.active_trip is trip
    assert profile.bought_units == set()
    assert trip.purchased_taxonomies == set()
    assert profile.strategy == "recent_activity"
