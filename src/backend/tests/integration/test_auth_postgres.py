"""Auth trên Postgres local đã seed (auth §20.2). Chạy: RUN_POSTGRES_INTEGRATION=1.

Mỗi test tự dọn user đăng ký qua SEED_DATABASE_URL (superuser) — cdp_writer không có DELETE trên
cdp.profiles, đúng như thiết kế, nên chỉ superuser xoá được profile mồ côi do test tạo ra.
"""
import asyncio
import os
import uuid

import psycopg
import pytest

from src.backend.app.application.auth.errors import (
    CdpUnavailable,
    RefreshTokenInvalid,
    RefreshTokenReuse,
)
from src.backend.app.application.auth.use_cases import (
    AuthenticateUser,
    ChangePassword,
    RegisterUser,
    RotateSession,
    UpdateProfile,
)
from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.domain.auth.privacy import hash_email
from src.backend.app.infrastructure.auth.argon2_hasher import Argon2Hasher
from src.backend.app.infrastructure.auth.postgres_login_attempts import PostgresLoginAttemptLog
from src.backend.app.infrastructure.auth.postgres_refresh_tokens import PostgresRefreshTokenStore
from src.backend.app.infrastructure.auth.postgres_user_repository import PostgresUserRepository
from src.backend.app.infrastructure.auth.rate_limiter import InMemoryRateLimiter
from src.backend.app.infrastructure.cdp.local_cdp_client import LocalCdpClient
from src.backend.tests.fakes.auth import jwt_issuer

APP_URL = os.getenv("DATABASE_URL", "postgresql://vota_app_login:vota@localhost:5432/vota")
CDP_URL = os.getenv("CDP_DATABASE_URL", "postgresql://cdp_client_login:cdp@localhost:5432/vota")
SEED_URL = os.getenv("SEED_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/vota")
PASSWORD = "Demo@2026"
PERSONA_EMAILS = ["minh.anh@example.com", "quoc.bao@example.com", "thu.ha@example.com", "khach.moi@example.com"]

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="set RUN_POSTGRES_INTEGRATION=1 to test the seeded local database",
)

HASHER = Argon2Hasher()  # tham số thật: hash seed phải không cần rehash
USERS = PostgresUserRepository(APP_URL)
REFRESH = PostgresRefreshTokenStore(APP_URL)
ISSUER = jwt_issuer()


def run(coro):
    return asyncio.run(coro)


def register(cdp_url=CDP_URL):
    return RegisterUser(users=USERS, hasher=HASHER, cdp=LocalCdpClient(cdp_url), tokens=ISSUER, refresh=REFRESH,
                        limiter=InMemoryRateLimiter())


def login():
    return AuthenticateUser(users=USERS, hasher=HASHER, tokens=ISSUER, refresh=REFRESH, limiter=InMemoryRateLimiter(),
                            attempts=PostgresLoginAttemptLog(APP_URL))


@pytest.fixture
def email():
    address = f"it-{uuid.uuid4().hex[:10]}@vota.test-auth"
    yield address
    with psycopg.connect(SEED_URL, autocommit=True) as db:
        row = db.execute("DELETE FROM app.users WHERE email = %s RETURNING cdp_user_id", (address,)).fetchone()
        db.execute("DELETE FROM app.login_attempts WHERE user_id IS NULL AND attempted_at > now() - interval '1 hour'"
                   " AND email_hash = %s", (hash_email(address),))
        if row:
            db.execute("DELETE FROM cdp.profiles WHERE cdp_user_id = %s", (row[0],))


def test_register_creates_cdp_profile_then_app_user(email):
    outcome = run(register()(email=email, password="ngua o chay tren de", full_name="IT", client_ip="127.0.0.1"))
    with psycopg.connect(SEED_URL) as db:
        assert db.execute("SELECT 1 FROM cdp.profiles WHERE cdp_user_id = %s", (outcome.user.cdp_user_id,)).fetchone()
        stored = db.execute("SELECT cdp_user_id, password_hash FROM app.users WHERE email = %s", (email,)).fetchone()
    assert stored[0] == outcome.user.cdp_user_id and stored[1].startswith("$argon2id$")


def test_cdp_failure_leaves_no_app_user(email):
    with pytest.raises(CdpUnavailable):
        run(register("postgresql://nobody:nothing@localhost:1/none")(
            email=email, password="ngua o chay tren de", full_name="IT", client_ip="127.0.0.1"))
    assert run(USERS.find_by_email(email)) is None


