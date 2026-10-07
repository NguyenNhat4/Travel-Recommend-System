"""DTO khớp src/shared/contracts/schemas/auth.yaml. Tên trường camelCase như contract."""
from __future__ import annotations

from typing import Literal

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.backend.app.application.auth.principal import AuthenticatedUser
from src.backend.app.application.auth.use_cases import AuthOutcome


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


_PHONE = re.compile(r"^0[0-9]{9}$")


class UpdateProfileRequest(BaseModel):
    """PATCH /auth/me (FR-USR-04): chỉ trường có mặt mới đổi; `phone = null` xoá số. Email không sửa được."""

    model_config = ConfigDict(extra="forbid")

    fullName: str | None = Field(default=None, max_length=100)
    phone: str | None = None

    @field_validator("fullName")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("họ tên không được rỗng")
        return value

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not _PHONE.fullmatch(value):
            raise ValueError("số điện thoại gồm 10 chữ số, bắt đầu bằng 0")
        return value

    @model_validator(mode="after")
    def _something_to_change(self) -> "UpdateProfileRequest":
        if not self.model_fields_set:
            raise ValueError("cần ít nhất một trường")
        if "fullName" in self.model_fields_set and self.fullName is None:
            raise ValueError("họ tên không được null")
        return self


class AuthUser(BaseModel):
    userId: str
    cdpUserId: str
    email: str
    fullName: str
    phone: str | None = None

    @classmethod
    def of(cls, user: AuthenticatedUser) -> "AuthUser":
        return cls(userId=user.user_id, cdpUserId=user.cdp_user_id, email=user.email, fullName=user.display_name,
                   phone=user.phone)


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
