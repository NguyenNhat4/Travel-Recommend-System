"""Các bước sau khi có tiền: xác nhận đơn, hoàn tiền, huỷ event purchase (spec booking §6.3, §9.2).

Mỗi hàm idempotent theo trạng thái đã lưu, nên webhook gửi trùng và job đối soát gọi lại đều an toàn.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from src.backend.app.application.booking.purchase_events import record_then_commit
from src.backend.app.application.ports.booking_store import BookingStore
from src.backend.app.application.ports.cdp_client import CdpClient, CdpUnavailableError, PurchaseEvent
from src.backend.app.application.ports.payment_gateway import (
    PaymentGateway,
    PaymentProviderError,
    PaymentProviderUnavailable,
)
from src.backend.app.core.request_context import current_request_id
from src.backend.app.domain.booking import Booking
from src.backend.app.domain.booking.status import BookingStatus, PaymentStatus

logger = logging.getLogger(__name__)


def purchase_events(booking: Booking, timestamp: datetime) -> list[PurchaseEvent]:
    return [
        PurchaseEvent(
            booking_item_id=item.booking_item_id, cdp_user_id=booking.cdp_user_id, product_id=item.product_id,
            taxonomy=item.taxonomy, event_group_id=booking.event_group_id, quantity=item.quantity,
            unit_price=float(item.unit_price), using_date=item.using_date, timestamp=timestamp,
        )
        for item in booking.items
    ]


class Settlement:
    def __init__(self, store: BookingStore, gateway: PaymentGateway, cdp: CdpClient, clock: Callable[[], datetime]):
        self._store, self._gateway, self._cdp, self._clock = store, gateway, cdp, clock

    async def confirm_paid(self, booking_id: str) -> Booking | None:
        """Đơn đã thu tiền nhưng chưa xác nhận: ghi purchase sang CDP rồi commit CONFIRMED.

        CDP lỗi thì CdpUnavailableError nổi lên (webhook trả 500 để Stripe gửi lại) và KHÔNG huỷ event nào:
        khách đã trả tiền nên đơn phải được xác nhận.
        """
        async with self._store.transaction() as tx:
            booking = await tx.get_by_id(booking_id, lock=True)
            if (booking is None or booking.status is not BookingStatus.PENDING_PAYMENT
                    or booking.payment is None or booking.payment.status is not PaymentStatus.SUCCEEDED):
                return booking
            now = self._clock()

            async def commit() -> None:
                booking.confirm(now)
                await tx.save(booking)
                await tx.clear_cart_items(booking.cdp_user_id, [(i.product_id, i.using_date) for i in booking.items])

            try:
                await record_then_commit(self._cdp, purchase_events(booking, now), commit)
            except CdpUnavailableError:
                logger.warning("booking.confirm.cdp_unavailable bookingId=%s requestId=%s",
                               booking_id, current_request_id())
                raise
            return booking

    async def refund(self, booking_id: str) -> None:
        """Gọi Refund API cho thanh toán REFUND_PENDING chưa có refund_id. Lỗi tạm thời thì để job đối soát gọi lại."""
        async with self._store.transaction() as tx:
            booking = await tx.get_by_id(booking_id, lock=True)
            payment = booking.payment if booking else None
            if (payment is None or payment.status is not PaymentStatus.REFUND_PENDING or payment.refund_id
                    or not payment.payment_intent_id):
                return
            try:
                refund = await self._gateway.create_refund(
                    booking_id=booking_id, payment_intent_id=payment.payment_intent_id, amount=payment.amount,
                    idempotency_key=f"refund:{booking_id}",
                )
            except PaymentProviderUnavailable:
                logger.warning("booking.refund.provider_unavailable bookingId=%s requestId=%s",
                               booking_id, current_request_id())
                return
            except PaymentProviderError:
                logger.error("booking.refund.rejected bookingId=%s paymentIntentId=%s",
                             booking_id, payment.payment_intent_id)
                booking.finish_refund(succeeded=False)
                await tx.save(booking)
                return
            if refund.status == "succeeded":
                booking.finish_refund(succeeded=True)
                payment.refund_id = refund.refund_id
            elif refund.status in ("failed", "canceled"):
                logger.error("booking.refund.failed bookingId=%s paymentIntentId=%s",
                             booking_id, payment.payment_intent_id)
                booking.finish_refund(succeeded=False)
                payment.refund_id = refund.refund_id
            else:
                booking.start_refund(refund.refund_id)
            await tx.save(booking)

    async def cancel_purchase_events(self, booking_id: str) -> None:
        """Đánh dấu huỷ event purchase trên CDP để gợi ý không dùng chuyến đã huỷ (CDP §3.3 mục 3)."""
        async with self._store.transaction() as tx:
            booking = await tx.get_by_id(booking_id, lock=True)
            if (booking is None or booking.status is not BookingStatus.CANCELLED or booking.confirmed_at is None
                    or booking.purchase_events_cancelled_at is not None):
                return
            now = self._clock()
            try:
                await self._cdp.cancel_purchases(purchase_events(booking, booking.confirmed_at))
            except CdpUnavailableError:
                logger.warning("booking.cancel_events.cdp_unavailable bookingId=%s requestId=%s",
                               booking_id, current_request_id())
                return
            booking.purchase_events_cancelled_at = now
            await tx.save(booking)
