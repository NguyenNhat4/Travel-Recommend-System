"""Mã sản phẩm (ref) của một lượt assistant v2.

Ref lấy từ lịch sử hội thoại chỉ cho biết productId. Muốn nói giá, giờ hay hiện thẻ của sản phẩm đó thì phải tra lại
trong lượt (NFR-REL-01, PRD architecture §3): chỉ sản phẩm tra được trong lượt mới có dữ kiện. Registry sống trong
một lượt, nên con trỏ trang cũng chỉ dùng được trong chính lượt đó.
"""
from __future__ import annotations

import json
import secrets
from copy import deepcopy
from typing import Any

from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.domain.itinerary.draft_validation import (
    available_on,
    entry_mode,
    suitable_slots,
)

#: Thuộc tính đưa cho orc so sánh, chọn và lập lịch; còn lại (ảnh, lịch trống chi tiết…) chỉ giữ ở server.
VIEW_ATTRIBUTES = (
    "address", "durationMinutes", "openingHours", "ticketed", "pool", "kidsPool", "kidsClub", "spa", "oceanView",
    "familyFriendly", "privateBeach", "nearBeach", "breakfastIncluded", "priceAdults", "maxOccupancy",
    "amenities", "audience", "reviewScore", "parentProductId", "originCity", "destinationCity", "departureDate",
    "departureAt", "arrivalAt", "departureTimeLocal", "arrivalTimeLocal", "airline", "flightNo", "flightNumber",
    "cabinClass", "simulated", "latitude", "longitude", "availability",
)
DESCRIPTION_CHARS = 400


class ProductRegistry:
    def __init__(self, known: dict[str, str] | None = None):
        self._ids = dict(known or {})                     # ref → productId, cả lịch sử
        self._refs = {pid: ref for ref, pid in self._ids.items()}
        self._products: dict[str, dict[str, Any]] = {}    # ref → sản phẩm tra trong lượt
        self._cursors: dict[str, tuple[str, int]] = {}
        self._next = max((int(ref[1:]) for ref in self._ids if ref[1:].isdigit()), default=0) + 1

    def add(self, product: dict[str, Any]) -> str:
        """Ghi sản phẩm vừa tra; cùng productId (từ nguồn nào) luôn cùng một ref."""
        ref = self._refs.get(product["productId"])
        if ref is None:
            ref = f"p{self._next}"
            self._next += 1
            self._ids[ref] = product["productId"]
            self._refs[product["productId"]] = ref
        self._products[ref] = deepcopy(product)
        return ref

    def identify(self, ref: str) -> str:
        if ref not in self._ids:
            raise ToolError("UNKNOWN_REF")
        return self._ids[ref]

    def ref_of(self, product_id: str) -> str | None:
        return self._refs.get(product_id)

    def product(self, ref: str) -> dict[str, Any]:
        """Sản phẩm tra được trong lượt. Ref chỉ có trong lịch sử là STALE_REF: phải tra lại trước khi dùng."""
        if ref not in self._products:
            raise ToolError("STALE_REF" if ref in self._ids else "UNKNOWN_REF")
        return deepcopy(self._products[ref])

    def fetched(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self._products)

    def known(self) -> dict[str, str]:
        """ref → productId để lưu cho lượt sau; không mang giá hay tình trạng còn chỗ."""
        return dict(self._ids)

    def fact(self, ref: str, field: str) -> Any:
        """Giá trị một field của sản phẩm tra trong lượt (cấp gốc hoặc attributes); None khi không có."""
        product = self._products.get(ref) or {}
        value = product.get(field, (product.get("attributes") or {}).get(field))
        return value if isinstance(value, (str, int, float, bool)) else None

    def view(self, ref: str, *, dates: list[str] | None = None) -> dict[str, Any]:
        """Bản rút gọn cho orc: field không có giá trị bị bỏ (vắng = chưa biết)."""
        product = self._products[ref]
        attributes = product.get("attributes") or {}
        view = {key: product.get(key) for key in ("name", "taxonomy", "destination", "unitPrice", "priceUnit",
                                                   "available", "availableFrom", "availableTo", "rating", "reviewCount", "starRating")}
        if product["taxonomy"] in ("attraction", "golf"):
            view["suitable_slots"] = suitable_slots(product)
            view["entryPolicy"] = entry_mode(product)
        if dates:
            from datetime import date
            view["availability_by_date"] = {day: available_on(product, date.fromisoformat(day)) for day in dates}
        view["description"] = (product.get("description") or "")[:DESCRIPTION_CHARS]
        view.update({key: attributes.get(key) for key in VIEW_ATTRIBUTES})
        return {key: value for key, value in view.items() if value not in (None, "")}

    def issue_cursor(self, arguments: dict[str, Any], offset: int) -> str:
        cursor = secrets.token_urlsafe(12)
        self._cursors[cursor] = (_fingerprint(arguments), offset)
        return cursor

    def cursor_offset(self, cursor: str, arguments: dict[str, Any]) -> int:
        """Vị trí trang tiếp; con trỏ lạ hoặc đã đổi tham số thì CURSOR_MISMATCH (đổi điều kiện là truy vấn mới)."""
        found = self._cursors.get(cursor)
        if found is None:
            raise ToolError("CURSOR_MISMATCH", reason="unknown_cursor")
        current = _fingerprint(arguments)
        if found[0] != current:
            previous, next_args = json.loads(found[0]), json.loads(current)
            changed = sorted(key for key in previous.keys() | next_args.keys() if previous.get(key) != next_args.get(key))
            raise ToolError("CURSOR_MISMATCH", reason="parameters_changed:" + ",".join(changed))
        return found[1]


def _fingerprint(arguments: dict[str, Any]) -> str:
    """Điều kiện của truy vấn; cỡ trang và mã loại trừ đổi được giữa các trang mà vẫn là cùng truy vấn."""
    return json.dumps({key: value for key, value in arguments.items() if key not in ("cursor", "limit", "exclude_refs", "why")},
                      sort_keys=True, ensure_ascii=False)
