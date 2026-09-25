"""Bản giả `ProductQuery`: catalog trong bộ nhớ dựng từ các dòng products.jsonl (không cần DB)."""
from __future__ import annotations

from src.backend.app.domain.catalog import ListingItem, Product


def _recommendable(product: Product, products: list[Product]) -> bool:
    """Cùng quy tắc với view catalog.product_meta: tự đặt được, hoặc có ít nhất một con đặt được."""
    if not product.is_search_unit:
        return False
    return product.is_bookable or any(
        c.parent_id == product.product_id and c.available and c.unit_price is not None for c in products)


class InMemoryProductQuery:
    def __init__(self, rows: list[dict]):
        self.products = [Product.from_cdp(r) for r in rows]
        self.by_id = {p.product_id: p for p in self.products}
        self.search_unit_calls = 0

    async def get(self, product_id: str) -> Product | None:
        return self.by_id.get(product_id)

    async def variants(self, parent_product_id: str) -> list[Product]:
        return [p for p in self.products if p.parent_id == parent_product_id]

    async def search_units(self) -> list[ListingItem]:
        self.search_unit_calls += 1
        return [ListingItem(p, _recommendable(p, self.products)) for p in self.products if p.is_search_unit]
