"""Adapter `PostgresProductQuery` trên database local đã seed, chạy bằng role `vota_app` (DATABASE_URL) như Backend thật."""
import asyncio
import os
import time

import psycopg
import pytest

from src.backend.app.application.catalog.use_cases import GetProductDetail
from src.backend.app.infrastructure.persistence.postgres_catalog import PostgresProductQuery

APP_URL = os.getenv("DATABASE_URL", "postgresql://vota_app_login:vota@localhost:5432/vota")

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="set RUN_POSTGRES_INTEGRATION=1 to test the seeded local database",
)


@pytest.fixture(scope="module")
def property_with_rooms() -> tuple[str, int]:
    with psycopg.connect(APP_URL) as conn:
        return conn.execute(
            """
            SELECT attributes->>'parentProductId', count(*)::int FROM cdp.products
             WHERE attributes->>'level' = 'room' AND attributes ? 'parentProductId'
             GROUP BY 1 ORDER BY 2 DESC LIMIT 1
            """).fetchone()


def test_property_detail_and_rooms(property_with_rooms):
    parent, room_count = property_with_rooms
    query = PostgresProductQuery(APP_URL)
    rooms = asyncio.run(query.variants(parent))
    assert len(rooms) == room_count and all(r.parent_id == parent and r.level == "room" for r in rooms)
    detail = asyncio.run(GetProductDetail(query)(parent))
    assert detail["productId"] == parent and detail["variantSummary"]["count"] == room_count


def test_detail_reads_are_within_the_catalog_budget(property_with_rooms):
    """NFR-PERF-01: chi tiết ≤ 100 ms. Đo trên máy dev, gồm cả mở kết nối."""
    parent, _ = property_with_rooms
    use_case = GetProductDetail(PostgresProductQuery(APP_URL))
    asyncio.run(use_case(parent))  # làm nóng
    started = time.perf_counter()
    asyncio.run(use_case(parent))
    assert time.perf_counter() - started < 0.1


def test_unknown_or_malformed_ids_are_none_not_errors():
    query = PostgresProductQuery(APP_URL)
    assert asyncio.run(query.get("00000000-0000-0000-0000-000000000000")) is None
    assert asyncio.run(query.get("nt-hotel-01")) is None
    assert asyncio.run(query.variants("nt-hotel-01")) == []


def test_search_units_match_product_meta():
    units = asyncio.run(PostgresProductQuery(APP_URL).search_units())
    with psycopg.connect(APP_URL) as conn:
        expected, recommendable = conn.execute(
            "SELECT count(*), count(*) FILTER (WHERE is_recommendable) FROM catalog.product_meta WHERE is_search_unit"
        ).fetchone()
    assert len(units) == expected and sum(u.recommendable for u in units) == recommendable
    assert not any(u.product.level in ("room", "flight") for u in units)
