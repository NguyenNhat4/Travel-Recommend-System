"""Dữ liệu mô phỏng cho demo sau mỗi lần nạp catalog (docs/prd/data-model.md §3.1, chốt 09/10/2026), theo thứ tự phụ thuộc:

1. `simulated_rooms`   — hạng phòng cho khách sạn có giá nhưng chưa có phòng (`demo:room:*`);
2. `simulated_fill`    — tuyến chiều ngược (`demo:reverse:*`) rồi vé phủ ngày (`demo:fill:*`) cho mọi tuyến;
3. `combo_components`  — sản phẩm cho mọi thành phần combo + `price_share` (`demo:combo:*`), nối được tuyến chiều ngược ở bước 2;
4. `simulated_fill`    — lần hai, phủ vé cho tuyến mô phỏng của combo sinh ở bước 3.
Chạy sau `simulated_business.sync` và sau parse combo (`sync_combo_items`), trong cùng transaction của bước nạp. Mỗi bước tự đọc cờ
bật/tắt của mình (`SIMULATED_ROOMS`, `SIMULATED_FILL_FLIGHTS`, `SIMULATED_COMBO_ITEMS`) và chỉ ghi dòng của mình.

Một lần qua tunnel DB (cả bốn bước trong một transaction; `--dry-run` chạy rồi ROLLBACK nên cần quyền ghi):
    python -m data_collection.seed.demo_data --database-url-env CLOUD_SEED_DATABASE_URL [--as-of YYYY-MM-DD] [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date

from . import combo_components, simulated_fill, simulated_rooms
from .simulated_fill import today_vn

logger = logging.getLogger(__name__)


def infer_as_of(conn) -> date:
    """`as_of` của lần nạp đang có: cửa sổ hạng phòng luôn là [as_of, as_of + 29]; không có phòng nào thì hôm nay (giờ VN)."""
    row = conn.execute("""SELECT min(available_from) FROM cdp.products
                           WHERE taxonomy = 'hotel' AND attributes->>'level' = 'room' AND available
                             AND source_ref NOT LIKE 'demo:%'""").fetchone()
    value = row[0] if row and not isinstance(row, dict) else (row or {}).get("min")
    return value or today_vn()


def has_price_share(conn) -> bool:
    """Migration 0010 đã áp (cột `catalog.combo_items.price_share`, view lọc `comboOnly`)? Chưa áp thì bước thành phần combo bị bỏ
    qua thay vì làm hỏng cả transaction nạp catalog (deploy job cào có thể chạy trước deploy backend, nơi chạy migration)."""
    row = conn.execute("""SELECT count(*) FROM information_schema.columns
                           WHERE table_schema = 'catalog' AND table_name = 'combo_items' AND column_name = 'price_share'""").fetchone()
    return bool(row[0] if row is not None and not isinstance(row, dict) else (row or {}).get("count"))


def sync(conn, as_of: date | None = None) -> dict[str, int]:
    """Bốn bước trên `conn` (không commit); trả số đếm gộp, số của lần phủ vé thứ hai đè lần thứ nhất."""
    as_of = as_of or infer_as_of(conn)
    counts: dict[str, int] = {}
    counts.update(simulated_rooms.sync(conn, as_of=as_of))
    first = simulated_fill.sync(conn, as_of=as_of)
    if has_price_share(conn):
        counts.update(combo_components.sync(conn, as_of=as_of))
    else:
        logger.warning("demo_data: chưa áp migration 0010 (catalog.combo_items.price_share) — bỏ qua thành phần combo mô phỏng")
        counts["comboComponentsSkipped"] = 1
    second = simulated_fill.sync(conn, as_of=as_of)
    counts.update(second)
    counts["fillWritten"] = first.get("fillWritten", 0) + second.get("fillWritten", 0)
    counts.pop("written", None)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dữ liệu mô phỏng cho demo: phòng, tuyến chiều ngược, vé phủ ngày, thành phần combo.")
    parser.add_argument("--database-url-env", default="SEED_DATABASE_URL", help="tên biến môi trường chứa DSN")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None, help="ngày đầu cửa sổ (mặc định: suy từ cửa sổ hạng phòng)")
    parser.add_argument("--dry-run", action="store_true", help="chạy trong transaction rồi ROLLBACK")
    args = parser.parse_args(argv)
    url = os.environ.get(args.database_url_env)
    if not url:
        parser.error(f"{args.database_url_env} chưa đặt")
    import psycopg
    with psycopg.connect(url) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(7791024)")  # cùng khoá ghi catalog với job fresh
        counts = sync(conn, args.as_of)
        if args.dry_run:
            conn.rollback()
    print(("[dry-run, đã rollback] " if args.dry_run else "") + f"as_of={args.as_of or 'suy từ DB'} · "
          + " · ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
