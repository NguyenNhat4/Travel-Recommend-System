"""Use case lập lịch trình: API gọi vào đây, agent nằm sau port `ItineraryPlanner`."""
from __future__ import annotations

import asyncio
from typing import Any

from src.backend.app.application.ports.itinerary_planner import ItineraryPlanner, ItineraryPlannerFactory


class PlanItinerary:
    def __init__(self, planner_factory: ItineraryPlannerFactory, request_timeout_seconds: float):
        self._planner_factory = planner_factory
        self.request_timeout_seconds = request_timeout_seconds

    def planner(self, authorization: str | None) -> ItineraryPlanner | None:
        """None khi chưa cấu hình nguồn dữ liệu cho agent; route trả SEARCH_UNAVAILABLE."""
        return self._planner_factory(authorization)

    @staticmethod
    def inputs(request: dict[str, Any], request_id: str) -> dict[str, Any]:
        """ItineraryRequest (đã validate theo contract) → input của graph."""
        context = request.get("context")
        return {
            "query": request.get("message") or "",
            "conversation_id": request.get("conversationId"),
            "intent_override": request.get("intentOverride") or {},
            "language": context["language"] if context else None,
            "request_id": request_id,
        }

    async def run(self, planner: ItineraryPlanner, request: dict[str, Any], request_id: str) -> dict[str, Any]:
        """Chạy trọn graph trong giới hạn thời gian của request; hết giờ thì ném TimeoutError."""
        return await asyncio.wait_for(planner.ainvoke(self.inputs(request, request_id)),
                                      timeout=self.request_timeout_seconds)
