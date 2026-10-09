"""Port sinh giả thuyết query plan bằng LLM cho /search (kiến trúc search §5; contract 1.17.0 `queryPlan.llm`).

Adapter (`infrastructure/llm/query_hypothesis.py`) gọi chat model với structured output; use case chỉ thấy port này.
Giả thuyết là dữ liệu thô của model — `domain/search/hypothesis.validate_hypothesis` kiểm với catalog trước khi dùng.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from src.backend.app.domain.search.hypothesis import QueryHypothesis


class QueryHypothesisPort(Protocol):
    """`hypothesize(query, context)`: `query` = câu đã chuẩn hoá (q'); `context` = tóm tắt plan rule + từ vựng được phép
    (`application/search/query_plan_llm.hypothesis_context`). Trả None khi model không cho được giả thuyết; lỗi mạng /
    provider thì ném — use case bắt và giữ plan rule. Tuỳ chọn `version: str` (model + phiên bản prompt) làm nhãn cache."""

    def hypothesize(self, query: str, context: Mapping[str, Any]) -> QueryHypothesis | None: ...
