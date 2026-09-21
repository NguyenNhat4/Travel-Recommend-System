<<<<<<< HEAD
=======
"""Composition root — nơi duy nhất nối infrastructure vào use case (ARCHITECTURE.md §5).

Gộp hai nhánh: phần nối PostgreSQL (CDP client, catalog lookup, ghi event nền) và engine recsys
(search / similar / recommendations). Recsys chạy thẳng trên database đã seed thay vì đọc file:
`PostgresVectorStore` thay `InMemoryVectorStore`, `PostgresCdpReader` thay `LocalCdpClient` đọc JSONL.

Hai adapter CDP cùng tồn tại vì là hai chiều khác nhau, không phải bản trùng lặp:
  * `clients.LocalCdpClient`  — GHI (async): purchase khi checkout, huỷ bù trừ, browse event, profile.
  * `cdp.PostgresCdpReader`   — ĐỌC (sync): lịch sử của khách và bảng phổ biến cho recsys.
Cả hai đi qua `CDP_DATABASE_URL`; không nơi nào khác được SQL thẳng vào schema `cdp` (AGENTS.md §6.1).

Nạp index tốn thời gian (embed toàn bộ search unit lần đầu, sau đó đọc cache .npy), nên chạy trong
`lifespan` một lần lúc khởi động. Thiếu database thì log rồi bỏ qua phần recsys — các route còn lại
vẫn phục vụ được, đúng tinh thần "CDP lỗi thì không kéo sập cả app" (hop-dong-tich-hop-cdp.md §6).
"""
from __future__ import annotations

import asyncio
import sys
>>>>>>> origin/release-mvp-v1
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.backend.app.api.router import api_router
from src.backend.app.api.v1.routes import recommendations as recommendations_routes
from src.backend.app.api.v1.routes import search as search_routes
from src.backend.app.application.recommendation import BuildPopularity, RecommendForUser
from src.backend.app.application.search import SearchProducts, SimilarProducts
from src.backend.app.core.config import get_settings
from src.backend.app.core.request_context import install_request_id
from src.backend.app.core.settings import settings as recsys_settings
from src.backend.app.infrastructure.cdp.postgres_cdp_reader import PostgresCdpReader
from src.backend.app.infrastructure.clients.cdp_event_dispatcher import BackgroundCdpEventRecorder
from src.backend.app.infrastructure.clients.cdp_http_client import CdpHttpClient
<<<<<<< HEAD
from src.backend.app.infrastructure.clients.itinerary_conversation_store import InMemoryConversationStore
from src.backend.app.infrastructure.clients.itinerary_fixture_clients import FixtureItineraryClients
from src.backend.app.infrastructure.clients.itinerary_http_clients import ItineraryHttpClients
from src.backend.app.application.itinerary.contracts import error_response
from src.backend.app.core.request_context import current_request_id
=======
from src.backend.app.infrastructure.clients.local_cdp_client import LocalCdpClient
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

        embedder = embedder or SentenceTransformersEmbedder(recsys_settings.embed_model)
        # Catalog đi qua DATABASE_URL: role vota_app chỉ SELECT được cdp.products, đúng ranh giới.
        vector_store = PostgresVectorStore(
            settings.database_url, embedder, recsys_settings.embed_cache_dir
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
            cutoff=recsys_settings.search_cutoff,
            max_limit=recsys_settings.search_max_limit,
        ),
        "similar": SimilarProducts(index),
        "recommend": RecommendForUser(
            index, cdp_reader, popularity, candidate_k=recsys_settings.recommend_candidate_k
        ),
    }
>>>>>>> origin/release-mvp-v1


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    async with AsyncExitStack() as stack:
<<<<<<< HEAD
        cdp_http = await stack.enter_async_context(
            httpx.AsyncClient(base_url=settings.cdp_base_url, timeout=settings.cdp_timeout_seconds)
        )
=======
        if settings.cdp_adapter == "local":
            cdp_client = LocalCdpClient(settings.cdp_database_url)
        else:
            cdp_http = await stack.enter_async_context(
                httpx.AsyncClient(base_url=settings.cdp_base_url, timeout=settings.cdp_timeout_seconds)
            )
            cdp_client = CdpHttpClient(cdp_http, settings.cdp_service_token)
>>>>>>> origin/release-mvp-v1
        # Use cases receive these through dependencies; nothing else talks to the CDP.
        app.state.cdp_client = cdp_client
        app.state.product_lookup = PostgresProductLookup(settings.database_url)
        app.state.browse_event_recorder = BackgroundCdpEventRecorder(
            app.state.cdp_client, max_queue=settings.cdp_event_queue_size
        )
        app.state.browse_event_recorder.start()
<<<<<<< HEAD
        app.state.itinerary_conversation_store = InMemoryConversationStore(
            ttl_seconds=settings.itinerary_conversation_ttl_seconds
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
=======

        try:
            for name, service in build_recsys(settings).items():
                setattr(app.state, name, service)
            print(f"RecSys ready: {len(app.state.index.units)} search unit, model {app.state.index.model_version}")
        except Exception as exc:  # database chưa seed, thiếu model embedding…
            app.state.index = None
            print(f"RecSys disabled: {exc}")

>>>>>>> origin/release-mvp-v1
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
install_request_id(app)


@app.exception_handler(RequestValidationError)
async def request_validation_error(_, __):
    request_id = current_request_id() or "validation"
    return JSONResponse(status_code=422, content=error_response(
        "VALIDATION_ERROR", "Yêu cầu không hợp lệ.", request_id
    ))

app.include_router(api_router, prefix="/api/v1")
# Hai router recsys đã tự mang prefix /api/v1 nên mount thẳng vào app,
# nếu đưa vào api_router thì đường dẫn thành /api/v1/api/v1/search.
app.include_router(search_routes.router)
app.include_router(recommendations_routes.router)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
