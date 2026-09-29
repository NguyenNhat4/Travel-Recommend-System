"""Catalog giả lập (spec P1.5) — mục đích DUY NHẤT là chạy thử khung. Không dùng số đo từ đây để kết luận.

Sinh bản ghi đúng dạng `products.jsonl` (kể cả phòng/chuyến con) để đi qua CÙNG pipeline với `--source jsonl`.
Tỷ lệ theo bản crawl 16/09 (spec P1.5): property 50%, attraction 36%, combo 8%, route 5%, golf 1%; 12 điểm đến Zipf s=1,1;
toạ độ tâm + nhiễu σ=3 km; 35% property không có amenity; 34% attraction là điểm công cộng (giá null); ~49% property không có sao.
"""
from __future__ import annotations

import math
import uuid

import numpy as np

from .amenities import load_seed

VARIANT_SHARES = {"hotel_property": 0.50, "attraction": 0.36, "combo": 0.08, "flight_route": 0.05, "golf": 0.01}
ZIPF_S = 1.1
GEO_SIGMA_M = 3000.0
PROPERTY_NO_AMENITY = 0.35
ATTRACTION_PUBLIC = 0.34
STAR_NULL = 0.49
# (tên, tỉnh, lat, lon) — tâm điểm đến xấp xỉ
DESTINATIONS = [
    ("Nha Trang", "Khánh Hòa", 12.2388, 109.1967), ("Phú Quốc", "Kiên Giang", 10.2270, 103.9637),
    ("Đà Nẵng", "Đà Nẵng", 16.0544, 108.2022), ("Hội An", "Quảng Nam", 15.8801, 108.3380),
    ("Hạ Long", "Quảng Ninh", 20.9510, 107.0800), ("Hà Nội", "Hà Nội", 21.0285, 105.8542),
    ("TP. Hồ Chí Minh", "TP. Hồ Chí Minh", 10.7769, 106.7009), ("Sa Pa", "Lào Cai", 22.3364, 103.8438),
    ("Đà Lạt", "Lâm Đồng", 11.9404, 108.4583), ("Quy Nhơn", "Bình Định", 13.7765, 109.2237),
    ("Cửa Hội", "Nghệ An", 18.7560, 105.7340), ("Tây Ninh", "Tây Ninh", 11.3100, 106.0983),
]
TAXONOMY = {"hotel_property": "hotel", "attraction": "attraction", "combo": "combo", "flight_route": "flight", "golf": "golf"}
# giá lognormal theo taxonomy: (median VND, sigma)
PRICE = {"hotel": (1_500_000, 0.6), "attraction": (400_000, 0.7), "combo": (3_500_000, 0.5), "flight": (1_400_000, 0.4),
         "golf": (2_500_000, 0.3)}
# vài chuỗi amenity không có trong seed → đi đường raw (có tần suất đủ để thành raw:<slug>)
RAW_AMENITIES = ["TV màn hình phẳng", "Minibar", "Ban công", "Két an toàn", "Ấm đun nước điện", "Bàn làm việc"]
PROPERTY_TYPES = [None, None, None, "khách sạn", "resort", "khu nghỉ dưỡng", "homestay", "căn hộ"]
ROOM_NAMES = ["Deluxe", "Superior", "Standard", "Suite", "Family", "Villa hướng biển", "Bungalow"]
AIRLINES = ["VietJet Air", "Vietnam Airlines", "Bamboo Airways", "Vietravel Airlines", "Sun PhuQuoc Airways"]
AUDIENCE = ["gia đình", "trẻ em", "cặp đôi", "nhóm bạn"]


def _zipf_weights(n: int, s: float) -> np.ndarray:
    w = 1.0 / np.arange(1, n + 1) ** s
    return w / w.sum()


def _jitter(rng: np.random.Generator, lat: float, lon: float, sigma_m: float) -> tuple[float, float]:
    dy, dx = rng.normal(0.0, sigma_m, 2)
    return lat + dy / 111_320.0, lon + dx / (111_320.0 * math.cos(math.radians(lat)))


