"""Port đo lần gọi của web / agent (docs/prd/deployment-plan.md §5, docs/prd/architecture.md §2)."""
from __future__ import annotations

from typing import Any, Protocol


class CallTelemetry(Protocol):
    def record(self, event: dict[str, Any]) -> None:
        """Một lần gọi đã xong: source, kind (http | tool), name, status, ms, và chi tiết (stageMs, resultCount,
        productIds). Không có câu tìm kiếm, dữ liệu cá nhân hay bí mật."""

    def set_catalog(self, products: int | None) -> None:
        """Backend vừa nạp bản catalog / recsys mới vào bộ nhớ."""

    def snapshot(self, after: int = 0, limit: int = 200) -> dict[str, Any]:
        """Sự kiện có seq > after (mới nhất sau cùng), tổng hợp theo (source, name) và trạng thái catalog."""
