#!/usr/bin/env python3
"""Gộp dữ liệu thô từ data/interim/*.jsonl thành catalog theo schema Product (§6 handbook).

Đầu ra (trong --data-dir, mặc định ./data):
  products.jsonl       một Product mỗi dòng, đúng 13 trường của schema
  products.csv         cùng dữ liệu, attributes để dạng JSON
  dedup_report.csv     các cụm sản phẩm trùng giữa nguồn (khách sạn, điểm tham quan) và điểm giống nhau
  stats.md             đối chiếu mục tiêu handbook, số lượng theo nguồn / loại / điểm đến, mẫu để đọc tay
  map/                 vị trí cho Google My Maps (CSV mỗi lớp) và web app (places.geojson), can-kiem-tra.csv

Quy tắc gộp trùng (handbook §3: "vinpearl.com for names and descriptions, the OTAs for pricing and availability"):
  tên, mô tả, ảnh, hạng phòng       → Vinpearl; không có Vinpearl thì booking.com, rồi agoda.com
  giá, tình trạng còn chỗ            → nguồn có giá quan sát mới nhất (priceObservedAt, theo ngày); cùng ngày thì OTA trước:
                                        booking.com → agoda.com → trip.com → Vinpearl (trip.com với vé tham quan)
  giá Vinpearl                        → attributes.vinpearlPrice; mọi giá OTA → attributes.otaPrices
  hạng sao, địa chỉ                   → nguồn chính; thiếu thì lấy từ nguồn còn lại
  toạ độ khách sạn                    → nguồn chính; toạ độ nghi sai (trùng khách sạn khác địa chỉ, xa tâm điểm đến)
                                        thì lấy nguồn còn lại. Hạng phòng dùng toạ độ khách sạn
  toạ độ vé/combo/golf Vinpearl       → địa điểm dùng vé trong collectors/venues.csv (crawl.py venues), rồi trip.com
  toạ độ vé máy bay                   → sân bay đến (geo.AIRPORTS); sửa tay mọi loại: collectors/location_overrides.csv
  giờ mở cửa, thời lượng tham quan    → trip.com
Theo kế hoạch (collectors/plan.py): chỉ giữ sản phẩm OTA thuộc các điểm đến trong kế hoạch, tối đa N mỗi điểm đến;
sản phẩm Vinpearl luôn được giữ. Tắt bằng --no-plan.
"""

from __future__ import annotations

import argparse
import copy
import csv
import gzip
import json
import logging
import math
import re
import resource
import sys
import time
import traceback
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from collectors import mapexport
from collectors.common import Paths, default_data_dir, read_jsonl, setup_logging
from collectors.geo import AIRPORTS, DESTINATION_ALIASES, DESTINATION_CENTERS, clean_coords, destination_in_text, destination_radius_km, km_from_destination, normalise_destination
from collectors.plan import TARGET_MAX, TARGET_MIN, Budget, budget_with, select_destinations
from collectors.textutil import clean_text, detect_lang, first_int, fold, iso_date, uniq
from collectors.venues import Venue, VenueMatcher, load_venues, ticket_image_slug, ticket_place_name

log = logging.getLogger("normalise")

NAMESPACE = uuid.UUID("7a1c9e1e-3b0e-4f5c-9d3a-2f6f0b9c4e21")
TAXONOMIES = ("hotel", "flight", "combo", "attraction", "golf")
PRODUCT_FIELDS = (
    "productId", "name", "taxonomy", "destination", "description", "attributes",
    "unitPrice", "currency", "available", "availableFrom", "availableTo", "imageUrl", "sourceRef",
)
SOURCE_ORDER = {"vinpearl": 0, "booking": 1, "agoda": 2, "trip": 3}

OCEAN_RE = re.compile(r"hướng biển|nhìn ra biển|view biển|giáp biển|sát biển|bãi biển riêng|ocean ?view|sea ?view|beach ?front", re.I)
FAMILY_RE = re.compile(r"gia đình|trẻ em|trẻ nhỏ|family|kids|children|phòng thông nhau|connecting", re.I)
HOTEL_BRAND_RE = re.compile(r"^(melia |meliá )?(vinpearl|vinholidays)\b", re.I)  # "Homestay gần Vinpearl" không tính


# ---------------------------------------------------------------------- tiện ích


def product_id(source_ref: str) -> str:
    return str(uuid.uuid5(NAMESPACE, source_ref))


def make_product(meta: dict | None = None, **kw) -> dict:
    p = {k: kw.get(k) for k in PRODUCT_FIELDS}
    p["name"] = clean_text(p["name"])
    p["description"] = clean_text(p["description"]) or None
    p["currency"] = p["currency"] or "VND"
    p["attributes"] = _compact(p["attributes"] or {})
    p["productId"] = product_id(p["sourceRef"])
    if isinstance(p["unitPrice"], float):
        p["unitPrice"] = int(round(p["unitPrice"]))
    p["_meta"] = meta or {}
    return p


def _compact(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def to_vnd(amount, currency: str | None, rates: dict[str, float]) -> tuple[int | None, bool]:
    if amount in (None, 0, ""):
        return None, False
    cur = (currency or "VND").upper()
    if cur == "VND":
        return int(round(float(amount))), False
    rate = rates.get(cur)
    if not rate:
        return None, False
    return int(round(float(amount) * rate / 1000.0) * 1000), True


def latest_by_key(records: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for r in records:
        k = r.get("key")
        if not k:
            continue
        if k not in best or (r.get("crawledAt") or "") >= (best[k].get("crawledAt") or ""):
            best[k] = r
    return list(best.values())


def trip_route_history(records: list[dict]) -> list[dict]:
    """Keep services observed in older route snapshots, with their actual timestamp.

    A route SEO snapshot is a selection, not evidence that omitted services ceased
    to exist. Each service uses its newest snapshot, never a historical low price.
    """
    routes = {}
    services = defaultdict(dict)
    business = defaultdict(dict)
    round_trips = defaultdict(dict)
    for record in sorted(records, key=lambda r: r.get("crawledAt") or ""):
        key = record.get("key")
        if not key:
            continue
        routes[key] = copy.deepcopy(record)
        for quote in record.get("businessQuotes", []):
            key_quote = quote.get("url")
            if key_quote and quote.get("observedAt", "") >= business[key].get(key_quote, {}).get("observedAt", ""):
                business[key][key_quote] = quote
        for capture in record.get("roundTripQuotes", []):
            round_trips[key][(capture.get("url"), capture.get("observedAt"))] = capture
        by_number = defaultdict(list)
        for flight in record.get("flights", []):
            if flight.get("flightNumber"):
                by_number[flight["flightNumber"]].append({**flight, "observedAt": record.get("crawledAt")})
        services[key].update(by_number)
    for key, route in routes.items():
        route["businessQuotes"] = list(business[key].values())
        route["roundTripQuotes"] = list(round_trips[key].values())
        current = {f.get("flightNumber") for f in route.get("flights", [])}
        route["flights"] = [{**flight, "notInLatestSnapshot": number not in current}
                            for number, flights in services[key].items() for flight in flights]
    return list(routes.values())


def _nights(q: dict) -> int | None:
    try:
        return (date.fromisoformat(q["checkout"]) - date.fromisoformat(q["checkin"])).days
    except (KeyError, TypeError, ValueError):
        return None


def haversine_m(a: dict, b: dict) -> float | None:
    la1, lo1, la2, lo2 = a.get("latitude"), a.get("longitude"), b.get("latitude"), b.get("longitude")
    if None in (la1, lo1, la2, lo2):
        return None
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = p2 - p1, math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(h))


_GENERIC_NAME = re.compile(r"\b(khu nghi duong|khach san|hotel|the|va|and|affiliated by|by|former name[^)]*|ten truoc day[^)]*)\b")


def name_keys(*names: str | None) -> list[str]:
    """Các biến thể tên để so khớp: tên đầy đủ, bỏ phần trong ngoặc, phần trong ngoặc (tên tiếng Anh của agoda)."""
    out = []
    for n in names:
        if not n:
            continue
        variants = [n, re.sub(r"\(.*\)", " ", n)] + re.findall(r"\(([^()]+)\)", n)
        for v in variants:
            k = re.sub(r"\s+", " ", _GENERIC_NAME.sub(" ", fold(v))).strip()
            if k and k not in out:
                out.append(k)
    return out


def _digits(s: str) -> set[str]:
    return set(re.findall(r"\d+", s))


def name_score(a: list[str], b: list[str]) -> float:
    from rapidfuzz import fuzz

    best = 0.0
    for x in a:
        for y in b:
            if _digits(x) != _digits(y):
                continue
            best = max(best, fuzz.token_sort_ratio(x, y))
    return best


def duration_minutes(text: str | None) -> int | None:
    """'3–5 tiếng đồng hồ' → 180; '1–2 ngày' → 480 (một ngày tham quan ~8 tiếng); '30 phút' → 30.

    Số đầu tiên có thể là thập phân: '0.5–1 ngày' phải ra 240 phút, không phải 0 — đọc số nguyên sẽ lấy
    nhầm phần '0' và làm 12 địa điểm có thời lượng bằng 0.
    """
    if not text:
        return None
    t = fold(text)                                   # fold() bỏ dấu chấm thập phân, nên tìm số trên bản gốc
    m = re.search(r"\d+(?:[.,]\d+)?", text)
    if not m:
        return None
    n = float(m.group(0).replace(",", "."))
    if n <= 0:
        return None
    if "ngay" in t or "day" in t:
        return round(n * 480)
    if "tieng" in t or "gio" in t or "hour" in t:
        return round(n * 60)
    if "phut" in t or "min" in t:
        return round(n)
    return None


# ---------------------------------------------------------------------- Vinpearl


def price_evidence(record, prices_by_date=None):
    """Preserve query dates and observation time. available_from/to is only set when there is
    real evidence of a window: either a single queried stay (checkIn/checkOut), or a genuinely
    dense/contiguous multi-date sweep (--calendar-days) — never invented from sparse sample dates
    like the old 3-sample-date default (vd. 29/09, 15/10, 14/11 rải rác 47 ngày)."""
    query = record.get("priceQuery") or {}
    observed = record.get("crawledAt")
    attrs = {"priceObservedAt": observed, "priceQuery": query or None}
    available_from = available_to = None
    if prices_by_date:
        attrs["availabilityDatesObserved"] = sorted(day for day, price in prices_by_date.items() if price is not None and price > 0)
        attrs["availabilityEvidenceKind"] = "dated_price_results"
    elif query.get("checkin") and query.get("checkout"):
        attrs["checkIn"] = query["checkin"]
        attrs["checkOut"] = query["checkout"]
        attrs["availabilityEvidenceKind"] = "queried_stay_not_a_general_date_range"
        available_from, available_to = query["checkin"], query["checkout"]
    queried = sorted(query.get("dates") or [])
    if len(queried) >= 7:
        span = (date.fromisoformat(queried[-1]) - date.fromisoformat(queried[0])).days + 1
        if len(queried) / span >= 0.8:  # ngày hỏi nằm sát nhau, không phải vài ngày mẫu rời rạc
            available_from, available_to = queried[0], queried[-1]
    return attrs, available_from, available_to


def vinpearl_hotel(r: dict) -> tuple[dict | None, list[dict]]:
    name = r.get("name")
    if not name:
        return None, []
    site = r.get("site") or {}
    hotel_ref = f"vinpearl:hotel:{r.get('hotelId') or fold(name).replace(' ', '-')}"
    destination = normalise_destination(name, site.get("destination"), r.get("address"))  # tên Vinpearl chứa điểm đến
    description = r.get("description") or ""
    about = "\n\n".join(x for x in (site.get("aboutTitle"), site.get("aboutText")) if x)
    if len(about) > len(description) * 1.2:
        description = about
    rooms_raw = [x for x in r.get("rooms") or [] if x.get("name")]
    site_prices = {fold(x.get("name")): x for x in site.get("rooms") or []}
    room_prices = [x.get("price") or x.get("minPrice") for x in rooms_raw if x.get("price") or x.get("minPrice")]
    best = r.get("bestPrice") or {}
    price = min(room_prices) if room_prices else best.get("salePrice")
    text_blob = " ".join([name, description] + [x["name"] for x in rooms_raw])
    query = r.get("priceQuery") or {}
    lat, lng = clean_coords(r.get("latitude"), r.get("longitude"))
    prop_evidence, prop_avail_from, prop_avail_to = price_evidence(
        r, {day: price for room in rooms_raw for day, price in (room.get("pricesByDate") or {}).items()}
    )
    prop = make_product(
        meta={"src": "vinpearl"},
        name=name,
        taxonomy="hotel",
        destination=destination,
        description=description,
        availableFrom=prop_avail_from,
        availableTo=prop_avail_to,
        attributes={
            "level": "property",
            **prop_evidence,
            "brand": "Vinpearl",
            "hotelCode": r.get("hotelCode"),
            "address": r.get("address"),
            "latitude": lat,
            "longitude": lng,
            "starRating": r.get("starRating"),
            "starRatingType": "official" if r.get("starRating") else None,
            "tripAdvisorRating": r.get("tripAdvisorRating"),
            "tripAdvisorReviewCount": r.get("reviewCount"),
            "amenities": r.get("amenities"),
            "policy": r.get("policy"),
            "roomTypeCount": len(rooms_raw) or None,
            "oceanView": bool(OCEAN_RE.search(text_blob)) or None,
            "familyFriendly": bool(FAMILY_RE.search(text_blob) or any((x.get("maxChild") or 0) > 0 for x in rooms_raw)) or None,
            "memberPrice": best.get("memberPrice"),
            "priceDate": (query.get("dates") or [None])[0],
            "priceNights": query.get("nights"),
            "priceAdults": query.get("adults"),
            "images": r.get("images"),
            "url": r.get("pageUrl"),
            "bookingUrl": r.get("bookingUrl"),
            "descriptionLang": detect_lang(description),
            "fieldSources": {
                "name": "vinpearl",
                "description": "vinpearl.com" if description == about and about else "vinpearl",
                "unitPrice": "vinpearl",
            },
        },
        unitPrice=price,
        currency="VND",
        available=bool(room_prices),
        imageUrl=(r.get("images") or [None])[0],
        sourceRef=hotel_ref,
    )
    rooms = []
    for room in rooms_raw:
        room_name = room["name"]
        room_text = " ".join([room_name, room.get("description") or ""] + (room.get("amenities") or []))
        occupancy = room.get("maxOccupancy")
        site_room = site_prices.get(fold(room_name)) or {}
        room_price = room.get("price") or room.get("minPrice")
        room_desc = room.get("description") or site_room.get("description") or room.get("shortDescription") or ""
        derived_desc = len(room_desc) < 80  # vd. "Deluxe Twin Terrace": quá ngắn để embedding → ghép thêm thông tin phòng
        if derived_desc:
            facts = [f"{room_name} tại {name}", room_desc if fold(room_desc) != fold(room_name) else ""]
            if room.get("sizeM2"):
                facts.append(f"Diện tích {room['sizeM2']:g} m²")
            if room.get("bedType"):
                facts.append(f"Giường: {room['bedType']}")
            if occupancy:
                facts.append(f"Tối đa {occupancy} khách")
            if room.get("amenities"):
                facts.append("Tiện nghi: " + ", ".join(room["amenities"][:12]))
            room_desc = ". ".join(x for x in facts if x) + "."
        room_evidence, room_avail_from, room_avail_to = price_evidence(r, room.get("pricesByDate"))
        rooms.append(
            make_product(
                meta={"src": "vinpearl", "roomName": room_name},
                name=f"{name} - {room_name}",
                taxonomy="hotel",
                destination=destination,
                description=room_desc,
                availableFrom=room_avail_from,
                availableTo=room_avail_to,
                attributes={
                    "level": "room",
                    **room_evidence,
                    "brand": "Vinpearl",
                    "hotelName": name,
                    "roomName": room_name,
                    "roomCode": room.get("code"),
                    "parentProductId": prop["productId"],
                    "starRating": r.get("starRating"),
                    "latitude": lat,
                    "longitude": lng,
                    "maxOccupancy": occupancy,
                    "maxAdult": room.get("maxAdult"),
                    "maxChild": room.get("maxChild"),
                    "bedrooms": room.get("bedrooms"),
                    "bedType": room.get("bedType"),
                    "isVilla": room.get("isVilla") or None,
                    "roomSizeM2": room.get("sizeM2"),
                    "amenities": room.get("amenities"),
                    "includesBreakfast": room.get("includesBreakfast") or None,
                    "ratePlans": room.get("ratePlans"),
                    "pricesByDate": room.get("pricesByDate"),
                    "pricesByDateQueried": r.get("priceDatesQueried"),
                    "listPrice": site_room.get("listPrice"),
                    "oceanView": bool(OCEAN_RE.search(room_text)) or None,
                    "familyFriendly": bool(FAMILY_RE.search(room_text) or (room.get("maxChild") or 0) > 0 or (occupancy or 0) >= 3) or None,
                    "priceDate": next(iter(room.get("pricesByDate") or {}), None),
                    "images": room.get("images"),
                    "url": r.get("pageUrl"),
                    "bookingUrl": r.get("bookingUrl"),
                    "descriptionSource": "derived: thông tin phòng (mô tả gốc quá ngắn)" if derived_desc else None,
                    "descriptionLang": detect_lang(room_desc),
                    "fieldSources": {"unitPrice": "vinpearl"},
                },
                unitPrice=room_price,
                currency="VND",
                available=room_price is not None,
                imageUrl=(room.get("images") or [None])[0] or prop["imageUrl"],
                sourceRef=f"{hotel_ref}:room:{room.get('roomTypeId') or fold(room_name).replace(' ', '-')}",
            )
        )
    return prop, rooms


def _member_tier(name: str) -> str | None:
    """'[VIN33 - Diamond] - ...' → 'VIN33 - Diamond'; '[Khách hàng đặc biệt] ...' → 'Khách hàng đặc biệt'."""
    m = re.match(r"^\[((?:VIN\s*33|VinClub|Khách hàng đặc biệt)[^\]]*)\]", name or "", re.I)
    return m.group(1).strip() if m else None


def vinpearl_taxonomy(r: dict) -> str:
    name = fold(r.get("name"))
    code = (r.get("tourCode") or "").upper()
    if "golf" in name or "tee time" in name:
        return "golf"
    if "combo" in name or code.startswith("GN") or re.search(r"\bgoi\b|nghi duong|\d+\s*n\s*\d+\s*d|khach san", name):
        return "combo"
    return "attraction"


POLICY_TITLE_RE = re.compile(r"điều khoản|chính sách|hoàn\s*h|hướng dẫn|lưu ý|quy định|terms|cancellation|how to use|policy", re.I)
# API Vinpearl thường để điều khoản trong khối mang tiêu đề "Mô tả" / "Description", nên phải nhận ra
# theo cả nội dung: trước khi có bước này, 344 vé dùng chung vài đoạn điều khoản làm mô tả.
POLICY_BODY_RE = re.compile(
    r"^\W{0,3}(lưu ý quan trọng|important note|vé (?:chỉ|có giá trị|đã mua|không được)|"
    r"ticket(?:s)? (?:need|are|is|valid)|the voucher|instructions for use|vui lòng lựa chọn ngày|"
    r"children under|regulations for applying|guests? between|quy định để áp dụng|"
    r"quý khách hàng cao dưới)", re.I)
MEMBER_PREFIX_RE = re.compile(r"^\[(?:VIN\s*33|VinClub|Khách hàng đặc biệt)[^\]]*\]\s*-?\s*", re.I)
MIN_TICKET_DESCRIPTION = 120


def base_ticket_name(name: str | None) -> str:
    """Bỏ nhãn hạng thành viên và nhãn đối tượng ưu đãi, giữ tên địa điểm để còn phân biệt được vé."""
    return MEMBER_PREFIX_RE.sub("", ticket_place_name(name or "")).strip()


def split_policy_lines(text: str) -> tuple[str, str]:
    """Tách một khối thành (nội dung, chính sách) theo từng dòng.

    Khối "Thông tin chung" của Vinpearl hay mở đầu bằng một đoạn điều khoản rồi mới tới phần giới thiệu thật;
    loại cả khối là mất tới bảy nghìn ký tự nội dung dùng được cho embedding.
    """
    keep, policy = [], []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            keep.append("")
        elif POLICY_BODY_RE.match(s):
            policy.append(s)
        else:
            keep.append(s)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(keep)).strip(), "\n".join(policy).strip()


