"""Thành tiền và kiểm tra một dòng giỏ so với catalog (backend spec §2.6, §7.1, §7.2)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from src.backend.app.domain.catalog.models import Product


def line_total(taxonomy: str, unit_price: int, quantity: int, nights: int | None) -> int:
    """Chỉ khách sạn nhân số đêm; mọi taxonomy khác bỏ qua nights kể cả khi client gửi."""
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
