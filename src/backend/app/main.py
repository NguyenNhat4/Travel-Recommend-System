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
import threading
from pathlib import Path
import logging
import os
import socket
import sys
from concurrent.futures import Executor, ThreadPoolExecutor
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.backend.app.agents.runtime_dependencies import RuntimeAgentDependencies
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.api.errors import install_error_handlers
from src.backend.app.api.middleware import (
    install_call_telemetry,
    install_cors,
    install_http_logging,
    install_request_id,
)
from src.backend.app.infrastructure.persistence import db_connection
from src.backend.app.api.ops import ops_router
from src.backend.app.api.v1.router import api_router, root_router
from src.backend.app.application.auth.use_cases import (
    AuthenticateUser,
    ChangePassword,
    GetCurrentUser,
    RegisterUser,
    RevokeSession,
    RotateSession,
    UpdateProfile,
)
from src.backend.app.application.booking import (
    BookingDraftService,
    CancelBooking,
    CartService,
    CreateBookingHold,
    GetBooking,
    ListBookings,
    MergeGuestBooking,
    PaymentEventHandler,
    ReconcileBookings,
    Settlement,
)
from src.backend.app.application.catalog.use_cases import GetProductDetail, GetSimilarProducts, ListProducts
from src.backend.app.application.itinerary.history import ConversationHistory
from src.backend.app.application.itinerary.engine_tools import InProcessItineraryTools
from src.backend.app.application.telemetry import traced
from src.backend.app.application.itinerary.use_cases import PlanItinerary
from src.backend.app.application.tracking.behaviour import BehaviourTracker
from src.backend.app.domain.booking import DraftPolicy, HoldPolicy
from src.backend.app.domain.catalog import ListingItem
from src.backend.app.application.recommendation import BuildPopularity, RecommendForUser
from src.backend.app.application.search import SearchProducts, SimilarProducts, SuggestProducts
from src.backend.app.application.search.search_log import SearchLogRecorder
from src.backend.app.domain.search import HybridConfig
from src.backend.app.core.config import REPO_ROOT, Settings, get_settings, shared_backend_violations
from src.backend.app.core.logging_config import configure_logging, log_event
from src.backend.app.infrastructure.persistence.db_peer_registry import DbPeerRegistry
from src.backend.app.infrastructure.persistence.db_probe import DatabaseProbe
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
from src.backend.app.infrastructure.telemetry.memory import InMemoryCallTelemetry
from src.backend.app.infrastructure.payments.fake_gateway import FakeGateway
from src.backend.app.infrastructure.payments.stripe_gateway import StripePaymentGateway
from src.backend.app.infrastructure.persistence.conversation_store import (
    InMemoryConversationStore,
    RedisConversationStore,
)
from src.backend.app.infrastructure.persistence.postgres_conversation_archive import PostgresConversationArchive
from src.backend.app.infrastructure.persistence.guest_booking_store import (
    GuestBookingRedisStore,
    GuestDraftRepository,
    InMemoryKeyValue,
    RedisKeyValue,
)
from src.backend.app.infrastructure.persistence.postgres_booking import (
    PostgresBookingDraftRepository,
    PostgresBookingStore,
    PostgresCartRepository,
    PostgresProductCatalog,
)
from src.backend.app.infrastructure.persistence.postgres_catalog import PostgresProductLookup, PostgresProductQuery
from src.backend.app.infrastructure.persistence.postgres_search_logs import PostgresSearchLogWriter

configure_logging()  # một lần, trước mọi logger.info lúc nạp module (docs/spec/logging-schema.md)
logger = logging.getLogger("uvicorn.error")

# psycopg async không chạy được trên ProactorEventLoop — event loop mặc định của Windows và của
# uvicorn trên Windows. Phải đặt trước khi uvicorn tạo loop, nếu không mọi truy cập cdp.* qua
# LocalCdpClient trả InterfaceError lúc chạy thật. Trên Linux/macOS dòng này không có tác dụng gì.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def build_catalog(settings, state) -> dict:
    """Use case /products. `state` là app.state sau bước dựng RecSys (có thể đã tắt)."""
    products = PostgresProductQuery(settings.database_url)
    return {
        "get_product_detail": GetProductDetail(products),
        "list_products": ListProducts(
            products, getattr(state, "listing_units", None), getattr(state, "product_popularity", None) or {},
            max_limit=settings.search_max_limit),
        "get_similar_products": GetSimilarProducts(products, getattr(state, "similar", None)),
    }


