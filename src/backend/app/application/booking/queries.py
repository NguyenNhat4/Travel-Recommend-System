"""Đọc lại đơn của chính người dùng (backend spec §7.3) và liệt kê đơn (FR-BKG-14)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.booking.errors import BookingNotFound
from src.backend.app.application.booking.views import booking_response, booking_summary, pagination
from src.backend.app.application.ports.booking_store import BookingStore
from src.backend.app.application.ports.product_catalog import ProductCatalog
from src.backend.app.domain.booking import BookingTab, tab_of


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


class ListBookings:
    """Một trang đơn của chính người dùng, mới nhất trước. Tab, lọc và đếm dùng chung `tab_of` của domain."""

    def __init__(self, store: BookingStore, clock: Callable[[], datetime]):
        self._store, self._clock = store, clock

    async def __call__(
        self, principal: AuthPrincipal, *, tab: BookingTab = BookingTab.UPCOMING, taxonomy: str | None = None,
        days: int | None = None, page: int = 1, page_size: int = 20,
    ) -> dict:
        now = self._clock()
        since = now - timedelta(days=days) if days else None
        async with self._store.transaction() as tx:
            overviews = await tx.list_overviews(principal.cdp_user_id, since)
            matching = [
                o for o in overviews
                if tab_of(o, now) is tab and (taxonomy is None or taxonomy in o.taxonomies)]
            start = (page - 1) * page_size
            page_ids = [o.booking_id for o in matching[start:start + page_size]]
            bookings = await tx.get_many(page_ids)
        return {
            "data": [booking_summary(b, tab) for b in bookings],
            "pagination": pagination(page, page_size, len(matching)),
        }
