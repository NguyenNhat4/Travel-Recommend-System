"""Entry cho LangGraph Studio: dựng graph itinerary với tool và LLM theo `.env`, chỉ để dev.

Chạy từ repo root: `.venv-studio/bin/langgraph dev` (đọc `langgraph.json`), rồi mở link Studio mà lệnh in ra.
Nguồn dữ liệu cho tool theo `ITINERARY_DATA_MODE` như backend, bỏ trống thì `inprocess`:
- `inprocess`: engine Search/Recommendation/Similar/catalog thật, dựng một lần lúc nạp graph bằng `build_recsys`
  và `build_catalog` của `main.py` — cần Postgres đã seed, Weaviate đã index và model e5 local.
- `fixture`: 50 sản phẩm `src/shared/mocks/itinerary-agent/products.json`, không cần Postgres hay Weaviate.
LLM dựng như backend (`build_chat_model`). Studio không gửi Bearer nên `get_recommendations` chạy như khách.
Lượt đầu chỉ gửi `{"query": "3 ngày ở Nha Trang cho gia đình"}` (id tự đặt chưa tồn tại thì intake trả
`CONVERSATION_NOT_FOUND`); lượt sau gửi thêm `conversation_id` lấy từ output lượt trước để intake nạp lại intent.
"""
from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.backend.app.agents.graph import build_graph  # noqa: E402
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway  # noqa: E402
from src.backend.app.core.config import get_settings  # noqa: E402
from src.backend.app.infrastructure.llm import build_chat_model  # noqa: E402
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore  # noqa: E402

# Store sống theo tiến trình `langgraph dev`, như store in-memory của backend khi chạy dev.
_STORE = InMemoryConversationStore()
# Engine nạp catalog + index mất vài giây; Studio có thể gọi factory nhiều lần nên giữ lại theo tiến trình.
_CLIENTS: dict[str, object] = {}
_CLIENTS_LOCK = asyncio.Lock()


def _inprocess_clients(settings):
    from src.backend.app.application.itinerary.engine_tools import InProcessItineraryTools
    from src.backend.app.main import ITINERARY_TOOL_WORKERS, build_catalog, build_recsys

    state = SimpleNamespace(**build_recsys(settings))
    for name, service in build_catalog(settings, state).items():
        setattr(state, name, service)
    pool = ThreadPoolExecutor(max_workers=ITINERARY_TOOL_WORKERS, thread_name_prefix="itinerary-tool")
    return InProcessItineraryTools(
        search=lambda: state.search,
        recommend=lambda: state.recommend,
        index=lambda: state.index,
        product_detail=lambda: state.get_product_detail,
        similar_products=lambda: state.get_similar_products,
        token_verifier=lambda: None,  # không có Bearer: tool recommendation trả gợi ý cho khách
        revoked_tokens=lambda: None,
        executor=pool,
    )


def _clients(settings):
    mode = settings.itinerary_data_mode or "inprocess"
    if mode not in _CLIENTS:
        if mode == "inprocess":
            _CLIENTS[mode] = _inprocess_clients(settings)
        elif mode == "fixture":
            from src.backend.app.infrastructure.clients.itinerary_fixture_clients import FixtureItineraryClients

            _CLIENTS[mode] = FixtureItineraryClients()
        else:
            raise RuntimeError(f"ITINERARY_DATA_MODE={mode} chưa hỗ trợ trong Studio; dùng inprocess hoặc fixture")
        print(f"LangGraph Studio: itinerary tools mode={mode}")
    return _CLIENTS[mode]


async def make_graph():
    """Graph compile không checkpointer: Studio tự gắn checkpointer của nó cho từng thread.

    Factory async vì `langgraph dev` chặn lời gọi I/O đồng bộ trên event loop (blockbuster): dựng engine
    (kết nối Weaviate, Postgres) chạy trong thread.
    """
    settings = get_settings()
    async with _CLIENTS_LOCK:
        clients = await asyncio.to_thread(_clients, settings)
    tools = ItineraryToolGateway(clients, clients, clients, similar=clients)
    return build_graph(tools=tools, llm=build_chat_model(settings), store=_STORE, owner="studio",
                       tool_timeout_seconds=settings.itinerary_tool_timeout_seconds,
                       llm_timeout_seconds=settings.itinerary_llm_timeout_seconds)
