"""Port đơn nháp của "Đặt ngay" (spec dat-truc-tiep-theo-don-nhap.md §4).

Hai adapter như giỏ hàng: PostgreSQL (app.booking_drafts, app.booking_draft_items) cho người đã đăng nhập, Redis cho khách
chưa đăng nhập. `owner_key` là `cdp_user_id` hoặc `guestId`.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, Sequence

from src.backend.app.domain.booking import BookingDraft, CartLine


class BookingDraftRepository(Protocol):
    async def create(
        self, draft: BookingDraft, *, copy_to_cart: Sequence[CartLine], now: datetime, max_live: int,
    ) -> None:
        """Ghi đơn nháp và, trong cùng thao tác ghi, chép `copy_to_cart` vào giỏ của `draft.owner_key`.

        Mục giỏ đã có cùng sản phẩm và ngày thì giữ nguyên, không cộng dồn, không ghi đè (R-CPY-01, R-CPY-02). Đồng thời
        dọn đơn nháp đã hết hạn của chủ giỏ và giữ lại tối đa `max_live` đơn nháp còn hạn, bỏ cái cũ nhất (R-DRF-07).
        """
        ...

    async def get(self, owner_key: str, draft_id: str) -> BookingDraft | None:
        """None khi không có hoặc không thuộc `owner_key`. Đơn nháp đã hết hạn vẫn được trả để báo 410."""
        ...

    async def update_item(
        self, owner_key: str, draft_id: str, cart_item_id: str, *, using_date: date | None, quantity: int,
        nights: int | None, unit_price: int, adults: int, children: int, child_unit_price: int | None,
    ) -> bool:
        """False = không có mục này trong đơn nháp của chủ giỏ. Ghi lại giá snapshot bằng giá hiện tại."""
        ...

    async def remove_item(self, owner_key: str, draft_id: str, cart_item_id: str) -> bool:
        """False = không có mục này trong đơn nháp của chủ giỏ. Bỏ mục cuối cùng thì xoá luôn đơn nháp (R-DRF-14)."""
        ...

    async def adopt(self, draft: BookingDraft) -> bool:
        """Nhận một đơn nháp có sẵn mã (gộp từ khách chưa đăng nhập, R-MRG-02). False = mã đã tồn tại, không ghi gì."""
        ...
