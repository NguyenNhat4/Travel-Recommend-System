"""Đổi mã lỗi thẻ của Stripe sang failureReason của contract (spec booking §10.2)."""
from __future__ import annotations

# Số lần thẻ bị từ chối tối đa trong một đơn (Q4); chặn card testing.
MAX_FAILED_ATTEMPTS = 3

_BY_CODE = {
    "insufficient_funds": "INSUFFICIENT_FUNDS",
    "expired_card": "EXPIRED_CARD",
    "incorrect_cvc": "INCORRECT_CVC",
    "invalid_cvc": "INCORRECT_CVC",
    "authentication_required": "AUTHENTICATION_FAILED",
    "payment_intent_authentication_failure": "AUTHENTICATION_FAILED",
    "processing_error": "PROCESSING_ERROR",
    "try_again_later": "PROCESSING_ERROR",
}


def failure_reason_from_stripe(decline_code: str | None, error_code: str | None = None) -> str:
    for code in (decline_code, error_code):
        if code and code in _BY_CODE:
            return _BY_CODE[code]
    return "CARD_DECLINED"
