"""Trạng thái đơn và thanh toán (docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md §5).

Giá trị viết thường vì đó là giá trị trong database; API trả bản viết HOA.
"""
from __future__ import annotations

from enum import Enum


class BookingStatus(str, Enum):
    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    PAYMENT_FAILED = "payment_failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    OPEN = "open"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"
    REFUND_FAILED = "refund_failed"


class InvalidTransition(Exception):
    """Chuyển trạng thái không nằm trong máy trạng thái; caller coi là lỗi lập trình hoặc dữ liệu."""


REFUND_STATES = (PaymentStatus.REFUND_PENDING, PaymentStatus.REFUNDED, PaymentStatus.REFUND_FAILED)
