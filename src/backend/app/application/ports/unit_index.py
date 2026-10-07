"""Metadata các search unit mà ba engine Search / Similar / Recommendation cùng đọc để lọc trước."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from src.backend.app.domain.catalog import Product, UnitAttributes


@dataclass
class UnitIndex:
    """Ảnh chụp search unit từ Postgres; vector không nằm ở đây mà truy vấn qua `VectorSearchPort`."""
    units: list[Product]
    taxonomy: np.ndarray               # (n,) str
    destination: np.ndarray            # (n,) str
    available: np.ndarray              # (n,) bool
    recommendable: np.ndarray          # (n,) bool  — is_recommendable của product_meta
    parent_of: dict[str, str]          # child product_id → parent product_id
    model_version: str
    attrs: UnitAttributes | None = None  # thuộc tính lọc Phase A (F3/F5/F6); None → dựng từ unit, không có con

    def __post_init__(self):
        self.idx = {p.product_id: i for i, p in enumerate(self.units)}
        if self.attrs is None:
            self.attrs = UnitAttributes.build(self.units)

    def resolve(self, product_id: str) -> int | None:
        """Phòng/chuyến → index của cha."""
        return self.idx.get(self.parent_of.get(product_id, product_id))

    def mask(self, taxonomy=None, destination=None, only_available=True, only_recommendable=False, *,
             origin_city: str | None = None, destination_city: str | None = None,
             price_min: float | None = None, price_max: float | None = None,
             star_min: float | None = None, exclude_amenities: Iterable[str] = (),
             exclude_brands: Iterable[str] = (), exclude_taxonomies: Iterable[str] = (),
             exclude_flags: Iterable[str] = (), min_occupancy: int | None = None,
             require_entities: Iterable[str] = ()) -> np.ndarray:
        """Mask bool theo index unit; mọi tham số mới mặc định tắt nên không đổi hành vi cũ.

        Quy ước "không biết" (spec §2.7 [C2]):
        - giá: có một trong hai biên thì unit giá NaN bị LOẠI (contract: giá null bị loại khi áp filter giá);
        - sao: chỉ loại unit sao ĐÃ BIẾT và < `star_min`; NaN giữ lại (mềm — demote ở `soft_star_order`);
        - tiện ích: chỉ loại unit CÓ khoá nằm trong `exclude_amenities`; vắng khoá = không biết → giữ;
        - cờ (`exclude_flags`, `UnitAttributes.FLAGS`): chỉ loại unit CÓ cờ; không cờ = không biết → giữ;
        - sức chứa: chỉ loại unit sức chứa ĐÃ BIẾT và < `min_occupancy`; NaN giữ (không biết ≠ "quá nhỏ").
        `exclude_taxonomies`: loại unit có taxonomy nằm trong tập (kiến trúc §6 — chặn cross-vertical).
        `require_entities` (contract 1.18.0, entity gate CỨNG): chỉ giữ unit có ít nhất một khoá entity trong tập
        (`UnitAttributes.entities` — dựng từ TÊN unit, chỉ attraction/combo có khoá); unit không có khoá bị loại — đây là gate,
        không phải quy ước "không biết → giữ". Rỗng = không gate.
        """
        m = np.ones(len(self.units), dtype=bool)
        if only_available:
            m &= self.available
        if only_recommendable:
            m &= self.recommendable
        if taxonomy:
            m &= np.isin(self.taxonomy, [taxonomy] if isinstance(taxonomy, str) else list(taxonomy))
        if destination:
            m &= self.destination == destination
        a = self.attrs
        if origin_city:
            m &= a.origin_city == origin_city
        if destination_city:
            m &= a.destination_city == destination_city
        if price_min is not None or price_max is not None:
            m &= ~np.isnan(a.min_price)
            if price_min is not None:
                m &= a.min_price >= price_min
            if price_max is not None:
                m &= a.min_price <= price_max
        if star_min is not None:
            m &= np.isnan(a.star_rating) | (a.star_rating >= star_min)
        excluded = frozenset(exclude_amenities)
        if excluded:
            m &= np.array([not (keys & excluded) for keys in a.amenities], dtype=bool)
        brands = [b for b in exclude_brands if b]
        if brands:   # "không phải Vinpearl": chỉ loại unit có ghi brand đó; brand rỗng = không biết → giữ
            m &= ~np.isin(a.brand, brands)
        drop_tax = sorted({t for t in exclude_taxonomies if t})
        if drop_tax:
            m &= ~np.isin(self.taxonomy, drop_tax)
        drop_flags = frozenset(f for f in exclude_flags if f)
        if drop_flags:
            m &= np.array([not (f & drop_flags) for f in a.flags], dtype=bool)
        if min_occupancy is not None:
            m &= np.isnan(a.max_occupancy) | (a.max_occupancy >= min_occupancy)
        req = frozenset(k for k in require_entities if k)
        if req:
            m &= np.array([bool(e & req) for e in a.entities], dtype=bool)
        return m

    def matched_children(self, i: int, *, price_min: float | None = None, price_max: float | None = None,
                         min_occupancy: int | None = None, limit: int = 5) -> list[str]:
        """productId các phòng/chuyến con của unit `i` thoả MỌI điều kiện được truyền (kiến trúc §6 parent–child filter),
        theo thứ tự đã lưu (giá tăng dần, giá null cuối), tối đa `limit`. Không truyền điều kiện nào → [].

        Giá: có biên thì con giá null bị loại (như `mask`). Sức chứa: con không biết sức chứa được giữ."""
        if (price_min is None and price_max is None and min_occupancy is None) or limit <= 0:
            return []
        priced = price_min is not None or price_max is not None
        out: list[str] = []
        for child_id, price, occupancy in self.attrs.children[i]:
            if priced and (price is None or (price_min is not None and price < price_min)
                           or (price_max is not None and price > price_max)):
                continue
            if min_occupancy is not None and occupancy is not None and occupancy < min_occupancy:
                continue
            out.append(child_id)
            if len(out) >= limit:
                break
        return out

    def star_known_ok(self, star_min: float) -> np.ndarray:
        """True ở unit có sao ĐÃ BIẾT và >= `star_min`; NaN → False (dùng để đẩy unit chưa biết sao xuống sau)."""
        star = self.attrs.star_rating
        return ~np.isnan(star) & (star >= star_min)

    def allowed_ids(self, mask: np.ndarray) -> list[str] | None:
        """productId của các unit trong mask; None khi mask phủ toàn bộ (khỏi gửi filter)."""
        if mask.all():
            return None
        return [self.units[i].product_id for i in np.flatnonzero(mask)]

class VectorStorePort(Protocol):
    def load(self) -> UnitIndex: ...


class CdpClientPort(Protocol):
    """Cửa duy nhất vào CDP (handbook §6). Trả dict theo tên trường CDP (camelCase)."""

    def events_for_user(self, cdp_user_id: str) -> list[dict]: ...
    def purchase_events(self, since_days: int = 730) -> list[dict]: ...
    def all_events(self) -> list[dict]: ...
