"""Composition root — nơi duy nhất nối infrastructure vào use case (docs/prd/architecture.md §2).

Gộp hai nhánh: phần nối PostgreSQL (CDP client, catalog lookup, ghi event nền) và engine recsys
(search / similar / recommendations). `WeaviateVectorStore` nạp metadata search unit từ PostgreSQL và
trả kho vector Weaviate để mỗi request truy vấn top-K; `PostgresCdpReader` đọc lịch sử. Cả hai thay các bản giả ở `tests/fakes/`.

Hai adapter CDP trong `infrastructure/cdp/` cùng tồn tại vì là hai chiều khác nhau, không phải bản trùng lặp:
  * `LocalCdpClient`     — GHI (async): purchase khi checkout, huỷ bù trừ, browse event, profile.
  * `PostgresCdpReader`  — ĐỌC (sync): lịch sử của khách và bảng phổ biến cho recsys.
Cả hai đi qua `CDP_DATABASE_URL`; không nơi nào khác được SQL thẳng vào schema `cdp` (AGENTS.md §6.1).

Nạp metadata search unit lúc khởi động rồi nạp lại mỗi `CATALOG_REFRESH_SECONDS`; vector ở lại Weaviate.
Lần nạp lại lỗi thì giữ bản đang phục vụ. Chưa nạp được lần nào (thiếu database, Weaviate hoặc index) thì log
rồi bỏ qua phần recsys — các route còn lại vẫn phục vụ được, đúng tinh thần "CDP lỗi thì không kéo sập cả app"
(hop-dong-tich-hop-cdp.md §6).
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
from src.backend.app.api.v1.router import api_router, root_router
from src.backend.app.application.auth.use_cases import (
    AuthenticateUser,
    ChangePassword,
    GetCurrentUser,
    RegisterUser,
    RevokeSession,
    RotateSession,
)
from src.backend.app.application.itinerary.use_cases import PlanItinerary
from src.backend.app.application.recommendation import BuildPopularity, RecommendForUser
from src.backend.app.application.search import SearchProducts, SimilarProducts
from src.backend.app.core.config import REPO_ROOT, Settings, get_settings
from src.backend.app.infrastructure.auth.argon2_hasher import Argon2Hasher
from src.backend.app.infrastructure.auth.jwt_issuer import JwtConfig, JwtIssuer
from src.backend.app.infrastructure.auth.keys import load_rsa_pem_pair
from src.backend.app.infrastructure.auth.postgres_login_attempts import PostgresLoginAttemptLog
from src.backend.app.infrastructure.auth.postgres_refresh_tokens import PostgresRefreshTokenStore
from src.backend.app.infrastructure.auth.postgres_user_repository import PostgresUserRepository
from src.backend.app.infrastructure.auth.rate_limiter import InMemoryRateLimiter, RedisRateLimiter
from src.backend.app.infrastructure.auth.revoked_tokens import NoRevokedTokens, RedisRevokedTokens
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
    owns_vector_store = vector_store is None
    try:
        if vector_store is None:
            from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION
            from src.backend.app.infrastructure.embeddings.cohere_embedder import CohereEmbedder
            from src.backend.app.infrastructure.vectors.weaviate_store import (
                WeaviateVectorSearch,
                WeaviateVectorStore,
                connect_weaviate,
            )

            if embedder is None:
                embedder = CohereEmbedder(
                    settings.cohere_api_key,
                    settings.embed_model,
                    base_url=settings.cohere_base_url,
                    dimension=settings.embed_dimension,
                    timeout_seconds=settings.cohere_timeout_seconds,
                )
                owns_embedder = True
            vector_store = WeaviateVectorStore(
                settings.database_url,
                WeaviateVectorSearch(
                    connect_weaviate(
                        settings.weaviate_url,
                        api_key=settings.weaviate_api_key,
                        grpc_port=settings.weaviate_grpc_port,
                        timeout_seconds=settings.weaviate_timeout_seconds,
                    ),
                    collection=settings.weaviate_collection,
                    dimension=settings.embed_dimension,
                ),
                expected_model_version=f"{settings.embed_model}:{TEXT_BUILDER_VERSION}",
            )
        logger.info("startup.recsys.index.load.start source=weaviate")
        index, vector_search = vector_store.load()
    except Exception:
        if owns_embedder and hasattr(embedder, "close"):
            embedder.close()
        search_store = getattr(vector_store, "search", None)
        if owns_vector_store and search_store is not None and hasattr(search_store, "close"):
            search_store.close()
        raise
    logger.info("startup.recsys.index.load.ready search_units=%d", len(index.units))

    # Lịch sử đi qua CDP_DATABASE_URL: vota_app không đọc được cdp.events.
    cdp_reader = cdp_reader or PostgresCdpReader(settings.cdp_database_url)
    logger.info("startup.recsys.popularity.build.start")
    popularity = BuildPopularity(index, cdp_reader)()
    logger.info("startup.recsys.popularity.build.ready")
    return {
        "recsys_embedder": embedder,
        "recsys_vectors": vector_search,
        "recsys_store": vector_store,
        "index": index,
        "search": SearchProducts(
            index,
            vector_search,
            embedder,
            cutoff=settings.search_cutoff,
            max_limit=settings.search_max_limit,
            candidate_k=settings.search_candidate_k,
        ),
        "similar": SimilarProducts(index, vector_search),
        "recommend": RecommendForUser(
            index, vector_search, cdp_reader, popularity, candidate_k=settings.recommend_candidate_k
        ),
    }


#: Chưa nạp được lần nào (database chưa seed, Weaviate chưa index…) thì thử lại sớm, không chờ trọn chu kỳ.
RECSYS_RETRY_SECONDS = 30.0


class RecsysRefresher:
    """Nạp lại engine recsys theo chu kỳ để giá, trạng thái và cửa sổ ngày theo kịp job cào.

    Client Cohere/Weaviate dùng chung giữa các lần nạp; request đang chạy giữ use case của bản cũ nên không
    client nào bị đóng giữa chừng. Lần nạp lại lỗi thì giữ bản đang phục vụ thay vì tắt recsys.
    """

    def __init__(self, app: FastAPI, settings: Settings, build=None):
        self.app, self.settings = app, settings
        self._build = build  # test tiêm bản giả; mặc định là build_recsys
        self.services: dict = {}
        self._failures = 0
        self._stop = asyncio.Event()

    async def reload(self) -> bool:
        first = not self.services
        try:
            updated = await asyncio.to_thread(
                self._build or build_recsys, self.settings,
                self.services.get("recsys_embedder"), self.services.get("recsys_store"),
            )
        except Exception as exc:  # database chưa seed, Weaviate chưa index, lỗi mạng…
            self._failures += 1
            if not first:
                logger.warning("catalog.refresh.failed error=%s; giữ bản đang phục vụ", exc)
            elif self._failures == 1:
                print(f"RecSys disabled: {exc}")
                logger.warning("startup.recsys.disabled error=%s; retry_seconds=%s", exc, RECSYS_RETRY_SECONDS)
            else:  # vẫn chưa lên: không lặp cảnh báo mỗi 30 giây
                logger.debug("startup.recsys.retry_failed error=%s", exc)
            return False
        self._failures = 0
        self.services = updated
        for name, service in updated.items():  # không có await giữa các phép gán: request thấy trọn một bản
            setattr(self.app.state, name, service)
        if first:
            print(f"RecSys ready: {len(updated['index'].units)} search unit, model {updated['index'].model_version}")
            logger.info("startup.recsys.ready search_units=%d", len(updated["index"].units))
        else:
            logger.info("catalog.refresh.ready search_units=%d", len(updated["index"].units))
        return True

    async def run(self) -> None:
        while not self._stop.is_set():
            delay = self.settings.catalog_refresh_seconds
            if not self.services:
                delay = min(delay, RECSYS_RETRY_SECONDS)
            try:
                await asyncio.wait_for(self._stop.wait(), delay)
            except asyncio.TimeoutError:
                await self.reload()

    def stop(self) -> None:
        self._stop.set()

    def close(self) -> None:
        for name in ("recsys_embedder", "recsys_vectors"):
            resource = self.services.get(name)
            if resource is not None and hasattr(resource, "close"):
                resource.close()


def build_auth(settings: Settings, cdp_client, redis_client=None) -> dict:
    """Dựng use case auth (docs/spec/hop-dong-tich-hop-auth.md). Trả dict để lifespan gắn vào app.state.

    Production bắt buộc có file khoá RS256 và Redis; dev/test được dùng khoá tạm và rate limiter
    trong bộ nhớ để chạy được không cần hạ tầng.
    """
    is_production = settings.app_env == "production"
    private_pem, public_pem = load_rsa_pem_pair(
        settings.jwt_private_key_path, settings.jwt_public_key_path,
        base_dir=REPO_ROOT, allow_ephemeral=not is_production,
    )
    issuer = JwtIssuer(JwtConfig(
        private_key=private_pem, public_key=public_pem, issuer=settings.jwt_issuer,
        audience=settings.jwt_audience, access_ttl_seconds=settings.jwt_access_ttl_seconds,
        leeway_seconds=settings.jwt_clock_skew_seconds,
    ))
    if redis_client is not None:
        limiter = RedisRateLimiter(redis_client)
        revoked = RedisRevokedTokens(redis_client)
    elif is_production:
        raise RuntimeError("AUTH_REDIS_URL là bắt buộc khi APP_ENV=production")
    else:
        logger.warning("auth.ratelimit.in_memory — AUTH_REDIS_URL trống, bộ đếm chỉ sống trong tiến trình này")
        limiter = InMemoryRateLimiter()
        revoked = NoRevokedTokens()

    users = PostgresUserRepository(settings.database_url)
    hasher = Argon2Hasher(
        memory_kib=settings.argon2_memory_kib, time_cost=settings.argon2_time_cost,
        parallelism=settings.argon2_parallelism,
    )
    refresh = PostgresRefreshTokenStore(settings.database_url, ttl_seconds=settings.refresh_ttl_seconds)
    return {
        "token_verifier": issuer,
        "revoked_tokens": revoked,
        "register_user": RegisterUser(
            users=users, hasher=hasher, cdp=cdp_client, tokens=issuer, refresh=refresh, limiter=limiter
        ),
        "authenticate_user": AuthenticateUser(
            users=users, hasher=hasher, tokens=issuer, refresh=refresh, limiter=limiter,
            attempts=PostgresLoginAttemptLog(settings.database_url),
        ),
        "rotate_session": RotateSession(users=users, tokens=issuer, refresh=refresh),
        "revoke_session": RevokeSession(refresh=refresh),
        "change_password": ChangePassword(users=users, hasher=hasher, refresh=refresh),
        "get_current_user": GetCurrentUser(users=users),
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

        redis_client = None
        if settings.auth_redis_url:
            import redis.asyncio as redis_asyncio

            redis_client = redis_asyncio.from_url(settings.auth_redis_url)
            stack.push_async_callback(redis_client.aclose)
        for name, service in build_auth(settings, cdp_client, redis_client).items():
            setattr(app.state, name, service)
        logger.info("startup.auth.ready ratelimit=%s", "redis" if redis_client else "memory")
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

        # Recsys tách khỏi phần itinerary: chưa nạp được thì tắt recsys và thử lại sau, các route còn lại
        # (kể cả assistant chạy fixture) vẫn phục vụ được.
        logger.info("startup.recsys.start model=%s", settings.embed_model)
        for name in ("index", "search", "similar", "recommend"):
            setattr(app.state, name, None)
        recsys = RecsysRefresher(app, settings)
        await recsys.reload()
        refresh_task = asyncio.create_task(recsys.run())
        logger.info("startup.ready")
        try:
            yield
        finally:
            recsys.stop()
            await refresh_task  # chờ lần nạp đang chạy xong rồi mới đóng client dùng chung
            recsys.close()
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
app.include_router(root_router)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
