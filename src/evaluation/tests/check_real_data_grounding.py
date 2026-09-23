"""Kiểm agent trên catalog Postgres thật: điểm đến được chuẩn hóa và mọi sản phẩm có trong DB.

Cần backend chạy với ITINERARY_DATA_MODE=http và Postgres đã seed:

    docker compose up -d --wait postgres
    ITINERARY_DATA_MODE=http ITINERARY_SERVICE_BASE_URL=http://127.0.0.1:8000 \
        .venv/bin/python -m uvicorn src.backend.app.main:app --port 8000
    .venv/bin/python src/evaluation/tests/check_real_data_grounding.py

Handbook §12 đặt grounding của trợ lý ở 100% "sản phẩm thật, đúng thành phố", nên bất kỳ
dòng FAIL nào cũng là chưa đạt, không tính theo tỷ lệ.
"""

import argparse
import json
import os
import subprocess
import sys

import httpx

#: Mỗi câu viết lệch dấu hoặc viết tắt phải ra cùng điểm đến chuẩn như câu viết đủ.
CASES = [
    ("đi Đà Nẵng 2 ngày", "Đà Nẵng"),
    ("da nang 2 ngay", "Đà Nẵng"),
    ("tphcm 2 ngày", "TP. Hồ Chí Minh"),
    ("Nha Trang 3 ngày", "Nha Trang"),
    ("ha long 2 ngay", "Hạ Long"),
    ("tokyo 2 ngày", None),
]


def products(body: dict) -> list[tuple[str, dict]]:
    itinerary = body.get("itinerary") or {}
    found = []
    if stay := (itinerary.get("stay") or {}).get("product"):
        found.append(("stay", stay))
    for day in itinerary.get("days", []):
        for slot in day.get("slots", []):
            if product := slot.get("product"):
                found.append((f"day{day.get('day')}", product))
    return found


def from_database(product_id: str, dsn: str | None) -> list[str] | None:
    query = ("SELECT name, destination, coalesce(unit_price::text, 'NULL') "
             "FROM cdp.products WHERE product_id = %(id)s;")
    if dsn:
        import psycopg
        with psycopg.connect(dsn) as conn:
            row = conn.execute(query, {"id": product_id}).fetchone()
        return [str(value) for value in row] if row else None
    # Không có DSN thì đọc qua container compose, giống cách dev chạy tay.
    literal = query.replace("%(id)s", "'" + product_id.replace("'", "''") + "'")
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "postgres",
         "-d", "vota", "-tA", "-F", "|", "-c", literal],
        capture_output=True, text=True, check=True)
    line = result.stdout.strip()
    return line.split("|") if line else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("ASSISTANT_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--dsn", default=os.environ.get("SEED_DATABASE_URL"))
    args = parser.parse_args()

    listed = httpx.get(f"{args.base_url}/api/v1/destinations", timeout=30).json()["destinations"]
    supported = {item["destination"] for item in listed}
    print(f"/destinations: {len(supported)} điểm đến, {sum(i['productCount'] for i in listed)} sản phẩm")

    checked = failures = 0
    for message, expected in CASES:
        response = httpx.post(f"{args.base_url}/api/v1/assistant/itineraries",
                              json={"message": message}, timeout=180)
        body = response.json()
        status = body.get("status") or body.get("error", {}).get("code")
        destination = (body.get("intent") or {}).get("destination")

        if expected is None:
            ok = response.status_code == 422 and status == "UNSUPPORTED_DESTINATION"
            failures += not ok
            print(f"\n{'ok  ' if ok else 'FAIL'} {message!r} → {response.status_code} {status}")
            continue

        print(f"\n{message!r} → {status} dest={destination!r}")
        if destination != expected:
            print(f"   FAIL điểm đến chưa chuẩn hóa: mong {expected!r}")
            failures += 1

        for where, product in products(body):
            checked += 1
            row = from_database(product["productId"], args.dsn)
            if row is None:
                print(f"   FAIL {where} {product['productId']} không có trong cdp.products")
                failures += 1
                continue
            price = product.get("unitPrice")
            same = (row[0] == product["name"]
                    and row[1] == product["destination"] == destination
                    and ((row[2] == "NULL" and price is None)
                         or (row[2] != "NULL" and price is not None and abs(float(row[2]) - float(price)) < 0.01)))
            if same:
                print(f"   ok   {where:6} {product['taxonomy']:10} {product['name'][:46]}")
            else:
                failures += 1
                print(f"   FAIL {where} lệch DB | db={row} | response="
                      f"{json.dumps([product['name'], product['destination'], price], ensure_ascii=False)}")

    print(f"\n=== {checked - failures}/{checked} sản phẩm khớp DB, {failures} lỗi ===")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
