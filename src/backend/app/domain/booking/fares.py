"""Dòng giá của một dịch vụ trong giỏ và trong đơn (spec checkout-nhieu-buoc-hanh-khach.md §4.3, §4.4).

Thành tiền của một mục bằng tổng `amount` các dòng giá. Mọi đơn giá lấy từ catalog tại thời điểm tính; Web không tự cộng
tiền và Backend không nhận số tiền từ client (FR-BKG-02). Code thuần, không import framework.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

# Dịch vụ tính theo người: số vé = số người lớn + số trẻ em.
PER_PERSON_TAXONOMIES = ("flight", "attraction", "golf")
# Chỉ vé tham quan và golf có giá trẻ em riêng trong catalog (D2). Chuyến bay: mọi hành khách trả một giá (D3);
# combo tính theo gói (D4); khách sạn tính theo phòng-đêm.
CHILD_PRICED_TAXONOMIES = ("attraction", "golf")


class FareType(str, Enum):
    ADULT = "ADULT"
    CHILD = "CHILD"
    ROOM = "ROOM"
    PACKAGE = "PACKAGE"


@dataclass(frozen=True)
class FareLine:
    """Một loại giá trong một dịch vụ: đơn giá cho 1 khách, 1 phòng-đêm hoặc 1 gói."""

    fare_type: FareType
    unit_price: int
    count: int
    nights: int | None = None  # chỉ khác None khi fare_type là ROOM

    @property
    def amount(self) -> int:
        return self.unit_price * self.count * (self.nights or 1)

    def to_json(self) -> dict[str, Any]:
        """Dạng lưu trong `booking_items.metadata` và trả trong API (camelCase theo contract `FareLine`)."""
        return {"fareType": self.fare_type.value, "unitPrice": self.unit_price, "count": self.count,
                "nights": self.nights, "amount": self.amount}

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "FareLine":
        return cls(FareType(data["fareType"]), int(data["unitPrice"]), int(data["count"]),
                   int(data["nights"]) if data.get("nights") else None)


def child_unit_price(taxonomy: str, unit_price: int, attributes: Mapping[str, Any]) -> int | None:
    """Giá vé trẻ em hợp lệ của sản phẩm, hoặc None khi trẻ em trả giá người lớn (D2).

    Hợp lệ khi `attributes.childPrice` là số và 0 < childPrice ≤ unitPrice. Giá 0 nghĩa là nguồn không có giá riêng
    (không phải miễn phí); giá cao hơn người lớn nhiều khả năng là lỗi dữ liệu. Cả hai đều bị bỏ qua.
    """
    if taxonomy not in CHILD_PRICED_TAXONOMIES:
        return None
    raw = attributes.get("childPrice")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    price = int(round(raw))
    return price if 0 < price <= unit_price else None


def fare_lines(
    taxonomy: str, unit_price: int, attributes: Mapping[str, Any], *, quantity: int, nights: int | None,
    adults: int, children: int,
) -> list[FareLine]:
    """Các dòng giá của một mục theo bảng §4.3. `quantity` là số phòng (khách sạn), số gói (combo) hoặc số vé."""
    if taxonomy == "hotel":
        return [FareLine(FareType.ROOM, unit_price, quantity, max(1, nights or 1))]
    if taxonomy == "combo":
        return [FareLine(FareType.PACKAGE, unit_price, quantity)]
    lines = [FareLine(FareType.ADULT, unit_price, adults)]
    if children:
        lines.append(FareLine(FareType.CHILD, child_unit_price(taxonomy, unit_price, attributes) or unit_price, children))
    return lines


def lines_total(lines: list[FareLine]) -> int:
    return sum(line.amount for line in lines)
