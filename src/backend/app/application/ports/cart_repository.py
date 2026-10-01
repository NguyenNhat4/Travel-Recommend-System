"""Port giỏ hàng phía server (app.carts, app.cart_items)."""
from __future__ import annotations

from datetime import date
from typing import Protocol

from src.backend.app.domain.booking import Cart


class CartRepository(Protocol):
    async def get(self, cdp_user_id: str) -> Cart: ...

    async def upsert(
        self, cdp_user_id: str, *, product_id: str, using_date: date, quantity: int, nights: int | None,
        unit_price: int, adults: int, children: int, child_unit_price: int | None,
    ) -> None:
        """Ghi mục giỏ theo giá trị TUYỆT ĐỐI; đã có cùng productId + usingDate thì ghi đè.

        Cộng dồn (backend spec §7.1 mục 6, R-CRT-04) do use case làm trước khi gọi, vì luật sức chứa và số khách tối đa
        phải kiểm trên kết quả đã cộng và không biểu diễn được trong SQL.
        """
        ...

    async def update(
        self, cdp_user_id: str, cart_item_id: str, *, using_date: date | None, quantity: int, nights: int | None,
        nights_given: bool, unit_price: int, adults: int, children: int, child_unit_price: int | None,
    ) -> bool:
        """False = không có mục này trong giỏ của user. Ghi lại giá snapshot bằng giá hiện tại (người lớn và trẻ em)."""
        ...

    async def remove(self, cdp_user_id: str, cart_item_id: str) -> bool: ...
