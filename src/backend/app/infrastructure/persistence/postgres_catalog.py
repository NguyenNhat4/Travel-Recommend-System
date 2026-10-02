"""PostgreSQL catalog adapters owned by the Backend app connection."""
from __future__ import annotations

import uuid

import psycopg
from psycopg.rows import dict_row

from src.backend.app.application.tracking.behaviour import CatalogProduct
from src.backend.app.domain.catalog import ListingItem, Product
from src.backend.app.infrastructure.persistence.db_connection import connect_async


class PostgresProductLookup:
    """Minimal product lookup used to ground behaviour events in the catalog."""

    def __init__(self, database_url: str):
        self._database_url = database_url

    async def find_product(self, product_id: str) -> CatalogProduct | None:
        try:
            async with await connect_async(self._database_url, row_factory=dict_row) as conn:
                row = await (
                    await conn.execute(
                        """
                        SELECT product_id::text AS product_id, taxonomy, unit_price
                        FROM cdp.products WHERE product_id = %s::uuid
                        """,
                        (product_id,),
                    )
                ).fetchone()
        except psycopg.errors.InvalidTextRepresentation:
            return None
        return CatalogProduct(
            product_id=row["product_id"],
            taxonomy=row["taxonomy"],
            unit_price=float(row["unit_price"]) if row["unit_price"] is not None else None,
        ) if row else None


_PRODUCT_COLUMNS = """
    p.product_id::text AS product_id, p.name, p.taxonomy, p.destination, p.description, p.attributes,
    p.unit_price, p.currency, p.available, p.available_from, p.available_to, p.image_url
"""


def _uuid_or_none(value: str) -> str | None:
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        return None


def _product(row: dict) -> Product:
    return Product(
        product_id=row["product_id"], name=row["name"], taxonomy=row["taxonomy"], destination=row["destination"],
        description=row["description"] or "", attributes=row["attributes"] or {},
        # numeric(14,2) về Python là Decimal; ép float cho khớp Product và JSON response.
        unit_price=float(row["unit_price"]) if row["unit_price"] is not None else None,
        currency=row["currency"].strip(), available=row["available"], available_from=row["available_from"],
        available_to=row["available_to"], image_url=row["image_url"])


class PostgresProductQuery:
    """Đọc catalog cho /products qua DATABASE_URL (role vota_app chỉ SELECT được cdp.products và catalog.*).

    `get` và `variants` đọc thẳng cdp.products (khoá chính / products_parent_idx) để nằm trong ngân sách
    100 ms của NFR-PERF-01. `search_units` đọc view catalog.product_meta — nơi duy nhất định nghĩa vai trò
    sản phẩm — nên chậm hơn (~100 ms); chỉ dùng khi RecSys tắt.
    """

    def __init__(self, database_url: str):
        self._database_url = database_url

    async def _fetch(self, sql: str, params: tuple) -> list[dict]:
        async with await connect_async(self._database_url, row_factory=dict_row) as conn:
            return await (await conn.execute(sql, params)).fetchall()

    async def get(self, product_id: str) -> Product | None:
        pid = _uuid_or_none(product_id)
        if pid is None:
            return None
        rows = await self._fetch(f"SELECT {_PRODUCT_COLUMNS} FROM cdp.products p WHERE p.product_id = %s::uuid", (pid,))
        return _product(rows[0]) if rows else None

    async def variants(self, parent_product_id: str) -> list[Product]:
        pid = _uuid_or_none(parent_product_id)
        if pid is None:
            return []
        rows = await self._fetch(
            f"SELECT {_PRODUCT_COLUMNS} FROM cdp.products p WHERE p.attributes->>'parentProductId' = %s", (pid,))
        return [_product(r) for r in rows]

    async def search_units(self) -> list[ListingItem]:
        rows = await self._fetch(
            f"""SELECT {_PRODUCT_COLUMNS}, m.is_recommendable
                  FROM cdp.products p JOIN catalog.product_meta m USING (product_id)
                 WHERE m.is_search_unit""", ())
        return [ListingItem(_product(r), bool(r["is_recommendable"])) for r in rows]
