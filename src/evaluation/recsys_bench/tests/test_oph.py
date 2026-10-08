"""OPH-L bench modules (plan docs/plan/2026-10-09-recsys-cong-thuc-oph.md §5.1): layered profile, scorer, smoothed popularity,
registry parsing. DB-free; toy vectors in 2-3 dimensions."""
from datetime import date, datetime, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from src.backend.app.domain.recommendation import score_candidates as prod_score
from src.backend.app.domain.recommendation.popularity import Popularity, Purchase
from src.backend.app.domain.recommendation.profile import ResolvedEvent, build_profile
from src.evaluation.recsys_bench.theme_study import pop_smooth
from src.evaluation.recsys_bench.theme_study.layered_profile import SESSION_TRIP_ID, make_layered_build_profile
from src.evaluation.recsys_bench.theme_study.oph_scorer import Q_HIGH, Q_LOW, make_scorer
from src.evaluation.recsys_bench.theme_study.origin import infer_origin, mismatch
from src.evaluation.recsys_bench.theme_study.registry import expand, parse

TODAY = date(2026, 10, 8)
E = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [0.6, 0.8, 0.0]], dtype=np.float32)
TAX = np.array(["hotel", "hotel", "attraction", "flight"])
DEST = np.array(["Đà Nẵng", "Vũng Tàu", "Nha Trang", "Đà Nẵng"])


def ev(unit, name, days, trip, using=None):
    return ResolvedEvent(unit, name, days, trip, f"p{unit}", using)


def build(bp, events):
    return bp(events, E, TAX, DEST, today=TODAY)


# ---------------------------------------------------------------- layered profile

def test_layer_switches_off_returns_base_object_and_labels():
    state = {}
    seen = {}

    def base(*a, **k):
        seen["p"] = build_profile(*a, **k)
        return seen["p"]

    p = build(make_layered_build_profile(base, state), [ev(0, "purchase", 30, "g1", date(2026, 10, 20))])
    assert p is seen["p"]
    assert state["ctx0"] == state["ctx"] == "booked" and state["segment"] == "P1_frequent"


def booked_then_view():
    # booked hotel in Đà Nẵng (trip still to come), then a newer stray view of a Vũng Tàu hotel (production I-3)
    return [ev(0, "purchase", 10, "g1", date(2026, 10, 20)), ev(1, "product_view", 1, "_solo_p1")]


def test_production_lets_later_view_take_over_the_booked_trip():
    assert build(build_profile, booked_then_view()).active_trip.trip_id == "_solo_p1"


@pytest.mark.parametrize("flag", ["booked_first", "session_agg"])
def test_booked_trip_comes_first(flag):
    state = {}
    p = build(make_layered_build_profile(build_profile, state, **{flag: True}), booked_then_view())
    assert p.active_trip.trip_id == "g1" and p.strategy == "cross_vertical"
    assert state["ctx"] == "booked" and state["ctx0"] == "session"


def test_two_browse_trips_become_one_session_trip():
    state = {}
    events = [ev(0, "product_view", 3, "_solo_p0"), ev(3, "product_view", 2, "_solo_p3"), ev(1, "product_view", 1, "_solo_p1")]
    p = build(make_layered_build_profile(build_profile, state, session_agg=True), events)
    t = p.active_trip
    assert t.trip_id == SESSION_TRIP_ID and not t.purchased_taxonomies
    assert t.destination == "Đà Nẵng"                     # two of three views (weighted mode), not the newest one
    assert len(t.events) == 3 and abs(np.linalg.norm(t.vec) - 1) < 1e-6
    assert set(p.trips) == {"_solo_p0", "_solo_p3", "_solo_p1"} and p.n_events == 3
    assert state["ctx"] == "session"


def test_single_browse_trip_stays_the_real_trip():
    p = build(make_layered_build_profile(build_profile, {}, session_agg=True), [ev(1, "product_view", 1, "_solo_p1")])
    assert p.active_trip.trip_id == "_solo_p1"


@pytest.mark.parametrize("events, segment", [
    ([], "P4_no_history"),
    ([ev(0, "product_view", 40, "_solo_p0")], "P2_first_time"),
    ([ev(0, "purchase", 400, "g1", date(2025, 9, 20))], "P3_dormant"),
    ([ev(0, "purchase", 200, "g1", date(2026, 3, 20))], "P1_frequent"),
])
def test_segment_labels(events, segment):
    state = {}
    build(make_layered_build_profile(build_profile, state), events)
    assert state["segment"] == segment


def test_dormant_half_life_only_touches_dormant_users():
    old = [ev(0, "purchase", 400, "g1", date(2025, 9, 1)), ev(2, "purchase", 700, "g2", date(2024, 11, 1))]
    a = build(build_profile, old)
    b = build(make_layered_build_profile(build_profile, {}, dormant_hl_mult=3.0), old)
    assert not np.allclose(a.u_long, b.u_long)
    recent = [ev(0, "purchase", 100, "g1", date(2026, 7, 1)), ev(2, "purchase", 300, "g2", date(2025, 12, 20))]
    np.testing.assert_allclose(build(build_profile, recent).u_long,
                               build(make_layered_build_profile(build_profile, {}, dormant_hl_mult=3.0), recent).u_long)


