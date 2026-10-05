"""Thuộc tính lọc cứng theo search unit cho /search (FR-SRC-03; kiến trúc Phase A — F3 phủ định tiện ích, F5 chặng bay,
F6 giá/sao).

Một mảng theo index unit cho mỗi thuộc tính, cùng chiều với `UnitIndex.taxonomy` / `destination`, để `UnitIndex.mask`
AND thêm điều kiện mà không đụng SQL hay DDL. Giá trị lấy từ `attributes` của unit **và của phòng/chuyến con** (unit giá
NULL lấy giá thấp nhất của con — cùng quy ước với `ProductSummary.price` trong listing).

Quy ước "không biết" (spec §2.7 [C2], `amenities.py`): tiện ích vắng khoá = không biết; `brand` / `originCity` /
`destinationCity` rỗng = ""; `starRating` / `min_price` không có = NaN. Filter quyết định loại hay giữ "không biết" ở
`UnitIndex.mask`, không phải ở đây. Thuần stdlib + numpy; không pydantic, không DB.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..search.amenities import amenity_keys
from .models import Product


def _amenity_strings(p: Product) -> list[str]:
    """`attributes.amenities` là list chuỗi; None / không phải list / phần tử không phải chuỗi → bỏ qua, không báo lỗi."""
    raw = p.attributes.get("amenities")
    if not isinstance(raw, (list, tuple)):
        return []
    return [s for s in raw if isinstance(s, str)]


def _text(p: Product, key: str) -> str:
    value = p.attributes.get(key)
    return value if isinstance(value, str) else ""


def _star(p: Product) -> float:
    value = p.attributes.get("starRating")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return math.nan
    return float(value)


def _min_price(p: Product, kids: Sequence[Product]) -> float:
    prices = [x.unit_price for x in (p, *kids) if x.unit_price is not None]
    return float(min(prices)) if prices else math.nan


@dataclass(frozen=True)
class UnitAttributes:
    """Mảng thuộc tính theo index unit; mọi mảng cùng chiều (n,) với `UnitIndex.units`."""

    amenities: tuple[frozenset[str], ...]   # khoá `amenities.KEYS` của unit + con; frozenset rỗng = không biết
    brand: np.ndarray                       # (n,) object — "" khi thiếu
    star_rating: np.ndarray                 # (n,) float64 — NaN khi thiếu
    min_price: np.ndarray                   # (n,) float64 — NaN khi unit lẫn con đều không có giá
    origin_city: np.ndarray                 # (n,) object — "" trừ route bay
    destination_city: np.ndarray            # (n,) object — "" trừ route bay

    def __len__(self) -> int:
        return len(self.amenities)

    @staticmethod
    def build(units: Sequence[Product], children_of: Mapping[str, Sequence[Product]] | None = None) -> "UnitAttributes":
        """Dựng từ danh sách unit (đúng thứ tự của `UnitIndex.units`) và map cha → con; không có con thì chỉ dùng unit."""
        kids_of: Mapping[str, Sequence[Product]] = children_of or {}
        kids = [kids_of.get(p.product_id, ()) for p in units]
        return UnitAttributes(
            amenities=tuple(
                amenity_keys(_amenity_strings(p) + [s for c in cs for s in _amenity_strings(c)]) for p, cs in zip(units, kids)
            ),
            brand=_object_array([_text(p, "brand") for p in units]),
            star_rating=np.array([_star(p) for p in units], dtype=np.float64),
            min_price=np.array([_min_price(p, cs) for p, cs in zip(units, kids)], dtype=np.float64),
            origin_city=_object_array([_text(p, "originCity") for p in units]),
            destination_city=_object_array([_text(p, "destinationCity") for p in units]),
        )


def _object_array(values: list[Any]) -> np.ndarray:
    """Mảng object dựng tường minh để danh sách rỗng vẫn ra shape (0,) chứ không thành mảng float."""
    out = np.empty(len(values), dtype=object)
    out[:] = values
    return out
