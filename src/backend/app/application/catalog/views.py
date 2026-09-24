"""Chiếu `Product` sang payload contract `ProductSummary` / `ProductDetail` (schemas/catalog.yaml)."""
from __future__ import annotations

from src.backend.app.domain.catalog import Product


def _rating(attributes: dict) -> float | None:
    """reviewScore / reviewScoreScale * 5, một chữ số thập phân; thiếu thang điểm thì None (contract `rating`)."""
    try:
        score, scale = float(attributes["reviewScore"]), float(attributes["reviewScoreScale"])
    except (KeyError, TypeError, ValueError):
        return None
    if scale <= 0:
        return None
    return round(min(5.0, max(0.0, score / scale * 5)), 1)


def _review_count(attributes: dict) -> int | None:
    try:
        return int(attributes["reviewCount"])
    except (KeyError, TypeError, ValueError):
        return None


def product_summary(product: Product) -> dict:
    attributes = product.attributes or {}
    return {
        "productId": product.product_id,
        "name": product.name,
        "taxonomy": product.taxonomy,
        "destination": product.destination,
        "brand": attributes.get("brand"),
        "unitPrice": product.unit_price,
        "currency": product.currency,
        "priceUnit": product.price_unit,
        "available": product.available,
        # Property/route không đặt trực tiếp (FR-CAT-02). null = đơn vị đặt được nhưng chưa kiểm theo kỳ ở.
        "bookable": None if product.is_bookable else False,
        "availableFrom": product.available_from.isoformat() if product.available_from else None,
        "availableTo": product.available_to.isoformat() if product.available_to else None,
        "imageUrl": product.image_url,
        "rating": _rating(attributes),
        "reviewCount": _review_count(attributes),
        "attributes": attributes,
    }


def product_detail(product: Product, variants: list[Product]) -> dict:
    return {**product_summary(product), "description": product.description or "",
            "variants": [product_summary(variant) for variant in variants]}
