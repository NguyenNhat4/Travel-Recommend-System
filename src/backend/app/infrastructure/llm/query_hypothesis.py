"""Adapter `QueryHypothesisPort`: chat model LangChain + structured output → giả thuyết query plan cho /search
(đề xuất đã chốt `docs/prd/update/2026-10-06-search-llm-fallback-query-plan.md`; kiến trúc search §5 "Hợp đồng LLM").

Model chỉ trả JSON theo `HypothesisSchema` (không productId, không xếp hạng); use case kiểm mọi giá trị với catalog trước khi
dùng. Nhiệt độ 0. Chọn provider theo tên model (`gpt-*`/`o*` → OpenAI, `gemini-*` → Gemini, `claude-*` → Anthropic); tên model
lạ → thứ tự key như `client.build_chat_model` (Gemini → OpenAI → Anthropic). `build_chat_model` của Trợ lý không đổi.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

from src.backend.app.domain.search.hypothesis import QueryHypothesis

from .client import ANTHROPIC_DEFAULT_MODEL, GEMINI_DEFAULT_MODEL

#: Đổi prompt / schema → đổi phiên bản: cache đĩa lọc theo tag `<model>|<PROMPT_VERSION>`.
PROMPT_VERSION = "qh-2026-10-06.1"
DEFAULT_MODEL = "gpt-4o-mini"


class HypothesisSchema(BaseModel):
    """Structured output. Mọi trường tuỳ chọn: không chắc thì để null / danh sách rỗng."""
    intent: str | None = Field(None, description="Ý định ngắn gọn, ví dụ hotel_search, flight_search, attraction_search, "
                                                 "combo_search, golf_search, mixed, unknown")
    confidence: float | None = Field(None, description="Độ chắc của chính giả thuyết này, 0..1")
    destination: str | None = Field(None, description="Điểm đến (không phải câu vé máy bay) — đúng chính tả một giá trị "
                                                      "trong danh sách destinations, chỉ khi câu nêu rõ nơi đó")
    taxonomy: str | None = Field(None, description="Đúng MỘT loại sản phẩm câu hỏi: hotel | flight | attraction | combo | "
                                                   "golf; câu hỏi nhiều loại hoặc không rõ thì null")
    origin: str | None = Field(None, description="Câu vé máy bay: thành phố đi, đúng một giá trị trong flightCities")
    destination_city: str | None = Field(None, description="Câu vé máy bay: thành phố đến, đúng một giá trị trong flightCities")
    must_not_amenities: list[str] = Field(default_factory=list, description="Khoá tiện ích câu LOẠI TRỪ rõ ràng "
                                                                            "(\"không có X\", \"trừ X\")")
    must_not_taxonomies: list[str] = Field(default_factory=list, description="Loại sản phẩm câu LOẠI TRỪ rõ ràng")
    price_min: int | None = Field(None, description="Giá tối thiểu, VND nguyên")
    price_max: int | None = Field(None, description="Giá tối đa, VND nguyên (\"dưới 2 triệu\" → 2000000)")
    star_min: float | None = Field(None, description="Hạng sao tối thiểu 1..5")
    party_total: int | None = Field(None, description="Tổng số khách khi câu nêu số người")
    soft_preferences: list[str] = Field(default_factory=list, description="Mong muốn mềm (view biển, yên tĩnh…), tự do")
    unknown_slots: list[str] = Field(default_factory=list, description="Ràng buộc câu nêu mà không map được vào trường nào")


_SYSTEM = """Bạn là bộ phân tích câu tìm kiếm của một sàn du lịch Việt Nam (khách sạn, vé máy bay, vé tham quan, combo, golf).
Nhiệm vụ: đọc câu khách gõ và trả về MỘT giả thuyết JSON có cấu trúc về các ràng buộc cứng của câu.

