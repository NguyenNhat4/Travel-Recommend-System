"""Auth ở biên HTTP thật (auth §20.3, §20.5).

Mỗi response phải (1) khớp schema contract gán cho status đó và (2) có status được khai báo trong
`paths/auth.yaml` / `paths/recommendations.yaml`. Bốn endpoint v1 giữ nguyên shape.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from src.backend.app.application.auth.principal import AuthenticatedUser
from src.backend.app.core.config import Settings, get_settings
from src.backend.app.infrastructure.auth.keys import generate_rsa_pem_pair
from src.backend.app.main import app
from src.backend.tests.fakes.auth import fast_hasher, jwt_issuer
from src.backend.tests.fakes.auth_app import SERVICE_TOKEN, AuthWorld, installed
from src.shared.contracts.scripts.bundle_openapi import bundle

DOC = bundle()
PASSWORD = "Demo@2026"
_HASH = fast_hasher().hash(PASSWORD)
PERSONAS = [
    AuthenticatedUser(f"00000000-0000-0000-0000-00000000000{n}", email, _HASH, name, f"VP000000{n}", persona=persona)
    for n, email, name, persona in [
        (1, "minh.anh@example.com", "Minh Anh", "P1_frequent"),
        (2, "quoc.bao@example.com", "Quốc Bảo", "P2_first_time"),
        (3, "thu.ha@example.com", "Thu Hà", "P3_dormant"),
        (4, "khach.moi@example.com", "Khách mới", "P4_no_history"),
    ]
]


def settings(**overrides) -> Settings:
    values = dict(app_env="test", auth_service_token=SERVICE_TOKEN, internal_api_enabled=False,
                  trusted_proxies="127.0.0.1/32")
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def world():
    w = AuthWorld(list(PERSONAS))
    app.dependency_overrides[get_settings] = lambda: settings()
    with installed(app, w):
        yield w
    app.dependency_overrides.clear()


@pytest.fixture
def client(world):
    return TestClient(app)


def assert_contract(response, path: str, method: str) -> None:
    operation = DOC["paths"][path][method]
    status = str(response.status_code)
    assert status in operation["responses"], f"{method.upper()} {path} trả {status} chưa khai báo trong contract"
    declared = operation["responses"][status]
    if "$ref" in declared:
        declared = DOC["components"]["responses"][declared["$ref"].split("/")[-1]]
    if "content" not in declared:
        assert not response.content
        return
    schema = declared["content"]["application/json"]["schema"]
    errors = [e.message for e in Draft202012Validator(dict(schema, components=DOC["components"]),
                                                      format_checker=FormatChecker()).iter_errors(response.json())]
    assert not errors, errors
    if response.status_code >= 400:
        assert response.json()["error"]["code"] in DOC["components"]["schemas"]["ErrorCode"]["enum"]


def svc(**extra):
    return {"X-Service-Token": SERVICE_TOKEN, **extra}


# --- v1 ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("persona", PERSONAS, ids=[p.persona for p in PERSONAS])
def test_all_four_personas_log_in_with_v1_shape(client, persona):
    r = client.post("/api/v1/auth/login", json={"email": persona.email.upper(), "password": PASSWORD})
    assert r.status_code == 200
    assert_contract(r, "/auth/login", "post")
    body = r.json()
    assert set(body) == {"accessToken", "tokenType", "expiresIn", "user"}  # không có refresh token ở v1
    assert body["user"]["cdpUserId"] == persona.cdp_user_id

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['accessToken']}"})
    assert me.status_code == 200
    assert_contract(me, "/auth/me", "get")
    assert me.json() == body["user"]


def test_login_errors_follow_contract(client):
    unknown = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    bad = client.post("/api/v1/auth/login", json={"email": "minh.anh@example.com", "password": "sai-mat-khau"})
    for r in (unknown, bad):
        assert r.status_code == 401
        assert_contract(r, "/auth/login", "post")
    # Cùng mã, cùng thông điệp: không thành oracle liệt kê tài khoản.
    assert unknown.json()["error"]["code"] == bad.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert unknown.json()["error"]["message"] == bad.json()["error"]["message"]


def test_sixth_wrong_password_is_429_with_retry_after(client):
    for _ in range(5):
        assert client.post("/api/v1/auth/session", headers=svc(),
                           json={"email": "thu.ha@example.com", "password": "wrong-pass"}).status_code == 401
    r = client.post("/api/v1/auth/session", headers=svc(), json={"email": "thu.ha@example.com", "password": "wrong-pass"})
    assert r.status_code == 429 and r.headers["Retry-After"] == "900"
    assert_contract(r, "/auth/session", "post")
    assert r.json()["error"]["retryable"] is True
    assert r.json()["error"]["details"] == {"retryAfterSeconds": 900}


def test_register_v1_shape_and_conflict(client, world):
    body = {"email": "gia.huy@example.vn", "password": "ngua o chay tren de", "fullName": "Phạm Gia Huy"}
    r = client.post("/api/v1/auth/register", json=body)
    assert r.status_code == 201
    assert_contract(r, "/auth/register", "post")
    assert r.json()["user"]["cdpUserId"].startswith("VPW")
    assert world.profiles.created == [r.json()["user"]["cdpUserId"]]

    dup = client.post("/api/v1/auth/register", json=body)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"
    assert_contract(dup, "/auth/register", "post")

    weak = client.post("/api/v1/auth/register", json={**body, "email": "x@y.vn", "password": "password123"})
    assert weak.status_code == 400 and weak.json()["error"]["details"]["reasons"]
    assert_contract(weak, "/auth/register", "post")


def test_me_requires_bearer(client):
    for headers, code in [({}, "UNAUTHENTICATED"), ({"Authorization": "Bearer nope"}, "INVALID_TOKEN"),
                          ({"Authorization": "Basic abc"}, "INVALID_TOKEN")]:
        r = client.get("/api/v1/auth/me", headers=headers)
        assert r.status_code == 401 and r.json()["error"]["code"] == code
        assert_contract(r, "/auth/me", "get")


def test_emergency_revoked_jti_is_rejected(client, world):
    token = client.post("/api/v1/auth/login", json={"email": "minh.anh@example.com", "password": PASSWORD}).json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    world.revoked_jti.add(world.issuer.verify(token).token_id)
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_TOKEN"
    # Cũng không hạ xuống khách ở endpoint đọc.
    assert client.get("/api/v1/recommendations", headers=headers).status_code == 401


def test_demo_accounts_order_and_production_404(client):
    r = client.get("/api/v1/auth/demo-accounts")
    assert r.status_code == 200
    assert_contract(r, "/auth/demo-accounts", "get")
    assert [a["email"] for a in r.json()["accounts"]] == [p.email for p in PERSONAS]
    assert "password" not in r.text.lower()

    app.dependency_overrides[get_settings] = lambda: settings(app_env="production")
    r = client.get("/api/v1/auth/demo-accounts")
    assert r.status_code == 404
    assert_contract(r, "/auth/demo-accounts", "get")


# --- nhóm chỉ BFF -----------------------------------------------------------------------------

def test_session_endpoints_require_service_token(client):
    login = {"email": "minh.anh@example.com", "password": PASSWORD}
    for headers in ({}, {"X-Service-Token": "wrong" * 10}):
        r = client.post("/api/v1/auth/session", json=login, headers=headers)
        assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_TOKEN"
        assert_contract(r, "/auth/session", "post")
    # Token cấu hình quá ngắn: luôn từ chối, kể cả khi client gửi trùng.
    app.dependency_overrides[get_settings] = lambda: settings(auth_service_token="short")
    assert client.post("/api/v1/auth/session", json=login, headers={"X-Service-Token": "short"}).status_code == 401


def test_session_lifecycle_create_rotate_revoke(client):
    r = client.post("/api/v1/auth/session", headers=svc(), json={"email": "minh.anh@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert_contract(r, "/auth/session", "post")
    first = r.json()
    assert first["state"] == "authenticated" and first["refreshToken"].startswith("rt_")

    r = client.post("/api/v1/auth/session/token", headers=svc(), json={"refreshToken": first["refreshToken"]})
    assert r.status_code == 200
    assert_contract(r, "/auth/session/token", "post")
    second = r.json()
    assert second["refreshToken"] != first["refreshToken"]

    r = client.post("/api/v1/auth/session/revoke", headers=svc(), json={"refreshToken": second["refreshToken"]})
    assert r.status_code == 204
    assert_contract(r, "/auth/session/revoke", "post")
    r = client.post("/api/v1/auth/session/token", headers=svc(), json={"refreshToken": second["refreshToken"]})
    assert r.status_code == 401
    assert_contract(r, "/auth/session/token", "post")


def test_stolen_refresh_token_logs_out_both_sides(client):
    first = client.post("/api/v1/auth/session", headers=svc(),
                        json={"email": "minh.anh@example.com", "password": PASSWORD}).json()
    victim = client.post("/api/v1/auth/session/token", headers=svc(),
                         json={"refreshToken": first["refreshToken"]}).json()
    thief = client.post("/api/v1/auth/session/token", headers=svc(), json={"refreshToken": first["refreshToken"]})
    assert thief.status_code == 401
    again = client.post("/api/v1/auth/session/token", headers=svc(), json={"refreshToken": victim["refreshToken"]})
    assert again.status_code == 401


def test_change_password_keeps_current_session_only(client):
    login = {"email": "quoc.bao@example.com", "password": PASSWORD}
    current = client.post("/api/v1/auth/session", headers=svc(), json=login).json()
    other = client.post("/api/v1/auth/session", headers=svc(), json=login).json()
    r = client.put("/api/v1/auth/password", headers={"Authorization": f"Bearer {current['accessToken']}"},
                   json={"currentPassword": PASSWORD, "newPassword": "bien xanh cat trang"})
    assert r.status_code == 204
    assert_contract(r, "/auth/password", "put")
    assert client.post("/api/v1/auth/session/token", headers=svc(),
                       json={"refreshToken": current["refreshToken"]}).status_code == 200
    assert client.post("/api/v1/auth/session/token", headers=svc(),
                       json={"refreshToken": other["refreshToken"]}).status_code == 401


def test_jwks_is_public_and_matches_contract(client):
    r = client.get("/.well-known/jwks.json")
    assert r.status_code == 200
    assert_contract(r, "/.well-known/jwks.json", "get")


# --- recommendations: gỡ IDOR ------------------------------------------------------------------

def test_recommendations_ignore_cdp_user_id_query(client, world):
    r = client.get("/api/v1/recommendations", params={"cdp_user_id": "VP0000001"})
    assert r.status_code == 200 and r.json()["strategy"] == "popular"
    assert world.recommend_calls == [None]


def test_recommendations_use_verified_identity_and_reject_bad_token(client, world):
    token = client.post("/api/v1/auth/login", json={"email": "minh.anh@example.com", "password": PASSWORD}).json()["accessToken"]
    assert client.get("/api/v1/recommendations", headers={"Authorization": f"Bearer {token}"}).json()["cdpUserId"] == "VP0000001"
    # Token ký bằng khoá lạ: 401, KHÔNG hạ xuống popular.
    forged, _ = jwt_issuer(private_key=generate_rsa_pem_pair()[0]).issue_access_token(
        PERSONAS[1], session_id=None, amr=("pwd",))
    r = client.get("/api/v1/recommendations", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401
    assert_contract(r, "/recommendations", "get")
    assert world.recommend_calls == ["VP0000001"]


def test_internal_recommendations_gated(client, world):
    url = "/api/v1/internal/recommendations"
    r = client.get(url, params={"cdp_user_id": "VP0000003"})
    assert r.status_code == 401
    assert_contract(r, "/internal/recommendations", "get")
    r = client.get(url, params={"cdp_user_id": "VP0000003"}, headers=svc())
    assert r.status_code == 200 and r.json()["cdpUserId"] == "VP0000003"

    app.dependency_overrides[get_settings] = lambda: settings(app_env="production")
    r = client.get(url, params={"cdp_user_id": "VP0000003"}, headers=svc())
    assert r.status_code == 404
    assert_contract(r, "/internal/recommendations", "get")
    app.dependency_overrides[get_settings] = lambda: settings(app_env="production", internal_api_enabled=True)
    assert client.get(url, params={"cdp_user_id": "VP0000003"}, headers=svc()).status_code == 200


def test_forwarded_for_trusted_only_from_configured_proxies(world):
    from src.backend.app.api.deps import client_ip

    class Req:
        def __init__(self, peer, xff):
            self.client = type("C", (), {"host": peer})()
            self.headers = {"x-forwarded-for": xff}

    cfg = settings(trusted_proxies="10.0.0.0/8")
    assert client_ip(Req("10.1.2.3", "1.2.3.4, 10.9.9.9"), cfg) == "1.2.3.4"
    assert client_ip(Req("8.8.8.8", "1.2.3.4"), cfg) == "8.8.8.8"  # peer lạ: bỏ qua header
