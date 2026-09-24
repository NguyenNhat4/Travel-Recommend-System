"""Port `BookingRepository` trên `app.bookings` / `app.booking_items` qua `DATABASE_URL` (role `vota_app`).

`app.booking_items.line_total` là cột sinh `unit_price * quantity`, không nhân số đêm; backend không đọc cột này
mà tính thành tiền bằng `domain.booking.line_total` (backend §2.6).
"""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from src.backend.app.application.ports.booking_repository import Booking, BookingLine


class PostgresBookingRepository:
    def __init__(self, database_url: str):
        self._database_url = database_url

    def _connect(self):
        return psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row, autocommit=True)

    async def reference_taken(self, reference_code: str) -> bool:
        async with await self._connect() as conn:
            row = await (await conn.execute("SELECT 1 FROM app.bookings WHERE reference_code = %s",
                                            (reference_code,))).fetchone()
        return row is not None

    async def save(self, booking: Booking) -> None:
        async with await self._connect() as conn:
            async with conn.transaction():
                row = await (await conn.execute(
                    """
                    INSERT INTO app.bookings (reference_code, cdp_user_id, event_group_id, contact_name,
                                              contact_email, contact_phone, special_request, total_amount,
                                              currency, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING booking_id
                    """,
                    (booking.reference_code, booking.cdp_user_id, booking.event_group_id, booking.contact_name,
                     booking.contact_email, booking.contact_phone, booking.special_request, booking.total_amount,
                     booking.currency, booking.created_at),
                )).fetchone()
                async with conn.cursor() as cursor:
                    await cursor.executemany(
                        """
                        INSERT INTO app.booking_items (booking_item_id, booking_id, product_id, taxonomy,
                                                       product_name, unit_price, quantity, using_date,
                                                       using_date_to, guest_names)
                        VALUES (%s::uuid, %s, %s::uuid, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        [(line.booking_item_id, row["booking_id"], line.product_id, line.taxonomy, line.product_name,
                          line.unit_price, line.quantity, line.using_date, line.using_date_to,
                          list(line.guest_names)) for line in booking.lines],
                    )
                # Checkout thành công thì xoá sạch giỏ, cùng transaction với booking (backend §7.2).
                await conn.execute(
                    "DELETE FROM app.cart_items WHERE cart_id = (SELECT cart_id FROM app.carts WHERE cdp_user_id = %s)",
                    (booking.cdp_user_id,),
                )
                await conn.execute("UPDATE app.carts SET updated_at = now() WHERE cdp_user_id = %s",
                                   (booking.cdp_user_id,))

    async def find(self, reference_code: str, cdp_user_id: str) -> Booking | None:
        async with await self._connect() as conn:
            head = await (await conn.execute(
                """
                SELECT booking_id, reference_code, cdp_user_id, event_group_id, contact_name, contact_email,
                       contact_phone, special_request, total_amount, currency, created_at
                FROM app.bookings WHERE reference_code = %s AND cdp_user_id = %s
                """,
                (reference_code, cdp_user_id),
            )).fetchone()
            if head is None:
                return None
            rows = await (await conn.execute(
                """
                SELECT booking_item_id::text AS booking_item_id, product_id::text AS product_id, taxonomy,
                       product_name, unit_price, quantity, using_date, using_date_to, guest_names
                FROM app.booking_items WHERE booking_id = %s
                ORDER BY using_date, product_name, booking_item_id
                """,
                (head["booking_id"],),
            )).fetchall()
        return Booking(
            reference_code=head["reference_code"], cdp_user_id=head["cdp_user_id"],
            event_group_id=head["event_group_id"], contact_name=head["contact_name"],
            contact_email=head["contact_email"], contact_phone=head["contact_phone"],
            special_request=head["special_request"], total_amount=int(head["total_amount"]),
            currency=(head["currency"] or "VND").strip(), created_at=head["created_at"],
            lines=tuple(BookingLine(
                booking_item_id=row["booking_item_id"], product_id=row["product_id"], taxonomy=row["taxonomy"],
                product_name=row["product_name"], unit_price=float(row["unit_price"]), quantity=row["quantity"],
                using_date=row["using_date"], using_date_to=row["using_date_to"],
                guest_names=tuple(row["guest_names"] or ()),
            ) for row in rows),
        )
