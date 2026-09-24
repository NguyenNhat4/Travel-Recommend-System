"""Luật đặt chỗ thuần: đơn vị đặt được, cửa sổ ngày, lịch trống, thành tiền, mã tham chiếu.

Nguồn: docs/prd/requirements.md FR-CAT-02, FR-BKG-02, AC-BKG-01; docs/spec/hop-dong-tich-hop-backend.md §2.6, §7.
"""
from __future__ import annotations

import secrets
import string
from datetime import date

from src.backend.app.domain.catalog import Product

from .errors import DateOutOfRange, InvalidField, NotBookable, ProductNotFound, ProductUnavailable

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def bookable_product(product: Product | None, product_id: str) -> Product:
    """Sản phẩm phải tồn tại, là đơn vị đặt được (hạng phòng, chuyến bay, vé...) và đang bán."""
    if product is None:
        raise ProductNotFound(product_id)
    if not product.is_bookable:
        raise NotBookable(product_id)
    if not product.available:
        raise ProductUnavailable(product_id)
    return product


def stay_nights(product: Product, nights: int | None) -> int | None:
    """Số đêm của mục giỏ: bắt buộc ≥ 1 với hotel, bỏ qua với loại khác (backend §7.1)."""
    if product.taxonomy != "hotel":
        return None
    if nights is None or nights < 1:
        raise InvalidField("nights", productId=product.product_id)
    return nights


def calendar_open(availability: object, start: date, days: int) -> bool:
    """`days` ngày liên tiếp từ `start` đều là "1" trong lịch 30 ngày; không có lịch thì coi là mở.

    Cùng quy tắc với `open_nights` của seed (`src/data_collection/seed/catalog_meta.py`), để chuyến seed
    và lượt đặt thật đọc lịch giống nhau: ký tự i = ngày `from + i`, "1" = còn trống.
    """
    if not isinstance(availability, dict):
        return True
    calendar, first = availability.get("calendar"), availability.get("from")
    if not calendar or not first:
        return True
    i = (start - date.fromisoformat(str(first))).days
    return 0 <= i and i + days <= len(calendar) and all(c == "1" for c in calendar[i:i + days])


def ensure_open(product: Product, using_date: date, nights: int | None) -> None:
    """`using_date` trong cửa sổ bán và lịch còn trống mọi đêm (hotel) hoặc đúng ngày dùng (loại khác)."""
    lo, hi = product.available_from, product.available_to
    if (lo is not None and using_date < lo) or (hi is not None and using_date > hi):
        raise DateOutOfRange(product.product_id, lo.isoformat() if lo else None, hi.isoformat() if hi else None)
    if not calendar_open(product.attributes.get("availability"), using_date, nights or 1):
        raise ProductUnavailable(product.product_id)


def line_total(unit_price: float, price_unit: str, quantity: int, nights: int | None) -> int:
    """VND nguyên: `nights` chỉ nhân khi giá tính theo đêm (contract `PriceUnit`, backend §2.6)."""
    multiplier = (nights or 1) if price_unit == "PER_NIGHT" else 1
    return int(round(unit_price * quantity * multiplier))


def reference_code(day: date, token: str | None = None) -> str:
    """`VOTA-YYYYMMDD-XXXX`, XXXX là 4 ký tự chữ hoa và số (contract `ReferenceCode`)."""
    token = token or "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
    return f"VOTA-{day:%Y%m%d}-{token}"


def event_group_id(day: date, token: str | None = None) -> str:
    """Mã chuyến của một checkout. Tiền tố `WEB` để không trùng mã `OFF…` mà seed đã sinh."""
    token = token or "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
    return f"WEB{day:%Y%m%d}{token}"
