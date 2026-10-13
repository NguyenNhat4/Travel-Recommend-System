"""Hậu xử lý kết quả `RecommendForUser` thành RecommendationResponse (schemas/recommendations.yaml).

Route `/recommendations` và tool itinerary chạy trong tiến trình cùng dùng, để hai đường trả cùng một shape.
"""
from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Callable

from src.backend.app.core.logging_config import log_event

logger = logging.getLogger(__name__)

#: Khoá `diagnostics` chỉ dành cho engine: thời gian từng bước, kết quả tra cache, số event đã đọc. Ghi vào log
#: `recsys.recommend`, không trả ra API (contract không khai), theo tiền lệ các trường chỉ dành cho engine của Search.
ENGINE_ONLY_DIAGNOSTICS = ("stageMs", "cacheOutcome", "eventsRead")


def recommendation_response(recommend: Callable[..., dict[str, Any]], cdp_user_id: str | None, *, k: int,
                            destination: str | None) -> dict[str, Any]:
    started = perf_counter()
    result = recommend(cdp_user_id, k=k, destination=destination)
    result["cdpUserId"] = cdp_user_id
    latency = max(0, round((perf_counter() - started) * 1000))
    diagnostics = result.setdefault("diagnostics", {})
    engine_only = {key: diagnostics.pop(key) for key in ENGINE_ONLY_DIAGNOSTICS if key in diagnostics}
    diagnostics["latencyMs"] = latency
    strategy = result.get("strategy")
    log_event(logger, "recsys.recommend", persona="user" if cdp_user_id else "guest", branch=strategy,
              result_count=len(result.get("recommendations") or []), duration_ms=latency,
              cache=engine_only.get("cacheOutcome"), stage_ms=engine_only.get("stageMs"),
              events_read=engine_only.get("eventsRead"))
    if cdp_user_id and strategy == "popular":  # có người dùng mà vẫn rơi về popular: cold-start hoặc CDP lỗi
        log_event(logger, "recsys.fallback", reason="popular", persona="user")
    return result