Quy tắc bắt buộc:
- KHÔNG bao giờ trả mã sản phẩm, tên sản phẩm cụ thể hay thứ hạng kết quả. Chỉ điền các trường của schema.
- Chỉ điền khi câu nói RÕ. Không chắc, không có trong câu, hoặc phải đoán → để null / danh sách rỗng. Bỏ trống tốt hơn đoán sai.
- Giá trị phải lấy ĐÚNG chính tả từ danh sách được phép bên dưới; giá trị ngoài danh sách sẽ bị loại.
- taxonomy: chỉ khi câu hỏi đúng MỘT loại sản phẩm. Câu hỏi nhiều loại ("khách sạn và vé máy bay") → null.
  Combo đứng đầu câu ("combo vé máy bay + khách sạn") là combo.
- destination: điểm đến của câu thường (không phải vé máy bay). Câu nêu nhiều nơi ngang hàng ("A hoặc B") → null.
  Tên thương hiệu chứa địa danh (ví dụ "Saigon …" ở Đà Lạt) không phải điểm đến.
- origin / destination_city: CHỈ cho câu vé máy bay; thiếu nơi đi thì để null, không đoán.
- must_not_amenities / must_not_taxonomies: CHỈ khi câu loại trừ rõ ("không có", "không gồm", "trừ", "không phải").
  "Không cần / không nhất thiết X" KHÔNG phải loại trừ.
- price_min / price_max: VND nguyên ("dưới 2 triệu" → price_max 2000000; "từ 500k" → price_min 500000).
- star_min: chỉ khi câu nêu số sao. party_total: tổng số khách khi câu nêu số người.
- Ràng buộc câu nêu mà không map được vào trường nào → ghi vào unknown_slots (văn bản ngắn).
- confidence: độ chắc của bạn với toàn bộ giả thuyết (0..1).

