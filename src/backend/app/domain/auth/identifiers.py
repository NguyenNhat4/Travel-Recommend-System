"""Cấp phát cdp_user_id cho tài khoản đăng ký qua web (auth §3.6.2).

cdp_user_id là danh tính nghiệp vụ, không phải user_id: carts, bookings, cdp.events và engine
recommendation đều khoá theo nó. Quan hệ với app.users là 1–1 và bất biến.

Hai dải tách hẳn nhau:
    VP + 7 chữ số   — CHỈ job seed (VP0000001…VP0002000). Backend không bao giờ cấp trong dải này.
    VPW + 12 ký tự  — Backend cấp lúc đăng ký.

Tách dải để chạy lại seed không bao giờ đè lên tài khoản người dùng thật, và ngược lại.
"""
from __future__ import annotations

import re
import secrets

WEB_PREFIX = "VPW"
_BODY_LEN = 12

# Crockford base32: bỏ I, L, O, U để không nhầm với 1, 0 và không tạo từ tục.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

SEED_PATTERN = re.compile(r"^VP\d{7}$")
WEB_PATTERN = re.compile(rf"^{WEB_PREFIX}[{_ALPHABET}]{{{_BODY_LEN}}}$")


def new_web_cdp_user_id() -> str:
    """Sinh ngẫu nhiên, không dùng bộ đếm.

    Bộ đếm tuần tự cho phép đếm số người dùng và đoán ID hàng xóm, và cần khoá giữa hai connection
    mà auth §3.6.3 cố ý không dùng chung transaction. 12 ký tự base32 = 60 bit, va chạm không đáng lo;
    INSERT vẫn có UNIQUE chặn, caller thử lại (tối đa 3 lần) nếu trúng.
    """
    body = "".join(secrets.choice(_ALPHABET) for _ in range(_BODY_LEN))
    return f"{WEB_PREFIX}{body}"


def is_seed_cdp_user_id(value: str) -> bool:
    return bool(SEED_PATTERN.match(value))


def is_web_cdp_user_id(value: str) -> bool:
    return bool(WEB_PATTERN.match(value))
