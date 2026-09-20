"""Bước 0 — sinh catalog tổng hợp khi chưa có crawl (MOCK_DATA_SPEC §1b).

Crawler chưa xong không được chặn mock. Module này sinh `products.synthetic.jsonl` **đúng contract
`src/data_collection/docs/SCHEMA.md`**: 13 trường cấp cao nhất, mọi thứ khác nằm trong `attributes`.
Mọi bước sau chạy y nguyên trên file này hay trên `products.jsonl` thật.

Quy mô ~450 dòng là cố ý (§1b): chạy nhanh, đọc tay được. Hệ quả: hai dòng `db/verify.sql`
(`products = 2216`, `is_recommendable properties >= 300`) FAIL theo thiết kế vì đó là ngưỡng của
crawl thật. Không thổi quy mô lên để lách — xem `AGENTS.md` §6.5.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np

from . import config
from .common import (
    inclusive_int,
    round_price,
    slugify,
    stable_order_key,
    uuid5_for,
    window_end,
)

# Tên dùng để ghép; giữ ở module này vì chỉ gen_products cần.
RESORT_BRANDS = ["Vinpearl Resort", "Vinpearl Beachfront", "VinHolidays Fiesta", "Vinpearl Discovery"]
OTHER_BRANDS = ["Sunrise Hotel", "Blue Bay Hotel", "An Nhiên Boutique", "Sea Pearl Hotel", "Lotus Riverside"]
ROOM_TYPES = [
    ("Deluxe Ocean View", True),
    ("Deluxe City View", False),
    ("Superior Twin", False),
    ("Grand Suite", True),
    ("Family Villa", True),
    ("Executive Suite", False),
    ("Standard Double", False),
]
#: Vé bán được — mang brand Vinpearl.
ATTRACTION_TICKETED_TEMPLATES = [
    "VinWonders {dest}",
    "Vinpearl Safari {dest}",
    "Grand World {dest}",
    "Tata Show {dest}",
    "Thuỷ cung {dest}",
    "Cáp treo {dest}",
]
#: Điểm công cộng không bán vé — ticketed=false, unitPrice=null. Tỷ lệ do
#: ATTRACTION_UNTICKETED_RATE quyết định, không do số lượng template.
ATTRACTION_PUBLIC_TEMPLATES = [
    "Chợ đêm {dest}",
    "Phố cổ {dest}",
    "Bảo tàng {dest}",
]


def _description(kind: str, name: str, destination: str, extra: str = "") -> str:
    base = {
        "property": f"{name} là cơ sở lưu trú tại {destination}, thuận tiện di chuyển tới trung tâm và bãi biển.",
        "room": f"{name} được thiết kế hiện đại, đầy đủ tiện nghi cho kỳ nghỉ tại {destination}.",
        "route": f"Vé máy bay một chiều {name}. Thời gian bay ngắn, nhiều khung giờ trong ngày.",
        "flight": f"Chuyến bay thẳng {name}.",
        "attraction": f"{name} là điểm đến nổi bật tại {destination}, phù hợp cho gia đình và nhóm bạn.",
        "golf": f"{name} — sân golf tiêu chuẩn quốc tế tại {destination}, khung cảnh thoáng đãng.",
        "combo": f"{name} tại {destination}.",
    }[kind]
    return f"{base} {extra}".strip()


def _latlon(rng: np.random.Generator, destination: str) -> tuple[float, float]:
    lat, lon = config.DESTINATION_LATLON[destination]
    return (
        round(lat + float(rng.normal(0, 0.03)), 6),
        round(lon + float(rng.normal(0, 0.03)), 6),
    )


def _record(
    *,
    source_ref: str,
    name: str,
    taxonomy: str,
    destination: str,
    description: str,
    attributes: dict,
    unit_price: int | None,
    available: bool = True,
    available_from: dt.date | None = None,
    available_to: dt.date | None = None,
) -> dict:
    """Một dòng products.jsonl — đúng 13 trường, không hơn không kém (SCHEMA.md §1)."""
    slug = slugify(name) or "san-pham"
    return {
        "productId": str(uuid5_for(source_ref)),
        "name": name,
        "taxonomy": taxonomy,
        "destination": destination,
        "description": description,
        "attributes": attributes,
        "unitPrice": unit_price,
        "currency": "VND",
        "available": available,
        "availableFrom": available_from.isoformat() if available_from else None,
        "availableTo": available_to.isoformat() if available_to else None,
        "imageUrl": f"https://placehold.co/800x600?text={slug}",
        "sourceRef": source_ref,
    }


def _hotels(rng: np.random.Generator, as_of: dt.date) -> list[dict]:
    """40 property (60% Vinpearl), mỗi property 2–5 room.

    Hai điểm đến neo (Nha Trang, Phú Quốc) luôn có property Vinpearl **có phòng** vì persona
    P1/P3 cần đặt ở đó. Không để may rủi quyết định việc này.
    """
    records: list[dict] = []
    for index in range(config.N_HOTEL_PROPERTIES):
        destination = config.DESTINATIONS[index % len(config.DESTINATIONS)]
        # Hai property đầu là neo cho persona: luôn Vinpearl, luôn có phòng.
        if index < len(config.ANCHOR_DESTINATIONS):
            destination = config.ANCHOR_DESTINATIONS[index]
            is_vinpearl = True
        else:
            is_vinpearl = bool(rng.random() < config.VINPEARL_PROPERTY_RATE)
        brand_pool = RESORT_BRANDS if is_vinpearl else OTHER_BRANDS
        brand_name = brand_pool[int(rng.integers(len(brand_pool)))]
        name = f"{brand_name} {destination}"
        if index >= len(config.ANCHOR_DESTINATIONS):
            name = f"{name} {index:02d}"

        source_ref = f"synthetic:hotel:{slugify(name)}"
        lat, lon = _latlon(rng, destination)
        star = float(config.STAR_RATINGS[int(rng.integers(len(config.STAR_RATINGS)))])
        attributes = {
            "level": "property",
            "province": config.DESTINATION_PROVINCE[destination],
            "city": destination,
            "address": f"Khu du lịch {destination}, {config.DESTINATION_PROVINCE[destination]}",
            "latitude": lat,
            "longitude": lon,
            "locationSource": "manual",
            "locationPrecision": "exact",
            "starRating": star,
            "starRatingType": "official",
            "reviewScore": round(float(rng.uniform(*config.REVIEW_SCORE_RANGE)), 1),
            "reviewScoreScale": 10.0,
            "reviewCount": inclusive_int(rng, config.REVIEW_COUNT_RANGE),
            "descriptionLang": "vi",
            "url": f"https://example.invalid/hotel/{slugify(name)}",
            "fieldSources": {"unitPrice": "synthetic", "description": "synthetic"},
        }
        if is_vinpearl:
            attributes["brand"] = "Vinpearl"

        # Property có giá tham khảo nhưng is_bookable=false (level=property) — chỉ đặt ở cấp phòng.
        property_record = _record(
            source_ref=source_ref,
            name=name,
            taxonomy="hotel",
            destination=destination,
            description=_description("property", name, destination),
            attributes=attributes,
            unit_price=round_price(rng.uniform(*config.PRICE_RANGE["hotel_property"])),
        )
        records.append(property_record)

        n_rooms = inclusive_int(rng, config.ROOMS_PER_PROPERTY)
        chosen = rng.choice(len(ROOM_TYPES), size=n_rooms, replace=False)
        for room_index in chosen:
            room_name, ocean = ROOM_TYPES[int(room_index)]
            full_name = f"{name} - {room_name}"
            room_ref = f"synthetic:hotel_room:{slugify(full_name)}"
            room_attributes = {
                "level": "room",
                "parentProductId": property_record["productId"],
                "hotelName": name,
                "roomName": room_name,
                "maxOccupancy": int(
                    config.MAX_OCCUPANCY_CHOICES[int(rng.integers(len(config.MAX_OCCUPANCY_CHOICES)))]
                ),
                "roomSizeM2": inclusive_int(rng, config.ROOM_SIZE_M2_RANGE),
                "oceanView": bool(ocean and rng.random() < config.OCEAN_VIEW_RATE + 0.4),
                "starRating": star,
                "latitude": lat,
                "longitude": lon,
                "locationSource": "manual",
                "locationPrecision": "exact",
                "descriptionLang": "vi",
                "url": f"https://example.invalid/hotel/{slugify(name)}/{slugify(room_name)}",
                "fieldSources": {"unitPrice": "synthetic"},
            }
            if is_vinpearl:
                room_attributes["brand"] = "Vinpearl"
            records.append(
                _record(
                    source_ref=room_ref,
                    name=full_name,
                    taxonomy="hotel",
                    destination=destination,
                    description=_description("room", full_name, destination),
                    attributes=room_attributes,
                    unit_price=round_price(rng.uniform(*config.PRICE_RANGE["hotel_room"])),
                )
            )
    return records


def _flights(rng: np.random.Generator, as_of: dt.date) -> list[dict]:
    """12 tuyến × 8–15 chuyến trong cửa sổ. Một tuyến cố ý không có chuyến nào (§1b)."""
    records: list[dict] = []
    # Chỉ chiều tới điểm đến: 3 origin × 4 destination = 12 tuyến.
    pairs = [
        (origin, dest)
        for origin in config.AIRPORT_ORIGINS
        for dest in config.AIRPORT_DESTINATIONS
    ][: config.N_FLIGHT_ROUTES]

    empty_routes = set(range(config.CATALOG_EMPTY_ROUTES))
    for route_index, ((origin_code, origin_city), (dest_code, dest_city, destination)) in enumerate(pairs):
        route_name = f"Vé máy bay {origin_city} - {dest_city}"
        route_ref = f"synthetic:flight_route:{slugify(route_name)}"
        duration = config.FLIGHT_DURATION_MINUTES.get(dest_code, 100)
        route_attributes = {
            "level": "route",
            "originCity": origin_city,
            "destinationCity": dest_city,
            "originDestination": origin_city,
            "originAirports": [origin_code],
            "destinationAirports": [dest_code],
            "destinationAirportName": f"Sân bay {dest_city}",
            "durationMinutes": duration,
            "latitude": config.DESTINATION_LATLON.get(destination, (16.0, 108.0))[0],
            "longitude": config.DESTINATION_LATLON.get(destination, (16.0, 108.0))[1],
            "locationSource": "ourairports",
            "locationPrecision": "airport",
            "descriptionLang": "vi",
            "url": f"https://example.invalid/flights/{slugify(route_name)}",
            "fieldSources": {"unitPrice": "synthetic"},
        }
        route_record = _record(
            source_ref=route_ref,
            name=route_name,
            taxonomy="flight",
            destination=destination,
            description=_description("route", f"{origin_city} - {dest_city}", destination),
            attributes=route_attributes,
            unit_price=round_price(rng.uniform(*config.PRICE_RANGE["flight_route"])),
        )
        records.append(route_record)

        if route_index in empty_routes:
            continue  # tuyến trống: để câu hỏi "mọi route có ≥ 1 chuyến?" có ví dụ thật

        for flight_index in range(inclusive_int(rng, config.FLIGHTS_PER_ROUTE)):
            airline_code, airline_name = config.AIRLINES[int(rng.integers(len(config.AIRLINES)))]
            flight_no = f"{airline_code}{int(rng.integers(100, 999))}"
            day_offset = int(rng.integers(0, config.WINDOW_DAYS))
            flight_day = as_of + dt.timedelta(days=day_offset)
            depart_hour = int(rng.integers(5, 21))
            depart_minute = int(rng.choice([0, 15, 30, 45]))
            depart = dt.datetime(
                flight_day.year, flight_day.month, flight_day.day, depart_hour, depart_minute
            )
            arrive = depart + dt.timedelta(minutes=duration)
            full_name = f"{airline_name} {flight_no}: {origin_city} - {dest_city} ({depart:%H:%M})"
            flight_ref = f"synthetic:flight:{slugify(route_name)}:{flight_no}:{flight_day:%Y%m%d}:{flight_index}"
            records.append(
                _record(
                    source_ref=flight_ref,
                    name=full_name,
                    taxonomy="flight",
                    destination=destination,
                    description=_description("flight", full_name, destination),
                    attributes={
                        "level": "flight",
                        "parentProductId": route_record["productId"],
                        # SCHEMA.md §3.7 và sample dùng `airline` = tên hãng, mã ở `airlineCode`.
                        "airline": airline_name,
                        "airlineCode": airline_code,
                        "flightNumber": flight_no,
                        "departureAt": depart.replace(tzinfo=None).isoformat() + "+07:00",
                        "arrivalAt": arrive.replace(tzinfo=None).isoformat() + "+07:00",
                        "originCity": origin_city,
                        "destinationCity": dest_city,
                        "originDestination": origin_city,
                        "originAirport": origin_code,
                        "destinationAirport": dest_code,
                        "destinationAirportName": f"Sân bay {dest_city}",
                        "durationMinutes": duration,
                        "nonstop": True,
                        "latitude": route_attributes["latitude"],
                        "longitude": route_attributes["longitude"],
                        "locationSource": "ourairports",
                        "locationPrecision": "airport",
                        "descriptionLang": "vi",
                        "url": route_attributes["url"],
                        "fieldSources": {"unitPrice": "synthetic"},
                    },
                    unit_price=round_price(rng.uniform(*config.PRICE_RANGE["flight"])),
                    # Chuyến bay: from = to = ngày bay (DATABASE_SCHEMA §1 mục 13).
                    available_from=flight_day,
                    available_to=flight_day,
                )
            )
    return records


def _attractions(rng: np.random.Generator, as_of: dt.date) -> list[dict]:
    records: list[dict] = []
    for index in range(config.N_ATTRACTIONS):
        destination = config.DESTINATIONS[index % len(config.DESTINATIONS)]
        # Tỷ lệ không bán vé do config quyết định (§1b: 15%), rồi mới chọn tên cho hợp.
        ticketed = bool(rng.random() >= config.ATTRACTION_UNTICKETED_RATE)
        pool = ATTRACTION_TICKETED_TEMPLATES if ticketed else ATTRACTION_PUBLIC_TEMPLATES
        template = pool[index % len(pool)]
        name = f"{template.format(dest=destination)} {index:02d}"
        source_ref = f"synthetic:attraction:{slugify(name)}"
        lat, lon = _latlon(rng, destination)
        attributes = {
            "province": config.DESTINATION_PROVINCE[destination],
            "city": destination,
            "venue": name,
            "openingHours": config.ATTRACTION_OPENING_HOURS[
                int(rng.integers(len(config.ATTRACTION_OPENING_HOURS)))
            ],
            "durationMinutes": int(
                config.ATTRACTION_DURATION_MINUTES[
                    int(rng.integers(len(config.ATTRACTION_DURATION_MINUTES)))
                ]
            ),
            "latitude": lat,
            "longitude": lon,
            "locationSource": "manual",
            "locationPrecision": "venue",
            "descriptionLang": "vi",
            "url": f"https://example.invalid/attraction/{slugify(name)}",
            "fieldSources": {"unitPrice": "synthetic"},
        }
        if ticketed:
            attributes["brand"] = "Vinpearl"
        else:
            # Điểm công cộng: ticketed=false và unitPrice=null → is_bookable=false (view product_meta).
            attributes["ticketed"] = False
        records.append(
            _record(
                source_ref=source_ref,
                name=name,
                taxonomy="attraction",
                destination=destination,
                description=_description("attraction", name, destination),
                attributes=attributes,
                unit_price=round_price(rng.uniform(*config.PRICE_RANGE["attraction"])) if ticketed else None,
            )
        )
    return records


def _golf(rng: np.random.Generator, as_of: dt.date) -> list[dict]:
    records: list[dict] = []
    for index in range(config.N_GOLF):
        destination = config.DESTINATIONS[index % len(config.DESTINATIONS)]
        name = f"Vinpearl Golf {destination}"
        if index >= len(config.DESTINATIONS):
            name = f"{name} {index:02d}"
        source_ref = f"synthetic:golf:{slugify(name)}"
        lat, lon = _latlon(rng, destination)
        records.append(
            _record(
                source_ref=source_ref,
                name=name,
                taxonomy="golf",
                destination=destination,
                description=_description("golf", name, destination),
                attributes={
                    "brand": "Vinpearl",
                    "province": config.DESTINATION_PROVINCE[destination],
                    "venue": name,
                    "holes": int(config.GOLF_HOLES_CHOICES[int(rng.integers(len(config.GOLF_HOLES_CHOICES)))]),
                    "teeTimeSlots": list(config.GOLF_TEE_TIME_SLOTS),
                    "latitude": lat,
                    "longitude": lon,
                    "locationSource": "manual",
                    "locationPrecision": "venue",
                    "descriptionLang": "vi",
                    "url": f"https://example.invalid/golf/{slugify(name)}",
                    "fieldSources": {"unitPrice": "synthetic"},
                },
                unit_price=round_price(rng.uniform(*config.PRICE_RANGE["golf"])),
            )
        )
    return records


def _combos(rng: np.random.Generator, as_of: dt.date, catalog: list[dict]) -> list[dict]:
    """40 combo, description liệt kê thành phần bằng **đúng tên** sản phẩm cùng destination.

    Đây là điều kiện để `parse_combos` map được ≥ 70%: nếu description bịa tên, bước sau không có gì để khớp.
    """
    by_destination: dict[str, dict[str, list[dict]]] = {}
    for record in catalog:
        attributes = record["attributes"]
        if record["taxonomy"] == "hotel" and attributes.get("level") == "room":
            kind = "room"
        elif record["taxonomy"] == "attraction" and attributes.get("ticketed", True):
            kind = "attraction"
        elif record["taxonomy"] == "golf":
            kind = "golf"
        else:
            continue
        by_destination.setdefault(record["destination"], {}).setdefault(kind, []).append(record)

    usable = [d for d in config.DESTINATIONS if "room" in by_destination.get(d, {})]
    records: list[dict] = []
    for index in range(config.N_COMBOS):
        destination = usable[index % len(usable)]
        pools = by_destination[destination]
        room = pools["room"][int(rng.integers(len(pools["room"])))]
        nights = int(config.COMBO_NIGHTS_CHOICES[int(rng.integers(len(config.COMBO_NIGHTS_CHOICES)))])
        days = nights + 1
        room_label = room["attributes"]["roomName"]
        hotel_label = room["attributes"]["hotelName"]

        parts = [f"{nights} đêm phòng {room_label} tại {hotel_label}"]
        if pools.get("attraction"):
            attraction = pools["attraction"][int(rng.integers(len(pools["attraction"])))]
            parts.append(f"vé {attraction['name']}")
        if pools.get("golf") and rng.random() < 0.25:
            golf = pools["golf"][int(rng.integers(len(pools["golf"])))]
            parts.append(f"1 lượt chơi {golf['name']}")
        parts.append("buffet sáng")
        if rng.random() < 0.35:
            parts.append("xe đưa đón sân bay")

        # name chứa "3N2Đ" để regex nights bắt được (§2.3).
        name = f"Combo {days}N{nights}Đ {destination} {index:02d}"
        per_person = bool(rng.random() < config.COMBO_PER_PERSON_RATE)
        min_pax = int(config.COMBO_MIN_PAX_CHOICES[int(rng.integers(len(config.COMBO_MIN_PAX_CHOICES)))])
        tail = f" Áp dụng cho {min_pax} khách."
        if per_person:
            tail += " Giá cho 1 khách."
        description = f"{name} bao gồm: " + " + ".join(parts) + "." + tail

        source_ref = f"synthetic:combo:{slugify(name)}"
        records.append(
            _record(
                source_ref=source_ref,
                name=name,
                taxonomy="combo",
                destination=destination,
                description=description,
                attributes={
                    "brand": "Vinpearl",
                    "province": config.DESTINATION_PROVINCE[destination],
                    "venue": hotel_label,
                    "latitude": room["attributes"]["latitude"],
                    "longitude": room["attributes"]["longitude"],
                    "locationSource": "manual",
                    "locationPrecision": "venue",
                    "descriptionLang": "vi",
                    "url": f"https://example.invalid/combo/{slugify(name)}",
                    "fieldSources": {"unitPrice": "synthetic"},
                },
                unit_price=round_price(rng.uniform(*config.PRICE_RANGE["combo"])),
            )
        )
    return records


def _apply_messy_edges(rng: np.random.Generator, catalog: list[dict]) -> list[dict]:
    """Cạnh lộn xộn cố ý (§1b): thiếu ảnh, mô tả ngắn, 2 cặp property gần trùng tên."""
    for record in catalog:
        if rng.random() < config.CATALOG_MISSING_IMAGE_RATE:
            record["imageUrl"] = None
        # Combo được miễn: description của combo là **đầu vào của parse_combos**, cắt cụt nó thì
        # §1b ("map được ≥ 70%") không thể đạt. Cạnh lộn xộn này nhằm vào search/dedupe, nên
        # áp cho các taxonomy khác là đủ.
        if record["taxonomy"] != "combo" and rng.random() < config.CATALOG_SHORT_DESCRIPTION_RATE:
            record["description"] = record["name"][:39]

    properties = [
        r for r in catalog if r["taxonomy"] == "hotel" and r["attributes"].get("level") == "property"
    ]
    for pair_index in range(config.CATALOG_NEAR_DUPLICATE_PAIRS):
        if pair_index >= len(properties):
            break
        original = properties[pair_index]
        name = original["name"].replace("Resort", "Resort & Spa")
        if name == original["name"]:
            name = f"{original['name']} Hotel"
        source_ref = f"synthetic:hotel:{slugify(name)}"
        clone = dict(original)
        clone["name"] = name
        clone["sourceRef"] = source_ref
        clone["productId"] = str(uuid5_for(source_ref))
        clone["attributes"] = dict(original["attributes"])
        clone["description"] = _description("property", name, original["destination"])
        catalog.append(clone)
    return catalog


def build_catalog(seed: int, as_of: dt.date) -> list[dict]:
    """Sinh toàn bộ catalog tổng hợp. Thuần — không chạm database, không ghi file."""
    from .common import make_rng

    rng = make_rng(seed, "gen_products")
    catalog: list[dict] = []
    catalog += _hotels(rng, as_of)
    catalog += _flights(rng, as_of)
    catalog += _attractions(rng, as_of)
    catalog += _golf(rng, as_of)
    catalog += _combos(rng, as_of, catalog)
    catalog = _apply_messy_edges(rng, catalog)

    # sourceRef là UNIQUE trong cdp.products; trùng ở đây sẽ nổ lúc load, nên chặn sớm.
    seen: set[str] = set()
    unique: list[dict] = []
    for record in catalog:
        if record["sourceRef"] in seen:
            continue
        seen.add(record["sourceRef"])
        unique.append(record)

    # Thứ tự cố định để file tái lập được byte-for-byte với cùng seed.
    unique.sort(key=lambda r: stable_order_key(r["sourceRef"]))
    _validate(unique)
    return unique


def _validate(catalog: list[dict]) -> None:
    """Chặn trước những thứ sẽ làm hỏng view `catalog.product_meta`.

    Các cast trong view (`(attributes->>'starRating')::numeric`, `::uuid`, `::double precision`)
    không có phòng vệ: một giá trị sai kiểu làm **mọi** truy vấn trên view lỗi, kể cả verify.sql.
    """
    expected_keys = {
        "productId", "name", "taxonomy", "destination", "description", "attributes",
        "unitPrice", "currency", "available", "availableFrom", "availableTo", "imageUrl", "sourceRef",
    }
    ids = {r["productId"] for r in catalog}
    for record in catalog:
        if set(record) != expected_keys:
            raise ValueError(f"{record['sourceRef']}: sai bộ 13 trường: {sorted(set(record) ^ expected_keys)}")
        attributes = record["attributes"]
        for key in ("latitude", "longitude", "starRating", "reviewScore"):
            if key in attributes and not isinstance(attributes[key], (int, float)):
                raise ValueError(f"{record['sourceRef']}: attributes.{key} phải là số")
        if "reviewCount" in attributes and not isinstance(attributes["reviewCount"], int):
            raise ValueError(f"{record['sourceRef']}: attributes.reviewCount phải là int")
        parent = attributes.get("parentProductId")
        if parent is not None and parent not in ids:
            raise ValueError(f"{record['sourceRef']}: parentProductId mồ côi {parent}")


def write_catalog(path: Path, catalog: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in catalog:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def run(*, seed: int, as_of: dt.date, out_path: Path) -> dict:
    catalog = build_catalog(seed, as_of)
    write_catalog(out_path, catalog)
    counts: dict[str, int] = {}
    for record in catalog:
        level = record["attributes"].get("level")
        variant = f"{record['taxonomy']}/{level}" if level else record["taxonomy"]
        counts[variant] = counts.get(variant, 0) + 1
    return {"path": str(out_path), "total": len(catalog), "variants": counts,
            "window": [as_of.isoformat(), window_end(as_of).isoformat()]}
