"""Kiểm và dựng một mục của giỏ hoặc của đơn nháp từ catalog: dùng chung cho `CartService` và `BookingDraftService`.

Hai nguồn dùng cùng luật (còn bán, ngày trong cửa sổ, số khách R-CRT-01…05) để trang thanh toán và `POST /bookings`
không phải phân biệt mục đến từ đâu (spec dat-truc-tiep-theo-don-nhap.md R-DRF-01, R-GST-12).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.backend.app.application.booking.errors import LineRejected
from src.backend.app.application.booking.messages import CART_MESSAGE, validation_failed
from src.backend.app.domain.booking import check_product, child_unit_price
from src.backend.app.domain.booking.party import Guests
from src.backend.app.domain.booking.party_rules import resolve_cart_guests
from src.backend.app.domain.catalog.models import Product


@dataclass(frozen=True)
class ResolvedLine:
    """Giá trị tuyệt đối để ghi xuống kho: số lượng, số khách, số đêm và snapshot giá hiện tại."""

    product_id: str
    using_date: date
    quantity: int
    nights: int | None
    unit_price: int
    adults: int
    children: int
    child_unit_price: int | None


def stay_nights(product: Product, nights: int | None) -> int | None:
    """Chỉ khách sạn có số đêm; loại khác bỏ qua kể cả khi client gửi."""
    return max(1, nights or 1) if product.taxonomy == "hotel" else None


def child_snapshot(product: Product) -> int | None:
    """Giá vé trẻ em hợp lệ hiện tại; None nghĩa là trẻ em trả giá người lớn (spec checkout §4.4)."""
    return child_unit_price(product.taxonomy, int(product.unit_price), product.attributes)


def resolve_line(
    product: Product, *, using_date: date, quantity: int | None, nights: int | None, guests: Guests | None,
    mode: str = "add", existing_quantity: int | None = None, existing_guests: Guests | None = None,
) -> ResolvedLine:
    """Kiểm sản phẩm và số khách rồi trả mục đã chuẩn hoá. Vi phạm thì raise `LineRejected` hoặc `ValidationFailed`."""
    issue = check_product(product, using_date)
    if issue:
        raise LineRejected(issue.code, issue.details)
    result = resolve_cart_guests(
        product.taxonomy, mode=mode, request_quantity=quantity, request_guests=guests,
        existing_quantity=existing_quantity, existing_guests=existing_guests, max_occupancy=product.max_occupancy)
    if result.violations:
        raise validation_failed(result.violations, user_message=CART_MESSAGE)
    return ResolvedLine(
        product_id=product.product_id, using_date=using_date, quantity=result.quantity,
        nights=stay_nights(product, nights), unit_price=int(product.unit_price), adults=result.guests.adults,
        children=result.guests.children, child_unit_price=child_snapshot(product))
