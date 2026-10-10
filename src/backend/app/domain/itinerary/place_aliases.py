"""Tên dân gian của điểm tham quan nổi tiếng → tên trong catalog (chat thử 10/10, M03). Hàm thuần.

Người dùng gọi "Lăng Bác", "Hồ Gươm", "văn miếu"; catalog ghi "Lăng Chủ tịch Hồ Chí Minh", "Hồ Hoàn Kiếm", "Văn Miếu –
Quốc Tử Giám". Không có bảng này thì Search bằng nguyên câu ("lăng bác mấy giờ mở cửa vậy") không đưa đúng nơi lên, và
trợ lý tự trả lời giờ mở cửa bằng kiến thức của LLM. Chỉ ghi tên có thật trong catalog; tên catalog đã đủ trong câu thì
không cần ghi ở đây (`exploration.named_in` khớp thẳng).
"""
from __future__ import annotations

import re
from typing import NamedTuple

from .normalization import fold


class Place(NamedTuple):
    #: Tên sản phẩm trong catalog.
    name: str
    #: Điểm đến của sản phẩm (đúng tên điểm đến của catalog).
    destination: str
    #: Câu tìm nơi đó trong điểm đến: tên đã bỏ phần trùng tên thành phố, vì Search hiểu "Hồ Chí Minh" trong "Lăng Chủ tịch
    #: Hồ Chí Minh" là điểm đến TP. Hồ Chí Minh và trả toàn kết quả ở đó (đo 2026-10-11).
    query: str


_LANG = Place("Lăng Chủ tịch Hồ Chí Minh", "Hà Nội", "Lăng Chủ tịch")
_VAN_MIEU = Place("Văn Miếu – Quốc Tử Giám", "Hà Nội", "Văn Miếu Quốc Tử Giám")
_PHO_CO = Place("Khu Phố Cổ Hà Nội", "Hà Nội", "Khu Phố Cổ")
_BUU_DIEN = Place("Bưu điện trung tâm Sài Gòn", "TP. Hồ Chí Minh", "Bưu điện trung tâm")
_BA_NA = Place("Sun World Bà Nà Hills", "Đà Nẵng", "Sun World Bà Nà Hills")
_PONAGAR = Place("Tháp Bà Ponagar", "Nha Trang", "Tháp Bà Ponagar")
_DAI_NOI = Place("Hoàng Thành Huế", "Huế", "Hoàng Thành")

#: Khoá đã `fold` (không dấu, chữ thường) → nơi trong catalog.
PLACE_ALIASES: dict[str, Place] = {
    "lang bac": _LANG, "lang bac ho": _LANG, "lang chu tich": _LANG, "lang ho chu tich": _LANG,
    "ho guom": Place("Hồ Hoàn Kiếm", "Hà Nội", "Hồ Hoàn Kiếm"),
    "van mieu": _VAN_MIEU, "quoc tu giam": _VAN_MIEU,
    "pho co ha noi": _PHO_CO, "36 pho phuong": _PHO_CO,
    "nha tho lon": Place("Nhà Thờ Lớn Hà Nội", "Hà Nội", "Nhà Thờ Lớn"),
    "hoang thanh thang long": Place("Hoàng Thành Thăng Long", "Hà Nội", "Hoàng Thành Thăng Long"),
    "cho ben thanh": Place("Chợ Bến Thành", "TP. Hồ Chí Minh", "Chợ Bến Thành"),
    "dinh doc lap": Place("Dinh Độc Lập", "TP. Hồ Chí Minh", "Dinh Độc Lập"),
    "buu dien thanh pho": _BUU_DIEN, "buu dien sai gon": _BUU_DIEN,
    "ba na": _BA_NA, "ba na hills": _BA_NA,
    "thap ba": _PONAGAR, "ponagar": _PONAGAR,
    "dai noi": _DAI_NOI, "dai noi hue": _DAI_NOI,
}

_SPACES = re.compile(r"\s+")


def _folded(text: str) -> str:
    return f" {_SPACES.sub(' ', fold(text or ''))} "


def place_of(text: str) -> Place | None:
    """Nơi nổi tiếng mà câu gọi bằng tên dân gian; nhiều tên thì lấy cách gọi dài nhất ("lăng bác hồ" thắng "lăng bác")."""
    padded = _folded(text)
    found = [alias for alias in PLACE_ALIASES if f" {alias} " in padded]
    return PLACE_ALIASES[max(found, key=len)] if found else None


def place_named(text: str) -> str | None:
    """Tên catalog của nơi câu gọi bằng tên dân gian ("lăng bác" → "Lăng Chủ tịch Hồ Chí Minh")."""
    place = place_of(text)
    return place.name if place else None


def with_catalog_names(text: str) -> str:
    """Câu kèm thêm tên catalog của nơi được gọi bằng tên dân gian, để so tên (`named_in`) khớp được."""
    name = place_named(text)
    return f"{text} {name}" if name else text
