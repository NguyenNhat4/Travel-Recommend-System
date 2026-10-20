"""Entity thuần cho catalog. Không import FastAPI/DB/numpy."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

TAXONOMIES = ("hotel", "flight", "attraction", "combo", "golf")
#: Nguồn điểm đánh giá theo thứ tự ưu tiên (docs/spec/data-collection/schema.md §8.1): (khoá điểm, khoá thang,
#: khoá số lượt). Thang `None` là thang 5 cố định của nguồn đó.
RATING_SOURCES = (
    ("reviewScore", "reviewScoreScale", "reviewCount"),
    ("tripAdvisorRating", None, "tripAdvisorReviewCount"),
    ("rating", "ratingScale", "reviewCount"),
)


def entry_policy(taxonomy: str, price: float | None, ticketed: bool | None = None) -> str:
    """Phí vào cửa, gồm giả định tham quan tự do được chốt 13/10/2026; không đổi giá nguồn."""
    if taxonomy in ("attraction", "golf"):
        if price == 0 or ticketed is False:
            return "free"
        if price is None and ticketed is not True:
            return "assumed_free"
    return "unknown" if price is None else "paid"


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
    def from_cdp(cls, row: dict) -> Product:
        """row = một dòng products.jsonl (13 trường CDP, camelCase)."""
        return cls(
            product_id=row["productId"], name=row["name"], taxonomy=row["taxonomy"], destination=row["destination"],
            description=row.get("description") or "", attributes=row.get("attributes") or {},
            unit_price=row.get("unitPrice"), currency=row.get("currency") or "VND",
            available=bool(row.get("available")),
            available_from=_date(row.get("availableFrom")), available_to=_date(row.get("availableTo")),
            image_url=row.get("imageUrl"),
        )

    def _rating_source(self) -> tuple[float, int | None] | None:
        """Điểm 0–5 (một chữ số) và số lượt của nguồn đầu tiên trong `RATING_SOURCES` có điểm hợp lệ."""
        for score_key, scale_key, count_key in RATING_SOURCES:
            try:
                score = float(self.attributes.get(score_key))
                scale = 5.0 if scale_key is None else float(self.attributes.get(scale_key))
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(score) and math.isfinite(scale)) or scale <= 0:
                continue
            count = self.attributes.get(count_key)
            count = int(count) if isinstance(count, (int, float)) and not isinstance(count, bool) and count >= 0 else None
            return round(max(0.0, min(5.0, score / scale * 5)), 1), count
        return None

    @property
    def rating(self) -> float | None:
        """Điểm đánh giá 0–5, một chữ số (contract ProductSummary.rating); không nguồn nào có điểm thì None."""
        source = self._rating_source()
        return source[0] if source else None

    @property
    def review_count(self) -> int | None:
        """Số lượt của cùng nguồn với `rating`; `rating` là None thì cũng None (hop-dong-tich-hop-backend.md §2.2)."""
        source = self._rating_source()
        return source[1] if source else None

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

    @property
    def entry_policy(self) -> str:
        return entry_policy(self.taxonomy, self.unit_price, self.attributes.get("ticketed"))

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
