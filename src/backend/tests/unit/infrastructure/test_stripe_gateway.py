"""StripePaymentGateway trên httpx.MockTransport: không gọi mạng, không cần khoá Stripe thật."""
import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import ValidationError

from src.backend.app.application.ports.payment_gateway import (
    CheckoutLine,
    InvalidWebhookSignature,
    PaymentProviderError,
    PaymentProviderUnavailable,
)
from src.backend.app.core.config import Settings
from src.backend.app.infrastructure.payments.stripe_gateway import StripePaymentGateway, encode_form

SECRET = "sk_test_unit"
WHSEC = "whsec_unit"
NOW = 1_790_000_000


def run(handler, call):
    async def main():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://stripe.test") as http:
            return await call(StripePaymentGateway(SECRET, WHSEC, client=http, retry_delay_seconds=0))
    return asyncio.run(main())


def session_json(**kw):
    data = {"id": "cs_test_1", "url": "https://checkout.stripe.com/c/pay/cs_test_1", "status": "open",
            "payment_status": "unpaid", "payment_intent": None, "amount_total": 11_960_000, "currency": "vnd"}
    data.update(kw)
    return data


def create(gateway):
    return gateway.create_checkout_session(
        booking_id="b-1", reference_code="VOTA-20260916-AB12", cdp_user_id="VP0000001", customer_email="a@b.vn",
        lines=[CheckoutLine("Phòng Deluxe", 10_200_000, 1), CheckoutLine("Vé VinWonders", 880_000, 2)],
        expires_at=datetime(2026, 9, 16, 3, 31, tzinfo=timezone.utc),
        success_url="http://web/booking/VOTA-20260916-AB12?payment=return",
        cancel_url="http://web/booking/VOTA-20260916-AB12?payment=cancelled", idempotency_key="booking:b-1")


def signed(payload: dict, *, secret=WHSEC, timestamp=NOW) -> tuple[bytes, str]:
    body = json.dumps(payload).encode()
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return body, f"t={timestamp},v1={digest}"


def test_encode_form_flattens_nested_params_like_stripe_expects():
    assert encode_form({"a": {"b": [{"c": 1}, {"c": True}]}, "skip": None}) == {"a[b][0][c]": "1", "a[b][1][c]": "true"}


def test_create_session_sends_vnd_amounts_metadata_and_idempotency_key():
    seen = {}

    def handler(request):
        seen["headers"], seen["form"] = request.headers, parse_qs(request.content.decode())
        return httpx.Response(200, json=session_json())

    session = run(handler, create)
    form = {k: v[0] for k, v in seen["form"].items()}
    assert seen["headers"]["Authorization"] == f"Bearer {SECRET}"
    assert seen["headers"]["Idempotency-Key"] == "booking:b-1"
    assert form["mode"] == "payment" and form["locale"] == "vi" and form["submit_type"] == "book"
    assert form["line_items[0][price_data][currency]"] == "vnd"
    assert form["line_items[0][price_data][unit_amount]"] == "10200000"          # VND: không nhân 100
    assert form["line_items[1][quantity]"] == "2"
    assert form["metadata[bookingId]"] == form["payment_intent_data[metadata][bookingId]"] == "b-1"
    assert form["expires_at"] == str(int(datetime(2026, 9, 16, 3, 31, tzinfo=timezone.utc).timestamp()))
    # Stripe không còn nhận payment_method_types trên Checkout Session; phương thức do Dashboard quyết định.
    assert not any(key.startswith("payment_method_types") for key in form)
    assert session.session_id == "cs_test_1" and session.url.startswith("https://checkout.stripe.com")


def test_5xx_is_retried_then_succeeds_and_timeouts_become_unavailable():
    calls = []

    def flaky(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json=session_json())

    assert run(flaky, create).session_id == "cs_test_1" and len(calls) == 3

    def down(request):
        raise httpx.ConnectTimeout("timeout", request=request)

    with pytest.raises(PaymentProviderUnavailable):
        run(down, create)


def test_4xx_is_a_rejection_not_retried():
    calls = []

    def bad(request):
        calls.append(1)
        return httpx.Response(400, json={"error": {"code": "parameter_invalid_integer", "message": "x"}})

    with pytest.raises(PaymentProviderError):
        run(bad, create)
    assert len(calls) == 1


