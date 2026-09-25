"""Lỗi nghiệp vụ của booking. Tầng API dịch `code`, `http_status` và `details` sang Error Envelope."""
from __future__ import annotations


class BookingError(Exception):
    code = "INTERNAL_ERROR"
    http_status = 500
    retryable = False

    def __init__(self, message: str = "", details: dict | None = None):
        super().__init__(message or self.code)
        self._details = details

    @property
    def details(self) -> dict | None:
        return self._details


class CartEmpty(BookingError):
    code, http_status = "CART_EMPTY", 400


class ValidationFailed(BookingError):
    code, http_status = "VALIDATION_ERROR", 400


class ProductNotFound(BookingError):
    code, http_status = "PRODUCT_NOT_FOUND", 404


class CartItemNotFound(BookingError):
    code, http_status = "CART_ITEM_NOT_FOUND", 404


class BookingNotFound(BookingError):
    code, http_status = "BOOKING_NOT_FOUND", 404


class LineRejected(BookingError):
    """Một dòng giỏ vi phạm catalog: PRODUCT_UNAVAILABLE, PRICE_CHANGED hoặc DATE_OUT_OF_RANGE."""

    _STATUS = {"PRODUCT_UNAVAILABLE": 409, "PRICE_CHANGED": 409, "DATE_OUT_OF_RANGE": 422}

    def __init__(self, code: str, details: dict):
        super().__init__(code, details)
        self.code = code
        self.http_status = self._STATUS[code]


class PendingPaymentExists(BookingError):
    code, http_status = "BOOKING_PENDING_PAYMENT", 409


class BookingAlreadyPaid(BookingError):
    code, http_status = "BOOKING_ALREADY_PAID", 409


class BookingNotCancellable(BookingError):
    code, http_status = "BOOKING_NOT_CANCELLABLE", 409


class PaymentUnavailable(BookingError):
    code, http_status, retryable = "PAYMENT_PROVIDER_UNAVAILABLE", 503, True


class InvalidWebhook(BookingError):
    code, http_status = "INVALID_WEBHOOK_SIGNATURE", 400
