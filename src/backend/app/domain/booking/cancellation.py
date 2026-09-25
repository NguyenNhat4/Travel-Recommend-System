"""Chính sách huỷ và hoàn tiền (FR-BKG-07, Q5)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Iterable

from .models import Booking, BookingItem
from .status import BookingStatus, PaymentStatus

# Việt Nam không có giờ mùa hè; offset cố định tránh phụ thuộc gói tzdata.
VN_TZ = timezone(timedelta(hours=7))


class CancelDecision(str, Enum):
    EXPIRE_SESSION = "expire_session"      # chưa trả tiền: huỷ ngay, đóng phiên thanh toán
    REFUND_FULL = "refund_full"            # đã trả, còn hạn: hoàn 100%
    ALREADY_CANCELLED = "already_cancelled"  # huỷ lặp lại: trả kết quả cũ
    ALREADY_PAID = "already_paid"          # đã thu tiền nhưng đơn chưa xác nhận xong
    TOO_LATE = "too_late"
    NOT_ACTIVE = "not_active"              # đã thất bại hoặc hết hạn giữ chỗ


def cancellable_until(items: Iterable[BookingItem]) -> datetime:
    """00:00 giờ Việt Nam của ngày liền trước usingDate sớm nhất trong đơn, trả về UTC."""
    earliest: date = min(item.using_date for item in items)
    cutoff = datetime.combine(earliest - timedelta(days=1), time(0, 0), tzinfo=VN_TZ)
    return cutoff.astimezone(timezone.utc)


def decide_cancellation(booking: Booking, now: datetime) -> CancelDecision:
    status, payment = booking.status, booking.payment
    if status is BookingStatus.CANCELLED:
        return CancelDecision.ALREADY_CANCELLED
    if status is BookingStatus.PENDING_PAYMENT:
        if payment is not None and payment.status is PaymentStatus.SUCCEEDED:
            return CancelDecision.ALREADY_PAID
        return CancelDecision.EXPIRE_SESSION
    if status is BookingStatus.CONFIRMED:
        return CancelDecision.REFUND_FULL if now < cancellable_until(booking.items) else CancelDecision.TOO_LATE
    return CancelDecision.NOT_ACTIVE
