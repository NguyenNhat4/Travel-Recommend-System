import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.backend.app.core.config import Settings, get_settings
from src.backend.app.infrastructure.clients.local_cdp_client import LocalCdpClient
from src.backend.app.infrastructure.persistence.postgres_catalog import PostgresProductLookup
from src.backend.app.main import app, health, lifespan


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

        from src.backend.app.api.v1.routes.assistant import _runtime

        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
            itinerary_http_clients=SimpleNamespace(), itinerary_conversation_store=SimpleNamespace(),
            itinerary_llm=llm)))
        first, second = _runtime(request, None), _runtime(request, "Bearer x")
        self.assertIs(first.llm, llm)
        self.assertIs(second.llm, llm)


if __name__ == "__main__":
    unittest.main()
