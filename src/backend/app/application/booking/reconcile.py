"""Job đối soát chạy nền (spec booking §8.2): lo các việc dở dang khi webhook bị lỡ hoặc tiến trình chết giữa chừng."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Callable

from src.backend.app.application.booking.payment_events import PaymentEventHandler
from src.backend.app.application.booking.settlement import Settlement
from src.backend.app.application.ports.booking_store import BookingStore
from src.backend.app.application.ports.cdp_client import CdpUnavailableError
from src.backend.app.application.ports.payment_gateway import PaymentEvent, PaymentGateway, PaymentProviderUnavailable
from src.backend.app.domain.booking.status import BookingStatus, PaymentStatus

logger = logging.getLogger(__name__)
# Bản ghi đơn nháp hết hạn được giữ thêm một ngày để trang thanh toán còn báo được "hết hạn" thay vì "không tìm thấy".
DRAFT_RETENTION = timedelta(days=1)


class ReconcileBookings:
    def __init__(
        self, store: BookingStore, gateway: PaymentGateway, settlement: Settlement, handler: PaymentEventHandler,
        clock: Callable[[], datetime], *, batch_size: int = 50,
    ):
        self._store, self._gateway, self._settlement, self._handler = store, gateway, settlement, handler
        self._clock, self._batch = clock, batch_size

    async def __call__(self) -> int:
        # Nhiều worker × nhiều VM cùng chạy vòng lặp này; chỉ một nơi được đối soát mỗi lượt để
        # không gọi Stripe/CDP trùng (hoàn tiền, huỷ purchase event).
        async with self._store.reconcile_leader() as leader:
            if not leader:
                logger.debug("reconcile.skipped not_leader")
                return 0
            return await self._run()

    async def _run(self) -> int:
        async with self._store.transaction() as tx:
            ids = await tx.find_reconcile_ids(self._clock(), self._batch)
            purged = await tx.purge_expired_drafts(self._clock() - DRAFT_RETENTION)
        if purged:
            logger.info("reconcile.drafts_purged count=%d", purged)
        for booking_id in ids:
            try:
                await self.reconcile_one(booking_id)
            except (PaymentProviderUnavailable, CdpUnavailableError):
                logger.warning("reconcile.deferred bookingId=%s", booking_id)
            except Exception:
                logger.exception("reconcile.failed bookingId=%s", booking_id)
        return len(ids)

    async def reconcile_one(self, booking_id: str) -> None:
        async with self._store.transaction() as tx:
            booking = await tx.get_by_id(booking_id, lock=True)
            if booking is None or booking.payment is None:
                return
            status, payment = booking.status, booking.payment
            complete = False
            expired_open = (status is BookingStatus.PENDING_PAYMENT and payment.status is PaymentStatus.OPEN
                            and booking.hold_expires_at is not None and self._clock() >= booking.hold_expires_at)
            if expired_open:
                session = await self._gateway.retrieve_checkout_session(payment.checkout_session_id)
                if session.status == "complete" and session.payment_status == "paid":
                    event = PaymentEvent(
                        event_id=f"reconcile:{booking_id}", kind="checkout_completed", booking_id=booking_id,
                        session_id=session.session_id, payment_intent_id=session.payment_intent_id,
                        payment_status="paid", amount=session.amount_total, currency=session.currency)
                    complete = True
                else:
                    if session.status == "open" and await self._gateway.expire_checkout_session(
                            session.session_id) == "already_complete":
                        return  # khách vừa trả tiền; lần chạy sau sẽ thấy phiên complete
                    booking.expire()
                    await tx.save(booking)
                    return
        if expired_open and complete:
            await self._handler(event)
            return
        if status is BookingStatus.PENDING_PAYMENT and payment.status is PaymentStatus.SUCCEEDED:
            await self._settlement.confirm_paid(booking_id)
        elif payment.status is PaymentStatus.REFUND_PENDING and not payment.refund_id:
            await self._settlement.refund(booking_id)
        if status is BookingStatus.CANCELLED and booking.confirmed_at and not booking.purchase_events_cancelled_at:
            await self._settlement.cancel_purchase_events(booking_id)
