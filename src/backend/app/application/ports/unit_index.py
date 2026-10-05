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
             exclude_brands: Iterable[str] = ()) -> np.ndarray:
        """Mask bool theo index unit; mọi tham số mới mặc định tắt nên không đổi hành vi cũ.

        Quy ước "không biết" (spec §2.7 [C2]):
        - giá: có một trong hai biên thì unit giá NaN bị LOẠI (contract: giá null bị loại khi áp filter giá);
        - sao: chỉ loại unit sao ĐÃ BIẾT và < `star_min`; NaN giữ lại (mềm — demote ở `soft_star_order`);
        - tiện ích: chỉ loại unit CÓ khoá nằm trong `exclude_amenities`; vắng khoá = không biết → giữ.
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
        return m

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
