import asyncio

from src.backend.app.infrastructure.cdp.local_cdp_client import LocalCdpClient
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
