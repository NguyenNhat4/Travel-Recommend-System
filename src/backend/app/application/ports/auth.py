"""Port của auth. Application chỉ phụ thuộc các interface này (docs/prd/architecture.md §2).

Hiện thực nằm ở infrastructure/auth/; chỉ composition root nối chúng vào use case.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.backend.app.application.auth.principal import AuthenticatedUser


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

    async def email_exists(self, email: str) -> bool:
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


class RefreshTokenStore(Protocol):
    async def issue(self, *, user_id: str, session_id: str, family_id: str | None = None) -> str:
        """Trả token bản rõ; chỉ SHA-256 được lưu (auth §10.4)."""
        ...

    async def rotate(self, token: str, *, session_id: str) -> tuple[str, str]:
        """Trả (token mới, user_id).

        Token đã xoay mà bị dùng lại = dấu hiệu bị đánh cắp → thu hồi CẢ family và ném
        RefreshTokenReuse. Đây là cách duy nhất phát hiện token bị trộm.
        """
        ...

    async def revoke(self, token: str, *, reason: str) -> None:
        ...

    async def revoke_all_for_user(self, user_id: str, *, reason: str) -> int:
        ...


class TokenIssuer(Protocol):
    def issue_access_token(
        self, user: AuthenticatedUser, *, session_id: str | None, amr: tuple[str, ...]
    ) -> tuple[str, int]:
        """Trả (JWT, số giây tới hạn)."""
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
    async def check(self, scope: str, key: str) -> None:
        """Ném RateLimited(retry_after_seconds) khi vượt ngưỡng (auth §9.1)."""
        ...

    async def register_failure(self, scope: str, key: str) -> int:
        """Tăng bộ đếm, trả số lần thất bại trong cửa sổ hiện tại."""
        ...

    async def reset(self, scope: str, key: str) -> None:
        """Đăng nhập đúng thì xoá sạch bộ đếm."""
        ...
