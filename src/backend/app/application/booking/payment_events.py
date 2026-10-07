"""Xử lý webhook đã xác thực chữ ký (spec booking §6.3, §7.3, §8.3, §9.2). Idempotent theo máy trạng thái."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from src.backend.app.application.booking.settlement import Settlement
from src.backend.app.application.ports.booking_store import BookingStore
from src.backend.app.application.ports.payment_gateway import PaymentEvent, PaymentGateway, PaymentProviderUnavailable
from src.backend.app.core.logging_config import log_event
from src.backend.app.domain.booking import Booking, failure_reason_from_stripe
from src.backend.app.domain.booking.status import BookingStatus, PaymentStatus

logger = logging.getLogger(__name__)
_CLOSED = (BookingStatus.PAYMENT_FAILED, BookingStatus.EXPIRED, BookingStatus.CANCELLED)


class PaymentEventHandler:
    def __init__(
        self, store: BookingStore, gateway: PaymentGateway, settlement: Settlement, *, max_failed_attempts: int,
        clock: Callable[[], datetime],
    ):
        self._store, self._gateway, self._settlement = store, gateway, settlement
        self._max_attempts, self._clock = max_failed_attempts, clock

    async def __call__(self, event: PaymentEvent) -> None:
        handler = {
            "checkout_completed": self._completed,
            "checkout_expired": self._expired,
            "payment_failed": self._failed,
            "refund_updated": self._refund_updated,
            "dispute_created": self._dispute,
        }[event.kind]
        await handler(event)

    async def _load(self, tx, event: PaymentEvent) -> Booking | None:
        booking = await tx.get_by_id(event.booking_id, lock=True) if event.booking_id else None
        if booking is None and event.session_id:
            booking = await tx.get_by_session(event.session_id, lock=True)
        return booking

    async def _completed(self, event: PaymentEvent) -> None:
        if event.payment_status != "paid":
            return  # thanh toán trễ (chuyển khoản...) không dùng trong dự án; chờ event sau
        booking_id: str | None = None
        rejected = False
        ref = amount = items = None
        async with self._store.transaction() as tx:
            booking = await self._load(tx, event)
            if booking is None or booking.payment is None:
                logger.error("payment.completed.no_booking sessionId=%s paymentIntentId=%s",
                             event.session_id, event.payment_intent_id)
                return
            payment = booking.payment
            if booking.status is BookingStatus.CONFIRMED or payment.status in (
                    PaymentStatus.REFUND_PENDING, PaymentStatus.REFUNDED, PaymentStatus.REFUND_FAILED):
                return  # gửi trùng, hoặc đã xử lý (kể cả đã chuyển sang hoàn tiền)
            if booking.status is BookingStatus.PENDING_PAYMENT and payment.status not in (
                    PaymentStatus.OPEN, PaymentStatus.SUCCEEDED):
                return
            if booking.status in _CLOSED:
                # Tiền về cho đơn đã đóng: nhận rồi hoàn ngay để khách không mất tiền.
                logger.error("payment.completed.booking_closed bookingId=%s sessionId=%s paymentIntentId=%s",
                             booking.booking_id, event.session_id, event.payment_intent_id)
                payment.payment_intent_id = event.payment_intent_id or payment.payment_intent_id
                booking.reject_paid("BOOKING_CLOSED")
            elif (event.amount is not None and event.amount != payment.amount) or (
                    event.currency and event.currency.lower() != payment.currency.lower()):
                logger.error("payment.completed.amount_mismatch bookingId=%s sessionId=%s paymentIntentId=%s",
                             booking.booking_id, event.session_id, event.payment_intent_id)
                payment.payment_intent_id = event.payment_intent_id or payment.payment_intent_id
                booking.reject_paid("AMOUNT_MISMATCH")
            else:
                booking.record_payment_received(event.payment_intent_id)
            await tx.save(booking)
            booking_id, rejected = booking.booking_id, payment.status is PaymentStatus.REFUND_PENDING
            ref, amount, items = booking.reference_code, booking.total_amount, len(booking.items)
        if rejected:
            await self._settlement.refund(booking_id)
            return
        await self._settlement.confirm_paid(booking_id)
        log_event(logger, "payment.settled", booking_ref=ref, amount_vnd=amount, item_count=items,
                  event_id=event.event_id)

    async def _expired(self, event: PaymentEvent) -> None:
        async with self._store.transaction() as tx:
            booking = await self._load(tx, event)
            if (booking and booking.status is BookingStatus.PENDING_PAYMENT and booking.payment
                    and booking.payment.status is PaymentStatus.OPEN):
                booking.expire()
                await tx.save(booking)

    async def _failed(self, event: PaymentEvent) -> None:
        session_id: str | None = None
        async with self._store.transaction() as tx:
            booking = await self._load(tx, event)
            if (booking is None or booking.status is not BookingStatus.PENDING_PAYMENT or booking.payment is None
                    or booking.payment.status is not PaymentStatus.OPEN):
                return
            reason = failure_reason_from_stripe(event.decline_code, event.error_code)
            final = booking.register_card_failure(reason, self._max_attempts)
            log_event(logger, "payment.failed", "WARNING", booking_ref=booking.reference_code,
                      amount_vnd=booking.total_amount, item_count=len(booking.items), decline_code=event.decline_code,
                      failed_attempts=booking.payment.failed_attempts, event_id=event.event_id)
            await tx.save(booking)
            session_id = booking.payment.checkout_session_id if final else None
        if session_id:
            try:
                await self._gateway.expire_checkout_session(session_id)
            except PaymentProviderUnavailable:
                # Đơn đã PAYMENT_FAILED; nếu phiên còn mở và khách trả tiền thì nhánh "đơn đã đóng" sẽ hoàn tiền.
                logger.error("payment.failed.expire_session_failed sessionId=%s", session_id)

    async def _refund_updated(self, event: PaymentEvent) -> None:
        async with self._store.transaction() as tx:
            booking = await self._load(tx, event)
            if (booking is None or booking.payment is None
                    or booking.payment.status is not PaymentStatus.REFUND_PENDING):
                return
            if event.refund_status == "succeeded":
                booking.finish_refund(succeeded=True)
            elif event.refund_status in ("failed", "canceled"):
                logger.error("payment.refund.failed bookingId=%s paymentIntentId=%s",
                             booking.booking_id, booking.payment.payment_intent_id)
                booking.finish_refund(succeeded=False)
            else:
                return
            booking.payment.refund_id = event.refund_id or booking.payment.refund_id
            await tx.save(booking)

    async def _dispute(self, event: PaymentEvent) -> None:
        # Tranh chấp chỉ ghi log, xử lý tay (đề xuất Q8).
        logger.error("payment.dispute paymentIntentId=%s amount=%s", event.payment_intent_id, event.amount)
