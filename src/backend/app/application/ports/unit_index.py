"""Metadata các search unit mà ba engine Search / Similar / Recommendation cùng đọc để lọc trước."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.backend.app.domain.catalog import Product


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

    def __post_init__(self):
        self.idx = {p.product_id: i for i, p in enumerate(self.units)}

    def resolve(self, product_id: str) -> int | None:
        """Phòng/chuyến → index của cha."""
        return self.idx.get(self.parent_of.get(product_id, product_id))

    def mask(self, taxonomy=None, destination=None, only_available=True, only_recommendable=False) -> np.ndarray:
        m = np.ones(len(self.units), dtype=bool)
        if only_available:
            m &= self.available
        if only_recommendable:
            m &= self.recommendable
        if taxonomy:
            m &= np.isin(self.taxonomy, [taxonomy] if isinstance(taxonomy, str) else list(taxonomy))
        if destination:
            m &= self.destination == destination
        return m

    def allowed_ids(self, mask: np.ndarray) -> list[str] | None:
        """productId của các unit trong mask; None khi mask phủ toàn bộ (khỏi gửi filter)."""
        if mask.all():
            return None
        return [self.units[i].product_id for i in np.flatnonzero(mask)]
