"""Lỗi nghiệp vụ của booking. Tầng API dịch `code`, `http_status` và `details` sang Error Envelope."""
from __future__ import annotations


class BookingError(Exception):
    code = "INTERNAL_ERROR"
    http_status = 500
    retryable = False
    # Thông điệp tiếng Việt riêng cho người dùng; None thì tầng API dùng câu mặc định theo mã lỗi.
    user_message: str | None = None

    def __init__(self, message: str = "", details: dict | None = None):
        super().__init__(message or self.code)
        self._details = details

    @property
    def details(self) -> dict | None:
        return self._details


class CartEmpty(BookingError):
    code, http_status = "CART_EMPTY", 400


class ValidationFailed(BookingError):
    """Vi phạm luật dữ liệu. `details.fields[]` có `{field, reason, message}` cho mọi vi phạm (spec checkout §7.5)."""

    code, http_status = "VALIDATION_ERROR", 400


class ProductNotFound(BookingError):
    code, http_status = "PRODUCT_NOT_FOUND", 404


class CartItemNotFound(BookingError):
    code, http_status = "CART_ITEM_NOT_FOUND", 404


class BookingNotFound(BookingError):
    code, http_status = "BOOKING_NOT_FOUND", 404


class DirectBookingOnly(BookingError):
    """Khách sạn và vé máy bay không thêm được vào giỏ, chỉ đặt trực tiếp qua đơn nháp (R-DIR-01)."""

    code, http_status = "DIRECT_BOOKING_ONLY", 422


class BookingDraftNotFound(BookingError):
    """Không có đơn nháp này, hoặc đơn nháp của chủ giỏ khác: không phân biệt hai trường hợp (R-DRF-11)."""

    code, http_status = "BOOKING_DRAFT_NOT_FOUND", 404


class BookingDraftExpired(BookingError):
    code, http_status = "BOOKING_DRAFT_EXPIRED", 410


class GuestStoreUnavailable(BookingError):
    """Kho giỏ và đơn nháp của khách chưa đăng nhập (Redis) không phản hồi."""

    code, http_status, retryable = "INTERNAL_ERROR", 503, True


class LineRejected(BookingError):
    """Một dòng giỏ vi phạm catalog: PRODUCT_UNAVAILABLE, PRICE_CHANGED hoặc DATE_OUT_OF_RANGE."""

    _STATUS = {"PRODUCT_UNAVAILABLE": 409, "PRICE_CHANGED": 409, "DATE_OUT_OF_RANGE": 422}

    def __init__(self, code: str, details: dict | None):
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
