"""Port của auth. Application chỉ phụ thuộc các interface này (docs/prd/architecture.md §2).

Hiện thực nằm ở infrastructure/auth/; chỉ composition root nối chúng vào use case.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.backend.app.application.auth.principal import AuthenticatedUser, AuthPrincipal


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str:
        ...

    def verify(self, password: str, stored_hash: str) -> bool:
        """So sánh hằng thời gian. Chấp nhận cả hash bcrypt cũ của user seed (auth §8.2)."""
        ...

    def needs_rehash(self, stored_hash: str) -> bool:
        """True với hash bcrypt hoặc tham số Argon2 đã cũ → caller rehash sau khi verify đúng."""
        ...

    def dummy_verify(self) -> None:
        """Chạy một lần verify giả khi email không tồn tại.

        Không có nó, thời gian phản hồi trở thành oracle liệt kê tài khoản (auth §3.6.4).
        """
        ...


class UserRepository(Protocol):
    async def find_by_email(self, email: str) -> AuthenticatedUser | None:
        ...

    async def find_by_id(self, user_id: str) -> AuthenticatedUser | None:
        ...

    async def email_exists(self, email: str) -> bool:
        ...

    async def list_personas(self) -> list[AuthenticatedUser]:
        """User seed có persona, cho /auth/demo-accounts."""
        ...

    async def create(
        self, *, email: str, password_hash: str, display_name: str, cdp_user_id: str
    ) -> AuthenticatedUser:
        """Ném EmailAlreadyExists khi trùng email, CdpUserIdTaken khi trùng cdp_user_id."""
        ...

    async def update_password_hash(self, user_id: str, password_hash: str) -> None:
        ...

    async def touch_last_login(self, user_id: str) -> None:
        ...


@dataclass(frozen=True)
class RotatedRefreshToken:
    token: str
    user_id: str
    session_id: str


class RefreshTokenStore(Protocol):
    async def issue(self, *, user_id: str, session_id: str) -> str:
        """Mở family mới, trả token bản rõ; chỉ SHA-256 được lưu (auth §10.4)."""
        ...

    async def rotate(self, token: str) -> RotatedRefreshToken:
        """Một lần dùng: token cũ đánh dấu rotated, token mới cùng family và cùng session_id.

        Token đã xoay mà bị dùng lại = dấu hiệu bị đánh cắp → thu hồi CẢ family cùng mọi phiên
        của user và ném RefreshTokenReuse. Token lạ/hết hạn/đã thu hồi → RefreshTokenInvalid.
        """
        ...

    async def revoke(self, token: str, *, reason: str) -> None:
        """Thu hồi cả family của token. Token lạ hoặc đã thu hồi: không lỗi (idempotent)."""
        ...

    async def revoke_all_for_user(
        self, user_id: str, *, reason: str, except_session_id: str | None = None
    ) -> int:
        ...


class TokenIssuer(Protocol):
    def issue_access_token(
        self, user: AuthenticatedUser, *, session_id: str | None, amr: tuple[str, ...]
    ) -> tuple[str, int]:
        """Trả (JWT, số giây tới hạn)."""
        ...


class TokenVerifier(Protocol):
    def verify(self, token: str) -> AuthPrincipal:
        """Kiểm đủ 10 điểm của auth §10.3. Ném TokenExpired hoặc TokenInvalid."""
        ...

    def jwks(self) -> dict:
        """Public key cho /.well-known/jwks.json."""
        ...


class RevokedTokens(Protocol):
    async def is_revoked(self, token_id: str) -> bool:
        """jti nằm trong danh sách thu hồi khẩn `jwt:revoked:{jti}` (auth §10.3 điểm 9, §16.1)."""
        ...


class LoginAttemptLog(Protocol):
    async def record(
        self,
        *,
        email: str,
        user_id: str | None,
        ip_prefix: str,
        user_agent_hash: str | None,
        succeeded: bool,
        failure_reason: str | None,
        at: datetime | None = None,
    ) -> None:
        """Ghi app.login_attempts. email được băm trước khi lưu — không bao giờ lưu email thô."""
        ...


class RateLimiter(Protocol):
    """Scope là tên ở auth §9.1: login:email, login:ip, login:ipwide, register:ip."""

    async def hit(self, scope: str, key: str) -> None:
        """Đếm MỌI lần thử (không chỉ lần sai); vượt ngưỡng thì ném RateLimited."""
        ...

    async def check(self, scope: str, key: str) -> None:
        """Ném RateLimited(retry_after_seconds) khi vượt ngưỡng (auth §9.1)."""
        ...

    async def register_failure(self, scope: str, key: str) -> int:
        """Tăng bộ đếm, trả số lần thất bại trong cửa sổ hiện tại."""
        ...

    async def reset(self, scope: str, key: str) -> None:
        """Đăng nhập đúng thì xoá sạch bộ đếm."""
        ...
