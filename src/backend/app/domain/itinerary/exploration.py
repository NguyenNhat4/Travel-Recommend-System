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
from .geo import coords, haversine_km
from .normalization import fold
from .types import Product

MOST_REVIEWED = "most_reviewed"
TOP_RATED = "top_rated"
CHEAPEST = "cheapest"
FREE_ENTRY = "free_entry"
ALSO_POPULAR = "also_popular"
#: Nơi người dùng nêu tên trong câu hỏi ("Văn Miếu buổi tối có mở không?"): luôn là thẻ đầu tiên.
ASKED = "asked"
#: Gần nơi người dùng hỏi quanh ("gần Văn Miếu có gì nữa?").
NEAR = "near"
#: Người dùng muốn chỗ rẻ: thẻ sau thẻ rẻ nhất, cũng thuộc nhóm giá thấp (`cheapest_cards`).
LOW_PRICE = "low_price"
#: "Gần" tính theo đường chim bay; xa hơn thì không gọi là gần nữa.
NEAR_KM = 3.0

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


def cheapest_cards(products: list[Product], limit: int) -> list[dict]:
    """Người dùng muốn chỗ rẻ ("khách sạn giá rẻ", "rẻ nhất là chỗ nào"): các nơi có giá, rẻ nhất trước; thẻ đầu lý do
    `CHEAPEST`, các thẻ sau `LOW_PRICE`. Mỗi nơi tối đa một thẻ (`distinct_places`)."""
    priced = sorted((product for product in distinct_places(products) if price(product) is not None), key=price)
    return [{"product": product, "reasons": [CHEAPEST if index == 0 else LOW_PRICE]}
            for index, product in enumerate(priced[:limit])]


def has_amenity(product: Product, key: str) -> bool:
    """Catalog ghi nhận có tiện ích này: cờ `attributes.<key> = true`, hoặc một chuỗi trong `attributes.amenities` khớp
    khoá đó theo từ vựng của Search (`domain/search/amenities.py`). Catalog thật hầu như chỉ có dạng chuỗi."""
    attributes = product.get("attributes") or {}
    if attributes.get(key) is True:
        return True
    strings = attributes.get("amenities")
    return isinstance(strings, list) and key in amenity_keys(item for item in strings if isinstance(item, str))


_NAME_CUT = re.compile(r"\s+[-–(|]|\s*\[")


def short_name(product: Product) -> str:
    """Phần đầu của tên, như người dùng hay gọi: "Văn Miếu – Quốc Tử Giám" → "Văn Miếu", "[VinWonders] Vé…" → "Vé…"."""
    name = product.get("name") or ""
    return _NAME_CUT.split(_BRACKET_PREFIX.sub("", name).strip(), maxsplit=1)[0].strip()


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


#: Tên gần đúng: phần tên nơi người dùng hỏi phải có trong tên sản phẩm (tính theo từ, đã `fold`).
MIN_NAME_SHARE = 0.6
MIN_SHARED_WORDS = 2


def closest_matches(products: list[Product], name: str, exclude: Iterable[str] = ()) -> list[Product]:
    """Các sản phẩm có tên gần `name` nhất khi không sản phẩm nào khớp trọn tên (LLM viết "Lăng Bác Hồ", catalog ghi
    "Lăng Chủ tịch Hồ Chí Minh"): ít nhất `MIN_SHARED_WORDS` từ và `MIN_NAME_SHARE` số từ của `name` nằm trong tên sản
    phẩm, cùng tỷ lệ cao nhất; giữ thứ tự Search (liên quan hơn trước). Không sản phẩm nào đủ thì danh sách rỗng."""
    wanted = fold(name).split()
    if len(wanted) < MIN_SHARED_WORDS:
        return []
    excluded = {fold(item) for item in exclude}
    scored = []
    for product in products:
        words = set(fold(product.get("name") or "").split())
        if not words or fold(product.get("name") or "") in excluded:
            continue
        shared = sum(1 for word in wanted if word in words)
        if shared >= MIN_SHARED_WORDS and shared / len(wanted) >= MIN_NAME_SHARE:
            scored.append((shared / len(wanted), product))
    best = max((share for share, _ in scored), default=None)
    return [product for share, product in scored if share == best]


def closest_named(products: list[Product], name: str, exclude: Iterable[str] = ()) -> Product | None:
    """Sản phẩm gần tên `name` nhất (`closest_matches`); các sản phẩm gần nhất nằm ở hai thành phố khác nhau ("phố cổ":
    Hà Nội, Hội An) thì None, để hỏi lại thay vì tự chọn."""
    matches = closest_matches(products, name, exclude)
    return matches[0] if matches and len({fold(item.get("destination")) for item in matches}) == 1 else None


def near_cards(products: list[Product], anchor: Product, limit: int) -> list[dict]:
    """Tối đa `limit` thẻ gần `anchor` nhất (trong `NEAR_KM`), không tính chính nó và nơi trùng nó; thiếu toạ độ thì
    rỗng (không đoán là gần)."""
    origin = coords(anchor)
    if origin is None:
        return []
    anchor_key = _group(anchor)
    scored = []
    for product in distinct_places(products):
        point = coords(product)
        if point is None or product["productId"] == anchor["productId"] or _same_place(_group(product), anchor_key):
            continue
        km = haversine_km(origin, point)
        if km <= NEAR_KM:
            scored.append((km, product))
    scored.sort(key=lambda item: item[0])
    return [{"product": product, "reasons": [NEAR]} for _, product in scored[:limit]]


def within_km(products: list[Product], anchor: Product, km: float) -> list[Product]:
    """Sản phẩm có toạ độ trong bán kính `km` quanh `anchor`, gần trước; anchor thiếu toạ độ thì rỗng."""
    origin = coords(anchor)
    if origin is None:
        return []
    scored = [(haversine_km(origin, point), product) for product in products if (point := coords(product)) is not None]
    return [product for distance, product in sorted(scored, key=lambda item: item[0]) if distance <= km]


def with_amenity(products: list[Product], key: str) -> list[Product]:
    return [item for item in products if has_amenity(item, key)]
