"""Máy trạng thái phiên (auth §3.3, §3.8). Thuần: không Redis, không HTTP, không DB.

Ba trạng thái, không có trạng thái thứ tư:
    anonymous     — khách vãng lai, không có cdp_user_id, không ghi CDP (auth §3.7)
    pending_mfa   — đúng mật khẩu nhưng chưa qua yếu tố thứ hai. CHƯA mang cdp_user_id.
    authenticated — xác thực đầy đủ

Quy tắc xuyên suốt: bất cứ khi nào mức đặc quyền đổi thì sid phải xoay (chống session fixation).
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import StrEnum


class SessionState(StrEnum):
    ANONYMOUS = "anonymous"
    PENDING_MFA = "pending_mfa"
    AUTHENTICATED = "authenticated"


class SessionEvent(StrEnum):
    """Tên khớp các dòng A–L của bảng auth §3.8."""

    VISIT = "visit"                      # A
    REGISTER = "register"                # B
    LOGIN = "login"                      # C
    LOGIN_NEEDS_MFA = "login_needs_mfa"  # D
    MFA_VERIFIED = "mfa_verified"        # E
    SWITCH_ACCOUNT = "switch_account"    # F
    LOGOUT = "logout"                    # G
    UA_MISMATCH = "ua_mismatch"          # H
    EXPIRED = "expired"                  # I
    PASSWORD_CHANGED = "password_changed"  # J
    MFA_CHANGED = "mfa_changed"          # K
    EMAIL_VERIFIED = "email_verified"    # L


@dataclass(frozen=True)
class Transition:
    state: SessionState | None          # None = phiên bị huỷ
    rotate_sid: bool
    carries_identity: bool              # phiên có được mang cdp_user_id sau bước này không


class InvalidTransition(RuntimeError):
    pass


# Chỉ dòng EMAIL_VERIFIED không xoay sid: nó không nâng mức đặc quyền theo hướng lợi dụng được.
_TABLE: dict[tuple[SessionState, SessionEvent], Transition] = {
    (SessionState.ANONYMOUS, SessionEvent.VISIT): Transition(SessionState.ANONYMOUS, False, False),
    (SessionState.ANONYMOUS, SessionEvent.REGISTER): Transition(SessionState.AUTHENTICATED, True, True),
    (SessionState.ANONYMOUS, SessionEvent.LOGIN): Transition(SessionState.AUTHENTICATED, True, True),
    (SessionState.ANONYMOUS, SessionEvent.LOGIN_NEEDS_MFA): Transition(SessionState.PENDING_MFA, True, False),
    (SessionState.PENDING_MFA, SessionEvent.MFA_VERIFIED): Transition(SessionState.AUTHENTICATED, True, True),
    (SessionState.AUTHENTICATED, SessionEvent.SWITCH_ACCOUNT): Transition(SessionState.AUTHENTICATED, True, True),
    (SessionState.AUTHENTICATED, SessionEvent.PASSWORD_CHANGED): Transition(SessionState.AUTHENTICATED, True, True),
    (SessionState.AUTHENTICATED, SessionEvent.MFA_CHANGED): Transition(SessionState.AUTHENTICATED, True, True),
    (SessionState.AUTHENTICATED, SessionEvent.EMAIL_VERIFIED): Transition(SessionState.AUTHENTICATED, False, True),
}

# Huỷ phiên áp cho mọi trạng thái.
_TERMINAL = {SessionEvent.LOGOUT, SessionEvent.UA_MISMATCH, SessionEvent.EXPIRED}


def apply(state: SessionState, event: SessionEvent) -> Transition:
    """Ném InvalidTransition cho cặp không hợp lệ — ví dụ pending_mfa mà gọi LOGIN.

    Không có nhánh "mặc định cho qua": bước chuyển không khai báo là lỗi lập trình, và im lặng cho qua
    ở tầng này nghĩa là một phiên nửa-đăng-nhập có thể mang danh tính.
    """
    if event in _TERMINAL:
        return Transition(None, True, False)
    try:
        return _TABLE[(state, event)]
    except KeyError:
        raise InvalidTransition(f"{state} + {event}") from None


def new_session_id() -> str:
    """sid phía backend: 128 bit ngẫu nhiên, ràng buộc refresh token và claim `sid` của JWT.

    Khác cookie `vota_sid` của BFF — BFF xoay sid cookie theo bảng §3.8 mà không cần backend biết.
    """
    return "s_" + secrets.token_urlsafe(16)
