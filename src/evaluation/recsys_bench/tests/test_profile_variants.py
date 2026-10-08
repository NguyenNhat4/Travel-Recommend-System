"""FR-REC-02 / AC-REC-02: purchase must survive repeated views in a trip.

"Production" here means `build_profile` in `src/backend/app/domain/recommendation/profile.py` on this branch, which is the
08/10/2026 production engine (`release-mvp-v2` @ `6f77e80`, including `9b703ba`: trip age, `ends_on` and purchased units are
computed over *every* event, so `MAX_REPEAT_PER_TRIP` only caps vector weight).

Split in two on 2026-10-08 (plan WP1, `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md`) because the single original case
bundled two different expectations and therefore stayed xfail on an engine that had already fixed the business half:

- `test_purchase_state_survives_repeat_cap`  — trip state (bought units, taxonomies, `ends_on`, open trip, strategy).
  Production **passes**; this is a regression guard for `9b703ba`.
- `test_strong_events_weight_trip_vector`    — the purchase also carries weight in the trip vector. Production still fails
  (strict xfail): the 4th+ repeat of a unit is dropped from `trip.events` even when it is a purchase. Fixing it is plan WP5.3.

P1/P4 are experimental implementations in `theme_study/profile_variants.py`; passing them does not mean production is fixed.
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


BUILDERS = [
    pytest.param(build_profile, id="production"),
    pytest.param(make_build_profile(cap_fix=True), id="P1"),
    pytest.param(make_build_profile(confidence=True), id="P2"),
    pytest.param(make_build_profile(cap_fix=True, confidence=True, session=True), id="P4"),
]


def _repeat_capped_trip(builder, reverse_input):
    """Three views of the same unit then a purchase of it — the purchase is the 4th repeat, so it is the one
    `MAX_REPEAT_PER_TRIP` drops. Every event is older than the 14-day view-only window, so only `usingDate` can keep
    this trip open: if the purchase is lost, the trip silently stops being an open trip."""
    events = [event("product_view", d) for d in (24, 23, 22)]
    purchase = event("purchase", 21, USING_DATE)
    events.append(purchase)
    if reverse_input:
        events.reverse()
    return build(builder, events), purchase


@pytest.mark.parametrize("builder", BUILDERS)
@pytest.mark.parametrize("reverse_input", [False, True], ids=["oldest-first", "newest-first"])
def test_purchase_state_survives_repeat_cap(builder, reverse_input):
    profile, _ = _repeat_capped_trip(builder, reverse_input)
    trip = profile.trips["trip-1"]
    assert profile.bought_units == {0}
    assert trip.purchased_taxonomies == {"hotel"}
    assert trip.ends_on == USING_DATE
    assert not trip.ended
    assert profile.active_trip is trip
    assert profile.strategy == "cross_vertical"


#: Only the `cap_fix` variants claim to keep strong events in the vector. Production and P2 share the production cap, so
#: both drop the purchase — P2 is listed as xfail too, to document that P2 alone does not fix this half.
CAP_XFAIL = pytest.mark.xfail(
    strict=True, reason="plan WP5.3: the repeat cap still drops the 4th+ event from trip.events even for a purchase")


@pytest.mark.parametrize("builder", [
    pytest.param(build_profile, id="production", marks=CAP_XFAIL),
    pytest.param(make_build_profile(confidence=True), id="P2", marks=CAP_XFAIL),
    pytest.param(make_build_profile(cap_fix=True), id="P1"),
    pytest.param(make_build_profile(cap_fix=True, confidence=True, session=True), id="P4"),
])
@pytest.mark.parametrize("reverse_input", [False, True], ids=["oldest-first", "newest-first"])
def test_strong_events_weight_trip_vector(builder, reverse_input):
    """A purchase must also contribute to the trip vector, not only to the trip's state: `W_TYPE["purchase"] = 1.0` is
    five times a view, so dropping it leaves the trip pointing at whatever the user merely browsed."""
    profile, purchase = _repeat_capped_trip(builder, reverse_input)
    assert purchase in profile.trips["trip-1"].events


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
