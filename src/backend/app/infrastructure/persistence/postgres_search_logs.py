"""`SearchLogReader` trên `app.search_logs` (DDL `db/vota_schema.sql`). Hôm nay chưa code nào ghi bảng này nên thường trả
rỗng; adapter viết nhỏ để prewarm có head query ngay khi backend bắt đầu ghi log tìm kiếm."""
from __future__ import annotations

import logging

import psycopg

logger = logging.getLogger("uvicorn.error")

_SQL = """
    SELECT query, count(*) AS n, max(created_at) AS last_at
    FROM app.search_logs
    WHERE created_at >= now() - make_interval(days => %s)
    GROUP BY query
    ORDER BY n DESC, last_at DESC
    LIMIT %s
"""


class PostgresSearchLogReader:
    def __init__(self, database_url: str, *, timeout_seconds: float = 5.0):
        self._database_url = database_url
        self._timeout = timeout_seconds

    def head_queries(self, *, days: int, limit: int) -> list[str]:
        if limit <= 0:
            return []
        try:
            with psycopg.connect(self._database_url, connect_timeout=int(self._timeout)) as conn:
                rows = conn.execute(_SQL, (days, limit)).fetchall()
        except Exception as exc:  # noqa: BLE001 — thiếu bảng, mất kết nối… prewarm chỉ mất head query, không mất startup
            logger.warning("search.prewarm.head_queries.failed error=%s", exc)
            return []
        return [str(r[0]) for r in rows if r[0]]
