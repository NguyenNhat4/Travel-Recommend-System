"""Chọn thẻ cho lượt khám phá trước khi lập lịch (FR-AGT-06). Hàm thuần, không gọi model.

Mỗi thẻ mang một lý do khác nhau ("nhiều người đánh giá nhất", "rẻ nhất"...). Lý do luôn đúng trên **toàn bộ** kết quả
Search của lượt đó, không trên phần đã cắt: sản phẩm tốt nhất theo một lý do mà đã được chọn vì lý do khác thì lý do đó
gộp vào thẻ cũ, không gán cho sản phẩm hạng hai. Kịch bản bản 4 từng nói sai "rẻ nhất" vì bỏ sót một hostel có hồ bơi.

LLM chỉ viết câu dẫn từ lý do và số liệu ở đây; số trong câu do code điền (`agents/steps/exploration.py`).
"""

from __future__ import annotations

from collections.abc import Iterable
import re

from ..search.amenities import amenity_keys
from .normalization import fold
from .types import Product

MOST_REVIEWED = "most_reviewed"
TOP_RATED = "top_rated"
CHEAPEST = "cheapest"
FREE_ENTRY = "free_entry"
ALSO_POPULAR = "also_popular"
#: Nơi người dùng nêu tên trong câu hỏi ("Văn Miếu buổi tối có mở không?"): luôn là thẻ đầu tiên.
ASKED = "asked"

#: Thứ tự lý do theo loại: điểm tham quan ưu tiên nơi nhiều người đến, khách sạn ưu tiên giá.
REASON_ORDER = {
    "hotel": (CHEAPEST, TOP_RATED, MOST_REVIEWED),
    "attraction": (MOST_REVIEWED, TOP_RATED, FREE_ENTRY),
}
DEFAULT_REASON_ORDER = (MOST_REVIEWED, TOP_RATED, CHEAPEST)
#: "Điểm cao nhất" chỉ tính sản phẩm có ít nhất chừng này lượt đánh giá; 9,9 điểm với 3 lượt không đáng tin bằng 9,4 với
#: 3.500 lượt. Không sản phẩm nào đạt thì bỏ lý do này.
MIN_REVIEWS_FOR_TOP_RATED = 20
_BRACKET_PREFIX = re.compile(r"^\s*\[([^\]]+)\]")


def _reviews(product: Product) -> int:
    value = product.get("reviewCount")
    return value if isinstance(value, int) and value > 0 else 0


def _rating(product: Product) -> float | None:
    value = product.get("rating")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def price(product: Product) -> int | None:
    """Giá niêm yết dương; 0 hoặc thiếu thì None (không đem so "rẻ nhất")."""
    value = product.get("unitPrice")
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else None


def free_entry(product: Product) -> bool:
    """Tham quan tự do: catalog ghi rõ không cần vé, hoặc giá bằng 0."""
    attributes = product.get("attributes") or {}
    return attributes.get("ticketed") is False or product.get("unitPrice") == 0


def _group(product: Product) -> str:
    """Khoá gộp các sản phẩm của cùng một nơi: khách sạn cha của một hạng phòng (`parentProductId`), phần trong `[...]`
    đầu tên ("[VinWonders Phú Quốc] Vé ..."), hoặc phần trước " - " ("VinHolidays Fiesta Phú Quốc - Phòng Tiêu Chuẩn")."""
    attributes = product.get("attributes") or {}
    parent = product.get("parentProductId") or attributes.get("parentProductId")
    if parent:
        return f"parent:{parent}"
    name = product.get("name") or ""
    match = _BRACKET_PREFIX.match(name)
    return fold(match.group(1) if match else name.split(" - ")[0])


def _same_place(key: str, other: str) -> bool:
    """Cùng khoá, hoặc tên ngắn (từ hai từ) nằm trọn trong tên dài: "hòn Thơm" và "Cáp Treo Hòn Thơm" (LLM thật 10/10)."""
    if key == other:
        return True
    short, long_ = sorted((key, other), key=len)
    return len(short.split()) >= 2 and f" {short} " in f" {long_} "