def test_missing_secret_key_is_treated_as_unavailable():
    async def main():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as http:
            await create(StripePaymentGateway("", WHSEC, client=http))

    with pytest.raises(PaymentProviderUnavailable):
        asyncio.run(main())


@pytest.mark.parametrize("status,expected", [("complete", "already_complete"), ("expired", "already_expired")])
def test_expire_on_closed_session_asks_stripe_what_happened(status, expected):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(400, json={"error": {"code": "checkout_session_not_open"}})
        return httpx.Response(200, json=session_json(status=status))

    assert run(handler, lambda g: g.expire_checkout_session("cs_test_1")) == expected
    assert run(lambda r: httpx.Response(200, json=session_json(status="expired")),
               lambda g: g.expire_checkout_session("cs_test_1")) == "expired"


def test_refund_uses_idempotency_key_and_maps_status():
    seen = {}

    def handler(request):
        seen["key"], seen["form"] = request.headers["Idempotency-Key"], parse_qs(request.content.decode())
        return httpx.Response(200, json={"id": "re_1", "status": "pending", "amount": 11_960_000})

    refund = run(handler, lambda g: g.create_refund(
        booking_id="b-1", payment_intent_id="pi_1", amount=11_960_000, idempotency_key="refund:b-1"))
    assert seen["key"] == "refund:b-1" and seen["form"]["payment_intent"] == ["pi_1"]
    assert (refund.refund_id, refund.status) == ("re_1", "pending")


# --- webhook ---------------------------------------------------------------------------------

def gateway():
    return StripePaymentGateway(SECRET, WHSEC, client=httpx.AsyncClient())


def test_webhook_with_valid_signature_is_normalised():
    body, header = signed({"id": "evt_1", "type": "checkout.session.completed", "data": {"object": session_json(
        status="complete", payment_status="paid", payment_intent="pi_1", metadata={"bookingId": "b-1"})}})
    event = gateway().parse_webhook(body, header, now=NOW)
    assert (event.kind, event.booking_id, event.payment_intent_id, event.amount, event.payment_status) == (
        "checkout_completed", "b-1", "pi_1", 11_960_000, "paid")


def test_webhook_payment_failed_carries_decline_code():
    body, header = signed({"id": "evt_2", "type": "payment_intent.payment_failed", "data": {"object": {
        "id": "pi_1", "metadata": {"bookingId": "b-1"},
        "last_payment_error": {"code": "card_declined", "decline_code": "insufficient_funds"}}}})
    event = gateway().parse_webhook(body, header, now=NOW)
    assert (event.kind, event.decline_code, event.error_code) == ("payment_failed", "insufficient_funds", "card_declined")


@pytest.mark.parametrize("mutate", [
    lambda body, header: (body + b" ", header),                                  # body bị sửa
    lambda body, header: (body, header.replace("v1=", "v1=00")),                 # chữ ký sai
    lambda body, header: (body, None),                                           # thiếu header
    lambda body, header: (body, "garbage"),                                      # sai định dạng
])
def test_webhook_with_bad_signature_is_rejected(mutate):
    body, header = signed({"id": "evt_3", "type": "checkout.session.expired", "data": {"object": {"id": "cs"}}})
    with pytest.raises(InvalidWebhookSignature):
        gateway().parse_webhook(*mutate(body, header), now=NOW)


def test_webhook_older_than_five_minutes_is_rejected_and_other_secret_fails():
    body, header = signed({"id": "evt_4", "type": "checkout.session.expired", "data": {"object": {"id": "cs"}}},
                          timestamp=NOW - 301)
    with pytest.raises(InvalidWebhookSignature):
        gateway().parse_webhook(body, header, now=NOW)
    body, header = signed({"id": "evt_5", "type": "checkout.session.expired", "data": {"object": {"id": "cs"}}},
                          secret="whsec_other")
    with pytest.raises(InvalidWebhookSignature):
        gateway().parse_webhook(body, header, now=NOW)


def test_uninteresting_event_types_are_ignored():
    body, header = signed({"id": "evt_6", "type": "customer.created", "data": {"object": {"id": "cus_1"}}})
    assert gateway().parse_webhook(body, header, now=NOW) is None


def test_settings_refuse_live_keys():
    with pytest.raises(ValidationError):
        Settings(stripe_secret_key="sk_live_x")
    assert Settings(stripe_secret_key="sk_test_x").stripe_secret_key == "sk_test_x"