def build_recsys(settings, embedder=None, vector_store=None, cdp_reader=None) -> dict:
    """Dựng engine recsys trên database đã seed.

    Ba tham số override để test tiêm giả lập mà không cần Postgres hay tải model embedding.
    """
    owns_embedder = False
    owns_vector_store = vector_store is None
    try:
        if vector_store is None:
            from src.backend.app.domain.catalog import TEXT_BUILDER_VERSION
            from src.backend.app.infrastructure.embeddings.factory import build_embedder
            from src.backend.app.infrastructure.vectors.weaviate_store import (
                WeaviateVectorSearch,
                WeaviateVectorStore,
                connect_weaviate,
            )

            if embedder is None:
                embedder = build_embedder(settings)  # e5-small chạy local (PRD FR-SRC-02)
                owns_embedder = True
                if settings.search_embed_cache:
                    # Cache vector truy vấn (NFR-PERF-03, contract 1.12.0 `embedCache`) bọc quanh embedder dùng chung:
                    # RecsysRefresher truyền lại object này mỗi lần nạp catalog nên cache sống qua reload.
                    from src.backend.app.application.search.query_cache import CachingQueryEmbedder, QueryEmbeddingCache

                    embedder = CachingQueryEmbedder(
                        embedder, QueryEmbeddingCache(settings.search_embed_cache_size),
                        log_every=settings.search_embed_cache_log_every,
                    )
            vector_store = WeaviateVectorStore(
                settings.database_url,
                WeaviateVectorSearch(
                    connect_weaviate(
                        settings.weaviate_url,
                        api_key=settings.weaviate_api_key,
                        grpc_port=settings.weaviate_grpc_port,
                        timeout_seconds=settings.weaviate_timeout_seconds,
                    ),
                    collection=settings.vector_collection,
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
    cdp_reader = cdp_reader or PostgresCdpReader(settings.cdp_database_url, timeout_seconds=settings.cdp_timeout_seconds)
    logger.info("startup.recsys.popularity.build.start")
    popularity = BuildPopularity(index, cdp_reader)()
    logger.info("startup.recsys.popularity.build.ready")
    # Hybrid dùng chính adapter vector làm nhánh BM25 (cùng collection `Product`); tắt bằng SEARCH_HYBRID=false.
    # Kênh fuzzy + trọng số RRF (contract 1.16.0) dùng chung cho cả bộ ngưỡng câu không dấu; mặc định tắt / 1.0.
    fusion = dict(
        fuzzy_k=settings.search_fuzzy_k,
        fuzzy_candidate_k=settings.search_fuzzy_candidate_k,
        fuzzy_min_sim=settings.search_fuzzy_min_sim,
        dense_weight=settings.search_rrf_dense_weight,
        lexical_weight=settings.search_rrf_lexical_weight,
        fuzzy_weight=settings.search_rrf_fuzzy_weight,
    )
    hybrid = HybridConfig(
        rrf_k=settings.search_rrf_k,
        lexical_k=settings.search_lexical_k,
        lexical_cutoff=min(settings.search_lexical_cutoff, settings.search_cutoff),  # contract: lexicalCutoff ≤ cutoff
        min_coverage=settings.search_lexical_min_coverage,
        **fusion,
    ) if settings.search_hybrid and hasattr(vector_search, "bm25") else None
    logger.info("startup.recsys.search.mode=%s", "HYBRID_CANDIDATE_SCORE" if hybrid else "ANN_CANDIDATE_SCORE")
    logger.info("startup.recsys.search.normalize=%s", settings.search_normalize)
    # Câu không dấu (contract 1.14.0 `queryProfile`): bộ ngưỡng vớt riêng, chỉ khi hybrid bật và SEARCH_NO_DIACRITICS_MODE=relax.
    relax = settings.search_no_diacritics_mode == "relax"
    no_diacritics_cutoff = settings.search_no_diacritics_cutoff if relax else None
    no_diacritics = HybridConfig(
        rrf_k=settings.search_rrf_k,
        lexical_k=settings.search_no_diacritics_lexical_k,
        lexical_cutoff=min(settings.search_no_diacritics_lexical_cutoff,
                           no_diacritics_cutoff if no_diacritics_cutoff is not None else settings.search_cutoff),
        min_coverage=settings.search_no_diacritics_min_coverage,
        **fusion,
    ) if hybrid and relax else None
    logger.info("startup.recsys.search.dest_filter=%s no_diacritics=%s", settings.search_dest_filter,
                settings.search_no_diacritics_mode)
    logger.info("startup.recsys.search.query_plan negation=%s taxonomy=%s strong_only=%s route=%s numeric=%s party=%s "
                "tone=%s", settings.search_negation_filter, settings.search_taxonomy_filter,
                settings.search_taxonomy_strong_only, settings.search_route_filter, settings.search_numeric_filter,
                settings.search_party_filter, settings.search_tone_normalize)
    logger.info("startup.recsys.search.fusion fuzzy_k=%s weights=%s/%s/%s", settings.search_fuzzy_k if hybrid else 0,
                settings.search_rrf_dense_weight, settings.search_rrf_lexical_weight, settings.search_rrf_fuzzy_weight)
    product_popularity = {index.units[u].product_id: s for u, s in popularity.unit_scores().items()}
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
            lexical=vector_search if hybrid else None,
            hybrid=hybrid,
            lexical_candidate_k=settings.search_lexical_candidate_k,
            normalize=settings.search_normalize,
            dest_filter=settings.search_dest_filter,
            dest_filter_fallback=settings.search_dest_filter_fallback,
            no_diacritics=no_diacritics,
            no_diacritics_cutoff=no_diacritics_cutoff,
            no_diacritics_min_tokens=settings.search_no_diacritics_min_tokens,
            negation_filter=settings.search_negation_filter,
            taxonomy_filter=settings.search_taxonomy_filter,
            route_filter=settings.search_route_filter,
            numeric_filter=settings.search_numeric_filter,
            tone_normalize=settings.search_tone_normalize,
            taxonomy_strong_only=settings.search_taxonomy_strong_only,
            party_filter=settings.search_party_filter,
        ),
        "similar": SimilarProducts(index, vector_search),
        # GET /search/suggestions (FR-SRC-05): khớp chữ trên chính index này, không gọi embed hay kho vector.
        "suggest": SuggestProducts(index, product_popularity),
        # GET /products: cùng tập search unit với /search, sắp xếp popular theo lượt mua CDP (backend §4.1).
        "listing_units": [ListingItem(p, bool(index.recommendable[i])) for i, p in enumerate(index.units)],
        "product_popularity": product_popularity,
        "recommend": RecommendForUser(
            index, vector_search, cdp_reader, popularity, candidate_k=settings.recommend_candidate_k
        ),
    }


