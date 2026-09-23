"""FastAPI dependency: lấy use case mà composition root (`main.py`) đã nối sẵn vào `app.state`.

Route chỉ nhận use case qua `Depends`, không tự dựng adapter hay agent (docs/prd/architecture.md §2, quy tắc 8).
"""
from typing import Any

from fastapi import Request

from src.backend.app.application.itinerary.use_cases import PlanItinerary


def get_plan_itinerary(request: Request) -> PlanItinerary:
    return request.app.state.plan_itinerary


def get_search(request: Request) -> Any:
    """None khi recsys bị tắt lúc khởi động; route search trả trang rỗng thay vì 500."""
    return getattr(request.app.state, "search", None)


def get_similar(request: Request) -> Any:
    return request.app.state.similar


def get_recommend(request: Request) -> Any:
    return request.app.state.recommend
