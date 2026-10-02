"""FakeGateway: cổng thanh toán giả, không gọi mạng.

Dùng cho test và cho `PAYMENT_PROVIDER=fake` (chạy offline, tái hiện lỗi Stripe không phản hồi). Không dùng ở production.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Sequence

from src.backend.app.application.ports.payment_gateway import (
    CheckoutLine,
    CheckoutSession,
    ExpireResult,
    InvalidWebhookSignature,
    PaymentEvent,
    PaymentProviderUnavailable,
    Refund,
)

VALID_SIGNATURE = "fake-valid"


class FakeGateway:
    def __init__(self, *, mode: str = "ok", refund_status: str = "succeeded"):
        self.mode = mode  # "ok" | "timeout"
        self.refund_status = refund_status
        self.sessions: dict[str, dict] = {}
        self.refunds: dict[str, Refund] = {}
        self.calls: list[str] = []
        self.idempotency_keys: dict[str, CheckoutSession] = {}

    def _guard(self, name: str) -> None:
        self.calls.append(name)
        if self.mode == "timeout":
            raise PaymentProviderUnavailable("fake timeout")

    async def create_checkout_session(
        self, *, booking_id: str, reference_code: str, cdp_user_id: str, customer_email: str,
        lines: Sequence[CheckoutLine], expires_at: datetime, success_url: str, cancel_url: str, idempotency_key: str,
    ) -> CheckoutSession:
        self._guard("create_checkout_session")
        if idempotency_key in self.idempotency_keys:
            return self.idempotency_keys[idempotency_key]
        session_id = f"cs_fake_{uuid.uuid4().hex[:12]}"
        amount = sum(line.unit_amount * line.quantity for line in lines)
        self.sessions[session_id] = {"booking_id": booking_id, "amount": amount, "status": "open",
                                     "payment_status": "unpaid", "payment_intent": None, "lines": list(lines),
                                     "customer_email": customer_email}
        session = CheckoutSession(session_id=session_id, url=f"https://checkout.fake/{session_id}", status="open",
                                  amount_total=amount, currency="vnd")
        self.idempotency_keys[idempotency_key] = session
        return session

    async def expire_checkout_session(self, session_id: str) -> ExpireResult:
        self._guard("expire_checkout_session")
        session = self.sessions[session_id]
        if session["status"] == "complete":
            return "already_complete"
        if session["status"] == "expired":
            return "already_expired"
        session["status"] = "expired"
        return "expired"

    async def retrieve_checkout_session(self, session_id: str) -> CheckoutSession:
        self._guard("retrieve_checkout_session")
        s = self.sessions[session_id]
        return CheckoutSession(session_id=session_id, url=None, status=s["status"], payment_status=s["payment_status"],
                               payment_intent_id=s["payment_intent"], amount_total=s["amount"], currency="vnd")

    async def create_refund(
        self, *, booking_id: str, payment_intent_id: str, amount: int, idempotency_key: str
    ) -> Refund:
        self._guard("create_refund")
        if idempotency_key not in self.refunds:
            self.refunds[idempotency_key] = Refund(f"re_fake_{uuid.uuid4().hex[:10]}", self.refund_status, amount)
        return self.refunds[idempotency_key]

    def parse_webhook(self, raw_body: bytes, signature_header: str | None) -> PaymentEvent | None:
        if signature_header != VALID_SIGNATURE:
            raise InvalidWebhookSignature("fake: chữ ký sai")
        data = json.loads(raw_body)
        return PaymentEvent(**data) if data.get("kind") else None

    # --- điều khiển từ test ---------------------------------------------------------------------

    def pay(self, session_id: str, *, amount: int | None = None) -> PaymentEvent:
        """Khách trả tiền thành công trên trang thanh toán; trả về webhook tương ứng."""
        s = self.sessions[session_id]
        s.update(status="complete", payment_status="paid", payment_intent=f"pi_fake_{session_id[-6:]}")
        return PaymentEvent(
            event_id=f"evt_{uuid.uuid4().hex[:8]}", kind="checkout_completed", booking_id=s["booking_id"],
            session_id=session_id, payment_intent_id=s["payment_intent"], payment_status="paid",
            amount=s["amount"] if amount is None else amount, currency="vnd")

    def decline(self, session_id: str, decline_code: str = "generic_decline") -> PaymentEvent:
        s = self.sessions[session_id]
        return PaymentEvent(event_id=f"evt_{uuid.uuid4().hex[:8]}", kind="payment_failed", booking_id=s["booking_id"],
                            payment_intent_id=f"pi_fake_{session_id[-6:]}", decline_code=decline_code)

    def expire_event(self, session_id: str) -> PaymentEvent:
        s = self.sessions[session_id]
        s["status"] = "expired"
        return PaymentEvent(event_id=f"evt_{uuid.uuid4().hex[:8]}", kind="checkout_expired",
                            booking_id=s["booking_id"], session_id=session_id)
