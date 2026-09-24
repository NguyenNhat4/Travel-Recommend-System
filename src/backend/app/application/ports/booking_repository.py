"""Port lưu đơn đặt chỗ demo (`app.bookings`, `app.booking_items`; backend §7.2–7.3).

CDP không có bảng booking: với CDP một lần đặt chỉ là các event `purchase` cùng `event_group_id`.
Bảng này giữ phần CDP không giữ (mã tham chiếu, liên hệ, snapshot dòng hàng) để Web hiển thị.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class BookingLine:
    booking_item_id: str
    product_id: str
    taxonomy: str
    product_name: str
    unit_price: float
    quantity: int
    using_date: date
    using_date_to: date | None
    guest_names: tuple[str, ...]


@dataclass(frozen=True)
class Booking:
    reference_code: str
    cdp_user_id: str
    event_group_id: str
    contact_name: str
    contact_email: str
    contact_phone: str
    special_request: str | None     # DDL chỉ có một cột cho cả đơn
    total_amount: int
    currency: str
    created_at: datetime
    lines: tuple[BookingLine, ...]


class BookingRepository(Protocol):
    async def reference_taken(self, reference_code: str) -> bool:
        ...

    async def save(self, booking: Booking) -> None:
        """Ghi booking và các dòng, rồi xoá giỏ của khách, trong CÙNG một transaction (cdp §5 bước 4)."""
        ...

    async def find(self, reference_code: str, cdp_user_id: str) -> Booking | None:
        """Chỉ chủ đơn đọc được; đơn của người khác trả None như không tồn tại (backend §7.3)."""
        ...