#: Chưa nạp được lần nào (database chưa seed, Weaviate chưa index…) thì thử lại sớm, không chờ trọn chu kỳ.
RECSYS_RETRY_SECONDS = 30.0
#: Shutdown chờ prewarm đang chạy tối đa chừng này rồi mới đóng embedder (prewarm kiểm `stop` giữa hai lô).
PREWARM_SHUTDOWN_WAIT_SECONDS = 10.0


def prewarm_from_settings(settings, services: dict, stop: threading.Event):
    """Nạp sẵn cache vector truy vấn: file câu gold (`SEARCH_PREWARM_FILE`, tương đối theo src/backend) + head query của
    `app.search_logs`. Chạy trong thread (model chạy đồng bộ); `stop` cắt giữa hai lô khi shutdown."""
    from src.backend.app.application.search.prewarm import prewarm, read_query_file
    from src.backend.app.infrastructure.persistence.postgres_search_logs import PostgresSearchLogReader

    path = Path(settings.search_prewarm_file)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    queries = read_query_file(path)
    if not queries:
        logger.warning("search.prewarm.file.empty path=%s", path)
    head = PostgresSearchLogReader(settings.database_url).head_queries(
        days=settings.search_prewarm_head_days, limit=settings.search_prewarm_head_queries)
    logger.info("search.prewarm.start file_queries=%d head_queries=%d", len(queries), len(head))
    return prewarm(services["search"], services["recsys_embedder"], [*queries, *head],
                   inputs_per_minute=settings.search_prewarm_inputs_per_minute, stop=stop)


