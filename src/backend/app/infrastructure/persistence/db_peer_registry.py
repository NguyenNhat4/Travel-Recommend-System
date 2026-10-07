"""Sổ "VM nào còn với tới DB" trong Redis dùng chung, để `/health/ready` phân biệt hai tình huống khác nhau.

- Một VM mất DB, các VM khác vẫn ổn: VM đó hỏng cục bộ (pgbouncer chết, firewall) → bị loại khỏi LB.
- Mọi VM cùng mất DB: loại hết chỉ khiến LB không còn backend nào, trang catalog/search (không cần DB) cũng sập
  → giữ lại, phục vụ chế độ không DB.

Mỗi VM ghi dấu "DB ổn" kèm thời điểm vào một sorted set khi probe thành công và xoá dấu khi probe hỏng. Khi VM tự
thấy DB hỏng, nó đếm dấu còn mới của VM khác. Mỗi VM xoá dấu của mình TRƯỚC khi đếm, nên hai VM hỏng cùng lúc không
thể cùng thấy "còn bạn tốt" (cả hai cùng bị loại): VM hỏng sau cùng luôn thấy 0 và được giữ lại.
Redis không với tới được → trả None (không biết); người gọi coi như mất toàn cục, vì loại hết là kết cục tệ hơn.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Protocol

logger = logging.getLogger(__name__)

KEY = "vota:ready:db_ok"


class SortedSetClient(Protocol):
    async def zadd(self, name: str, mapping: dict[str, float]) -> int: ...
    async def zrem(self, name: str, *values: str) -> int: ...
    async def zcount(self, name: str, min: float, max: float) -> int: ...
    async def zscore(self, name: str, value: str) -> float | None: ...
    async def zremrangebyscore(self, name: str, min: float, max: float) -> int: ...


class DbPeerRegistry:
    def __init__(self, redis: SortedSetClient, member: str, *, ttl_seconds: float = 30.0,
                 clock: Callable[[], float] = time.time):
        self._redis, self._member, self._ttl, self._clock = redis, member, ttl_seconds, clock

    async def mark_ok(self) -> None:
        try:
            await self._redis.zadd(KEY, {self._member: self._clock()})
        except Exception as exc:  # noqa: BLE001 — sổ chỉ là phụ trợ, không làm hỏng readiness
            logger.warning("readiness.peers.write_failed error=%s", type(exc).__name__)

    async def mark_failed(self) -> None:
        try:
            await self._redis.zrem(KEY, self._member)
        except Exception as exc:  # noqa: BLE001
            logger.warning("readiness.peers.write_failed error=%s", type(exc).__name__)

    async def peers_ok(self) -> int | None:
        """Số VM KHÁC còn dấu "DB ổn" mới hơn ttl; None nếu không đọc được Redis."""
        now = self._clock()
        try:
            await self._redis.zremrangebyscore(KEY, 0, now - self._ttl)
            total = await self._redis.zcount(KEY, now - self._ttl, "+inf")
            mine = await self._redis.zscore(KEY, self._member)
        except Exception as exc:  # noqa: BLE001
            logger.warning("readiness.peers.read_failed error=%s", type(exc).__name__)
            return None
        return int(total) - (1 if mine is not None else 0)
