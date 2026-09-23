"""Ngưỡng rate limit và lockout (auth §9.1, §9.2). Thuần: adapter Redis/in-memory đọc bảng này.

Chỉ các dòng thuộc P0. Gửi lại mail, đặt lại mật khẩu và OTP là P1 — ngoài phạm vi.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitRule:
    limit: int
    window_seconds: int
    # Vượt ngưỡng thì khoá thêm bao lâu. 0 = không khoá riêng, chỉ chờ cửa sổ trượt nhả ra.
    lockout_seconds: int = 0


RULES: dict[str, RateLimitRule] = {
    # Đếm lần SAI; đăng nhập đúng xoá sạch bộ đếm.
    "login:email": RateLimitRule(limit=5, window_seconds=15 * 60, lockout_seconds=15 * 60),
    "login:ip": RateLimitRule(limit=20, window_seconds=15 * 60, lockout_seconds=15 * 60),
    # Đếm MỌI lần thử, chống credential stuffing.
    "login:ipwide": RateLimitRule(limit=100, window_seconds=60 * 60),
    "register:ip": RateLimitRule(limit=5, window_seconds=60 * 60),
}


def rule_for(scope: str) -> RateLimitRule:
    try:
        return RULES[scope]
    except KeyError:
        raise ValueError(f"scope rate limit lạ: {scope}") from None
