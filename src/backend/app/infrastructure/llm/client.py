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
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-20250514"


def chat_model_name(settings: Settings) -> str | None:
    """Model thực sự được dùng: `ITINERARY_LLM_MODEL`, bỏ trống thì mặc định của provider được chọn."""
    if settings.itinerary_llm_model:
        return settings.itinerary_llm_model
    if settings.gemini_api_key:
        return GEMINI_DEFAULT_MODEL
    if settings.openai_api_key:
        return OPENAI_DEFAULT_MODEL
    if settings.anthropic_api_key:
        return ANTHROPIC_DEFAULT_MODEL
    return None


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
        return FunctionCallingModel(ChatGoogleGenerativeAI(
            model=model or GEMINI_DEFAULT_MODEL,
            google_api_key=settings.gemini_api_key,
            temperature=temperature,
        ), "gemini")

    if settings.openai_api_key:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-openai") from exc
        return FunctionCallingModel(ChatOpenAI(
            model=model or OPENAI_DEFAULT_MODEL,
            api_key=settings.openai_api_key,
            temperature=temperature,
            # None = không gửi tham số, giữ nguyên hành vi mặc định của model.
            reasoning_effort=settings.itinerary_llm_reasoning_effort,
        ), "openai")

    if settings.anthropic_api_key:
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-anthropic") from exc
        return FunctionCallingModel(ChatAnthropic(
            model=model or ANTHROPIC_DEFAULT_MODEL,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
        ), "anthropic")

    raise RuntimeError(
        "No LLM API key found. Set GEMINI_API_KEY, OPENAI_API_KEY or ANTHROPIC_API_KEY in .env, "
        "or set ITINERARY_USE_LLM=false to run without an LLM. See .env.example."
    )


class StructuredOrchestratorModel:
    """Force native JSON-schema output for OpenAI; and bind native function tools for v2."""
    def __init__(self, model):
        self.model = model

    def with_structured_output(self, schema):
        return self.model.with_structured_output(schema, method="json_schema", strict=True)

    def bind_tools(self, tools, *, tool_choice=None, parallel_tool_calls=None, strict=None):
        return FunctionCallingModel(self.model, "openai").bind_tools(
            tools, tool_choice=tool_choice, parallel_tool_calls=parallel_tool_calls, strict=strict)


def strict_parameters(schema: dict) -> dict:
    """OpenAI strict: tất cả properties required; field optional chuyển thành nullable, không đổi schema gốc."""
    from copy import deepcopy
    result = deepcopy(schema)
    def visit(node):
        if not isinstance(node, dict):
            return
        if "properties" in node:
            required = set(node.get("required", []))
            for key, value in node["properties"].items():
                if key not in required:
                    kind = value.get("type")
                    if kind:
                        value["type"] = list(dict.fromkeys((kind if isinstance(kind, list) else [kind]) + ["null"]))
                        if "enum" in value and None not in value["enum"]:
                            value["enum"].append(None)
                    else:
                        old = deepcopy(value)
                        value.clear()
                        value["anyOf"] = [old, {"type": "null"}]
                visit(value)
            node["required"] = list(node["properties"])
            node["additionalProperties"] = False
        for key in ("items",):
            visit(node.get(key))
        for key in ("anyOf", "oneOf"):
            for child in node.get(key, []):
                visit(child)
    visit(result)
    return result


class FunctionCallingModel:
    """Chuẩn hoá tuỳ chọn provider; SDK chỉ ở infrastructure."""
    def __init__(self, model, provider):
        self.model, self.provider = model, provider

    def __getattr__(self, name):
        return getattr(self.model, name)

    def bind_tools(self, tools, *, tool_choice=None, parallel_tool_calls=None, strict=None):
        from copy import deepcopy
        definitions = deepcopy(tools)
        if strict is None and parallel_tool_calls is None:
            # Legacy v1 binds plain gateway definitions with provider defaults, unchanged.
            return self.model.bind_tools(definitions, tool_choice=tool_choice)
        if self.provider == "openai":
            for tool in definitions:
                function = tool.get("function", tool)
                function["parameters"] = strict_parameters(function["parameters"])
            # Reasoning models support function tools via Responses, not Chat Completions (live 400).
            # Clone per binding so the shared v1 JSON-schema model keeps its original transport/config.
            model = self.model
            name = getattr(model, "model_name", None)
            if isinstance(name, str) and name.startswith(("gpt-6", "gpt-5", "o1", "o3", "o4")):
                model = model.model_copy(update={"use_responses_api": True})
            return model.bind_tools(definitions, tool_choice=tool_choice, strict=strict,
                                    parallel_tool_calls=parallel_tool_calls)
        # Gemini/Anthropic dùng any để bắt buộc gọi tool; vẫn kiểm schema local.
        options = {"tool_choice": "any" if tool_choice == "required" else tool_choice}
        if self.provider == "anthropic":
            options["parallel_tool_calls"] = parallel_tool_calls
        return self.model.bind_tools(definitions, **options)


def build_orchestrator_model(settings: Settings, shared_model: Any | None) -> Any | None:
    """Build the explicitly selected provider/model; the composition root handles safe fallback."""
    if not settings.itinerary_use_llm or not settings.itinerary_orchestrator_model:
        return shared_model
    provider = settings.itinerary_orchestrator_provider
    model = settings.itinerary_orchestrator_model
    temperature = settings.itinerary_llm_temperature
    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("Orchestrator OpenAI key is not configured")
        from langchain_openai import ChatOpenAI
        kwargs = {"model": model, "api_key": settings.openai_api_key, "max_retries": 0}
        effort = settings.itinerary_orchestrator_reasoning_effort
        if model.startswith("gpt-6.1-sol") and effort in ("none", "minimal"):
            raise RuntimeError("GPT-6.1 Sol does not support none/minimal reasoning")
        if effort:
            kwargs["reasoning_effort"] = effort
        # Reasoning models reject sampling parameters; measure effort/latency separately in B12.
        if not model.startswith(("gpt-6", "gpt-5", "o1", "o3", "o4")):
            kwargs["temperature"] = temperature
        return StructuredOrchestratorModel(ChatOpenAI(**kwargs))
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("Orchestrator Gemini key is not configured")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return FunctionCallingModel(ChatGoogleGenerativeAI(model=model, google_api_key=settings.gemini_api_key,
                                                         temperature=temperature), "gemini")
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("Orchestrator Anthropic key is not configured")
        from langchain_anthropic import ChatAnthropic
        return FunctionCallingModel(ChatAnthropic(model=model, api_key=settings.anthropic_api_key,
                                                 temperature=temperature), "anthropic")
    raise RuntimeError("Set ITINERARY_ORCHESTRATOR_PROVIDER explicitly when selecting a model")
