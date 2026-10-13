"""StripePaymentGateway: Checkout Session, Refund và kiểm chữ ký webhook, gọi REST của Stripe bằng httpx.

- Chỉ chạy với khoá test (`sk_test_…`); composition root từ chối khởi động nếu nhận `sk_live_…`.
- Mọi lệnh ghi có `Idempotency-Key`; timeout 10 giây, tự thử lại khi lỗi mạng hoặc 5xx.
- Không ghi log body/response: có thể chứa email; chỉ log mã HTTP và thao tác (NFR-SEC-03).
- Không dùng SDK `stripe`: bốn endpoint là đủ, và httpx cho phép test offline bằng MockTransport.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Any, Sequence

import httpx

from src.backend.app.application.ports.payment_gateway import (
    CheckoutLine,
    CheckoutSession,
    ExpireResult,
    InvalidWebhookSignature,
    PaymentEvent,
    PaymentProviderError,
    PaymentProviderUnavailable,
    Refund,
)

logger = logging.getLogger(__name__)
STRIPE_API = "https://api.stripe.com"
_TIMEOUT_SECONDS = 10.0
_RETRIES = 2
_SIGNATURE_TOLERANCE_SECONDS = 300


def _flatten(prefix: str, value: Any, out: dict[str, str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _flatten(f"{prefix}[{key}]" if prefix else key, item, out)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _flatten(f"{prefix}[{index}]", item, out)
    elif value is not None:
        out[prefix] = str(value).lower() if isinstance(value, bool) else str(value)


def encode_form(params: dict[str, Any]) -> dict[str, str]:
    """Stripe nhận form-encoded với khoá lồng dạng `a[b][0][c]`."""
    out: dict[str, str] = {}
    _flatten("", params, out)
    return out


def _session(data: dict) -> CheckoutSession:
    return CheckoutSession(
        session_id=data["id"], url=data.get("url"), status=data.get("status", "open"),
        payment_status=data.get("payment_status") or "unpaid", payment_intent_id=data.get("payment_intent"),
        amount_total=data.get("amount_total"), currency=data.get("currency"),
    )


class StripePaymentGateway:
    def __init__(
        self, secret_key: str, webhook_secret: str, *, client: httpx.AsyncClient | None = None,
        base_url: str = STRIPE_API, retry_delay_seconds: float = 0.3,
    ):
        self._secret, self._webhook_secret = secret_key, webhook_secret
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT_SECONDS)
        self._owns_client = client is None
        self._retry_delay = retry_delay_seconds

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(
        self, method: str, path: str, *, data: dict[str, Any] | None = None, idempotency_key: str | None = None,
    ) -> dict:
        if not self._secret:
            raise PaymentProviderUnavailable("STRIPE_SECRET_KEY chưa cấu hình")
        headers = {"Authorization": f"Bearer {self._secret}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        last: Exception | None = None
        for attempt in range(_RETRIES + 1):
            try:
                response = await self._client.request(
                    method, path, headers=headers, data=encode_form(data) if data else None)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last = exc
                logger.warning("stripe.request.network_error op=%s attempt=%d", path, attempt)
            else:
                if response.status_code >= 500 or response.status_code == 429:
                    last = PaymentProviderUnavailable(f"stripe {response.status_code}")
                    logger.warning("stripe.request.unavailable op=%s status=%d attempt=%d",
                                   path, response.status_code, attempt)
                elif response.status_code >= 400:
                    error = (response.json().get("error") or {}) if response.content else {}
                    logger.warning("stripe.request.rejected op=%s status=%d code=%s",
                                   path, response.status_code, error.get("code"))
                    raise _Rejected(response.status_code, error.get("code"), error.get("message", ""))
                else:
                    return response.json()
            if attempt < _RETRIES:
                await asyncio.sleep(self._retry_delay)
        raise PaymentProviderUnavailable(str(last)) from last

    async def create_checkout_session(
        self, *, booking_id: str, reference_code: str, cdp_user_id: str, customer_email: str,
        lines: Sequence[CheckoutLine], expires_at: datetime, success_url: str, cancel_url: str, idempotency_key: str,
    ) -> CheckoutSession:
        params = {
            "mode": "payment",
            "locale": "vi",
            "submit_type": "book",
            "expires_at": int(expires_at.timestamp()),
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": reference_code,
            "customer_email": customer_email,
            "metadata": {"bookingId": booking_id},
            "payment_intent_data": {"metadata": {"bookingId": booking_id}},
            "line_items": [
                {"quantity": line.quantity,
                 "price_data": {"currency": "vnd", "unit_amount": line.unit_amount,
                                "product_data": {"name": line.name}}}
                for line in lines
            ],
        }
        try:
            return _session(await self._request(
                "POST", "/v1/checkout/sessions", data=params, idempotency_key=idempotency_key))
        except _Rejected as exc:
            raise PaymentProviderError(str(exc)) from exc

    async def expire_checkout_session(self, session_id: str) -> ExpireResult:
        try:
            await self._request("POST", f"/v1/checkout/sessions/{session_id}/expire")
            return "expired"
        except _Rejected as exc:
            if exc.status != 400:
                raise PaymentProviderError(str(exc)) from exc
        # 400: phiên không còn ở trạng thái open. Hỏi lại để biết đã trả tiền hay đã hết hạn.
        session = await self.retrieve_checkout_session(session_id)
        if session.status == "complete":
            return "already_complete"
        if session.status == "expired":
            return "already_expired"
        raise PaymentProviderError(f"không đóng được phiên {session_id}")

    async def retrieve_checkout_session(self, session_id: str) -> CheckoutSession:
        try:
            return _session(await self._request("GET", f"/v1/checkout/sessions/{session_id}"))
        except _Rejected as exc:
            raise PaymentProviderError(str(exc)) from exc

    async def create_refund(
        self, *, booking_id: str, payment_intent_id: str, amount: int, idempotency_key: str
    ) -> Refund:
        params = {"payment_intent": payment_intent_id, "amount": amount, "reason": "requested_by_customer",
                  "metadata": {"bookingId": booking_id}}
        try:
            data = await self._request("POST", "/v1/refunds", data=params, idempotency_key=idempotency_key)
        except _Rejected as exc:
            raise PaymentProviderError(str(exc)) from exc
        return Refund(refund_id=data["id"], status=data.get("status", "pending"), amount=data.get("amount", amount))

    # --- webhook ---------------------------------------------------------------------------------

    def _verify(self, raw_body: bytes, header: str | None, now: float) -> None:
        if not header or not self._webhook_secret:
            raise InvalidWebhookSignature("thiếu chữ ký")
        parts = dict(pair.split("=", 1) for pair in header.split(",") if "=" in pair)
        timestamp = parts.get("t")
        signatures = [value for key, value in (p.split("=", 1) for p in header.split(",") if "=" in p) if key == "v1"]
        if not timestamp or not signatures or not timestamp.isdigit():
            raise InvalidWebhookSignature("chữ ký sai định dạng")
        if abs(now - int(timestamp)) > _SIGNATURE_TOLERANCE_SECONDS:
            raise InvalidWebhookSignature("timestamp quá cũ")
        expected = hmac.new(
            self._webhook_secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
            raise InvalidWebhookSignature("chữ ký không khớp")

    def parse_webhook(self, raw_body: bytes, signature_header: str | None, *, now: float | None = None) -> PaymentEvent | None:
        self._verify(raw_body, signature_header, time.time() if now is None else now)
        try:
            event = json.loads(raw_body)
            kind, obj = event["type"], event["data"]["object"]
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidWebhookSignature("payload không đọc được") from exc
        event_id = event.get("id", "")
        metadata = obj.get("metadata") or {}
        booking_id = metadata.get("bookingId")
        if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            return PaymentEvent(
                event_id=event_id, kind="checkout_completed", booking_id=booking_id, session_id=obj.get("id"),
                payment_intent_id=obj.get("payment_intent"), payment_status=obj.get("payment_status"),
                amount=obj.get("amount_total"), currency=obj.get("currency"))
        if kind == "checkout.session.expired":
            return PaymentEvent(event_id=event_id, kind="checkout_expired", booking_id=booking_id,
                                session_id=obj.get("id"))
        if kind == "payment_intent.payment_failed":
            error = obj.get("last_payment_error") or {}
            return PaymentEvent(
                event_id=event_id, kind="payment_failed", booking_id=booking_id, payment_intent_id=obj.get("id"),
                decline_code=error.get("decline_code"), error_code=error.get("code"))
        if kind in ("refund.updated", "refund.created", "refund.failed"):
            return PaymentEvent(
                event_id=event_id, kind="refund_updated", booking_id=booking_id,
                payment_intent_id=obj.get("payment_intent"), refund_id=obj.get("id"),
                refund_status=obj.get("status"), amount=obj.get("amount"))
        if kind == "charge.dispute.created":
            return PaymentEvent(event_id=event_id, kind="dispute_created",
                                payment_intent_id=obj.get("payment_intent"), amount=obj.get("amount"))
        return None


class _Rejected(Exception):
    def __init__(self, status: int, code: str | None, message: str):
        super().__init__(f"stripe {status} {code}")
        self.status = status
