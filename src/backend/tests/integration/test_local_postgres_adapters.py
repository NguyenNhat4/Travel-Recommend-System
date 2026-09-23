"""Read-only integration checks against the seeded local PostgreSQL instance."""
import asyncio
import os

import psycopg
import pytest

from src.backend.app.infrastructure.clients.local_cdp_client import LocalCdpClient
from src.backend.app.infrastructure.persistence.postgres_catalog import PostgresProductLookup

APP_URL = os.getenv("DATABASE_URL", "postgresql://vota_app_login:vota@localhost:5432/vota")
CDP_URL = os.getenv("CDP_DATABASE_URL", "postgresql://cdp_client_login:cdp@localhost:5432/vota")

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="set RUN_POSTGRES_INTEGRATION=1 to test the seeded local database",
)


def test_local_cdp_and_catalog_adapters_read_seeded_persona() -> None:
    async def scenario() -> None:
        cdp = LocalCdpClient(CDP_URL)
        profile = await cdp.get_profile("VP0000001")
        assert profile is not None
        assert profile.lifecycle_stage == "active"
        assert profile.vinclub_tier == "Gold"

        events = await cdp.list_events("VP0000001", max_events=5)
        assert len(events) == 5
        assert events == sorted(events, key=lambda event: event.timestamp, reverse=True)

        purchases = await cdp.list_events("VP0000001", event_name="purchase", max_events=20)
        assert purchases
        assert all(event.event_name == "purchase" for event in purchases)

        lookup = PostgresProductLookup(APP_URL)
        item = next(event for event in purchases if event.product_id is not None)
        product = await lookup.find_product(item.product_id)
        assert product is not None
        assert product.product_id == item.product_id
        assert await lookup.find_product("not-a-uuid") is None

    asyncio.run(scenario())


def test_database_roles_enforce_the_two_connection_boundary() -> None:
    with psycopg.connect(APP_URL, autocommit=True) as app:
        assert app.execute("SELECT count(*) FROM cdp.products").fetchone()[0] == 11_387
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("SELECT count(*) FROM cdp.events")

    with psycopg.connect(CDP_URL, autocommit=True) as cdp:
        assert cdp.execute("SELECT count(*) FROM cdp.profiles").fetchone()[0] == 2_000
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cdp.execute("SELECT count(*) FROM catalog.combo_items")
