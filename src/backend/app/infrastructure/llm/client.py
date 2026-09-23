"""Adapter dựng chat model. SDK của provider chỉ được import ở đây (docs/prd/architecture.md §2).

Composition root gọi `build_chat_model` một lần trong lifespan và dùng chung client cho mọi
request: các lớp chat model của LangChain chỉ giữ cấu hình bất biến cộng một client httpx có
connection pool, còn `with_structured_output()`/`bind_tools()` trả về object mới chứ không sửa
model gốc — nên phần theo-request đã nằm ở chỗ khác (gateway mang Authorization, graph mang owner).
"""
from __future__ import annotations

from typing import Any, Literal

from src.backend.app.core.config import Settings

LlmMode = Literal["live", "disabled", "unavailable"]

GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-20250514"


def build_chat_model(settings: Settings) -> Any | None:
    """Dựng một chat model theo API key có sẵn, hoặc None khi ITINERARY_USE_LLM=false.

    Thứ tự provider: Gemini → OpenAI → Anthropic. Raise RuntimeError khi đã bật LLM nhưng
    không có key nào hoặc thiếu SDK của provider được chọn; người gọi tự quyết định điều đó
    có phải lỗi chí mạng hay không.
    """
    if not settings.itinerary_use_llm:
        return None

    model = settings.itinerary_llm_model
    temperature = settings.itinerary_llm_temperature

    # Import trong từng nhánh: thiếu package chỉ làm hỏng đúng provider đang được chọn.
    if settings.gemini_api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-google-genai") from exc
        return ChatGoogleGenerativeAI(
            model=model or GEMINI_DEFAULT_MODEL,
            google_api_key=settings.gemini_api_key,
            temperature=temperature,
        )

    if settings.openai_api_key:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-openai") from exc
        return ChatOpenAI(
            model=model or settings.model_name,
            api_key=settings.openai_api_key,
            temperature=temperature,
        )

    if settings.anthropic_api_key:
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-anthropic") from exc
        return ChatAnthropic(
            model=model or ANTHROPIC_DEFAULT_MODEL,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
        )

    raise RuntimeError(
        "No LLM API key found. Set GEMINI_API_KEY, OPENAI_API_KEY or ANTHROPIC_API_KEY in .env, "
        "or set ITINERARY_USE_LLM=false to run without an LLM. See .env.example."
    )
