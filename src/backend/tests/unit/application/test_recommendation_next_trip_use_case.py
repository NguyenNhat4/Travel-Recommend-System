"""PR-B (FR-REC-04, chốt 09/10): tầng application — lệch tag model → công thức cũ + WARNING một lần; request khoá điểm đến →
không áp cap 2 món / điểm đến. Catalog giả (`tests/conftest.py`), khách P3 không có chuyến mở."""
import logging

from src.backend.app.application.recommendation import RecommendForUser
from src.backend.app.application.recommendation import use_cases as UC


def _rec(services, **kw):
    return RecommendForUser(services["index"], services["vectors"], services["recommend"].cdp, services["recommend"].popularity, **kw)


def _ids(r):
    return [x["productId"] for x in r["recommendations"]]


def test_model_mismatch_falls_back_to_old_formula_and_warns_once(services, caplog):
    assert services["index"].model_version.startswith("fake@")                 # catalog giả không khớp tag calibrate
    UC._CALIBRATION_WARNED.clear()
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        on = _rec(services, max_per_destination=None)("P3", k=5, now=services["now"])
        _rec(services, max_per_destination=None)("P3", k=5, now=services["now"])
    off = _rec(services, next_trip_scoring=False, max_per_destination=None)("P3", k=5, now=services["now"])
    assert on["strategy"] == "dormant" and _ids(on) == _ids(off)
    assert sum("next_trip_scoring" in r.getMessage() for r in caplog.records) == 1


def test_destination_cap_only_without_locked_destination(services):
    now = services["now"]
    free = _rec(services, max_per_destination=None)("P3", k=6, now=now)
    capped = _rec(services, max_per_destination=1)("P3", k=6, now=now)
    dests = [x["destination"] for x in capped["recommendations"]]
    assert len(dests) == len(set(dests)) and len(_ids(free)) >= len(_ids(capped))
    locked = _rec(services, max_per_destination=1)("P3", k=6, now=now, destination="Nha Trang")
    locked_free = _rec(services, max_per_destination=None)("P3", k=6, now=now, destination="Nha Trang")
    assert _ids(locked) == _ids(locked_free)                                    # khoá điểm đến → không áp cap
