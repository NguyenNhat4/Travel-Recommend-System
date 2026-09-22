"""`CdpClientPort` (đường **đọc** của recsys) trên `cdp.events` của PostgreSQL local.

Thay `LocalCdpClient` đọc JSONL trong cùng thư mục này. Đừng nhầm với
`infrastructure/clients/local_cdp_client.py`: file đó là đường **ghi** (async, `record_purchases`,
`cancel`, browse event, profile) theo port `application/ports/cdp_client.py`. Hai port khác nhau,
cùng chạm `cdp.*` và cùng đi qua `CDP_DATABASE_URL` — không có code nào ngoài hai adapter này
được SQL thẳng vào schema `cdp` (AGENTS.md §6.1).

Connection phải là `CDP_DATABASE_URL` (role `cdp_reader`/`cdp_writer`). Dùng `DATABASE_URL`
sẽ lỗi `permission denied for table events`: role `vota_app` cố ý không đọc được
`cdp.events`/`cdp.profiles`, và đó là ranh giới CDP được mô phỏng bằng quyền.

Trả dict **camelCase** đúng tên trường CDP (`cdpUserId`, `eventName`, `usingDate`…) vì đó là hình dạng
`profile.py`/`popularity.py` đang đọc, và cũng là hình dạng `HttpCdpClient` sẽ trả khi lên CDP thật.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

#: `timestamp` là từ khoá SQL nên phải để trong ngoặc kép ở mọi câu lệnh.
_COLUMNS = """
    cdp_user_id, event_name, "timestamp", product_id, taxonomy,
    event_group_id, quantity, unit_price, using_date
"""


def _to_cdp(row: tuple) -> dict:
    """Một dòng `cdp.events` → dict theo tên trường CDP."""
    cdp_user_id, event_name, timestamp, product_id, taxonomy, group_id, quantity, unit_price, using_date = row
    return {
        "cdpUserId": cdp_user_id,
        "eventName": event_name,
        "timestamp": timestamp.isoformat() if timestamp is not None else None,
        "productId": str(product_id) if product_id is not None else None,
        "taxonomy": taxonomy,
        "eventGroupId": group_id,
        "quantity": quantity,
        "unitPrice": float(unit_price) if unit_price is not None else None,
        "usingDate": using_date.isoformat() if using_date is not None else None,
    }


class PostgresCdpReader:
    """Chỉ đọc. Mọi thao tác ghi đi qua `clients/local_cdp_client.LocalCdpClient`."""

    def __init__(self, cdp_database_url: str):
        self._cdp_database_url = cdp_database_url

    def _query(self, sql: str, params: tuple) -> list[dict]:
        import psycopg

        with psycopg.connect(self._cdp_database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [_to_cdp(row) for row in cur.fetchall()]

    def events_for_user(self, cdp_user_id: str) -> list[dict]:
        """Lịch sử của một khách, mới nhất trước — `profile.py` dựng hồ sơ từ đây."""
        return self._query(
            f'SELECT {_COLUMNS} FROM cdp.events WHERE cdp_user_id = %s ORDER BY "timestamp" DESC',
            (cdp_user_id,),
        )

    def purchase_events(self, since_days: int = 730) -> list[dict]:
        """Toàn bộ `purchase` trong N ngày — đầu vào của bảng phổ biến (`popularity.py`)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        return self._query(
            f'SELECT {_COLUMNS} FROM cdp.events '
            f'WHERE event_name = %s AND "timestamp" >= %s ORDER BY "timestamp" DESC',
            ("purchase", cutoff),
        )

    def all_events(self) -> list[dict]:
        """Read a deterministic full event snapshot for offline evaluation only."""
        return self._query(
            f'SELECT {_COLUMNS} FROM cdp.events '
            'ORDER BY cdp_user_id, "timestamp", event_id',
            (),
        )
