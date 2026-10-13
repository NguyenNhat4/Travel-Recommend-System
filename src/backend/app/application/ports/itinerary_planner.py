"""Port chạy agent lập lịch trình cho một request.

`application/itinerary/use_cases.py` chỉ biết port này; `agents/` hiện thực nó bằng LangGraph và `main.py`
nối hai bên (docs/prd/architecture.md §2, quy tắc 8).
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol


class ItineraryPlanner(Protocol):
    async def ainvoke(self, inputs: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Chạy trọn graph, trả state cuối (có `response`, `http_status`). `config`: nhãn trace của run."""
        ...

    def astream(self, inputs: dict[str, Any], config: dict[str, Any] | None = None) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Phát (`state`, state) sau node hoặc (`event`, payload) cho activity/preview."""
        ...

    def topology(self) -> dict[str, Any]:
        """Node và cạnh của graph, để UI vẽ trace."""
        ...


#: Dựng planner cho một request từ header Authorization và chủ hội thoại (cdp_user_id đã xác thực, None khi
#: là khách); None khi agent chưa được cấu hình dữ liệu.
ItineraryPlannerFactory = Callable[[str | None, str | None], ItineraryPlanner | None]
