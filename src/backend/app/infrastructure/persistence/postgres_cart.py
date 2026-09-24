"""Port `CartRepository` trên `app.carts` / `app.cart_items` qua `DATABASE_URL` (role `vota_app`)."""
from __future__ import annotations

import uuid
from datetime import date

import psycopg
from psycopg.rows import dict_row

from src.backend.app.application.ports.cart_repository import Cart, CartLine

_ITEMS = """
SELECT cart_item_id::text AS cart_item_id, product_id::text AS product_id, quantity, using_date, using_date_to,
       unit_price_snapshot, added_at
FROM   app.cart_items WHERE cart_id = %s
ORDER  BY added_at, cart_item_id
"""

#: Mục phải thuộc giỏ của đúng khách: id của người khác cũng coi như không tồn tại.
_OWNED = "cart_item_id = %s::uuid AND cart_id = (SELECT cart_id FROM app.carts WHERE cdp_user_id = %s)"


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True


class PostgresCartRepository:
    def __init__(self, database_url: str):
        self._database_url = database_url

    def _connect(self):
        return psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row, autocommit=True)

    @staticmethod
    async def _cart(conn, cdp_user_id: str) -> dict:
        """Giỏ đang mở của khách; chưa có thì tạo (UNIQUE cdp_user_id, chịu được hai request song song)."""
        select = "SELECT cart_id, updated_at FROM app.carts WHERE cdp_user_id = %s"
        row = await (await conn.execute(select, (cdp_user_id,))).fetchone()
        if row is None:
            await conn.execute("INSERT INTO app.carts (cdp_user_id) VALUES (%s) ON CONFLICT (cdp_user_id) DO NOTHING",
                               (cdp_user_id,))
            row = await (await conn.execute(select, (cdp_user_id,))).fetchone()
        return row

    @staticmethod
    async def _touch(conn, cdp_user_id: str) -> None:
        await conn.execute("UPDATE app.carts SET updated_at = now() WHERE cdp_user_id = %s", (cdp_user_id,))

    async def load(self, cdp_user_id: str) -> Cart:
        async with await self._connect() as conn:
            cart = await self._cart(conn, cdp_user_id)
            rows = await (await conn.execute(_ITEMS, (cart["cart_id"],))).fetchall()
        return Cart(
            cart_id=str(cart["cart_id"]), cdp_user_id=cdp_user_id, updated_at=cart["updated_at"],
            lines=tuple(CartLine(
                cart_item_id=row["cart_item_id"], product_id=row["product_id"], quantity=row["quantity"],
                using_date=row["using_date"], using_date_to=row["using_date_to"],
                unit_price_snapshot=float(row["unit_price_snapshot"]), added_at=row["added_at"],
            ) for row in rows),
        )

    async def add(self, cdp_user_id: str, product_id: str, using_date: date, using_date_to: date | None,
                  quantity: int, unit_price: float) -> None:
        async with await self._connect() as conn:
            async with conn.transaction():
                cart = await self._cart(conn, cdp_user_id)
                await conn.execute(
                    """
                    INSERT INTO app.cart_items (cart_id, product_id, quantity, using_date, using_date_to,
                                                unit_price_snapshot)
                    VALUES (%s, %s::uuid, %s, %s, %s, %s)
                    ON CONFLICT (cart_id, product_id, using_date)
                    DO UPDATE SET quantity = app.cart_items.quantity + EXCLUDED.quantity
                    """,
                    (cart["cart_id"], product_id, quantity, using_date, using_date_to, unit_price),
                )
                await self._touch(conn, cdp_user_id)

    async def update(self, cdp_user_id: str, cart_item_id: str, using_date: date, using_date_to: date | None,
                     quantity: int) -> bool:
        if not _is_uuid(cart_item_id):
            return False
        async with await self._connect() as conn:
            async with conn.transaction():
                cursor = await conn.execute(
                    f"UPDATE app.cart_items SET using_date = %s, using_date_to = %s, quantity = %s WHERE {_OWNED}",
                    (using_date, using_date_to, quantity, cart_item_id, cdp_user_id),
                )
                if cursor.rowcount:
                    await self._touch(conn, cdp_user_id)
                return cursor.rowcount > 0

    async def remove(self, cdp_user_id: str, cart_item_id: str) -> bool:
        if not _is_uuid(cart_item_id):
            return False
        async with await self._connect() as conn:
            async with conn.transaction():
                cursor = await conn.execute(f"DELETE FROM app.cart_items WHERE {_OWNED}", (cart_item_id, cdp_user_id))
                if cursor.rowcount:
                    await self._touch(conn, cdp_user_id)
                return cursor.rowcount > 0