def _pid(i: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vbench:fake:{i}"))


def generate_products(n: int, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed + 101)
    seed_labels = [s.label for s in sorted(load_seed(), key=lambda x: x.key)]
    amen_w = _zipf_weights(len(seed_labels), ZIPF_S)
    rng.shuffle(amen_w)            # không để thứ tự alphabet quyết định amenity phổ biến
    dest_w = _zipf_weights(len(DESTINATIONS), ZIPF_S)

    counts = {v: int(round(n * s)) for v, s in VARIANT_SHARES.items()}
    counts["hotel_property"] += n - sum(counts.values())
    variants = [v for v, c in counts.items() for _ in range(c)]
    rng.shuffle(variants)

    out: list[dict] = []
    for i, variant in enumerate(variants):
        d_name, prov, lat0, lon0 = DESTINATIONS[rng.choice(len(DESTINATIONS), p=dest_w)]
        lat, lon = _jitter(rng, lat0, lon0, GEO_SIGMA_M)
        tax = TAXONOMY[variant]
        med, sig = PRICE[tax]
        price: float | None = float(round(med * math.exp(rng.normal(0, sig)), -3))
        attrs: dict = {"province": prov, "latitude": lat, "longitude": lon}
        name = f"{variant} {i} {d_name}"
        desc = f"Sản phẩm thử nghiệm số {i} tại {d_name}, {prov}. Văn bản giả lập để chạy khung benchmark."
        available = bool(rng.random() < 0.95)
        pid = _pid(str(i))
        children: list[dict] = []
        if variant == "hotel_property":
            attrs["level"] = "property"
            ptype = PROPERTY_TYPES[rng.integers(len(PROPERTY_TYPES))]
            if ptype:
                attrs["propertyType"] = ptype
            name = f"{(ptype or 'Khách sạn').title()} Thử {i} {d_name}"
            if rng.random() >= STAR_NULL:
                attrs["starRating"] = float(rng.integers(3, 6))
            has_amenity = rng.random() >= PROPERTY_NO_AMENITY   # không amenity = cả property lẫn phòng con (coverage 65%)
            if has_amenity:
                k = int(rng.integers(2, 10))
                am = list(rng.choice(seed_labels, size=min(k, len(seed_labels)), replace=False, p=amen_w))
                am += [r for r in RAW_AMENITIES if rng.random() < 0.3]
                attrs["amenities"] = am
            for r in range(int(rng.integers(0, 4))):
                rattrs = {"level": "room", "parentProductId": pid, "roomName": ROOM_NAMES[rng.integers(len(ROOM_NAMES))],
                          "latitude": lat, "longitude": lon, "province": prov}
                if has_amenity and rng.random() < 0.5:
                    rattrs["amenities"] = list(rng.choice(seed_labels, size=2, replace=False, p=amen_w))
                rprice = float(round(med * math.exp(rng.normal(0, sig)), -3))
                children.append(_rec(_pid(f"{i}-r{r}"), f"{name} - {rattrs['roomName']}", "hotel", d_name, desc, rattrs, rprice, True))
            price = None if children else price   # property có phòng: giá lấy từ phòng con
        elif variant == "flight_route":
            attrs["level"] = "route"
            attrs["originCity"] = "Hà Nội" if d_name != "Hà Nội" else "TP. Hồ Chí Minh"
            attrs["destinationCity"] = d_name
            name = f"Vé máy bay {attrs['originCity']} - {d_name}"
            for r in range(int(rng.integers(1, 4))):
                fattrs = {"level": "flight", "parentProductId": pid, "airline": AIRLINES[rng.integers(len(AIRLINES))],
                          "latitude": lat, "longitude": lon}
                fprice = float(round(med * math.exp(rng.normal(0, sig)), -3))
                children.append(_rec(_pid(f"{i}-f{r}"), name, "flight", d_name, desc, fattrs, fprice, True))
            price = None
        elif variant == "attraction":
            if rng.random() < ATTRACTION_PUBLIC:
                attrs["ticketed"] = False
                price = None
            if rng.random() < 0.3:
                attrs["audience"] = list(rng.choice(AUDIENCE, size=2, replace=False))
            name = f"Điểm tham quan {i} {d_name}"
        elif variant == "combo":
            name = f"Combo nghỉ dưỡng {i} {d_name}"
        elif variant == "golf":
            name = f"Sân golf {i} {d_name}"
        out.append(_rec(pid, name, tax, d_name, desc, attrs, price, available))
        out.extend(children)
    return out


def _rec(pid: str, name: str, tax: str, dest: str, desc: str, attrs: dict, price: float | None, available: bool) -> dict:
    return {"productId": pid, "name": name, "taxonomy": tax, "destination": dest, "description": desc, "attributes": attrs,
            "unitPrice": price, "currency": "VND", "priceUnit": "UNKNOWN" if price is None else "PER_UNIT",
            "available": available, "availableFrom": None, "availableTo": None, "imageUrl": None, "sourceRef": f"fake:{pid}"}
