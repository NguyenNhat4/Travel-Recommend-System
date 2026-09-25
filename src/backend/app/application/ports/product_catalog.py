"""Port đọc sản phẩm từ catalog cho giỏ hàng và đơn (cdp.products, chỉ đọc)."""
from __future__ import annotations

from typing import Protocol, Sequence

from src.backend.app.domain.catalog.models import Product


class ProductCatalog(Protocol):
    async def get_products(self, product_ids: Sequence[str]) -> dict[str, Product]:
        """ID không tồn tại (hoặc không phải uuid) không có trong kết quả."""
        ...
