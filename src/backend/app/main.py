"""Composition root — nơi duy nhất nối infrastructure vào use case (docs/prd/architecture.md §2).

Gộp hai nhánh: phần nối PostgreSQL (CDP client, catalog lookup, ghi event nền) và engine recsys
(search / similar / recommendations). Recsys chạy thẳng trên database đã seed thay vì đọc file:
`PostgresVectorStore` và `PostgresCdpReader` thay các bản giả đọc JSONL ở `tests/fakes/`.

Hai adapter CDP trong `infrastructure/cdp/` cùng tồn tại vì là hai chiều khác nhau, không phải bản trùng lặp:
  * `LocalCdpClient`     — GHI (async): purchase khi checkout, huỷ bù trừ, browse event, profile.
  * `PostgresCdpReader`  — ĐỌC (sync): lịch sử của khách và bảng phổ biến cho recsys.
Cả hai đi qua `CDP_DATABASE_URL`; không nơi nào khác được SQL thẳng vào schema `cdp` (AGENTS.md §6.1).

Nạp index tốn thời gian (embed toàn bộ search unit lần đầu, sau đó đọc cache .npy), nên chạy trong
`lifespan` một lần lúc khởi động. Thiếu database thì log rồi bỏ qua phần recsys — các route còn lại
vẫn phục vụ được, đúng tinh thần "CDP lỗi thì không kéo sập cả app" (hop-dong-tich-hop-cdp.md §6).
"""
from __future__ import annotations

import asyncio
import sys
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
from fastapi import FastAPI

from src.backend.app.agents.runtime_dependencies import RuntimeAgentDependencies
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.api.errors import install_error_handlers
from src.backend.app.api.middleware import install_cors, install_request_id
from src.backend.app.api.v1.router import api_router
from src.backend.app.application.itinerary.use_cases import PlanItinerary
from src.backend.app.application.recommendation import BuildPopularity, RecommendForUser
from src.backend.app.application.search import SearchProducts, SimilarProducts
from src.backend.app.core.config import Settings, get_settings
from src.backend.app.infrastructure.cdp.event_dispatcher import BackgroundCdpEventRecorder
from src.backend.app.infrastructure.cdp.http_cdp_client import CdpHttpClient
from src.backend.app.infrastructure.cdp.local_cdp_client import LocalCdpClient
from src.backend.app.infrastructure.cdp.postgres_cdp_reader import PostgresCdpReader
from src.backend.app.infrastructure.clients.itinerary_fixture_clients import FixtureItineraryClients
from src.backend.app.infrastructure.clients.itinerary_http_clients import ItineraryHttpClients
from src.backend.app.infrastructure.llm.client import LazyChatModel
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore
from src.backend.app.infrastructure.persistence.postgres_catalog import PostgresProductLookup

# psycopg async không chạy được trên ProactorEventLoop — event loop mặc định của Windows và của
# uvicorn trên Windows. Phải đặt trước khi uvicorn tạo loop, nếu không mọi truy cập cdp.* qua
# LocalCdpClient trả InterfaceError lúc chạy thật. Trên Linux/macOS dòng này không có tác dụng gì.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def build_recsys(settings, embedder=None, vector_store=None, cdp_reader=None) -> dict:
    """Dựng engine recsys trên database đã seed.

    Ba tham số override để test tiêm giả lập mà không cần Postgres hay tải model embedding.
    """
    if vector_store is None:
        from src.backend.app.infrastructure.embeddings.sentence_transformers_embedder import (
            SentenceTransformersEmbedder,
        )
        from src.backend.app.infrastructure.vectors.postgres_store import PostgresVectorStore

        embedder = embedder or SentenceTransformersEmbedder(settings.embed_model)
        # Catalog đi qua DATABASE_URL: role vota_app chỉ SELECT được cdp.products, đúng ranh giới.
        vector_store = PostgresVectorStore(
            settings.database_url, embedder, settings.embed_cache_dir
        )
    index = vector_store.load()

    # Lịch sử đi qua CDP_DATABASE_URL: vota_app không đọc được cdp.events.
    cdp_reader = cdp_reader or PostgresCdpReader(settings.cdp_database_url)
    popularity = BuildPopularity(index, cdp_reader)()
    return {
        "index": index,
        "search": SearchProducts(
            index,
            embedder,
            cutoff=settings.search_cutoff,
            max_limit=settings.search_max_limit,
        ),
        "similar": SimilarProducts(index),
        "recommend": RecommendForUser(
            index, cdp_reader, popularity, candidate_k=settings.recommend_candidate_k
        ),
    }


