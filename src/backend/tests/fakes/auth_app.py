"""Gắn use case auth dựng trên bản giả vào `app.state` của app FastAPI thật, cho test HTTP."""
from __future__ import annotations

from contextlib import contextmanager

from src.backend.app.application.auth.use_cases import (
    AuthenticateUser,
    ChangePassword,
    GetCurrentUser,
    RegisterUser,
    RevokeSession,
    RotateSession,
)
from src.backend.app.infrastructure.auth.rate_limiter import InMemoryRateLimiter
from src.backend.tests.fakes.auth import (
    FakeProfiles,
    InMemoryRefreshTokens,
    InMemoryUsers,
    RecordingAttempts,
    fast_hasher,
    jwt_issuer,
)

SERVICE_TOKEN = "s" * 40


class AuthWorld:
    def __init__(self, users):
        self.hasher = fast_hasher()
        self.users = InMemoryUsers(users)
        self.profiles = FakeProfiles()
        self.refresh = InMemoryRefreshTokens()
        self.limiter = InMemoryRateLimiter()
        self.issuer = jwt_issuer()
        self.recommend_calls: list = []
        self.revoked_jti: set[str] = set()

    async def is_revoked(self, token_id):
        return token_id in self.revoked_jti

    def recommend(self, cdp_user_id, **kwargs):
        self.recommend_calls.append(cdp_user_id)
        return {"strategy": "personal" if cdp_user_id else "popular", "destination": kwargs.get("destination"),
                "nextVertical": None, "recommendations": [],
                "diagnostics": {"eventsUsed": 0, "coldStart": cdp_user_id is None, "excludedVerticals": []}}

    def state(self) -> dict:
        common = dict(users=self.users, hasher=self.hasher)
        return {
            "token_verifier": self.issuer,
            "revoked_tokens": self,
            "register_user": RegisterUser(**common, cdp=self.profiles, tokens=self.issuer, refresh=self.refresh,
                                          limiter=self.limiter),
            "authenticate_user": AuthenticateUser(**common, tokens=self.issuer, refresh=self.refresh,
                                                  limiter=self.limiter, attempts=RecordingAttempts()),
            "rotate_session": RotateSession(users=self.users, tokens=self.issuer, refresh=self.refresh),
            "revoke_session": RevokeSession(refresh=self.refresh),
            "change_password": ChangePassword(**common, refresh=self.refresh),
            "get_current_user": GetCurrentUser(users=self.users),
            "recommend": self.recommend,
        }


@contextmanager
def installed(app, world: AuthWorld):
    saved = {name: getattr(app.state, name, None) for name in world.state()}
    for name, value in world.state().items():
        setattr(app.state, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(app.state, name, value)
