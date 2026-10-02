"""Giỏ hàng server-side (backend spec §7.1, FR-BKG-01; spec checkout-nhieu-buoc-hanh-khach.md §5.5).

Giỏ chỉ nhận tour, trải nghiệm và tiện ích khác; khách sạn và vé máy bay đặt trực tiếp qua đơn nháp. Chủ giỏ là người đã
đăng nhập (PostgreSQL) hoặc khách chưa đăng nhập (Redis, không sinh event CDP) — spec dat-truc-tiep-theo-don-nhap.md §3, §8.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Callable

from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.booking.errors import (
    CartItemNotFound, DirectBookingOnly, GuestStoreUnavailable, ProductNotFound, ValidationFailed,
)
from src.backend.app.application.booking.lines import resolve_line, stay_nights, vn_today
from src.backend.app.application.booking.owner import CartOwner, owner_of
from src.backend.app.application.booking.views import cart_response
from src.backend.app.application.ports.cart_repository import CartRepository
from src.backend.app.application.ports.product_catalog import ProductCatalog
from src.backend.app.application.tracking.behaviour import BehaviourTracker, CatalogProduct
from src.backend.app.domain.booking import GUEST_CART_MAX_ITEMS, is_cart_eligible
from src.backend.app.domain.booking.party import Guests

DIRECT_BOOKING_MESSAGE = "Khách sạn và vé máy bay được đặt trực tiếp, không thêm vào giỏ hàng."
CART_FULL_MESSAGE = f"Giỏ hàng chỉ chứa tối đa {GUEST_CART_MAX_ITEMS} mục. Vui lòng đăng nhập hoặc bỏ bớt mục."


def cart_full_error() -> ValidationFailed:
    error = ValidationFailed(CART_FULL_MESSAGE, {"fields": [
        {"field": "productId", "reason": "CART_FULL", "message": CART_FULL_MESSAGE}]})
    error.user_message = CART_FULL_MESSAGE
    return error


class CartService:
    def __init__(
        self, carts: CartRepository, catalog: ProductCatalog, tracker: BehaviourTracker,
        *, guest_carts: CartRepository | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._carts, self._guest_carts, self._catalog, self._tracker, self._clock = (
            carts, guest_carts, catalog, tracker, clock)

    def _repo(self, owner: CartOwner) -> CartRepository:
        if not owner.is_guest:
            return self._carts
        if self._guest_carts is None:
            raise GuestStoreUnavailable("kho giỏ của khách chưa được cấu hình")
        return self._guest_carts

    async def get(self, who: CartOwner | AuthPrincipal) -> dict:
        owner = owner_of(who)
        cart = await self._repo(owner).get(owner.key)
        products = await self._catalog.get_products([line.product_id for line in cart.lines])
        return cart_response(cart, products, cdp_user_id=owner.cdp_user_id)

    async def add(
        self, who: CartOwner | AuthPrincipal, *, product_id: str, using_date: date, quantity: int | None,
        nights: int | None, guests: Guests | None = None,
    ) -> dict:
        owner = owner_of(who)
        product = (await self._catalog.get_products([product_id])).get(product_id)
        if product is None:
            raise ProductNotFound("sản phẩm không tồn tại", {"productId": product_id})
        if not is_cart_eligible(product.taxonomy):
            error = DirectBookingOnly(
                "sản phẩm chỉ đặt trực tiếp", {"productId": product.product_id, "taxonomy": product.taxonomy})
            error.user_message = DIRECT_BOOKING_MESSAGE
            raise error
        carts = self._repo(owner)
        cart = await carts.get(owner.key)
        existing = next((l for l in cart.lines if l.product_id == product.product_id and l.using_date == using_date), None)
        if owner.is_guest and existing is None and len(cart.lines) >= GUEST_CART_MAX_ITEMS:
            raise cart_full_error()
        # Thêm trùng sản phẩm và ngày thì cộng dồn; luật sức chứa và số khách tối đa kiểm trên kết quả đã cộng (R-CRT-04).
        line = resolve_line(
            product, using_date=using_date, quantity=quantity, nights=nights, guests=guests,
            today=vn_today(self._clock()), existing_quantity=existing.quantity if existing else None,
            existing_guests=existing.guests if existing else None)
        await carts.upsert(
            owner.key, product_id=line.product_id, using_date=line.using_date, quantity=line.quantity,
            nights=line.nights, unit_price=line.unit_price, adults=line.adults, children=line.children,
            child_unit_price=line.child_unit_price,
        )
        # Chỉ ghi event sau khi ghi giỏ thành công; recorder không bao giờ chặn request. Khách chưa đăng nhập không có
        # danh tính CDP nên không sinh event (FR-CDP-02).
        if owner.cdp_user_id is not None:
            added = quantity if quantity is not None else (guests.total if guests else 1)
            self._tracker.track_add_to_cart(
                owner.cdp_user_id,
                CatalogProduct(product.product_id, product.taxonomy, float(product.unit_price)),
                added, using_date,
            )
        return await self.get(owner)

    async def update(
        self, who: CartOwner | AuthPrincipal, cart_item_id: str, *, using_date: date | None, quantity: int | None,
        nights: int | None, nights_given: bool, guests: Guests | None = None,
    ) -> dict:
        owner = owner_of(who)
        carts = self._repo(owner)
        cart = await carts.get(owner.key)
        line = next((l for l in cart.lines if l.cart_item_id == cart_item_id), None)
        if line is None:
            raise CartItemNotFound("mục giỏ không tồn tại", {"cartItemId": cart_item_id})
        product = (await self._catalog.get_products([line.product_id])).get(line.product_id)
        if product is None:
            raise ProductNotFound("sản phẩm không tồn tại", {"productId": line.product_id})
        resolved = resolve_line(
            product, using_date=using_date or line.using_date, quantity=quantity, nights=nights, guests=guests,
            today=vn_today(self._clock()), mode="update", existing_quantity=line.quantity, existing_guests=line.guests)
        # Sửa mục giỏ nghĩa là khách đã thấy giá hiện tại: ghi lại giá snapshot (người lớn và trẻ em) để checkout
        # không báo PRICE_CHANGED nữa.
        await carts.update(
            owner.key, cart_item_id, using_date=using_date, quantity=resolved.quantity,
            nights=stay_nights(product, nights) if nights_given else line.nights, nights_given=True,
            unit_price=resolved.unit_price, adults=resolved.adults, children=resolved.children,
            child_unit_price=resolved.child_unit_price,
        )
        return await self.get(owner)

    async def remove(self, who: CartOwner | AuthPrincipal, cart_item_id: str) -> dict:
        owner = owner_of(who)
        if not await self._repo(owner).remove(owner.key, cart_item_id):
            raise CartItemNotFound("mục giỏ không tồn tại", {"cartItemId": cart_item_id})
        return await self.get(owner)
