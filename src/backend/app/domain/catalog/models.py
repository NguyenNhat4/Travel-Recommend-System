"""Entity thuần cho catalog. Không import FastAPI/DB/numpy."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

TAXONOMIES = ("hotel", "flight", "attraction", "combo", "golf")


def _date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


@dataclass
class Product:
    product_id: str
    name: str
    taxonomy: str
    destination: str
    description: str
    attributes: dict[str, Any] = field(default_factory=dict)
    unit_price: float | None = None
    currency: str = "VND"
    available: bool = True
    available_from: date | None = None
    available_to: date | None = None
    image_url: str | None = None

    @classmethod
    def from_cdp(cls, row: dict) -> "Product":
        """row = một dòng products.jsonl (13 trường CDP, camelCase)."""
        return cls(
            product_id=row["productId"], name=row["name"], taxonomy=row["taxonomy"], destination=row["destination"],
            description=row.get("description") or "", attributes=row.get("attributes") or {},
            unit_price=row.get("unitPrice"), currency=row.get("currency") or "VND",
            available=bool(row.get("available")),
            available_from=_date(row.get("availableFrom")), available_to=_date(row.get("availableTo")),
            image_url=row.get("imageUrl"),
        )

    @property
    def rating(self) -> float | None:
        """Điểm đánh giá 0–5 = reviewScore / reviewScoreScale × 5, một chữ số (contract ProductSummary.rating)."""
        score, scale = self.attributes.get("reviewScore"), self.attributes.get("reviewScoreScale")
        try:
            score, scale = float(score), float(scale)
        except (TypeError, ValueError):
            return None
        if scale <= 0:
            return None
        return round(max(0.0, min(5.0, score / scale * 5)), 1)

    @property
    def review_count(self) -> int | None:
        value = self.attributes.get("reviewCount")
        return int(value) if isinstance(value, (int, float)) and value >= 0 else None

    @property
    def max_occupancy(self) -> int | None:
        value = self.attributes.get("maxOccupancy")
        return int(value) if isinstance(value, (int, float)) and value >= 1 else None

    @property
    def has_variants(self) -> bool:
        """Tầng cha có tầng con để đặt (property → hạng phòng, route → chuyến bay)."""
        return self.level in ("property", "route")

    @property
    def price_unit(self) -> str:
        if self.unit_price is None:
            return "UNKNOWN"
        if self.taxonomy == "hotel":
            return "PER_NIGHT"
        if self.taxonomy == "combo":
            return "PER_PACKAGE"
        return "PER_PERSON"

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
