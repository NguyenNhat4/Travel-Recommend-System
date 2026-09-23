"""Adapter LLM provider cho agent itinerary (port `application/ports/llm.py`).

`get_llm()` chọn provider theo API key có trong môi trường. Agent không import file này: `main.py` đưa
`LazyChatModel` vào graph, nên thiếu key chỉ làm node trả `LLM_UNAVAILABLE` lúc gọi, không chặn khởi động.
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_local_env() -> None:
    """Load simple KEY=value entries without requiring a runtime dependency."""
    env_file = Path(__file__).resolve().parents[5] / ".env"  # repo root
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


_load_local_env()


def get_llm(model: str | None = None, temperature: float = 0.0):
    """Create an LLM client from environment configuration.

    Checks for API keys in this order:
    1. GEMINI_API_KEY → ChatGoogleGenerativeAI
    2. OPENAI_API_KEY → ChatOpenAI
    3. ANTHROPIC_API_KEY → ChatAnthropic

    Override model with the `model` parameter or LLM_MODEL env var.
    """
    if os.getenv("GEMINI_API_KEY"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-google-genai") from exc
        return ChatGoogleGenerativeAI(
            model=model or os.getenv("LLM_MODEL", "gemini-2.5-flash"),
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=temperature,
        )

    if os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-openai") from exc
        return ChatOpenAI(
            model=model or os.getenv("ITINERARY_LLM_MODEL") or os.getenv("LLM_MODEL") or os.getenv("MODEL_NAME", "gpt-4o-mini"),
            temperature=temperature,
        )

    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-anthropic") from exc
        return ChatAnthropic(
            model=model or os.getenv("LLM_MODEL", "claude-sonnet-4-20250514"),
            temperature=temperature,
        )

    raise RuntimeError(
        "No LLM API key found. Set GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY in .env\n"
        "See .env.example for configuration."
    )


class LazyChatModel:
    """Tạo client mới qua `get_llm()` ở mỗi lời gọi, giống hành vi cũ `llm or get_llm()` trong node."""

    def with_structured_output(self, schema):
        return get_llm().with_structured_output(schema)

    def bind_tools(self, tools):
        return get_llm().bind_tools(tools)
