from contextlib import AsyncExitStack, asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.app.api.router import api_router
from src.backend.app.core.config import get_settings
from src.backend.app.core.request_context import install_request_id
from src.backend.app.infrastructure.clients.cdp_event_dispatcher import BackgroundCdpEventRecorder
from src.backend.app.infrastructure.clients.cdp_http_client import CdpHttpClient
from src.backend.app.infrastructure.clients.local_cdp_client import LocalCdpClient
from src.backend.app.infrastructure.persistence.postgres_catalog import PostgresProductLookup


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
        try:
            yield
        finally:
            await app.state.browse_event_recorder.stop()
    print("Shutting down...")


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    description="Travel recommendation and itinerary API",
    version="1.0.0",
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

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
