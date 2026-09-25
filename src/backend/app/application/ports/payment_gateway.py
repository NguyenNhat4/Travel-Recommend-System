"""Port tới cổng thanh toán (Stripe). Use case chỉ biết interface này; SDK/HTTP nằm ở infrastructure/payments."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, Sequence

ExpireResult = Literal["expired", "already_complete", "already_expired"]
PaymentEventKind = Literal["checkout_completed", "checkout_expired", "payment_failed", "refund_updated", "dispute_created"]


class PaymentProviderUnavailable(Exception):
    """Timeout, lỗi mạng hoặc 5xx từ cổng thanh toán: đáng thử lại (503 PAYMENT_PROVIDER_UNAVAILABLE)."""


class PaymentProviderError(Exception):
    """Cổng thanh toán từ chối yêu cầu (4xx): thử lại nguyên vẹn không có tác dụng."""


class InvalidWebhookSignature(Exception):
    pass


@dataclass(frozen=True)
class CheckoutLine:
    name: str
    unit_amount: int  # VND, không có số lẻ
    quantity: int


@dataclass(frozen=True)
class CheckoutSession:
    session_id: str
    url: str | None
    status: Literal["open", "complete", "expired"]
    payment_status: Literal["paid", "unpaid", "no_payment_required"] = "unpaid"
    payment_intent_id: str | None = None
    amount_total: int | None = None
    currency: str | None = None


@dataclass(frozen=True)
class Refund:
    refund_id: str
    status: Literal["pending", "succeeded", "failed", "canceled", "requires_action"]
    amount: int


@dataclass(frozen=True)
class PaymentEvent:
    """Sự kiện webhook đã được xác thực chữ ký và chuẩn hoá; loại không quan tâm không sinh PaymentEvent."""

    event_id: str
    kind: PaymentEventKind
    booking_id: str | None = None
    session_id: str | None = None
    payment_intent_id: str | None = None
    payment_status: str | None = None
    amount: int | None = None
    currency: str | None = None
    decline_code: str | None = None
    error_code: str | None = None
    refund_id: str | None = None
    refund_status: str | None = None


class PaymentGateway(Protocol):
    async def create_checkout_session(
        self,
        *,
        booking_id: str,
        reference_code: str,
        cdp_user_id: str,
        customer_email: str,
        lines: Sequence[CheckoutLine],
        expires_at: datetime,
        success_url: str,
        cancel_url: str,
        idempotency_key: str,
    ) -> CheckoutSession: ...

    async def expire_checkout_session(self, session_id: str) -> ExpireResult: ...

    async def retrieve_checkout_session(self, session_id: str) -> CheckoutSession: ...

    async def create_refund(
        self, *, booking_id: str, payment_intent_id: str, amount: int, idempotency_key: str
    ) -> Refund: ...

    def parse_webhook(self, raw_body: bytes, signature_header: str | None) -> PaymentEvent | None:
        """Kiểm chữ ký rồi chuẩn hoá. None = loại event bỏ qua. Sai chữ ký ném InvalidWebhookSignature."""
        ...
