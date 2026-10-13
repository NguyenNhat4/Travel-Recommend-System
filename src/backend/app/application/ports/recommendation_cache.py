"""Port kho cache kết quả gợi ý (`GET /recommendations`), chốt 2026-10-12.

PRD: `docs/prd/architecture.md` §4 (Redis giữ cache gợi ý 15 phút ở DB index riêng), đề xuất
`docs/prd/update-archive/2026-10-12-cache-goi-y-tren-redis.md`. Kho chỉ giữ byte theo khoá; khoá, mã hoá giá trị và chống tính
trùng nằm ở `application/recommendation/cache.py`. Adapter: `infrastructure/persistence/redis_recommendation_cache.py`.
"""
from __future__ import annotations

from typing import Protocol


class RecommendationCacheUnavailable(Exception):
    """Kho lỗi, chậm quá hạn hoặc đang ngắt mạch. Use case gặp lỗi này thì tính trực tiếp, không trả lỗi cho khách."""


class RecommendationCacheStore(Protocol):
    def get(self, key: str) -> bytes | None:
        """Giá trị đã lưu, `None` khi không có hoặc đã hết hạn."""
        ...

    def put(self, key: str, value: bytes, ttl_seconds: int) -> None:
        """Ghi kèm TTL. Mọi khoá phải có TTL: Redis chạy `noeviction`."""
        ...

    def try_lock(self, key: str, token: str, ttl_ms: int) -> bool:
        """Đặt khoá tính nếu chưa ai giữ (`SET NX PX`); True khi lấy được."""
        ...

    def unlock(self, key: str, token: str) -> None:
        """Bỏ khoá tính chỉ khi vẫn là của `token` (không xoá khoá người khác đã lấy lại sau khi hết hạn)."""
        ...
