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
from src.backend.app.infrastructure.llm import build_chat_model, chat_model_name


def settings(**overrides) -> Settings:
    base = {
        "itinerary_use_llm": True,
        "openai_api_key": "",
        "gemini_api_key": "",
        "anthropic_api_key": "",
        "itinerary_llm_model": None,
        "itinerary_llm_temperature": 0.0,
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
        self.assertEqual(llm.model.provider, "ChatGoogleGenerativeAI")
        self.assertEqual(calls[0]["google_api_key"], "g")
        self.assertEqual(calls[0]["model"], "gemini-2.5-flash")

    def test_openai_wins_over_anthropic(self):
        mock, calls = fake_sdk("langchain_openai", "ChatOpenAI")
        with mock:
            llm = build_chat_model(settings(openai_api_key="o", anthropic_api_key="a"))
        self.assertEqual(llm.model.provider, "ChatOpenAI")
        self.assertEqual(calls[0]["api_key"], "o")

    def test_anthropic_is_the_last_resort(self):
        mock, calls = fake_sdk("langchain_anthropic", "ChatAnthropic")
        with mock:
            llm = build_chat_model(settings(anthropic_api_key="a"))
        self.assertEqual(llm.model.provider, "ChatAnthropic")
        self.assertEqual(calls[0]["api_key"], "a")

    def test_openai_uses_its_default_then_honours_itinerary_llm_model(self):
        mock, calls = fake_sdk("langchain_openai", "ChatOpenAI")
        with mock:
            build_chat_model(settings(openai_api_key="o"))
            build_chat_model(settings(openai_api_key="o", itinerary_llm_model="gpt-4.1"))
        self.assertEqual([call["model"] for call in calls], ["gpt-4o-mini", "gpt-4.1"])

    def test_openai_reasoning_effort_is_forwarded_only_when_set(self):
        """Model reasoning từ chối function tools khi reasoning bật mặc định; None thì không gửi gì."""
        mock, calls = fake_sdk("langchain_openai", "ChatOpenAI")
        with mock:
            build_chat_model(settings(openai_api_key="o"))
            build_chat_model(settings(openai_api_key="o", itinerary_llm_reasoning_effort="none"))
        self.assertEqual([call["reasoning_effort"] for call in calls], [None, "none"])

    def test_chat_model_name_reports_the_model_build_chat_model_uses(self):
        self.assertEqual(chat_model_name(settings(openai_api_key="o")), "gpt-4o-mini")
        self.assertEqual(chat_model_name(settings(gemini_api_key="g", openai_api_key="o")), "gemini-2.5-flash")
        self.assertEqual(chat_model_name(settings(openai_api_key="o", itinerary_llm_model="gpt-4.1")), "gpt-4.1")
        self.assertIsNone(chat_model_name(settings()))

    def test_temperature_comes_from_the_itinerary_specific_setting(self):
        """Agent chỉ gọi structured output/tool calling, không dùng chung llm_temperature=0.7."""
        mock, calls = fake_sdk("langchain_openai", "ChatOpenAI")
        with mock:
            build_chat_model(settings(openai_api_key="o", llm_temperature=0.7))
        self.assertEqual(calls[0]["temperature"], 0.0)


if __name__ == "__main__":
    unittest.main()


class OrchestratorModelTests(unittest.TestCase):
    def build(self, **overrides):
        from src.backend.app.infrastructure.llm import build_orchestrator_model
        return build_orchestrator_model(settings(**overrides), "shared")

    def test_disabled_llm_or_blank_model_reuses_shared_model(self):
        from src.backend.app.infrastructure.llm import build_orchestrator_model
        self.assertEqual(self.build(itinerary_orchestrator_model=None), "shared")
        self.assertEqual(build_orchestrator_model(settings(itinerary_use_llm=False, itinerary_orchestrator_model="gpt-6.1-sol"), "shared"), "shared")

    def test_explicit_openai_provider_wins_even_when_common_provider_is_gemini(self):
        mock, calls = fake_sdk("langchain_openai", "ChatOpenAI")
        with mock:
            result = self.build(openai_api_key="o", gemini_api_key="g", itinerary_orchestrator_model="gpt-6.1-sol",
                                itinerary_orchestrator_provider="openai", itinerary_orchestrator_reasoning_effort="low")
        self.assertEqual(result.model.model, "gpt-6.1-sol")
        self.assertNotIn("temperature", calls[0])
        self.assertEqual(calls[0]["reasoning_effort"], "low")
        self.assertEqual(calls[0]["max_retries"], 0)

    def test_model_selection_requires_explicit_provider_and_matching_key(self):
        for provider in (None, "openai", "gemini", "anthropic"):
            with self.subTest(provider=provider), self.assertRaises(RuntimeError):
                self.build(itinerary_orchestrator_model="gpt-6.1-sol", itinerary_orchestrator_provider=provider)

    def test_gpt_61_sol_rejects_unsupported_reasoning_effort(self):
        for effort in ("none", "minimal"):
            with self.subTest(effort=effort), self.assertRaises(RuntimeError):
                self.build(openai_api_key="o", itinerary_orchestrator_model="gpt-6.1-sol",
                           itinerary_orchestrator_provider="openai", itinerary_orchestrator_reasoning_effort=effort)

    def test_openai_uses_native_schema_without_function_tools(self):
        from unittest.mock import Mock

        from src.backend.app.infrastructure.llm.client import (
            StructuredOrchestratorModel,
        )
        inner = Mock()
        adapter = StructuredOrchestratorModel(inner)
        adapter.with_structured_output("schema")
        inner.with_structured_output.assert_called_once_with("schema", method="json_schema", strict=True)

    def test_empty_optional_env_fields_are_none(self):
        value = settings(itinerary_orchestrator_model="", itinerary_orchestrator_provider="", itinerary_orchestrator_reasoning_effort="")
        self.assertIsNone(value.itinerary_orchestrator_model)
        self.assertIsNone(value.itinerary_orchestrator_provider)
        self.assertIsNone(value.itinerary_orchestrator_reasoning_effort)

    def test_orchestrator_binds_function_tools(self):
        from unittest.mock import Mock

        from src.backend.app.infrastructure.llm.client import (
            StructuredOrchestratorModel,
        )
        inner = Mock()
        StructuredOrchestratorModel(inner).bind_tools([], tool_choice="required", strict=True, parallel_tool_calls=True)
        inner.bind_tools.assert_called_once_with([], tool_choice="required", strict=True, parallel_tool_calls=True)


def test_openai_reasoning_function_binding_clones_transport_only():
    from unittest.mock import Mock

    from src.backend.app.infrastructure.llm.client import FunctionCallingModel
    inner=Mock(); inner.model_name='gpt-6-luna'; clone=inner.model_copy.return_value
    FunctionCallingModel(inner,'openai').bind_tools([],tool_choice='required',strict=True,parallel_tool_calls=True)
    inner.model_copy.assert_called_once_with(update={'use_responses_api':True})
    clone.bind_tools.assert_called_once_with([],tool_choice='required',strict=True,parallel_tool_calls=True)
    inner.bind_tools.assert_not_called()


def test_provider_tool_options_do_not_send_openai_strict_to_other_providers():
    from unittest.mock import Mock

    from src.backend.app.infrastructure.llm.client import FunctionCallingModel
    for provider in ('gemini','anthropic'):
        inner=Mock()
        FunctionCallingModel(inner,provider).bind_tools([],tool_choice='required',strict=True,parallel_tool_calls=True)
        kwargs={'tool_choice':'any', **({'parallel_tool_calls':True} if provider=='anthropic' else {})}
        inner.bind_tools.assert_called_once_with([],**kwargs)


def test_legacy_plain_tool_definitions_keep_provider_defaults():
    from unittest.mock import Mock

    from src.backend.app.infrastructure.llm.client import FunctionCallingModel
    inner=Mock()
    definitions=[{'name':'search_products','description':'Search','parameters':{'type':'object'}}]
    FunctionCallingModel(inner,'openai').bind_tools(definitions,tool_choice='any')
    inner.bind_tools.assert_called_once_with(definitions,tool_choice='any')
    inner.model_copy.assert_not_called()
