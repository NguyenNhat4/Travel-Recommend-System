"""Webhook Stripe: gọi thẳng FastAPI, không qua BFF, xác thực bằng chữ ký Stripe-Signature (không dùng JWT)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import JSONResponse

from src.backend.app.api.deps import get_use_case
from src.backend.app.application.booking.errors import InvalidWebhook
from src.backend.app.application.ports.payment_gateway import InvalidWebhookSignature
from src.backend.app.core.request_context import current_request_id

router = APIRouter(tags=["payments-internal"])
logger = logging.getLogger(__name__)


@router.post("/payments/stripe/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request, stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    handler=Depends(get_use_case("payment_event_handler")),
):
    # Raw body TRƯỚC mọi parse JSON: chữ ký tính trên đúng dãy byte Stripe gửi.
    raw = await request.body()
    gateway = request.app.state.payment_gateway
    try:
        event = gateway.parse_webhook(raw, stripe_signature)
    except InvalidWebhookSignature as exc:
        client = request.client.host if request.client else "unknown"
        logger.warning("payment.webhook.bad_signature requestId=%s ip=%s", current_request_id(), client)
        raise InvalidWebhook("chữ ký không hợp lệ") from exc
    if event is not None:
        try:
            await handler(event)
        except Exception:
            # 500 để Stripe gửi lại (CDP hoặc DB lỗi tạm thời); không trả chi tiết lỗi cho Stripe.
            logger.exception("payment.webhook.failed eventId=%s kind=%s requestId=%s",
                             event.event_id, event.kind, current_request_id())
            return JSONResponse(status_code=500, content={"error": "internal"})
    return Response(status_code=status.HTTP_200_OK)
