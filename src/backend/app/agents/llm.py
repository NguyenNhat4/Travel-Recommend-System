"""Nhánh dự phòng dựng LLM cho các node.

Việc chọn provider và dựng SDK nằm ở `infrastructure/llm` (ARCHITECTURE.md §5, §12); module này
chỉ chuyển nó về đúng dạng không-tham-số mà các node gọi khi không được tiêm sẵn client.

Đường chạy bình thường là composition root tiêm `app.state.itinerary_llm` vào graph, nên hàm dưới
đây chỉ chạy ở CLI, ở test, hoặc khi LLM bị tắt — lúc đó nó raise và node `classify` biến lỗi này
thành 503 LLM_UNAVAILABLE có kiểm soát.
"""

from __future__ import annotations

from typing import Any

from src.backend.app.core.config import get_settings
from src.backend.app.infrastructure.llm import build_chat_model


def get_llm(model: str | None = None, temperature: float | None = None) -> Any:
    """Dựng một client LLM từ Settings; raise khi không có LLM để dùng."""
    settings = get_settings()
    overrides = {"itinerary_llm_model": model, "itinerary_llm_temperature": temperature}
    overrides = {key: value for key, value in overrides.items() if value is not None}
    if overrides:
        settings = settings.model_copy(update=overrides)
    llm = build_chat_model(settings)
    if llm is None:
        raise RuntimeError("LLM is disabled (ITINERARY_USE_LLM=false).")
    return llm
