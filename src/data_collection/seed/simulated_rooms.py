"""Hạng phòng mô phỏng cho khách sạn có giá nhưng chưa có hạng phòng nào (docs/prd/data-model.md §3.1 "Hạng phòng cho khách sạn
chưa có phòng", FR-CAT-03 ngoại lệ 5, chốt 09/10/2026).

Khách sạn tổng (không gộp, không mô phỏng) có `unit_price` mà không có hạng phòng con thật nào bị tắt theo FR-CAT-02 (`noBookableRoom`):
không ra tìm kiếm mặc định, gợi ý, trợ lý và không đặt được. Bước này sinh cho mỗi khách sạn đó một "Phòng tiêu chuẩn": giá = giá của khách
sạn (giá thấp nhất nguồn báo), `maxOccupancy` 2, lịch mở đủ cửa sổ, ảnh = ảnh khách sạn, `sourceRef = demo:room:<sourceRef khách sạn>`,
`simulated: true`, tên "(giá minh hoạ)"; rồi bật lại khách sạn như job cào làm khi có phòng đặt được (bỏ `noBookableRoom`; không bật dòng
đã gộp, giá quá hạn hoặc ngoài cửa sổ). Khách sạn có hạng phòng thật, hoặc tắt cấu hình → phòng mô phỏng `available = false`, không xoá.

Một lần qua tunnel DB:
    python -m data_collection.seed.simulated_rooms --database-url-env CLOUD_SEED_DATABASE_URL [--as-of YYYY-MM-DD] [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import date

from .catalog_meta import WINDOW_DAYS, window
from .simulated_business import COLUMNS, MUTABLE, NAMESPACE
from .simulated_fill import today_vn

ENV = "SIMULATED_ROOMS"
PREFIX = "demo:room:"
ROOM_NAME = "Phòng tiêu chuẩn"
COPY = ("latitude", "longitude", "locationPrecision", "locationSource", "address", "province", "city", "starRating", "brand")
NOTE = ("Hạng phòng mô phỏng (giá minh hoạ = giá thấp nhất nguồn báo cho khách sạn, không phải giá của một hạng phòng cụ thể); "
        "chỉ dùng cho demo.")


def enabled(env: dict | None = None) -> bool:
    """Mặc định bật (docs/prd/data-model.md §3.1); chỉ 0/false/no/off là tắt."""
    return str((os.environ if env is None else env).get(ENV, "")).strip().lower() not in ("0", "false", "no", "off")


def _is_property(row: dict) -> bool:
    return row["taxonomy"] == "hotel" and ((row["attributes"] or {}).get("level") or "property") == "property"


def _demo(row: dict) -> bool:
    return str(row["source_ref"]).startswith("demo:")


def plan(rows: list[dict], as_of: date, on: bool) -> tuple[list[dict], list[dict]]:
    """(hạng phòng mô phỏng mong muốn, khách sạn cần bật lại) từ các dòng taxonomy hotel."""
    lo, hi = window(as_of)
    with_rooms = {(r["attributes"] or {}).get("parentProductId") for r in rows
                  if (r["attributes"] or {}).get("level") == "room" and not _demo(r)}
    existing = {r["source_ref"]: r for r in rows if str(r["source_ref"]).startswith(PREFIX)}
    out: dict[str, dict] = {}
    reopened = []
    for prop in sorted(rows, key=lambda r: r["product_id"]) if on else ():
        a = prop["attributes"] or {}
        if (not _is_property(prop) or _demo(prop) or a.get("mergedInto") or prop.get("unit_price") is None
                or prop["product_id"] in with_rooms):
            continue
        ref = f"{PREFIX}{prop['source_ref']}"
        attrs = {k: a[k] for k in COPY if a.get(k) is not None}
        attrs.update(level="room", parentProductId=prop["product_id"], roomName=ROOM_NAME, hotelName=prop["name"],
                     maxOccupancy=2, priceNights=1, simulated=True, descriptionLang="vi",
                     descriptionSource="mô phỏng: hạng phòng cho khách sạn chưa có phòng",
                     fieldSources={"unitPrice": "mô phỏng"},
                     availability={"from": lo.isoformat(), "days": WINDOW_DAYS, "calendar": "1" * WINDOW_DAYS})
        if a.get("images"):
            attrs["images"] = a["images"][:5]
        out[ref] = {"product_id": str(uuid.uuid5(NAMESPACE, ref)), "name": f"{prop['name']} - {ROOM_NAME} (giá minh hoạ)",
                    "taxonomy": "hotel", "destination": prop["destination"], "description": NOTE, "attributes": attrs,
                    "unit_price": prop["unit_price"], "currency": prop.get("currency") or "VND", "available": True,
                    "available_from": lo, "available_to": hi, "image_url": prop.get("image_url"), "source_ref": ref}
        if not prop["available"] and a.get("noBookableRoom") and not a.get("priceFreshness") and not a.get("windowClosed"):
            reopened.append({**prop, "available": True,
                             "attributes": {k: v for k, v in a.items() if k != "noBookableRoom"},
                             "available_from": prop.get("available_from") or lo, "available_to": prop.get("available_to") or hi})
    by_id = {r["product_id"]: r for r in rows}
    # Gộp A vào B chuyển phòng mô phỏng của A sang làm con của B: tắt phòng đó không được tắt B khi B còn phòng mô phỏng của chính nó.
    keeps_room = {r["attributes"]["parentProductId"] for r in out.values()}
    for ref, row in existing.items():
        if ref not in out and row["available"]:
            out[ref] = {**row, "available": False}
            parent = by_id.get((row["attributes"] or {}).get("parentProductId"))
            if (parent and parent["available"] and parent["product_id"] not in with_rooms
                    and parent["product_id"] not in keeps_room):  # chỉ còn phòng mô phỏng: tắt như FR-CAT-02
                reopened.append({**parent, "available": False,
                                 "attributes": {**(parent["attributes"] or {}), "noBookableRoom": True}})
    return list(out.values()), reopened


def sync(conn, on: bool | None = None, as_of: date | None = None, dry_run: bool = False) -> dict[str, int]:
    """Upsert demo:room:* và bật lại khách sạn tương ứng trong transaction của `conn`. Chỉ ghi các dòng đó."""
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    on = enabled() if on is None else on
    as_of = as_of or today_vn()
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(f"SELECT {', '.join(COLUMNS)} FROM cdp.products WHERE taxonomy = 'hotel'")
        rows = [{**r, "product_id": str(r["product_id"])} for r in cursor.fetchall()]
    rooms, reopened = plan(rows, as_of, on)
    before = {r["product_id"]: r for r in rows}
    changes = [r for r in [*rooms, *reopened] if r["product_id"] not in before
               or any(before[r["product_id"]][c] != r[c] for c in MUTABLE)]
    if changes and not dry_run:
        with conn.cursor() as cursor:
            cursor.executemany(
                f"""INSERT INTO cdp.products AS p ({', '.join(COLUMNS)}) VALUES ({', '.join(['%s'] * len(COLUMNS))})
                    ON CONFLICT (product_id) DO UPDATE SET {', '.join(f'{c} = EXCLUDED.{c}' for c in MUTABLE)}""",
                [[Jsonb(row[c]) if c == "attributes" else row[c] for c in COLUMNS] for row in changes])
    return {"simulatedRooms": sum(1 for r in rooms if r["available"]),
            "simulatedRoomsClosed": sum(1 for r in rooms if not r["available"]), "hotelsReopened": len(reopened),
            "changed": len(changes), "written": 0 if dry_run else len(changes)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sinh/khoá hạng phòng mô phỏng (demo:room:*) cho khách sạn chưa có phòng.")
    parser.add_argument("--database-url-env", default="SEED_DATABASE_URL", help="tên biến môi trường chứa DSN")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None, help="ngày đầu cửa sổ (mặc định: hôm nay giờ VN)")
    parser.add_argument("--dry-run", action="store_true", help="chỉ tính, không ghi")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--enable", action="store_true", help=f"bật kể cả khi {ENV}=0")
    group.add_argument("--disable", action="store_true", help="khoá mọi hạng phòng mô phỏng")
    args = parser.parse_args(argv)
    url = os.environ.get(args.database_url_env)
    if not url:
        parser.error(f"{args.database_url_env} chưa đặt")
    import psycopg
    on = True if args.enable else False if args.disable else enabled()
    with psycopg.connect(url) as conn:
        if args.dry_run:
            conn.execute("SET TRANSACTION READ ONLY")
        else:
            conn.execute("SELECT pg_advisory_xact_lock(7791024)")  # cùng khoá ghi catalog với job fresh
        counts = sync(conn, on, args.as_of, dry_run=args.dry_run)
    print(" · ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
