"""Port giỏ hàng phía server (app.carts, app.cart_items)."""
from __future__ import annotations

from datetime import date
from typing import Protocol

from src.backend.app.domain.booking import Cart


class CartRepository(Protocol):
    async def get(self, cdp_user_id: str) -> Cart: ...

    async def add(
        self, cdp_user_id: str, *, product_id: str, using_date: date, quantity: int, nights: int | None,
        unit_price: int,
    ) -> None:
        """Thêm mục; cùng productId + usingDate thì cộng dồn quantity (backend spec §7.1 mục 6)."""
        ...

    async def update(
        self, cdp_user_id: str, cart_item_id: str, *, using_date: date | None, quantity: int | None,
        nights: int | None, nights_given: bool, unit_price: int,
    ) -> bool:
        """False = không có mục này trong giỏ của user. Ghi lại giá snapshot bằng giá hiện tại."""
        ...

    async def remove(self, cdp_user_id: str, cart_item_id: str) -> bool: ...
