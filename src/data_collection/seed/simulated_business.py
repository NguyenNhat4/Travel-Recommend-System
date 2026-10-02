"""Vé Thương gia mô phỏng cho demo UI chọn hạng (docs/prd/data-model.md §3, FR-CAT-03).

Sinh từ vé máy bay thật đã nạp trong cdp.products, sau mỗi lần nạp catalog: seed demo (luôn bật), `seed --catalog-only`
và job fresh (mặc định bật; tắt bằng SIMULATED_BUSINESS_FARES=0). Giá = giá vé gốc × 2,65, làm tròn nghìn đồng; luôn gắn
`simulated: true` và "(giá minh hoạ)". Vé Thương gia thật cùng hành trình và ngày luôn thắng. Không xoá dòng: vé
không còn hợp lệ chuyển available = false (đơn cũ có thể trỏ tới).

Chạy một lần qua tunnel DB (chỉ ghi các dòng demo:business:*):
    python -m data_collection.seed.simulated_business --database-url-env CLOUD_SEED_DATABASE_URL [--disable]
"""
from __future__ import annotations

import argparse
import copy
import os
import sys
import uuid

ENV = "SIMULATED_BUSINESS_FARES"
PREFIX = "demo:business:"
RATIO = 2.65  # Vietnam Airlines "Giá vé tham khảo" HAN–SGN: 3.957.000 / 1.494.000 (một chiều), 7.914.000 / 2.988.000 (khứ hồi)
NAMESPACE = uuid.UUID("7a1c9e1e-3b0e-4f5c-9d3a-2f6f0b9c4e21")  # = normalise.NAMESPACE: productId = uuid5(sourceRef)
COLUMNS = ("product_id", "name", "taxonomy", "destination", "description", "attributes", "unit_price", "currency",
           "available", "available_from", "available_to", "image_url", "source_ref")
MUTABLE = ("name", "description", "attributes", "unit_price", "available", "available_from", "available_to", "image_url")
NOTE = "Giá minh hoạ hạng Thương gia (giá vé gốc × 2,65), không phải giá nguồn báo; chỉ dùng cho demo."


def enabled(env: dict | None = None) -> bool:
    """Mặc định bật (docs/prd/data-model.md §3); chỉ 0/false/no/off là tắt."""
    return str((os.environ if env is None else env).get(ENV, "")).strip().lower() not in ("0", "false", "no", "off")


def price(value) -> int:
    return int(round(float(value) * RATIO / 1000.0)) * 1000


def _journey(row: dict) -> tuple:
    a = row["attributes"] or {}
    back = a.get("returnFlight") if isinstance(a.get("returnFlight"), dict) else {}
    day = row.get("available_from")
    return (a.get("tripType") or "oneWay", a.get("originAirport"), a.get("destinationAirport"), a.get("flightNumber"),
            str(day) if day else str(a.get("departureAt") or "")[:10], back.get("flightNumber"),
            a.get("returnDate") or str(back.get("departureAt") or "")[:10] or None)


def _is_source(row: dict) -> bool:
    a = row["attributes"] or {}
    return (row["taxonomy"] == "flight" and a.get("level") == "flight" and bool(a.get("flightNumber"))
            and not a.get("simulated") and not row["source_ref"].startswith(PREFIX)
            and a.get("cabinClass") not in ("BUSINESS", "FIRST") and row.get("unit_price") is not None)


def simulate(source: dict, blocked: bool) -> dict:
    a = copy.deepcopy(source["attributes"] or {})
    a.update(cabinClass="BUSINESS", simulated=True,
             fieldSources={**(a.get("fieldSources") or {}), "unitPrice": "mô phỏng", "cabinClass": "mô phỏng"})
    ref = PREFIX + source["source_ref"]
    return {"product_id": str(uuid.uuid5(NAMESPACE, ref)), "name": f"{source['name']} — Thương gia (giá minh hoạ)",
            "taxonomy": "flight", "destination": source["destination"],
            "description": f"{NOTE} {source.get('description') or ''}".strip(), "attributes": a,
            "unit_price": price(source["unit_price"]), "currency": source.get("currency") or "VND",
            "available": bool(source["available"]) and not blocked, "available_from": source.get("available_from"),
            "available_to": source.get("available_to"), "image_url": source.get("image_url"), "source_ref": ref}


def plan(rows: list[dict], on: bool) -> list[dict]:
    """Desired demo:business:* rows from the current catalog rows (flights; other rows are ignored)."""
    flights = [r for r in rows if r["taxonomy"] == "flight"]
    existing = {r["source_ref"]: r for r in flights if r["source_ref"].startswith(PREFIX)}
    real_business = {_journey(r) for r in flights
                     if (r["attributes"] or {}).get("cabinClass") == "BUSINESS" and r["available"]
                     and not (r["attributes"] or {}).get("simulated") and not r["source_ref"].startswith(PREFIX)}
    out = {}
    if on:
        for row in flights:
            if _is_source(row):
                sim = simulate(row, _journey(row) in real_business)
                out[sim["source_ref"]] = sim
    for ref, row in existing.items():
        if ref not in out and row["available"]:  # source gone, turned off or no longer eligible → close, keep row
            out[ref] = {**row, "available": False}
    return list(out.values())


def sync(conn, on: bool | None = None) -> dict[str, int]:
    """Upsert demo:business:* rows inside the caller's transaction (psycopg connection). Only those rows are written."""
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    on = enabled() if on is None else on
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(f"SELECT {', '.join(COLUMNS)} FROM cdp.products WHERE taxonomy = 'flight'")
        rows = [{**r, "product_id": str(r["product_id"])} for r in cursor.fetchall()]
    desired = plan(rows, on)
    before = {r["product_id"]: r for r in rows}
    changes = [r for r in desired if r["product_id"] not in before
               or any(before[r["product_id"]][c] != r[c] for c in MUTABLE)]
    if changes:
        with conn.cursor() as cursor:
            cursor.executemany(
                f"""INSERT INTO cdp.products AS p ({', '.join(COLUMNS)}) VALUES ({', '.join(['%s'] * len(COLUMNS))})
                    ON CONFLICT (product_id) DO UPDATE SET {', '.join(f'{c} = EXCLUDED.{c}' for c in MUTABLE)}""",
                [[Jsonb(row[c]) if c == "attributes" else row[c] for c in COLUMNS] for row in changes])
    return {"simulatedBusiness": sum(1 for r in desired if r["available"]),
            "simulatedBusinessClosed": sum(1 for r in desired if not r["available"]),
            "simulatedBusinessWritten": len(changes)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sinh/khoá vé Thương gia mô phỏng trong cdp.products.")
    parser.add_argument("--database-url-env", default="SEED_DATABASE_URL", help="tên biến môi trường chứa DSN")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--enable", action="store_true", help="bật kể cả khi SIMULATED_BUSINESS_FARES=0")
    group.add_argument("--disable", action="store_true", help="khoá mọi vé mô phỏng")
    args = parser.parse_args(argv)
    url = os.environ.get(args.database_url_env)
    if not url:
        parser.error(f"{args.database_url_env} chưa đặt")
    import psycopg
    on = True if args.enable else False if args.disable else enabled()
    with psycopg.connect(url) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(7791024)")  # cùng khoá ghi catalog với job fresh
        counts = sync(conn, on)
    print(" · ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