# ---------------------------------------------------------------- origin + scorer

def toy_index(origins=("", "", "", "Hà Nội")):
    return SimpleNamespace(taxonomy=TAX, destination=DEST, attrs=SimpleNamespace(origin_city=np.array(origins, dtype=object)),
                           recommendable=np.ones(4, bool), available=np.ones(4, bool),
                           units=[SimpleNamespace(product_id=f"p{i}") for i in range(4)])


def space(glob=(0, 1, 2, 3)):
    return SimpleNamespace(glob=list(glob), local={g: i for i, g in enumerate(glob)})


def test_infer_origin_uses_newest_flight_event():
    idx = toy_index(("", "", "TP. Hồ Chí Minh", "Hà Nội"))
    idx.taxonomy = np.array(["hotel", "hotel", "flight", "flight"])
    events = [ev(2, "purchase", 50, "g1"), ev(3, "product_view", 5, "_solo_p3"), ev(0, "product_view", 1, "_solo_p0")]
    assert infer_origin(events, list(range(4)), idx) == ("Hà Nội", 3)
    assert infer_origin([ev(0, "product_view", 1, "x")], list(range(4)), idx) == (None, None)
    assert mismatch(list(range(4)), idx, "Hà Nội").tolist() == [False, False, True, False]
    assert not mismatch(list(range(4)), idx, None).any()


def test_scorer_all_off_equals_production():
    p = build(build_profile, booked_then_view())
    pop = np.array([0.1, 0.5, 0.0, 1.0], dtype=np.float32)
    state = {"space": space(), "events": booked_then_view()}
    s, u = make_scorer(state, toy_index())(p, E, pop)
    s0, u0 = prod_score(p, E, pop)
    np.testing.assert_array_equal(s, s0)
    np.testing.assert_array_equal(u, u0)


def test_scorer_none_branch_is_f14c_and_masks_wrong_origin():
    p = build(build_profile, [ev(0, "purchase", 200, "g1", date(2026, 3, 1)), ev(3, "purchase", 200, "g1", date(2026, 3, 1))])
    assert p.active_trip is None
    pop = np.array([0.2, 0.0, 0.0, 1.0], dtype=np.float32)
    state = {"space": space(), "events": [ev(3, "purchase", 200, "g1")], "segment_cfg": "P1_frequent"}
    s, _ = make_scorer(state, toy_index(), none_scorer="F14c")(p, E, pop)
    sem = np.clip((E @ p.u_long - Q_LOW) / (Q_HIGH - Q_LOW), 0, 1)
    np.testing.assert_allclose(s, 0.65 * sem + 0.35 * pop, rtol=1e-6)
    s2, _ = make_scorer(state, toy_index(("", "", "", "Huế")), none_scorer="F14c", origin_mode="pen")(p, E, pop)
    assert s2[3] == s[3]                                    # route 3 is the one the origin came from → not a mismatch
    idx = toy_index(("", "", "", "Huế"))
    state["events"] = []
    s3, _ = make_scorer(state, idx, none_scorer="F14c", origin_mode="pen")(p, E, pop)
    np.testing.assert_allclose(s3, s)                       # no flight history → origin unknown → nothing masked


def test_scorer_open_branch_origin_penalty_and_cart():
    events = [ev(0, "purchase", 10, "g1", date(2026, 10, 20)), ev(1, "add_to_cart", 2, "g1"),
              ev(3, "product_view", 3, "g1")]
    p = build(build_profile, events)
    pop = np.zeros(4, dtype=np.float32)
    idx = toy_index(("", "", "", "Hà Nội"))
    idx.attrs.origin_city = np.array(["", "", "", "Huế"], dtype=object)
    s0, _ = prod_score(p, E, pop)
    state = {"space": space(), "events": events}
    s, _ = make_scorer(state, idx, origin_mode="pen", w_origin=0.3, w_cart=0.05)(p, E, pop)
    assert state["origin"] == "Huế"                         # newest flight event is unit 3 itself → no mismatch
    np.testing.assert_allclose(s, s0 + 0.05 * np.array([0, 1, 0, 0]), rtol=1e-6)
    # unit 2 becomes a route from Đà Lạt: the user's origin (Huế, from unit 3) differs → penalised, or masked
    idx2 = toy_index(("", "", "Đà Lạt", "Huế"))
    idx2.taxonomy = np.array(["hotel", "hotel", "flight", "flight"])
    state = {"space": space(), "events": events}
    s2, _ = make_scorer(state, idx2, origin_mode="pen", w_origin=0.3)(p, E, pop)
    assert s2[2] == pytest.approx(s0[2] - 0.3) and s2[3] == pytest.approx(s0[3])
    s3, _ = make_scorer(state, idx2, origin_mode="mask")(p, E, pop)
    assert s3[2] == -np.inf


# ---------------------------------------------------------------- smoothed popularity

NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