def distinct_places(products: Iterable[Product]) -> list[Product]:
    """Giữ sản phẩm đầu tiên của mỗi nơi; vé khác loại của cùng một nơi không chiếm thêm thẻ."""
    seen: list[str] = []
    kept = []
    for product in products:
        key = _group(product)
        if key and not any(_same_place(key, other) for other in seen):
            seen.append(key)
            kept.append(product)
    return kept


def _best(products: list[Product], reason: str) -> Product | None:
    """Sản phẩm đứng đầu theo một lý do trên cả danh sách; hoà thì theo thứ tự Search (giữ nguyên thứ tự gốc)."""
    if reason == MOST_REVIEWED:
        pool = [item for item in products if _reviews(item)]
        return max(pool, key=_reviews) if pool else None
    if reason == TOP_RATED:
        pool = [item for item in products
                if _rating(item) is not None and _reviews(item) >= MIN_REVIEWS_FOR_TOP_RATED]
        return max(pool, key=lambda item: (_rating(item), _reviews(item))) if pool else None
    if reason == CHEAPEST:
        pool = [item for item in products if price(item) is not None]
        return min(pool, key=price) if pool else None
    if reason == FREE_ENTRY:
        pool = [item for item in products if free_entry(item)]
        return max(pool, key=_reviews) if pool else None
    return None


def pick_cards(products: list[Product], limit: int, taxonomy: str | None = None) -> list[dict]:
    """Tối đa `limit` thẻ `{product, reasons}`, mỗi thẻ ít nhất một lý do và không hai thẻ chung một lý do.

    Lý do được xét theo `REASON_ORDER` của loại; còn chỗ thì thêm sản phẩm nhiều đánh giá kế tiếp với lý do
    `ALSO_POPULAR` (không tuyên bố "nhất" gì). Mỗi nơi tối đa một thẻ (`distinct_places`).
    """
    places = distinct_places(products)
    cards: list[dict] = []
    for reason in REASON_ORDER.get(taxonomy or "", DEFAULT_REASON_ORDER):
        best = _best(places, reason)
        if best is None:
            continue
        existing = next((card for card in cards if card["product"]["productId"] == best["productId"]), None)
        if existing is not None:
            existing["reasons"].append(reason)
        elif len(cards) < limit:
            cards.append({"product": best, "reasons": [reason]})
    chosen = {card["product"]["productId"] for card in cards}
    for product in sorted(places, key=_reviews, reverse=True):
        if len(cards) >= limit:
            break
        if product["productId"] not in chosen:
            cards.append({"product": product, "reasons": [ALSO_POPULAR]})
            chosen.add(product["productId"])
    return cards


def has_amenity(product: Product, key: str) -> bool:
    """Catalog ghi nhận có tiện ích này: cờ `attributes.<key> = true`, hoặc một chuỗi trong `attributes.amenities` khớp
    khoá đó theo từ vựng của Search (`domain/search/amenities.py`). Catalog thật hầu như chỉ có dạng chuỗi."""
    attributes = product.get("attributes") or {}
    if attributes.get(key) is True:
        return True
    strings = attributes.get("amenities")
    return isinstance(strings, list) and key in amenity_keys(item for item in strings if isinstance(item, str))


_NAME_CUT = re.compile(r"\s+[-–(|]|\s*\[")


def named_in(products: list[Product], text: str, exclude: Iterable[str] = ()) -> Product | None:
    """Sản phẩm mà câu hỏi nêu tên: phần đầu của tên (trước " – ", " - ", "(") nằm trọn trong câu, tối thiểu hai từ; nhiều
    sản phẩm khớp thì lấy tên dài nhất ("Văn Miếu – Quốc Tử Giám" khớp "Văn Miếu buổi tối có mở không?")."""
    padded = f" {fold(text)} "
    excluded = {fold(name) for name in exclude}  # tên điểm đến: "Hà Nội có gì" không phải hỏi về sản phẩm tên "Hà Nội"
    found = []
    for product in products:
        name = product.get("name") or ""
        core = fold(_NAME_CUT.split(_BRACKET_PREFIX.sub("", name).strip(), maxsplit=1)[0])
        if len(core.split()) >= 2 and core not in excluded and f" {core} " in padded:
            found.append((len(core), product))
    return max(found, key=lambda item: item[0])[1] if found else None


def with_amenity(products: list[Product], key: str) -> list[Product]:
    return [item for item in products if has_amenity(item, key)]
