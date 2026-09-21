"""Phần dùng chung cho load_products.py và seed_histories.py, theo file thiết kế DB của nhóm ("V-OTA Database Schema", 20/09/2026):
vai trò sản phẩm (view catalog.product_meta), cửa sổ đặt chỗ 30 ngày và lịch khả dụng 30 ký tự 1/0 (MOCK_DATA_SPEC §2).

Quyết định nằm ở đây (đổi một chỗ là cả loader lẫn seed đổi theo):
  * is_bookable  = hạng phòng, chuyến bay, điểm tham quan/vé, combo, golf **có giá** (unitPrice != null). Khách sạn (property) và tuyến bay
    (route) là cha, không đặt trực tiếp. Điểm tham quan chưa có giá vẫn tìm được nhưng không đặt được.
  * is_search_unit = khách sạn, tuyến bay, điểm tham quan, combo, golf (hạng phòng và chuyến bay dùng vector của cha).
  * is_recommendable = search unit tự đặt được, hoặc có >= 1 con đặt được (khách sạn không có phòng đặt được thì không được gợi ý).
Mọi tỷ lệ của lịch khả dụng nằm trong config.py.
"""
from __future__ import annotations

import math
import random
import zlib
from collections import defaultdict
from datetime import date, timedelta

from . import config

SELLABLE = ("hotel_room", "flight", "attraction", "combo", "golf")
SEARCH_UNITS = ("hotel_property", "flight_route", "attraction", "combo", "golf")
WINDOW_DAYS = config.WINDOW_DAYS                  # cửa sổ [as_of, as_of + 29]


def stable_order_key(value: str) -> int:
    """Thứ tự cố định, không phụ thuộc PYTHONHASHSEED — thay cho `hash(product_id)` của spec (hash() đổi giữa các tiến trình)."""
    return zlib.crc32(value.encode("utf-8"))


def variant(r: dict) -> str:
    """Tên variant phải khớp chính xác view ``catalog.product_meta`` trong DDL chính thức."""
    taxonomy = r["taxonomy"]
    level = r["attributes"].get("level")
    if taxonomy == "hotel":
        return f"hotel_{level or 'property'}"
    if taxonomy == "flight":
        return "flight_route" if level == "route" else "flight"
    return taxonomy


def window(as_of: date) -> tuple[date, date]:
    return as_of, as_of + timedelta(days=WINDOW_DAYS - 1)


def is_vinpearl(r: dict, by_id: dict[str, dict] | None = None) -> bool:
    """Brand Vinpearl theo chính dòng đó; hạng phòng / chuyến bay thiếu brand thì xét dòng cha (khi có ``by_id``)."""
    if r["attributes"].get("brand") == "Vinpearl" or str(r["sourceRef"]).startswith("vinpearl:"):
        return True
    parent = by_id.get(r["attributes"].get("parentProductId") or "") if by_id else None
    return parent is not None and is_vinpearl(parent)


def build_meta(rows: list[dict]) -> dict[str, dict]:
    """productId -> {variant, is_bookable, is_search_unit, is_recommendable, parent_product_id}."""
    meta: dict[str, dict] = {}
    bookable_children: dict[str, int] = defaultdict(int)
    for r in rows:
        v = variant(r)
        level = r["attributes"].get("level", "")
        bookable = level not in ("property", "route") and r["attributes"].get("ticketed", True) is not False \
            and r["unitPrice"] is not None
        meta[r["productId"]] = {"variant": v, "is_bookable": bookable, "is_search_unit": v in SEARCH_UNITS,
                                "parent_product_id": r["attributes"].get("parentProductId")}
        if bookable and r["available"] and meta[r["productId"]]["parent_product_id"]:
            bookable_children[meta[r["productId"]]["parent_product_id"]] += 1
    for pid, m in meta.items():
        m["is_recommendable"] = m["is_search_unit"] and (m["is_bookable"] or bookable_children[pid] > 0)
    return meta


# ------------------------------------------------------------------ lịch khả dụng
def room_closed_target(product: dict, as_of: date, by_id: dict[str, dict] | None = None) -> int:
    """Số đêm kín trong cửa sổ: U(25%, 40%) × 30; Vinpearl ×1,3 nhưng không vượt 40%."""
    rng = random.Random(f"cal-share|{product['productId']}|{as_of.isoformat()}")
    share = rng.uniform(*config.ROOM_CLOSED_SHARE)
    if is_vinpearl(product, by_id):
        share = min(config.ROOM_CLOSED_CAP, share * config.ROOM_VINPEARL_MULT)
    lo = math.ceil(round(config.ROOM_CLOSED_SHARE[0] * WINDOW_DAYS, 6))
    hi = math.floor(round(config.ROOM_CLOSED_CAP * WINDOW_DAYS, 6))
    return min(hi, max(lo, round(share * WINDOW_DAYS)))


def room_calendar(product: dict, as_of: date, by_id: dict[str, dict] | None = None) -> str:
    """Chuỗi 30 ký tự: '1' = trống, '0' = kín, ký tự đầu là đêm as_of.

    Số đêm kín = room_closed_target(); xếp thành cụm 1–4 đêm liên tiếp, giữa hai cụm luôn có ≥ 1 đêm trống; cụm chứa đêm
    thứ Sáu / thứ Bảy được chọn với trọng số ROOM_WEEKEND_CLUSTER_WEIGHT để mỗi đêm T6/T7 dễ kín ≈ ROOM_WEEKEND_MULT lần
    đêm thường. Xác định theo (productId, as_of).
    """
    rng = random.Random(f"cal|{product['productId']}|{as_of.isoformat()}")
    weekend = [(as_of + timedelta(days=i)).weekday() in (4, 5) for i in range(WINDOW_DAYS)]
    closed = [False] * WINDOW_DAYS
    remaining = room_closed_target(product, as_of, by_id)
    while remaining > 0:
        length = min(remaining, rng.randint(*config.ROOM_CLOSED_CLUSTER))
        while length > 0:
            starts = [s for s in range(WINDOW_DAYS - length + 1)
                      if not any(closed[j] for j in range(max(0, s - 1), min(WINDOW_DAYS, s + length + 1)))]
            if starts:
                break
            length -= 1
        if length == 0:
            break
        s = rng.choices(starts, [config.ROOM_WEEKEND_CLUSTER_WEIGHT if any(weekend[s:s + length]) else 1.0 for s in starts])[0]
        for j in range(s, s + length):
            closed[j] = True
        remaining -= length
    return "".join("0" if c else "1" for c in closed)


def ticket_calendar(product_id: str, as_of: date) -> str:
    """Điểm tham quan / golf: toàn '1', trừ 15% sản phẩm (cố định theo crc32) bị blackout 2–3 ngày ngẫu nhiên trong cửa sổ."""
    if stable_order_key(f"blackout|{product_id}") % 10_000 >= config.TICKET_BLACKOUT_SHARE * 10_000:
        return "1" * WINDOW_DAYS
    rng = random.Random(f"blackout|{product_id}|{as_of.isoformat()}")
    days = set(rng.sample(range(WINDOW_DAYS), rng.randint(*config.TICKET_BLACKOUT_DAYS)))
    return "".join("0" if i in days else "1" for i in range(WINDOW_DAYS))


def open_nights(calendar: str, as_of: date, start: date, nights: int) -> bool:
    """Tất cả các đêm [start, start + nights) đều nằm trong cửa sổ và trống."""
    i = (start - as_of).days
    return 0 <= i and i + nights <= len(calendar) and all(c == "1" for c in calendar[i:i + nights])
