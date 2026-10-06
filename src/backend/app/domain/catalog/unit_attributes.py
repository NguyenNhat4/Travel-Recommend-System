"""Thuộc tính lọc cứng theo search unit cho /search (FR-SRC-03; kiến trúc Phase A — F3 phủ định tiện ích, F5 chặng bay,
F6 giá/sao; kiến trúc Phase A/B §6 filter-first — cờ loại sản phẩm, sức chứa, lọc phòng/chuyến con).

Một mảng theo index unit cho mỗi thuộc tính, cùng chiều với `UnitIndex.taxonomy` / `destination`, để `UnitIndex.mask`
AND thêm điều kiện mà không đụng SQL hay DDL. Giá trị lấy từ `attributes` của unit **và của phòng/chuyến con** (unit giá
NULL lấy giá thấp nhất của con — cùng quy ước với `ProductSummary.price` trong listing; sức chứa lớn nhất của unit + con —
cùng quy ước với `VariantSummary.max_occupancy`).

Cờ (`flags`, checklist dữ liệu §15): `includesFlight` / `includesHotel` cho combo có thành phần (`catalog.combo_items.item_kind`)
là `flight` / `hotel`; `ticketed` cho điểm tham quan có `attributes.ticketed` đúng bằng `true`. Thành phần combo do loader
truyền vào (`combo_kinds_of`), không parse lại mô tả ở đây.

Quy ước "không biết" (spec §2.7 [C2], `amenities.py`): tiện ích vắng khoá = không biết; `brand` / `originCity` /
`destinationCity` rỗng = ""; `starRating` / `min_price` / `max_occupancy` không có = NaN; không có cờ = không biết. Filter
quyết định loại hay giữ "không biết" ở `UnitIndex.mask`, không phải ở đây. Thuần stdlib + numpy; không pydantic, không DB.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..search.amenities import amenity_keys
from .models import Product

FLAG_INCLUDES_FLIGHT = "includesFlight"
FLAG_INCLUDES_HOTEL = "includesHotel"
FLAG_TICKETED = "ticketed"
FLAGS = frozenset({FLAG_INCLUDES_FLIGHT, FLAG_INCLUDES_HOTEL, FLAG_TICKETED})

#: Một phòng/chuyến con: (product_id, unit_price hoặc None, maxOccupancy hoặc None).
ChildRow = tuple[str, float | None, float | None]


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


def _max_occupancy(p: Product, kids: Sequence[Product]) -> float:
    """Sức chứa lớn nhất của unit và con (`Product.max_occupancy`: số ≥ 1, khác → bỏ); không ai có → NaN."""
    occ = [x.max_occupancy for x in (p, *kids) if x.max_occupancy is not None]
    return float(max(occ)) if occ else math.nan


def _flags(p: Product, combo_kinds: Iterable[str]) -> frozenset[str]:
    out: set[str] = set()
    if p.taxonomy == "combo":
        kinds = set(combo_kinds)
        if "flight" in kinds:
            out.add(FLAG_INCLUDES_FLIGHT)
        if "hotel" in kinds:
            out.add(FLAG_INCLUDES_HOTEL)
    if p.taxonomy == "attraction" and p.attributes.get("ticketed") is True:
        out.add(FLAG_TICKETED)
    return frozenset(out)


def _child_rows(kids: Sequence[Product]) -> tuple[ChildRow, ...]:
    """(id, giá, sức chứa) của từng con, sắp theo giá tăng dần (giá None cuối), hoà → id."""
    rows = [(c.product_id,
             float(c.unit_price) if c.unit_price is not None else None,
             float(c.max_occupancy) if c.max_occupancy is not None else None) for c in kids]
    rows.sort(key=lambda r: (r[1] is None, r[1] if r[1] is not None else 0.0, r[0]))
    return tuple(rows)


@dataclass(frozen=True)
class UnitAttributes:
    """Mảng thuộc tính theo index unit; mọi mảng cùng chiều (n,) với `UnitIndex.units`.

    Ba trường cuối có mặc định để dựng tay theo kiểu cũ vẫn chạy: bỏ trống → mọi unit "không biết" (không cờ, sức chứa NaN,
    không con)."""

    amenities: tuple[frozenset[str], ...]   # khoá `amenities.KEYS` của unit + con; frozenset rỗng = không biết
    brand: np.ndarray                       # (n,) object — "" khi thiếu
    star_rating: np.ndarray                 # (n,) float64 — NaN khi thiếu
    min_price: np.ndarray                   # (n,) float64 — NaN khi unit lẫn con đều không có giá
    origin_city: np.ndarray                 # (n,) object — "" trừ route bay
    destination_city: np.ndarray            # (n,) object — "" trừ route bay
    flags: tuple[frozenset[str], ...] = ()          # cờ `FLAGS` theo unit; frozenset rỗng = không cờ / không biết
    max_occupancy: np.ndarray | None = None         # (n,) float64 — max maxOccupancy của unit + con, NaN khi không biết
    children: tuple[tuple[ChildRow, ...], ...] = ()  # con của từng unit, sắp theo giá (None cuối) rồi id

    def __post_init__(self) -> None:
        n = len(self.amenities)
        if not self.flags:
            object.__setattr__(self, "flags", (frozenset(),) * n)
        if self.max_occupancy is None:
            object.__setattr__(self, "max_occupancy", np.full(n, np.nan, dtype=np.float64))
        if not self.children:
            object.__setattr__(self, "children", ((),) * n)
        if len(self.flags) != n or len(self.children) != n or self.max_occupancy.shape != (n,):
            raise ValueError("flags / max_occupancy / children phải cùng chiều với amenities")

    def __len__(self) -> int:
        return len(self.amenities)

    @staticmethod
    def build(units: Sequence[Product], children_of: Mapping[str, Sequence[Product]] | None = None,
              combo_kinds_of: Mapping[str, Iterable[str]] | None = None) -> "UnitAttributes":
        """Dựng từ danh sách unit (đúng thứ tự của `UnitIndex.units`) và map cha → con; không có con thì chỉ dùng unit.

        `combo_kinds_of`: combo product_id → các `item_kind` của thành phần combo (`catalog.combo_items`); None → không combo
        nào có cờ."""
        kids_of: Mapping[str, Sequence[Product]] = children_of or {}
        kinds_of: Mapping[str, Iterable[str]] = combo_kinds_of or {}
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
            flags=tuple(_flags(p, kinds_of.get(p.product_id, ())) for p in units),
            max_occupancy=np.array([_max_occupancy(p, cs) for p, cs in zip(units, kids)], dtype=np.float64),
            children=tuple(_child_rows(cs) for cs in kids),
        )


def _object_array(values: list[Any]) -> np.ndarray:
    """Mảng object dựng tường minh để danh sách rỗng vẫn ra shape (0,) chứ không thành mảng float."""
    out = np.empty(len(values), dtype=object)
    out[:] = values
    return out