def test_vota_app_cannot_create_cdp_profiles():
    with psycopg.connect(APP_URL, autocommit=True) as app:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("INSERT INTO cdp.profiles (cdp_user_id) VALUES ('VPWINTEGRATION0')")


@pytest.mark.parametrize("persona_email", PERSONA_EMAILS)
def test_seeded_personas_log_in_and_end_on_argon2id(persona_email):
    outcome = run(login()(email=persona_email, password=PASSWORD, client_ip="127.0.0.1"))
    assert outcome.user.cdp_user_id.startswith("VP000000")
    stored = run(USERS.find_by_email(persona_email)).password_hash
    # Seed cũ (bcrypt) được nâng cấp ngay lần đăng nhập đầu; seed mới đã là Argon2id đúng tham số.
    assert stored.startswith("$argon2id$") and not HASHER.needs_rehash(stored)


def test_refresh_rotation_and_reuse_on_postgres(email):
    run(register()(email=email, password="ngua o chay tren de", full_name="IT", client_ip="127.0.0.1"))
    first = run(login()(email=email, password="ngua o chay tren de", client_ip="127.0.0.1", with_session=True))
    rotate = RotateSession(users=USERS, tokens=ISSUER, refresh=REFRESH)
    second = run(rotate(refresh_token=first.refresh_token))
    assert second.session_id == first.session_id
    with pytest.raises(RefreshTokenReuse):
        run(rotate(refresh_token=first.refresh_token))
    with pytest.raises(RefreshTokenInvalid):
        run(rotate(refresh_token=second.refresh_token))
    with psycopg.connect(SEED_URL) as db:
        reasons = {r[0] for r in db.execute(
            "SELECT revoked_reason FROM app.refresh_tokens t JOIN app.users u USING (user_id) WHERE u.email = %s",
            (email,))}
    assert reasons == {"rotation", "reuse_detected"}


def test_change_password_revokes_other_sessions_only(email):
    run(register()(email=email, password="ngua o chay tren de", full_name="IT", client_ip="127.0.0.1"))
    current = run(login()(email=email, password="ngua o chay tren de", client_ip="127.0.0.1", with_session=True))
    other = run(login()(email=email, password="ngua o chay tren de", client_ip="127.0.0.1", with_session=True))
    change = ChangePassword(users=USERS, hasher=HASHER, refresh=REFRESH)
    run(change(principal=ISSUER.verify(current.access_token), current_password="ngua o chay tren de",
               new_password="bien xanh cat trang"))
    rotate = RotateSession(users=USERS, tokens=ISSUER, refresh=REFRESH)
    run(rotate(refresh_token=current.refresh_token))
    with pytest.raises(RefreshTokenInvalid):
        run(rotate(refresh_token=other.refresh_token))


def test_update_profile_persists_name_and_phone_and_never_touches_email_or_hash(email):
    outcome = run(register()(email=email, password="ngua o chay tren de", full_name="IT", client_ip="127.0.0.1"))
    principal = AuthPrincipal(user_id=outcome.user.user_id, cdp_user_id=outcome.user.cdp_user_id, email=email)
    update = UpdateProfile(users=USERS)

    updated = run(update(principal, full_name="Tên Mới", phone="0345484496", set_phone=True))
    assert (updated.display_name, updated.phone) == ("Tên Mới", "0345484496")
    reloaded = run(USERS.find_by_id(outcome.user.user_id))
    assert (reloaded.display_name, reloaded.phone, reloaded.email) == ("Tên Mới", "0345484496", email)
    assert reloaded.password_hash == outcome.user.password_hash

    run(update(principal, full_name="Chỉ đổi tên"))                       # không động tới số
    assert run(USERS.find_by_id(outcome.user.user_id)).phone == "0345484496"
    cleared = run(update(principal, phone=None, set_phone=True))
    assert cleared.phone is None and cleared.display_name == "Chỉ đổi tên"


def test_database_rejects_a_malformed_phone_even_if_the_api_layer_were_bypassed(email):
    outcome = run(register()(email=email, password="ngua o chay tren de", full_name="IT", client_ip="127.0.0.1"))
    for bad in ("034548", "1345484496", "03454844961", "0345 484 496"):
        with psycopg.connect(APP_URL) as app:
            with pytest.raises(psycopg.errors.CheckViolation):
                app.execute("UPDATE app.users SET phone = %s WHERE user_id = %s::uuid", (bad, outcome.user.user_id))

