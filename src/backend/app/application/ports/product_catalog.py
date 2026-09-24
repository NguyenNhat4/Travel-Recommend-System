"""Port đọc catalog sản phẩm ở mọi tầng (property, hạng phòng, route, chuyến bay...) cho trang chi tiết và giỏ.

Khác `UnitIndex` (chỉ search unit, nạp một lần cho RecSys): giỏ và checkout cần giá và tình trạng hiện tại của
đúng đơn vị đặt được, nên đọc thẳng catalog mỗi request.
"""
from __future__ import annotations

from typing import Protocol, Sequence

from src.backend.app.domain.catalog import Product


class ProductCatalog(Protocol):
    async def get(self, product_id: str) -> Product | None:
        """None khi không có sản phẩm, kể cả khi `product_id` không phải id hợp lệ."""
        ...

    async def get_many(self, product_ids: Sequence[str]) -> dict[str, Product]:
        """Chỉ trả các id tìm thấy."""
        ...

    async def children(self, parent_id: str) -> list[Product]:
        """Các sản phẩm có `attributes.parentProductId = parent_id` (hạng phòng, chuyến bay)."""
        ...
