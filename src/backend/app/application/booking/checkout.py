"""Checkout toàn bộ giỏ và đọc lại đơn (backend §7.2–7.4, cdp §5).

Thứ tự bắt buộc: kiểm giỏ/giá/tình trạng → ghi `purchase` sang CDP → commit booking và xoá giỏ. Event có
trước khi trả `201`, nên `/recommendations` gọi ngay sau đó đã thấy lượt đặt (vòng lặp K1, FR-REC-02).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from src.backend.app.application.ports.booking_repository import Booking, BookingLine, BookingRepository
from src.backend.app.application.ports.cart_repository import CartRepository
from src.backend.app.application.ports.cdp_client import CdpClient, CdpUnavailableError, PurchaseEvent
from src.backend.app.application.ports.product_catalog import ProductCatalog
from src.backend.app.core.request_context import current_request_id
from src.backend.app.domain.booking import (
    BookingNotFound,
    CartEmpty,
    CheckoutFailed,
    InvalidField,
    PriceChanged,
    bookable_product,
    ensure_open,
    event_group_id,
    reference_code,
)

from .purchase_events import commit_with_purchase_events
from .views import booking_line_total, booking_view, stay_length

logger = logging.getLogger(__name__)

#: Giá numeric(14,2) đi qua float: lệch dưới nửa đồng coi là bằng nhau.
_PRICE_TOLERANCE = 0.005


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_item_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Checkout:
    carts: CartRepository
    bookings: BookingRepository
    catalog: ProductCatalog
    cdp: CdpClient
    clock: Callable[[], datetime] = field(default=_utc_now)
    new_item_id: Callable[[], str] = field(default=_new_item_id)

    async def __call__(self, cdp_user_id: str, contact: dict, item_details: list[dict]) -> dict:
        cart = await self.carts.load(cdp_user_id)
        if not cart.lines:
            raise CartEmpty()
        # itemDetails chỉ bổ sung thông tin theo mục, không đổi thành phần giỏ (backend §7.2).
        details = {detail["cartItemId"]: detail for detail in item_details}
        unknown = sorted(set(details) - {line.cart_item_id for line in cart.lines})
        if unknown:
            raise InvalidField("itemDetails", cartItemId=unknown[0])

        products = await self.catalog.get_many([line.product_id for line in cart.lines])
        now = self.clock()
        group = event_group_id(now.date())
        lines: list[BookingLine] = []
        events: list[PurchaseEvent] = []
        for line in cart.lines:
            product = bookable_product(products.get(line.product_id), line.product_id)
            if abs(product.unit_price - line.unit_price_snapshot) > _PRICE_TOLERANCE:
                raise PriceChanged(product.product_id, line.unit_price_snapshot, product.unit_price)
            ensure_open(product, line.using_date, stay_length(product.taxonomy, line.using_date, line.using_date_to))
            item_id = self.new_item_id()
            lines.append(BookingLine(
                booking_item_id=item_id, product_id=product.product_id, taxonomy=product.taxonomy,
                product_name=product.name, unit_price=product.unit_price, quantity=line.quantity,
                using_date=line.using_date, using_date_to=line.using_date_to,
                guest_names=tuple(details.get(line.cart_item_id, {}).get("guestNames") or ()),
            ))
            events.append(PurchaseEvent(
                booking_item_id=item_id, cdp_user_id=cdp_user_id, product_id=product.product_id,
                taxonomy=product.taxonomy, event_group_id=group, quantity=line.quantity,
                unit_price=product.unit_price, using_date=line.using_date, timestamp=now,
            ))

        requests: list[str] = []
        for line in cart.lines:
            text = (details.get(line.cart_item_id, {}).get("specialRequest") or "").strip()
            if text and text not in requests:
                requests.append(text)
        booking = Booking(
            reference_code=await self._reference_code(now), cdp_user_id=cdp_user_id, event_group_id=group,
            contact_name=contact["fullName"], contact_email=contact["email"], contact_phone=contact["phone"],
            special_request="\n".join(requests) or None,
            total_amount=sum(booking_line_total(line) for line in lines), currency="VND", created_at=now,
            lines=tuple(lines),
        )
        try:
            await commit_with_purchase_events(self.cdp, events, lambda: self.bookings.save(booking))
        except CdpUnavailableError as exc:
            logger.warning("checkout.cdp_unavailable requestId=%s reason=%s", current_request_id(), exc)
            raise CheckoutFailed() from exc
        except Exception as exc:
            logger.exception("checkout.commit_failed requestId=%s referenceCode=%s",
                             current_request_id(), booking.reference_code)
            raise CheckoutFailed() from exc
        logger.info("checkout.confirmed requestId=%s referenceCode=%s items=%d",
                    current_request_id(), booking.reference_code, len(lines))
        return booking_view(booking, products)

    async def _reference_code(self, now: datetime) -> str:
        for _ in range(5):
            code = reference_code(now.date())
            if not await self.bookings.reference_taken(code):
                return code
        raise CheckoutFailed()


@dataclass
class GetBooking:
    bookings: BookingRepository
    catalog: ProductCatalog

    async def __call__(self, cdp_user_id: str, reference_code: str) -> dict:
        booking = await self.bookings.find(reference_code, cdp_user_id)
        if booking is None:
            raise BookingNotFound()
        return booking_view(booking, await self.catalog.get_many([line.product_id for line in booking.lines]))
