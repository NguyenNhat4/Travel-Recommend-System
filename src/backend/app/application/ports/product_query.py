"""Port đọc catalog cho trang danh sách và chi tiết sản phẩm (cdp.products + catalog.product_meta, chỉ đọc)."""
from __future__ import annotations

from typing import Protocol, Sequence

from src.backend.app.domain.catalog import ListingItem, Product


class ProductQuery(Protocol):
    async def get(self, product_id: str) -> Product | None:
        """Mọi tầng (property, phòng, route, chuyến bay...). id không tồn tại hoặc không phải uuid → None."""
        ...

    async def variants(self, parent_product_id: str) -> Sequence[Product]:
        """Tầng con của một sản phẩm cha; cha không tồn tại hoặc không có con → rỗng."""
        ...

    async def search_units(self) -> Sequence[ListingItem]:
        """Toàn bộ tầng cha kèm is_recommendable. Chỉ dùng khi RecSys tắt (không có UnitIndex trong RAM)."""
        ...
