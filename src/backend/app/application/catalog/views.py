"""Chuyển entity catalog sang payload contract (ProductSummary, ProductDetail — schemas/catalog.yaml)."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from src.backend.app.domain.catalog import Product, VariantSummary


def _money(value: float | None) -> int | float | None:
    """Giá VND là số nguyên (backend §2.6); numeric(14,2) của DB về float nên bỏ phần .0."""
    if value is None:
        return None
    return int(value) if float(value).is_integer() else value


def public_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """[C2] Tầng serialization bỏ key có giá trị false: API chỉ trả true hoặc vắng mặt."""
    return {k: v for k, v in attributes.items() if v is not False}


def product_summary(product: Product, fare_classes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """`fare_classes`: hạng vé cùng hành trình (chỉ vé máy bay tầng con, contract 1.9.0); None thì không có khoá."""
    summary = {
        "productId": product.product_id,
        "name": product.name,
        "taxonomy": product.taxonomy,
        "destination": product.destination,
        "unitPrice": _money(product.unit_price),
        "currency": product.currency,
        "priceUnit": product.price_unit,
        "available": product.available,
        "availableFrom": product.available_from.isoformat() if product.available_from else None,
        "availableTo": product.available_to.isoformat() if product.available_to else None,
        "imageUrl": product.image_url,
        "rating": product.rating,
        "reviewCount": product.review_count,
        "attributes": public_attributes(product.attributes),
    }
    if fare_classes:
        summary["fareClasses"] = fare_classes
    return summary


def product_detail(product: Product, variants: VariantSummary | None,
                   fare_classes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        **product_summary(product, fare_classes),
        "description": product.description or "",
        "variantSummary": None if variants is None else {
            "count": variants.count,
            "minPrice": _money(variants.min_price),
            "maxPrice": _money(variants.max_price),
            "maxOccupancy": variants.max_occupancy,
        },
    }


def destination_list(destinations: Iterable[str]) -> dict[str, Any]:
    """DestinationListResponse: số unit theo điểm đến, sắp theo tên.

    Route `/destinations` và tool itinerary chạy trong tiến trình cùng dùng.
    """
    counts = Counter(str(value) for value in destinations)
    return {"destinations": [{"destination": name, "productCount": count}
                             for name, count in sorted(counts.items())]}
