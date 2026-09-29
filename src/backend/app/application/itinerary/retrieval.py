"""Hydrate, normalize and filter products returned by itinerary tools."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import date

from src.backend.app.application.ports.itinerary_tools import CatalogPort
from src.backend.app.domain.itinerary.types import (
    Candidates, Constraints, Product, Sources, ToolErrorPayload, ToolResult, TripIntent,
)

from src.backend.app.application.itinerary.tool_contracts import SIMILAR_PRODUCTS

DETAIL_FIELDS = ("description", "attributes", "availableFrom", "availableTo")


def _products(results: list[ToolResult]) -> list[Product]:
    values = []
    for result in results:
        data = result.get("data", {})
        values.extend(data.get("results", []))
        values.extend(data.get("recommendations", []))
    return values


async def hydrate(results: list[ToolResult], tools: CatalogPort, existing_details: dict[str, Product],
                  timeout_seconds: float) -> tuple[dict[str, Product], dict[str, ToolErrorPayload]]:
    details, errors = deepcopy(existing_details), {}
    missing = {p["productId"] for p in _products(results) if p.get("productId") and
               any(field not in p for field in DETAIL_FIELDS)} - details.keys()
    semaphore = asyncio.Semaphore(5)

    async def load(product_id: str) -> None:
        async with semaphore:
            try:
                details[product_id] = await asyncio.wait_for(tools.get_product_detail(product_id), timeout_seconds)
            except Exception as exc:
                errors[product_id] = exc.as_dict() if hasattr(exc, "as_dict") else {
                    "code": "PRODUCT_DETAIL_UNAVAILABLE", "retryable": False, "httpStatus": None}
    await asyncio.gather(*(load(product_id) for product_id in sorted(missing)))
    return details, errors


def _normalized(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _off_destination(product: Product, intent: TripIntent) -> bool:
    return _normalized(product.get("destination")) != _normalized(intent.get("destination"))


def _drop_reason(product: Product, intent: TripIntent, constraints: Constraints) -> str | None:
    if product.get("productId") in constraints.get("exclude_products", []):
        return "PRODUCT_DROPPED_EXCLUDED"
    if _off_destination(product, intent):
        return "PRODUCT_DROPPED_DESTINATION"
    if not product.get("available"):
        return "PRODUCT_DROPPED_UNAVAILABLE"
    taxonomy = product.get("taxonomy")
    if taxonomy in constraints.get("exclude_taxonomies", []):
        return "PRODUCT_DROPPED_TAXONOMY"
    if intent.get("startDate"):
        visit = date.fromisoformat(intent["startDate"])
        if product.get("availableFrom") and visit < date.fromisoformat(product["availableFrom"]):
            return "PRODUCT_DROPPED_DATE"
        if product.get("availableTo") and visit > date.fromisoformat(product["availableTo"]):
            return "PRODUCT_DROPPED_DATE"
    if taxonomy == "hotel":
        price_max, unit = constraints.get("hotel_price_max"), constraints.get("hotel_price_unit")
        if price_max is not None:
            if product.get("unitPrice") is None or (unit and product.get("priceUnit", "UNKNOWN") != unit):
                return "PRODUCT_DROPPED_PRICE_BASIS"
            if product["unitPrice"] > price_max or (constraints.get("price_strict") and product["unitPrice"] >= price_max):
                return "PRODUCT_DROPPED_PRICE"
        attributes = product.get("attributes", {})
        if constraints.get("star_rating_min") is not None and attributes.get("starRating", -1) < constraints["star_rating_min"]:
            return "PRODUCT_DROPPED_ATTRIBUTES"
        if any(attributes.get(key) is not value for key, value in constraints.get("hotel_attributes", {}).items()):
            return "PRODUCT_DROPPED_ATTRIBUTES"
        if constraints.get("specific_hotel") and _normalized(constraints["specific_hotel"]) not in _normalized(product.get("name")):
            return "PRODUCT_DROPPED_NAMED_REQUIREMENT"
    if constraints.get("specific_activity") and taxonomy in {"attraction", "golf"} and \
            _normalized(constraints["specific_activity"]) not in _normalized(product.get("name")):
        return "PRODUCT_DROPPED_NAMED_REQUIREMENT"
    return None


def collect(tool_results: list[ToolResult], details: dict[str, Product], intent: TripIntent,
            constraints: Constraints) -> tuple[Candidates, Sources, dict[str, str]]:
    candidates, sources, dropped = {}, {}, {}
    for result in tool_results:
        data = result.get("data", {})
        # Similar tìm cùng taxonomy trên cả catalog, không theo điểm đến: sản phẩm ở nơi khác không phải
        # sản phẩm "bị loại" của chuyến này, nên bỏ qua lặng lẽ thay vì thành cảnh báo. Kết quả nằm ở
        # `results` nên mang nguồn "search" (ItemSource.SEARCH), như Search.
        similar = result.get("name") == SIMILAR_PRODUCTS
        for source, products in (("search", data.get("results", [])),
                                 ("recommendation", data.get("recommendations", []))):
            for projection in products:
                product_id = projection.get("productId")
                if not product_id:
                    continue
                product = {**deepcopy(details.get(product_id, {})), **deepcopy(projection)}
                if similar and _off_destination(product, intent):
                    continue
                reason = _drop_reason(product, intent, constraints)
                if reason:
                    dropped[product_id] = reason
                    candidates.pop(product_id, None)
                    sources.pop(product_id, None)
                else:
                    candidates[product_id], sources[product_id] = product, source
    return candidates, sources, dropped
