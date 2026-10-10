"""Thăm dò database cho `/health/ready` (chỉ dành cho load balancer, không dùng cho autohealing).

Một lệnh `SELECT 1` có timeout, kết quả cache vài giây để các probe liên tiếp của LB (và nhiều worker) không tạo
thêm kết nối mỗi lượt. Dùng đúng DSN mà request dùng, nên sidecar pgbouncer hỏng cũng bị phát hiện.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Callable

import psycopg

logger = logging.getLogger(__name__)


def _select_one(database_url: str, timeout_seconds: float) -> None:
    with psycopg.connect(database_url, connect_timeout=max(1, math.ceil(timeout_seconds))) as conn:
        conn.execute("SELECT 1")


class DatabaseProbe:
    def __init__(self, database_url: str, *, timeout_seconds: float = 2.0, cache_seconds: float = 5.0,
                 clock: Callable[[], float] = time.monotonic, select_one: Callable[[str, float], None] = _select_one):
        self._url, self._timeout, self._cache = database_url, timeout_seconds, cache_seconds
        self._clock, self._select_one = clock, select_one
        self._checked_at: float | None = None
        self._ok = False
        self._lock = asyncio.Lock()

    async def ok(self) -> bool:
        async with self._lock:  # một lượt thăm dò tại một thời điểm; các lượt đồng thời dùng kết quả vừa có
            now = self._clock()
            if self._checked_at is not None and now - self._checked_at < self._cache:
                return self._ok
            try:
                await asyncio.wait_for(asyncio.to_thread(self._select_one, self._url, self._timeout), self._timeout + 1)
                self._ok = True
            except Exception as exc:  # noqa: BLE001 — mọi lỗi (từ chối, hết hạn, xác thực) đều là "chưa sẵn sàng"
                if self._ok or self._checked_at is None:
                    logger.warning("readiness.database.unavailable error=%s", type(exc).__name__)
                self._ok = False
            self._checked_at = now
            return self._ok
