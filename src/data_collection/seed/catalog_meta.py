"""Phần dùng chung cho load_catalog.py và seed_histories.py, theo file thiết kế DB của nhóm ("V-OTA Database Schema", 20/09/2026):
vai trò sản phẩm (view catalog.product_meta), cửa sổ đặt chỗ 30 ngày và lịch khả dụng 30 ký tự 1/0.

Quyết định nằm ở đây (đổi một chỗ là cả loader lẫn seed đổi theo):
  * is_bookable  = hạng phòng, chuyến bay, điểm tham quan/vé, combo, golf **có giá** (unitPrice != null). Khách sạn (property) và tuyến bay
    (route) là cha, không đặt trực tiếp. Điểm tham quan chưa có giá vẫn tìm được nhưng không đặt được.
  * is_search_unit = khách sạn, tuyến bay, điểm tham quan, combo, golf (hạng phòng và chuyến bay dùng vector của cha).
  * is_recommendable = search unit tự đặt được, hoặc có >= 1 con đặt được (khách sạn không có phòng đặt được thì không được gợi ý).
"""
from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, timedelta

SELLABLE = ("hotel_room", "flight", "attraction", "combo", "golf")
SEARCH_UNITS = ("hotel_property", "flight_route", "attraction", "combo", "golf")
WINDOW_DAYS = 30                                  # cửa sổ [as_of, as_of + 29]
CAL_ORIGIN = date(2026, 1, 1)                     # gốc cố định: trạng thái một đêm không đổi khi cuộn cửa sổ
FIXED_HOLIDAYS = {(1, 1), (4, 30), (5, 1), (9, 2)}  # ngày lễ dương lịch cố định; ngày lễ âm lịch (Tết, giỗ tổ) không mô hình hoá


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


def is_vinpearl(r: dict) -> bool:
    return r["attributes"].get("brand") == "Vinpearl" or str(r["sourceRef"]).startswith("vinpearl:")


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
def room_closed_days(product_id: str, vinpearl: bool, last_day: date) -> list[bool]:
    """Trạng thái kín (True) / trống của một hạng phòng cho mọi đêm từ CAL_ORIGIN đến last_day. Kín 25–40% (Vinpearl +8 điểm %),
    theo cụm 1–4 đêm liên tiếp, đêm thứ Sáu / thứ Bảy dễ kín hơn. Xác định theo (productId, ngày) nên không đổi khi as_of dịch."""
    rng = random.Random(f"cal|{product_id}")
    frac = min(0.55, rng.uniform(0.25, 0.40) + (0.08 if vinpearl else 0.0))
    p_start = 1.0 / (1.0 + 2.5 * (1 - frac) / frac)   # cụm kín trung bình 2,5 đêm → tỷ lệ kín dài hạn ≈ frac
    p_weekday = p_start / (1 + 2 / 7 * 0.5)           # đêm T6/T7 dễ kín hơn ×1,5 mà trung bình vẫn ≈ frac
    out: list[bool] = []
    remaining = 0
    d = CAL_ORIGIN
    while d <= last_day:
        if remaining > 0:
            out.append(True)
            remaining -= 1
        elif rng.random() < p_weekday * (1.5 if d.weekday() in (4, 5) else 1.0):
            remaining = rng.randint(1, 4) - 1
            out.append(True)
        else:
            out.append(False)
        d += timedelta(days=1)
    return out


def room_calendar(product: dict, as_of: date) -> str:
    """Chuỗi 30 ký tự: '1' = trống, '0' = kín, ký tự đầu là đêm as_of."""
    lo, hi = window(as_of)
    closed = room_closed_days(product["productId"], is_vinpearl(product), hi)
    start = (lo - CAL_ORIGIN).days
    return "".join("0" if c else "1" for c in closed[start:start + WINDOW_DAYS])


def ticket_calendar(as_of: date, holidays: set[date] | None = None) -> str:
    """Điểm tham quan / combo / golf: chỉ blackout ngày lễ."""
    lo, _ = window(as_of)
    out = []
    for i in range(WINDOW_DAYS):
        d = lo + timedelta(days=i)
        out.append("0" if (d.month, d.day) in FIXED_HOLIDAYS or (holidays and d in holidays) else "1")
    return "".join(out)


def open_nights(calendar: str, as_of: date, start: date, nights: int) -> bool:
    """Tất cả các đêm [start, start + nights) đều nằm trong cửa sổ và trống."""
    i = (start - as_of).days
    return 0 <= i and i + nights <= len(calendar) and all(c == "1" for c in calendar[i:i + nights])
