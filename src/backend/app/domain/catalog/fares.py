"""Hạng vé của cùng một hành trình bay (contract FareClass / ProductSummary.fareClasses, 1.9.0).

Mỗi hạng vé là một sản phẩm `taxonomy: flight`, `level: flight` riêng (đề xuất đã chốt
docs/prd/update-archive/2026-09-29-ve-khu-hoi-dat-duoc.md). Hàm ở đây chỉ gom các sản phẩm cùng hành trình và dựng mảng
cho Web; không suy hạng, giá, hành lý hay số ghế khi nguồn không cung cấp.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from typing import Any

from .models import Product

CABIN_CODES = {"ECONOMY": "ECO", "PREMIUM_ECONOMY": "PRE", "BUSINESS": "BUS", "FIRST": "FST"}
CABIN_NAMES = {"ECO": "Phổ thông", "PRE": "Phổ thông đặc biệt", "BUS": "Thương gia", "FST": "Hạng nhất"}
UNKNOWN_CABIN_NAME = "Giá rẻ nhất"
_ORDER = {code: i for i, code in enumerate(("ECO", "PRE", "BUS", "FST"))}


def is_fare_variant(product: Product) -> bool:
    return product.taxonomy == "flight" and product.level == "flight"


def itinerary_key(product: Product) -> tuple | None:
    """Khoá hành trình: loại vé, các số hiệu chuyến và giờ đi; khứ hồi thêm chuyến và giờ về. Không gồm hạng / giá."""
    if not is_fare_variant(product):
        return None
    a = product.attributes
    numbers = tuple(a.get("flightNumbers") or ([a["flightNumber"]] if a.get("flightNumber") else []))
    if not numbers:
        return None
    back = a.get("returnFlight") if isinstance(a.get("returnFlight"), dict) else {}
    return (a.get("tripType") or "oneWay", a.get("parentProductId"), numbers, str(a.get("departureAt") or "")[:16],
            back.get("flightNumber"), str(back.get("departureAt") or a.get("returnDate") or "")[:16])


def _price(value: float | None) -> int | float | None:
    if value is None:
        return None
    return int(value) if float(value).is_integer() else value


def fare_class(product: Product, today: date) -> dict[str, Any]:
    a = product.attributes
    code = CABIN_CODES.get(str(a.get("cabinClass") or "").upper())
    valid_until = a.get("priceValidUntil")
    try:
        expired = valid_until is not None and date.fromisoformat(str(valid_until)[:10]) < today
    except ValueError:
        expired = False
    if expired:
        status = "EXPIRED"
    elif product.available and product.unit_price is not None:
        status = "AVAILABLE"
    else:
        status = "NOT_CHECKED"
    return {
        "productId": product.product_id,
        "code": code,
        "name": CABIN_NAMES.get(code, UNKNOWN_CABIN_NAME),
        "price": _price(product.unit_price),
        "currency": product.currency,
        "priceValidUntil": str(valid_until)[:10] if valid_until else None,
        "availabilityStatus": status,
        # Chưa nguồn nào cung cấp số ghế, hành lý theo kg, suất ăn hay điều kiện đổi vé: để null (= chưa biết).
        "soldOut": None,
        "carryOnKg": None,
        "checkedKg": None,
        "mealIncluded": None,
        "changeRule": None,
    }


def fare_classes_by_product(products: Iterable[Product], today: date) -> dict[str, list[dict[str, Any]]]:
    """productId → fareClasses của hành trình chứa nó (gồm chính nó), theo thứ tự ECO, PRE, BUS, FST, chưa rõ hạng.

    Chỉ gom trong tập `products` được đưa vào (thường là các tầng con của cùng một tuyến)."""
    groups: dict[tuple, list[Product]] = defaultdict(list)
    for product in products:
        key = itinerary_key(product)
        if key is not None:
            groups[key].append(product)
    out: dict[str, list[dict[str, Any]]] = {}
    for members in groups.values():
        fares = sorted((fare_class(p, today) for p in members),
                       key=lambda f: (_ORDER.get(f["code"], len(_ORDER)), f["price"] is None, f["price"] or 0))
        for product in members:
            out[product.product_id] = fares
    return out
