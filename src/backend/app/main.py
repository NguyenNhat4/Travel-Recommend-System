"""Composition root — nơi duy nhất nối infrastructure vào use case (docs/prd/architecture.md §2).

Gộp hai nhánh: phần nối PostgreSQL (CDP client, catalog lookup, ghi event nền) và engine recsys
(search / similar / recommendations). `WeaviateVectorStore` lấy vector đã persist, hydrate sản phẩm từ
PostgreSQL; `PostgresCdpReader` đọc lịch sử. Cả hai thay các bản giả ở `tests/fakes/`.

Hai adapter CDP trong `infrastructure/cdp/` cùng tồn tại vì là hai chiều khác nhau, không phải bản trùng lặp:
  * `LocalCdpClient`     — GHI (async): purchase khi checkout, huỷ bù trừ, browse event, profile.
  * `PostgresCdpReader`  — ĐỌC (sync): lịch sử của khách và bảng phổ biến cho recsys.
Cả hai đi qua `CDP_DATABASE_URL`; không nơi nào khác được SQL thẳng vào schema `cdp` (AGENTS.md §6.1).

Nạp index từ collection `Product` của Weaviate trong `lifespan` một lần lúc khởi động. Thiếu database,
Weaviate hoặc index thì log rồi bỏ qua phần recsys — các route còn lại
vẫn phục vụ được, đúng tinh thần "CDP lỗi thì không kéo sập cả app" (hop-dong-tich-hop-cdp.md §6).
"""
from __future__ import annotations

import asyncio
import logging
import os
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
from src.backend.app.infrastructure.llm import build_chat_model
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore
from src.backend.app.infrastructure.persistence.postgres_catalog import PostgresProductLookup

logger = logging.getLogger("uvicorn.error")

