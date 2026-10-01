"""Kiểm tra một dòng giỏ so với catalog (backend spec §2.6, §7.1, §7.2; spec checkout-nhieu-buoc-hanh-khach.md §8.1)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from src.backend.app.domain.catalog.models import Product

from .fares import child_unit_price


def line_total(taxonomy: str, unit_price: int, quantity: int, nights: int | None) -> int:
    """Thành tiền khi KHÔNG có trẻ em: `unitPrice × quantity` (khách sạn nhân thêm số đêm).

    Đây là trường hợp riêng của tổng các dòng giá (`fares.lines_total`), giữ lại để đọc đơn tạo trước khi có dòng giá
    (`booking_items.metadata` rỗng) và cho client cũ không thấy khác biệt.
    """
    stay = max(1, nights or 1) if taxonomy == "hotel" else 1
    return unit_price * quantity * stay


@dataclass(frozen=True)
class LineIssue:
    """Vi phạm nghiệp vụ trả về dạng giá trị; tầng API dịch sang HTTP."""

    code: str  # PRODUCT_UNAVAILABLE | PRICE_CHANGED | DATE_OUT_OF_RANGE
    details: dict[str, Any]


def check_product(
    product: Product, using_date: date, *, snapshot_price: int | None = None
) -> LineIssue | None:
    """Dùng chung cho thêm giỏ (không có snapshot) và tạo đơn (so với giá lúc thêm giỏ)."""
    if not product.available or not product.is_bookable:
        return LineIssue("PRODUCT_UNAVAILABLE", {"productId": product.product_id})
    if snapshot_price is not None and int(product.unit_price) != snapshot_price:
        return LineIssue(
            "PRICE_CHANGED",
            {"productId": product.product_id, "oldPrice": snapshot_price, "newPrice": int(product.unit_price)},
        )
    if (product.available_from and using_date < product.available_from) or (
        product.available_to and using_date > product.available_to
    ):
        return LineIssue(
            "DATE_OUT_OF_RANGE",
            {
                "productId": product.product_id,
                "availableFrom": product.available_from.isoformat() if product.available_from else None,
                "availableTo": product.available_to.isoformat() if product.available_to else None,
            },
        )
    return None


def effective_child_price(product: Product) -> int:
    """Giá một vé trẻ em thực tế: giá trẻ em hợp lệ của sản phẩm, không có thì bằng giá người lớn (D2)."""
    unit = int(product.unit_price)
    return child_unit_price(product.taxonomy, unit, product.attributes) or unit


def check_child_price(
    product: Product, *, snapshot_child: int | None, snapshot_adult: int | None
) -> LineIssue | None:
    """So giá vé trẻ em hiện tại với snapshot lúc thêm hoặc sửa mục giỏ; chỉ gọi khi mục có trẻ em.

    `snapshot_child` là None nghĩa là lúc đó sản phẩm không có giá trẻ em hợp lệ, tức trẻ em trả `snapshot_adult`.
    """
    if snapshot_adult is None:
        return None
    old = snapshot_child if snapshot_child is not None else snapshot_adult
    new = effective_child_price(product)
    if old == new:
        return None
    return LineIssue(
        "PRICE_CHANGED", {"productId": product.product_id, "oldPrice": old, "newPrice": new, "fareType": "CHILD"})
