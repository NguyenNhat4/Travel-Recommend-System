"""Đọc sản phẩm từ response và đối chiếu với `cdp.products` thật.

Tách từ `src/evaluation/tests/check_real_data_grounding.py` để dùng chung với runner golden
(`src/evaluation/agent/golden.py`); script đó import lại các hàm này thay vì định nghĩa riêng.
"""

from __future__ import annotations

import subprocess
from typing import Any


def products_in_response(body: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Mọi ProductSummary nằm trong `itinerary.stay`, `itinerary.days[].slots[].product`
    và `searchResults` (mọi taxonomy) — không chỉ sản phẩm đã xếp lịch."""
    found: list[tuple[str, dict[str, Any]]] = []
    itinerary = body.get("itinerary") or {}
    if stay := (itinerary.get("stay") or {}).get("product"):
        found.append(("stay", stay))
    for day in itinerary.get("days", []):
        for slot in day.get("slots", []):
            if product := slot.get("product"):
                found.append((f"day{day.get('day')}", product))
    search_results = body.get("searchResults") or {}
    for taxonomy, items in search_results.items():
        for product in items or []:
            found.append((f"searchResults.{taxonomy}", product))
    return found


def product_from_db(product_id: str, dsn: str | None) -> list[str] | None:
    """`[name, destination, unit_price|"NULL", available]` từ `cdp.products`, `None` nếu không tồn tại.

    `product_id` là cột `uuid`; một chuỗi không đúng định dạng UUID (agent bịa id) không tồn tại
    trong bảng cũng như một id hợp lệ nhưng vắng mặt — cả hai trả `None` thay vì để driver ném lỗi.
    """
    query = ("SELECT name, destination, coalesce(unit_price::text, 'NULL'), available::text "
             "FROM cdp.products WHERE product_id = %(id)s;")
    if dsn:
        import psycopg
        try:
            with psycopg.connect(dsn) as conn:
                row = conn.execute(query, {"id": product_id}).fetchone()
        except psycopg.errors.InvalidTextRepresentation:
            return None
        return [str(value) for value in row] if row else None
    # Không có DSN thì đọc qua container compose, giống cách dev chạy tay.
    literal = query.replace("%(id)s", "'" + product_id.replace("'", "''") + "'")
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "postgres",
         "-d", "vota", "-tA", "-F", "|", "-c", literal],
        capture_output=True, text=True)
    if result.returncode != 0:
        return None  # id không hợp lệ về kiểu (invalid UUID) hoặc lỗi khác — coi là không tồn tại.
    line = result.stdout.strip()
    return line.split("|") if line else None


def check_product_grounding(where: str, product: dict[str, Any], dsn: str | None) -> str | None:
    """Đối chiếu một product với DB. Trả về thông điệp lỗi, hoặc `None` nếu khớp."""
    row = product_from_db(product["productId"], dsn)
    if row is None:
        return f"{where} {product['productId']} không có trong cdp.products"
    name, destination, price_text, available_text = row
    price = product.get("unitPrice")
    price_ok = (price_text == "NULL" and price is None) or (
        price_text != "NULL" and price is not None and abs(float(price_text) - float(price)) < 0.01
    )
    available_ok = (available_text == "true") == bool(product.get("available"))
    if name != product["name"] or destination != product["destination"] or not price_ok or not available_ok:
        return (f"{where} {product['productId']} lệch DB | db={row} | response="
                f"{[product['name'], product['destination'], price, product.get('available')]}")
    return None