# psycopg async không chạy được trên ProactorEventLoop — event loop mặc định của Windows và của
# uvicorn trên Windows. Phải đặt trước khi uvicorn tạo loop, nếu không mọi truy cập cdp.* qua
# LocalCdpClient trả InterfaceError lúc chạy thật. Trên Linux/macOS dòng này không có tác dụng gì.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def build_recsys(settings, embedder=None, vector_store=None, cdp_reader=None) -> dict:
    """Dựng engine recsys trên database đã seed.

    Ba tham số override để test tiêm giả lập mà không cần Postgres hay tải model embedding.
    """
    owns_embedder = False
    if vector_store is None:
        from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION
        from src.backend.app.infrastructure.embeddings.cohere_embedder import CohereEmbedder
        from src.backend.app.infrastructure.vectors.weaviate_store import WeaviateClient, WeaviateVectorStore

        if embedder is None:
            embedder = CohereEmbedder(
                settings.cohere_api_key,
                settings.embed_model,
                base_url=settings.cohere_base_url,
                dimension=settings.embed_dimension,
                timeout_seconds=settings.cohere_timeout_seconds,
            )
            owns_embedder = True
        weaviate = WeaviateClient(
            settings.weaviate_url,
            collection=settings.weaviate_collection,
            api_key=settings.weaviate_api_key,
            timeout_seconds=settings.weaviate_timeout_seconds,
        )
        vector_store = WeaviateVectorStore(
            settings.database_url,
            weaviate,
            expected_model_version=f"{settings.embed_model}:{TEXT_BUILDER_VERSION}",
            dimension=settings.embed_dimension,
        )
    logger.info("startup.recsys.index.load.start source=weaviate")
    try:
        index = vector_store.load()
    except Exception:
        if owns_embedder and hasattr(embedder, "close"):
            embedder.close()
        raise
    finally:
        client = getattr(vector_store, "client", None)
        if client is not None:
            client.close()
    logger.info("startup.recsys.index.load.ready search_units=%d", len(index.units))

    # Lịch sử đi qua CDP_DATABASE_URL: vota_app không đọc được cdp.events.
    cdp_reader = cdp_reader or PostgresCdpReader(settings.cdp_database_url)
    logger.info("startup.recsys.popularity.build.start")
    popularity = BuildPopularity(index, cdp_reader)()
    logger.info("startup.recsys.popularity.build.ready")
    return {
        "recsys_embedder": embedder,
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


def _itinerary_runtime(app: FastAPI, settings: Settings, authorization: str | None):
    """Dựng dependency của agent cho một request. Đọc `app.state` lúc gọi để test thay được client/LLM."""
    clients = getattr(app.state, "itinerary_http_clients", None)
    store = getattr(app.state, "itinerary_conversation_store", None)
    if clients is None or store is None:
        return None
    catalog = clients if getattr(clients, "supports_catalog", False) else None
    gateway = ItineraryToolGateway(clients, clients, catalog, recommendation_authorization=authorization)
    return RuntimeAgentDependencies(
        gateway, store, getattr(app.state, "itinerary_llm", None), authorization,
        tool_timeout_seconds=settings.itinerary_tool_timeout_seconds,
        llm_timeout_seconds=settings.itinerary_llm_timeout_seconds,
    )


def _itinerary_planner(app: FastAPI, settings: Settings, authorization: str | None):
    runtime = _itinerary_runtime(app, settings, authorization)
    return runtime.planner() if runtime is not None else None


def _forward_langsmith_env(settings) -> None:
    """Đẩy đúng 4 biến LangSmith vào os.environ khi được bật chủ ý qua Settings.

    LangSmith SDK (bên trong `with_structured_output`/`bind_tools` của LangChain) tự đọc thẳng
    os.environ, không biết gì về Settings — không có cách nào truyền config vào nó qua tham số.
    Trước đây agents/llm.py:_load_local_env() đẩy TOÀN BỘ .env vào os.environ lúc import module,
    nên các biến này bật một cách âm thầm dù không ai chủ ý cấu hình. Ở đây chỉ đẩy đúng 4 biến,
    chỉ khi LANGSMITH_TRACING=true và có key, và chỉ ở composition root — bật là quyết định rõ
    ràng, không phải tác dụng phụ của việc đọc .env.
    """
    if not settings.langsmith_tracing:
        return
    if not settings.langsmith_api_key:
        print("LangSmith tracing bật nhưng thiếu LANGSMITH_API_KEY; bỏ qua.")
        return
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    print(f"LangSmith tracing: on (project={settings.langsmith_project})")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    _forward_langsmith_env(settings)
    logger.info("startup.begin app=%s env=%s", settings.app_name, settings.app_env)
    async with AsyncExitStack() as stack:
        logger.info("startup.cdp_adapter.start adapter=%s", settings.cdp_adapter)
        if settings.cdp_adapter == "local":
            cdp_client = LocalCdpClient(settings.cdp_database_url)
        else:
            cdp_http = await stack.enter_async_context(
                httpx.AsyncClient(base_url=settings.cdp_base_url, timeout=settings.cdp_timeout_seconds)
            )
            cdp_client = CdpHttpClient(cdp_http, settings.cdp_service_token)
        logger.info("startup.cdp_adapter.ready adapter=%s", settings.cdp_adapter)
        # Use cases receive these through dependencies; nothing else talks to the CDP.
        app.state.cdp_client = cdp_client
        app.state.product_lookup = PostgresProductLookup(settings.database_url)
        app.state.browse_event_recorder = BackgroundCdpEventRecorder(
            app.state.cdp_client, max_queue=settings.cdp_event_queue_size
        )
        logger.info("startup.browse_event_recorder.start")
        app.state.browse_event_recorder.start()
        logger.info("startup.browse_event_recorder.ready")
        app.state.itinerary_conversation_store = InMemoryConversationStore(
            ttl_seconds=settings.itinerary_conversation_ttl_seconds
        )
        app.state.plan_itinerary = PlanItinerary(
            lambda authorization: _itinerary_planner(app, settings, authorization),
            settings.itinerary_request_timeout_seconds,
        )
        mode = settings.itinerary_data_mode or ("fixture" if settings.app_env in {"development", "test"} else "disabled")
        app.state.itinerary_data_mode = mode
        logger.info("startup.itinerary_clients.start mode=%s", mode)
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
        logger.info("startup.itinerary_clients.ready mode=%s", mode)

        # Một client LLM dùng chung cho mọi request thay vì dựng lại trong từng node. LLM tách khỏi
        # phần dữ liệu: thiếu API key hoặc tắt hẳn thì chỉ itinerary trả 503 LLM_UNAVAILABLE, các
        # route khác và /assistant/status vẫn phục vụ được.
        try:
            app.state.itinerary_llm = build_chat_model(settings)
            app.state.itinerary_llm_mode = "live" if app.state.itinerary_llm else "disabled"
        except Exception as exc:  # thiếu API key, thiếu SDK của provider…
            app.state.itinerary_llm = None
            app.state.itinerary_llm_mode = "unavailable"
            print(f"Itinerary LLM unavailable: {exc}")
        print(f"Itinerary LLM: {app.state.itinerary_llm_mode}")

        # Recsys tách khỏi phần itinerary: thiếu database hoặc model embedding thì tắt recsys,
        # các route còn lại (kể cả assistant chạy fixture) vẫn phục vụ được.
        try:
            logger.info("startup.recsys.start model=%s", settings.embed_model)
            for name, service in build_recsys(settings).items():
                setattr(app.state, name, service)
            print(f"RecSys ready: {len(app.state.index.units)} search unit, model {app.state.index.model_version}")
            logger.info("startup.recsys.ready search_units=%d", len(app.state.index.units))
        except Exception as exc:  # database chưa seed, thiếu model embedding…
            app.state.index = None
            print(f"RecSys disabled: {exc}")
            logger.exception("startup.recsys.disabled error=%s", exc)

        logger.info("startup.ready")
        try:
            yield
        finally:
            embedder = getattr(app.state, "recsys_embedder", None)
            if embedder is not None and hasattr(embedder, "close"):
                embedder.close()
            logger.info("shutdown.browse_event_recorder.stop")
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
