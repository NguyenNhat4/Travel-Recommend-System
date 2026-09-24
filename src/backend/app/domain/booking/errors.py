"""Lỗi nghiệp vụ của giỏ và đặt chỗ. `code` là ErrorCode của contract; tầng API dịch sang HTTP status.

Bảng mã: docs/spec/hop-dong-tich-hop-backend.md §8.2.
"""
from __future__ import annotations


class BookingError(Exception):
    code = "INTERNAL_ERROR"
    retryable = False

    def __init__(self, **details):
        super().__init__(self.code)
        self.details = details or None


class ProductNotFound(BookingError):
    code = "PRODUCT_NOT_FOUND"

    def __init__(self, product_id: str):
        super().__init__(productId=product_id)


class NotBookable(BookingError):
    """Property/route: không đặt trực tiếp, phải chọn hạng phòng hoặc chuyến bay (FR-CAT-02)."""

    code = "VALIDATION_ERROR"

    def __init__(self, product_id: str):
        super().__init__(fields=["productId"], productId=product_id, reason="NOT_BOOKABLE_LEVEL")


class InvalidField(BookingError):
    code = "VALIDATION_ERROR"

    def __init__(self, *fields: str, **details):
        super().__init__(fields=list(fields), **details)


class ProductUnavailable(BookingError):
    code = "PRODUCT_UNAVAILABLE"

    def __init__(self, product_id: str):
        super().__init__(productId=product_id)


class DateOutOfRange(BookingError):
    code = "DATE_OUT_OF_RANGE"

    def __init__(self, product_id: str, available_from: str | None, available_to: str | None):
        super().__init__(productId=product_id, availableFrom=available_from, availableTo=available_to)


class PriceChanged(BookingError):
    code = "PRICE_CHANGED"

    def __init__(self, product_id: str, old_price: float, new_price: float | None):
        super().__init__(productId=product_id, oldPrice=old_price, newPrice=new_price)


class CartEmpty(BookingError):
    code = "CART_EMPTY"


class CartItemNotFound(BookingError):
    code = "CART_ITEM_NOT_FOUND"

    def __init__(self, cart_item_id: str):
        super().__init__(cartItemId=cart_item_id)


class BookingNotFound(BookingError):
    code = "BOOKING_NOT_FOUND"


class CheckoutFailed(BookingError):
    """CDP không xác nhận purchase hoặc commit booking lỗi: không có booking, giỏ còn nguyên (cdp §5)."""

    code = "INTERNAL_ERROR"
    retryable = True
