"""Tên điểm đến của catalog cho system prompt của orc v2.

Model không biết catalog gọi một nơi là gì ("Sài Gòn", "HCM" hay "TP. Hồ Chí Minh"); đoán sai thì lọc theo điểm đến
rỗng. Danh sách lấy từ catalog (không viết cứng: catalog đổi theo job cào), giữ trong process `ttl_seconds` để không
tốn request nguồn của từng lượt. Lỗi thì dùng bản cũ nếu có, không thì None: orc vẫn còn tool list_destinations.
"""
from __future__ import annotations

import asyncio
import logging
from time import monotonic
from typing import Callable

logger = logging.getLogger(__name__)


class DestinationNames:
    def __init__(self, *, ttl_seconds: float = 600, timeout_seconds: float = 2,
                 clock: Callable[[], float] = monotonic):
        self.ttl, self.timeout, self.clock = ttl_seconds, timeout_seconds, clock
        self._names: list[str] | None = None
        self._fetched_at = 0.0

    async def get(self, tools) -> list[str] | None:
        if self._names is not None and self.clock() - self._fetched_at < self.ttl:
            return self._names
        try:
            data = await asyncio.wait_for(tools.list_destinations(), self.timeout)
            names = sorted({row["destination"] for row in data["destinations"] if row.get("destination")})
        except Exception as exc:  # thiếu catalog, lỗi mạng, quá giờ: lượt vẫn chạy
            logger.warning("itinerary.v2.destinations_unavailable reason=%s", type(exc).__name__)
            if self._names is not None:
                self._fetched_at = self.clock()  # dùng bản cũ thêm một chu kỳ, không lượt nào cũng chờ nguồn lỗi
            return self._names
        if names:
            self._names, self._fetched_at = names, self.clock()
        return self._names
