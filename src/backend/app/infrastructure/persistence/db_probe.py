"""Kiểm nhanh PostgreSQL còn sống không, cho `/health/ready`. Kết quả được cache để health check không dồn tải."""
from __future__ import annotations

import asyncio
import time
from typing import Callable

from src.backend.app.infrastructure.persistence.db_connection import connect_async


class DatabaseProbe:
    def __init__(
        self,
        database_url: str,
        *,
        ttl_seconds: float = 5.0,
        timeout_seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._database_url = database_url
        self._ttl = ttl_seconds
        self._timeout = timeout_seconds
        self._clock = clock
        self._checked_at: float | None = None
        self._up = False
        self._lock = asyncio.Lock()

    async def is_up(self) -> bool:
        async with self._lock:  # một lần ping cho mọi request đồng thời trong cùng cửa sổ TTL
            now = self._clock()
            if self._checked_at is not None and now - self._checked_at < self._ttl:
                return self._up
            self._up = await self._ping()
            self._checked_at = self._clock()
            return self._up

    async def _ping(self) -> bool:
        try:
            async def run() -> None:
                async with await connect_async(
                    self._database_url, connect_timeout=max(1, int(self._timeout))
                ) as conn:
                    await conn.execute("SELECT 1")

            await asyncio.wait_for(run(), timeout=self._timeout + 2)
            return True
        except Exception:  # noqa: BLE001 - mọi lỗi nghĩa là "không dùng được"
            return False
