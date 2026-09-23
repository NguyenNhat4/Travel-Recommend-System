from datetime import datetime, timedelta, timezone

import jwt
import pytest
import json
from types import SimpleNamespace
from unittest.mock import patch

from src.backend.app.api.v1.routes.recommendations import recommendations
from src.backend.app.core.security import JwtError, optional_cdp_user_id


SECRET = "unit-test-secret-at-least-32-bytes-long"


def token(**overrides):
    payload = {
        "sub": "web-user-1",
        "cdp_user_id": "VP0000001",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    payload.update(overrides)
    return jwt.encode(payload, SECRET, algorithm="HS256")


def test_optional_jwt_returns_none_for_anonymous_request():
    assert optional_cdp_user_id(None, secret="", algorithm="HS256") is None


def test_optional_jwt_verifies_and_returns_cdp_user_id():
    assert optional_cdp_user_id(
        f"Bearer {token()}", secret=SECRET, algorithm="HS256"
    ) == "VP0000001"


@pytest.mark.parametrize(
    ("authorization", "secret", "code", "status"),
    [
        # Token sinh lúc chạy test, không lúc import: bộ test dài hơn hạn 5 phút sẽ làm token hết hạn.
        (lambda: "Basic abc", SECRET, "INVALID_TOKEN", 401),
        (lambda: f"Bearer {token()}", "wrong-secret-at-least-32-bytes-long", "INVALID_TOKEN", 401),
        (lambda: f"Bearer {token(exp=datetime.now(timezone.utc) - timedelta(seconds=1))}", SECRET,
         "TOKEN_EXPIRED", 401),
        (lambda: f"Bearer {token(cdp_user_id='')}", SECRET, "INVALID_TOKEN", 401),
        (lambda: f"Bearer {token()}", "", "INTERNAL_ERROR", 500),
    ],
    ids=["basic-scheme", "wrong-secret", "expired", "empty-cdp-user-id", "missing-secret"],
)
def test_optional_jwt_fails_closed(authorization, secret, code, status):
    with pytest.raises(JwtError) as caught:
        optional_cdp_user_id(authorization(), secret=secret, algorithm="HS256")
    assert (caught.value.code, caught.value.status_code) == (code, status)


def recommendation_request(calls):
    def recommend(cdp_user_id, **kwargs):
        calls.append((cdp_user_id, kwargs))
        return {
            "strategy": "popular", "destination": kwargs.get("destination"),
            "nextVertical": None, "recommendations": [],
            "diagnostics": {"eventsUsed": 0, "coldStart": True, "excludedVerticals": []},
        }

    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(recommend=recommend)))


def test_recommendation_route_uses_verified_claim_and_destination():
    calls = []
    response = recommendations(
        k=7, destination="Nha Trang",
        authorization=f"Bearer {token()}",
        recommend=recommendation_request(calls).app.state.recommend,
        settings=SimpleNamespace(jwt_secret=SECRET, jwt_algorithm="HS256"),
    )
    assert calls == [("VP0000001", {"k": 7, "destination": "Nha Trang"})]
    assert response["cdpUserId"] == "VP0000001"
    assert isinstance(response["diagnostics"]["latencyMs"], int)


def test_recommendation_route_does_not_fallback_on_invalid_token():
    calls = []
    response = recommendations(
        k=5, destination=None,
        authorization="Bearer invalid",
        recommend=recommendation_request(calls).app.state.recommend,
        settings=SimpleNamespace(jwt_secret=SECRET, jwt_algorithm="HS256"),
    )
    assert response.status_code == 401
    assert json.loads(response.body)["error"]["code"] == "INVALID_TOKEN"
    assert calls == []