def _itinerary_planner(app: FastAPI, settings: Settings, authorization: str | None):
    """Dựng agent cho một request. Đọc `app.state` lúc gọi để test thay được client/LLM sau khi khởi động."""
    clients = getattr(app.state, "itinerary_http_clients", None)
    store = getattr(app.state, "itinerary_conversation_store", None)
    if clients is None or store is None:
        return None
    gateway = ItineraryToolGateway(clients, clients, clients, recommendation_authorization=authorization)
    return RuntimeAgentDependencies(
        gateway, store, getattr(app.state, "itinerary_llm", None), authorization,
        tool_timeout_seconds=settings.itinerary_tool_timeout_seconds,
        llm_timeout_seconds=settings.itinerary_llm_timeout_seconds,
    ).planner()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    async with AsyncExitStack() as stack:
        if settings.cdp_adapter == "local":
            cdp_client = LocalCdpClient(settings.cdp_database_url)
        else:
            cdp_http = await stack.enter_async_context(
                httpx.AsyncClient(base_url=settings.cdp_base_url, timeout=settings.cdp_timeout_seconds)
            )
            cdp_client = CdpHttpClient(cdp_http, settings.cdp_service_token)
        # Use cases receive these through dependencies; nothing else talks to the CDP.
        app.state.cdp_client = cdp_client
        app.state.product_lookup = PostgresProductLookup(settings.database_url)
        app.state.browse_event_recorder = BackgroundCdpEventRecorder(
            app.state.cdp_client, max_queue=settings.cdp_event_queue_size
        )
        app.state.browse_event_recorder.start()
        app.state.itinerary_conversation_store = InMemoryConversationStore(
            ttl_seconds=settings.itinerary_conversation_ttl_seconds
        )
        app.state.itinerary_llm = LazyChatModel()
        app.state.plan_itinerary = PlanItinerary(
            lambda authorization: _itinerary_planner(app, settings, authorization),
            settings.itinerary_request_timeout_seconds,
        )
        mode = settings.itinerary_data_mode or ("fixture" if settings.app_env in {"development", "test"} else "disabled")
        app.state.itinerary_data_mode = mode
        if mode == "fixture":
            app.state.itinerary_http_clients = FixtureItineraryClients()
        elif mode == "http":
            if not settings.itinerary_service_base_url:
                raise RuntimeError("ITINERARY_SERVICE_BASE_URL is required when ITINERARY_DATA_MODE=http")
            itinerary_http = await stack.enter_async_context(httpx.AsyncClient(
                base_url=settings.itinerary_service_base_url.rstrip("/") + "/api/v1/",
                timeout=settings.itinerary_tool_timeout_seconds,
            ))
            app.state.itinerary_http_clients = ItineraryHttpClients(itinerary_http)
        else:
            app.state.itinerary_http_clients = None

        # Recsys tách khỏi phần itinerary: thiếu database hoặc model embedding thì tắt recsys,
        # các route còn lại (kể cả assistant chạy fixture) vẫn phục vụ được.
        try:
            for name, service in build_recsys(settings).items():
                setattr(app.state, name, service)
            print(f"RecSys ready: {len(app.state.index.units)} search unit, model {app.state.index.model_version}")
        except Exception as exc:  # database chưa seed, thiếu model embedding…
            app.state.index = None
            print(f"RecSys disabled: {exc}")

        try:
            yield
        finally:
            await app.state.browse_event_recorder.stop()
    print("Shutting down...")


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    description="Travel recommendation and itinerary API",
    version="1.4.0",
    lifespan=lifespan,
)

install_cors(app, settings.cors_origins)
install_request_id(app)
install_error_handlers(app)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
