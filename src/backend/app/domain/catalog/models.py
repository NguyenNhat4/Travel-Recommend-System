"""Entity thuần cho catalog. Không import FastAPI/DB/numpy."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TAXONOMIES = ("hotel", "flight", "attraction", "combo", "golf")


@dataclass
class Product:
    product_id: str
    name: str
    taxonomy: str
    destination: str
    description: str
    attributes: dict[str, Any] = field(default_factory=dict)
    unit_price: float | None = None
    available: bool = True
    image_url: str | None = None

    @classmethod
    def from_cdp(cls, row: dict) -> "Product":
        """row = một dòng products.jsonl (13 trường CDP, camelCase)."""
        return cls(
            product_id=row["productId"], name=row["name"], taxonomy=row["taxonomy"], destination=row["destination"],
            description=row.get("description") or "", attributes=row.get("attributes") or {},
            unit_price=row.get("unitPrice"), available=bool(row.get("available")), image_url=row.get("imageUrl"),
        )

    # --- vai trò suy ra (cùng quy tắc với view catalog.product_meta)
    @property
    def level(self) -> str | None:
        return self.attributes.get("level")

    @property
    def parent_id(self) -> str | None:
        return self.attributes.get("parentProductId") or None

    @property
    def variant(self) -> str:
        if self.taxonomy == "hotel":
            return "hotel_" + (self.level or "property")
        if self.taxonomy == "flight":
            return "flight_route" if self.level == "route" else "flight"
        return self.taxonomy

    @property
    def is_search_unit(self) -> bool:
        return self.variant not in ("hotel_room", "flight")

    @property
    def is_bookable(self) -> bool:
        return self.level not in ("property", "route") and self.attributes.get("ticketed") is not False and self.unit_price is not None