Danh sách được phép:
- taxonomy: {taxonomies}
- destinations: {destinations}
- flightCities: {flight_cities}
- khoá tiện ích (khoá: cụm khách hay gõ): {amenities}"""


def system_prompt(context: Mapping[str, Any]) -> str:
    vocab = context.get("vocab") or {}
    amen = vocab.get("amenities") or {}
    return _SYSTEM.format(
        taxonomies=", ".join(vocab.get("taxonomies") or ()),
        destinations="; ".join(vocab.get("destinations") or ()) or "(trống)",
        flight_cities="; ".join(vocab.get("flightCities") or ()) or "(trống)",
        amenities="; ".join(f"{k}: {v}" for k, v in amen.items()) or "(trống)",
    )


def user_prompt(query: str, context: Mapping[str, Any]) -> str:
    rule = {k: v for k, v in (context.get("rule") or {}).items() if v not in (None, [], "")}
    parts = [f"Câu (đã chuẩn hoá): {query}"]
    if context.get("rawQuery"):
        parts.append(f"Câu gốc: {context['rawQuery']}")
    parts.append("Bộ phân tích luật đã hiểu (có thể thiếu hoặc không chắc): "
                 + json.dumps(rule, ensure_ascii=False, sort_keys=True))
    return "\n".join(parts)


def _as_mapping(out: Any) -> Mapping[str, Any] | None:
    if out is None:
        return None
    if hasattr(out, "model_dump"):
        return out.model_dump()
    if isinstance(out, Mapping):
        return out
    if isinstance(out, str):
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, Mapping) else None
    return None


class LangChainQueryHypothesizer:
    """`hypothesize(query, context)` → `QueryHypothesis` | None. `chat_model`: bất kỳ chat model LangChain nào có
    `with_structured_output` (test tiêm model giả, không gọi mạng)."""

    def __init__(self, chat_model: Any, *, model_name: str, method: str | None = None):
        # `method`: cách structured output của LangChain (None = mặc định của provider; "function_calling" nếu provider
        # không nhận json_schema có trường tuỳ chọn)
        kw = {"method": method} if method else {}
        self._structured = chat_model.with_structured_output(HypothesisSchema, **kw)
        self.model_name = model_name
        self.version = f"{model_name}|{PROMPT_VERSION}"

    def hypothesize(self, query: str, context: Mapping[str, Any]) -> QueryHypothesis | None:
        messages = [("system", system_prompt(context)), ("human", user_prompt(query, context))]
        data = _as_mapping(self._structured.invoke(messages))
        return QueryHypothesis.from_mapping(data) if data is not None else None


def _provider(model: str, *, openai_api_key: str, gemini_api_key: str, anthropic_api_key: str) -> str:
    m = model.lower()
    if m.startswith(("gpt", "o1", "o3", "o4", "chatgpt")):
        return "openai"
    if m.startswith("gemini"):
        return "gemini"
    if m.startswith("claude"):
        return "anthropic"
    for name, key in (("gemini", gemini_api_key), ("openai", openai_api_key), ("anthropic", anthropic_api_key)):
        if key:
            return name
    return "openai"


def build_query_hypothesizer(*, model: str = DEFAULT_MODEL, openai_api_key: str = "", gemini_api_key: str = "",
                             anthropic_api_key: str = "", timeout_seconds: float = 5.0,
                             max_retries: int = 0) -> LangChainQueryHypothesizer:
    """Dựng adapter thật. Raise RuntimeError khi thiếu API key của provider hoặc thiếu SDK — composition root quyết định
    (thường: log cảnh báo, chạy không adapter → `queryPlan.llm.status = unavailable`)."""
    model = model or DEFAULT_MODEL
    provider = _provider(model, openai_api_key=openai_api_key, gemini_api_key=gemini_api_key,
                         anthropic_api_key=anthropic_api_key)
    if provider == "openai":
        if not openai_api_key:
            raise RuntimeError("SEARCH_LLM_FALLBACK cần OPENAI_API_KEY cho model " + model)
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-openai") from exc
        chat = ChatOpenAI(model=model, api_key=openai_api_key, temperature=0, timeout=timeout_seconds,
                          max_retries=max_retries)
    elif provider == "gemini":
        if not gemini_api_key:
            raise RuntimeError("SEARCH_LLM_FALLBACK cần GEMINI_API_KEY cho model " + model)
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-google-genai") from exc
        chat = ChatGoogleGenerativeAI(model=model or GEMINI_DEFAULT_MODEL, google_api_key=gemini_api_key, temperature=0,
                                      timeout=timeout_seconds, max_retries=max_retries)
    else:
        if not anthropic_api_key:
            raise RuntimeError("SEARCH_LLM_FALLBACK cần ANTHROPIC_API_KEY cho model " + model)
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-anthropic") from exc
        chat = ChatAnthropic(model=model or ANTHROPIC_DEFAULT_MODEL, api_key=anthropic_api_key, temperature=0,
                             timeout=timeout_seconds, max_retries=max_retries)
    return LangChainQueryHypothesizer(chat, model_name=model)


def query_hypothesizer_from_settings(settings: Any) -> LangChainQueryHypothesizer:
    """Đọc `search_llm_fallback_model` + API key của `Settings` (core/config.py). Hạn gọi model = hạn chờ của request ×2
    (lượt quá hạn vẫn chạy nốt để ghi cache), tối thiểu 3 s."""
    timeout_ms = int(getattr(settings, "search_llm_fallback_timeout_ms", 1500))
    return build_query_hypothesizer(
        model=getattr(settings, "search_llm_fallback_model", DEFAULT_MODEL) or DEFAULT_MODEL,
        openai_api_key=getattr(settings, "openai_api_key", "") or "",
        gemini_api_key=getattr(settings, "gemini_api_key", "") or "",
        anthropic_api_key=getattr(settings, "anthropic_api_key", "") or "",
        timeout_seconds=max(3.0, 2 * timeout_ms / 1000.0),
    )
