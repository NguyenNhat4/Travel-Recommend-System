"""Khách huỷ đơn (spec booking §9, FR-BKG-07)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.booking.errors import (
    BookingAlreadyPaid,
    BookingNotCancellable,
    BookingNotFound,
    PaymentUnavailable,
)
from src.backend.app.application.booking.settlement import Settlement
from src.backend.app.application.booking.views import booking_response, iso
from src.backend.app.application.ports.booking_store import BookingStore
from src.backend.app.application.ports.payment_gateway import PaymentGateway, PaymentProviderUnavailable
from src.backend.app.application.ports.product_catalog import ProductCatalog
from src.backend.app.domain.booking import CancelDecision, cancellable_until, decide_cancellation

logger = logging.getLogger(__name__)


class CancelBooking:
    def __init__(
        self, store: BookingStore, gateway: PaymentGateway, settlement: Settlement, catalog: ProductCatalog,
        clock: Callable[[], datetime],
    ):
        self._store, self._gateway, self._settlement = store, gateway, settlement
        self._catalog, self._clock = catalog, clock

    async def __call__(self, principal: AuthPrincipal, reference_code: str, reason: str | None) -> dict:
        refund_needed = False
        async with self._store.transaction() as tx:
            booking = await tx.get_by_reference(reference_code, principal.cdp_user_id, lock=True)
            if booking is None:
                raise BookingNotFound("không tìm thấy đơn")
            now = self._clock()
            decision = decide_cancellation(booking, now)
            details = {"referenceCode": booking.reference_code}
            if decision is CancelDecision.NOT_ACTIVE:
                raise BookingNotCancellable("đơn không còn hiệu lực", {**details, "reason": "NOT_ACTIVE"})
            if decision is CancelDecision.TOO_LATE:
                raise BookingNotCancellable("đã quá hạn huỷ trực tuyến", {
                    **details, "reason": "TOO_LATE", "cancellableUntil": iso(cancellable_until(booking.items))})
            if decision is CancelDecision.ALREADY_PAID:
                raise BookingAlreadyPaid("đơn vừa được thanh toán", details)
            if decision is CancelDecision.EXPIRE_SESSION:
                # Đóng phiên Stripe được thì mới ghi CANCELLED, để khách không trả tiền được cho đơn đã huỷ.
                try:
                    result = await self._gateway.expire_checkout_session(booking.payment.checkout_session_id)
                except PaymentProviderUnavailable as exc:
                    raise PaymentUnavailable("cổng thanh toán không phản hồi") from exc
                if result == "already_complete":
                    raise BookingAlreadyPaid("đơn vừa được thanh toán", details)
                booking.cancel_unpaid(now, reason)
                await tx.save(booking)
            elif decision is CancelDecision.REFUND_FULL:
                # Ghi CANCELLED + REFUND_PENDING trước khi gọi Stripe: database là bản ghi bền của việc phải hoàn tiền.
                booking.cancel_paid(now, reason)
                await tx.save(booking)
                refund_needed = True
            booking_id = booking.booking_id
        if refund_needed:
            await self._settlement.refund(booking_id)
            await self._settlement.cancel_purchase_events(booking_id)
        async with self._store.transaction() as tx:
            booking = await tx.get_by_id(booking_id)
        products = await self._catalog.get_products([i.product_id for i in booking.items])
        return booking_response(booking, products)
