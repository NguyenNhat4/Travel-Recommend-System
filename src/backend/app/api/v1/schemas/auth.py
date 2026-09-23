"""DTO khớp src/shared/contracts/schemas/auth.yaml. Tên trường camelCase như contract."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.backend.app.application.auth.principal import AuthenticatedUser
from src.backend.app.application.auth.use_cases import AuthOutcome, DemoAccount


# Kiểm dạng tối thiểu; không kéo thêm email-validator. Email so khớp sau khi lower() ở use case.
Email = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)


class RegisterRequest(BaseModel):
    email: str = Email
    # Tối đa 128 dù contract v1 không ghi: chặn DoS Argon2 (auth §8.3). Chính sách đầy đủ ở domain.
    password: str = Field(min_length=8, max_length=128)
    fullName: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: str = Email
    password: str = Field(max_length=128)


class SessionRequest(LoginRequest):
    captchaToken: str | None = None  # CAPTCHA_PROVIDER=noop ở P0


class RefreshRequest(BaseModel):
    refreshToken: str = Field(min_length=1, max_length=256)


class PasswordChangeRequest(BaseModel):
    currentPassword: str = Field(max_length=128)
    newPassword: str = Field(min_length=8, max_length=128)


class AuthUser(BaseModel):
    userId: str
    cdpUserId: str
    email: str
    fullName: str

    @classmethod
    def of(cls, user: AuthenticatedUser) -> "AuthUser":
        return cls(userId=user.user_id, cdpUserId=user.cdp_user_id, email=user.email, fullName=user.display_name)


class AuthResponse(BaseModel):
    accessToken: str
    tokenType: Literal["Bearer"] = "Bearer"
    expiresIn: int
    user: AuthUser

    @classmethod
    def of(cls, outcome: AuthOutcome) -> "AuthResponse":
        return cls(accessToken=outcome.access_token, expiresIn=outcome.expires_in, user=AuthUser.of(outcome.user))


class SessionResponse(BaseModel):
    state: Literal["anonymous", "pending_mfa", "authenticated"]
    accessToken: str | None = None
    refreshToken: str | None = None
    expiresIn: int | None = None
    user: AuthUser | None = None

    @classmethod
    def of(cls, outcome: AuthOutcome) -> "SessionResponse":
        # P0 không có 2FA nên không phiên nào dừng ở pending_mfa.
        return cls(
            state="authenticated", accessToken=outcome.access_token, refreshToken=outcome.refresh_token,
            expiresIn=outcome.expires_in, user=AuthUser.of(outcome.user),
        )


class DemoAccountOut(BaseModel):
    email: str
    fullName: str
    personaLabel: str
    blurb: str

    @classmethod
    def of(cls, account: DemoAccount) -> "DemoAccountOut":
        return cls(email=account.email, fullName=account.full_name,
                   personaLabel=account.persona_label, blurb=account.blurb)


class DemoAccountListResponse(BaseModel):
    accounts: list[DemoAccountOut]
