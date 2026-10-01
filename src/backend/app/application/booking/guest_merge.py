"""Gộp giỏ và đơn nháp của khách chưa đăng nhập vào tài khoản vừa đăng nhập (spec dat-truc-tiep-theo-don-nhap.md §8.3)."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Callable

from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.booking.errors import ValidationFailed
from src.backend.app.application.booking.owner import GUEST_ID_PATTERN
from src.backend.app.application.ports.booking_draft_repository import BookingDraftRepository
from src.backend.app.application.ports.cart_repository import CartRepository
from src.backend.app.application.ports.guest_booking_store import GuestBookingStore
from src.backend.app.application.ports.product_catalog import ProductCatalog
from src.backend.app.application.tracking.behaviour import BehaviourTracker, CatalogProduct
from src.backend.app.core.request_context import current_request_id
from src.backend.app.domain.booking import BookingDraft, CartLine, is_cart_eligible

logger = logging.getLogger(__name__)


class MergeGuestBooking:
    def __init__(
        self, guests: GuestBookingStore, carts: CartRepository, drafts: BookingDraftRepository, catalog: ProductCatalog,
        tracker: BehaviourTracker, *, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._guests, self._carts, self._drafts, self._catalog, self._tracker, self._clock = (
            guests, carts, drafts, catalog, tracker, clock)

    async def __call__(self, principal: AuthPrincipal, guest_id: str) -> dict:
        if not GUEST_ID_PATTERN.match(guest_id or ""):
            message = "Mã khách không hợp lệ."
            raise ValidationFailed(message, {"fields": [{"field": "guestId", "reason": "INVALID", "message": message}]})
        user = principal.cdp_user_id
        guest_cart, guest_drafts = await self._guests.export(guest_id)
        now = self._clock()
        live = [draft for draft in guest_drafts if not draft.is_expired(now)]
        lines = [*guest_cart.lines, *(line for draft in live for line in draft.lines)]
        products = await self._catalog.get_products(list({line.product_id for line in lines}))

        # Giỏ: mục tài khoản chưa có thì thêm; trùng sản phẩm và ngày thì chỉ giữ mục đang có trong tài khoản (R-MRG-01).
        existing = {(l.product_id, l.using_date) for l in (await self._carts.get(user)).lines}
        entered: dict[tuple[str, date], CartLine] = {}  # mỗi cặp (sản phẩm, ngày) thực sự vào tài khoản: ghi một event
        merged_items = skipped = 0
        for line in guest_cart.lines:
            key = (line.product_id, line.using_date)
            product = products.get(line.product_id)
            if product is None or not is_cart_eligible(product.taxonomy):
                continue  # sản phẩm không còn trong catalog, hoặc dữ liệu cũ trái luật giỏ: bỏ, không làm lỗi (R-MRG-06)
            if key in existing:
                skipped += 1
                continue
            await self._carts.upsert(
                user, product_id=line.product_id, using_date=line.using_date, quantity=line.quantity, nights=line.nights,
                unit_price=line.unit_price_snapshot, adults=line.adults, children=line.children,
                child_unit_price=line.child_unit_price_snapshot)
            existing.add(key)
            entered[key] = line
            merged_items += 1

        # Đơn nháp còn hạn: chuyển sang tài khoản với cùng mã và cùng hạn để trang thanh toán đang mở dùng tiếp (R-MRG-02).
        merged_drafts = 0
        for draft in live:
            usable = [line for line in draft.lines if line.product_id in products]
            if not usable:
                continue
            adopted = await self._drafts.adopt(BookingDraft(draft.draft_id, user, usable, draft.created_at, draft.expires_at))
            if adopted:
                merged_drafts += 1
                for line in usable:
                    entered.setdefault((line.product_id, line.using_date), line)

        await self._guests.purge(guest_id)
        for (product_id, using_date), line in entered.items():
            product = products[product_id]
            self._tracker.track_add_to_cart(
                user, CatalogProduct(product.product_id, product.taxonomy, float(product.unit_price)),
                line.quantity, using_date)
        logger.info("booking.guest_merge cartItems=%d duplicates=%d drafts=%d guest=%s requestId=%s",
                    merged_items, skipped, merged_drafts, guest_id[:8], current_request_id())
        return {"mergedCartItems": merged_items, "skippedDuplicates": skipped, "mergedDrafts": merged_drafts}
