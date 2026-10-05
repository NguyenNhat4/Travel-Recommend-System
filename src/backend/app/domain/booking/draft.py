"""Đặt trực tiếp qua đơn nháp (FR-BKG-01; docs/spec/booking/dat-truc-tiep-theo-don-nhap.md §3, §4)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import CartLine

# Khách sạn và vé máy bay không vào giỏ: giá và chỗ trống đổi liên tục nên chỉ đặt trực tiếp (R-DIR-01).
DIRECT_BOOKING_TAXONOMIES = frozenset({"hotel", "flight"})

MAX_DRAFT_ITEMS = 20       # một lần Đặt ngay (một lịch trình) có tối đa 20 mục
MAX_LIVE_DRAFTS = 5        # mỗi chủ giỏ có tối đa 5 đơn nháp còn hạn (R-DRF-07)
GUEST_CART_MAX_ITEMS = 20  # giỏ của khách chưa đăng nhập (R-GST-10)


def is_cart_eligible(taxonomy: str) -> bool:
    """Chỉ tour, trải nghiệm và tiện ích khác (attraction, golf, combo) thêm được vào giỏ."""
    return taxonomy not in DIRECT_BOOKING_TAXONOMIES


@dataclass(frozen=True)
class DraftPolicy:
    """Hiệu lực của một đơn nháp: tính từ lúc tạo, không gia hạn (R-DRF-05)."""

    ttl_minutes: int = 30

    def __post_init__(self) -> None:
        if self.ttl_minutes < 1:
            raise ValueError("thời gian hiệu lực của đơn nháp phải từ 1 phút")

    def expires_at(self, now: datetime) -> datetime:
        return now + timedelta(minutes=self.ttl_minutes)


@dataclass(frozen=True)
class BookingDraft:
    """Các mục của một lần Đặt ngay. Không giữ chỗ, không trừ tồn kho; thành phần cố định từ lúc tạo."""

    draft_id: str
    owner_key: str  # cdp_user_id của người đã đăng nhập, hoặc guestId của khách chưa đăng nhập
    lines: list[CartLine]
    created_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at
