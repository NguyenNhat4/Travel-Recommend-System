"""Đọc lại đơn của chính người dùng (backend spec §7.3)."""
from __future__ import annotations

from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.booking.errors import BookingNotFound
from src.backend.app.application.booking.views import booking_response
from src.backend.app.application.ports.booking_store import BookingStore
from src.backend.app.application.ports.product_catalog import ProductCatalog


class GetBooking:
    def __init__(self, store: BookingStore, catalog: ProductCatalog):
        self._store, self._catalog = store, catalog

    async def __call__(self, principal: AuthPrincipal, reference_code: str) -> dict:
        async with self._store.transaction() as tx:
            booking = await tx.get_by_reference(reference_code, principal.cdp_user_id)
        if booking is None:
            # Mã của người khác cũng trả 404, không lộ mã nào tồn tại.
            raise BookingNotFound("không tìm thấy đơn")
        products = await self._catalog.get_products([i.product_id for i in booking.items])
        return booking_response(booking, products)