class RecsysRefresher:
    """Nạp lại engine recsys theo chu kỳ để giá, trạng thái và cửa sổ ngày theo kịp job cào.

    Embedder/client Weaviate dùng chung giữa các lần nạp; request đang chạy giữ use case của bản cũ nên không
    client nào bị đóng giữa chừng. Lần nạp lại lỗi thì giữ bản đang phục vụ thay vì tắt recsys.
    """

    def __init__(self, app: FastAPI, settings: Settings, build=None, on_publish=None, prewarm=None):
        self.app, self.settings = app, settings
        self._build = build  # test tiêm bản giả; mặc định là build_recsys
        self._on_publish = on_publish  # dựng lại use case đọc engine recsys (catalog) sau mỗi lần nạp
        self._prewarm = prewarm  # test tiêm bản giả; mặc định prewarm_from_settings (chạy một lần, sau lần nạp đầu)
        self.services: dict = {}
        self._failures = 0
        self._stop = asyncio.Event()
        self._prewarm_task: asyncio.Task | None = None
        self._prewarm_stop = threading.Event()

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
                logger.warning("startup.recsys.disabled error=%s; retry_seconds=%s", exc, RECSYS_RETRY_SECONDS)
            else:  # vẫn chưa lên: không lặp cảnh báo mỗi 30 giây
                logger.debug("startup.recsys.retry_failed error=%s", exc)
            return False
        self._failures = 0
        self.services = updated
        for name, service in updated.items():  # không có await giữa các phép gán: request thấy trọn một bản
            setattr(self.app.state, name, service)
        if self._on_publish is not None:
            self._on_publish()
        if first:
            logger.info("startup.recsys.ready search_units=%d", len(updated["index"].units))
            if getattr(self.settings, "search_prewarm", False) and self._prewarm_task is None:
                # Nền, không chặn startup: request vẫn được phục vụ (miss) trong lúc cache đang nạp.
                self._prewarm_task = asyncio.create_task(self._run_prewarm())
        else:
            logger.info("catalog.refresh.ready search_units=%d", len(updated["index"].units))
            stats = getattr(self.services.get("recsys_embedder"), "cache", None)
            if stats is not None and hasattr(stats, "stats"):
                logger.info("search.embed_cache %s", " ".join(f"{k}={v}" for k, v in stats.stats().items()))
        return True

    async def _run_prewarm(self) -> None:
        try:
            report = await asyncio.to_thread(self._prewarm or prewarm_from_settings, self.settings, self.services,
                                             self._prewarm_stop)
            logger.info("search.prewarm.done %s", " ".join(f"{k}={v}" for k, v in report.as_dict().items()))
        except Exception as exc:  # noqa: BLE001 — prewarm hỏng thì cache chỉ nạp dần theo request, không ảnh hưởng phục vụ
            logger.warning("search.prewarm.failed error=%s", exc)

    async def wait_prewarm(self, timeout: float = PREWARM_SHUTDOWN_WAIT_SECONDS) -> None:
        """Shutdown: chờ prewarm dừng (đã nhận `stop`) trước khi đóng embedder dùng chung."""
        if self._prewarm_task is None:
            return
        try:
            await asyncio.wait_for(asyncio.shield(self._prewarm_task), timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            logger.warning("search.prewarm.shutdown_timeout seconds=%s", timeout)

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
        self._prewarm_stop.set()

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
        # Dùng chung với route trợ lý (giới hạn tin gửi, NFR-SEC-04).
        "rate_limiter": limiter,
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
        "update_profile": UpdateProfile(users=users),
    }


