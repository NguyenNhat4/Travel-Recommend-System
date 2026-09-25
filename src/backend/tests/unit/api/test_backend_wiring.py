import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.backend.app.core.config import Settings, get_settings
from src.backend.app.infrastructure.cdp.local_cdp_client import LocalCdpClient
from src.backend.app.infrastructure.persistence.postgres_catalog import PostgresProductLookup
from src.backend.app.application.itinerary.use_cases import PlanItinerary
from src.backend.app.main import _forward_langsmith_env, _itinerary_runtime, app, health, lifespan


def test_default_composition_root_uses_local_postgres_adapters() -> None:
    async def scenario() -> None:
        async with lifespan(app):
            assert (await health())["status"] == "ok"
            assert any(getattr(route, "path", None) == "/health" for route in app.routes)
            assert isinstance(app.state.cdp_client, LocalCdpClient)
            assert isinstance(app.state.product_lookup, PostgresProductLookup)

    asyncio.run(scenario())


class ItineraryLlmWiringTests(unittest.TestCase):
    """Composition root phải dựng client LLM một lần và không được sập khi thiếu API key.

    Trước bản sửa này `app.state.itinerary_llm` không bao giờ được gán, nên route luôn truyền
    llm=None xuống graph và mỗi node tự dựng một client mới. Test cuối khoá lại đúng điều đó.
    """

    def run_lifespan(self, **overrides):
        """Chạy lifespan thật với Settings đã ghi đè, trả về (llm, llm_mode)."""
        # get_settings có lru_cache; patch thẳng hàm để không rò cấu hình sang test khác.
        settings = get_settings().model_copy(update=overrides)
        with patch("src.backend.app.main.get_settings", return_value=settings):
            async def scenario():
                async with lifespan(app):
                    return app.state.itinerary_llm, app.state.itinerary_llm_mode
            return asyncio.run(scenario())

    def test_switch_off_leaves_no_client_and_reports_disabled(self):
        llm, mode = self.run_lifespan(itinerary_use_llm=False)
        self.assertIsNone(llm)
        self.assertEqual(mode, "disabled")

    def test_missing_api_key_does_not_break_startup(self):
        """Thiếu key chỉ làm itinerary trả 503; app và các route khác vẫn phải khởi động."""
        llm, mode = self.run_lifespan(itinerary_use_llm=True, openai_api_key="",
                                      gemini_api_key="", anthropic_api_key="")
        self.assertIsNone(llm)
        self.assertEqual(mode, "unavailable")

    def test_configured_key_produces_one_client_shared_by_every_request(self):
        built = []

        def fake_build(settings: Settings):
            built.append(settings)
            return SimpleNamespace(name="chat-model")

        with patch("src.backend.app.main.build_chat_model", fake_build):
            llm, mode = self.run_lifespan(itinerary_use_llm=True, openai_api_key="sk-test")
        self.assertEqual(mode, "live")
        self.assertIsNotNone(llm)
        # Dựng đúng một lần cho cả vòng đời process, không phải một lần cho mỗi node.
        self.assertEqual(len(built), 1)

        fake_app = SimpleNamespace(state=SimpleNamespace(
            itinerary_http_clients=SimpleNamespace(), itinerary_conversation_store=SimpleNamespace(),
            itinerary_llm=llm))
        settings = Settings()
        first = _itinerary_runtime(fake_app, settings, None)
        second = _itinerary_runtime(fake_app, settings, "Bearer x")
        self.assertIs(first.llm, llm)
        self.assertIs(second.llm, llm)


class LangSmithForwardingTests(unittest.TestCase):
    """Chỉ 4 biến LANGSMITH_* được đẩy vào os.environ, và chỉ khi bật chủ ý.

    Trước bản sửa lỗi #2, `_load_local_env()` cũ đẩy TOÀN BỘ `.env` vào `os.environ` lúc import,
    nên tracing bật một cách âm thầm. `_forward_langsmith_env` thay nó bằng một hành động tường
    minh trong composition root, giới hạn đúng 4 biến LangSmith cần.
    """

    LANGSMITH_KEYS = ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_ENDPOINT", "LANGSMITH_PROJECT")

    def setUp(self):
        self._saved = {key: os.environ.pop(key, None) for key in self.LANGSMITH_KEYS}
        self.addCleanup(self._restore)

    def _restore(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_does_nothing_when_tracing_is_off(self):
        _forward_langsmith_env(Settings(langsmith_tracing=False, langsmith_api_key="lsv2_x"))
        self.assertNotIn("LANGSMITH_TRACING", os.environ)

    def test_does_nothing_when_tracing_is_on_but_key_is_missing(self):
        _forward_langsmith_env(Settings(langsmith_tracing=True, langsmith_api_key=""))
        self.assertNotIn("LANGSMITH_TRACING", os.environ)

    def test_forwards_exactly_the_four_langsmith_vars_when_explicitly_enabled(self):
        _forward_langsmith_env(Settings(langsmith_tracing=True, langsmith_api_key="lsv2_x",
                                        langsmith_endpoint="https://example.test",
                                        langsmith_project="demo"))
        self.assertEqual(os.environ["LANGSMITH_TRACING"], "true")
        self.assertEqual(os.environ["LANGSMITH_API_KEY"], "lsv2_x")
        self.assertEqual(os.environ["LANGSMITH_ENDPOINT"], "https://example.test")
        self.assertEqual(os.environ["LANGSMITH_PROJECT"], "demo")


class TraceConfigTests(unittest.TestCase):
    """Mỗi lượt phải tự nhận diện được trong LangSmith.

    Không có config thì mọi trace tên "LangGraph" và không mang request id, nên một lượt
    quan sát được trên UI demo không dò ngược ra trace của nó. Tên run lấy từ chính câu
    người dùng gõ — dữ liệu này graph đã ghi làm input, không lộ thêm gì.
    """

    @staticmethod
    def _config(message, *args, **kwargs):
        return PlanItinerary.trace_config(message, *args, **kwargs)

    def test_run_is_named_after_the_user_message_and_carries_the_request_id(self):
        config = self._config("đi Nha Trang 2 ngày", "req-1", "conv-9", transport="sse",
                               run_id="run-7")
        self.assertEqual(config["run_name"], "đi Nha Trang 2 ngày")
        self.assertEqual(config["metadata"], {"request_id": "req-1", "conversation_id": "conv-9",
                                              "transport": "sse", "run_id": "run-7"})
        self.assertEqual(config["tags"], ["itinerary", "sse"])

    def test_name_survives_a_blank_multiline_or_overlong_message(self):
        self.assertEqual(self._config("  ", "r", "c", transport="json")["run_name"],
                         "itinerary turn")
        self.assertEqual(self._config("đi\n\n  Huế", "r", "c", transport="json")["run_name"],
                         "đi Huế")
        long_name = self._config("x" * 200, "r", "c", transport="json")["run_name"]
        self.assertEqual(len(long_name), 60)

    def test_json_transport_has_no_run_id(self):
        self.assertNotIn("run_id", self._config("x", "r", "c", transport="json")["metadata"])


if __name__ == "__main__":
    unittest.main()
