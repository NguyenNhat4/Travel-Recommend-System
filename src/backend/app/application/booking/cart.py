"""Giỏ hàng server-side (backend spec §7.1, FR-BKG-01; spec checkout-nhieu-buoc-hanh-khach.md §5.5)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Callable

from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.booking.errors import CartItemNotFound, LineRejected, ProductNotFound
from src.backend.app.application.booking.messages import CART_MESSAGE, validation_failed
from src.backend.app.application.booking.views import cart_response
from src.backend.app.application.ports.cart_repository import CartRepository
from src.backend.app.application.ports.product_catalog import ProductCatalog
from src.backend.app.application.tracking.behaviour import BehaviourTracker, CatalogProduct
from src.backend.app.domain.booking import check_product, child_unit_price
from src.backend.app.domain.booking.party import Guests
from src.backend.app.domain.booking.party_rules import resolve_cart_guests
from src.backend.app.domain.catalog.models import Product


def _stay(product: Product, nights: int | None) -> int | None:
    """Chỉ khách sạn có số đêm; loại khác bỏ qua kể cả khi client gửi."""
    return max(1, nights or 1) if product.taxonomy == "hotel" else None


def _child_snapshot(product: Product) -> int | None:
    """Giá vé trẻ em hợp lệ hiện tại; None nghĩa là trẻ em trả giá người lớn (spec §4.4)."""
    return child_unit_price(product.taxonomy, int(product.unit_price), product.attributes)


class CartService:
    def __init__(
        self, carts: CartRepository, catalog: ProductCatalog, tracker: BehaviourTracker,
        *, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._carts, self._catalog, self._tracker, self._clock = carts, catalog, tracker, clock

    async def get(self, principal: AuthPrincipal) -> dict:
        cart = await self._carts.get(principal.cdp_user_id)
        products = await self._catalog.get_products([line.product_id for line in cart.lines])
        return cart_response(cart, products)

    async def add(
        self, principal: AuthPrincipal, *, product_id: str, using_date: date, quantity: int | None, nights: int | None,
        guests: Guests | None = None,
    ) -> dict:
        product = (await self._catalog.get_products([product_id])).get(product_id)
        if product is None:
            raise ProductNotFound("sản phẩm không tồn tại", {"productId": product_id})
        issue = check_product(product, using_date)
        if issue:
            raise LineRejected(issue.code, issue.details)
        cart = await self._carts.get(principal.cdp_user_id)
        existing = next((l for l in cart.lines if l.product_id == product.product_id and l.using_date == using_date), None)
        result = resolve_cart_guests(
            product.taxonomy, mode="add", request_quantity=quantity, request_guests=guests,
            existing_quantity=existing.quantity if existing else None,
            existing_guests=existing.guests if existing else None, max_occupancy=product.max_occupancy)
        if result.violations:
            raise validation_failed(result.violations, user_message=CART_MESSAGE)
        await self._carts.upsert(
            principal.cdp_user_id, product_id=product.product_id, using_date=using_date, quantity=result.quantity,
            nights=_stay(product, nights), unit_price=int(product.unit_price), adults=result.guests.adults,
            children=result.guests.children, child_unit_price=_child_snapshot(product),
        )
        # Chỉ ghi event sau khi ghi giỏ thành công; recorder không bao giờ chặn request.
        added = quantity if quantity is not None else (guests.total if guests else 1)
        self._tracker.track_add_to_cart(
            principal.cdp_user_id,
            CatalogProduct(product.product_id, product.taxonomy, float(product.unit_price)),
            added, using_date,
        )
        return await self.get(principal)

    async def update(
        self, principal: AuthPrincipal, cart_item_id: str, *, using_date: date | None, quantity: int | None,
        nights: int | None, nights_given: bool, guests: Guests | None = None,
    ) -> dict:
        cart = await self._carts.get(principal.cdp_user_id)
        line = next((l for l in cart.lines if l.cart_item_id == cart_item_id), None)
        if line is None:
            raise CartItemNotFound("mục giỏ không tồn tại", {"cartItemId": cart_item_id})
        product = (await self._catalog.get_products([line.product_id])).get(line.product_id)
        if product is None:
            raise ProductNotFound("sản phẩm không tồn tại", {"productId": line.product_id})
        new_date = using_date or line.using_date
        issue = check_product(product, new_date)
        if issue:
            raise LineRejected(issue.code, issue.details)
        result = resolve_cart_guests(
            product.taxonomy, mode="update", request_quantity=quantity, request_guests=guests,
            existing_quantity=line.quantity, existing_guests=line.guests, max_occupancy=product.max_occupancy)
        if result.violations:
            raise validation_failed(result.violations, user_message=CART_MESSAGE)
        # Sửa mục giỏ nghĩa là khách đã thấy giá hiện tại: ghi lại giá snapshot (người lớn và trẻ em) để checkout
        # không báo PRICE_CHANGED nữa.
        await self._carts.update(
            principal.cdp_user_id, cart_item_id, using_date=using_date, quantity=result.quantity,
            nights=_stay(product, nights) if nights_given else line.nights, nights_given=True,
            unit_price=int(product.unit_price), adults=result.guests.adults, children=result.guests.children,
            child_unit_price=_child_snapshot(product),
        )
        return await self.get(principal)

    async def remove(self, principal: AuthPrincipal, cart_item_id: str) -> dict:
        if not await self._carts.remove(principal.cdp_user_id, cart_item_id):
            raise CartItemNotFound("mục giỏ không tồn tại", {"cartItemId": cart_item_id})
        return await self.get(principal)