def _ticket_blocks(r: dict) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Tách "trải nghiệm" (Mô tả, Thông tin chung, Bao gồm) khỏi "chính sách" (Điều khoản, Hoàn huỷ, Hướng dẫn).

    Mô tả dùng để embedding chỉ nên nói về sản phẩm; điều khoản đi vào attributes.policies.
    """
    content, policies = [], {}
    for block in r.get("extraInfos") or []:
        title, text = block.get("title") or "", (block.get("text") or "").strip()
        if not text:
            continue
        if POLICY_TITLE_RE.search(title):
            policies.setdefault(title or "Điều khoản", text[:2000])
            continue
        body, policy = split_policy_lines(text)
        if policy:
            policies.setdefault(f"{title} (trích từ mô tả)" if title else "Điều khoản", policy[:2000])
        if body:
            content.append((title, body))
    return content, policies


def ticket_description(r: dict, name: str, content: list[tuple[str, str]], price, audience: list[str]) -> tuple[str | None, str | None]:
    """Mô tả vé/combo Vinpearl. Luôn mở đầu bằng tên vé: nhiều vé của cùng một khu vui chơi dùng chung
    đúng một đoạn giới thiệu địa điểm, thiếu dòng này thì vector của chúng gần như trùng nhau."""
    vi_content = [b for b in content if detect_lang(b[1]) == "vi"]
    content = vi_content or content  # có bản tiếng Việt thì bỏ bản tiếng Anh trùng nội dung
    sections = [f"{t}\n{x}" if t and fold(t) in ("bao gom", "includes") else x for t, x in content]
    body = [x for x in [r.get("description"), r.get("highlight")] + sections if x]
    lead = base_ticket_name(name)
    joined = "\n\n".join(body)
    if len(joined) >= MIN_TICKET_DESCRIPTION:
        return "\n\n".join([lead] + body), None
    facts = []
    if r.get("lengthOfTour") not in (None, "", "0", 0):
        facts.append(f"Thời lượng: {r['lengthOfTour']}")
    if r.get("serviceIncluded"):
        facts.append(f"Bao gồm: {r['serviceIncluded']}")
    if audience:
        facts.append("Phù hợp: " + ", ".join(audience))
    if r.get("destinationName"):
        facts.append(f"Địa điểm: {r['destinationName']}")
    if price:
        facts.append("Giá từ " + _fmt_vnd(price))
    text = "\n\n".join([lead] + body + ([". ".join(facts)] if facts else []))
    if not body:
        return (text or r.get("shortDescription")), "derived: tên vé, thời lượng, đối tượng, địa điểm, giá"
    return text, "derived: mô tả gốc quá ngắn, bổ sung từ thông tin vé"


def vinpearl_tour_product(r: dict, today: date) -> dict | None:
    name = r.get("name")
    if not name:
        return None
    content, policies = _ticket_blocks(r)
    sale_end = iso_date(r.get("saleEndDate"))
    price = next((p for p in (r.get("adultSalePrice"), r.get("adultOriginalPrice")) if isinstance(p, (int, float)) and p > 0), None)
    audience = r.get("audience") or []
    description, description_source = ticket_description(r, name, content, price, audience)
    # giá 0 / thiếu trang chi tiết: không coi là miễn phí hay đặt được
    available = (price is not None and bool(r.get("isEnabled", True)) and (sale_end is None or sale_end >= today.isoformat()))
    text_blob = " ".join([name, description or ""] + audience)
    return make_product(
        meta={"src": "vinpearl", "supplierCode": r.get("supplierCode"), "supplierName": r.get("supplierName"),
              "imageUrlSlug": ticket_image_slug(r)},
        name=name,
        taxonomy=vinpearl_taxonomy(r),
        destination=normalise_destination(ticket_place_name(name), r.get("destinationName")),
        description=description,
        attributes={
            "brand": "Vinpearl",
            "tourCode": r.get("tourCode"),
            "province": r.get("destinationName"),
            "departure": r.get("departure"),
            "adultOriginalPrice": r.get("adultOriginalPrice"),
            "childPrice": r.get("childSalePrice") or r.get("childOriginalPrice"),
            "promo": r.get("shortDescription"),
            "audience": audience,
            "familyFriendly": ("Gia đình" in audience) or bool(FAMILY_RE.search(text_blob)) or None,
            "serviceIncluded": r.get("serviceIncluded"),
            "serviceExcluded": r.get("serviceExcluded"),
            "itinerary": r.get("tripItinerary"),
            "lengthOfTour": r.get("lengthOfTour") if r.get("lengthOfTour") not in ("0", 0) else None,
            "soldQuantity": r.get("soldQuantity"),
            "supplier": r.get("supplierName"),
            "vinpearlType": r.get("type"),
            "salesChannels": r.get("salesChannels"),
            "priceObservedAt": r.get("crawledAt"),
            "availabilityRangeKind": "sale_window" if r.get("saleStartDate") or r.get("saleEndDate") else None,
            "memberTier": _member_tier(name),
            "images": r.get("images"),
            "url": r.get("pageUrl"),
            "hasDetail": r.get("hasDetail"),
            "detailMissing": True if not r.get("hasDetail") else None,
            "priceMissing": True if price is None else None,
            "policies": policies,
            "descriptionSource": description_source,
            "descriptionLang": detect_lang(description),
            "fieldSources": {"unitPrice": "vinpearl"},
        },
        unitPrice=price,
        currency="VND",
        available=available,
        availableFrom=iso_date(r.get("saleStartDate")),
        availableTo=sale_end,
        imageUrl=(r.get("images") or [None])[0],
        sourceRef=f"vinpearl:tour:{r.get('tourCode') or r.get('id')}",
    )


def vinpearl_bundle_product(r: dict, today: date) -> dict | None:
    """Combo vé máy bay khứ hồi + khách sạn từ API bundle Vinpearl (collectors/vinpearl_bundles.py).
    Giá theo ngày khởi hành nằm ở pricesByDate (`adults` người lớn, 1 phòng, `nights` đêm); unitPrice = giá của ngày khởi hành
    sớm nhất chưa qua. Mô tả không chứa giá để text embedding không đổi theo từng lần cào."""
    hotel = r.get("hotelName")
    if not hotel or not r.get("hotelId"):
        return None
    cut = today.isoformat()
    prices = {d: p for d, p in sorted((r.get("pricesByDate") or {}).items()) if d >= cut and p}
    first_day = next(iter(prices), None)
    origin = r.get("originCity") or r.get("originAirport")
    nights, adults = r.get("nights") or 1, r.get("adults") or 2
    lat, lng = clean_coords(r.get("latitude"), r.get("longitude"))
    facts = [f"Combo gồm vé máy bay khứ hồi từ {origin} ({r.get('originAirport')}) đến sân bay {r.get('destinationAirport')} "
             f"cho {adults} người lớn và {nights} đêm tại {hotel}"]
    if r.get("starRating"):
        facts.append(f"khách sạn {r['starRating']:g} sao")
    if r.get("address"):
        facts.append(f"địa chỉ {r['address']}")
    description = ", ".join(facts) + "."
    if r.get("shortDescription"):
        description += " " + r["shortDescription"]
    if r.get("amenities"):
        description += " Tiện ích: " + ", ".join(r["amenities"][:10]) + "."
    return make_product(
        meta={"src": "vinpearl"},
        name=f"Combo vé máy bay khứ hồi từ {origin} + {nights} đêm tại {hotel}",
        taxonomy="combo",
        destination=normalise_destination(hotel, r.get("address")),
        description=description,
        attributes={
            "brand": "Vinpearl",
            "comboKind": "flight_hotel",
            "originAirport": r.get("originAirport"),
            "originCity": r.get("originCity"),
            "destinationAirport": r.get("destinationAirport"),
            "hotelName": hotel,
            "hotelCode": r.get("hotelCode"),
            "starRating": r.get("starRating"),
            "address": r.get("address"),
            "latitude": lat,
            "longitude": lng,
            "locationSource": "vinpearl" if lat is not None else None,
            "locationPrecision": "exact" if lat is not None else None,
            "amenities": r.get("amenities"),
            "tripAdvisorRating": r.get("tripAdvisorRating"),
            "tripAdvisorReviewCount": r.get("reviewCount"),
            "nights": nights,
            "priceNights": nights,
            "priceAdults": adults,
            "priceDate": first_day,
            "pricePerPerson": (r.get("pricePerPersonByDate") or {}).get(first_day) if first_day else None,
            "pricesByDate": prices or None,
            "pricesByDateQueried": sorted(d for d in r.get("datesQueried") or [] if d >= cut) or None,
            "availabilityEvidenceKind": "dated_price_results" if prices else None,
            "priceObservedAt": r.get("crawledAt"),
            "images": r.get("images"),
            "url": f"https://vinpearl.com/vi/hotels/{r['urlSlug']}" if r.get("urlSlug") else None,
            "descriptionSource": "derived: chặng bay, khách sạn và tiện ích của combo (API bundle Vinpearl)",
            "descriptionLang": detect_lang(description),
            "fieldSources": {"unitPrice": "vinpearl", "description": "vinpearl"},
        },
        unitPrice=prices.get(first_day) if first_day else None,
        currency="VND",
        available=bool(prices),
        availableFrom=first_day,
        availableTo=next(reversed(prices), None) if prices else None,
        imageUrl=(r.get("images") or [None])[0],
        sourceRef=f"vinpearl:bundle:{r.get('originAirport')}:{r.get('hotelCode') or r['hotelId']}",
    )


# ---------------------------------------------------------------------- booking.com


def booking_hotel(r: dict, rates: dict[str, float]) -> tuple[dict | None, list[dict]]:
    name = r.get("name")
    if not name:
        return None, []
    plan = r.get("plan") or {}
    addr = r.get("address") or {}
    destination = normalise_destination(
        r.get("city"), addr.get("locality"), addr.get("street"), r.get("province"), addr.get("region"), plan.get("destination"), name
    )
    hotel_ref = f"booking:hotel:{r.get('hotelId') or fold(name).replace(' ', '-')}"
    rooms_raw = r.get("rooms") or []
    converted_any = False
    room_prices = []
    for room in rooms_raw:
        vnd, conv = to_vnd(room.get("minPrice"), room.get("currency"), rates)
        room["_vnd"] = vnd
        converted_any |= conv
        if vnd:
            room_prices.append(vnd)
    facilities = uniq((r.get("popularFacilities") or []) + (r.get("facilities") or []))
    text_blob = " ".join([name, r.get("description") or ""] + facilities + [x.get("name") or "" for x in rooms_raw])
    price_query = r.get("priceQuery") or {}
    review = r.get("reviewScore")
    lat, lng = clean_coords(r.get("latitude"), r.get("longitude"))
    via_api = r.get("transport") == "apify" and lat is not None
    evidence, avail_from, avail_to = price_evidence(r)
    common = {
        **evidence,
        "province": r.get("province"),
        "city": r.get("city"),
        "address": addr.get("street"),
        "latitude": lat,
        "longitude": lng,
        "locationSource": "booking.com (API)" if via_api else None,
        "starRating": r.get("starRating"),
        "starRatingType": r.get("starRatingType"),
        "propertyType": r.get("propertyType"),
        "brand": "Vinpearl" if HOTEL_BRAND_RE.search(fold(name)) else None,
    }
    meta = {"src": "booking", "plan": plan, **({"coordApi": True} if via_api else {})}
    prop = make_product(
        meta=meta,
        name=name,
        taxonomy="hotel",
        destination=destination,
        description=r.get("description") or r.get("descriptionShort"),
        availableFrom=avail_from,
        availableTo=avail_to,
        attributes={
            "level": "property",
            **common,
            "reviewScore": review,
            "reviewScoreScale": r.get("reviewScoreScale") if review is not None else None,
            "reviewCount": r.get("reviewCount"),
            "amenities": facilities[:60],
            "highlights": r.get("highlights"),
            "roomTypeCount": len(rooms_raw) or None,
            "oceanView": bool(OCEAN_RE.search(text_blob)) or None,
            "familyFriendly": bool(FAMILY_RE.search(text_blob)) or None,
            "priceDate": price_query.get("checkin"),
            "priceNights": _nights(price_query),
            "priceAdults": price_query.get("adults"),
            "priceConverted": converted_any or None,
            "images": r.get("images"),
            "url": r.get("url"),
            "descriptionLang": detect_lang(r.get("description") or r.get("descriptionShort")),
            "fieldSources": {"name": "booking.com", "description": "booking.com", "unitPrice": "booking.com"},
        },
        unitPrice=min(room_prices) if room_prices else None,
        currency="VND",
        available=bool(room_prices),
        imageUrl=(r.get("images") or [None])[0],
        sourceRef=hotel_ref,
    )
    rooms = []
    for room in rooms_raw:
        room_name = room.get("name")
        if not room_name:
            continue
        facts = [room_name]
        if room.get("bed"):
            facts.append(room["bed"])
        if room.get("maxOccupancy"):
            facts.append(f"Tối đa {room['maxOccupancy']} khách")
        facts.extend((room.get("facilities") or [])[:25])
        room_desc = ". ".join(uniq(facts))
        if r.get("description"):
            room_desc = f"{room_desc}.\n\n{r['description']}"
        room_text = " ".join([room_name] + (room.get("facilities") or []))
        occ = room.get("maxOccupancy")
        rooms.append(
            make_product(
                meta={"src": "booking", "roomName": room_name},
                name=f"{name} - {room_name}",
                taxonomy="hotel",
                destination=destination,
                description=room_desc,
                availableFrom=avail_from,
                availableTo=avail_to,
                attributes={
                    "level": "room",
                    **common,
                    "hotelName": name,
                    "roomName": room_name,
                    "roomId": room.get("roomId"),
                    "parentProductId": prop["productId"],
                    "bed": room.get("bed"),
                    "maxOccupancy": occ,
                    "roomSizeM2": room.get("sizeM2"),
                    "amenities": room.get("facilities"),
                    "conditions": room.get("conditions"),
                    "oceanView": bool(OCEAN_RE.search(room_text)) or None,
                    "familyFriendly": bool(FAMILY_RE.search(room_text) or (occ or 0) >= 3) or None,
                    "priceDate": price_query.get("checkin"),
                    "priceNights": _nights(price_query),
                    "descriptionSource": "derived: thông tin phòng + mô tả khách sạn",
                    "descriptionLang": detect_lang(room_desc),
                    "url": r.get("url"),
                    "fieldSources": {"unitPrice": "booking.com"},
                },
                unitPrice=room.get("_vnd"),
                currency="VND",
                available=bool(room.get("_vnd")),
                imageUrl=prop["imageUrl"],
                sourceRef=f"{hotel_ref}:room:{room.get('roomId') or fold(room_name).replace(' ', '-')}",
            )
        )
    return prop, rooms


def booking_attraction_product(r: dict, rates: dict[str, float]) -> dict | None:
    name = r.get("name")
    if not name:
        return None
    vnd, converted = to_vnd(r.get("price"), r.get("currency"), rates)
    parts = [r.get("subtitle"), r.get("description")]
    if r.get("highlights"):
        parts.append("Điểm nổi bật:\n" + "\n".join(f"- {h}" for h in r["highlights"]))
    description = "\n\n".join(x for x in parts if x)
    fname = fold(name)
    destination = normalise_destination(name, r.get("subtitle"), r.get("city"))
    # parse_attraction_html() (collectors/booking_attractions.py) không lấy toạ độ — trang chỉ có bản đồ
    # tương tác (JS), không thấy toạ độ tĩnh trong HTML lúc kiểm tra (23/09/2026). Lỗ hổng có sẵn từ trước, không
    # phải mới hôm nay — dùng cùng fallback tâm điểm đến đã duyệt cho trip_combo_product(), tránh bị
    # drop_missing_coordinates() loại hết dù giá đã đúng.
    center = DESTINATION_CENTERS.get(destination or "")
    return make_product(
        meta={"src": "booking_attraction"},
        name=name,
        taxonomy="golf" if "golf" in fname else "combo" if "combo" in fname else "attraction",
        destination=destination,
        description=description,
        attributes={
            "latitude": center[0] if center else None,
            "longitude": center[1] if center else None,
            "locationSource": "destination_center" if center else None,
            "locationPrecision": "destination" if center else None,
            "city": r.get("city"),
            "duration": r.get("duration"),
            "durationMinutes": duration_minutes(r.get("duration")),
            "cancellation": r.get("cancellation"),
            "additionalInfo": r.get("additionalInfo"),
            "guideLanguages": r.get("guideLanguages"),
            "meetingPoints": r.get("meetingPoints"),
            "highlights": r.get("highlights"),
            "included": r.get("included"),
            "excluded": r.get("excluded"),
            "rating": r.get("rating"),
            "reviewCount": r.get("reviewCount"),
            "originalPrice": r.get("price") if converted else None,
            "originalCurrency": r.get("currency") if converted else None,
            "priceConverted": converted or None,
            "familyFriendly": bool(FAMILY_RE.search(description)) or None,
            "images": r.get("images"),
            "url": r.get("url"),
            "descriptionLang": r.get("descriptionLang") or detect_lang(description),
            "fieldSources": {"unitPrice": "booking.com"},
        },
        unitPrice=vnd,
        currency="VND",
        available=vnd is not None,
        imageUrl=(r.get("images") or [None])[0],
        sourceRef=f"booking:attraction:{r.get('productId')}",
    )


# ---------------------------------------------------------------------- agoda.com


def agoda_hotel(r: dict, rates: dict[str, float]) -> dict | None:
    name = r.get("name")
    if not name:
        return None
    plan = r.get("plan") or {}
    addr = r.get("address") or {}
    destination = normalise_destination(
        addr.get("region"), addr.get("locality"), addr.get("street"), (r.get("citySlug") or "").replace("-", " "),
        plan.get("destination"), name,
    )
    price, converted = to_vnd(r.get("minPrice"), r.get("currency"), rates)
    facilities = r.get("facilities") or []
    text_blob = " ".join([name, r.get("description") or ""] + facilities)
    q = r.get("priceQuery") or {}
    review = r.get("reviewScore")
    lat, lng = clean_coords(r.get("latitude"), r.get("longitude"))
    via_api = r.get("transport") == "apify" and lat is not None  # toạ độ do API trả về: được ưu tiên khi gộp (merge_hotel_cluster)
    evidence, avail_from, avail_to = price_evidence(r)
    return make_product(
        meta={"src": "agoda", "plan": plan, **({"coordApi": True} if via_api else {})},
        name=name,
        taxonomy="hotel",
        destination=destination,
        description=r.get("description"),
        availableFrom=avail_from,
        availableTo=avail_to,
        attributes={
            "level": "property",
            "nameEn": r.get("nameEn"),
            "address": ", ".join(x for x in (addr.get("street"), addr.get("locality"), addr.get("region")) if x) or None,
            "city": addr.get("region"),
            "latitude": lat,
            "longitude": lng,
            "locationSource": "agoda.com (API)" if via_api else None,
            "starRating": r.get("starRating"),
            "starRatingType": "official" if r.get("starRating") else None,
            "reviewScore": review,
            "reviewScoreScale": r.get("reviewScoreScale") if review is not None else None,
            "reviewCount": r.get("reviewCount"),
            "amenities": facilities[:60],
            "oceanView": bool(OCEAN_RE.search(text_blob)) or None,
            "familyFriendly": bool(FAMILY_RE.search(text_blob)) or None,
            "brand": "Vinpearl" if any(HOTEL_BRAND_RE.search(k) for k in name_keys(name, r.get("nameEn"))) else None,
            "priceDate": q.get("checkin"),
            **evidence,
            "priceNights": _nights(q),
            "priceAdults": q.get("adults"),
            "priceConverted": converted or None,
            "images": r.get("images"),
            "url": r.get("url"),
            "descriptionLang": detect_lang(r.get("description")),
            "fieldSources": {"name": "agoda.com", "description": "agoda.com", "unitPrice": "agoda.com"},
        },
        unitPrice=price,
        currency="VND",
        available=price is not None,
        imageUrl=(r.get("images") or [None])[0],
        sourceRef=f"agoda:hotel:{r.get('slug')}:{r.get('citySlug')}",
    )


def agoda_api_hotel(r: dict, rates: dict[str, float], today: date) -> tuple[dict | None, list[dict]]:
    """Khách sạn Agoda lấy qua API (collectors/agoda_api.py): cùng sourceRef với bản cào bằng trình duyệt (agoda:hotel:<slug>:<city>)
    nên productId không đổi; thêm hạng phòng với giá rẻ nhất theo từng ngày nhận phòng (USD đã gồm thuế phí → VND theo tỷ giá)."""
    name = r.get("name")
    if not name:
        return None, []
    cut = today.isoformat()
    queried = sorted(d for d in r.get("datesQueried") or [] if d >= cut)
    addr = r.get("address") or {}
    plan = r.get("plan") or {}
    destination = normalise_destination(
        addr.get("region"), addr.get("locality"), addr.get("street"), (r.get("citySlug") or "").replace("-", " "),
        plan.get("destination"), name,
    )
    lat, lng = clean_coords(r.get("latitude"), r.get("longitude"))
    hotel_ref = f"agoda:hotel:{r.get('slug')}:{r.get('citySlug')}"
    priced = []
    for room in r.get("rooms") or []:
        if not room.get("name"):
            continue
        by_day, converted = {}, False
        for day, amount in sorted((room.get("pricesByDate") or {}).items()):
            vnd, conv = to_vnd(amount, room.get("currency") or "USD", rates) if day >= cut else (None, False)
            if vnd:
                by_day[day], converted = vnd, converted or conv
        priced.append((room, by_day, converted))
    first_day = min((d for _, by_day, _ in priced for d in by_day), default=None)
    price = min((by_day[first_day] for _, by_day, _ in priced if first_day in by_day), default=None)
    facilities = r.get("facilities") or []
    text_blob = " ".join([name, r.get("description") or ""] + facilities)
    images = r.get("images") or []
    prop = make_product(
        meta={"src": "agoda", "plan": plan, **({"coordApi": True} if lat is not None else {})},
        name=name,
        taxonomy="hotel",
        destination=destination,
        description=r.get("description"),
        attributes={
            "level": "property",
            "nameEn": r.get("nameEn") if r.get("nameEn") != name else None,
            "propertyType": r.get("propertyType"),
            "address": addr.get("full") or ", ".join(x for x in (addr.get("street"), addr.get("locality"), addr.get("region")) if x) or None,
            "city": addr.get("region"),
            "latitude": lat,
            "longitude": lng,
            "locationSource": "agoda.com (API)" if lat is not None else None,
            "starRating": r.get("starRating"),
            "starRatingType": "official" if r.get("starRating") else None,
            "reviewScore": r.get("reviewScore"),
            "reviewScoreScale": 10.0 if r.get("reviewScore") is not None else None,
            "reviewCount": r.get("reviewCount"),
            "amenities": facilities[:60],
            "oceanView": bool(OCEAN_RE.search(text_blob)) or None,
            "familyFriendly": bool(FAMILY_RE.search(text_blob)) or None,
            "brand": "Vinpearl" if any(HOTEL_BRAND_RE.search(k) for k in name_keys(name, r.get("nameEn"))) else None,
            "agodaHotelId": r.get("hotelId"),
            "roomTypeCount": len(priced) or None,
            "priceDate": first_day,
            "priceNights": 1,
            "priceAdults": 2,
            "priceObservedAt": r.get("crawledAt"),
            "priceConverted": any(conv for _, _, conv in priced) or None,
            "availabilityEvidenceKind": "dated_price_results" if first_day else None,
            "availabilityDatesObserved": sorted({d for _, by_day, _ in priced for d in by_day}) or None,
            "images": images,
            "url": r.get("url"),
            "descriptionLang": detect_lang(r.get("description")),
            "fieldSources": {"name": "agoda.com", "description": "agoda.com", "unitPrice": "agoda.com"},
        },
        unitPrice=price,
        currency="VND",
        available=price is not None,
        imageUrl=images[0] if images else None,
        sourceRef=hotel_ref,
    )
    rooms = []
    for room, by_day, converted in priced:
        room_name = room["name"]
        facts = [f"{room_name} tại {name}"]
        if room.get("sizeM2"):
            facts.append(f"Diện tích {room['sizeM2']:g} m²")
        if room.get("bedType"):
            facts.append(f"Giường: {room['bedType']}")
        if room.get("maxOccupancy"):
            facts.append(f"Tối đa {room['maxOccupancy']} khách")
        if room.get("features"):
            facts.append("Đặc điểm: " + ", ".join(room["features"][:12]))
        description = ". ".join(facts) + "."
        room_text = " ".join([room_name] + (room.get("features") or []))
        room_day = next(iter(by_day), None)
        rooms.append(make_product(
            meta={"src": "agoda", "roomName": room_name},
            name=f"{name} - {room_name}",
            taxonomy="hotel",
            destination=destination,
            description=description,
            attributes={
                "level": "room",
                "hotelName": name,
                "roomName": room_name,
                "agodaRoomTypeId": room.get("roomId"),
                "parentProductId": prop["productId"],
                "starRating": r.get("starRating"),
                "latitude": lat,
                "longitude": lng,
                "maxOccupancy": room.get("maxOccupancy"),
                "maxExtraBeds": room.get("maxExtraBeds"),
                "bedType": room.get("bedType"),
                "roomSizeM2": room.get("sizeM2"),
                "amenities": room.get("features"),
                "includesBreakfast": room.get("breakfastIncluded"),
                "freeCancellation": room.get("freeCancellation"),
                "ratePlans": room.get("ratePlans"),
                "pricesByDate": by_day or None,
                "pricesByDateQueried": queried or None,
                "priceDate": room_day,
                "priceNights": 1,
                "priceAdults": 2,
                "priceObservedAt": r.get("crawledAt"),
                "priceConverted": converted or None,
                "oceanView": bool(OCEAN_RE.search(room_text)) or None,
                "familyFriendly": bool(FAMILY_RE.search(room_text) or (room.get("maxOccupancy") or 0) >= 3) or None,
                "images": room.get("images"),
                "url": r.get("url"),
                "descriptionSource": "derived: thông tin phòng (API agoda.com)",
                "descriptionLang": detect_lang(description),
                "fieldSources": {"unitPrice": "agoda.com"},
            },
            unitPrice=by_day.get(room_day) if room_day else None,
            currency="VND",
            available=bool(by_day),
            imageUrl=(room.get("images") or [None])[0] or prop["imageUrl"],
            sourceRef=f"{hotel_ref}:room:{room.get('roomId')}",
        ))
    return prop, rooms


# ---------------------------------------------------------------------- trip.com – khách sạn


def trip_hotel(r: dict, rates: dict[str, float]) -> tuple[dict | None, list[dict]]:
    """Normalize fresh Trip room JSON at 14/30/60-day sample dates.

    The old list-card price is never used as a room price. Physical room IDs
    stay stable across runs; a missing API response is excluded upstream.
    """
    name = r.get("name")
    if not name:
        return None, []
    plan = r.get("plan") or {}
    destination = normalise_destination(r.get("city"), r.get("province"), r.get("address"), plan.get("destination"), name)
    hotel_ref = f"trip:hotel:{r.get('hotelId') or fold(name).replace(' ', '-')}"
    queried = sorted(set(r.get("priceDatesQueried") or []))
    raw_rooms = ([room for room in r.get("rooms") or [] if room.get("name") and room.get("roomId")]
                 if queried else [])
    by_day: dict[str, int] = {}
    for room in raw_rooms:
        for day, amount in (room.get("pricesByDate") or {}).items():
            price, _ = to_vnd(amount, room.get("currency") or "VND", rates)
            if price is not None:
                by_day[day] = min(price, by_day.get(day, price))
    first_day = min(by_day) if by_day else None
    price = by_day[first_day] if first_day else None
    if not queried:
        price, _ = to_vnd(r.get("minPrice"), r.get("currency"), rates)
    facilities = r.get("facilities") or []
    text_blob = " ".join([name, r.get("description") or ""] + facilities)
    lat, lng = clean_coords(r.get("latitude"), r.get("longitude"))
    evidence, avail_from, avail_to = price_evidence(
        {**r, "priceQuery": {"dates": queried, "adults": 2, "currency": "VND"}}, by_day)
    common = {"pricesByDateQueried": queried, "pricesByDate": by_day,
              "availabilityByDate": {day: day in by_day for day in queried},
              "priceRefreshedAt": r.get("crawledAt")}
    prop = make_product(
        meta={"src": "trip", "plan": plan}, name=name, taxonomy="hotel",
        destination=destination,
        description=r.get("description") or f"{name} tại {destination}.",
        availableFrom=avail_from, availableTo=avail_to,
        attributes={"level": "property", **evidence, **common,
                    "province": r.get("province"), "city": r.get("city"),
                    "address": r.get("address"), "latitude": lat, "longitude": lng,
                    "starRating": r.get("starRating"),
                    "starRatingType": "official" if r.get("starRating") else None,
                    "propertyType": r.get("propertyType"),
                    "reviewScore": r.get("reviewScore"),
                    "reviewScoreScale": r.get("reviewScoreScale"),
                    "reviewCount": r.get("reviewCount"),
                    "amenities": facilities[:60],
                    "brand": "Vinpearl" if HOTEL_BRAND_RE.search(fold(name)) else None,
                    "oceanView": bool(OCEAN_RE.search(text_blob)) or None,
                    "familyFriendly": bool(FAMILY_RE.search(text_blob)) or None,
                    "priceDate": first_day, "priceNights": 1, "priceAdults": 2,
                    "roomTypeCount": len(raw_rooms), "images": r.get("images"),
                    "url": r.get("url"), "descriptionLang": "vi",
                    "fieldSources": {"name": "trip.com", **({"unitPrice": "trip.com"} if price else {})}},
        unitPrice=price, currency="VND", available=price is not None,
        imageUrl=(r.get("images") or [None])[0], sourceRef=hotel_ref)
    rooms = []
    for room in raw_rooms:
        room_prices = {}
        for day, amount in (room.get("pricesByDate") or {}).items():
            converted, _ = to_vnd(amount, room.get("currency") or "VND", rates)
            if converted is not None:
                room_prices[day] = converted
        first = min(room_prices) if room_prices else None
        room_price = room_prices[first] if first else None
        room_name = room["name"]
        description = f"Phòng {room_name} tại {name}."
        if room.get("sizeM2"):
            description += f" Diện tích {room['sizeM2']} m²."
        if room.get("maxOccupancy"):
            description += f" Tối đa {room['maxOccupancy']} khách."
        rooms.append(make_product(
            meta={"src": "trip", "roomName": room_name},
            name=f"{name} - {room_name}", taxonomy="hotel", destination=destination,
            description=description, attributes={
                "level": "room", "parentProductId": prop["productId"],
                "hotelName": name, "roomName": room_name, "roomId": room["roomId"],
                "maxOccupancy": room.get("maxOccupancy"), "roomSizeM2": room.get("sizeM2"),
                "images": room.get("images"), "latitude": lat, "longitude": lng,
                "pricesByDate": room_prices, "pricesByDateQueried": queried,
                "availabilityByDate": {day: day in room_prices for day in queried},
                "priceDate": first, "priceNights": 1, "priceAdults": 2,
                "priceRefreshedAt": r.get("crawledAt"), "url": r.get("url"),
                "descriptionLang": "vi",
                "fieldSources": {"unitPrice": "trip.com"} if room_price else {}},
            unitPrice=room_price, currency="VND", available=room_price is not None,
            imageUrl=(room.get("images") or r.get("images") or [None])[0],
            sourceRef=f"{hotel_ref}:room:{room['roomId']}"))
    return prop, rooms


def trip_combo_product(r: dict) -> dict | None:
    """Combo bay+ở THẬT từ trip.com/packages (nguồn mới 23/09/2026, xem collectors/trip_combos.py) — khác với
    combo Vinpearl hiện có (vé trọn gói đơn lẻ, phân loại qua từ khoá trong tên, xem vinpearl_taxonomy()).
    Giá đã là VND (trip_combos.py chỉ crawl VND) nên không cần to_vnd()."""
    name = r.get("hotelName")
    if not name or not r.get("price"):
        return None
    flight = r.get("flight") or {}
    out_seg, in_seg = flight.get("outbound") or {}, flight.get("inbound") or {}
    destination = r.get("destination") or r.get("toCity")
    title = f"Vé máy bay khứ hồi {r.get('fromCity')} - {r.get('toCity')} + {r.get('roomType') or 'phòng'} tại {name}"
    parts = [
        f"Chuyến bay khứ hồi {r.get('fromCity')} - {r.get('toCity')} ({out_seg.get('airlineCode') or ''})".strip(),
        f"{r.get('roomType') or 'Phòng'} tại khách sạn {name}",
    ]
    # Trang combo không trả toạ độ khách sạn (xem collectors/trip_combos.py) — dùng tâm điểm đến làm toạ độ xấp
    # xỉ, cùng cách trip_route_products() dùng toạ độ sân bay cho flight, để không bị drop_missing_coordinates()
    # loại bỏ vì "thiếu toạ độ". Đánh dấu rõ locationPrecision="destination" (không phải "exact") để phân biệt.
    center = DESTINATION_CENTERS.get(destination or "")
    return make_product(
        meta={"src": "trip_combo"},
        name=title,
        taxonomy="combo",
        destination=destination,
        description=". ".join(parts),
        attributes={
            "comboKind": "trip_real_flight_hotel",  # phân biệt với combo Vinpearl (vé trọn gói, phân loại qua từ khoá)
            "priceBasis": "per_person",
            "fromCode": r.get("fromCode"),
            "toCode": r.get("toCode"),
            "departDate": r.get("departDate"),
            "returnDate": r.get("returnDate"),
            "outboundFlight": out_seg or None,
            "inboundFlight": in_seg or None,
            "latitude": center[0] if center else None,
            "longitude": center[1] if center else None,
            "locationSource": "destination_center" if center else None,
            "locationPrecision": "destination" if center else None,
            "hotelName": name,
            "hotelStarRating": r.get("starRating"),
            "roomType": r.get("roomType"),
            "reviewScore": r.get("reviewScore"),
            "reviewScoreScale": r.get("reviewScoreScale"),
            "reviewCount": r.get("reviewCount"),
            "separatePrice": r.get("separatePrice"),  # giá đặt riêng (không combo) để so sánh mức tiết kiệm
            "priceObservedAt": r.get("crawledAt"),
            "url": r.get("url"),
            "descriptionLang": "vi",
            "fieldSources": {"unitPrice": "trip.com"},
        },
        unitPrice=r.get("price"),
        currency="VND",
        available=True,
        imageUrl=r.get("image"),
        sourceRef=f"trip:{r.get('key')}",  # key đã có dạng "combo:<from>-<to>:<hotelId>" (xem trip_combos.py)
    )


# ---------------------------------------------------------------------- trip.com


def trip_attraction_product(r: dict) -> dict | None:
    name = r.get("name")
    if not name:
        return None
    plan = r.get("plan") or {}
    tags = r.get("tags") or []
    description = r.get("introduction")
    facts = [name]
    if tags:
        facts.append("Loại hình: " + ", ".join(tags))
    if r.get("address"):
        facts.append("Địa chỉ: " + r["address"])
    if r.get("openingHours"):
        facts.append("Giờ mở cửa: " + r["openingHours"])
    if r.get("suggestedDuration"):
        facts.append("Thời gian tham quan đề xuất: " + r["suggestedDuration"])
    derived = None
    # mô tả dưới ngưỡng thì embedding gần như không có tín hiệu; bù bằng dữ liệu có cấu trúc đã crawl
    if not description:
        description, derived = ". ".join(facts), "derived: loại hình, địa chỉ, giờ mở cửa, thời lượng"
    elif len(description) < MIN_TICKET_DESCRIPTION and len(facts) > 1:
        description = description + "\n\n" + ". ".join(facts[1:])
        derived = "derived: mô tả gốc quá ngắn, bổ sung loại hình, địa chỉ, giờ mở cửa"
    fname = fold(name)
    text_blob = " ".join([name, description] + tags + [r.get("rankInfo") or ""])
    lat, lng = clean_coords(r.get("latitude"), r.get("longitude"))
    return make_product(
        meta={"src": "trip_attraction", "plan": plan},
        name=name,
        taxonomy="golf" if "golf" in fname else "combo" if "combo" in fname else "attraction",
        destination=normalise_destination(r.get("district"), r.get("address"), r.get("province"), plan.get("destination"), name),
        description=description,
        attributes={
            "nameEn": r.get("englishName") if r.get("englishName") != name else None,
            "address": r.get("address"),
            "district": r.get("district"),
            "province": r.get("province"),
            "latitude": lat,
            "longitude": lng,
            "tags": tags,
            "openingHours": r.get("openingHours"),
            "openingHoursDetail": r.get("openingHoursDetail"),
            "suggestedDuration": r.get("suggestedDuration"),
            "durationMinutes": duration_minutes(r.get("suggestedDuration")),
            "entryPolicies": r.get("entryPolicies"),
            "rating": r.get("rating"),
            "ratingScale": r.get("ratingScale") if r.get("rating") is not None else None,
            "reviewCount": r.get("reviewCount"),
            "popularityScore": r.get("hotScore"),
            "ranking": r.get("rankInfo"),
            # trip.com không hiện giá KHÔNG có nghĩa là miễn phí / không bán vé: chỉ ghi True khi có giá, còn lại để trống (chưa rõ)
            "ticketed": True if r.get("price") is not None else None,
            "priceObservedAt": r.get("crawledAt"),
            "familyFriendly": bool(FAMILY_RE.search(text_blob)) or None,
            "images": r.get("images"),
            "url": r.get("url"),
            "descriptionSource": derived,
            "descriptionLang": detect_lang(description),
            "fieldSources": {"name": "trip.com", "description": "trip.com", "unitPrice": "trip.com"},
        },
        unitPrice=r.get("price"),
        currency="VND",
        available=True,  # địa điểm có trên trip.com (dữ liệu mock cho demo): chưa có giá thì unitPrice = null, không kết luận "hết vé"
        imageUrl=(r.get("images") or [None])[0],
        sourceRef=f"trip:attraction:{r.get('poiId')}",
    )


ICT = timezone(timedelta(hours=7))  # giờ Việt Nam


def _ict(ts: str | None) -> datetime | None:
    """Thời điểm chuyến bay của trip.com là UTC ('…T02:20:00.000Z'; đã đối chiếu với danh sách chuyến trên trang, vd. Nha Trang →
    TP.HCM 10/10/2026 chỉ có chuyến từ 07:00, không có chuyến 00:10). Quy về giờ Việt Nam. Chuỗi không có múi giờ coi là giờ Việt Nam."""
    if not ts:
        return None
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(ICT) if t.tzinfo else t.replace(tzinfo=ICT)


def _hhmm(ts: str | None) -> str | None:
    t = _ict(ts)
    return t.strftime("%H:%M") if t else None


def _ict_date(ts: str | None) -> str | None:
    t = _ict(ts)
    return t.date().isoformat() if t else None


def _ict_iso(ts: str | None) -> str | None:
    t = _ict(ts)
    return t.replace(microsecond=0).isoformat() if t else None


def _fmt_vnd(v) -> str:
    return f"{int(v):,}".replace(",", ".") + "₫"


def _fmt_duration(minutes: int | None) -> str | None:
    if not minutes:
        return None
    h, m = divmod(minutes, 60)
    return f"{h} giờ {m} phút" if h and m else f"{h} giờ" if h else f"{m} phút"


def airport_location(destination_code: str | None, origin_code: str | None) -> dict:
    """Toạ độ sân bay đến (ghim trên bản đồ) + sân bay đi (vẽ đường bay)."""
    out: dict = {}
    dest = AIRPORTS.get((destination_code or "").upper())
    if dest:
        out.update(latitude=dest[1], longitude=dest[2], destinationAirportName=dest[0], locationSource="ourairports",
                   locationPrecision="airport")
    origin = AIRPORTS.get((origin_code or "").upper())
    if origin:
        out.update(originLatitude=origin[1], originLongitude=origin[2])
    return out


def trip_roundtrip_products(record: dict, route: dict) -> list[dict]:
    """Trip SEO lists adjacent out/in pairs; only complete, reversed and chronological pairs are usable.

    The offer on the outbound node is the total round-trip price. Never add two one-way minima.
    Cabin remains unknown unless explicitly supplied by source evidence.
    """
    legs = record.get("roundTripLegs") or []
    out, seen = [], set()
    for index, go in enumerate(legs[:-1]):
        back = legs[index + 1]
        if go.get("leg") != "out" or back.get("leg") != "in":
            continue
        dep, arr, ret, end = (_ict(go.get("departureTime")), _ict(go.get("arrivalTime")),
                              _ict(back.get("departureTime")), _ict(back.get("arrivalTime")))
        if (not all((dep, arr, ret, end, go.get("flightNumber"), back.get("flightNumber"), go.get("from"), go.get("to")))
                or not dep < arr <= ret < end or go['from'] != back.get('to') or go['to'] != back.get('from')):
            continue
        price = go.get('price')
        if not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0 or go.get('currency') != 'VND':
            continue
        if back.get('price') not in (None, price):  # unverified price semantics: don't guess
            continue
        cabin = go.get('cabinClass')
        if cabin not in ('ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', 'FIRST') or cabin != back.get('cabinClass'):
            cabin = None
        day, return_day = dep.date().isoformat(), ret.date().isoformat()
        ref = (f"trip:roundtrip:{go['from']}-{go['to']}:{go['flightNumber']}:{day}:"
               f"{back['flightNumber']}:{return_day}:{cabin or 'unknown'}")
        if ref in seen:
            continue
        seen.add(ref)
        def leg_attrs(leg):
            return {"flightNumber": leg['flightNumber'], "airline": leg.get('airline'),
                    "originAirport": leg['from'], "destinationAirport": leg['to'],
                    "departureAt": _ict_iso(leg['departureTime']), "arrivalAt": _ict_iso(leg['arrivalTime'])}
        attrs = {**leg_attrs(go), "level": "flight", "parentProductId": route['productId'],
                 "tripType": "roundTrip", "fixedDepartureDate": True, "cabinClass": cabin,
                 "returnFlight": leg_attrs(back), "returnDate": return_day,
                 "stayDays": (ret.date() - dep.date()).days, "priceBasis": "per_person",
                 "priceValidUntil": go.get('priceValidUntil'), "priceObservedAt": record.get('crawledAt'),
                 "originCity": route['attributes'].get('originCity'),
                 "destinationCity": route['destination'], "url": record.get('url'),
                 "fieldSources": {"unitPrice": "trip.com"},
                 "descriptionLang": "vi", **airport_location(go['to'], go['from'])}
        out.append(make_product(meta={"src": "trip_flight", "plan": record.get('plan') or {}},
                   name=f"Khứ hồi {go['flightNumber']} / {back['flightNumber']}: {go['from']} - {go['to']} ({day} – {return_day})",
                   taxonomy='flight', destination=route['destination'],
                   description=f"Vé khứ hồi {go['from']} - {go['to']}, đi {day}, về {return_day}. "
                               f"Giá tổng hai chặng cho một người lớn {_fmt_vnd(price)}; ghi nhận {record.get('crawledAt') or 'chưa rõ'}.",
                   attributes=attrs, unitPrice=price, currency='VND', available=True,
                   availableFrom=day, availableTo=day, sourceRef=ref, imageUrl=None))
    return out


def trip_route_products(r: dict, flights_per_route: int) -> list[dict]:
    from_city, to_city = r.get("fromCity"), r.get("toCity")
    if not from_city or not to_city:
        return []
    # tên hiển thị theo điểm đến chuẩn ("Đảo Phú Quốc" → "Phú Quốc"); giữ tên gốc nếu không khớp
    from_city = normalise_destination(from_city) or from_city
    to_city = normalise_destination(to_city) or to_city
    flights = [f for f in r.get("flights") or [] if f.get("flightNumber")]
    prices = [f["price"] for f in flights if f.get("price")]
    one_way = r.get("oneWay") or {}
    round_trip = r.get("roundTrip") or {}
    monthly = [m for m in one_way.get("monthly") or [] if m.get("price")]
    cheapest_month = min(monthly, key=lambda m: m["price"])["month"] if monthly else None
    dates = sorted({d for f in flights if (d := _ict_date(f.get("departureTime")))})  # ngày bay (giờ VN) trên mọi chuyến đã thấy
    from_airports = ", ".join(r.get("fromAirports") or []) or r.get("fromCode", "").upper()
    to_airports = ", ".join(r.get("toAirports") or []) or r.get("toCode", "").upper()
    price = min(prices) if prices else one_way.get("lowPrice")
    destination = normalise_destination(to_city)
    facts = [f"Vé máy bay một chiều từ {from_city} ({from_airports}) đến {to_city} ({to_airports})."]
    if r.get("airlines"):
        facts.append("Hãng khai thác: " + ", ".join(r["airlines"]) + ".")
    if r.get("minDurationMinutes"):
        facts.append(f"Thời gian bay khoảng {_fmt_duration(r['minDurationMinutes'])}.")
    if price:
        facts.append(f"Giá một chiều từ {_fmt_vnd(price)}" + (f", khứ hồi từ {_fmt_vnd(round_trip['lowPrice'])}." if round_trip.get("lowPrice") else "."))
    if cheapest_month:
        facts.append(f"Tháng có giá trung bình rẻ nhất: {cheapest_month}.")
    route_ref = f"trip:route:{r.get('fromCode')}-{r.get('toCode')}"
    route = make_product(
        meta={"src": "trip_flight", "plan": r.get("plan") or {}, "fromDestination": normalise_destination(from_city)},
        name=f"Vé máy bay {from_city} - {to_city}",
        taxonomy="flight",
        destination=destination,
        description=" ".join(facts),
        attributes={
            "level": "route",
            "originCity": from_city,
            "destinationCity": to_city,
            "originDestination": normalise_destination(from_city),
            "originAirports": r.get("fromAirports"),
            "destinationAirports": r.get("toAirports"),
            "airlines": r.get("airlines"),
            "durationMinutes": r.get("minDurationMinutes"),
            "roundTripFrom": round_trip.get("lowPrice"),
            "monthlyPrices": {m["month"]: m["price"] for m in monthly},
            "cheapestMonth": cheapest_month,
            "flightCount": len({f["flightNumber"] for f in flights}),
            **airport_location((r.get("toAirports") or [r.get("toCode")])[0], (r.get("fromAirports") or [r.get("fromCode")])[0]),
            "priceObservedAt": r.get("crawledAt"),
            "url": r.get("url"),
            "descriptionSource": "derived: dữ liệu chuyến bay trip.com",
            "descriptionLang": "vi",
            "fieldSources": {"unitPrice": "trip.com"},
        },
        unitPrice=price,
        currency="VND",
        available=price is not None,
        availableFrom=dates[0] if dates else None,  # ngày bay sớm nhất / muộn nhất trip.com liệt kê (giờ VN)
        availableTo=dates[-1] if dates else None,
        imageUrl=None,
        sourceRef=route_ref,
    )
    by_number: dict[str, list[dict]] = defaultdict(list)
    for f in flights:
        by_number[f["flightNumber"]].append(f)
    ranked = sorted(by_number.items(), key=lambda kv: min((x.get("price") or 10**12) for x in kv[1]))
    out = [route]
    for number, legs in (ranked if flights_per_route == 0 else ranked[:flights_per_route]):
        cheapest = min(legs, key=lambda x: x.get("price") or 10**12)
        leg_dates = sorted({d for x in legs if (d := _ict_date(x.get("departureTime")))})
        dep, arr = _hhmm(cheapest.get("departureTime")), _hhmm(cheapest.get("arrivalTime"))
        desc = (
            f"Chuyến bay {'thẳng ' if cheapest.get('nonstop') else ''}{cheapest.get('airline')} {number} từ "
            f"{cheapest.get('fromAirport') or from_city} ({cheapest.get('from')}) đến {cheapest.get('toAirport') or to_city} "
            f"({cheapest.get('to')}), cất cánh {dep}, hạ cánh {arr}, thời gian bay {_fmt_duration(cheapest.get('durationMinutes'))}."
        )
        if cheapest.get("price"):
            desc += f" Giá tham khảo một chiều từ {_fmt_vnd(cheapest['price'])} (ngày {_ict_date(cheapest.get('departureTime')) or '?'})."
        out.append(
            make_product(
                meta={"src": "trip_flight", "plan": r.get("plan") or {}, "fromDestination": normalise_destination(from_city)},
                name=f"{cheapest.get('airline')} {number}: {from_city} - {to_city} ({dep})",
                taxonomy="flight",
                destination=destination,
                description=desc,
                attributes={
                    "level": "flight",
                    "tripType": "oneWay",
                    "parentProductId": route["productId"],
                    "flightNumber": number,
                    "airline": cheapest.get("airline"),
                    "airlineCode": cheapest.get("airlineCode"),
                    "originCity": from_city,
                    "destinationCity": to_city,
                    "originDestination": normalise_destination(from_city),
                    "originAirport": cheapest.get("from"),
                    "destinationAirport": cheapest.get("to"),
                    "departureTimeLocal": dep,
                    "arrivalTimeLocal": arr,
                    "durationMinutes": cheapest.get("durationMinutes"),
                    "nonstop": cheapest.get("nonstop"),
                    **airport_location(cheapest.get("to"), cheapest.get("from")),
                    "datesSeen": leg_dates,
                    "departureAt": _ict_iso(cheapest.get("departureTime")),
                    "arrivalAt": _ict_iso(cheapest.get("arrivalTime")),
                    "priceObservedAt": cheapest.get("observedAt") or r.get("crawledAt"),
                    "notInLatestSnapshot": cheapest.get("notInLatestSnapshot") or None,
                    "url": r.get("url"),
                    "descriptionSource": "derived: dữ liệu chuyến bay trip.com",
                    "descriptionLang": "vi",
                    "fieldSources": {"unitPrice": "trip.com"},
                },
                unitPrice=cheapest.get("price"),
                currency="VND",
                available=cheapest.get("price") is not None,
                availableFrom=leg_dates[0] if leg_dates else None,
                availableTo=leg_dates[-1] if leg_dates else None,
                imageUrl=None,
                sourceRef=f"trip:flight:{cheapest.get('from')}-{cheapest.get('to')}:{number}",
            )
        )
    out.extend(trip_business_products(r, route))
    searched = trip_roundtrip_search_products(r, route)
    refs = {p["sourceRef"] for p in searched}
    out.extend(searched)  # a verified search quote wins over the SEO card of the same itinerary and cabin
    out.extend(p for p in trip_roundtrip_products(r, route) if p["sourceRef"] not in refs)
    return out


def trip_roundtrip_search_products(record: dict, route: dict) -> list[dict]:
    """Round-trip totals read from Trip's fare modal (collectors/trip_roundtrip_search), newest per itinerary+cabin.

    Same sourceRef as trip_roundtrip_products so the SEO card and the search update one ticket.
    No priceValidUntil: the search shows none, so none is invented (a stale SEO value is cleared).
    """
    from collectors.trip_roundtrip_search import parse_roundtrip
    origin = (record.get("fromAirports") or [None])[0]
    destination = (record.get("toAirports") or [None])[0]
    if not origin or not destination:
        return []
    latest: dict[str, dict] = {}
    for capture in record.get("roundTripQuotes", []):
        for q in parse_roundtrip(capture, origin, destination):
            go, back = q["outbound"], q["inbound"]
            day, return_day = go["departureAt"][:10], back["departureAt"][:10]
            ref = (f"trip:roundtrip:{origin}-{destination}:{go['flightNumber']}:{day}:"
                   f"{back['flightNumber']}:{return_day}:{q['cabinClass']}")
            if ref not in latest or q["observedAt"] >= latest[ref]["observedAt"]:
                latest[ref] = {**q, "ref": ref}
    out = []
    for ref, q in latest.items():
        go, back = q["outbound"], q["inbound"]
        day, return_day = go["departureAt"][:10], back["departureAt"][:10]
        def leg_attrs(leg, frm, to):
            return {"flightNumber": leg["flightNumber"], "airline": leg["airline"], "originAirport": frm,
                    "destinationAirport": to, "departureAt": leg["departureAt"], "arrivalAt": leg["arrivalAt"]}
        cabin_name = {"ECONOMY": "Phổ thông", "PREMIUM_ECONOMY": "Phổ thông đặc biệt", "BUSINESS": "Thương gia",
                      "FIRST": "Hạng nhất"}[q["cabinClass"]]
        attrs = {**leg_attrs(go, origin, destination), "level": "flight", "parentProductId": route["productId"],
                 "tripType": "roundTrip", "fixedDepartureDate": True, "cabinClass": q["cabinClass"],
                 "returnFlight": leg_attrs(back, destination, origin), "returnDate": return_day,
                 "stayDays": (date.fromisoformat(return_day) - date.fromisoformat(day)).days,
                 "priceBasis": "per_person", "priceValidUntil": None, "priceObservedAt": q["observedAt"],
                 "originCity": route["attributes"].get("originCity"), "destinationCity": route["destination"],
                 "url": q["url"], "descriptionLang": "vi",
                 "fieldSources": {"unitPrice": "trip.com", "cabinClass": "trip.com"},
                 **airport_location(destination, origin)}
        tickets = " Hành trình xuất thành nhiều vé riêng." if q["separateTickets"] else ""
        out.append(make_product(meta={"src": "trip_flight", "plan": record.get("plan") or {}},
                   name=f"Khứ hồi {go['flightNumber']} / {back['flightNumber']}: {origin} - {destination} "
                        f"— {cabin_name} ({day} – {return_day})",
                   taxonomy="flight", destination=route["destination"],
                   description=f"Vé khứ hồi {origin} - {destination}, đi {day} ({go['airline']} {go['flightNumber']}), "
                               f"về {return_day} ({back['airline']} {back['flightNumber']}). Hạng vé: {q['cabinLabel']}. "
                               f"Giá tổng hai chặng cho một người lớn {_fmt_vnd(q['price'])}; hình thức thanh toán tại "
                               f"nguồn: {q.get('payment') or 'không ghi rõ'}.{tickets} Ghi nhận {q['observedAt']}; "
                               f"giá có thể thay đổi tại nguồn.",
                   attributes=attrs, unitPrice=q["price"], currency="VND", available=True,
                   availableFrom=day, availableTo=day, sourceRef=ref, imageUrl=None))
    return out


def trip_business_products(record: dict, route: dict) -> list[dict]:
    from collectors.trip_business import parse_quote
    products = []
    for raw in record.get('businessQuotes', []):
        q = parse_quote(raw)
        if not q:
            continue
        origin = (record.get('fromAirports') or [None])[0]
        destination = (record.get('toAirports') or [None])[0]
        if origin != q['originAirport'] or destination != q['destinationAirport']:
            continue
        day = q['departureAt'][:10]
        number = q['flightNumber']
        ref = f"trip:flight:{origin.lower()}-{destination.lower()}:{number}:{day}:BUSINESS"
        attrs = {k: v for k, v in route['attributes'].items() if k in (
            'originCity', 'destinationCity', 'originDestination', 'latitude', 'longitude',
            'originLatitude', 'originLongitude', 'locationSource', 'locationPrecision', 'destinationAirportName')}
        attrs.update(level='flight', tripType='oneWay', parentProductId=route['productId'],
                     airline=q['airline'], airlineCode=number[:2], flightNumber=number,
                     originAirport=origin, destinationAirport=destination,
                     departureAt=q['departureAt'], arrivalAt=q['arrivalAt'],
                     departureTimeLocal=q['departureAt'][11:16], arrivalTimeLocal=q['arrivalAt'][11:16],
                     durationMinutes=q['durationMinutes'], nonstop=True, cabinClass='BUSINESS',
                     fixedDepartureDate=True, datesSeen=[day], priceObservedAt=q['observedAt'], url=q['url'],
                     descriptionSource='derived: dữ liệu chuyến bay trip.com', descriptionLang='vi',
                     fieldSources={'unitPrice': 'trip.com', 'cabinClass': 'trip.com',
                                  'departureAt': 'trip.com', 'arrivalAt': 'trip.com'})
        products.append(make_product(
            name=f"{q['airline']} {number}: {origin} - {destination} — Thương gia ({day})",
            taxonomy='flight', destination=route['destination'],
            description=f"{q['flight']}. Hạng vé: {q['cabin']}. Giá tham khảo một chiều cho 1 người lớn: "
                        f"{q['price']} VND; hình thức thanh toán tại nguồn: {q.get('payment') or 'không ghi rõ'}. "
                        f"Ghi nhận {q['observedAt']}; giá có thể thay đổi tại nguồn.",
            attributes=attrs, unitPrice=q['price'], currency='VND', available=True,
            availableFrom=day, availableTo=day, imageUrl=None, sourceRef=ref))
    return products


# ---------------------------------------------------------------------- gộp khách sạn


def merge_booking_flight_products(products: list[dict], records: list[dict], now=None) -> list[dict]:
    """Create dated cabin variants while preserving legacy flight IDs and matching route IDs.

    Full source observations stay in booking_flight_offers.jsonl. Party totals are
    never divided into per-person prices.
    """
    from collectors.booking_flights import AIRPORT_CITIES, digest

    now = now or datetime.now(timezone.utc)
    route_existing = {}
    for p in products:
        if p["taxonomy"] != "flight":
            continue
        a = p["attributes"]
        if a.get("level") == "route" and len(a.get("originAirports", [])) == len(a.get("destinationAirports", [])) == 1:
            route_existing[(a["originAirports"][0], a["destinationAirports"][0])] = p

    grouped = defaultdict(list)
    for record in latest_by_key(records):
        for offer in record.get("offers", []):
            context = offer.get("context") or {}
            if context.get("adults") != 1 or context.get("children") or context.get("tripType") != "ONEWAY":
                continue  # party totals cannot become per-person prices by division
            if context.get("cabinClass") not in ("ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"):
                continue
            identity = digest([offer["serviceKey"], offer["departureAt"], context["cabinClass"],
                               offer["segments"], offer.get("includedBaggage")])
            grouped[identity].append(offer)
    by_route = defaultdict(list)
    replacements = {}
    for service, offers in grouped.items():
        # Deduplicate repeated observations of exactly the same itinerary/conditions,
        # selecting the newest quote first, never the historical lowest price.
        latest = {}
        for o in sorted(offers, key=lambda x: x["observedAt"]):
            k = digest([o["context"], o["segments"], o.get("includedBaggage"), o.get("cardText")])
            latest[k] = o
        offers = list(latest.values())
        def fresh(o):
            observed = datetime.fromisoformat(o["observedAt"].replace("Z", "+00:00"))
            return (timedelta(0) <= now - observed <= timedelta(hours=24)
                    and datetime.fromisoformat(o["departureAt"]) > now)
        # Default display context first. Never label the representative quote a
        # globally cheapest ticket across passengers, cabins or dates.
        chosen = min(offers, key=lambda o: (not fresh(o), o["context"]["adults"] != 1,
                                           o["context"]["cabinClass"] != "ECONOMY", o["departureAt"], o["totalPrice"]))
        c = chosen["context"]
        origin, destination = c["originAirport"], c["destinationAirport"]
        route_key = (origin, destination)
        old_route = route_existing.get(route_key)
        route_ref = old_route["sourceRef"] if old_route else f"booking:route:{origin}-{destination}"
        legs = chosen["segments"]
        ref = f"booking:fare:{service}"  # never overwrite a legacy undated service
        numbers = ", ".join(l["flightNumber"] for l in legs)
        from_city, to_city = AIRPORT_CITIES[origin], AIRPORT_CITIES[destination]
        desc = (f"Hành trình một chiều {from_city} ({origin}) đến {to_city} ({destination}), "
                f"{'bay thẳng' if len(legs) == 1 else str(len(legs) - 1) + ' điểm dừng'}, "
                f"các chuyến {numbers}. Hãng bay: {', '.join(uniq(l.get('airline') for l in legs if l.get('airline')))}.")
        attrs = {"level": "flight", "parentProductId": product_id(route_ref),
                 "flightNumber": legs[0]["flightNumber"] if len(legs) == 1 else None,
                 "flightNumbers": [l["flightNumber"] for l in legs], "segments": legs,
                 "originAirport": origin, "destinationAirport": destination,
                 "originCity": from_city, "destinationCity": to_city, "originDestination": from_city,
                 "departureAt": chosen["departureAt"], "arrivalAt": chosen["arrivalAt"],
                 "datesSeen": sorted({o["departureAt"][:10] for o in offers}),
                 "nonstop": chosen["nonstop"], "bookable": True,
                 "priceContext": c, "priceUnit": "per_person", "priceBasis": "per_person", "priceKind": "quote",
                 "tripType": "oneWay", "cabinClass": c["cabinClass"], "fixedDepartureDate": True,
                 "priceValidUntil": (datetime.fromisoformat(chosen["observedAt"].replace("Z", "+00:00")) + timedelta(hours=24)).date().isoformat(),
                 "selectedOfferId": chosen["offerId"], "offerIds": [o["offerId"] for o in offers],
                 "priceObservedAt": chosen["observedAt"], "availabilityStatus": "available" if fresh(chosen) else "stale",
                 "url": chosen["bookingUrl"], "bookingUrl": chosen["bookingUrl"],
                 "fieldSources": {k: "booking.com" for k in ("description", "unitPrice", "available", "bookingUrl")},
                 "descriptionSource": "derived: lịch bay thực tế Booking.com", "descriptionLang": "vi",
                 **airport_location(destination, origin)}
        p = make_product(meta={"src": "booking_flight", "fromDestination": from_city},
                         name=f"{numbers}: {from_city} - {to_city}", taxonomy="flight", destination=to_city,
                         description=desc, attributes=attrs, unitPrice=chosen["totalPrice"], currency=chosen["currency"],
                         available=fresh(chosen), availableFrom=chosen["departureAt"][:10], availableTo=chosen["departureAt"][:10], imageUrl=None, sourceRef=ref)
        replacements[p["productId"]] = p
        by_route[route_key].append(p)
    for (origin, destination), flights in by_route.items():
        old = route_existing.get((origin, destination))
        ref = old["sourceRef"] if old else f"booking:route:{origin}-{destination}"
        best = min(flights, key=lambda p: (not p["available"], p["attributes"]["priceContext"]["adults"] != 1,
                                         p["attributes"]["priceContext"]["cabinClass"] != "ECONOMY", p["unitPrice"]))
        attrs = copy.deepcopy(best["attributes"])
        for key in ("parentProductId", "flightNumber", "flightNumbers", "segments", "departureAt", "arrivalAt", "nonstop", "sameAs", "tripType", "cabinClass", "fixedDepartureDate", "priceValidUntil"):
            attrs.pop(key, None)
        attrs.update(level="route", bookable=False, priceKind="from", originAirports=[origin],
                     destinationAirports=[destination], flightCount=len(flights))
        if old:
            attrs["sameAs"] = [f"booking:route:{origin}-{destination}"]
        p = make_product(meta={"src": "booking_flight", "fromDestination": AIRPORT_CITIES[origin]},
                         name=f"Vé máy bay {AIRPORT_CITIES[origin]} - {AIRPORT_CITIES[destination]}",
                         taxonomy="flight", destination=AIRPORT_CITIES[destination],
                         description=f"Tuyến bay một chiều từ {AIRPORT_CITIES[origin]} ({origin}) đến {AIRPORT_CITIES[destination]} ({destination}). Chọn chuyến và ngày cụ thể để xem báo giá Booking.com.",
                         attributes=attrs, unitPrice=best["unitPrice"], currency=best["currency"], available=best["available"],
                         availableFrom=None, availableTo=None, imageUrl=None, sourceRef=ref)
        replacements[p["productId"]] = p
    return [replacements.pop(p["productId"], p) for p in products] + list(replacements.values())


def cluster_hotels(props: list[dict], threshold: float) -> tuple[list[list[dict]], list[tuple]]:
    """Ghép khách sạn giữa Vinpearl / booking / agoda. Mỗi cụm có tối đa 1 bản của mỗi nguồn.
    Ghép khi (luôn cùng điểm đến): cách nhau ≤ 300 m và tên giống ≥ 75; ≤ 1 km và tên giống ≥ threshold;
    ≤ 5 km và tên gần như trùng (≥ 97, toạ độ các nguồn có thể lệch vài km); thiếu toạ độ (hoặc toạ độ nghi sai, xem
    flag_suspect_hotel_coords) và tên giống ≥ threshold + 4.
    Căn hộ/condotel có thể cùng toà nhà nhưng khác chủ: luôn yêu cầu tên giống ≥ threshold."""
    keys = {p["productId"]: name_keys(p["name"], p["attributes"].get("nameEn")) for p in props}
    by_dest: dict[str | None, list[dict]] = defaultdict(list)
    for p in props:
        by_dest[p["destination"]].append(p)
    pairs = []
    for dest, group in by_dest.items():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if a["_meta"]["src"] == b["_meta"]["src"]:
                    continue
                score = name_score(keys[a["productId"]], keys[b["productId"]])
                if score < 75:
                    continue
                shared_building = any(re.search(r"\b(apartment|can ho|condotel|vinhomes|flc sea tower|apec)\b", fold(p["name"]))
                                      for p in (a, b))
                if shared_building and score < threshold:
                    continue
                dist = haversine_m(a["attributes"], b["attributes"]) if _coords_trusted(a) and _coords_trusted(b) else None
                ok = (
                    dist is not None
                    and ((dist <= 300 and score >= 75) or (dist <= 1000 and score >= threshold) or (dist <= 5000 and score >= 97))
                ) or (dist is None and score >= threshold + 4)
                if ok:
                    pairs.append((score, -(dist or 0), a, b, dist))
    pairs.sort(key=lambda x: (x[0], x[1]), reverse=True)
    cluster_of = {p["productId"]: [p] for p in props}
    report = []
    for score, _, a, b, dist in pairs:
        ca, cb = cluster_of[a["productId"]], cluster_of[b["productId"]]
        if ca is cb:
            continue
        if {m["_meta"]["src"] for m in ca} & {m["_meta"]["src"] for m in cb}:
            continue
        ca.extend(cb)
        for m in cb:
            cluster_of[m["productId"]] = ca
        report.append((score, dist, a, b))
    clusters, seen = [], set()
    for p in props:
        c = cluster_of[p["productId"]]
        if id(c) not in seen:
            seen.add(id(c))
            clusters.append(sorted(c, key=lambda m: SOURCE_ORDER[m["_meta"]["src"]]))
    return clusters, report


def merge_hotel_cluster(members: list[dict], rooms_of: dict[str, list[dict]], rooms_per_hotel: int) -> tuple[dict, list[dict]]:
    primary = members[0]
    by = {m["_meta"]["src"]: m for m in members}
    vp, bk, ag, tp = by.get("vinpearl"), by.get("booking"), by.get("agoda"), by.get("trip")
    out = copy.deepcopy(primary)
    a = out["attributes"]
    fs = a.setdefault("fieldSources", {})
    others = members[1:]

    if not vp and bk and ag and a.get("descriptionLang") != "vi" and ag["attributes"].get("descriptionLang") == "vi":
        out["description"] = ag["description"]
        a["descriptionLang"] = "vi"
        fs["description"] = "agoda.com"

    ota = {}
    if bk and bk.get("unitPrice"):
        ota["booking.com"] = bk
    if ag and ag.get("unitPrice"):
        ota["agoda.com"] = ag
    if tp and tp.get("unitPrice"):
        ota["trip.com"] = tp
    if ota:
        # Giá quan sát mới nhất thắng (chốt 23/09/2026: booking.com không cào lại được trên VPS, giá cũ dần); cùng ngày thì giữ
        # thứ tự booking.com → agoda.com → trip.com → Vinpearl. sorted(..., reverse=True) giữ thứ tự cũ cho các nguồn cùng ngày.
        candidates = list(ota.items()) + ([("vinpearl", vp)] if vp and vp.get("unitPrice") else [])
        chosen_name, chosen = sorted(candidates, key=lambda kv: _observed_day(kv[1]), reverse=True)[0]
        if vp and vp.get("unitPrice"):
            a["vinpearlPrice"] = vp["unitPrice"]
        out["unitPrice"] = chosen["unitPrice"]
        out["available"] = True
        fs["unitPrice"] = fs["available"] = chosen_name
        a["priceDate"] = chosen["attributes"].get("priceDate")
        a["priceNights"] = chosen["attributes"].get("priceNights")
        for field in ("priceObservedAt", "priceQuery", "priceAdults", "checkIn", "checkOut", "availabilityEvidenceKind"):
            a[field] = chosen["attributes"].get(field)
        a.pop("availabilityDatesObserved", None)
        a["bookingUrl"] = chosen["attributes"].get("url")
        a["otaPrices"] = {k: v["unitPrice"] for k, v in ota.items()}

    api_src = next((m for m in members if m["_meta"].get("coordApi") and _coords_trusted(m)), None)
    own = primary if primary["_meta"]["src"] == "vinpearl" and _coords_trusted(primary) else None  # Vinpearl là nguồn chính chủ của khách sạn Vinpearl
    coord_src = own or api_src or (primary if _coords_trusted(primary) else next((m for m in others if _coords_trusted(m)), None))
    coord_src = coord_src or next((m for m in members if m["attributes"].get("latitude") is not None), None)
    for field in LOCATION_FIELDS:
        a.pop(field, None)
    if coord_src is not None:
        ca = coord_src["attributes"]
        a["latitude"], a["longitude"] = ca["latitude"], ca["longitude"]
        a["locationSource"] = ca.get("locationSource") or _src_label(coord_src)
        a["locationPrecision"] = "exact"
        if coord_src is not primary:
            fs["latitude"] = fs["longitude"] = a["locationSource"]
        if coord_src is api_src:  # toạ độ API thắng: ghi lại nếu nguồn HTML khác lệch đáng kể để còn soát
            far = [(m, haversine_m(m["attributes"], ca)) for m in members if m is not coord_src and _coords_trusted(m)]
            far = [(m, d) for m, d in far if d is not None and d > 500]
            if far:
                a["locationNote"] = "; ".join(f"toạ độ {_src_label(m)} lệch {d:.0f} m so với {a['locationSource']}" for m, d in far) + f"; dùng {a['locationSource']}"
        if coord_src["_meta"].get("coordSuspect"):
            a["locationWarning"] = coord_src["_meta"]["coordSuspect"]
        elif primary["_meta"].get("coordSuspect"):
            a["locationNote"] = f"toạ độ {_src_label(primary)} nghi sai ({primary['_meta']['coordSuspect']}) nên dùng {a['locationSource']}"

    for field in ("starRating", "starRatingType", "address", "province", "city", "propertyType"):
        if a.get(field) is None:
            donor = next((m for m in others if m["attributes"].get(field) is not None), None)
            if donor:
                a[field] = donor["attributes"][field]
                fs[field] = _src_label(donor)
    if a.get("reviewScore") is None:
        # primary (Vinpearl) không tự có reviewScore — mượn từ OTA khác trong cụm trước, TripAdvisor của
        # chính Vinpearl sau (thang 5, khác thang 10 của OTA nên phải kèm đúng reviewScoreScale)
        donor = next((m for m in others if m["attributes"].get("reviewScore") is not None), None)
        if donor:
            da = donor["attributes"]
            a["reviewScore"], a["reviewScoreScale"], a["reviewCount"] = da["reviewScore"], da.get("reviewScoreScale"), da.get("reviewCount")
            fs["reviewScore"] = _src_label(donor)
        elif a.get("tripAdvisorRating") is not None:
            a["reviewScore"], a["reviewScoreScale"], a["reviewCount"] = a["tripAdvisorRating"], 5.0, a.get("tripAdvisorReviewCount")
            fs["reviewScore"] = "vinpearl (tripadvisor)"
    for m, prefix in ((bk, "booking"), (ag, "agoda"), (tp, "trip")):
        if m and m is not primary and m["attributes"].get("reviewScore") is not None:
            a[f"{prefix}ReviewScore"] = m["attributes"]["reviewScore"]
            a[f"{prefix}ReviewCount"] = m["attributes"].get("reviewCount")
    a["amenities"] = uniq(sum((m["attributes"].get("amenities") or [] for m in members), []))[:80] or None
    for flag in ("oceanView", "familyFriendly"):
        if any(m["attributes"].get(flag) for m in members):
            a[flag] = True
    if not a.get("images"):
        donor = next((m for m in others if m["attributes"].get("images")), None)
        if donor:
            a["images"] = donor["attributes"]["images"]
            out["imageUrl"] = out["imageUrl"] or donor["imageUrl"]
    if others:
        a["sameAs"] = [m["sourceRef"] for m in others]
    if bk and bk is not primary:
        a["bookingComUrl"] = bk["attributes"].get("url")
    if ag and ag is not primary:
        a["agodaUrl"] = ag["attributes"].get("url")
    if tp and tp is not primary:
        a["tripUrl"] = tp["attributes"].get("url")
    out["attributes"] = _compact(a)

    # Giữ hạng phòng Trip theo physicalRoomId ổn định. Mỗi ID có giá/tình trạng
    # ở các mốc ngày vừa hỏi; khi gộp khách sạn với nguồn khác vẫn phải giữ chúng.
    ag_rooms = rooms_of.get(ag["productId"], []) if ag else []
    trip_rooms = rooms_of.get(tp["productId"], []) if tp else []
    if vp:
        rooms = [copy.deepcopy(x) for x in rooms_of.get(vp["productId"], [])]
        if bk and _observed_day(bk) >= _observed_day(vp):  # giá booking cũ hơn giá Vinpearl thì không đè
            _price_rooms_from_ota(rooms, rooms_of.get(bk["productId"], []))
    elif bk and ag_rooms and _observed_day(ag) > _observed_day(bk):  # hạng phòng + giá theo ngày của agoda mới hơn booking
        rooms = select_rooms(ag_rooms, rooms_per_hotel)
    elif bk:
        rooms = select_rooms(rooms_of.get(bk["productId"], []), rooms_per_hotel)
    elif ag_rooms:
        rooms = select_rooms(ag_rooms, rooms_per_hotel)
    else:
        rooms = []
    # Room IDs của Trip là khóa gốc; không khử theo tên vì hai physical rooms
    # có thể cùng tên nhưng tồn kho/giá khác nhau. Ngân sách OTA không cắt phòng
    # Trip đã được xác nhận qua JSON giá của lượt hiện tại.
    rooms.extend(copy.deepcopy(trip_rooms))
    for room in rooms:
        room["destination"] = out["destination"]
        ra = room["attributes"]
        ra["parentProductId"] = out["productId"]
        for field in LOCATION_FIELDS:  # hạng phòng luôn theo toạ độ khách sạn đã chọn
            if out["attributes"].get(field) is None:
                ra.pop(field, None)
            else:
                ra[field] = out["attributes"][field]
    return out, rooms


def _observed_day(p: dict) -> str:
    """Ngày quan sát giá (YYYY-MM-DD) để so độ mới giữa các nguồn; thiếu thì coi là cũ nhất."""
    return (p["attributes"].get("priceObservedAt") or "")[:10]


def _src_label(p: dict) -> str:
    return {"vinpearl": "vinpearl", "booking": "booking.com", "agoda": "agoda.com", "trip": "trip.com"}.get(p["_meta"]["src"], p["_meta"]["src"])


def _room_key(name: str) -> str:
    return re.sub(r"\b(phong|room|co|voi|giuong|bed|size|loai)\b", " ", fold(name)).strip()


def _price_rooms_from_ota(vp_rooms: list[dict], ota_rooms: list[dict]) -> None:
    """OTA thắng về giá: hạng phòng Vinpearl khớp tên với hạng phòng booking.com thì lấy giá booking.com."""
    from rapidfuzz import fuzz

    pairs = []
    for v in vp_rooms:
        for o in ota_rooms:
            if not o.get("unitPrice"):
                continue
            a, b = _room_key(v["_meta"]["roomName"]), _room_key(o["_meta"]["roomName"])
            if _digits(a) != _digits(b):
                continue
            score = fuzz.token_set_ratio(a, b)
            if score >= 85:
                pairs.append((score, v, o))
    pairs.sort(key=lambda x: x[0], reverse=True)
    used_v, used_o = set(), set()
    for score, v, o in pairs:
        if v["productId"] in used_v or o["productId"] in used_o:
            continue
        used_v.add(v["productId"])
        used_o.add(o["productId"])
        va = v["attributes"]
        if v.get("unitPrice"):
            va["vinpearlPrice"] = v["unitPrice"]
        v["unitPrice"] = o["unitPrice"]
        v["available"] = True
        va.setdefault("fieldSources", {})["unitPrice"] = "booking.com"
        va["otaRoomName"] = o["_meta"]["roomName"]
        va["priceDate"] = o["attributes"].get("priceDate")
        for field in ("priceObservedAt", "priceQuery", "priceNights", "checkIn", "checkOut", "availabilityEvidenceKind"):
            va[field] = o["attributes"].get(field)
        va.pop("availabilityDatesObserved", None)
        va["bookingUrl"] = o["attributes"].get("url")


def select_rooms(rooms: list[dict], n: int) -> list[dict]:
    chosen, seen = [], set()
    for room in sorted(rooms, key=lambda x: (x.get("unitPrice") is None, x.get("unitPrice") or 0)):
        key = _room_key(room["_meta"]["roomName"])
        if key in seen:
            continue
        seen.add(key)
        chosen.append(copy.deepcopy(room))
        if n > 0 and len(chosen) >= n:
            break
    return chosen


# ---------------------------------------------------------------------- vé Vinpearl ↔ điểm tham quan trip.com


POI_FIELDS = ("openingHours", "openingHoursDetail", "suggestedDuration", "durationMinutes", "latitude", "longitude", "address", "tags")


def merge_pois(tickets: list[dict], pois: list[dict]) -> tuple[list[dict], list[tuple]]:
    """Điểm tham quan trip.com trùng tên với vé Vinpearl → gộp vào vé (Vinpearl giữ tên/mô tả, giá theo trip.com);
    các vé Vinpearl khác có chứa tên điểm đó → bổ sung giờ mở cửa, thời lượng, toạ độ."""
    from rapidfuzz import fuzz

    kept, report = [], []
    by_dest: dict[str | None, list[dict]] = defaultdict(list)
    for t in tickets:
        by_dest[t["destination"]].append(t)
    for poi in pois:
        pkeys = name_keys(poi["name"], poi["attributes"].get("nameEn"))
        exact, related = None, []
        for t in by_dest.get(poi["destination"], []):
            tkey = name_keys(re.sub(r"^\[[^\]]*\]\s*-?\s*", "", t["name"]))
            score = name_score(pkeys, tkey)
            if score >= 92 and (exact is None or score > exact[0]):
                exact = (score, t)
            elif any(fuzz.token_set_ratio(pk, tk) == 100 and len(pk.split()) >= 2 for pk in pkeys for tk in tkey):
                related.append(t)
        for t in related + ([exact[1]] if exact else []):
            ta = t["attributes"]
            for f in POI_FIELDS:
                if ta.get(f) in (None, [], "") and poi["attributes"].get(f) not in (None, [], ""):
                    ta[f] = poi["attributes"][f]
            ta["poiRef"] = poi["sourceRef"]
            ta["poiName"] = poi["name"]
            ta["tripRating"] = poi["attributes"].get("rating")
            ta["tripReviewCount"] = poi["attributes"].get("reviewCount")
        if exact:
            t = exact[1]
            ta = t["attributes"]
            if poi.get("unitPrice"):
                if t.get("unitPrice"):
                    ta["vinpearlPrice"] = t["unitPrice"]
                t["unitPrice"] = poi["unitPrice"]
                t["available"] = True
                ta.setdefault("fieldSources", {})["unitPrice"] = "trip.com"
                ta["otaPrices"] = {"trip.com": poi["unitPrice"]}
            ta["sameAs"] = uniq((ta.get("sameAs") or []) + [poi["sourceRef"]])
            ta["tripUrl"] = poi["attributes"].get("url")
            report.append((exact[0], None, t, poi))
        else:
            kept.append(poi)
    return kept, report


# ---------------------------------------------------------------------- độ chi tiết khách sạn / nguyên căn

# Loại hình mà đơn vị cho thuê là cả căn (biệt thự, nhà nghỉ dưỡng, căn hộ), không phải một phòng trong khách sạn.
ENTIRE_PLACE_TYPES = {"biet thu", "nha nghi duong", "can ho"}
ENTIRE_PLACE_PHRASE = re.compile(r"\b(nguyen can|toan bo can|entire (villa|house|home|apartment|place|property)|whole (villa|house|home))\b")


def annotate_hotel_granularity(products: list[dict]) -> None:
    """TUỲ CHỌN (`--annotate-hotel-granularity`, mặc định tắt vì không đổi form catalog). Ghi vào attributes của dòng
    khách sạn (cấp property), không đổi 13 trường của Product:

    - hasRoomRows: có dòng phòng đi kèm hay không. False với khách sạn chỉ có ở Agoda (adapter Agoda chỉ lấy giá rẻ nhất
      cấp cơ sở, cố ý không lấy bảng phòng), để phía sau không hiểu nhầm là thiếu dữ liệu.
    - rentalUnit = "entire_place" + rentalUnitEvidence: chỉ khi có bằng chứng (loại hình hoặc cụm "nguyên căn").
      Không đoán từ tên. Tình trạng còn phòng không nằm trong mô tả/embedding: chỉ là bộ lọc lúc truy vấn.
    """
    room_names: dict[str, list[str]] = {}
    for p in products:
        a = p["attributes"]
        if p["taxonomy"] == "hotel" and a.get("level") == "room":
            room_names.setdefault(a.get("parentProductId"), []).append(p["name"])
    for p in products:
        a = p["attributes"]
        if p["taxonomy"] != "hotel" or a.get("level") != "property":
            continue
        rooms = room_names.get(p["productId"], [])
        a["hasRoomRows"] = bool(rooms)
        kind = fold(a.get("propertyType") or "")
        if kind in ENTIRE_PLACE_TYPES:
            a["rentalUnit"], a["rentalUnitEvidence"] = "entire_place", f"loại hình: {a.get('propertyType')}"
            continue
        m = ENTIRE_PLACE_PHRASE.search(fold(" ".join([p["name"], p["description"] or ""] + rooms)))
        if m:
            a["rentalUnit"], a["rentalUnitEvidence"] = "entire_place", f"cụm từ: {m.group(0)}"


# ---------------------------------------------------------------------- vị trí


LOCATION_OVERRIDES_CSV = Path(__file__).resolve().parent / "collectors" / "location_overrides.csv"
EXCLUDED_PRODUCTS_CSV = Path(__file__).resolve().parent / "collectors" / "excluded_products.csv"


def load_excluded_products(path: Path | None = None) -> dict[str, str]:
    """sourceRef của sản phẩm đã soát tay và quyết định loại, kèm lý do.

    Dùng cho thứ mà không quy tắc tự động nào bắt được: nguồn xếp nhầm danh mục (văn phòng bảo hiểm, hãng
    taxi nằm trong danh sách điểm tham quan), hoặc nguồn trả mô tả của sản phẩm khác.
    """
    path = path or EXCLUDED_PRODUCTS_CSV
    out: dict[str, str] = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ref, reason = (str(row.get(k) or "").strip() for k in ("sourceRef", "reason"))
            if ref:
                out[ref] = reason or "đã soát tay và loại"
    return out


# Trip xếp cả văn phòng bảo hiểm, hãng taxi, phòng khám... vào danh sách "điểm tham quan". Danh sách tay
# (excluded_products.csv) không theo kịp khi mở rộng ra nhiều thành phố, nên loại thêm theo quy tắc trên tên đã bỏ dấu.
# Quy tắc cố ý hẹp (từ khoá rõ nghĩa) và chỉ áp cho điểm tham quan của trip.com; sản phẩm bị loại được ghi ra
# data/excluded_auto.csv để soát lại, không xoá âm thầm.
NON_TOURISM_RULES: tuple[tuple[str, re.Pattern], ...] = tuple(
    (reason, re.compile(pattern)) for reason, pattern in (
        ("văn phòng bảo hiểm", r"\b(bao hiem|insurance|hanwha|prudential|manulife|dai ichi)\b"),
        ("cơ sở y tế", r"\b(benh vien|phong kham|tiem chung|vnvc|nha khoa|hospital|clinic|dental)\b"),
        ("hãng taxi / cho thuê xe", r"\b(taxi|cho thue xe|thue xe|motorbike rental|car rental|xanh sm)\b"),
        ("ngân hàng", r"\b(ngan hang|bank|atm)\b"),
        ("siêu thị / cửa hàng tiện lợi", r"\b(sieu thi|winmart|circle k|bach hoa xanh|family ?mart)\b"),
        ("trường học", r"\b(truong (mam non|tieu hoc|thcs|thpt|dai hoc|cao dang)|university|school)\b"),
        ("cơ quan hành chính", r"\b(uy ban nhan dan|ubnd|toa an|cong an)\b"),
        ("bất động sản", r"\b(bat dong san|real estate|du an can ho)\b"),
        ("đại lý / công ty lữ hành", r"\b(dai ly ve|travel agency|tour operator|cong ty (du lich|lu hanh))\b"),
        ("quán ăn / cà phê", r"\b(quan ca phe|cafe|ca phe|coffee|nha hang|restaurant)\b"),
    )
)


def non_tourism_reason(name: str | None) -> str | None:
    """Lý do tên này không phải điểm du lịch (theo quy tắc ở trên), hoặc None."""
    folded = fold(name or "")
    for reason, pattern in NON_TOURISM_RULES:
        if pattern.search(folded):
            return reason
    return None


DESTINATION_OVERRIDES_CSV = Path(__file__).resolve().parent / "collectors" / "destination_overrides.csv"
LOCATION_SOURCE = {"vinpearl": "vinpearl", "booking": "booking.com", "agoda": "agoda.com", "trip_attraction": "trip.com",
                   "booking_attraction": "booking.com"}
LOCATION_FIELDS = ("latitude", "longitude", "locationSource", "locationPrecision", "locationWarning")


def load_destination_overrides(path: Path | None = None) -> dict[str, tuple[str, str]]:
    """Điểm đến du lịch đã đối chiếu theo sourceRef; bắt buộc ghi bằng chứng, không đoán từ tên đường."""
    path = path or DESTINATION_OVERRIDES_CSV
    if not path.exists():
        return {}
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for n, row in enumerate(csv.DictReader(f), 2):
            ref, dest, evidence = (str(row.get(k) or "").strip() for k in ("sourceRef", "destination", "evidence"))
            if not ref or dest not in DESTINATION_ALIASES or not evidence:
                log.warning("%s dòng %d: thiếu sourceRef/bằng chứng hoặc điểm đến không hợp lệ – bỏ qua", path.name, n)
                continue
            out[ref] = (dest, evidence)
    return out


def apply_destination_overrides(products: list[dict], overrides: dict[str, tuple[str, str]]) -> int:
    changed = 0
    for p in products:
        if p["sourceRef"] not in overrides:
            continue
        dest, evidence = overrides[p["sourceRef"]]
        a = p["attributes"]
        if p["destination"] != dest:
            a["originalDestination"] = p["destination"]
            p["destination"] = dest
            changed += 1
        a["destinationSource"] = "reviewed: collectors/destination_overrides.csv"
        a["destinationEvidence"] = evidence
    return changed


def load_location_overrides(path: Path | None = None) -> dict[str, tuple[float, float]]:
    """collectors/location_overrides.csv: sourceRef,latitude,longitude,note – toạ độ sửa tay, thắng mọi nguồn."""
    out: dict[str, tuple[float, float]] = {}
    path = path or LOCATION_OVERRIDES_CSV
    if not path.exists():
        return out
    with open(path, encoding="utf-8-sig", newline="") as f:
        for n, row in enumerate(csv.DictReader(f), 2):
            ref = (row.get("sourceRef") or "").strip()
            if not ref:
                continue
            lat, lng = clean_coords(row.get("latitude"), row.get("longitude"))
            if lat is None:
                log.warning("%s dòng %d: toạ độ không hợp lệ (%s, %s) – bỏ qua", path.name, n, row.get("latitude"), row.get("longitude"))
                continue
            out[ref] = (lat, lng)
    return out


def apply_location_overrides(products: list[dict], overrides: dict[str, tuple[float, float]]) -> int:
    n = 0
    for p in products:
        if p["sourceRef"] in overrides:
            a = p["attributes"]
            a["latitude"], a["longitude"] = overrides[p["sourceRef"]]
            a["locationSource"], a["locationPrecision"] = "manual", "exact"
            p["_meta"]["locationOverride"] = True
            p["_meta"].pop("coordSuspect", None)
            n += 1
    return n


def _same_address(x: str | None, y: str | None) -> bool:
    tx, ty = set(fold(x).split()), set(fold(y).split())
    if not tx or not ty:
        return True  # thiếu địa chỉ thì không đủ căn cứ để nghi
    return len(tx & ty) / len(tx | ty) >= 0.8


def flag_suspect_hotel_coords(props: list[dict]) -> Counter:
    """Đánh dấu toạ độ khách sạn nghi sai: không dùng để ghép trùng, khi gộp thì ưu tiên toạ độ nguồn khác.
    - cách tâm điểm đến xa hơn bán kính trong geo.py (vd. API ghi Vinpearl Hà Tĩnh cách thành phố 34 km);
    - API Vinpearl ghi trùng toạ độ (≤ 30 m) cho hai khách sạn khác địa chỉ (vd. Vinpearl Empire Nha Trang ở
      Lê Thánh Tôn trùng Vinpearl Luxury Nha Trang trên đảo Hòn Tre). Chỉ xét Vinpearl: căn hộ trên OTA ở chung
      một toà nhà vốn trùng toạ độ."""
    stats: Counter = Counter()
    vinpearl = []
    for p in props:
        a = p["attributes"]
        if a.get("latitude") is None:
            continue
        km = km_from_destination(p["destination"], a["latitude"], a["longitude"])
        if km is not None and km > destination_radius_km(p["destination"]):
            p["_meta"]["coordSuspect"] = f"cách tâm {p['destination']} {km:.0f} km"
            stats["khách sạn: toạ độ xa tâm điểm đến"] += 1
        if p["_meta"]["src"] == "vinpearl":
            vinpearl.append(p)
    for i, x in enumerate(vinpearl):
        for y in vinpearl[i + 1:]:
            d = haversine_m(x["attributes"], y["attributes"])
            if d is not None and d <= 30 and not _same_address(x["attributes"].get("address"), y["attributes"].get("address")):
                for p, other in ((x, y), (y, x)):
                    if "coordSuspect" not in p["_meta"]:
                        p["_meta"]["coordSuspect"] = f"trùng toạ độ với {other['name']} (khác địa chỉ)"
                        stats["khách sạn: trùng toạ độ khách sạn khác"] += 1
    return stats


def _coords_trusted(p: dict) -> bool:
    return p["attributes"].get("latitude") is not None and not p["_meta"].get("coordSuspect")


def assign_venue_locations(tickets: list[dict], venues: list[Venue]) -> Counter:
    """Vé/combo/golf Vinpearl → địa điểm dùng vé (collectors/venues.csv): toạ độ nếu địa điểm đã có toạ độ dùng được
    (status ok/auto). Điểm đến theo địa điểm khi khớp qua nhà cung cấp, hoặc tên vé không nêu điểm đến (tỉnh trong API
    hay sai: Vinpearl Golf Léman ở TP.HCM bị ghi Hải Phòng, vé Grand World Hà Nội bị tính là Phú Quốc)."""
    stats: Counter = Counter()
    matcher = VenueMatcher(venues)
    for v in venues:
        v.tickets = 0  # đếm lại theo dữ liệu hiện tại (cột tickets trong CSV là của lần chạy crawl.py venues gần nhất)
    for t in tickets:
        m, a = t["_meta"], t["attributes"]
        venue, how = matcher.match(supplier_code=m.get("supplierCode"), supplier_name=m.get("supplierName"),
                                   name=t["name"], slug=m.get("imageUrlSlug"), destination_hint=t["destination"])
        if venue is None:
            stats["vé không khớp địa điểm nào"] += 1
            continue
        a["venue"] = venue.name
        venue.tickets += 1
        if venue.destination and venue.destination != t["destination"] and (how == "supplier" or not destination_in_text(ticket_place_name(t["name"]))):
            a["originalDestination"] = t["destination"]
            t["destination"] = venue.destination
            stats["vé đổi điểm đến theo địa điểm"] += 1
        if m.get("locationOverride"):
            continue
        if venue.usable:
            a["latitude"], a["longitude"] = venue.latitude, venue.longitude
            a["locationSource"], a["locationPrecision"] = venue.source_family, "venue"
            stats["vé có toạ độ địa điểm"] += 1
        else:
            stats["vé thuộc địa điểm chưa có toạ độ dùng được"] += 1
    return stats


def link_pois_to_venues(pois: list[dict], venues: list[Venue]) -> None:
    """Điểm tham quan trip.com đang là nguồn toạ độ của một địa điểm (source trip.com:<id>) → chung ghim với vé ở đó."""
    by_ref = {f"trip:attraction:{v.source.split(':', 1)[1]}": v for v in venues if v.usable and v.source.startswith("trip.com:")}
    for p in pois:
        venue = by_ref.get(p["sourceRef"])
        if venue:
            p["attributes"]["venue"] = venue.name


def finalize_locations(products: list[dict]) -> None:
    """Toạ độ luôn đủ cặp; ghi nguồn/độ chính xác còn thiếu; cảnh báo toạ độ xa tâm điểm đến (trừ sân bay)."""
    for p in products:
        a = p["attributes"]
        if a.get("latitude") is None or a.get("longitude") is None:
            for f in LOCATION_FIELDS:
                a.pop(f, None)
            continue
        src = p["_meta"].get("src")
        if "locationSource" not in a:
            a["locationSource"] = "trip.com" if a.get("poiRef") else LOCATION_SOURCE.get(src, src)
        if "locationPrecision" not in a:
            a["locationPrecision"] = "poi" if a.get("poiRef") else "exact"
        if a["locationPrecision"] != "airport" and "locationWarning" not in a:
            km = km_from_destination(p["destination"], a["latitude"], a["longitude"])
            if km is not None and km > destination_radius_km(p["destination"]):
                a["locationWarning"] = f"cách tâm {p['destination']} {km:.0f} km"


# Sản phẩm của chính Vinpearl và khách sạn mang thương hiệu Vinpearl trên Booking luôn được giữ (quy tắc sẵn có của
# normalise/plan), kể cả khi toạ độ bị cảnh báo: dòng vẫn mang locationWarning để soát sau.
KEEP_DESPITE_LOCATION_WARNING = ("vinpearl:",)
VINPEARL_BRAND = re.compile(r"\b(vinpearl|vinholidays)\b")


def _remove_with_children(products: list[dict], reasons: dict[str, str]) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Xoá các dòng trong `reasons` (productId → lý do) cùng mọi dòng con (hạng phòng của khách sạn, chuyến bay của tuyến)."""
    reasons = dict(reasons)
    grew = True
    while grew:
        grew = False
        for p in products:
            if p["attributes"].get("parentProductId") in reasons and p["productId"] not in reasons:
                reasons[p["productId"]] = "thuộc sản phẩm bị xoá"
                grew = True
    kept = [p for p in products if p["productId"] not in reasons]
    removed = [(p, reasons[p["productId"]]) for p in products if p["productId"] in reasons]
    return kept, removed


