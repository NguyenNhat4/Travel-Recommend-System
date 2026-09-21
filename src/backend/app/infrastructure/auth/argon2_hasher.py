"""Argon2id, giữ đường kiểm bcrypt cho user seed (auth §8.1, §8.2).

Chuỗi PHC tự mô tả thuật toán ($argon2id$… / $2b$…) nên app.users KHÔNG cần cột password_algo.
"""
from __future__ import annotations

import logging

import bcrypt
from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

logger = logging.getLogger(__name__)

_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")
# Mật khẩu giả để verify khi email không tồn tại; giữ độ trễ tương đương nhánh có user thật.
_DUMMY_PASSWORD = "dummy-password-for-constant-time-compare"


class Argon2Hasher:
    """Tham số mặc định theo OWASP 2024. Không hạ memory_cost để chạy nhanh hơn."""

    def __init__(self, *, memory_kib: int = 19456, time_cost: int = 2, parallelism: int = 1):
        self._hasher = Argon2PasswordHasher(
            memory_cost=memory_kib, time_cost=time_cost, parallelism=parallelism, hash_len=32, salt_len=16
        )
        self._dummy_hash = self._hasher.hash(_DUMMY_PASSWORD)

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, stored_hash: str) -> bool:
        if stored_hash.startswith("$argon2"):
            try:
                return self._hasher.verify(stored_hash, password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return False
        if stored_hash.startswith(_BCRYPT_PREFIXES):
            try:
                return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
            except ValueError:
                return False
        # Không nhận dạng được: từ chối, và báo động — dữ liệu trong cột này đã sai.
        logger.error("auth.unknown_hash_format")
        return False

    def needs_rehash(self, stored_hash: str) -> bool:
        if stored_hash.startswith(_BCRYPT_PREFIXES):
            return True
        if stored_hash.startswith("$argon2"):
            try:
                return self._hasher.check_needs_rehash(stored_hash)
            except InvalidHashError:
                return True
        return True

    def dummy_verify(self) -> None:
        """Đốt thời gian tương đương một lần verify thật (auth §3.6.4)."""
        try:
            self._hasher.verify(self._dummy_hash, "wrong-password")
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            pass
