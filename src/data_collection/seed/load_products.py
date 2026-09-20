"""Bước 1 — `products.jsonl` → `cdp.products` (MOCK_DATA_SPEC §2).

Mỗi dòng file thành một dòng bảng, tên trường camelCase → snake_case. `attributes` giữ **nguyên**
rồi bổ sung bốn nhóm khoá do loader gán: cửa sổ nguồn, lịch 30 ngày, thuộc tính combo, giờ cố định.

Nguyên tắc: không thêm cột vào `cdp.products` (đúng 13 trường handbook §6) — mọi thứ khác vào JSONB.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import numpy as np

from . import config
from .common import (
    inclusive_int,
    insert_batch,
    json_dump,
    make_rng,
    stable_order_key,
    window_end,
)

#: "3N2Đ" / "4N3D" — số đêm là nhóm thứ hai.
NIGHTS_COMPACT_RE = re.compile(r"(\d+)\s*[Nn]\s*(\d+)\s*[ĐđDd]")
#: "3 ngày 2 đêm"
NIGHTS_VERBOSE_RE = re.compile(r"(\d+)\s*ngày\s*(\d+)\s*đêm", re.IGNORECASE)
#: "cho 2 người" / "cho 4 khách"
MIN_PAX_RE = re.compile(r"cho\s+(\d+)\s*(?:người|khách)", re.IGNORECASE)
#: Giá tính theo đầu khách.
PER_PERSON_RE = re.compile(
    r"/\s*khách|/\s*người|giá cho 1 người|giá cho 1 khách|mỗi khách|per person", re.IGNORECASE
)

COLUMNS = [
    "product_id", "name", "taxonomy", "destination", "description", "attributes",
    "unit_price", "currency", "available", "available_from", "available_to", "image_url", "source_ref",
]


def _parse_date(value) -> dt.date | None:
    if not value:
        return None
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def parse_combo_attributes(name: str, description: str) -> dict:
    """`nights`, `minPax`, `priceBasis` cho combo (§2.3).

    `priceBasis` mặc định `per_package`; chỉ đổi sang `per_person` khi text nói rõ giá theo khách
    (chốt 20/09, DATABASE_SCHEMA §1 mục 10).
    """
    text = f"{name} {description}"
    attributes: dict = {}

    match = NIGHTS_COMPACT_RE.search(text) or NIGHTS_VERBOSE_RE.search(text)
    if match:
        attributes["nights"] = int(match.group(2))

    pax = MIN_PAX_RE.search(text)
    if pax:
        attributes["minPax"] = int(pax.group(1))

    attributes["priceBasis"] = "per_person" if PER_PERSON_RE.search(text) else "per_package"
    return attributes


def clip_window(
    record: dict, as_of: dt.date
) -> tuple[bool, dt.date | None, dt.date | None, dict]:
    """Cắt khoảng của nguồn vào cửa sổ đặt chỗ 30 ngày tính từ `as_of`.

    Trả về (available, available_from, available_to, khoá attributes cần thêm).
    Quy tắc DATABASE_SCHEMA §1 mục 13 và MOCK_DATA_SPEC §2.1.
    """
    end = window_end(as_of)
    source_from = _parse_date(record.get("availableFrom"))
    source_to = _parse_date(record.get("availableTo"))
    available = bool(record.get("available", True))

    extra: dict = {}
    # Giữ giá trị gốc để chạy lại loader với as_of khác vẫn cuộn đúng cửa sổ.
    if source_from:
        extra["sourceAvailableFrom"] = source_from.isoformat()
    if source_to:
        extra["sourceAvailableTo"] = source_to.isoformat()

    attributes = record.get("attributes", {})
    level = attributes.get("level")

    if record.get("taxonomy") == "flight" and level == "flight":
        # Chuyến bay: from = to = ngày bay. Ngoài cửa sổ thì DỜI vào, không bỏ đi.
        flight_day = source_from
        if flight_day is None or not (as_of <= flight_day <= end):
            offset = stable_order_key(record["productId"]) % config.WINDOW_DAYS
            flight_day = as_of + dt.timedelta(days=offset)
        return available, flight_day, flight_day, extra

    start = max(source_from, as_of) if source_from else as_of
    finish = min(source_to, end) if source_to else end

    if start > finish:
        # Nguồn hết hạn trước cửa sổ → không bán được trong cửa sổ này.
        return False, None, None, extra
    return available, start, finish, extra


def build_calendar(
    rng: np.random.Generator, record: dict, as_of: dt.date
) -> dict | None:
    """Chuỗi 30 ký tự `1` trống / `0` kín (§2.2).

    Chỉ `level = room` và taxonomy ∈ {attraction, golf} có khoá này.
    flight, property, route, combo **không** có — verify.sql kiểm đúng điều đó.
    """
    taxonomy = record["taxonomy"]
    level = record.get("attributes", {}).get("level")
    days = config.WINDOW_DAYS

    if taxonomy == "hotel" and level == "room":
        target = float(rng.uniform(*config.ROOM_OCCUPANCY_RANGE))
        is_vinpearl = record.get("attributes", {}).get("brand") == "Vinpearl"
        calendar = ["1"] * days
        closed = 0
        wanted = int(round(target * days))
        guard = 0
        while closed < wanted and guard < days * 4:
            guard += 1
            start = int(rng.integers(0, days))
            weekday = (as_of + dt.timedelta(days=start)).weekday()  # 4=Fri, 5=Sat
            probability = 1.0
            if weekday in (4, 5):
                probability *= config.WEEKEND_OCCUPANCY_FACTOR
            if is_vinpearl:
                probability *= config.VINPEARL_OCCUPANCY_FACTOR
            if rng.random() > min(probability / 2.0, 1.0):
                continue
            block = inclusive_int(rng, config.ROOM_BLOCK_NIGHTS)
            for offset in range(block):
                index = start + offset
                if index < days and calendar[index] == "1":
                    calendar[index] = "0"
                    closed += 1
        return {"from": as_of.isoformat(), "days": days, "calendar": "".join(calendar)}

    if taxonomy in ("attraction", "golf"):
        calendar = ["1"] * days
        if rng.random() < config.BLACKOUT_RATE:
            for _ in range(inclusive_int(rng, config.BLACKOUT_DAYS)):
                calendar[int(rng.integers(0, days))] = "0"
        return {"from": as_of.isoformat(), "days": days, "calendar": "".join(calendar)}

    return None


def build_rows(records: list[dict], as_of: dt.date, seed: int) -> list[tuple]:
    """Thuần: từ list bản ghi jsonl ra list tuple sẵn sàng insert."""
    rng = make_rng(seed, "load_products")
    rows: list[tuple] = []

    for record in records:
        attributes = dict(record.get("attributes") or {})
        available, start, finish, extra = clip_window(record, as_of)
        attributes.update(extra)

        calendar = build_calendar(rng, record, as_of)
        if calendar:
            attributes["availability"] = calendar

        if record["taxonomy"] == "combo":
            attributes.update(parse_combo_attributes(record["name"], record.get("description", "")))

        # Giờ cố định: chỉ đặt khi chưa có, không ghi đè dữ liệu crawl.
        if record["taxonomy"] == "hotel" and attributes.get("level") == "property":
            attributes.setdefault("checkInTime", config.HOTEL_CHECK_IN_TIME)
            attributes.setdefault("checkOutTime", config.HOTEL_CHECK_OUT_TIME)

        rows.append(
            (
                record["productId"],
                record["name"],
                record["taxonomy"],
                record["destination"],
                record.get("description") or "",
                json_dump(attributes),
                record.get("unitPrice"),
                record.get("currency") or "VND",
                available,
                start,
                finish,
                record.get("imageUrl"),
                record["sourceRef"],
            )
        )
    return rows


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_rows(conn, rows: list[tuple]) -> int:
    """Idempotent: ON CONFLICT (product_id) DO UPDATE toàn bộ cột (§2)."""
    updatable = [c for c in COLUMNS if c != "product_id"]
    assignments = ", ".join(f"{c} = EXCLUDED.{c}" for c in updatable)
    placeholder = "(" + ", ".join(["%s"] * len(COLUMNS)) + ")"
    statement = (
        f"INSERT INTO cdp.products ({', '.join(COLUMNS)}) VALUES {placeholder} "
        f"ON CONFLICT (product_id) DO UPDATE SET {assignments}"
    )
    with conn.cursor() as cur:
        from .common import chunked

        for batch in chunked(rows):
            cur.executemany(statement, batch)
    return len(rows)


def run(conn, *, products_path: Path, as_of: dt.date, seed: int) -> dict:
    records = read_jsonl(products_path)
    rows = build_rows(records, as_of, seed)
    write_rows(conn, rows)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM cdp.products")
        total = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM cdp.products WHERE NOT available")
        unavailable = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM cdp.products "
            "WHERE length(attributes#>>'{availability,calendar}') = %s",
            (config.WINDOW_DAYS,),
        )
        with_calendar = cur.fetchone()[0]
    return {
        "source": str(products_path),
        "rows": len(rows),
        "total": total,
        "unavailable": unavailable,
        "with_calendar": with_calendar,
    }
