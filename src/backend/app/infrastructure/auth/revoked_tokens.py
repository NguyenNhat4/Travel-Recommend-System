"""Danh sách thu hồi khẩn access token (auth §10.3 điểm 9, §16.1): key `jwt:revoked:{jti}`, TTL tới `exp`.

Bình thường không cần: access token chỉ sống 10 phút và đăng xuất thu hồi refresh token. Danh sách
này để chặn ngay một token cụ thể khi có sự cố, ví dụ `SET jwt:revoked:<jti> 1 EX 600` trên Redis.
"""
from __future__ import annotations


class RedisRevokedTokens:
    def __init__(self, redis):
        self._r = redis

    async def is_revoked(self, token_id: str) -> bool:
        return bool(await self._r.exists(f"jwt:revoked:{token_id}"))


class NoRevokedTokens:
    """Không có Redis (dev/test): không token nào bị thu hồi khẩn."""

    async def is_revoked(self, token_id: str) -> bool:
        return False
