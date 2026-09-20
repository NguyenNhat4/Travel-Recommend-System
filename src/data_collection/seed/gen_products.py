"""Generate a compact contract-valid catalog only when no crawled catalog exists."""
from __future__ import annotations

import json
import random
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

DESTINATIONS = ("Nha Trang", "Phú Quốc", "Đà Nẵng", "Hội An", "Hạ Long", "Cửa Hội", "Tây Ninh")
ORIGINS = ("Hà Nội", "TP. Hồ Chí Minh")
AIRPORTS = {"Nha Trang": "CXR", "Phú Quốc": "PQC", "Đà Nẵng": "DAD", "Hạ Long": "VDO", "Hà Nội": "HAN", "TP. Hồ Chí Minh": "SGN"}
ROOMS = ("Deluxe Ocean View", "Family Suite", "Executive King")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def product(source_ref: str, name: str, taxonomy: str, destination: str, description: str, attributes: dict,
            price: int | None, available_from: str | None = None, available_to: str | None = None) -> dict:
    return {
        "productId": str(uuid.uuid5(uuid.NAMESPACE_URL, source_ref)), "name": name, "taxonomy": taxonomy,
        "destination": destination, "description": description, "attributes": attributes, "unitPrice": price,
        "currency": "VND", "available": price is not None or attributes.get("level") in ("property", "route"),
        "availableFrom": available_from, "availableTo": available_to,
        "imageUrl": f"https://placehold.co/800x600?text={slug(name)}", "sourceRef": source_ref,
    }


def generate(as_of: date, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    rows: list[dict] = []
    rooms_by_destination: dict[str, list[dict]] = {d: [] for d in DESTINATIONS}
    attractions_by_destination: dict[str, list[dict]] = {d: [] for d in DESTINATIONS}

    for index in range(40):
        destination = DESTINATIONS[index % len(DESTINATIONS)]
        brand = "Vinpearl" if index < 24 else "V-OTA"
        name = f"{brand} Resort {destination} {index + 1:02d}"
        ref = f"synthetic:hotel:property:{index + 1}"
        prop = product(ref, name, "hotel", destination, f"Khu nghỉ dưỡng 4-5 sao tại {destination}, phù hợp gia đình và cặp đôi.",
                       {"level": "property", "brand": brand, "province": destination, "city": destination,
                        "latitude": 10.0 + index / 10, "longitude": 106.0 + index / 10, "starRating": 4 + index % 2,
                        "reviewScore": round(4.1 + (index % 8) / 10, 1), "reviewCount": 100 + index * 7}, None)
        rows.append(prop)
        for room_index, room_name in enumerate(ROOMS):
            room_ref = f"synthetic:hotel:room:{index + 1}:{room_index + 1}"
            room = product(room_ref, f"{name} — {room_name}", "hotel", destination,
                           f"Hạng phòng {room_name} tại {name}, gồm bữa sáng và tiện ích nghỉ dưỡng.",
                           {"level": "room", "parentProductId": prop["productId"], "brand": brand, "province": destination,
                            "roomName": room_name, "maxOccupancy": 2 + room_index, "oceanView": room_index == 0},
                           1_600_000 + room_index * 500_000)
            rows.append(room)
            rooms_by_destination[destination].append(room)

    flight_destinations = tuple(d for d in DESTINATIONS if d in AIRPORTS)
    for route_index, (origin, destination) in enumerate((o, d) for o in ORIGINS for d in flight_destinations):
        route_ref = f"synthetic:flight:route:{AIRPORTS[origin]}-{AIRPORTS[destination]}"
        route = product(route_ref, f"{origin} → {destination}", "flight", destination,
                        f"Tuyến bay từ {origin} đến {destination}.",
                        {"level": "route", "originDestination": origin, "originAirport": AIRPORTS[origin],
                         "destinationAirport": AIRPORTS[destination]}, None)
        rows.append(route)
        for flight_index in range(8):
            day = as_of + timedelta(days=(route_index * 2 + flight_index * 3) % 30)
            depart = datetime.combine(day, time(7 + flight_index % 10, 15), timezone(timedelta(hours=7)))
            arrive = depart + timedelta(hours=1, minutes=50)
            airline = ("VN", "VJ", "QH")[flight_index % 3]
            flight_ref = f"synthetic:flight:{AIRPORTS[origin]}-{AIRPORTS[destination]}:{day}:{flight_index}"
            rows.append(product(flight_ref, f"{airline}{100 + route_index * 10 + flight_index} {origin} → {destination}", "flight", destination,
                                f"Chuyến bay thẳng từ {origin} đến {destination}.",
                                {"level": "flight", "parentProductId": route["productId"], "originDestination": origin,
                                 "airline": airline, "flightNo": f"{airline}{100 + route_index * 10 + flight_index}",
                                 "departureAt": depart.isoformat(), "arrivalAt": arrive.isoformat(), "datesSeen": [day.isoformat()]},
                                900_000 + flight_index * 90_000, day.isoformat(), day.isoformat()))

    for index in range(60):
        destination = DESTINATIONS[index % len(DESTINATIONS)]
        ticketed = index % 7 != 0
        name = f"VinWonders {destination} — Vé tiêu chuẩn {index + 1:02d}"
        attraction = product(f"synthetic:attraction:{index + 1}", name, "attraction", destination,
                             f"Vé tham quan và vui chơi trong ngày tại {destination}.",
                             {"province": destination, "venue": f"VinWonders {destination}", "ticketed": ticketed,
                              "openingHours": "09:00–18:00", "brand": "Vinpearl"}, 650_000 if ticketed else None)
        rows.append(attraction)
        attractions_by_destination[destination].append(attraction)

    for index in range(8):
        destination = DESTINATIONS[index % len(DESTINATIONS)]
        rows.append(product(f"synthetic:golf:{index + 1}", f"Vinpearl Golf {destination} {index + 1}", "golf", destination,
                            f"Green fee và xe điện tại sân golf {destination}.",
                            {"province": destination, "brand": "Vinpearl", "holes": 18 if index % 3 else 27,
                             "teeTimeSlots": ["06:00", "08:00", "13:00"]}, 2_200_000 + index * 100_000))

    for index in range(40):
        destination = DESTINATIONS[index % len(DESTINATIONS)]
        room = rooms_by_destination[destination][index % len(rooms_by_destination[destination])]
        attraction = attractions_by_destination[destination][index % len(attractions_by_destination[destination])]
        nights = 2 + index % 2
        suffix = "giá cho 1 khách" if index % 3 == 0 else "giá trọn gói"
        name = f"Combo {nights + 1}N{nights}Đ {destination}: {room['name']} + {attraction['name']}"
        rows.append(product(f"synthetic:combo:{index + 1}", name, "combo", destination,
                            f"Bao gồm\n- {nights} đêm {room['name']}\n- 2 vé {attraction['name']}\n- Buffet sáng; {suffix}.",
                            {"brand": "Vinpearl", "province": destination, "venue": attraction["attributes"]["venue"]},
                            3_900_000 + index * 75_000))

    rng.shuffle(rows)
    return rows


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

