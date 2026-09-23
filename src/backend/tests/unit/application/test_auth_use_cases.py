"""Use case auth trên bản giả in-memory (auth §3.6, §3.8, §9, §10.4, §20.1)."""
import asyncio
import logging

import bcrypt
import pytest

from src.backend.app.application.auth.errors import (
    CdpUnavailable,
    EmailAlreadyExists,
    InvalidCredentials,
    RateLimited,
    RefreshTokenInvalid,
    RefreshTokenReuse,
    TokenInvalid,
    WeakPassword,
)
from src.backend.app.application.auth.principal import AuthenticatedUser, AuthPrincipal
from src.backend.app.application.auth.use_cases import (
    AuthenticateUser,
    ChangePassword,
    GetCurrentUser,
    ListDemoAccounts,
    RegisterUser,
    RevokeSession,
    RotateSession,
)
from src.backend.app.domain.auth.identifiers import is_web_cdp_user_id
from src.backend.app.infrastructure.auth.rate_limiter import InMemoryRateLimiter
from src.backend.tests.fakes.auth import (
    FakeProfiles,
    InMemoryRefreshTokens,
    InMemoryUsers,
    RecordingAttempts,
    fast_hasher,
    jwt_issuer,
)

HASHER = fast_hasher()
PASSWORD = "Demo@2026"


def run(coro):
    return asyncio.run(coro)


def seeded_user(**overrides) -> AuthenticatedUser:
    values = dict(user_id="00000000-0000-0000-0000-000000000001", email="minh.anh@example.com",
                  password_hash=HASHER.hash(PASSWORD), display_name="Minh Anh", cdp_user_id="VP0000001",
                  persona="P1_frequent")
    values.update(overrides)
    return AuthenticatedUser(**values)


class World:
    def __init__(self, users=None, *, profiles=None):
        self.users = InMemoryUsers(users if users is not None else [seeded_user()])
        self.profiles = profiles or FakeProfiles()
        self.refresh = InMemoryRefreshTokens()
        self.limiter = InMemoryRateLimiter()
        self.attempts = RecordingAttempts()
        self.issuer = jwt_issuer()

    def register(self):
        return RegisterUser(users=self.users, hasher=HASHER, cdp=self.profiles, tokens=self.issuer,
                            refresh=self.refresh, limiter=self.limiter)

    def login(self):
        return AuthenticateUser(users=self.users, hasher=HASHER, tokens=self.issuer, refresh=self.refresh,
                                limiter=self.limiter, attempts=self.attempts)

    def rotate(self):
        return RotateSession(users=self.users, tokens=self.issuer, refresh=self.refresh)


# --- đăng ký hai pha --------------------------------------------------------------------------

def test_register_creates_cdp_profile_before_user_and_logs_in():
    w = World([])
    outcome = run(w.register()(email=" Gia.Huy@Example.vn ", password="ngua o chay tren de",
                               full_name="Phạm Gia Huy", client_ip="10.0.0.1"))
    assert w.profiles.created == [outcome.user.cdp_user_id]
    assert is_web_cdp_user_id(outcome.user.cdp_user_id)
    assert outcome.user.email == "gia.huy@example.vn"
    assert outcome.refresh_token is None and outcome.session_id is None  # v1: không có refresh
    assert w.issuer.verify(outcome.access_token).cdp_user_id == outcome.user.cdp_user_id


def test_register_with_session_issues_bound_refresh_token():
    w = World([])
    outcome = run(w.register()(email="a@b.vn", password="ngua o chay tren de", full_name="A",
                               client_ip="10.0.0.1", with_session=True))
    assert outcome.refresh_token and outcome.session_id
    assert w.issuer.verify(outcome.access_token).session_id == outcome.session_id


def test_register_cdp_down_creates_no_user():
    w = World([], profiles=FakeProfiles(unavailable=True))
    with pytest.raises(CdpUnavailable) as caught:
        run(w.register()(email="a@b.vn", password="ngua o chay tren de", full_name="A", client_ip="1.1.1.1"))
    assert caught.value.retryable and caught.value.http_status == 503
    assert w.users.by_id == {}


def test_register_losing_email_race_leaves_orphan_profile_and_logs(caplog):
    w = World([])
    w.users.fail_create_with = EmailAlreadyExists("a@b.vn")
    with caplog.at_level(logging.WARNING), pytest.raises(EmailAlreadyExists):
        run(w.register()(email="a@b.vn", password="ngua o chay tren de", full_name="A", client_ip="1.1.1.1"))
    assert len(w.profiles.created) == 1 and w.users.by_id == {}
    assert "auth.orphan_profile" in caplog.text and "email_race" in caplog.text


