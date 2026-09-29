"""CDP sập khi đọc lịch sử: gợi ý vẫn trả `popular` thay vì lỗi (hop-dong-tich-hop-cdp.md §6,
`paths/recommendations.yaml`): because rỗng, diagnostics.coldStart true, eventsUsed 0, chỉ lỗi CDP mới log WARNING.
"""
import logging

import pytest
from fastapi.testclient import TestClient

from src.backend.app.api.deps import optional_principal
from src.backend.app.application.ports.cdp_client import CdpUnavailableError
from src.backend.app.application.recommendation import RecommendForUser
from src.backend.app.main import app
from src.backend.tests.contract.test_booking_contract import assert_contract
from src.backend.tests.fakes.booking import PRINCIPAL


class DownCdp:
    """`CdpHistoryReader` luôn lỗi ở đường đọc theo request."""

    def __init__(self, error: Exception):
        self.error = error
        self.calls = 0

    def events_for_user(self, cdp_user_id):
        self.calls += 1
        raise self.error

    def purchase_events(self, since_days=730):
        raise AssertionError("RecommendForUser không đọc lô purchase")


def outage() -> CdpUnavailableError:
    error = CdpUnavailableError("CDP history read failed")
    error.__cause__ = ConnectionRefusedError("connection refused")
    return error


def recommend_with(services, cdp) -> RecommendForUser:
    live = services["recommend"]
    return RecommendForUser(live.index, live.vectors, cdp, live.popularity)


@pytest.mark.parametrize("destination", [None, "Nha Trang"])
def test_cdp_outage_falls_back_to_popular(services, destination):
    cdp = DownCdp(outage())
    r = recommend_with(services, cdp)("P1", k=3, now=services["now"], destination=destination)
    assert cdp.calls == 1
    assert r["strategy"] == "popular" and r["destination"] == destination
    assert r["diagnostics"]["coldStart"] is True and r["diagnostics"]["eventsUsed"] == 0
    assert r["recommendations"] and all(x["because"] == [] for x in r["recommendations"])
    assert {"generatedAt", "modelVersion"} <= r.keys()
    # Giống hệt khách chưa đăng nhập: cùng một đường lui.
    guest = services["recommend"](None, k=3, now=services["now"], destination=destination)
    assert r == guest


def test_cdp_outage_logs_warning_without_user_id(services, caplog):
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        recommend_with(services, DownCdp(outage()))("VP0000001", k=3, now=services["now"])
    warnings = [rec.getMessage() for rec in caplog.records if rec.levelno == logging.WARNING]
    assert any("recommend.cdp_unavailable" in m and "ConnectionRefusedError" in m for m in warnings)
    assert "VP0000001" not in caplog.text


def test_other_errors_are_not_swallowed(services):
    with pytest.raises(ValueError):
        recommend_with(services, DownCdp(ValueError("bug")))("P1", k=3, now=services["now"])


def test_guest_and_explicit_events_do_not_read_cdp(services):
    cdp = DownCdp(outage())
    recommend = recommend_with(services, cdp)
    assert recommend(None, k=3, now=services["now"])["strategy"] == "popular"
    assert recommend("P1", k=3, now=services["now"], events=[])["strategy"] == "popular"
    assert cdp.calls == 0


def test_route_answers_200_popular_when_cdp_is_down(services):
    cdp = DownCdp(outage())
    saved = getattr(app.state, "recommend", None)
    app.state.recommend = recommend_with(services, cdp)
    app.dependency_overrides[optional_principal] = lambda: PRINCIPAL
    try:
        r = TestClient(app).get("/api/v1/recommendations", params={"k": 3})
    finally:
        app.dependency_overrides.pop(optional_principal, None)
        app.state.recommend = saved
    assert r.status_code == 200
    body = assert_contract(r, "/recommendations", "get")
    assert cdp.calls == 1 and body["cdpUserId"] == PRINCIPAL.cdp_user_id
    assert body["strategy"] == "popular" and body["diagnostics"]["coldStart"] is True
    assert body["diagnostics"]["eventsUsed"] == 0
    assert all(x["because"] == [] for x in body["recommendations"])
