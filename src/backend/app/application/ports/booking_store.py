"""Port lưu đơn đặt chỗ và thanh toán (app.bookings, booking_items, payments)."""
from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import date, datetime
from typing import Protocol, Sequence

from src.backend.app.domain.booking import Booking


class PendingBookingExists(Exception):
    """Người dùng đã có đơn giữ chỗ khác (unique index bookings_one_pending_per_user)."""


class ReferenceCodeTaken(Exception):
    """Trùng mã đặt chỗ hiển thị; caller sinh mã mới rồi thử lại."""


class BookingTx(Protocol):
    """Một transaction: commit khi thoát khối `async with` bình thường, rollback khi có exception.

    `lock=True` khoá dòng đơn (FOR UPDATE) cho tới hết transaction.
    """

    async def get_by_id(self, booking_id: str, *, lock: bool = False) -> Booking | None: ...
    async def get_by_reference(self, reference_code: str, cdp_user_id: str, *, lock: bool = False) -> Booking | None: ...
    async def get_by_session(self, session_id: str, *, lock: bool = False) -> Booking | None: ...
    async def get_pending_for_user(self, cdp_user_id: str, *, lock: bool = False) -> Booking | None: ...
    async def insert(self, booking: Booking) -> None: ...
    async def save(self, booking: Booking) -> None: ...
    async def clear_cart_items(self, cdp_user_id: str, keys: Sequence[tuple[str, date]]) -> None:
        """Xoá các mục giỏ đã đặt, khoá theo (productId, usingDate)."""
        ...

    async def find_reconcile_ids(self, now: datetime, limit: int) -> list[str]:
        """Đơn cần đối soát (spec booking §8.2); khoá SKIP LOCKED để hai tiến trình không dẫm nhau."""
        ...


class BookingStore(Protocol):
    def transaction(self) -> AbstractAsyncContextManager[BookingTx]: ...
