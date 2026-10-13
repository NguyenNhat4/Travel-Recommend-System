"""Quy tắc thuần cho GET /products: lọc, sắp xếp, trộn theo nhóm loại và tóm tắt tầng con
(docs/spec/hop-dong-tich-hop-backend.md §4.1)."""
from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import zip_longest

from .models import Product

PRODUCT_SORTS = ("popular", "price_asc", "price_desc")
DIVERSIFY_MODES = ("taxonomy",)
#: `diversify=taxonomy` (contract 1.27.0): nhóm trộn theo thứ tự cố định, chốt 2026-10-12. Golf chung nhóm vé tham quan.
DIVERSIFY_GROUPS: tuple[tuple[str, frozenset[str]], ...] = (
    ("hotel", frozenset({"hotel"})),
    ("experience", frozenset({"attraction", "golf"})),
    ("combo", frozenset({"combo"})),
    ("flight", frozenset({"flight"})),
)


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


def filter_items(items: Iterable[ListingItem], *, destination: str | None = None,
                 taxonomy: str | Collection[str] | None = None, available_only: bool = False,
                 free_only: bool = False) -> list[ListingItem]:
    """`taxonomy` là một loại hoặc một tập loại (contract 1.27.0, `taxonomy=attraction,golf`)."""
    wanted = None if taxonomy is None else ({taxonomy} if isinstance(taxonomy, str) else set(taxonomy))
    return [
        i for i in items
        if (destination is None or i.product.destination == destination)
        and (wanted is None or i.product.taxonomy in wanted)
        and (not available_only or i.product.available)
        and (not free_only or i.product.entry_policy in ("free", "assumed_free"))
    ]


def interleave_by_taxonomy(items: Sequence[ListingItem],
                           groups: Sequence[tuple[str, Collection[str]]] = DIVERSIFY_GROUPS) -> list[ListingItem]:
    """Trộn round-robin giữa các nhóm loại theo thứ tự của `groups`, giữ thứ tự sẵn có trong mỗi nhóm.

    Kết quả là một hoán vị của `items` (nhóm hết món thì bỏ qua), nên `total` và phân trang không đổi. Taxonomy không thuộc
    nhóm nào (giá trị enum thêm sau này) vào một nhóm cuối. Chỉ một nhóm có món thì thứ tự giữ nguyên.
    """
    slot = {taxonomy: n for n, (_, members) in enumerate(groups) for taxonomy in members}
    buckets: list[list[ListingItem]] = [[] for _ in range(len(groups) + 1)]
    for item in items:
        buckets[slot.get(item.product.taxonomy, len(groups))].append(item)
    return [item for row in zip_longest(*buckets) for item in row if item is not None]


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
