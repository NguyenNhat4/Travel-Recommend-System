"""Khoảng cách giữa các sản phẩm của lịch trình (AC-AGT-04, chốt 2026-10-07).

Khoảng cách là đường chim bay giữa hai toạ độ catalog (`attributes.latitude`/`longitude`). Nó đủ để so điểm nào gần hơn,
nhưng không phải quãng đường đi thật, nên lịch trình không hiện số km.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
import math

from .types import Product

Point = tuple[float, float]

EARTH_RADIUS_KM = 6371.0
# Hai lựa chọn chênh nhau dưới mức này coi như gần ngang nhau, khi đó giá quyết định. Không có mức này thì khoảng cách
# (số thực) gần như không bao giờ hoà và giá không bao giờ được dùng tới.
DISTANCE_BAND_KM = 2.0
# Toạ độ tâm thành phố: tour có đón khách, xe đưa đón... được nguồn gán toạ độ trung tâm. Nhận ra bằng toạ độ làm tròn
# (từ 4 chữ số thập phân trở xuống) mà nhiều sản phẩm cùng điểm đến dùng chung. Staging 07/10/2026: Huế 64/80, Vũng Tàu
# 48/48 điểm tham quan. Toạ độ thật của một khu vui chơi (VinWonders, 6 chữ số) dùng chung bởi nhiều vé thì vẫn giữ.
CITY_CENTRE_MAX_DECIMALS = 4
CITY_CENTRE_MIN_SHARED = 5


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def coords(product: Product) -> Point | None:
    """Toạ độ catalog của sản phẩm; None khi thiếu, không phải số hoặc ngoài phạm vi."""
    attributes = product.get("attributes") or {}
    lat, lng = _number(attributes.get("latitude")), _number(attributes.get("longitude"))
    if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


def _decimals(value: float) -> int:
    text = repr(value)
    return len(text.split(".")[1]) if "." in text and "e" not in text else 0


def located(products: Iterable[Product]) -> dict[str, Point]:
    """productId → toạ độ, chỉ cho sản phẩm rõ vị trí: bỏ sản phẩm thiếu toạ độ và toạ độ tâm thành phố.

    Số sản phẩm dùng chung một toạ độ được đếm trong các sản phẩm truyền vào (ứng viên của lượt), theo điểm đến.
    """
    points = {product["productId"]: (product.get("destination"), point)
              for product in products if (point := coords(product)) is not None}
    shared = Counter(points.values())

    def city_centre(key) -> bool:
        _, (lat, lng) = key
        return (max(_decimals(lat), _decimals(lng)) <= CITY_CENTRE_MAX_DECIMALS
                and shared[key] >= CITY_CENTRE_MIN_SHARED)

    return {product_id: key[1] for product_id, key in points.items() if not city_centre(key)}


def haversine_km(a: Point, b: Point) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def medoid(points: Mapping[str, Point]) -> Point | None:
    """Điểm (trong các điểm đã cho) có tổng khoảng cách tới các điểm còn lại nhỏ nhất; hoà thì productId nhỏ hơn.

    Dùng làm mốc của chuyến: khác trọng tâm, một điểm ở rất xa không kéo được mốc ra khỏi cụm chính.
    """
    if not points:
        return None
    best = min(points, key=lambda key: (sum(haversine_km(points[key], other) for other in points.values()), key))
    return points[best]


def band(km: float | None) -> float:
    """Mức khoảng cách để so sánh: cùng mức thì coi như gần ngang nhau. Chưa rõ khoảng cách thì xếp sau mọi mức."""
    return math.inf if km is None else float(int(km // DISTANCE_BAND_KM))