def _protected(p: dict) -> bool:
    return p["sourceRef"].startswith(KEEP_DESPITE_LOCATION_WARNING) or bool(VINPEARL_BRAND.search(fold(p["name"])))


def drop_location_warnings(products: list[dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Xoá dòng có attributes.locationWarning (toạ độ nằm ngoài bán kính điểm đến hoặc bị nghi sai), kèm mọi hạng phòng /
    chuyến bay con của dòng bị xoá để không có dòng mồ côi (catalog.py merge từ chối parent thiếu).
    Trả (dòng còn lại, [(dòng bị xoá, lý do)]). Sản phẩm và khách sạn thương hiệu Vinpearl không bị xoá."""
    reasons = {}
    for p in products:
        warning = p["attributes"].get("locationWarning")
        if warning and not _protected(p):
            reasons[p["productId"]] = ("cảnh báo vị trí: toạ độ xa tâm điểm đến" if str(warning).startswith("cách tâm")
                                       else f"cảnh báo vị trí: {str(warning)[:80]}")
    return _remove_with_children(products, reasons)


def drop_missing_coordinates(products: list[dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Xoá dòng không có toạ độ hợp lệ (không lên được bản đồ, không kiểm tra được điểm đến), kèm dòng con. Vinpearl được giữ."""
    reasons = {p["productId"]: "thiếu toạ độ" for p in products
               if (p["attributes"].get("latitude") is None or p["attributes"].get("longitude") is None) and not _protected(p)}
    return _remove_with_children(products, reasons)


# Hạng phòng cao cấp có thể đắt gấp nhiều lần phòng thường cùng khách sạn: giữ nếu tên nói rõ là suite / biệt thự / ...
LUXURY_ROOM = re.compile(r"\b(suite|villa|biet thu|penthouse|presidential|tong thong|estate|mansion|duplex|residence)\b")
PRICE_OUTLIER_RATIO = 8.0
PRICE_OUTLIER_FLOOR = 10_000_000  # VND / đêm


def drop_price_outliers(products: list[dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Xoá hạng phòng có giá phi lý so với các hạng phòng khác của cùng khách sạn: >= 10 triệu/đêm VÀ > 8 lần giá trung vị của
    khách sạn (cần >= 3 hạng phòng để so). Chính nguồn ghi giá đó (vd. Booking: "Phòng Giường Đôi Nhỏ" 132.000.000 ₫ trong khi các phòng
    khác ~1 triệu), nên đây là lỗi của nguồn chứ không phải lỗi parse. Tên có suite / biệt thự / tổng thống / ... được giữ vì đắt là
    hợp lý; sản phẩm Vinpearl (giá do chính Vinpearl công bố) cũng được giữ."""
    rooms_of: dict[str, list[dict]] = defaultdict(list)
    for p in products:
        a = p["attributes"]
        if p["taxonomy"] == "hotel" and a.get("level") == "room" and p.get("unitPrice") and a.get("parentProductId"):
            rooms_of[a["parentProductId"]].append(p)
    reasons: dict[str, str] = {}
    for rooms in rooms_of.values():
        if len(rooms) < 3:
            continue
        median = _median([int(r["unitPrice"]) for r in rooms])
        for r in rooms:
            price = r["unitPrice"]
            if (price >= PRICE_OUTLIER_FLOOR and price > PRICE_OUTLIER_RATIO * median
                    and not LUXURY_ROOM.search(fold(r["name"])) and not _protected(r)):
                reasons[r["productId"]] = (f"giá phòng bất thường: {price / median:.0f}× giá trung vị các hạng phòng cùng khách sạn "
                                           f"({median:,} ₫)".replace(",", "."))
    return _remove_with_children(products, reasons)


def drop_orphans(products: list[dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Xoá hạng phòng / chuyến bay mà dòng cha đã bị loại ở bước khác (vd. khách sạn không có giá)."""
    ids = {p["productId"] for p in products}
    reasons = {p["productId"]: "thuộc sản phẩm cha đã bị loại" for p in products
               if p["attributes"].get("parentProductId") and p["attributes"]["parentProductId"] not in ids}
    return _remove_with_children(products, reasons)


def write_location_exclusions(removed: list[tuple[dict, str]], path: Path) -> None:
    """Danh sách dòng bị xoá vì lỗi dữ liệu (cảnh báo vị trí, thiếu toạ độ, mồ côi), để truy vết; không cần kiểm tra thủ công."""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sourceRef", "name", "taxonomy", "level", "destination", "latitude", "longitude", "locationSource", "reason"])
        for p, reason in removed:
            a = p["attributes"]
            w.writerow([p["sourceRef"], p["name"], p["taxonomy"], a.get("level") or "", p["destination"] or "",
                        a.get("latitude"), a.get("longitude"), a.get("locationSource") or "", reason])


# ---------------------------------------------------------------------- tỉnh / thành


# Các nguồn ghi tỉnh theo nhiều kiểu: "Khu vực TP. Hồ Chí Minh", "Thành phố Đà Nẵng", "Đảo Phú Quốc".
# Đưa về một tên chuẩn để lọc và nhóm được; "Việt Nam" không phải tỉnh nên bỏ hẳn.
PROVINCE_CANONICAL = {
    "khu vuc tp ho chi minh": "TP. Hồ Chí Minh",
    "thanh pho ho chi minh": "TP. Hồ Chí Minh",
    "ho chi minh": "TP. Hồ Chí Minh",
    "thanh pho da nang": "Đà Nẵng",
    "thua thien hue": "Thừa Thiên Huế",
    "dao phu quoc": "Kiên Giang",
    "bac ninh": "Bắc Ninh",
    "khanh hoa": "Khánh Hòa",
    "thanh hoa": "Thanh Hóa",
}
NOT_A_PROVINCE = {"viet nam", "vietnam", "vn"}


def canonical_province(raw: str | None) -> str | None:
    if not raw:
        return None
    key = fold(raw)
    if key in NOT_A_PROVINCE:
        return None
    return PROVINCE_CANONICAL.get(key, raw.strip())


def tidy_attributes(products: list[dict]) -> Counter:
    """Chuẩn hoá tỉnh/thành và kiểu số của thuộc tính phòng, sau khi mọi nguồn đã được gộp."""
    stats: Counter = Counter()
    for p in products:
        a = p["attributes"]
        raw = a.get("province")
        if raw:
            canon = canonical_province(raw)
            if canon is None:
                a.pop("province", None)
                stats["bỏ giá trị không phải tỉnh"] += 1
            elif canon != raw:
                a["province"] = canon
                stats["tỉnh/thành đưa về tên chuẩn"] += 1
        size = a.get("roomSizeM2")
        if isinstance(size, float):          # nguồn trả lẫn 56 và 56.0
            a["roomSizeM2"] = int(size) if size == int(size) else round(size, 1)
            stats["diện tích phòng về một kiểu số"] += 1
    return stats


# ---------------------------------------------------------------------- mô tả tiếng Việt


VI_PROPERTY_TYPE = {
    "resort": "khu nghỉ dưỡng", "hotel": "khách sạn", "apartment": "căn hộ", "aparthotel": "căn hộ khách sạn",
    "villa": "biệt thự", "homestay": "homestay", "hostel": "nhà nghỉ", "guesthouse": "nhà khách",
    "condotel": "condotel", "motel": "nhà nghỉ", "bed and breakfast": "nhà nghỉ kèm bữa sáng",
}


def vietnamese_description(p: dict) -> str | None:
    """Dựng mô tả tiếng Việt từ thuộc tính có cấu trúc.

    Tiện ích của booking.com và agoda.com vốn đã là tiếng Việt, nên phần lớn nội dung vẫn là chữ của nguồn
    chứ không phải chữ tự nghĩ ra.
    """
    a = p["attributes"]
    where = a.get("city") or a.get("province") or p.get("destination")
    parts = []
    if p["taxonomy"] in ("attraction", "combo", "golf"):
        parts.append(f"{p['name']} tại {where}." if where else f"{p['name']}.")
        if a.get("tags"):
            parts.append("Loại hình: " + ", ".join(a["tags"]) + ".")
        if a.get("openingHours"):
            parts.append(f"Giờ mở cửa: {a['openingHours']}.")
        if a.get("suggestedDuration"):
            parts.append(f"Thời gian tham quan đề xuất: {a['suggestedDuration']}.")
    elif a.get("level") == "room":
        opening = a.get("roomName") or p["name"]
        if a.get("hotelName"):
            opening += f" thuộc {a['hotelName']}"
        if where:
            opening += f", {where}"
        parts.append(opening + ".")
        detail = []
        if a.get("roomSizeM2"):
            detail.append(f"diện tích {a['roomSizeM2']} m²")
        if a.get("maxOccupancy"):
            detail.append(f"sức chứa tối đa {a['maxOccupancy']} khách")
        if a.get("bed"):
            detail.append(str(a["bed"]).strip().lower())
        if detail:
            parts.append("Phòng " + ", ".join(detail) + ".")
    else:
        kind = VI_PROPERTY_TYPE.get(fold(a.get("propertyType") or ""), "cơ sở lưu trú")
        star = f" {a['starRating']:g} sao" if isinstance(a.get("starRating"), (int, float)) else ""
        parts.append(f"{p['name']} là {kind}{star}" + (f" tại {where}." if where else "."))
    if a.get("address"):
        parts.append(f"Địa chỉ: {a['address']}.")
    amenities = [x for x in (a.get("amenities") or []) if x][:12]
    if amenities:
        parts.append("Tiện ích: " + ", ".join(amenities) + ".")
    if a.get("reviewScore"):
        scale = a.get("reviewScoreScale") or 10
        count = f" từ {a['reviewCount']} lượt đánh giá" if a.get("reviewCount") else ""
        parts.append(f"Điểm đánh giá {a['reviewScore']:g}/{scale:g}{count}.")
    text = " ".join(parts)
    return text if len(text) >= 80 else None


def localise_descriptions(products: list[dict]) -> int:
    """Sản phẩm mà nguồn chỉ có mô tả tiếng Anh được dựng lại mô tả tiếng Việt từ thuộc tính có cấu trúc.

    Văn bản gốc không bị xoá: nó chuyển sang attributes.descriptionOriginal để còn đối chiếu.
    Hạng phòng ghép mô tả từ khách sạn cha nên cũng được dựng lại, không chỉ riêng cơ sở lưu trú.
    """
    localised = 0
    for p in products:
        a = p["attributes"]
        if a.get("descriptionLang") == "vi":
            continue
        text = vietnamese_description(p)
        if not text or detect_lang(text) != "vi":
            continue
        a["descriptionOriginal"] = p.get("description")
        p["description"] = text
        a["descriptionSource"] = "derived: dựng tiếng Việt từ thuộc tính (mô tả gốc không phải tiếng Việt)"
        a["descriptionLang"] = "vi"
        localised += 1
    return localised


# ---------------------------------------------------------------------- biến thể giá thành viên


def merge_member_variants(products: list[dict]) -> tuple[list[dict], int]:
    """Gộp [VIN33 - Gold/Platinum/Diamond] về một sản phẩm, giá từng hạng giữ lại trong attributes.memberPrices.

    Không xoá thẳng mọi biến thể: 5 trong 18 vé chỉ tồn tại dưới dạng biến thể thành viên, xoá hết là mất
    sản phẩm thật. Vé nào không có bản không-hạng thì giữ lại hạng giá cao nhất (gần giá công bố nhất).
    """
    by_base: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for p in products:
        if p["attributes"].get("memberTier"):
            by_base[(base_ticket_name(p["name"]), p["destination"])].append(p)
    plain = {(base_ticket_name(p["name"]), p["destination"]): p
             for p in products if not p["attributes"].get("memberTier")}
    dropped_ids: set[str] = set()
    for key, variants in by_base.items():
        keeper = plain.get(key)
        if keeper is None:
            keeper = max(variants, key=lambda v: (v.get("unitPrice") or 0))
            keeper["name"] = key[0]
            keeper["attributes"].pop("memberTier", None)
        prices = {v["attributes"]["memberTier"]: v.get("unitPrice")
                  for v in variants if v.get("unitPrice") and v["attributes"].get("memberTier")}
        if prices:
            keeper["attributes"]["memberPrices"] = prices
        dropped_ids.update(v["productId"] for v in variants if v is not keeper)
    return [p for p in products if p["productId"] not in dropped_ids], len(dropped_ids)


# ---------------------------------------------------------------------- kế hoạch


def drop_unsellable(products: list[dict]) -> tuple[list[dict], int]:
    """Bỏ sản phẩm không có giá mà nguồn cũng không cung cấp được: không đặt được, mô tả gần như trống.

    Đã thử lấy lại bằng `crawl.py retry-missing`; API chi tiết của Vinpearl trả HTTP 500 cho các vé này và
    agoda không trả giá cho nhiều ngày nhận phòng khác nhau.

    Không áp dụng cho điểm tham quan của trip.com (`trip:attraction:`): đó là địa điểm, trip.com không hiện giá thì chưa rõ
    có bán vé hay không, nên giữ dòng với `unitPrice = null` (KHÔNG kết luận "miễn phí"). Hạng phòng của khách sạn bị loại do
    apply_plan dọn theo.
    """
    keep, removed = [], 0
    for p in products:
        a = p["attributes"]
        if (p.get("unitPrice") is None and a.get("ticketed") is not False
                and a.get("level") not in ("room", "flight")
                and not p["sourceRef"].startswith("trip:attraction:")):
            removed += 1
            continue
        keep.append(p)
    return keep, removed


def apply_plan(products: list[dict], plan_names: set[str], budget: Budget, dropped: Counter) -> list[dict]:
    caps = {"booking": budget.booking_hotels, "agoda": budget.agoda_hotels, "trip_attraction": budget.trip_attractions,
            "booking_attraction": 10}
    groups: dict[tuple, list[dict]] = defaultdict(list)
    keep: list[dict] = []
    kept_ids: set[str] = set()
    for p in products:
        src = p["_meta"].get("src")
        level = p["attributes"].get("level")
        if level in ("room", "flight"):
            continue  # đi theo sản phẩm cha
        if src == "vinpearl" or p["attributes"].get("brand") == "Vinpearl":
            keep.append(p)
            kept_ids.add(p["productId"])
            continue
        if src in ("trip_flight", "booking_flight"):
            if p["destination"] in plan_names and p["_meta"].get("fromDestination") in plan_names:
                keep.append(p)
                kept_ids.add(p["productId"])
            else:
                dropped["tuyến bay ngoài kế hoạch"] += 1
            continue
        if p["destination"] not in plan_names:
            dropped[f"{src}: ngoài {len(plan_names)} điểm đến kế hoạch"] += 1
            continue
        groups[(src, p["destination"])].append(p)
    for (src, dest), items in groups.items():
        items.sort(key=lambda p: ((p["_meta"].get("plan") or {}).get("rank") or 10**6, -(p["attributes"].get("reviewCount") or 0)))
        cap = caps.get(src, 10**6)
        for p in items[:cap]:
            keep.append(p)
            kept_ids.add(p["productId"])
        if len(items) > cap:
            dropped[f"{src}: vượt {cap}/điểm đến"] += len(items) - cap
    for p in products:
        if p["attributes"].get("level") in ("room", "flight"):
            if p["attributes"].get("parentProductId") in kept_ids:
                keep.append(p)
            else:
                dropped[f"{p['attributes']['level']} của sản phẩm bị loại"] += 1
    return keep


# ---------------------------------------------------------------------- đầu ra


def write_outputs(products: list[dict], data: Path, report_rows: list[list], dropped: Counter, plan_names: set[str],
                  location_stats: Counter | None = None, venues: list[Venue] | None = None) -> None:
    clean = [{k: p[k] for k in PRODUCT_FIELDS} for p in products]
    jl = data / "products.jsonl"
    with open(jl, "w", encoding="utf-8") as f:
        for p in clean:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    with open(data / "products.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(PRODUCT_FIELDS)
        for p in clean:
            w.writerow([json.dumps(p[k], ensure_ascii=False) if k == "attributes" else ("" if p[k] is None else p[k]) for k in PRODUCT_FIELDS])
    with open(data / "dedup_report.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kind", "score", "distance_m", "destination", "kept_name", "kept_sourceRef", "merged_name", "merged_sourceRef"])
        w.writerows(report_rows)
    map_info = mapexport.write_map(clean, data / "map", venues or [])
    write_quality_review(clean, data / "quality_review.csv")
    write_stats(clean, data / "stats.md", len(report_rows), dropped, plan_names, location_stats or Counter(), map_info)
    log.info("Đã ghi %d sản phẩm → %s (+ products.csv, dedup_report.csv, quality_review.csv, stats.md, map/)", len(clean), jl)


def write_quality_review(products: list[dict], path: Path) -> None:
    """Danh sách kiểm tra cập nhật cùng catalog; thiếu giá không đồng nghĩa miễn phí hoặc hết vé."""
    fields = ["issues", "name", "taxonomy", "level", "destination", "sourceRef", "url", "descriptionLang",
              "unitPrice", "latitude", "longitude"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for p in products:
            a, issues = p["attributes"], []
            if p.get("unitPrice") is None:
                # trip.com không hiện giá ≠ miễn phí: chưa rõ có bán vé không
                issues.append("chưa có thông tin giá (trip.com không hiện giá, chưa rõ có bán vé không)"
                              if p["sourceRef"].startswith("trip:attraction:") else "thiếu giá: cần đối chiếu nguồn")
            if not p.get("description"):
                issues.append("thiếu mô tả")
            elif a.get("descriptionLang") != "vi":
                issues.append("cần đọc lại ngôn ngữ mô tả")
            if a.get("latitude") is None or a.get("longitude") is None:
                issues.append("thiếu tọa độ")
            if not p.get("imageUrl"):
                # vé máy bay không có ảnh sản phẩm: dùng logo hãng qua attributes.airlineCode / airlines
                issues.append("không có ảnh: dùng logo hãng bay" if p["taxonomy"] == "flight" else "thiếu ảnh")
            if a.get("locationWarning"):
                issues.append(a["locationWarning"])
            if issues:
                writer.writerow({"issues": "; ".join(issues), **{k: p.get(k) for k in ("name", "taxonomy", "destination", "sourceRef", "unitPrice")},
                                 **{k: a.get(k) for k in ("level", "url", "descriptionLang", "latitude", "longitude")}})


def write_stats(products: list[dict], path: Path, merged: int, dropped: Counter, plan_names: set[str],
                location_stats: Counter | None = None, map_info: dict | None = None) -> None:
    n = len(products)
    by_src = Counter(p["sourceRef"].split(":")[0] for p in products)
    by_tax = Counter(p["taxonomy"] for p in products)
    by_level = Counter(f"{p['taxonomy']}/{p['attributes'].get('level', '-')}" for p in products)
    by_dest = Counter(p["destination"] or "(không rõ)" for p in products)
    with_desc = [p for p in products if p.get("description")]
    vi_desc = [p for p in with_desc if p["attributes"].get("descriptionLang") == "vi"]
    priced = [p for p in products if p.get("unitPrice")]
    available = [p for p in products if p.get("available")]
    coords = [p for p in products if p["attributes"].get("latitude") is not None]
    dest_ok = [d for d, c in by_dest.items() if d in plan_names and c >= 20]
    tax_needed = {"hotel", "flight", "attraction", "combo"}

    def ok(flag: bool) -> str:
        return "✅" if flag else "⚠️"

    lines = [
        "# Thống kê catalog",
        "",
        f"Tạo lúc {date.today().isoformat()} · **{n} sản phẩm**",
        "",
        "## Đối chiếu handbook §3",
        "",
        "| Mục tiêu | Thực tế | |",
        "|---|---|---|",
        f"| 2.000–5.000 sản phẩm | {n} | {ok(TARGET_MIN <= n <= TARGET_MAX)} |",
        f"| 10–15 điểm đến (≥ 20 sản phẩm mỗi nơi) | {len(dest_ok)} | {ok(10 <= len(dest_ok) <= 15)} |",
        f"| Đủ hotel, flight, attraction, combo | {', '.join(sorted(by_tax))} | {ok(tax_needed <= set(by_tax))} |",
        f"| Mô tả được nhận diện là tiếng Việt | {len(vi_desc)} ({_pct(len(vi_desc), n)}) | {ok(len(vi_desc) >= 0.7 * n)} |",
        f"| Có giá | {len(priced)} ({_pct(len(priced), n)}) | {ok(len(priced) >= 0.8 * n)} |",
        f"| Được đánh dấu available trong dữ liệu | {len(available)} ({_pct(len(available), n)}) | |",
        f"| Có toạ độ | {len(coords)} ({_pct(len(coords), n)}) | |",
        f"| Sản phẩm trùng giữa các nguồn đã gộp | {merged} | |",
        "",
        "Nhãn ngôn ngữ được ước lượng từ tỷ lệ ký tự có dấu trong mô tả; không xác nhận tên hoặc toàn bộ nội dung đã là tiếng Việt. Cần đọc tay các mẫu bên dưới.",
        "Cờ available được suy ra từ dữ liệu nguồn và giá tại thời điểm crawl; chưa xác minh đặt chỗ hiện tại. Các trường còn thiếu được liệt kê trong `quality_review.csv`.",
        (f"Trong {n - len(priced)} sản phẩm không có giá, {sum(1 for p in products if p.get('unitPrice') is None and p['sourceRef'].startswith('trip:attraction:'))} "
         "là điểm tham quan trip.com không hiện giá (chưa rõ có bán vé hay không, `unitPrice = null`, không phải miễn phí); phần còn lại mới là thiếu giá cần đối chiếu nguồn."),
        "",
        "## Điểm đến × loại sản phẩm",
        "",
        "| Điểm đến | hotel | flight | attraction | combo | golf | tổng |",
        "|---|---|---|---|---|---|---|",
    ]
    matrix: dict[str, Counter] = defaultdict(Counter)
    for p in products:
        matrix[p["destination"] or "(không rõ)"][p["taxonomy"]] += 1
    for dest, _ in by_dest.most_common():
        c = matrix[dest]
        mark = "" if dest in plan_names else " *(ngoài kế hoạch)*"
        lines.append(f"| {dest}{mark} | {c['hotel']} | {c['flight']} | {c['attraction']} | {c['combo']} | {c['golf']} | {sum(c.values())} |")
    lines += [
        "",
        "## Theo nguồn", "", *[f"- {k}: {v}" for k, v in by_src.most_common()],
        "", "## Theo loại / cấp", "", *[f"- {k}: {v}" for k, v in sorted(by_level.items())],
        "", f"Độ dài mô tả trung vị: {_median([len(p['description']) for p in with_desc])} ký tự",
    ]
    if dropped:
        lines += ["", "## Bị loại", "", *[f"- {k}: {v}" for k, v in dropped.most_common()]]
    lines += location_section(products, location_stats or Counter(), map_info or {})
    lines += ["", "## Mẫu để đọc tay (kiểm tra chất lượng tên + mô tả)", ""]
    pool = [p for p in products if p["attributes"].get("level") not in ("room", "flight")]
    step = max(1, len(pool) // 15)
    for p in pool[::step][:15]:
        desc = (p.get("description") or "").replace("\n", " ")[:280].rstrip()
        lines.append(f"- **{p['name']}** · {p['taxonomy']} · {p['destination']} · {p.get('unitPrice')} VND\n\n  {desc}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def location_section(products: list[dict], location_stats: Counter, map_info: dict) -> list[str]:
    by_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    sources: Counter = Counter()
    precision: Counter = Counter()
    for p in products:
        a = p["attributes"]
        row = by_kind[f"{p['taxonomy']}/{a.get('level', '-')}"]
        row[0] += 1
        if a.get("latitude") is not None:
            row[1] += 1
            sources[a.get("locationSource")] += 1
            precision[a.get("locationPrecision")] += 1
    warnings = [p for p in products if p["attributes"].get("locationWarning") and p["attributes"].get("level") != "room"]
    lines = ["", "## Vị trí (toạ độ)", "", "| Loại / cấp | Sản phẩm | Có toạ độ | |", "|---|---|---|---|"]
    for kind, (total, with_coords) in sorted(by_kind.items()):
        lines.append(f"| {kind} | {total} | {with_coords} | {_pct(with_coords, total)} |")
    lines += [
        "",
        "Nguồn toạ độ: " + ", ".join(f"{k} {v}" for k, v in sources.most_common()),
        "",
        "Độ chính xác: " + ", ".join(f"{k} {v}" for k, v in precision.most_common())
        + " (exact = vị trí riêng của sản phẩm; venue = khu vui chơi/sân golf dùng vé; poi = điểm tham quan trip.com; airport = sân bay đến)",
    ]
    if location_stats:
        lines += ["", *[f"- {k}: {v}" for k, v in location_stats.most_common()]]
    if warnings:
        lines += ["", f"Cảnh báo toạ độ ({len(warnings)} sản phẩm, không tính hạng phòng):", ""]
        lines += [f"- {p['name']} · {p['destination']} · {p['attributes']['locationWarning']}" for p in warnings[:20]]
    if map_info:
        lines += ["", f"Bản đồ: {map_info.get('places', 0)} ghim trong `map/` ({', '.join(map_info.get('files', []))}). "
                      f"Cần kiểm tra tay: {map_info.get('review', 0)} dòng trong `map/can-kiem-tra.csv`."]
    return lines


def _pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "0%"


def _median(xs: list[int]) -> int:
    return sorted(xs)[len(xs) // 2] if xs else 0


# ---------------------------------------------------------------------- ảnh chụp từng bước (monitor)

STAGES = (
    ("mapped", "Ánh xạ từng nguồn → dòng 13 trường", "mỗi bản ghi interim thành khách sạn + hạng phòng, vé, điểm tham quan, "
     "tuyến bay + chuyến, combo; trước khi sửa điểm đến/toạ độ tay và trước khi gộp trùng"),
    ("merged", "Gộp trùng giữa các nguồn", "khách sạn cùng nơi gộp thành một (vinpearl thắng tên/mô tả, OTA thắng giá), "
     "điểm tham quan trip.com trùng vé Vinpearl gộp vào vé, thêm vé máy bay và combo"),
    ("filtered", "Lọc", "bỏ dòng đã soát tay, không phải điểm du lịch, không bán được, ngoài kế hoạch, trùng hoặc thiếu tên"),
    ("enriched", "Làm giàu", "chuẩn hoá thuộc tính và tỉnh, dựng mô tả tiếng Việt, gộp biến thể giá thành viên Vinpearl"),
    ("final", "Kiểm vị trí và giá → products.jsonl", "xoá dòng cảnh báo vị trí / thiếu toạ độ / giá phòng bất thường / "
     "dòng con mồ côi (theo cờ --keep-* của lượt)"),
)


class StepClock:
    """Thời gian, số dòng vào/ra và RAM đỉnh của từng bước normalize → `<stage-dir>/steps.json` + log `normalise.step.*`.

    Mỗi bước mở bằng `begin()`; bước mới tự đóng bước trước. File được ghi lại mỗi lần đổi bước: normalize chết giữa
    chừng thì bước cuối còn "running" chính là bước lỗi. Không có `--stage-dir` thì chỉ log."""

    def __init__(self, directory: Path | None):
        self.path = Path(directory) / "steps.json" if directory else None
        self.steps: list[dict] = []
        self._t0 = 0.0

    def begin(self, name: str, rows_in: int | None = None, done: int | None = None) -> None:
        """Mở bước `name`; `done` = số dòng ra của bước trước (bước trước tự đóng)."""
        self.end(done)
        self._t0 = time.monotonic()
        self.steps.append({"name": name, "status": "running", "rowsIn": rows_in, "rowsOut": None, "seconds": None,
                           "peakRssMb": None, "startedAt": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        log.info("normalise.step.start name=%s in=%s", name, rows_in)
        self._save()

    def end(self, rows_out: int | None = None) -> None:
        if not self.steps or self.steps[-1]["status"] != "running":
            return
        step = self.steps[-1]
        # ru_maxrss: KB trên Linux; là RAM đỉnh của cả tiến trình tính tới hết bước này
        step.update(status="ok", rowsOut=rows_out, seconds=round(time.monotonic() - self._t0, 3),
                    peakRssMb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024))
        log.info("normalise.step.done name=%s seconds=%s in=%s out=%s", step["name"], step["seconds"],
                 step["rowsIn"], rows_out)
        self._save()

    def fail(self, exc: BaseException) -> None:
        """Đánh dấu bước đang chạy là lỗi, kèm traceback rút gọn (40 dòng cuối), rồi log để job.log có tên bước."""
        if not self.steps or self.steps[-1]["status"] != "running":
            return
        step = self.steps[-1]
        step.update(status="error", seconds=round(time.monotonic() - self._t0, 3),
                    error=f"{type(exc).__name__}: {exc}"[:1000],
                    traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-6000:])
        log.error("normalise.step.failed name=%s error=%s", step["name"], step["error"], exc_info=exc)
        self._save()

    def _save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"steps": self.steps}, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)


class RecordErrorRateExceeded(RuntimeError):
    """Quá nhiều bản ghi của một nguồn lỗi khi ánh xạ: nhiều khả năng lỗi code hoặc nguồn đổi định dạng, không phải lỗi lẻ."""


class RecordGuard:
    """Ánh xạ từng bản ghi interim: bản ghi lỗi được ghi vào `<stage-dir>/errors.jsonl` (bước, nguồn, khoá bản ghi, lỗi,
    traceback rút gọn) và bỏ qua, thay vì làm sập cả normalize.

    Ngưỡng an toàn: một nguồn có từ `MIN_ERRORS` bản ghi lỗi trở lên và tỉ lệ lỗi vượt `max_percent`, hoặc mọi bản ghi của
    nguồn đều lỗi, thì dừng với `RecordErrorRateExceeded`. Lỗi code làm hỏng mọi bản ghi không được lặng lẽ bỏ hết dữ liệu
    (như Vinpearl ra 0 tour ngày 25/09/2026)."""

    MIN_ERRORS = 3

    def __init__(self, directory: Path | None, max_percent: float):
        self.path = Path(directory) / "errors.jsonl" if directory else None
        self.max_percent = max_percent
        self.errors: list[dict] = []
        self.total: Counter = Counter()
        self.failed: Counter = Counter()

    def call(self, source: str, record: dict, fn, *args, default=None):
        self.total[source] += 1
        try:
            return fn(record, *args)
        except Exception as exc:
            self.failed[source] += 1
            entry = {"step": "ánh xạ nguồn", "source": source, "function": getattr(fn, "__name__", str(fn)),
                     "input": StageDump._input(record), "error": f"{type(exc).__name__}: {exc}"[:500],
                     "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-3000:]}
            self.errors.append(entry)
            log.warning("normalise.record.failed source=%s input=%s error=%s", source, entry["input"], entry["error"])
            return default

    def summary(self) -> dict:
        return {source: {"records": self.total[source], "errors": self.failed[source]} for source in self.total}

    def verdict(self, source: str) -> str | None:
        """Thông báo lỗi nếu nguồn vượt ngưỡng, None nếu đạt."""
        failed, total = self.failed[source], self.total[source]
        if failed and (failed == total or (failed >= self.MIN_ERRORS and failed * 100 > self.max_percent * total)):
            first = next(e["error"] for e in self.errors if e["source"] == source)
            return (f"{source}: {failed}/{total} bản ghi lỗi khi ánh xạ (> {self.max_percent:g}%), xem errors.jsonl; "
                    f"lỗi đầu: {first}")
        return None

    def check(self) -> None:
        self.write()
        for source in self.failed:
            message = self.verdict(source)
            if message:
                raise RecordErrorRateExceeded(message)

    def write(self) -> None:
        self.write_all(self.errors)

    def write_all(self, errors: list[dict]) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in errors), encoding="utf-8")


class StageDump:
    """`--stage-dir`: ghi dòng sản phẩm sau từng bước (`<bước>.jsonl.gz`), dòng bị loại kèm lý do (`dropped.jsonl.gz`), cặp
    gộp trùng (`merges.jsonl`) và tóm tắt (`stages.json`) để monitor xem normalize làm gì với từng dòng. Không đổi kết quả.

    Ghi ngay lúc chụp vì các bước sau sửa dict tại chỗ. Không có `--stage-dir` thì mọi hàm là no-op."""

    def __init__(self, directory: Path | None):
        self.dir = Path(directory) if directory else None
        self.counts: Counter = Counter()
        self.by_source: dict[str, Counter] = defaultdict(Counter)
        self.dropped: Counter = Counter()
        self.handles: dict[str, object] = {}
        if self.dir:
            self.dir.mkdir(parents=True, exist_ok=True)
            for old in self.dir.glob("*"):
                if old.is_file():
                    old.unlink()

    def _handle(self, name: str):
        if name not in self.handles:
            # mức nén 1: ảnh chụp chỉ để xem, mức mặc định 9 tốn ~1/3 thời gian normalize (đo 28/09/2026)
            self.handles[name] = gzip.open(self.dir / f"{name}.jsonl.gz", "wt", encoding="utf-8", compresslevel=1)
        return self.handles[name]

    @staticmethod
    def _input(record: dict | None) -> dict | None:
        if not record:
            return None
        ref = {k: record.get(k) for k in ("key", "hotelId", "poiId", "tourCode", "slug", "url", "recordType")
               if record.get(k) not in (None, "")}
        return ref or None

    @staticmethod
    def source_of(row: dict) -> str:
        """Nhãn nguồn dùng chung cho mọi bước: `_meta.src` do bộ ánh xạ đặt (vd. trip_attraction, booking, vinpearl)."""
        return (row.get("_meta") or {}).get("src") or (row.get("sourceRef") or "-").split(":")[0]

    def add(self, stage: str, rows, interim: str, record: dict | None = None, input: dict | None = None) -> None:
        """Dòng vừa ánh xạ từ một bản ghi của `interim/<interim>.jsonl` (`input`: khoá bản ghi đã rút gọn, nếu có sẵn)."""
        if not self.dir:
            return
        rows = [r for r in (rows or []) if r]
        handle = self._handle(stage)
        ref = input if input is not None else self._input(record)
        for row in rows:
            source = self.source_of(row)
            handle.write(json.dumps({"source": source, "interim": interim, "input": ref, "product": row},
                                    ensure_ascii=False, default=str) + "\n")
            self.by_source[stage][source] += 1
        self.counts[stage] += len(rows)

    def snapshot(self, stage: str, rows: list[dict]) -> None:
        if not self.dir:
            return
        handle = self._handle(stage)
        for row in rows:
            source = self.source_of(row)
            handle.write(json.dumps({"source": source, "product": row}, ensure_ascii=False, default=str) + "\n")
            self.by_source[stage][source] += 1
        self.counts[stage] += len(rows)

    def drop(self, step: str, removed: list[tuple[dict, str]]) -> None:
        if not self.dir or not removed:
            return
        handle = self._handle("dropped")
        for row, reason in removed:
            handle.write(json.dumps({"step": step, "reason": reason, "product": row}, ensure_ascii=False, default=str) + "\n")
            self.dropped[step] += 1

    def diff(self, step: str, before: list[dict], after: list[dict], reason: str) -> None:
        """Dòng có trong `before` mà không còn trong `after` (so theo đối tượng: các bước lọc không sao chép dict)."""
        if not self.dir:
            return
        kept = {id(p) for p in after}
        self.drop(step, [(p, reason) for p in before if id(p) not in kept])

    def close(self, merges: list[list], final: list[dict]) -> None:
        """`final`: dòng cuối (products.jsonl đã ghi riêng) — chỉ đếm theo nguồn, không ghi lại."""
        if not self.dir:
            return
        for row in final:
            self.by_source["final"][self.source_of(row)] += 1
        final_rows = len(final)
        for handle in self.handles.values():
            handle.close()
        with open(self.dir / "merges.jsonl", "w", encoding="utf-8") as f:
            keys = ("kind", "score", "distanceM", "destination", "keptName", "keptRef", "mergedName", "mergedRef")
            for row in merges:
                f.write(json.dumps(dict(zip(keys, row)), ensure_ascii=False) + "\n")
        stages = []
        for stage, label, help_text in STAGES:
            rows = final_rows if stage == "final" else self.counts.get(stage, 0)
            stages.append({"id": stage, "label": label, "help": help_text, "rows": rows,
                           "file": "../products.jsonl" if stage == "final" else f"{stage}.jsonl.gz",
                           "bySource": dict(self.by_source.get(stage) or {})})
        summary = {"stages": stages, "dropped": dict(self.dropped), "merges": len(merges)}
        (self.dir / "stages.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    """Tham số dòng lệnh; normalise_stream dùng lại để ánh xạ theo phần với đúng tham số của bản theo lô."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=default_data_dir())
    ap.add_argument("--destinations", default=None, help="điểm đến kế hoạch (mặc định cả 15 trong collectors/plan.py)")
    ap.add_argument("--per-destination", type=int, default=None, help="số khách sạn/điểm tham quan tối đa mỗi điểm đến")
    ap.add_argument("--no-plan", action="store_true", help="giữ mọi sản phẩm đã crawl, không lọc theo kế hoạch")
    ap.add_argument("--rooms-per-hotel", type=int, default=None, help="số hạng phòng OTA giữ lại mỗi khách sạn (mặc định 3; 0 giữ tất cả)")
    ap.add_argument("--flights-per-route", type=int, default=0, help="số chuyến bay cụ thể mỗi tuyến (mặc định 0: giữ tất cả đã thu thập)")
    ap.add_argument("--match-threshold", type=float, default=88.0, help="điểm giống tên tối thiểu để ghép khách sạn giữa các nguồn")
    ap.add_argument("--min-description", type=int, default=0, help="loại sản phẩm có mô tả ngắn hơn N ký tự")
    ap.add_argument("--vietnamese-only", action="store_true", help="loại sản phẩm có mô tả không phải tiếng Việt")
    ap.add_argument("--keep-unsellable", action="store_true",
                    help="giữ cả sản phẩm không có giá mà nguồn không cung cấp được; mặc định loại bỏ")
    ap.add_argument("--keep-location-warnings", action="store_true",
                    help="giữ các dòng có attributes.locationWarning (mặc định xoá cùng hạng phòng/chuyến con; sản phẩm Vinpearl luôn giữ)")
    ap.add_argument("--keep-missing-coordinates", action="store_true",
                    help="giữ các dòng không có toạ độ (mặc định xoá cùng dòng con; sản phẩm Vinpearl luôn giữ)")
    ap.add_argument("--keep-price-outliers", action="store_true",
                    help="giữ các hạng phòng có giá phi lý so với phòng khác cùng khách sạn (mặc định xoá; xem drop_price_outliers)")
    ap.add_argument("--annotate-hotel-granularity", action="store_true",
                    help="thêm attributes.hasRoomRows / rentalUnit cho dòng khách sạn (mặc định tắt: không đổi form catalog)")
    ap.add_argument("--keep-member-variants", action="store_true",
                    help="giữ nguyên từng biến thể giá thành viên Vinpearl ([VIN33 - Gold]…); mặc định gộp về một sản phẩm")
    ap.add_argument("--usd-vnd", type=float, default=26300.0, help="tỷ giá dùng khi trang không trả VND")
    ap.add_argument("--eur-vnd", type=float, default=30500.0)
    ap.add_argument("--report-json", type=Path, default=None,
                    help="ghi số liệu từng bước (bản ghi thô → cụm gộp → dòng bị loại → dòng cuối) ra file JSON; không đổi kết quả")
    ap.add_argument("--stage-dir", type=Path, default=None,
                    help="ghi dòng sản phẩm sau từng bước + dòng bị loại kèm lý do (cho monitor); không đổi kết quả")
    ap.add_argument("--max-error-percent", type=float, default=5.0,
                    help="tỉ lệ bản ghi lỗi khi ánh xạ (%%) của một nguồn mà vượt thì dừng normalize (tối thiểu 3 bản ghi lỗi, "
                         "hoặc mọi bản ghi của nguồn đều lỗi); bản ghi lỗi lẻ tẻ chỉ bị bỏ và ghi vào errors.jsonl")
    ap.add_argument("--only-source", default=None, metavar="NGUỒN",
                    help="chỉ ánh xạ interim/<NGUỒN>.jsonl thành checkpoint (normalised/<NGUỒN>.jsonl) rồi dừng; "
                         "chạy riêng/song song cho từng nguồn, bước gộp chạy sau bằng --merge-only")
    ap.add_argument("--merge-only", action="store_true",
                    help="bỏ bước ánh xạ; gộp từ các checkpoint đã có (chạy lại từ bước gộp mà không ánh xạ lại)")
    ap.add_argument("--source-minimums", type=json.loads, default={},
                    help="ngưỡng bản ghi theo nguồn từ lượt tương đương, dùng bởi fresh_catalog")
    ap.add_argument("--allow-partial-sources", action="store_true",
                    help="cách ly nguồn lỗi/không có dòng, tiếp tục nguồn hợp lệ; ghi excludedSources trong report")
    ap.add_argument("--reuse-checkpoints", action="store_true",
                    help="chạy mặc định nhưng không ánh xạ lại nguồn đã có checkpoint còn mới (cùng file interim, cùng ngày, "
                         "cùng tham số ánh xạ, không vượt ngưỡng lỗi) — dùng ở cuối lượt sau khi từng nguồn đã chuẩn hoá")
    ap.add_argument("--checkpoint-dir", type=Path, default=None,
                    help="thư mục checkpoint theo nguồn (mặc định <data-dir>/normalised)")
    ap.add_argument("--today", type=date.fromisoformat, default=None,
                    help="ngày coi là hôm nay (YYYY-MM-DD) để output lặp lại được khi so/test; mặc định ngày máy")
    ap.add_argument("-v", "--verbose", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    if any(v is not None and v < 0 for v in (a.rooms_per_hotel, a.flights_per_route)):
        ap.error("rooms-per-hotel và flights-per-route phải >= 0 (0 giữ tất cả)")
    clock = StepClock(a.stage_dir)
    try:
        return _normalise(a, clock)
    except Exception as exc:
        clock.fail(exc)
        raise


# ---------------------------------------------------------------------- ánh xạ theo nguồn + checkpoint

# Thứ tự nguồn khi dựng lại danh sách khách sạn/vé/điểm tham quan ở bước gộp: giữ đúng thứ tự xử lý cũ để output không đổi.
HOTEL_SOURCES = ("vinpearl", "booking_hotels", "agoda_api", "agoda_hotels", "trip_hotels")
CHECKPOINT_DIR = "normalised"
MAPPER_VERSION = 4


def read_source(path: Path) -> list[dict]:
    """Bản ghi interim của một nguồn: bản mới nhất theo khoá (vé máy bay: lịch sử giá theo tuyến)."""
    return dedupe_source(path.stem, list(read_jsonl(path)))


def dedupe_source(stem: str, records: list[dict]) -> list[dict]:
    """Bỏ trùng theo khoá trên MỌI bản ghi đã đọc của nguồn (dùng chung cho bản theo lô và normalise_stream)."""
    return trip_route_history(records) if stem == "trip_flights" else latest_by_key(records)


def map_source(stem: str, records: list[dict], *, today: date, rates: dict, budget: Budget,
               guard: "RecordGuard") -> list[dict]:
    """Ánh xạ bản ghi interim của MỘT nguồn → mục checkpoint. Không phụ thuộc nguồn khác nên chạy riêng/song song được.

    Mục: `hotel` (prop + rooms, rooms None với agoda trình duyệt), `ticket`, `poi`, `attraction`, `routes`, `combo`,
    `bundle`, `record` (bản ghi gốc dùng ở bước gộp: chuyến bay booking). Bản ghi mapper trả None thì bỏ, như trước."""
    out: list[dict] = []

    def add(kind: str, record: dict, **fields) -> None:
        out.append({"kind": kind, "key": record.get("key"), "input": StageDump._input(record), **fields})

    for r in records:
        if stem == "vinpearl":
            if r.get("recordType") == "vinpearl_hotel":
                prop, rooms = guard.call(stem, r, vinpearl_hotel, default=(None, []))
                if prop:
                    add("hotel", r, prop=prop, rooms=rooms)
            elif r.get("recordType") == "vinpearl_tour":
                t = guard.call(stem, r, vinpearl_tour_product, today)
                if t:
                    add("ticket", r, row=t)
        elif stem == "booking_hotels":
            prop, rooms = guard.call(stem, r, booking_hotel, rates, default=(None, []))
            if prop:
                add("hotel", r, prop=prop, rooms=rooms)
        elif stem == "agoda_api":
            prop, rooms = guard.call(stem, r, agoda_api_hotel, rates, today, default=(None, []))
            if prop:
                add("hotel", r, prop=prop, rooms=rooms)
        elif stem == "agoda_hotels":
            prop = guard.call(stem, r, agoda_hotel, rates)
            if prop:
                add("hotel", r, prop=prop, rooms=None)
        elif stem == "trip_hotels":
            prop, rooms = guard.call(stem, r, trip_hotel, rates, default=(None, []))
            if prop:
                add("hotel", r, prop=prop, rooms=rooms)
        elif stem == "trip_attractions":
            poi = guard.call(stem, r, trip_attraction_product)
            if poi:
                add("poi", r, row=poi)
        elif stem == "booking_attractions":
            p = guard.call(stem, r, booking_attraction_product, rates)
            if p:
                add("attraction", r, row=p)
        elif stem == "trip_flights":
            routes = guard.call(stem, r, trip_route_products, budget.flights_per_route, default=[])
            add("routes", r, rows=routes)
        elif stem == "trip_combos":
            c = guard.call(stem, r, trip_combo_product)
            if c:
                add("combo", r, row=c)
        elif stem == "vinpearl_bundles":
            c = guard.call(stem, r, vinpearl_bundle_product, today)
            if c:
                add("bundle", r, row=c)
        elif stem == "booking_flights":
            add("record", r, record=r)
        # nguồn lạ (vd. booking_flight_offers ghi ra từ lần chạy trước): không ánh xạ, như trước
    return out


def entry_rows(entry: dict) -> list[dict]:
    """Dòng sản phẩm của một mục checkpoint (cho ảnh chụp bước `mapped`)."""
    if entry["kind"] == "hotel":
        return [entry["prop"], *(entry["rooms"] or [])]
    return list(entry.get("rows") or ([entry["row"]] if entry.get("row") else []))


def write_checkpoint(directory: Path, stem: str, entries: list[dict], meta: dict, errors: list[dict]) -> None:
    """`<dir>/<nguồn>.jsonl` (mục đã ánh xạ) + `.meta.json` (số bản ghi, lỗi, thời gian) + `.errors.jsonl`. Ghi tạm rồi đổi tên,
    nên bước gộp không đọc phải file dở."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in ((f"{stem}.jsonl", "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries)),
                       (f"{stem}.errors.jsonl", "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in errors)),
                       (f"{stem}.meta.json", json.dumps(meta, ensure_ascii=False, indent=1))):
        tmp = directory / f".{name}.tmp"
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(directory / name)


def checkpoint_fingerprint(interim: Path, today: date, rates: dict, budget: Budget) -> dict:
    """Những gì quyết định kết quả ánh xạ của một nguồn: file interim (mtime, cỡ) + ngày + tỷ giá + số chuyến mỗi tuyến."""
    st = interim.stat()
    return {"mapperVersion": MAPPER_VERSION, "interimMtimeNs": st.st_mtime_ns, "interimBytes": st.st_size, "today": today.isoformat(),
            "rates": rates, "flightsPerRoute": budget.flights_per_route}


def checkpoint_is_fresh(directory: Path, stem: str, fingerprint: dict) -> bool:
    meta = directory / f"{stem}.meta.json"
    if not meta.is_file() or not (directory / f"{stem}.jsonl").is_file():
        return False
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except ValueError:
        return False
    return data.get("status") == "ok" and all(data.get(k) == v for k, v in fingerprint.items())


def load_checkpoints(directory: Path) -> tuple[dict[str, list[dict]], dict[str, dict], list[dict]]:
    """(mục theo nguồn, meta theo nguồn, lỗi bản ghi) từ thư mục checkpoint."""
    entries, metas, errors = {}, {}, []
    for meta_path in sorted(directory.glob("*.meta.json")):
        stem = meta_path.name[:-len(".meta.json")]
        metas[stem] = json.loads(meta_path.read_text(encoding="utf-8"))
        # tách theo "\n", không dùng splitlines(): mô tả có U+2028/U+0085 (JSON giữ nguyên khi ensure_ascii=False)
        entries[stem] = [json.loads(line) for line in (directory / f"{stem}.jsonl").read_text(encoding="utf-8").split("\n")
                         if line.strip()]
        err = directory / f"{stem}.errors.jsonl"
        if err.is_file():
            errors += [json.loads(line) for line in err.read_text(encoding="utf-8").split("\n") if line.strip()]
    return entries, metas, errors


def _normalise(a: argparse.Namespace, clock: StepClock) -> int:
    paths = Paths(a.data_dir).ensure()
    setup_logging(paths, a.verbose)
    rates = {"USD": a.usd_vnd, "EUR": a.eur_vnd}
    today = a.today or date.today()
    budget = budget_with(a.per_destination, ota_rooms_per_hotel=a.rooms_per_hotel, flights_per_route=a.flights_per_route)
    checkpoints = a.checkpoint_dir or paths.data / CHECKPOINT_DIR

    if a.only_source or not a.merge_only:
        stems = [a.only_source] if a.only_source else [f.stem for f in sorted(paths.interim.glob("*.jsonl"))]
        clock.begin("đọc interim")
        read: dict[str, list[dict]] = {}
        for stem in stems:
            path = paths.interim / f"{stem}.jsonl"
            if not path.is_file():
                continue
            try:
                read[stem] = read_source(path)
            except Exception as exc:
                if not a.allow_partial_sources:
                    raise
                write_checkpoint(checkpoints, stem, [],
                                 {"source": stem, "status": "failed", "records": 0, "rows": 0,
                                  "error": f"{type(exc).__name__}: {exc}"}, [])
                continue
            log.info("Đọc %s: %d bản ghi", path.name, len(read[stem]))
        if not read and not a.allow_partial_sources:
            log.error("Không có dữ liệu trong %s. Chạy crawl.py trước.", paths.interim)
            clock.end(0)
            return 1
        records_read = sum(len(v) for v in read.values())
        clock.begin("ánh xạ nguồn", records_read, done=records_read)
        guard = RecordGuard(a.stage_dir, a.max_error_percent)
        mapped = 0
        for stem, records in read.items():
            fingerprint = checkpoint_fingerprint(paths.interim / f"{stem}.jsonl", today, rates, budget)
            if a.reuse_checkpoints and checkpoint_is_fresh(checkpoints, stem, fingerprint):
                log.info("normalise.source.reuse name=%s (checkpoint còn mới)", stem)
                continue
            started = time.monotonic()
            try:
                entries = map_source(stem, records, today=today, rates=rates, budget=budget, guard=guard)
            except Exception as exc:
                if not a.allow_partial_sources:
                    raise
                write_checkpoint(checkpoints, stem, [],
                                 {"source": stem, "status": "failed", "records": len(records), "rows": 0,
                                  "error": f"{type(exc).__name__}: {exc}", **fingerprint}, [])
                continue
            rows = sum(len(entry_rows(e)) for e in entries)
            mapped += rows
            verdict = guard.verdict(stem)
            write_checkpoint(checkpoints, stem, entries,
                             {"source": stem, "status": "failed" if verdict else "ok", "error": verdict,
                              "records": len(records), "entries": len(entries), "rows": rows,
                              "errors": guard.failed[stem], "seconds": round(time.monotonic() - started, 3),
                              **fingerprint},
                             [e for e in guard.errors if e["source"] == stem])
            log.info("normalise.source.done name=%s records=%d rows=%d errors=%d", stem, len(records), rows,
                     guard.failed[stem])
        if not a.allow_partial_sources:
            guard.check()  # vượt ngưỡng bản ghi lỗi của một nguồn thì dừng ở đây (sau khi đã ghi errors + meta "failed")
        if a.only_source:
            clock.end(mapped)
            return 0
        clock.begin("đọc checkpoint", mapped, done=mapped)
    else:
        clock.begin("đọc checkpoint")
    entries, metas, errors = load_checkpoints(checkpoints)
    for stem, minimum in a.source_minimums.items():
        if stem in metas and metas[stem].get('records', 0) < minimum:
            metas[stem].update(status='failed', error=f"Bản ghi giảm dưới ngưỡng {minimum}; giữ nguồn này để kiểm tra")
    excluded = {stem: m.get("error") or "Nguồn không có sản phẩm hợp lệ"
                for stem, m in metas.items() if m.get("status") == "failed" or not entries.get(stem)}
    if a.allow_partial_sources:
        for stem in excluded:
            entries.pop(stem, None)
    elif any(m.get("status") == "failed" for m in metas.values()):
        raise ValueError("Checkpoint nguồn lỗi; cần chuẩn hoá lại hoặc --allow-partial-sources")
    a.excluded_sources = excluded if a.allow_partial_sources else {}
    if not entries:
        log.error("Không có checkpoint trong %s. Chạy normalise.py --only-source trước.", checkpoints)
        clock.end(0)
        return 1
    return merge_catalog(a, clock, paths, entries, metas, errors, today, budget)


def merge_catalog(a: argparse.Namespace, clock: StepClock, paths: Paths, entries: dict[str, list[dict]],
                  metas: dict[str, dict], errors: list[dict], today: date, budget: Budget) -> int:
    """Phần sau ánh xạ, cần mọi nguồn: gộp trùng khách sạn/vé/chuyến bay, lọc, làm giàu, kiểm vị trí/giá, ghi output.
    Đọc từ checkpoint của từng nguồn (map_source); thứ tự dựng lại danh sách giống hệt luồng một khối trước đây."""
    destinations = select_destinations(a.destinations)
    plan_names = {d.name for d in destinations}
    dropped: Counter = Counter()
    report_rows: list[list] = []
    stage_report: dict = {"excludedSources": getattr(a, "excluded_sources", {}),
                          "recordsRead": {k: m["records"] for k, m in metas.items()}}  # chỉ để --report-json
    stages = StageDump(a.stage_dir)
    record_errors = {k: {"records": m["records"], "errors": m.get("errors", 0)} for k, m in metas.items()}
    if a.stage_dir:  # lỗi bản ghi của mọi nguồn về một file cho monitor
        RecordGuard(a.stage_dir, a.max_error_percent).write_all(errors)

    # dựng lại danh sách theo đúng thứ tự xử lý cũ
    agoda_api_keys = {e["key"] for e in entries.get("agoda_api", [])}
    props: list[dict] = []
    rooms_of: dict[str, list[dict]] = {}
    tickets: list[dict] = []
    for stem in HOTEL_SOURCES:
        for e in entries.get(stem, []):
            if e["kind"] == "ticket":
                tickets.append(e["row"])
                stages.add("mapped", [e["row"]], stem, input=e["input"])
                continue
            if stem == "agoda_hotels" and e["key"] in agoda_api_keys:
                continue  # bản cũ cùng key (cào bằng trình duyệt) thì bỏ, agoda API có hạng phòng + giá theo ngày
            props.append(e["prop"])
            if e["rooms"] is not None:
                rooms_of[e["prop"]["productId"]] = e["rooms"]
            stages.add("mapped", entry_rows(e), stem, input=e["input"])
    pois = [e["row"] for e in entries.get("trip_attractions", [])]
    for stem in ("trip_attractions", "booking_attractions", "trip_flights", "trip_combos", "vinpearl_bundles"):
        for e in entries.get(stem, []):
            stages.add("mapped", entry_rows(e), stem, input=e["input"])
    mapped = len(props) + sum(len(r or []) for r in rooms_of.values()) + len(tickets) + len(pois)
    clock.begin("sửa điểm đến, toạ độ", mapped, done=mapped)
    n_destination = apply_destination_overrides(props + tickets + pois, load_destination_overrides())
    location_stats = flag_suspect_hotel_coords(props)  # trước khi sửa tay: toạ độ gốc vẫn là bằng chứng cho khách sạn kia
    if n_destination:
        location_stats["điểm đến sửa theo bằng chứng (destination_overrides.csv)"] = n_destination
    n_override = apply_location_overrides(props + tickets + pois, load_location_overrides())
    if n_override:
        location_stats["toạ độ sửa tay (location_overrides.csv)"] = n_override

    clock.begin("gộp trùng khách sạn", len(props), done=mapped)
    clusters, pairs = cluster_hotels(props, a.match_threshold)
    products: list[dict] = []
    for members in clusters:
        merged, rooms = merge_hotel_cluster(members, rooms_of, budget.ota_rooms_per_hotel)
        products.append(merged)
        products.extend(rooms)
        dropped["khách sạn trùng giữa các nguồn (đã gộp)"] += len(members) - 1
    for score, dist, x, y in pairs:
        report_rows.append(["hotel", f"{score:.1f}", "" if dist is None else f"{dist:.0f}", x["destination"], x["name"], x["sourceRef"], y["name"], y["sourceRef"]])
    log.info("Khách sạn: %d bản ghi → %d sau khi gộp", len(props), len(clusters))
    stage_report.update(hotelRecords=len(props), hotelClusters=len(clusters))

    clock.begin("vé và điểm tham quan", len(tickets) + len(pois), done=len(products))
    # vé / điểm tham quan
    venues = load_venues()
    location_stats.update(assign_venue_locations(tickets, venues))
    pois, poi_pairs = merge_pois(tickets, pois)
    link_pois_to_venues(pois, venues)
    dropped["điểm tham quan trip.com trùng vé Vinpearl (đã gộp)"] += len(poi_pairs)
    for score, _, t, poi in poi_pairs:
        report_rows.append(["attraction", f"{score:.1f}", "", t["destination"], t["name"], t["sourceRef"], poi["name"], poi["sourceRef"]])
    products.extend(tickets)
    products.extend(pois)
    for e in entries.get("booking_attractions", []):
        products.append(e["row"])

    clock.begin("vé máy bay, combo", len(products), done=len(products))
    # vé máy bay
    for e in entries.get("trip_flights", []):
        products.extend(e["rows"])
    booking_flights = [e["record"] for e in entries.get("booking_flights", [])]
    products = merge_booking_flight_products(
        products, booking_flights,
        now=datetime.combine(a.today, datetime.min.time(), timezone.utc) if a.today else None)

    # combo bay+ở thật (trip.com/packages, nguồn mới 23/09/2026 — khác combo Vinpearl ở trên, không qua vinpearl_taxonomy())
    for e in entries.get("trip_combos", []):
        products.append(e["row"])
    # combo vé máy bay khứ hồi + khách sạn từ API bundle Vinpearl (HTTP, không cần trình duyệt)
    for e in entries.get("vinpearl_bundles", []):
        products.append(e["row"])
    if booking_flights:
        with open(paths.data / "booking_flight_offers.jsonl", "w", encoding="utf-8") as f:
            for r in booking_flights:
                for offer in r.get("offers", []):
                    f.write(json.dumps(offer, ensure_ascii=False) + "\n")

    stage_report["recordErrors"] = record_errors
    stage_report["rowsBuilt"] = len(products)
    stages.snapshot("merged", products)
    clock.begin("lọc", len(products), done=len(products))
    excluded = load_excluded_products()
    if excluded:
        before = len(products)
        stages.drop("excluded", [(p, excluded[p["sourceRef"]]) for p in products if p["sourceRef"] in excluded])
        products = [p for p in products if p["sourceRef"] not in excluded]
        if before - len(products):
            dropped["đã soát tay và loại (collectors/excluded_products.csv)"] += before - len(products)

    auto_excluded = [(p, non_tourism_reason(p["name"])) for p in products
                     if p["taxonomy"] == "attraction" and p["sourceRef"].startswith("trip:attraction:")]
    auto_excluded = [(p, reason) for p, reason in auto_excluded if reason]
    if auto_excluded:
        drop_refs = {p["sourceRef"] for p, _ in auto_excluded}
        stages.drop("notTourism", [(p, f"không phải điểm du lịch: {reason}") for p, reason in auto_excluded])
        products = [p for p in products if p["sourceRef"] not in drop_refs]
        for _p, reason in auto_excluded:
            dropped[f"không phải điểm du lịch theo quy tắc: {reason}"] += 1
        with open(paths.data / "excluded_auto.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["sourceRef", "name", "destination", "reason", "tags"])
            for p, reason in auto_excluded:
                w.writerow([p["sourceRef"], p["name"], p["destination"], reason, ", ".join(p["attributes"].get("tags") or [])])

    stage_report["rowsAfterExclusions"] = len(products)
    if not a.keep_unsellable:
        before_rows = products
        products, unsellable = drop_unsellable(products)
        stages.diff("unsellable", before_rows, products, "không có giá và nguồn không cung cấp được")
        if unsellable:
            dropped["không có giá và nguồn không cung cấp được (không đặt được)"] += unsellable

    stage_report["rowsAfterUnsellable"] = len(products)
    if not a.no_plan:
        before_rows = products
        products = apply_plan(products, plan_names, budget, dropped)
        stages.diff("plan", before_rows, products, "ngoài điểm đến/ngân sách kế hoạch, hoặc thuộc sản phẩm bị loại")

    final: list[dict] = []
    seen: set[str] = set()
    for p in products:
        if p["productId"] in seen:
            dropped["trùng sourceRef"] += 1
            stages.drop("validation", [(p, "trùng sourceRef")])
            continue
        if not p["name"] or p["taxonomy"] not in TAXONOMIES:
            dropped["thiếu tên / loại lạ"] += 1
            stages.drop("validation", [(p, "thiếu tên / loại lạ")])
            continue
        if a.min_description and len(p.get("description") or "") < a.min_description:
            dropped[f"mô tả < {a.min_description} ký tự"] += 1
            stages.drop("validation", [(p, f"mô tả < {a.min_description} ký tự")])
            continue
        if a.vietnamese_only and p["attributes"].get("descriptionLang") != "vi":
            dropped["mô tả không phải tiếng Việt"] += 1
            stages.drop("validation", [(p, "mô tả không phải tiếng Việt")])
            continue
        seen.add(p["productId"])
        final.append(p)

    stage_report["rowsAfterValidation"] = len(final)
    stages.snapshot("filtered", final)
    clock.begin("làm giàu", len(final), done=len(final))
    tidy = tidy_attributes(final)
    if tidy:
        log.info("Chuẩn hoá thuộc tính: %s", dict(tidy))

    localised = localise_descriptions(final)
    if localised:
        log.info("Dựng mô tả tiếng Việt từ thuộc tính cho %d sản phẩm (bản gốc giữ ở descriptionOriginal)", localised)

    if not a.keep_member_variants:
        before_rows = final
        final, merged_variants = merge_member_variants(final)
        stages.diff("memberVariants", before_rows, final, "biến thể giá thành viên, đã gộp vào memberPrices của vé gốc")
        if merged_variants:
            dropped["biến thể giá thành viên Vinpearl (đã gộp, giá từng hạng giữ trong memberPrices)"] += merged_variants

    stage_report["rowsAfterMemberMerge"] = len(final)
    stages.snapshot("enriched", final)
    if a.annotate_hotel_granularity:  # mặc định TẮT: không thêm khoá nào vào attributes (giữ nguyên form catalog)
        annotate_hotel_granularity(final)
    clock.begin("kiểm vị trí, giá", len(final), done=len(final))
    finalize_locations(final)
    # Mặc định xoá dòng lỗi dữ liệu theo yêu cầu (19/09/2026: không phải soát tay rồi thêm lại). Mỗi bước có cờ giữ lại.
    removed_all: list[tuple[dict, str]] = []
    if not a.keep_location_warnings:
        final, removed = drop_location_warnings(final)
        removed_all += removed
    if not a.keep_missing_coordinates:
        final, removed = drop_missing_coordinates(final)
        removed_all += removed
    if not a.keep_price_outliers:
        final, removed = drop_price_outliers(final)
        removed_all += removed
    final, removed = drop_orphans(final)
    removed_all += removed
    stages.drop("location", removed_all)
    if removed_all:
        for _p, reason in removed_all:
            dropped[f"{reason} (đã xoá, xem data/excluded_location.csv)"] += 1
        write_location_exclusions(removed_all, paths.data / "excluded_location.csv")
        log.info("Đã xoá %d dòng lỗi dữ liệu (danh sách: data/excluded_location.csv)", len(removed_all))
    clock.begin("ghi output", len(final), done=len(final))
    write_outputs(final, paths.data, report_rows, dropped, plan_names, location_stats, venues)
    stages.close(report_rows, final)
    clock.end(len(final))
    if a.report_json:
        stage_report.update(rowsFinal=len(final), dropped=dict(dropped), locationStats=dict(location_stats))
        a.report_json.write_text(json.dumps(stage_report, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(final)
    if not a.no_plan and not TARGET_MIN <= n <= TARGET_MAX:
        log.warning("Catalog có %d sản phẩm – handbook nhắm %d–%d. Xem data/stats.md.", n, TARGET_MIN, TARGET_MAX)
    return 0


if __name__ == "__main__":
    sys.exit(main())
