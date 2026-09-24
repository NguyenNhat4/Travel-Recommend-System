"""Giỏ hàng phía server (backend §7.1). Mọi thao tác trả toàn bộ `CartResponse`, không trả delta."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from src.backend.app.application.ports.cart_repository import Cart, CartRepository
from src.backend.app.application.ports.product_catalog import ProductCatalog
from src.backend.app.application.tracking.behaviour import BehaviourTracker, CatalogProduct
from src.backend.app.domain.booking import (
    CartItemNotFound,
    ProductNotFound,
    bookable_product,
    ensure_open,
    stay_nights,
)

from .views import cart_view, stay_length


def check_out(using_date: date, nights: int | None) -> date | None:
    return using_date + timedelta(days=nights) if nights else None


@dataclass
class CartService:
    carts: CartRepository
    catalog: ProductCatalog
    tracker: BehaviourTracker | None = None

    async def get(self, cdp_user_id: str) -> dict:
        return await self._view(await self.carts.load(cdp_user_id))

    async def add(self, cdp_user_id: str, product_id: str, using_date: date, quantity: int,
                  nights: int | None = None) -> dict:
        product = bookable_product(await self.catalog.get(product_id), product_id)
        nights = stay_nights(product, nights)
        ensure_open(product, using_date, nights)
        await self.carts.add(cdp_user_id, product.product_id, using_date, check_out(using_date, nights),
                             quantity, product.unit_price)
        if self.tracker is not None:  # chỉ ghi sau khi thêm thành công; CDP lỗi không ảnh hưởng response
            self.tracker.track_add_to_cart(
                cdp_user_id, CatalogProduct(product.product_id, product.taxonomy, product.unit_price),
                quantity, using_date)
        return await self.get(cdp_user_id)

    async def update(self, cdp_user_id: str, cart_item_id: str, *, using_date: date | None = None,
                     quantity: int | None = None, nights: int | None = None) -> dict:
        cart = await self.carts.load(cdp_user_id)
        line = next((item for item in cart.lines if item.cart_item_id == cart_item_id), None)
        if line is None:
            raise CartItemNotFound(cart_item_id)
        product = await self.catalog.get(line.product_id)
        if product is None:
            raise ProductNotFound(line.product_id)
        current_nights = stay_length(product.taxonomy, line.using_date, line.using_date_to)
        new_date = using_date or line.using_date
        new_nights = stay_nights(product, nights if nights is not None else current_nights)
        new_quantity = quantity or line.quantity
        if new_date != line.using_date or new_nights != current_nights:
            bookable_product(product, product.product_id)
            ensure_open(product, new_date, new_nights)
        twin = next((item for item in cart.lines if item.cart_item_id != line.cart_item_id
                     and item.product_id == line.product_id and item.using_date == new_date), None)
        if twin is not None:  # trùng (productId, usingDate) với mục khác: gộp như khi thêm
            await self.carts.update(cdp_user_id, twin.cart_item_id, twin.using_date, twin.using_date_to,
                                    twin.quantity + new_quantity)
            await self.carts.remove(cdp_user_id, line.cart_item_id)
        else:
            await self.carts.update(cdp_user_id, line.cart_item_id, new_date, check_out(new_date, new_nights),
                                    new_quantity)
        return await self.get(cdp_user_id)

    async def remove(self, cdp_user_id: str, cart_item_id: str) -> dict:
        if not await self.carts.remove(cdp_user_id, cart_item_id):
            raise CartItemNotFound(cart_item_id)
        return await self.get(cdp_user_id)

    async def _view(self, cart: Cart) -> dict:
        products = await self.catalog.get_many([line.product_id for line in cart.lines]) if cart.lines else {}
        return cart_view(cart, products)
