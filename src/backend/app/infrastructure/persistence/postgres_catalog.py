"""PostgreSQL catalog adapters owned by the Backend app connection."""
from __future__ import annotations

import uuid
from typing import Sequence

import psycopg
from psycopg.rows import dict_row

from src.backend.app.application.tracking.behaviour import CatalogProduct
from src.backend.app.domain.catalog import Product

#: 12 trường CDP mà `Product` dùng; `vota_app` được SELECT `cdp.products` (AGENTS.md §6.1).
_PRODUCT_COLUMNS = """
    product_id::text AS product_id, name, taxonomy, destination, description, attributes,
    unit_price, currency, available, available_from, available_to, image_url
"""


def _product(row: dict) -> Product:
    return Product.from_cdp({
        "productId": row["product_id"], "name": row["name"], "taxonomy": row["taxonomy"],
        "destination": row["destination"], "description": row["description"], "attributes": row["attributes"] or {},
        # numeric(14,2) về Python là Decimal; ép float cho khớp Product và JSON response.
        "unitPrice": float(row["unit_price"]) if row["unit_price"] is not None else None,
        "currency": (row["currency"] or "VND").strip(), "available": row["available"],
        "availableFrom": row["available_from"], "availableTo": row["available_to"], "imageUrl": row["image_url"],
    })


def _valid_ids(product_ids: Sequence[str]) -> list[str]:
    """Id không phải UUID thì không thể có trong catalog; bỏ trước để Postgres không lỗi ép kiểu."""
    valid = []
    for product_id in product_ids:
        try:
            valid.append(str(uuid.UUID(str(product_id))))
        except ValueError:
            continue
    return valid


class PostgresProductCatalog:
    """Port `ProductCatalog`: đọc mọi tầng sản phẩm, giá và tình trạng hiện tại, mỗi lần gọi."""

    def __init__(self, database_url: str):
        self._database_url = database_url

    async def _fetch(self, where: str, params: tuple) -> list[Product]:
        async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
            rows = await (await conn.execute(f"SELECT {_PRODUCT_COLUMNS} FROM cdp.products WHERE {where}",
                                             params)).fetchall()
        return [_product(row) for row in rows]

    async def get(self, product_id: str) -> Product | None:
        return (await self.get_many([product_id])).get(str(product_id))

    async def get_many(self, product_ids: Sequence[str]) -> dict[str, Product]:
        ids = _valid_ids(product_ids)
        if not ids:
            return {}
        return {product.product_id: product
                for product in await self._fetch("product_id = ANY(%s::uuid[])", (ids,))}

    async def children(self, parent_id: str) -> list[Product]:
        return await self._fetch("attributes->>'parentProductId' = %s", (str(parent_id),))


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
