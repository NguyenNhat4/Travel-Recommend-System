"""Composition root. Run: uvicorn src.cdp_clone.app.main:app --port 8100 (from repo root)."""
from fastapi import FastAPI
from sqlalchemy import Engine, create_engine

from src.cdp_clone.app.api.errors import install_error_handling
from src.cdp_clone.app.api.routes import router
from src.cdp_clone.app.config import Settings, get_settings
from src.cdp_clone.app.infrastructure.repository import CdpRepository


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = engine or create_engine(settings.database_url, pool_pre_ping=True)

    # Internal service: no CORS, browsers never call it (Web -> Backend -> CDP).
    app = FastAPI(title="CDP Clone", version="0.2.0")
    app.state.settings = settings
    app.state.repository = CdpRepository(engine)

    install_error_handling(app)
    app.include_router(router)

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    return app


def __getattr__(name: str):
    # Lazy so importing this module in tests does not require CDP_* env vars.
    if name == "app":
        return create_app()
    raise AttributeError(name)