def build_booking(settings: Settings, cdp_client, recorder, product_lookup, *, clock=None, booking_redis=None) -> dict:
    """Dựng giỏ hàng, đơn nháp của Đặt ngay, giữ chỗ, thanh toán Stripe, huỷ và đối soát (spec booking)."""
    from datetime import datetime, timezone

    clock = clock or (lambda: datetime.now(timezone.utc))
    # Giỏ và đơn nháp của khách chưa đăng nhập nằm ở Redis; thiếu Redis thì chỉ dev/test được dùng bộ nhớ tiến trình.
    if booking_redis is None and settings.app_env == "production":
        raise RuntimeError("BOOKING_REDIS_URL là bắt buộc ở production (giỏ và đơn nháp của khách chưa đăng nhập)")
    guest_store = GuestBookingRedisStore(
        RedisKeyValue(booking_redis) if booking_redis is not None else InMemoryKeyValue(),
        ttl_seconds=settings.guest_booking_ttl_days * 86_400, clock=clock)
    guest_drafts = GuestDraftRepository(guest_store)
    if settings.payment_provider == "fake":
        if settings.app_env == "production":
            raise RuntimeError("PAYMENT_PROVIDER=fake không được dùng ở production")
        gateway = FakeGateway()
    else:
        gateway = StripePaymentGateway(settings.stripe_secret_key, settings.stripe_webhook_secret)
    store = PostgresBookingStore(settings.database_url, settings.leader_lock_database_url or None)
    carts = PostgresCartRepository(settings.database_url)
    drafts = PostgresBookingDraftRepository(settings.database_url)
    catalog = PostgresProductCatalog(settings.database_url)
    tracker = BehaviourTracker(recorder, product_lookup)
    settlement = Settlement(store, gateway, cdp_client, clock)
    handler = PaymentEventHandler(
        store, gateway, settlement, max_failed_attempts=settings.payment_max_failed_attempts, clock=clock)
    reconciler = ReconcileBookings(store, gateway, settlement, handler, clock)
    return {
        "payment_gateway": gateway,
        "cart_service": CartService(carts, catalog, tracker, guest_carts=guest_store, clock=clock),
        "booking_draft_service": BookingDraftService(
            drafts, carts, catalog, tracker, store, DraftPolicy(settings.booking_draft_ttl_minutes),
            guest_drafts=guest_drafts, guest_carts=guest_store, reconciler=reconciler, clock=clock),
        "merge_guest_booking": MergeGuestBooking(guest_store, carts, drafts, catalog, tracker, clock=clock),
        "create_booking_hold": CreateBookingHold(
            store, carts, catalog, gateway, reconciler, HoldPolicy(settings.booking_hold_minutes),
            public_web_url=settings.public_web_url, provider=settings.payment_provider, clock=clock, drafts=drafts),
        "get_booking": GetBooking(store, catalog),
        "list_bookings": ListBookings(store, clock),
        "cancel_booking": CancelBooking(store, gateway, settlement, catalog, clock),
        "payment_event_handler": handler,
        "reconcile_bookings": reconciler,
    }


