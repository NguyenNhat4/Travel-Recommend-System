"""Quy tắc thuần cho GET /products: lọc, sắp xếp và tóm tắt tầng con (docs/spec/hop-dong-tich-hop-backend.md §4.1)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .models import Product

PRODUCT_SORTS = ("popular", "price_asc", "price_desc")


@dataclass(frozen=True)
class ListingItem:
    """Một sản phẩm ứng viên cho trang danh sách, kèm cờ is_recommendable của view product_meta."""
    product: Product
    recommendable: bool = True


@dataclass(frozen=True)
class VariantSummary:
    count: int
    min_price: float | None
    max_price: float | None
    max_occupancy: int | None


def summarize_variants(children: Iterable[Product]) -> VariantSummary:
    """count đếm mọi tầng con; khoảng giá chỉ tính con đang mở bán và có giá."""
    children = list(children)
    prices = [c.unit_price for c in children if c.available and c.unit_price is not None]
    occupancies = [c.max_occupancy for c in children if c.max_occupancy is not None]
    return VariantSummary(
        count=len(children),
        min_price=min(prices) if prices else None,
        max_price=max(prices) if prices else None,
        max_occupancy=max(occupancies) if occupancies else None,
    )


def filter_items(items: Iterable[ListingItem], *, destination: str | None = None, taxonomy: str | None = None,
                 available_only: bool = False) -> list[ListingItem]:
    return [
        i for i in items
        if (destination is None or i.product.destination == destination)
        and (taxonomy is None or i.product.taxonomy == taxonomy)
        and (not available_only or i.product.available)
    ]


def _price_key(item: ListingItem, descending: bool) -> tuple:
    """Sản phẩm chưa có giá luôn xếp cuối, bất kể chiều sắp xếp."""
    price = item.product.unit_price
    if price is None:
        return (1, 0.0, item.product.name)
    return (0, -price if descending else price, item.product.name)


def sort_items(items: Sequence[ListingItem], sort: str, popularity: Mapping[str, float] | None = None,
               *, variants: bool = False) -> list[ListingItem]:
    """popular: lượt mua nhiều trước, rồi sản phẩm gợi ý/đặt được, rồi giá có trước, rồi tên.

    Tầng con (variants=True) không có popularity riêng: popular xếp như price_asc.
    """
    if sort not in PRODUCT_SORTS:
        raise ValueError(f"sort không hợp lệ: {sort}")
    if sort == "price_desc":
        return sorted(items, key=lambda i: _price_key(i, True))
    if sort == "price_asc" or variants:
        return sorted(items, key=lambda i: _price_key(i, False))
    popularity = popularity or {}
    return sorted(items, key=lambda i: (
        -popularity.get(i.product.product_id, 0.0),
        not i.recommendable,
        i.product.unit_price is None,
        i.product.name,
    ))
