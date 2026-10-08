"""Nhóm đơn ở trang "Đơn hàng của tôi" (FR-BKG-14): Sắp đến, Hoàn thành, Đã huỷ.

Quy tắc nằm ở một chỗ này; bước lọc, đếm và phân trang của use case đều gọi `tab_of`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

from .cancellation import VN_TZ
from .models import BookingItem
from .status import BookingStatus


class BookingTab(str, Enum):
    UPCOMING = "upcoming"
    DONE = "done"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class BookingOverview:
    """Phần của một đơn đủ để xếp tab và lọc, không cần nạp dịch vụ và hành khách."""

    booking_id: str
    status: BookingStatus
    created_at: datetime
    hold_expires_at: datetime | None
    last_end_date: date                  # ngày kết thúc muộn nhất của mọi dịch vụ (trả phòng, ngày sử dụng cuối)
    taxonomies: tuple[str, ...]


def item_end_date(item: BookingItem) -> date:
    """Khách sạn kết thúc vào ngày trả phòng; dịch vụ khác kết thúc vào ngày sử dụng."""
    return item.using_date + timedelta(days=item.nights) if item.taxonomy == "hotel" and item.nights else item.using_date


def vn_today(now: datetime) -> date:
    return now.astimezone(VN_TZ).date()


def tab_of(overview: BookingOverview, now: datetime) -> BookingTab:
    status = overview.status
    if status is BookingStatus.PENDING_PAYMENT:
        held = overview.hold_expires_at is None or now < overview.hold_expires_at
        return BookingTab.UPCOMING if held else BookingTab.CANCELLED
    if status is BookingStatus.CONFIRMED:
        return BookingTab.UPCOMING if overview.last_end_date >= vn_today(now) else BookingTab.DONE
    return BookingTab.CANCELLED
