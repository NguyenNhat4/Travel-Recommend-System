"""Use case catalog: chi tiết, danh sách và sản phẩm tương tự (docs/spec/hop-dong-tich-hop-backend.md §4)."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.backend.app.application.catalog.errors import (
    CatalogUnavailable,
    InvalidCatalogRequest,
    ProductNotFound,
    ProductNotIndexed,
)
from src.backend.app.application.catalog.views import product_detail, product_summary
from src.backend.app.application.ports.product_query import ProductQuery
from src.backend.app.application.search.use_cases import SimilarProducts
from src.backend.app.core.call_context import note
from src.backend.app.domain.catalog import (
    DIVERSIFY_MODES,
    PRODUCT_SORTS,
    TAXONOMIES,
    ListingItem,
    fare_classes_by_product,
    filter_items,
    interleave_by_taxonomy,
    is_fare_variant,
    precompute_orders,
    sort_items,
    summarize_variants,
)


def _today() -> date:
    """Ngày Việt Nam: báo giá vé hết hạn theo ngày của nguồn (priceValidUntil)."""
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()


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
        fares = None
        if is_fare_variant(product) and product.parent_id:  # hạng vé của cùng hành trình nằm trong các chuyến anh em
            siblings = {p.product_id: p for p in await self.products.variants(product.parent_id)}
            siblings[product.product_id] = product
            fares = fare_classes_by_product(siblings.values(), _today()).get(product.product_id)
        return product_detail(product, variants, fares)


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
    # Số trang đã trả nhớ theo khoá truy vấn (LRU). 0 = tắt. Instance dựng lại mỗi lần nạp catalog, nên cache tự hết.
    response_cache_size: int = 0
    _orders: dict[str, list[ListingItem]] = field(init=False, repr=False, default_factory=dict)
    _cache: OrderedDict = field(init=False, repr=False, default_factory=OrderedDict)

    def __post_init__(self) -> None:
        # Thứ tự sắp xếp của từng `sort` tính một lần ở đây; request chỉ lọc và cắt trang (domain precompute_orders).
        if self.units is not None:
            self._orders = precompute_orders(self.units, self.popularity)

    async def __call__(self, *, destination: str | None = None, taxonomy: str | Sequence[str] | None = None,
                       available_only: bool = False, sort: str = "popular", limit: int = 20, offset: int = 0,
                       parent_product_id: str | None = None, diversify: str | None = None,
                       free_only: bool = False) -> dict:
        """`taxonomy`: một loại hoặc nhiều loại (route tách `taxonomy=a,b`), giá trị trùng bỏ qua.

        `diversify="taxonomy"` (contract 1.27.0): trộn theo nhóm loại sau khi sắp xếp, trước khi cắt trang; chỉ với
        `sort=popular` và không có `parent_product_id`.
        """
        taxonomies = [taxonomy] if isinstance(taxonomy, str) else (None if taxonomy is None else list(taxonomy))
        invalid = [name for name, bad in (
            ("sort", sort not in PRODUCT_SORTS),
            ("taxonomy", taxonomies is not None and (not taxonomies or not set(taxonomies) <= set(TAXONOMIES))),
            ("limit", not 1 <= limit <= self.max_limit),
            ("offset", offset < 0),
            ("diversify", diversify is not None and (diversify not in DIVERSIFY_MODES or sort != "popular"
                                                     or bool(parent_product_id))),
        ) if bad]
        if invalid:
            raise InvalidCatalogRequest("tham số không hợp lệ", {"fields": invalid})
        if parent_product_id is None and self.units is not None:
            return self._page_from_units(destination, taxonomies, available_only, sort, limit, offset, diversify)
        fares: Mapping[str, list] = {}
        if parent_product_id:
            children = await self.products.variants(parent_product_id)
            items: Sequence[ListingItem] = [ListingItem(p, p.is_bookable) for p in children]
            fares = fare_classes_by_product(children, _today())  # gom trên mọi chuyến của tuyến, trước khi phân trang
        else:
            items = self.units if self.units is not None else await self.products.search_units()
        ordered = sort_items(
            filter_items(items, destination=destination, taxonomy=None if taxonomies is None else set(taxonomies),
                         available_only=available_only, free_only=free_only),
            sort, self.popularity, variants=bool(parent_product_id))
        if diversify == "taxonomy":  # trộn trước khi cắt trang: hoán vị, `total` và các trang nối tiếp không đổi
            ordered = interleave_by_taxonomy(ordered)
        return {
            "results": [product_summary(i.product, fares.get(i.product.product_id))
                        for i in ordered[offset: offset + limit]],
            "total": len(ordered), "limit": limit, "offset": offset,
        }

    def _page_from_units(self, destination: str | None, taxonomies: list[str] | None, available_only: bool,
                         sort: str, limit: int, offset: int, diversify: str | None) -> dict:
        """Trang từ danh sách đã sắp xếp sẵn: lọc giữ thứ tự, không sắp xếp lại. Kết quả nhớ theo khoá, LRU."""
        key = (destination, None if taxonomies is None else tuple(sorted(set(taxonomies))), available_only, sort,
               limit, offset, diversify)
        if self.response_cache_size and key in self._cache:
            self._cache.move_to_end(key)
            note(catalogCache="hit")
            return self._cache[key]
        if destination is None and taxonomies is None and not available_only:
            ordered: list[ListingItem] = self._orders[sort]  # không có điều kiện lọc: dùng thẳng, không sửa danh sách này
        else:
            ordered = filter_items(self._orders[sort], destination=destination,
                                   taxonomy=None if taxonomies is None else set(taxonomies),
                                   available_only=available_only)
        if diversify == "taxonomy":  # trộn trước khi cắt trang: hoán vị, `total` và các trang nối tiếp không đổi
            ordered = interleave_by_taxonomy(ordered)
        result = {
            "results": [product_summary(i.product, None) for i in ordered[offset: offset + limit]],
            "total": len(ordered), "limit": limit, "offset": offset,
        }
        if self.response_cache_size:
            note(catalogCache="miss")
            self._cache[key] = result
            while len(self._cache) > self.response_cache_size:
                self._cache.popitem(last=False)
        return result


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
