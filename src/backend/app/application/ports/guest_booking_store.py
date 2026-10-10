"""Port đọc và xoá toàn bộ dữ liệu đặt chỗ của một khách chưa đăng nhập, dùng khi gộp vào tài khoản (spec §8.3)."""
from __future__ import annotations

from typing import Protocol

from src.backend.app.domain.booking import BookingDraft, Cart


class GuestBookingStore(Protocol):
    async def export(self, guest_id: str) -> tuple[Cart, list[BookingDraft]]:
        """Giỏ và mọi đơn nháp (kể cả đã hết hạn) của khách. Không có gì thì trả giỏ rỗng và danh sách rỗng."""
        ...

    async def purge(self, guest_id: str) -> None:
        """Xoá giỏ, đơn nháp và chỉ mục của khách (R-MRG-03)."""
        ...
