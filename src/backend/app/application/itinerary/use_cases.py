"""Use case lập lịch trình: API gọi vào đây, agent nằm sau port `ItineraryPlanner`."""
from __future__ import annotations

import asyncio
from typing import Any

from src.backend.app.application.ports.itinerary_planner import ItineraryPlanner, ItineraryPlannerFactory


class PlanItinerary:
    def __init__(self, planner_factory: ItineraryPlannerFactory, request_timeout_seconds: float):
        self._planner_factory = planner_factory
        self.request_timeout_seconds = request_timeout_seconds

    def planner(self, authorization: str | None, owner: str | None = None) -> ItineraryPlanner | None:
        """None khi chưa cấu hình nguồn dữ liệu cho agent; route trả SEARCH_UNAVAILABLE."""
        return self._planner_factory(authorization, owner)

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

    @staticmethod
    def trace_config(message: str | None, request_id: str, conversation: str,
                     *, transport: str, run_id: str | None = None) -> dict[str, Any]:
        """Name and label the run so one turn can be found in LangSmith from a log line.

        Without this every trace is called "LangGraph" and carries no request id, so a turn
        observed in the demo UI cannot be matched to its trace. The name is the user's own
        message, which the trace already records as graph input; no new data is exposed.
        Metadata set here propagates to every node run, so it is also filterable per node.
        """
        label = " ".join((message or "").split())[:60]
        metadata = {"request_id": request_id, "conversation_id": conversation, "transport": transport}
        if run_id is not None:
            metadata["run_id"] = run_id
        return {"run_name": label or "itinerary turn", "tags": ["itinerary", transport],
                "metadata": metadata}

    async def run(self, planner: ItineraryPlanner, request: dict[str, Any], request_id: str,
                  config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Chạy trọn graph trong giới hạn thời gian của request; hết giờ thì ném TimeoutError."""
        return await asyncio.wait_for(planner.ainvoke(self.inputs(request, request_id), config=config),
                                      timeout=self.request_timeout_seconds)
