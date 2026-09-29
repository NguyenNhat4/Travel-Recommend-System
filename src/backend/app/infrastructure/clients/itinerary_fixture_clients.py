"""Development itinerary ports backed by the checked-in 50-product fixture."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from src.backend.app.application.ports.itinerary_tools import ToolError


class FixtureItineraryClients:
    supports_catalog = True
    supports_similar = True

    def __init__(self) -> None:
        fixture = Path(__file__).resolve().parents[4] / "shared/mocks/itinerary-agent/products.json"
        self._products: list[dict[str, Any]] = json.loads(fixture.read_text(encoding="utf-8"))

    @property
    def product_count(self) -> int:
        return len(self._products)

    async def search_products(self, request: dict[str, Any]) -> dict[str, Any]:
        products = deepcopy(self._products)
        if destination := request.get("destination"):
            products = [p for p in products if p["destination"].casefold() == destination.casefold()]
        if taxonomy := request.get("taxonomy"):
            products = [p for p in products if p["taxonomy"] == taxonomy]
        if request.get("availableOnly", True):
            products = [p for p in products if p["available"]]
        if request.get("priceMin") is not None:
            products = [p for p in products if p.get("unitPrice") is not None and p["unitPrice"] >= request["priceMin"]]
        if request.get("priceMax") is not None:
            products = [p for p in products if p.get("unitPrice") is not None and p["unitPrice"] <= request["priceMax"]]
        if request.get("starRatingMin") is not None:
            products = [p for p in products if p.get("attributes", {}).get("starRating", -1) >= request["starRatingMin"]]
        if request.get("sort") == "price_asc":
            products.sort(key=lambda p: (p.get("unitPrice") is None, p.get("unitPrice") or 0))
        elif request.get("sort") == "price_desc":
            products.sort(key=lambda p: p.get("unitPrice") or -1, reverse=True)
        offset, limit = request.get("offset", 0), request.get("limit", 20)
        page = products[offset:offset + limit]
        return {"results": [{**product, "score": 1.0} for product in page],
                "total": len(products), "limit": limit, "offset": offset,
                "topScore": 1.0 if page else None, "requestId": "fixture-search"}

    async def get_recommendations(self, request: dict[str, Any], authorization: str | None = None) -> dict[str, Any]:
        destination = request.get("destination")
        products = [p for p in deepcopy(self._products) if p["available"]]
        if destination:
            products = [p for p in products if p["destination"].casefold() == destination.casefold()]
        return {"strategy": "popular", "destination": destination,
                "recommendations": [{**p, "because": []} for p in products[:request.get("k", 5)]]}

    async def get_similar_products(self, product_id: str, limit: int) -> dict[str, Any]:
        anchor = next((p for p in self._products if p["productId"] == product_id), None)
        if anchor is None:
            raise ToolError("PRODUCT_NOT_FOUND", http_status=404)
        # Như engine same_taxonomy: cùng taxonomy, còn chỗ, loại cả cụm của anchor (sản phẩm cha và mọi hạng
        # phòng/chuyến con của nó). Fixture không có vector nên chưa có "độ gần": cùng điểm đến xếp trước,
        # phần còn lại giữ thứ tự fixture.
        root = anchor.get("attributes", {}).get("parentProductId") or product_id
        cluster = {product_id, root}
        results = [p for p in deepcopy(self._products)
                   if p["taxonomy"] == anchor["taxonomy"] and p["available"] and p["productId"] not in cluster
                   and p.get("attributes", {}).get("parentProductId") != root]
        results.sort(key=lambda p: p["destination"] != anchor["destination"])
        return {"productId": product_id, "strategy": "same_taxonomy",
                "results": [{**p, "score": 1.0} for p in results[:limit]], "requestId": "fixture-similar"}

    async def get_product_detail(self, product_id: str) -> dict[str, Any]:
        product = next((p for p in self._products if p["productId"] == product_id), None)
        if product is None:
            raise ToolError("PRODUCT_NOT_FOUND", http_status=404)
        return deepcopy(product)

    async def list_destinations(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for product in self._products:
            counts[product["destination"]] = counts.get(product["destination"], 0) + 1
        return {"destinations": [{"destination": name, "productCount": count}
                                  for name, count in sorted(counts.items())]}
