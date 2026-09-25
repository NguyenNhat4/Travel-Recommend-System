"""Tạo đơn giữ chỗ và phiên thanh toán Stripe (spec booking §6.2, FR-BKG-02, FR-BKG-05, FR-BKG-06)."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.booking.errors import (
    CartEmpty,
    LineRejected,
    PaymentUnavailable,
    PendingPaymentExists,
    ProductNotFound,
    ValidationFailed,
)
from src.backend.app.application.booking.reconcile import ReconcileBookings
from src.backend.app.application.booking.views import booking_response, iso
from src.backend.app.application.ports.booking_store import BookingStore, PendingBookingExists, ReferenceCodeTaken
from src.backend.app.application.ports.cart_repository import CartRepository
from src.backend.app.application.ports.payment_gateway import (
    CheckoutLine,
    PaymentGateway,
    PaymentProviderError,
    PaymentProviderUnavailable,
)
from src.backend.app.application.ports.product_catalog import ProductCatalog
from src.backend.app.core.request_context import current_request_id
from src.backend.app.domain.booking import (
    Booking,
    BookingItem,
    HoldPolicy,
    Payment,
    check_product,
    new_reference_code,
)
from src.backend.app.domain.booking.status import BookingStatus

logger = logging.getLogger(__name__)
_REFERENCE_RETRIES = 5


@dataclass(frozen=True)
class ItemDetail:
    cart_item_id: str
    guest_names: list[str] = field(default_factory=list)
    special_request: str | None = None


@dataclass(frozen=True)
class Contact:
    full_name: str
    email: str
    phone: str


def _unit_amount(item: BookingItem) -> int:
    """Số tiền một đơn vị gửi sang Stripe: khách sạn nhân số đêm để tổng dòng khớp lineTotal."""
    return item.unit_price * (max(1, item.nights or 1) if item.taxonomy == "hotel" else 1)


class CreateBookingHold:
    def __init__(
        self, store: BookingStore, carts: CartRepository, catalog: ProductCatalog, gateway: PaymentGateway,
        reconciler: ReconcileBookings, hold: HoldPolicy, *, public_web_url: str, provider: str,
        clock: Callable[[], datetime],
    ):
        self._store, self._carts, self._catalog, self._gateway = store, carts, catalog, gateway
        self._reconciler, self._hold, self._web, self._provider, self._clock = (
            reconciler, hold, public_web_url.rstrip("/"), provider, clock)

    async def __call__(self, principal: AuthPrincipal, contact: Contact, details: list[ItemDetail]) -> dict:
        user = principal.cdp_user_id
        await self._release_stale_hold(user)

        cart = await self._carts.get(user)
        if not cart.lines:
            raise CartEmpty("giỏ hàng trống")
        lines_by_id = {line.cart_item_id: line for line in cart.lines}
        unknown = [d.cart_item_id for d in details if d.cart_item_id not in lines_by_id]
        if unknown:
            raise ValidationFailed("cartItemId không thuộc giỏ", {"fields": [{"field": "itemDetails", "cartItemIds": unknown}]})
        detail_by_id = {d.cart_item_id: d for d in details}

        products = await self._catalog.get_products([line.product_id for line in cart.lines])
        items: list[BookingItem] = []
        for line in cart.lines:
            product = products.get(line.product_id)
            if product is None:
                raise ProductNotFound("sản phẩm không tồn tại", {"productId": line.product_id})
            issue = check_product(product, line.using_date, snapshot_price=line.unit_price_snapshot)
            if issue:
                raise LineRejected(issue.code, issue.details)
            detail = detail_by_id.get(line.cart_item_id)
            items.append(BookingItem(
                booking_item_id=str(uuid.uuid4()), product_id=product.product_id, taxonomy=product.taxonomy,
                product_name=product.name, unit_price=int(product.unit_price), quantity=line.quantity,
                using_date=line.using_date, nights=line.nights if product.taxonomy == "hotel" else None,
                guest_names=list(detail.guest_names) if detail else [],
                special_request=detail.special_request if detail else None,
            ))

        now = self._clock()
        booking_id = str(uuid.uuid4())
        booking = Booking(
            booking_id=booking_id, reference_code=new_reference_code(now.date()), cdp_user_id=user,
            event_group_id=f"OFF{now:%Y%m%d}{uuid.uuid4().hex[:6].upper()}", contact_name=contact.full_name,
            contact_email=contact.email, contact_phone=contact.phone, created_at=now, items=items,
            hold_expires_at=self._hold.expires_at(now),
        )
        booking.payment = Payment(payment_id=str(uuid.uuid4()), provider=self._provider, amount=booking.total_amount)

        # Gọi Stripe TRƯỚC khi ghi database: Stripe lỗi thì chưa có gì để dọn (spec booking §6.1).
        try:
            session = await self._gateway.create_checkout_session(
                booking_id=booking_id, reference_code=booking.reference_code, cdp_user_id=user,
                customer_email=contact.email,
                lines=[CheckoutLine(name=item.product_name, unit_amount=_unit_amount(item), quantity=item.quantity)
                       for item in items],
                expires_at=booking.hold_expires_at,
                success_url=f"{self._web}/booking/{booking.reference_code}?payment=return",
                cancel_url=f"{self._web}/booking/{booking.reference_code}?payment=cancelled",
                idempotency_key=f"booking:{booking_id}",
            )
        except PaymentProviderUnavailable as exc:
            logger.warning("booking.create.provider_unavailable requestId=%s", current_request_id())
            raise PaymentUnavailable("cổng thanh toán không phản hồi") from exc
        except PaymentProviderError:
            logger.exception("booking.create.provider_rejected requestId=%s", current_request_id())
            raise
        payment = booking.payment
        payment.checkout_session_id, payment.checkout_url = session.session_id, session.url

        try:
            await self._insert(booking)
        except PendingBookingExists:
            await self._close_session(session.session_id)
            raise await self._pending_error(user)
        except BaseException:
            # Commit lỗi sau khi Stripe đã tạo phiên: đóng phiên để bù trừ (spec §6.2 F12).
            await self._close_session(session.session_id)
            raise
        return booking_response(booking, products)

    async def _insert(self, booking: Booking) -> None:
        for attempt in range(_REFERENCE_RETRIES):
            try:
                async with self._store.transaction() as tx:
                    await tx.insert(booking)
                return
            except ReferenceCodeTaken:
                booking.reference_code = new_reference_code(booking.created_at.date())
        raise RuntimeError("không sinh được mã đặt chỗ duy nhất")

    async def _release_stale_hold(self, cdp_user_id: str) -> None:
        """Có đơn giữ chỗ còn hạn thì báo 409; quá hạn mà webhook chưa tới thì đối soát ngay để giải phóng."""
        async with self._store.transaction() as tx:
            existing = await tx.get_pending_for_user(cdp_user_id)
        if existing is None:
            return
        if HoldPolicy.is_active(existing.hold_expires_at, self._clock()):
            raise PendingPaymentExists("đang có đơn chờ thanh toán", {
                "referenceCode": existing.reference_code, "holdExpiresAt": iso(existing.hold_expires_at)})
        await self._reconciler.reconcile_one(existing.booking_id)
        async with self._store.transaction() as tx:
            still = await tx.get_pending_for_user(cdp_user_id)
        if still is not None:
            raise PendingPaymentExists("đang có đơn chờ thanh toán", {
                "referenceCode": still.reference_code, "holdExpiresAt": iso(still.hold_expires_at)})

    async def _pending_error(self, cdp_user_id: str) -> PendingPaymentExists:
        async with self._store.transaction() as tx:
            existing = await tx.get_pending_for_user(cdp_user_id)
        details = ({"referenceCode": existing.reference_code, "holdExpiresAt": iso(existing.hold_expires_at)}
                   if existing else None)
        return PendingPaymentExists("đang có đơn chờ thanh toán", details)

    async def _close_session(self, session_id: str) -> None:
        try:
            await self._gateway.expire_checkout_session(session_id)
        except Exception:
            logger.error("booking.create.compensation_failed sessionId=%s requestId=%s",
                         session_id, current_request_id())

