"""Chính sách mật khẩu (auth §8.3). Thuần: không băm, không chạm DB.

Theo NIST SP 800-63B: bắt buộc độ dài và chặn mật khẩu đoán được, KHÔNG ép thành phần ký tự.
Ép hoa/số/ký tự đặc biệt đẩy người dùng tới `Matkhau@123` và không tăng entropy thật.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

MIN_LENGTH = 8
# Argon2 tốn bộ nhớ theo thiết kế; chuỗi dài vô hạn là một đường DoS rẻ tiền.
MAX_LENGTH = 128

# Tập rút gọn cho P0. Danh sách đầy đủ (top 10.000) nạp từ file ở bước sau — xem WeakPasswordError.reasons.
_COMMON = frozenset({
    "12345678", "123456789", "1234567890", "password", "password1", "password123",
    "qwerty123", "111111111", "abc12345", "iloveyou", "admin123", "letmein1",
    "matkhau", "matkhau123", "vietnam123", "123456a@", "1q2w3e4r",
})


class WeakPasswordError(ValueError):
    """400 WEAK_PASSWORD; `reasons` đi vào details để Web gắn vào ô mật khẩu."""

    def __init__(self, reasons: list[str]):
        super().__init__(", ".join(reasons))
        self.reasons = reasons


@dataclass(frozen=True)
class PasswordPolicy:
    min_length: int = MIN_LENGTH
    max_length: int = MAX_LENGTH

    def normalize(self, password: str) -> str:
        """NFKC trước khi băm, nếu không cùng một mật khẩu gõ từ hai bàn phím sẽ ra hai hash khác nhau."""
        return unicodedata.normalize("NFKC", password)

    def validate(self, password: str, *, email: str = "", full_name: str = "") -> str:
        """Trả về mật khẩu đã chuẩn hoá, hoặc ném WeakPasswordError."""
        candidate = self.normalize(password)
        reasons: list[str] = []

        if len(candidate) < self.min_length:
            reasons.append(f"Mật khẩu phải có ít nhất {self.min_length} ký tự.")
        if len(candidate) > self.max_length:
            reasons.append(f"Mật khẩu không được quá {self.max_length} ký tự.")

        lowered = candidate.lower()
        if lowered in _COMMON:
            reasons.append("Mật khẩu này nằm trong danh sách bị lộ, hãy chọn mật khẩu khác.")

        # Mật khẩu = email hoặc tên thì kẻ tấn công đoán ra ngay từ dữ liệu công khai.
        for label, source in (("email", email), ("tên", full_name)):
            source = source.strip().lower()
            if not source:
                continue
            if label == "email":
                source = source.split("@", 1)[0]
            if len(source) >= 3 and source in lowered:
                reasons.append(f"Mật khẩu không được chứa {label} của bạn.")

        if reasons:
            raise WeakPasswordError(reasons)
        return candidate
