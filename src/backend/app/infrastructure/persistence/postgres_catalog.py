"""PostgreSQL catalog adapters owned by the Backend app connection."""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from src.backend.app.application.tracking.behaviour import CatalogProduct


class PostgresProductLookup:
    """Minimal product lookup used to ground behaviour events in the catalog."""

    def __init__(self, database_url: str):
        self._database_url = database_url

    async def find_product(self, product_id: str) -> CatalogProduct | None:
        try:
            async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
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
