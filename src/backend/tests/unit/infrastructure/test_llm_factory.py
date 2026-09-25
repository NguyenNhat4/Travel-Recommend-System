"""Adapter dựng chat model: chọn provider, tôn trọng công tắc tắt, và tự truyền API key.

Test không gọi provider thật; nó thay hàm khởi tạo của SDK bằng bản ghi lại tham số, nên vừa
kiểm được nhánh nào chạy vừa kiểm được tham số nào đi vào SDK. Phần cuối là quan trọng nhất:
bỏ `_load_local_env()` nghĩa là không còn ai đẩy API key vào `os.environ`, nên adapter buộc
phải truyền `api_key`/`google_api_key` tường minh.
"""
from __future__ import annotations

import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from src.backend.app.core.config import Settings
from src.backend.app.infrastructure.llm import build_chat_model


def settings(**overrides) -> Settings:
    base = {
        "itinerary_use_llm": True,
        "openai_api_key": "",
        "gemini_api_key": "",
        "anthropic_api_key": "",
        "itinerary_llm_model": None,
        "itinerary_llm_temperature": 0.0,
        "model_name": "gpt-4o-mini",
        # Không đọc .env của máy đang chạy: test phải quyết định hết cấu hình.
        "_env_file": None,
    }
    return Settings(**{**base, **overrides})


def fake_sdk(module_name: str, class_name: str):
    """Thay module SDK bằng một module giả ghi lại kwargs của lần khởi tạo."""
    calls: list[dict] = []
    module = ModuleType(module_name)
    setattr(module, class_name, lambda **kwargs: calls.append(kwargs) or SimpleNamespace(
        provider=class_name, **kwargs))
    return patch.dict(sys.modules, {module_name: module}), calls


class BuildChatModelTests(unittest.TestCase):
    def test_returns_none_when_llm_is_switched_off(self):
        """ITINERARY_USE_LLM=false phải tắt trước khi hỏi tới API key."""
        self.assertIsNone(build_chat_model(settings(itinerary_use_llm=False, openai_api_key="sk-x")))

    def test_raises_when_enabled_without_any_key(self):
        with self.assertRaises(RuntimeError) as caught:
            build_chat_model(settings())
        self.assertIn("ITINERARY_USE_LLM=false", str(caught.exception))

    def test_gemini_wins_over_openai_and_anthropic(self):
        mock, calls = fake_sdk("langchain_google_genai", "ChatGoogleGenerativeAI")
        with mock:
            llm = build_chat_model(settings(gemini_api_key="g", openai_api_key="o", anthropic_api_key="a"))
        self.assertEqual(llm.provider, "ChatGoogleGenerativeAI")
        self.assertEqual(calls[0]["google_api_key"], "g")
        self.assertEqual(calls[0]["model"], "gemini-2.5-flash")

    def test_openai_wins_over_anthropic(self):
        mock, calls = fake_sdk("langchain_openai", "ChatOpenAI")
        with mock:
            llm = build_chat_model(settings(openai_api_key="o", anthropic_api_key="a"))
        self.assertEqual(llm.provider, "ChatOpenAI")
        self.assertEqual(calls[0]["api_key"], "o")

    def test_anthropic_is_the_last_resort(self):
        mock, calls = fake_sdk("langchain_anthropic", "ChatAnthropic")
        with mock:
            llm = build_chat_model(settings(anthropic_api_key="a"))
        self.assertEqual(llm.provider, "ChatAnthropic")
        self.assertEqual(calls[0]["api_key"], "a")

    def test_openai_falls_back_to_model_name_then_honours_itinerary_llm_model(self):
        mock, calls = fake_sdk("langchain_openai", "ChatOpenAI")
        with mock:
            build_chat_model(settings(openai_api_key="o", model_name="gpt-4o-mini"))
            build_chat_model(settings(openai_api_key="o", model_name="gpt-4o-mini",
                                      itinerary_llm_model="gpt-4.1"))
        self.assertEqual([call["model"] for call in calls], ["gpt-4o-mini", "gpt-4.1"])

    def test_temperature_comes_from_the_itinerary_specific_setting(self):
        """Agent chỉ gọi structured output/tool calling, không dùng chung llm_temperature=0.7."""
        mock, calls = fake_sdk("langchain_openai", "ChatOpenAI")
        with mock:
            build_chat_model(settings(openai_api_key="o", llm_temperature=0.7))
        self.assertEqual(calls[0]["temperature"], 0.0)


if __name__ == "__main__":
    unittest.main()