def test_register_rejects_existing_email_before_touching_cdp():
    w = World()
    with pytest.raises(EmailAlreadyExists):
        run(w.register()(email="MINH.ANH@example.com", password="ngua o chay tren de", full_name="X",
                         client_ip="1.1.1.1"))
    assert w.profiles.created == []


def test_register_weak_password_has_reasons():
    w = World([])
    with pytest.raises(WeakPassword) as caught:
        run(w.register()(email="a@b.vn", password="password123", full_name="A", client_ip="1.1.1.1"))
    assert caught.value.details["reasons"]


def test_register_rate_limited_per_ip():
    w = World([])
    for n in range(5):
        run(w.register()(email=f"u{n}@b.vn", password="ngua o chay tren de", full_name="U", client_ip="9.9.9.9"))
    with pytest.raises(RateLimited):
        run(w.register()(email="u9@b.vn", password="ngua o chay tren de", full_name="U", client_ip="9.9.9.9"))


# --- đăng nhập ---------------------------------------------------------------------------------

def test_login_success_records_attempt_and_touches_last_login():
    w = World()
    outcome = run(w.login()(email="Minh.Anh@example.com", password=PASSWORD, client_ip="203.0.113.7",
                            with_session=True))
    principal = w.issuer.verify(outcome.access_token)
    assert (principal.cdp_user_id, principal.amr) == ("VP0000001", ("pwd",))
    assert w.users.last_login == [outcome.user.user_id]
    record = w.attempts.records[-1]
    assert record["succeeded"] and record["ip_prefix"] == "203.0.113.0/24"


def test_unknown_email_and_bad_password_are_indistinguishable():
    w = World()
    with pytest.raises(InvalidCredentials) as unknown:
        run(w.login()(email="nobody@example.com", password=PASSWORD, client_ip="1.1.1.1"))
    with pytest.raises(InvalidCredentials) as bad:
        run(w.login()(email="minh.anh@example.com", password="sai-mat-khau", client_ip="1.1.1.1"))
    assert (unknown.value.code, str(unknown.value)) == (bad.value.code, str(bad.value))
    assert [r["failure_reason"] for r in w.attempts.records] == ["unknown_email", "bad_password"]


def test_sixth_wrong_password_is_locked_with_retry_after():
    w = World()
    for _ in range(5):
        with pytest.raises(InvalidCredentials):
            run(w.login()(email="minh.anh@example.com", password="wrong-one!", client_ip="1.1.1.1"))
    with pytest.raises(RateLimited) as caught:
        # Kể cả mật khẩu ĐÚNG cũng bị chặn khi đang khoá.
        run(w.login()(email="minh.anh@example.com", password=PASSWORD, client_ip="1.1.1.2"))
    assert caught.value.retry_after_seconds == 900 and caught.value.retryable
    assert w.attempts.records[-1]["failure_reason"] == "locked"


def test_successful_login_resets_failure_counter():
    w = World()
    for _ in range(4):
        with pytest.raises(InvalidCredentials):
            run(w.login()(email="minh.anh@example.com", password="wrong-one!", client_ip="1.1.1.1"))
    run(w.login()(email="minh.anh@example.com", password=PASSWORD, client_ip="1.1.1.1"))
    for _ in range(4):
        with pytest.raises(InvalidCredentials):
            run(w.login()(email="minh.anh@example.com", password="wrong-one!", client_ip="1.1.1.1"))


def test_bcrypt_seed_hash_is_upgraded_to_argon2id_on_login():
    legacy = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
    w = World([seeded_user(password_hash=legacy)])
    run(w.login()(email="minh.anh@example.com", password=PASSWORD, client_ip="1.1.1.1"))
    assert w.users.by_id[seeded_user().user_id].password_hash.startswith("$argon2id$")


# --- refresh rotation --------------------------------------------------------------------------

def test_rotation_issues_new_pair_in_same_session():
    w = World()
    first = run(w.login()(email="minh.anh@example.com", password=PASSWORD, client_ip="1.1.1.1", with_session=True))
    second = run(w.rotate()(refresh_token=first.refresh_token))
    assert second.refresh_token != first.refresh_token
    assert second.session_id == first.session_id
    assert w.issuer.verify(second.access_token).session_id == first.session_id


