"""Luật ngày của sản phẩm: cửa sổ đặt phòng khách sạn và bộ lọc ngày của /search (FR-SRC-03, FR-CAT-03; đề xuất PRD
`update-archive/2026-10-07-loc-theo-ngay-o-tim-kiem.md`).

Hai việc khác nhau, cùng một nguồn luật ngày:
- **Đặt chỗ** (`domain/booking/pricing.py`): ngày nhận phòng khách sạn từ hôm nay đến hôm nay + 3 tháng, 1–30 đêm. Lịch
  `attributes.availability` KHÔNG chặn đặt chỗ (số `0` có thể chỉ là "nguồn không có giá ngày đó").
- **Tìm kiếm với ngày** (`UnitIndex.mask(stay=…)`): ngoài luật cửa sổ, lịch `0` làm sản phẩm bị loại khỏi kết quả. Khách sạn được
  giữ khi có ít nhất một hạng phòng còn bán thoả đồng thời giá, số khách và ngày (`calendar_open`). Chỉ loại khi BIẾT là kín;
  ngày ngoài khoảng lịch, hạng phòng không có lịch, sản phẩm không có cửa sổ → "không biết" → giữ (spec §2.7 [C2]).

Thuần stdlib: không numpy, không pydantic, không DB.
"""
from __future__ import annotations

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

HOTEL_MAX_ADVANCE_MONTHS = 3
HOTEL_MAX_NIGHTS = 30

#: Lịch của một sản phẩm: (ordinal ngày của ký tự đầu, chuỗi "1"/"0"); ký tự i là ngày `from + i`, `1` mở, `0` kín.
Calendar = tuple[int, str]


def hotel_booking_window(today: date) -> tuple[date, date]:
    """Ngày nhận phòng khách sạn hợp lệ: từ hôm nay đến hôm nay + 3 tháng (cắt về cuối tháng nếu tháng đó ngắn hơn)."""
    month_index = today.month - 1 + HOTEL_MAX_ADVANCE_MONTHS
    year, month = today.year + month_index // 12, month_index % 12 + 1
    return today, date(year, month, min(today.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class StayDates:
    """`travelContext.checkIn` / `checkOut` của request (checkOut không bao gồm: kiểm mọi đêm trong [checkIn, checkOut)).

    `check_out = None`: chỉ có ngày dùng (vé, combo) hoặc khách sạn một đêm. `today`: hôm nay giờ Việt Nam, do nơi gọi truyền."""
    check_in: date
    check_out: date | None
    today: date

    def __post_init__(self) -> None:
        if self.check_out is not None and self.check_out <= self.check_in:
            raise ValueError("check_out phải sau check_in")

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days if self.check_out is not None else 1

    @property
    def start(self) -> int:
        return self.check_in.toordinal()

    @property
    def end(self) -> int:
        """Ordinal ngày đầu tiên SAU kỳ lưu trú (khoảng nửa mở [start, end))."""
        return self.start + self.nights

    def hotel_window_ok(self) -> bool:
        """Luật đặt phòng khách sạn: nhận trong [hôm nay, hôm nay + 3 tháng] và ở 1–30 đêm."""
        window_from, window_to = hotel_booking_window(self.today)
        return window_from <= self.check_in <= window_to and 1 <= self.nights <= HOTEL_MAX_NIGHTS


def parse_calendar(attributes: Mapping[str, Any]) -> Calendar | None:
    """`attributes.availability {from, days, calendar}` → Calendar; thiếu hoặc sai dạng → None ("không biết")."""
    raw = attributes.get("availability")
    if not isinstance(raw, Mapping):
        return None
    bits, start = raw.get("calendar"), raw.get("from")
    if not isinstance(bits, str) or not bits or set(bits) - {"0", "1"} or not isinstance(start, str):
        return None
    try:
        return date.fromisoformat(start).toordinal(), bits
    except ValueError:
        return None


def calendar_open(cal: Calendar, start: int, end: int) -> bool:
    """True khi không đêm nào trong [start, end) được biết là kín; đêm ngoài khoảng lịch tính là chưa biết (mở)."""
    first, bits = cal
    for day in range(start, end):
        k = day - first
        if 0 <= k < len(bits) and bits[k] == "0":
            return False
    return True


def as_ordinal(value: date | None) -> float:
    """Ordinal của ngày, NaN khi thiếu: dùng cho mảng numpy của `UnitAttributes` (miền này không import numpy)."""
    return float("nan") if value is None else float(value.toordinal())

