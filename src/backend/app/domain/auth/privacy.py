"""Rút gọn định danh trước khi ghi log hoặc lưu (auth §15.2). Thuần: chỉ stdlib.

Email không bao giờ ghi thô (dùng SHA-256), IP không bao giờ ghi đầy đủ (/24 hoặc /48),
session id chỉ ghi 8 ký tự đầu.
"""
from __future__ import annotations

import hashlib
import ipaddress


def hash_email(email: str) -> str:
    return "sha256:" + hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def ip_prefix(raw: str) -> str:
    """/24 cho IPv4, /48 cho IPv6. Không parse được thì trả 'unknown' thay vì ném lỗi:
    ghi nhật ký đăng nhập không được phép làm hỏng chính lần đăng nhập đó."""
    try:
        addr = ipaddress.ip_address(raw.strip())
    except ValueError:
        return "unknown"
    net = 24 if addr.version == 4 else 48
    return str(ipaddress.ip_network(f"{addr}/{net}", strict=False))


def short_sid(session_id: str | None) -> str:
    return (session_id or "-")[:8]
