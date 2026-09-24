"""Danh tính đã xác thực của một request (auth §3.5).

Đây là thứ DUY NHẤT use case được phép đọc để biết request thuộc về ai. Không đọc cdp_user_id,
user_id hay email từ query param hoặc body — auth §1.2 điều 2.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: str
    # Không bao giờ None: principal tồn tại nghĩa là đã xác thực đầy đủ.
    # Phiên pending_mfa KHÔNG sinh ra principal (auth §3.8 dòng D).
    cdp_user_id: str
    email: str
    session_id: str | None = None          # sid khi đến từ BFF; None khi là service nội bộ
    amr: tuple[str, ...] = ()              # pwd · otp · webauthn · oauth
    email_verified: bool = False
    token_id: str | None = None             # claim jti; dùng cho danh sách thu hồi khẩn (auth §10.3 điểm 9)

    def __post_init__(self) -> None:
        if not self.user_id or not self.cdp_user_id:
            raise ValueError("AuthPrincipal cần cả user_id và cdp_user_id")


@dataclass(frozen=True)
class AuthenticatedUser:
    """Một hàng app.users. cdp_user_id đi cùng hàng nên đăng nhập không phải hỏi sang CDP.

    Gương app.users.cdp_user_id tồn tại chính vì vota_app không có quyền SELECT cdp.profiles.
    """

    user_id: str
    email: str
    password_hash: str
    display_name: str
    cdp_user_id: str
    persona: str | None = None
    email_verified: bool = False
    mfa_enabled: bool = False