def purchases():
    day = 86400
    t0 = NOW.timestamp()
    return [Purchase(0, "Đà Nẵng", t0 - 10 * day, None), Purchase(0, "Đà Nẵng", t0 - 100 * day, None),
            Purchase(1, "Vũng Tàu", t0 - 5 * day, None), Purchase(3, "Đà Nẵng", t0 - 60 * day, None)]


@pytest.mark.parametrize("dest", [None, "Đà Nẵng"])
def test_box_90_alpha_0_matches_production(dest):
    pop = Popularity(purchases(), set(DEST), now=NOW)
    assert pop_smooth.smoothed_scores(pop, toy_index(), dest, None, 0.0, box=90) == pop.unit_scores(dest)


def test_shrinkage_formula():
    pop = Popularity(purchases(), set(DEST), now=NOW)
    out = pop_smooth.smoothed_scores(pop, toy_index(), None, 90.0, 1.0)
    n0 = 2 ** (-10 / 90) + 2 ** (-100 / 90)
    n1, n3 = 2 ** (-5 / 90), 2 ** (-60 / 90)
    m_dn_hotel = n0 / 1                        # (Đà Nẵng, hotel) = {0}; (Vũng Tàu, hotel) = {1}; (Đà Nẵng, flight) = {3}
    raw = {0: n0 + m_dn_hotel, 1: n1 + n1, 3: n3 + n3}
    mx = max(raw.values())
    assert out == pytest.approx({k: v / mx for k, v in raw.items()})


def test_install_only_changes_the_no_trip_branch():
    pop = Popularity(purchases(), set(DEST), now=NOW)
    state = {"ctx": "booked"}
    prod = pop.unit_scores()
    restore = pop_smooth.install(toy_index(), state, 90.0, 1.0)
    try:
        assert pop.unit_scores() == prod
        state["ctx"] = "none"
        assert pop.unit_scores() != prod
        state["ctx"] = "cold"
        assert pop.unit_scores() == prod
    finally:
        restore()
    state["ctx"] = "none"
    assert pop.unit_scores() == prod


# ---------------------------------------------------------------- registry

def test_aliases_expand_to_the_plan_ladder():
    assert expand("O5") == ["P0", "F0", "orig:pen:0.3", "book", "sess", "cart:0.05"]
    assert expand("V2p") == ["P0", "F0", "F14c", "destCap2", "oph"]
    c = parse("N3")
    assert (c.confidence, c.explore_fill, c.none_scorer, c.dest_cap, c.pop_h, c.pop_alpha, c.dormant_hl_mult) == \
           (True, True, "F14c", 2, 90.0, 1.0, 3.0)
    assert parse("B0+noExplore").explore_fill is False and parse("P0legacy+F0").confidence is False
    assert c.w_pop_by_segment == {"P3_dormant": 0.5}
    assert parse("B0").needs_scorer is False and parse("V0p").needs_scorer is True


@pytest.mark.parametrize("bad", ["P0+F0+nope", "B0+orig:x", "B1p+dormPop:0.5"])
def test_bad_config_names_fail_fast(bad):
    with pytest.raises(ValueError):
        parse(bad)


# ---------------------------------------------------------------- paired_ci additions (p, one-sided bound, Holm)

def test_identical_configs_have_p_one_and_shift_has_small_p():
    from src.evaluation.recsys_bench.theme_study import paired_ci as PC
    a = {f"u{i}": float(i % 2) for i in range(200)}
    same = PC.paired_ci(a, dict(a), boot=500)
    assert same["p"] == 1.0 and same["lo90_1s"] == 0.0
    better = {k: 1.0 for k in a}
    r = PC.paired_ci(a, better, boot=500)
    assert r["p"] == 0.0 and r["lo90_1s"] > 0


def test_holm_step_down_matches_hand_example():
    from src.evaluation.recsys_bench.theme_study import paired_ci as PC
    rows = [{"baseline": "A", "config": "B", "stratum": s, "metric": "hit@4", "seed": "all", "p": p}
            for s, p in (("s1", 0.01), ("s2", 0.04), ("s3", 0.03))]
    fam = [{"baseline": "A", "config": "B", "stratum": s, "metric": "hit@4"} for s in ("s1", "s2", "s3", "s4")]
    out = {r["stratum"]: r for r in PC.holm(rows, fam)}
    # sorted p: 0.01 (×3 = 0.03, reject at 0.05/3), 0.03 (×2 = 0.06, 0.03 > 0.025 → stop), 0.04 (×1, kept monotone 0.06)
    assert out["s1"]["reject"] and out["s1"]["pHolm"] == pytest.approx(0.03)
    assert not out["s3"]["reject"] and out["s3"]["pHolm"] == pytest.approx(0.06)
    assert not out["s2"]["reject"] and out["s2"]["pHolm"] == pytest.approx(0.06)
    assert out["s4"]["missing"]


def test_split_rows_adds_stratum_copies():
    from src.evaluation.recsys_bench.theme_study import paired_ci as PC
    rows = [{"config": "A", "stratum": "temporal", "uid": "u1", "ctx0": "booked", "hit@4": 1.0}]
    out = PC.split_rows(rows, ["ctx0"])
    assert [r["stratum"] for r in out] == ["temporal", "temporal|ctx0=booked"]
