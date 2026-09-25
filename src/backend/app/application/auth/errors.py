"""Lỗi của auth. Mã khớp bảng auth §17; tầng API dịch sang HTTP status."""
from __future__ import annotations


class AuthError(Exception):
    code = "INTERNAL_ERROR"
    http_status = 500
    retryable = False

    @property
    def details(self) -> dict | None:
        return None


class InvalidCredentials(AuthError):
    """Sai email và sai mật khẩu dùng CHUNG lỗi này, cùng thông điệp, cùng độ trễ."""

    code = "INVALID_CREDENTIALS"
    http_status = 401


class EmailAlreadyExists(AuthError):
    code = "EMAIL_ALREADY_EXISTS"
    http_status = 409


class CdpUserIdTaken(AuthError):
    """Nội bộ: va chạm cdp_user_id lúc INSERT. Caller sinh lại ID và thử lại."""

    code = "INTERNAL_ERROR"
    http_status = 500


class WeakPassword(AuthError):
    code = "WEAK_PASSWORD"
    http_status = 400

    def __init__(self, reasons: list[str]):
        super().__init__(", ".join(reasons))
        self.reasons = reasons

    @property
    def details(self) -> dict:
        return {"reasons": self.reasons}


class RateLimited(AuthError):
    code = "TOO_MANY_ATTEMPTS"
    http_status = 429
    retryable = True

    def __init__(self, retry_after_seconds: int):
        super().__init__(f"retry after {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds

    @property
    def details(self) -> dict:
        return {"retryAfterSeconds": self.retry_after_seconds}


class RefreshTokenInvalid(AuthError):
    code = "INVALID_TOKEN"
    http_status = 401


class RefreshTokenReuse(AuthError):
    """Token đã xoay bị dùng lại: cả family đã bị thu hồi. Luôn log mức ERROR."""

    code = "INVALID_TOKEN"
    http_status = 401


class CdpUnavailable(AuthError):
    """Không tạo được cdp.profiles lúc đăng ký (auth §3.6.3 bước ③)."""

    code = "CDP_UNAVAILABLE"
    http_status = 503
    retryable = True


class TokenInvalid(AuthError):
    """Bearer hỏng: sai chữ ký/issuer/audience/alg, thiếu claim. KHÔNG hạ thành khách (auth §3.11 dòng 2)."""

    code = "INVALID_TOKEN"
    http_status = 401


class TokenExpired(TokenInvalid):
    code = "TOKEN_EXPIRED"
    http_status = 401


class Unauthenticated(AuthError):
    """Route cần đăng nhập mà request không mang Bearer (auth §3.5)."""

    code = "UNAUTHENTICATED"
    http_status = 401
