"""Sở thích khách sạn khi lập lịch (FR-AGT-06, chốt 2026-10-10): **ưu tiên, không bắt buộc**. Hàm thuần.

Người dùng chọn trong ô sở thích của form hoặc nói trong câu ("ưu tiên khách sạn có hồ bơi, phù hợp trẻ nhỏ"). Sở thích
nằm trong `intent.interests` dưới dạng nhãn, không nằm trong `constraints.hotel_attributes`: ràng buộc đó là bộ lọc bắt
buộc (`application/itinerary/retrieval.py`), mà catalog thật hầu như chỉ ghi tiện ích dạng chuỗi (`attributes.amenities`),
nên một cờ `pool = true` bắt buộc sẽ loại gần hết khách sạn.

Sở thích được dùng hai chỗ: thêm cụm vào câu tìm khách sạn (`search_hints`), và lọc mềm ứng viên (`preferred`): chỉ giữ
khách sạn có ghi nhận tiện ích khi còn đủ `MIN_PREFERRED` khách sạn như vậy, thiếu thì giữ nguyên để lịch vẫn có chỗ ở.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..search.amenities import amenity_keys
from .normalization import fold
from .types import Product

#: Lọc mềm chỉ áp khi còn ít nhất chừng này khách sạn hợp sở thích, để luật chọn khách sạn gần, vừa ngân sách
#: (AC-AGT-04) vẫn có lựa chọn.
MIN_PREFERRED = 3


@dataclass(frozen=True)
class Preference:
    key: str
    label: str                       # nhãn hiện trong form, cũng là chữ ghi vào `intent.interests`
    cues: tuple[str, ...]            # cụm đã fold nhận ra sở thích trong câu hoặc trong `interests`
    hint: str                        # cụm thêm vào câu tìm khách sạn (nhãn text embed của catalog)
    amenities: tuple[str, ...] = ()  # khoá `domain/search/amenities.py` khớp chuỗi tiện ích
    attribute: str | None = None     # cờ `attributes.<attribute> = true` nếu catalog có


#: Năm sở thích đã có dữ liệu (đề xuất 2026-10-09, điểm chốt 7). Không có `kidsClub`, `kidsPool`: chưa có dữ liệu.
PREFERENCES: tuple[Preference, ...] = (
    Preference("pool", "Hồ bơi", ("ho boi", "be boi", "pool"), "hồ bơi", ("pool",), "pool"),
    Preference("familyFriendly", "Phù hợp trẻ nhỏ",
               ("phu hop tre nho", "phu hop tre em", "tre nho", "tre em", "gia dinh co tre", "kid friendly"),
               "phù hợp gia đình có trẻ nhỏ", ("familyRoom", "kidsClub"), "familyFriendly"),
    Preference("seaView", "View biển", ("view bien", "huong bien", "nhin ra bien", "sea view", "ocean view"),
               "hướng biển", ("seaView",), "oceanView"),
    # Dữ liệu chỉ nói có bữa sáng, không nói miễn phí (`amenities.py`), nên nhãn không hứa "miễn phí".
    Preference("breakfast", "Có bữa sáng", ("bua sang", "an sang", "breakfast"), "bữa sáng", ("breakfast",)),
    Preference("spa", "Spa", ("spa", "massage", "mat xa"), "spa và massage", ("spa",), "spa"),
)
_BY_KEY = {item.key: item for item in PREFERENCES}


def labels() -> list[str]:
    return [item.label for item in PREFERENCES]


def _matches(text: str, item: Preference) -> bool:
    padded = f" {fold(text)} "
    return any(f" {cue} " in padded for cue in item.cues)


def from_interests(interests: Iterable[str] | None) -> list[Preference]:
    """Sở thích khách sạn có trong `intent.interests`; sở thích khác (biển, ẩm thực) thuộc điểm tham quan, bỏ qua."""
    found = []
    for item in PREFERENCES:
        if any(_matches(value, item) for value in interests or [] if isinstance(value, str)):
            found.append(item)
    return found


def is_preference(value: str) -> bool:
    """`interests` này là sở thích khách sạn (không đưa vào câu tìm điểm tham quan)."""
    return any(_matches(value, item) for item in PREFERENCES)


def stated_preferences(text: str | None) -> list[Preference]:
    """Sở thích người dùng nói rõ là ưu tiên ("ưu tiên khách sạn có hồ bơi", "nếu được thì có spa"), đọc bằng luật.

    Chỉ đọc phần sau từ ưu tiên, để "không cần hồ bơi" hay "hồ bơi thì khỏi" không thành sở thích.
    """
    folded = f" {fold(text)} "
    for cue in (" uu tien ", " neu duoc ", " thich co ", " muon co "):
        if cue in folded:
            tail = folded.split(cue, 1)[1]
            return [item for item in PREFERENCES if any(f" {c} " in f" {tail} " for c in item.cues)]
    return []


def satisfies(product: Product, item: Preference) -> bool:
    """Catalog ghi nhận khách sạn có tiện ích này: cờ thuộc tính, hoặc chuỗi tiện ích khớp từ vựng của Search."""
    attributes = product.get("attributes") or {}
    if item.attribute and attributes.get(item.attribute) is True:
        return True
    strings = attributes.get("amenities")
    if not isinstance(strings, list):
        return False
    return bool(set(item.amenities) & amenity_keys(value for value in strings if isinstance(value, str)))


def preferred(hotels: list[Product], wanted: list[Preference], minimum: int = MIN_PREFERRED) -> list[Product]:
    """Khách sạn hợp sở thích nhất còn đủ `minimum` chỗ: hợp mọi sở thích, không đủ thì hợp ít nhất một, vẫn không đủ
    thì giữ nguyên danh sách (ưu tiên, không loại hết)."""
    if not wanted:
        return hotels
    every = [hotel for hotel in hotels if all(satisfies(hotel, item) for item in wanted)]
    if len(every) >= minimum:
        return every
    some = [hotel for hotel in hotels if any(satisfies(hotel, item) for item in wanted)]
    return some if len(some) >= minimum else hotels


def hints(wanted: list[Preference]) -> list[str]:
    return [item.hint for item in wanted]


def by_key(key: str) -> Preference | None:
    return _BY_KEY.get(key)