async def _reconcile_loop(reconcile, interval_seconds: int) -> None:
    """Job đối soát trong tiến trình Backend (đủ cho MVP nhờ trạng thái idempotent; tách worker thì chỉ đổi chỗ gọi)."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await reconcile()
        except Exception:
            logger.exception("booking.reconcile.loop_failed")


#: Pool riêng cho engine đồng bộ mà tool itinerary gọi trong tiến trình. Bằng số token mặc định của anyio —
#: sức chứa route sync khi agent còn gọi qua HTTP — và không tranh thread với `RecsysRefresher`.
ITINERARY_TOOL_WORKERS = 40
#: Engine / use case được bọc để đo lần gọi (application/telemetry.py).
TRACED_SERVICES = ("search", "similar", "recommend", "get_product_detail", "list_products", "get_similar_products")


def _inprocess_itinerary_tools(app: FastAPI, executor: Executor) -> InProcessItineraryTools:
    """Provider đọc `app.state` mỗi lời gọi: RecsysRefresher thay engine và nạp xong sau khi nối dây."""
    return InProcessItineraryTools(
        search=lambda: getattr(app.state, "search", None),
        recommend=lambda: getattr(app.state, "recommend", None),
        index=lambda: getattr(app.state, "index", None),
        product_detail=lambda: getattr(app.state, "get_product_detail", None),
        similar_products=lambda: getattr(app.state, "get_similar_products", None),
        list_products=lambda: getattr(app.state, "list_products", None),
        token_verifier=lambda: getattr(app.state, "token_verifier", None),
        revoked_tokens=lambda: getattr(app.state, "revoked_tokens", None),
        executor=executor,
        telemetry=getattr(app.state, "call_telemetry", None),
    )


def _itinerary_runtime(app: FastAPI, settings: Settings, authorization: str | None, owner: str | None = None):
    """Dựng dependency của agent cho một request. Đọc `app.state` lúc gọi để test thay được client/LLM."""
    clients = getattr(app.state, "itinerary_http_clients", None)
    store = getattr(app.state, "itinerary_conversation_store", None)
    if clients is None or store is None:
        return None
    catalog = clients if getattr(clients, "supports_catalog", False) else None
    # Cờ tường minh thay vì hasattr: client không khai báo similar thì planner không bao giờ thấy tool này.
    similar = clients if getattr(clients, "supports_similar", False) else None
    gateway = ItineraryToolGateway(clients, clients, catalog, recommendation_authorization=authorization,
                                   similar=similar)
    return RuntimeAgentDependencies(
        gateway, store, getattr(app.state, "itinerary_llm", None), authorization, owner=owner,
        archive=getattr(app.state, "itinerary_conversation_archive", None),
        tool_timeout_seconds=settings.itinerary_tool_timeout_seconds,
        llm_timeout_seconds=settings.itinerary_llm_timeout_seconds,
    )


def _itinerary_planner(app: FastAPI, settings: Settings, authorization: str | None, owner: str | None = None):
    runtime = _itinerary_runtime(app, settings, authorization, owner)
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
        logger.warning("startup.langsmith.skipped reason=missing_api_key")
        return
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    logger.info("startup.langsmith.on project=%s", settings.langsmith_project)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.ready = False
    db_connection.configure(
        connect_timeout_seconds=settings.db_connect_timeout_seconds,
        tcp_user_timeout_ms=settings.db_tcp_user_timeout_ms,
    )
    if settings.ready_requires_db:
        app.state.db_probe = DatabaseProbe(
            settings.database_url, timeout_seconds=settings.ready_db_timeout_seconds,
            cache_seconds=settings.ready_db_cache_seconds)
    violations = shared_backend_violations(settings)
    if violations:
        raise RuntimeError(
            "REQUIRE_SHARED_BACKENDS=true nhưng " + ", ".join(violations)
            + " trống hoặc trỏ loopback; mỗi bản sao sẽ có dịch vụ riêng và lệch trạng thái")
    _forward_langsmith_env(settings)
    log_event(logger, "app.startup", stage="begin", app=settings.app_name, env=settings.app_env,
              workers=os.environ.get("UVICORN_WORKERS"))
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
            if settings.ready_requires_db and settings.ready_db_outage_keeps_ready:
                # Hostname = một VM (các worker cùng VM dùng chung một dấu), xem db_peer_registry.py.
                app.state.db_peers = DbPeerRegistry(
                    redis_client, socket.gethostname(), ttl_seconds=settings.ready_db_peer_ttl_seconds)
        for name, service in build_auth(settings, cdp_client, redis_client).items():
            setattr(app.state, name, service)
        logger.info("startup.auth.ready ratelimit=%s", "redis" if redis_client else "memory")
        app.state.product_lookup = PostgresProductLookup(settings.database_url)
        # Log tìm kiếm (SEARCH_LOG_QUERIES, mặc định tắt): hàng đợi có trần + một luồng ghi app.search_logs; None → route
        # /search không ghi gì và không xác thực Bearer.
        app.state.search_log = (SearchLogRecorder(PostgresSearchLogWriter(settings.database_url))
                                if settings.search_log_queries else None)
        if app.state.search_log is not None:
            stack.callback(app.state.search_log.close)
        logger.info("startup.search_log enabled=%s", settings.search_log_queries)
        app.state.browse_event_recorder = BackgroundCdpEventRecorder(
            app.state.cdp_client, max_queue=settings.cdp_event_queue_size
        )
        logger.info("startup.browse_event_recorder.start")
        app.state.browse_event_recorder.start()
        logger.info("startup.browse_event_recorder.ready")
        booking_redis = None
        if settings.booking_redis_url:
            import redis.asyncio as redis_asyncio

            booking_redis = redis_asyncio.from_url(settings.booking_redis_url)
            stack.push_async_callback(booking_redis.aclose)
        for name, service in build_booking(
            settings, cdp_client, app.state.browse_event_recorder, app.state.product_lookup,
            booking_redis=booking_redis,
        ).items():
            setattr(app.state, name, service)
        if settings.booking_reconcile_interval_seconds:
            reconcile_task = asyncio.create_task(
                _reconcile_loop(app.state.reconcile_bookings, settings.booking_reconcile_interval_seconds))
            stack.callback(reconcile_task.cancel)
        gateway_close = getattr(app.state.payment_gateway, "aclose", None)
        if gateway_close is not None:
            stack.push_async_callback(gateway_close)
        logger.info("startup.booking.ready payment_provider=%s guest_store=%s", settings.payment_provider,
                    "redis" if booking_redis else "memory")
        archive = PostgresConversationArchive(settings.database_url)
        app.state.itinerary_conversation_archive = archive
        app.state.conversation_history = ConversationHistory(archive)
        if settings.itinerary_redis_url:
            import redis.asyncio as redis_asyncio

            itinerary_redis = redis_asyncio.from_url(settings.itinerary_redis_url)
            stack.push_async_callback(itinerary_redis.aclose)
            app.state.itinerary_conversation_store = RedisConversationStore(
                itinerary_redis, ttl_seconds=settings.itinerary_conversation_ttl_seconds)
            logger.info("startup.itinerary_conversation_store.ready mode=redis")
        elif settings.app_env == "production":
            raise RuntimeError("ITINERARY_REDIS_URL là bắt buộc khi APP_ENV=production")
        else:
            app.state.itinerary_conversation_store = InMemoryConversationStore(
                ttl_seconds=settings.itinerary_conversation_ttl_seconds)
            logger.warning("startup.itinerary_conversation_store.ready mode=memory")
        app.state.plan_itinerary = PlanItinerary(
            lambda authorization, owner: _itinerary_planner(app, settings, authorization, owner),
            settings.itinerary_request_timeout_seconds,
        )
        mode = settings.itinerary_data_mode or ("fixture" if settings.app_env in {"development", "test"} else "disabled")
        app.state.itinerary_data_mode = mode
        logger.info("startup.itinerary_clients.start mode=%s", mode)
        if mode == "fixture":
            app.state.itinerary_http_clients = FixtureItineraryClients()
        elif mode == "inprocess":
            pool = ThreadPoolExecutor(max_workers=ITINERARY_TOOL_WORKERS, thread_name_prefix="itinerary-tool")
            stack.callback(pool.shutdown, wait=False, cancel_futures=True)
            # Tên thuộc tính là lịch sử (thời chỉ có adapter HTTP); giữ nguyên vì route status và test đọc nó.
            app.state.itinerary_http_clients = _inprocess_itinerary_tools(app, pool)
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
            logger.warning("startup.itinerary_llm.unavailable error=%s", exc)
        logger.info("startup.itinerary_llm.mode mode=%s", app.state.itinerary_llm_mode)

        # Recsys tách khỏi phần itinerary: chưa nạp được thì tắt recsys và thử lại sau, các route còn lại
        # (kể cả assistant chạy fixture) vẫn phục vụ được.
        logger.info("startup.recsys.start model=%s", settings.embed_model)
        for name in ("index", "search", "similar", "suggest", "recommend", "listing_units", "product_popularity"):
            setattr(app.state, name, None)

        # Catalog đọc thẳng database nên vẫn chạy khi RecSys tắt; khi đó danh sách đọc search unit mỗi request
        # và /similar trả 503 SEARCH_UNAVAILABLE. Catalog giữ tham chiếu tới engine recsys nên phải dựng lại
        # sau mỗi lần RecsysRefresher nạp bản mới, nếu không /products và /similar dùng mãi bản lúc khởi động.
        def publish_catalog() -> None:
            for name, service in build_catalog(settings, app.state).items():
                setattr(app.state, name, service)
            # Đo lần gọi web / agent (docs/prd/deployment-plan.md §5): bọc engine vừa nạp, ghi số sản phẩm trong bộ nhớ.
            for name in TRACED_SERVICES:
                setattr(app.state, name, traced(getattr(app.state, name, None), name))
            units = getattr(getattr(app.state, "index", None), "units", None)
            app.state.call_telemetry.set_catalog(len(units) if units is not None else None)

        recsys = RecsysRefresher(app, settings, on_publish=publish_catalog)
        if not await recsys.reload():
            publish_catalog()
        app.state.behaviour_tracker = BehaviourTracker(app.state.browse_event_recorder, app.state.product_lookup)
        refresh_task = asyncio.create_task(recsys.run())

        log_event(logger, "app.startup", stage="ready", app=settings.app_name, env=settings.app_env)
        app.state.ready = True
        try:
            yield
        finally:
            log_event(logger, "app.shutdown", stage="begin")
            app.state.ready = False
            recsys.stop()
            await refresh_task  # chờ lần nạp đang chạy xong rồi mới đóng client dùng chung
            await recsys.wait_prewarm()
            recsys.close()
            logger.info("shutdown.browse_event_recorder.stop")
            await app.state.browse_event_recorder.stop()
    log_event(logger, "app.shutdown", stage="done")


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    description="Travel recommendation and itinerary API",
    version="1.18.0",
    lifespan=lifespan,
)

app.state.call_telemetry = InMemoryCallTelemetry()
install_cors(app, settings.cors_origins)
install_call_telemetry(app)
install_http_logging(app)  # trước install_request_id: nằm trong, đọc được X-Request-ID
install_request_id(app)
install_error_handlers(app, (psycopg.OperationalError,))
app.include_router(api_router, prefix="/api/v1")
app.include_router(root_router)
app.include_router(ops_router)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}


@app.get("/health/ready")
async def health_ready():
    ready = bool(getattr(app.state, "ready", False))
    # Có bật thì RecSys phải nạp xong: bản sao Weaviate rỗng chỉ trả /search rỗng với HTTP 200, LB sẽ không biết để loại.
    recsys_ready = not settings.ready_requires_recsys or getattr(app.state, "index", None) is not None
    probe = getattr(app.state, "db_probe", None) if settings.ready_requires_db else None
    db_reachable = True if probe is None else await probe.ok()
    db_outage = False
    db_ready = db_reachable
    peers = getattr(app.state, "db_peers", None)
    if peers is not None and probe is not None:
        if db_reachable:
            await peers.mark_ok()
        else:
            # Mất DB một mình (VM khác còn DB) thì bị loại; mất cùng lúc ở mọi VM (hoặc không biết) thì giữ lại
            # để catalog/search không cần DB vẫn phục vụ. Không phụ thuộc DB nên đường cần DB tự trả lỗi.
            await peers.mark_failed()
            others_ok = await peers.peers_ok()
            if others_ok is None or others_ok == 0:
                db_outage, db_ready = True, True
    ok = ready and recsys_ready and db_ready
    # Chỉ ghi khi trạng thái đổi: LB gọi endpoint này vài giây một lần, ghi mỗi lần sẽ ngập log.
    state = (ok, recsys_ready, db_reachable, db_outage)
    if state != getattr(app.state, "last_readiness", None):
        app.state.last_readiness = state
        if not db_reachable:
            log_event(logger, "db.unavailable", "ERROR", component="postgres", error_kind="readiness_probe",
                      scope="all_instances" if db_outage else "this_instance")
        if not ok:
            log_event(logger, "readiness.degraded", "WARNING", ready=ready, recsys=recsys_ready, db=db_reachable)
        elif db_outage:
            log_event(logger, "readiness.db_outage_kept", "WARNING", recsys=recsys_ready)
        else:
            logger.info("readiness.recovered")
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "starting", "ready": ok, "recsys": recsys_ready, "db": db_reachable,
                 "mode": "db_outage" if db_outage else "normal", "env": settings.app_env},
    )
