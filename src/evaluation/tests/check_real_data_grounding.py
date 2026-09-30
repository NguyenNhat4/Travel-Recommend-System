"""Kiểm agent trên catalog Postgres thật: điểm đến được chuẩn hóa và mọi sản phẩm có trong DB.

Cần backend chạy với ITINERARY_DATA_MODE=http và Postgres đã seed:

    docker compose up -d --wait postgres
    ITINERARY_DATA_MODE=http ITINERARY_SERVICE_BASE_URL=http://127.0.0.1:8000 \
        .venv/bin/python -m uvicorn src.backend.app.main:app --port 8000
    .venv/bin/python src/evaluation/tests/check_real_data_grounding.py

Handbook §12 đặt grounding của trợ lý ở 100% "sản phẩm thật, đúng thành phố", nên bất kỳ
dòng FAIL nào cũng là chưa đạt, không tính theo tỷ lệ.

Bộ case nhanh, 6 câu, chỉ soi chuẩn hóa điểm đến + grounding qua HTTP. Bộ đầy đủ (50 case,
đa lượt, đối chiếu tool/intent) ở `src/evaluation/agent/golden.py`; hai file dùng chung
`src/evaluation/agent/grounding.py`.
"""

import argparse
import os
import sys

import httpx

from src.evaluation.agent.grounding import check_product_grounding, products_in_response

#: Mỗi câu viết lệch dấu hoặc viết tắt phải ra cùng điểm đến chuẩn như câu viết đủ.
CASES = [
    ("đi Đà Nẵng 2 ngày", "Đà Nẵng"),
    ("da nang 2 ngay", "Đà Nẵng"),
    ("tphcm 2 ngày", "TP. Hồ Chí Minh"),
    ("Nha Trang 3 ngày", "Nha Trang"),
    ("ha long 2 ngay", "Hạ Long"),
    ("tokyo 2 ngày", None),
]


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
            ok = (response.status_code == 200 and status == "NEEDS_CLARIFICATION"
                  and "destination" in (body.get("missingFields") or []))
            failures += not ok
            print(f"\n{'ok  ' if ok else 'FAIL'} {message!r} → {response.status_code} {status}")
            continue

        print(f"\n{message!r} → {status} dest={destination!r}")
        if destination != expected:
            print(f"   FAIL điểm đến chưa chuẩn hóa: mong {expected!r}")
            failures += 1

        for where, product in products_in_response(body):
            checked += 1
            error = check_product_grounding(where, product, args.dsn)
            if error is None and product["destination"] != destination:
                error = f"{where} {product['productId']} sai điểm đến: mong {destination!r}, có {product['destination']!r}"
            if error is None:
                print(f"   ok   {where:6} {product['taxonomy']:10} {product['name'][:46]}")
            else:
                failures += 1
                print(f"   FAIL {error}")

    print(f"\n=== {checked - failures}/{checked} sản phẩm khớp DB, {failures} lỗi ===")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