def test_reused_refresh_token_revokes_the_whole_family(caplog):
    w = World()
    stolen = run(w.login()(email="minh.anh@example.com", password=PASSWORD, client_ip="1.1.1.1",
                           with_session=True)).refresh_token
    victim = run(w.rotate()(refresh_token=stolen)).refresh_token   # nạn nhân refresh trước
    with caplog.at_level(logging.ERROR), pytest.raises(RefreshTokenReuse):
        run(w.rotate()(refresh_token=stolen))                       # kẻ trộm dùng lại token cũ
    assert "auth.refresh_reuse" in caplog.text
    with pytest.raises(RefreshTokenInvalid):
        run(w.rotate()(refresh_token=victim))                       # cả hai bên đều bị đăng xuất
    assert w.refresh.live() == []


def test_unknown_refresh_token_is_invalid():
    with pytest.raises(RefreshTokenInvalid):
        run(World().rotate()(refresh_token="rt_nope"))


def test_logout_revokes_family_and_is_idempotent():
    w = World()
    token = run(w.login()(email="minh.anh@example.com", password=PASSWORD, client_ip="1.1.1.1",
                          with_session=True)).refresh_token
    revoke = RevokeSession(refresh=w.refresh)
    run(revoke(refresh_token=token))
    run(revoke(refresh_token=token))
    run(revoke(refresh_token="rt_unknown"))
    with pytest.raises(RefreshTokenInvalid):
        run(w.rotate()(refresh_token=token))


# --- đổi mật khẩu, me, demo --------------------------------------------------------------------

def test_change_password_revokes_other_sessions_but_keeps_current():
    w = World()
    current = run(w.login()(email="minh.anh@example.com", password=PASSWORD, client_ip="1.1.1.1", with_session=True))
    other = run(w.login()(email="minh.anh@example.com", password=PASSWORD, client_ip="1.1.1.1", with_session=True))
    principal = w.issuer.verify(current.access_token)
    change = ChangePassword(users=w.users, hasher=HASHER, refresh=w.refresh)
    assert run(change(principal=principal, current_password=PASSWORD, new_password="bien xanh cat trang")) == 1
    run(w.rotate()(refresh_token=current.refresh_token))
    with pytest.raises(RefreshTokenInvalid):
        run(w.rotate()(refresh_token=other.refresh_token))
    run(w.login()(email="minh.anh@example.com", password="bien xanh cat trang", client_ip="1.1.1.1"))


def test_change_password_requires_current_password_and_policy():
    w = World()
    principal = AuthPrincipal(seeded_user().user_id, "VP0000001", "minh.anh@example.com")
    change = ChangePassword(users=w.users, hasher=HASHER, refresh=w.refresh)
    with pytest.raises(InvalidCredentials):
        run(change(principal=principal, current_password="sai", new_password="bien xanh cat trang"))
    with pytest.raises(WeakPassword):
        run(change(principal=principal, current_password=PASSWORD, new_password="password123"))


def test_current_user_rejects_principal_not_matching_row():
    w = World()
    get = GetCurrentUser(users=w.users)
    assert run(get(AuthPrincipal(seeded_user().user_id, "VP0000001", "x"))).display_name == "Minh Anh"
    with pytest.raises(TokenInvalid):
        run(get(AuthPrincipal(seeded_user().user_id, "VP0000999", "x")))
    with pytest.raises(TokenInvalid):
        run(get(AuthPrincipal("missing", "VP0000001", "x")))


def test_demo_accounts_follow_presentation_order_without_passwords():
    users = [
        seeded_user(user_id=f"u{n}", email=f"p{n}@example.com", cdp_user_id=f"VP000000{n}", persona=persona)
        for n, persona in [(4, "P4_no_history"), (2, "P2_first_time"), (1, "P1_frequent"), (3, "P3_dormant")]
    ] + [seeded_user(user_id="t1", email="test01@vota.demo", cdp_user_id="VP0000005", persona=None)]
    accounts = run(ListDemoAccounts(users=InMemoryUsers(users))())
    assert [a.email for a in accounts] == ["p1@example.com", "p2@example.com", "p3@example.com", "p4@example.com"]
    assert accounts[0].persona_label == "Khách thân thiết"
    assert not any(hasattr(a, "password") for a in accounts)
