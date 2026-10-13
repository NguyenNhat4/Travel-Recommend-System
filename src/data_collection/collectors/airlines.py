"""Logo hãng bay cho ảnh vé máy bay (`imageUrl` / `image_url`).

Ảnh là logo trên CDN của Trip.com, lấy từ trang vé vn.trip.com (vd. /flights/ho-chi-minh-city-to-phu-quoc-island/airfares-sgn-pqc/,
12/10/2026): `https://pic.tripcdn.com/airline_logo/3x/<mã IATA thường>.png`. Tên hãng theo đúng `attributes.airline` của catalog.
Vé lấy logo hãng của chính vé; tuyến bay dùng ảnh thành phố đến (đặt trên DB), không dùng logo.
"""

from __future__ import annotations

AIRLINE_CODES: dict[str, str] = {
    "VietJet Air": "vj",
    "Vietnam Airlines": "vn",
    "Sun PhuQuoc Airways": "9g",
    "Vietravel Airlines": "vu",
    "Bamboo Airways": "qh",
}


def airline_logo(airline: str | None) -> str | None:
    """URL logo của hãng, hoặc None khi chưa biết hãng."""
    code = AIRLINE_CODES.get((airline or "").strip())
    return f"https://pic.tripcdn.com/airline_logo/3x/{code}.png" if code else None
