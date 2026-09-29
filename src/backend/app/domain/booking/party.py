"""Đoàn khách: loại khách, tuổi và loại giá theo ngày sử dụng (spec checkout-nhieu-buoc-hanh-khach.md §4.1, §4.2).

- Người lớn: từ 12 tuổi. Trẻ em: dưới 12 tuổi tại ngày sử dụng sớm nhất của đơn, bắt buộc có ngày sinh.
- Loại giá của trẻ em ở từng dịch vụ tính theo tuổi tại `usingDate` của dịch vụ đó.
- Em bé: trẻ em dưới 2 tuổi tại ngày bay; chỉ dùng cho luật chuyến bay.
- Tuổi là số năm tròn: người sinh 29/02 coi sinh nhật ở năm không nhuận là 01/03. Web (`checkoutRules.ts`) dùng cùng quy tắc.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from .fares import FareType

ADULT_MIN_AGE = 12
INFANT_MAX_AGE = 2  # dưới 2 tuổi
MAX_PARTY = 9


class TravelerType(str, Enum):
    """Giá trị viết thường vì đó là giá trị trong database; API trả bản viết HOA."""

    ADULT = "adult"
    CHILD = "child"


@dataclass(frozen=True)
class Traveler:
    """Một người trong đoàn. `ref` là mã tạm do Web sinh, duy nhất trong một đơn; họ tên đã chuẩn hoá khoảng trắng."""

    ref: str
    type: TravelerType
    surname: str
    given_names: str
    birth_date: date | None = None  # chỉ trẻ em; ngày sinh không bao giờ ra khỏi Backend

    @property
    def full_name(self) -> str:
        return f"{self.surname} {self.given_names}".strip()


@dataclass(frozen=True)
class Guests:
    """Số người lớn và trẻ em của một mục giỏ (theo loại giá tại ngày sử dụng). Không chứa tên."""

    adults: int
    children: int

    @property
    def total(self) -> int:
        return self.adults + self.children


@dataclass(frozen=True)
class RoomAllocation:
    """Ai ở một phòng của mục khách sạn và ai là người lớn đại diện nhận phòng."""

    traveler_refs: tuple[str, ...]
    lead_traveler_ref: str


def _birthday_in(birth: date, year: int) -> date:
    try:
        return birth.replace(year=year)
    except ValueError:  # 29/02 ở năm không nhuận
        return date(year, 3, 1)


def age_on(birth: date, day: date) -> int:
    """Số năm tròn của người sinh ngày `birth` vào ngày `day`."""
    years = day.year - birth.year
    return years - 1 if day < _birthday_in(birth, day.year) else years


def adult_from(birth: date) -> date:
    """Ngày trẻ tròn 12 tuổi và bắt đầu tính giá người lớn."""
    return _birthday_in(birth, birth.year + ADULT_MIN_AGE)


def fare_type_on(traveler: Traveler, day: date) -> FareType:
    """Loại giá của một người ở dịch vụ dùng vào ngày `day`. Trẻ em chưa có ngày sinh hợp lệ tính là trẻ em."""
    if traveler.type is TravelerType.ADULT:
        return FareType.ADULT
    if traveler.birth_date is None:
        return FareType.CHILD
    return FareType.ADULT if age_on(traveler.birth_date, day) >= ADULT_MIN_AGE else FareType.CHILD


def is_infant_on(traveler: Traveler, day: date) -> bool:
    return (traveler.type is TravelerType.CHILD and traveler.birth_date is not None
            and age_on(traveler.birth_date, day) < INFANT_MAX_AGE)
