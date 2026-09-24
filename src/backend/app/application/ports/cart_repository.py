"""Port giỏ hàng phía server, một giỏ đang mở cho mỗi khách (`app.carts`, `app.cart_items`; backend §7.1)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class CartLine:
    cart_item_id: str
    product_id: str
    quantity: int
    using_date: date
    using_date_to: date | None      # ngày trả phòng (hotel); None với vé, chuyến bay
    unit_price_snapshot: float      # giá lúc thêm; checkout so lại với catalog
    added_at: datetime


@dataclass(frozen=True)
class Cart:
    cart_id: str
    cdp_user_id: str
    updated_at: datetime
    lines: tuple[CartLine, ...]


class CartRepository(Protocol):
    async def load(self, cdp_user_id: str) -> Cart:
        """Giỏ đang mở của khách; chưa có thì tạo giỏ rỗng."""
        ...

    async def add(self, cdp_user_id: str, product_id: str, using_date: date, using_date_to: date | None,
                  quantity: int, unit_price: float) -> None:
        """Thêm mục; trùng (productId, usingDate) thì cộng dồn quantity (backend §7.1 cam kết 6)."""
        ...

    async def update(self, cdp_user_id: str, cart_item_id: str, using_date: date, using_date_to: date | None,
                     quantity: int) -> bool:
        """False khi mục không thuộc giỏ của khách."""
        ...

    async def remove(self, cdp_user_id: str, cart_item_id: str) -> bool:
        """False khi mục không thuộc giỏ của khách."""
        ...
