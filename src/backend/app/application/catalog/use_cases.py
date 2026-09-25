"""Use case catalog: chi tiết, danh sách và sản phẩm tương tự (docs/spec/hop-dong-tich-hop-backend.md §4)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from src.backend.app.application.catalog.errors import (
    CatalogUnavailable,
    InvalidCatalogRequest,
    ProductNotFound,
    ProductNotIndexed,
)
from src.backend.app.application.catalog.views import product_detail, product_summary
from src.backend.app.application.ports.product_query import ProductQuery
from src.backend.app.application.search.use_cases import SimilarProducts
from src.backend.app.domain.catalog import (
    PRODUCT_SORTS,
    TAXONOMIES,
    ListingItem,
    filter_items,
    sort_items,
    summarize_variants,
)


def _not_found(product_id: str) -> ProductNotFound:
    return ProductNotFound("sản phẩm không có trong catalog", {"productId": product_id})


@dataclass
class GetProductDetail:
    products: ProductQuery

    async def __call__(self, product_id: str) -> dict:
        product = await self.products.get(product_id)
        if product is None:
            raise _not_found(product_id)
        variants = summarize_variants(await self.products.variants(product.product_id)) if product.has_variants else None
        return product_detail(product, variants)


@dataclass
class ListProducts:
    """Không có parent_product_id: tầng cha (search unit). Có: tầng con — đơn vị đặt chỗ của sản phẩm cha đó.

    `units` là ảnh chụp search unit của RecSys lúc khởi động (nhanh, cùng tập với /search); RecSys tắt thì
    đọc lại từ database mỗi request. `popularity` = productId → điểm lượt mua 0–1 (rỗng khi RecSys tắt).
    """
    products: ProductQuery
    units: Sequence[ListingItem] | None = None
    popularity: Mapping[str, float] = field(default_factory=dict)
    max_limit: int = 50

    async def __call__(self, *, destination: str | None = None, taxonomy: str | None = None,
                       available_only: bool = False, sort: str = "popular", limit: int = 20, offset: int = 0,
                       parent_product_id: str | None = None) -> dict:
        invalid = [name for name, bad in (
            ("sort", sort not in PRODUCT_SORTS),
            ("taxonomy", taxonomy is not None and taxonomy not in TAXONOMIES),
            ("limit", not 1 <= limit <= self.max_limit),
            ("offset", offset < 0),
        ) if bad]
        if invalid:
            raise InvalidCatalogRequest("tham số không hợp lệ", {"fields": invalid})
        if parent_product_id:
            items: Sequence[ListingItem] = [
                ListingItem(p, p.is_bookable) for p in await self.products.variants(parent_product_id)]
        else:
            items = self.units if self.units is not None else await self.products.search_units()
        ordered = sort_items(
            filter_items(items, destination=destination, taxonomy=taxonomy, available_only=available_only),
            sort, self.popularity, variants=bool(parent_product_id))
        return {
            "results": [product_summary(i.product) for i in ordered[offset: offset + limit]],
            "total": len(ordered), "limit": limit, "offset": offset,
        }


@dataclass
class GetSimilarProducts:
    """Sản phẩm tương tự theo vector đã lưu của anchor (search-recommendation §3.6). `similar` None khi RecSys tắt."""
    products: ProductQuery
    similar: SimilarProducts | None

    async def __call__(self, product_id: str, limit: int = 8) -> dict:
        if not 1 <= limit <= 20:
            raise InvalidCatalogRequest("tham số không hợp lệ", {"fields": ["limit"]})
        if self.similar is None:
            raise CatalogUnavailable("vector index chưa sẵn sàng")
        # Weaviate client là đồng bộ: chạy ở thread riêng để không chặn event loop.
        found = await asyncio.to_thread(self.similar.lookup, product_id, limit)
        if found.status == "not_in_index":
            product = await self.products.get(product_id)
            if product is None:
                raise _not_found(product_id)
            raise ProductNotIndexed("sản phẩm chưa có vector",
                                    {"productId": product_id, "taxonomy": product.taxonomy})
        if found.status == "no_vector":
            raise ProductNotIndexed("sản phẩm chưa có vector", {"productId": product_id})
        return {
            "productId": found.anchor_id,
            "resolvedFrom": product_id if product_id != found.anchor_id else None,
            "strategy": "same_taxonomy",
            "results": list(found.results),
        }
