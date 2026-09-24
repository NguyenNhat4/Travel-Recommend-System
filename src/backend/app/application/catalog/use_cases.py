"""GET /products/{productId}: chi tiết sản phẩm kèm tầng con đặt được (backend §4.2)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Callable

from src.backend.app.application.ports.product_catalog import ProductCatalog
from src.backend.app.domain.booking import ProductNotFound

from .views import product_detail


def _today() -> date:
    return datetime.now(timezone.utc).date()


@dataclass
class GetProductDetail:
    catalog: ProductCatalog
    today: Callable[[], date] = field(default=_today)

    async def __call__(self, product_id: str) -> dict:
        product = await self.catalog.get(product_id)
        if product is None:
            raise ProductNotFound(product_id)
        variants = []
        if not product.is_bookable:
            today = self.today()
            # Chỉ con còn bán: đặt được, có giá, chưa qua ngày (chuyến bay có from = to = ngày bay).
            variants = sorted(
                (child for child in await self.catalog.children(product.product_id)
                 if child.is_bookable and child.available and child.unit_price is not None
                 and (child.available_to is None or child.available_to >= today)),
                key=lambda child: (child.unit_price, child.available_from or today, child.name),
            )
        return product_detail(product, variants)
