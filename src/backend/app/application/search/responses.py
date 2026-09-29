"""Payload của tool `search_products` cho Itinerary Agent, dựng từ kết quả Search."""
from __future__ import annotations

from typing import Any

# Metadata riêng của engine trên GET /search, không thuộc SearchResponse ổn định mà Agent tiêu thụ.
SEARCH_ENGINE_ONLY_FIELDS = frozenset({"cutoff", "diagnostics"})


def search_tool_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Tool chỉ giữ các trường SearchResponse ổn định mà Agent thực sự tiêu thụ.

    Adapter HTTP và adapter trong tiến trình cùng dùng, để hai đường trả cùng một shape.
    """
    return {key: value for key, value in data.items() if key not in SEARCH_ENGINE_ONLY_FIELDS}
