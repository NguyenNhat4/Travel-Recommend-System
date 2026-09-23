"""Bản giả in-memory cho port auth. Cùng ngữ nghĩa với adapter Postgres, không cần database."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass, replace

from src.backend.app.application.auth.errors import (
    CdpUserIdTaken,
    EmailAlreadyExists,
    RefreshTokenInvalid,
    RefreshTokenReuse,
)
from src.backend.app.application.auth.principal import AuthenticatedUser
from src.backend.app.application.ports.auth import RotatedRefreshToken
from src.backend.app.application.ports.cdp_client import CdpUnavailableError
from src.backend.app.infrastructure.auth.argon2_hasher import Argon2Hasher
from src.backend.app.infrastructure.auth.jwt_issuer import JwtConfig, JwtIssuer
from src.backend.app.infrastructure.auth.keys import generate_rsa_pem_pair

_KEYS = generate_rsa_pem_pair()


def fast_hasher() -> Argon2Hasher:
    """Argon2id tham số thấp cho test nhanh. Code thật luôn dùng tham số OWASP (Settings chặn ge=19456)."""
    return Argon2Hasher(memory_kib=1024, time_cost=1, parallelism=1)


def jwt_issuer(**overrides) -> JwtIssuer:
    config = dict(private_key=_KEYS[0], public_key=_KEYS[1], issuer="https://api.vota.test", audience="vota-api")
    config.update(overrides)
    return JwtIssuer(JwtConfig(**config))


def rsa_keys() -> tuple[str, str]:
    return _KEYS


class InMemoryUsers:
    def __init__(self, users: list[AuthenticatedUser] | None = None, *, fail_create_with: Exception | None = None):
        self.by_id = {u.user_id: u for u in users or []}
        self.fail_create_with = fail_create_with
        self.last_login: list[str] = []

    async def find_by_email(self, email):
        return next((u for u in self.by_id.values() if u.email == email.lower()), None)

    async def find_by_id(self, user_id):
        return self.by_id.get(user_id)

    async def email_exists(self, email):
        return await self.find_by_email(email) is not None

    async def list_personas(self):
        return [u for u in self.by_id.values() if u.persona]

    async def create(self, *, email, password_hash, display_name, cdp_user_id):
        if self.fail_create_with is not None:
            error, self.fail_create_with = self.fail_create_with, None
            raise error
        if await self.email_exists(email):
            raise EmailAlreadyExists(email)
        if any(u.cdp_user_id == cdp_user_id for u in self.by_id.values()):
            raise CdpUserIdTaken(cdp_user_id)
        user = AuthenticatedUser(str(uuid.uuid4()), email.lower(), password_hash, display_name, cdp_user_id)
        self.by_id[user.user_id] = user
        return user

    async def update_password_hash(self, user_id, password_hash):
        self.by_id[user_id] = replace(self.by_id[user_id], password_hash=password_hash)

    async def touch_last_login(self, user_id):
        self.last_login.append(user_id)


class FakeProfiles:
    def __init__(self, *, unavailable: bool = False):
        self.created: list[str] = []
        self.unavailable = unavailable

    async def ensure_profile(self, cdp_user_id, *, home_city=None):
        if self.unavailable:
            raise CdpUnavailableError("down")
        self.created.append(cdp_user_id)


@dataclass
class _Row:
    user_id: str
    family_id: str
    session_id: str
    rotated: bool = False
    revoked_reason: str | None = None


class InMemoryRefreshTokens:
    def __init__(self):
        self.rows: dict[str, _Row] = {}

    @staticmethod
    def _h(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def _add(self, user_id, family_id, session_id):
        token = "rt_" + secrets.token_urlsafe(32)
        self.rows[self._h(token)] = _Row(user_id, family_id, session_id)
        return token

    async def issue(self, *, user_id, session_id):
        return self._add(user_id, str(uuid.uuid4()), session_id)

    async def rotate(self, token):
        row = self.rows.get(self._h(token))
        if row is None:
            raise RefreshTokenInvalid("lạ")
        if row.rotated:
            for other in self.rows.values():
                if other.user_id == row.user_id and other.revoked_reason is None:
                    other.revoked_reason = "reuse_detected"
            raise RefreshTokenReuse("reuse")
        if row.revoked_reason is not None:
            raise RefreshTokenInvalid("đã thu hồi")
        row.rotated, row.revoked_reason = True, "rotation"
        return RotatedRefreshToken(self._add(row.user_id, row.family_id, row.session_id), row.user_id, row.session_id)

    async def revoke(self, token, *, reason):
        row = self.rows.get(self._h(token))
        if row is None:
            return
        for other in self.rows.values():
            if other.family_id == row.family_id and other.revoked_reason is None:
                other.revoked_reason = reason

    async def revoke_all_for_user(self, user_id, *, reason, except_session_id=None):
        count = 0
        for row in self.rows.values():
            if row.user_id == user_id and row.revoked_reason is None and row.session_id != except_session_id:
                row.revoked_reason = reason
                count += 1
        return count

    def live(self, user_id=None):
        return [r for r in self.rows.values() if r.revoked_reason is None and (user_id is None or r.user_id == user_id)]


class RecordingAttempts:
    def __init__(self):
        self.records: list[dict] = []

    async def record(self, **kwargs):
        self.records.append(kwargs)
