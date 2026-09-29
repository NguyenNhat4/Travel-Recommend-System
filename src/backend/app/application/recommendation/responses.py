"""Hậu xử lý kết quả `RecommendForUser` thành RecommendationResponse (schemas/recommendations.yaml).

Route `/recommendations` và tool itinerary chạy trong tiến trình cùng dùng, để hai đường trả cùng một shape.
"""
from __future__ import annotations

from time import perf_counter
from typing import Any, Callable


def recommendation_response(recommend: Callable[..., dict[str, Any]], cdp_user_id: str | None, *, k: int,
                            destination: str | None) -> dict[str, Any]:
    started = perf_counter()
    result = recommend(cdp_user_id, k=k, destination=destination)
    result["cdpUserId"] = cdp_user_id
    result.setdefault("diagnostics", {})["latencyMs"] = max(0, round((perf_counter() - started) * 1000))
    return result
