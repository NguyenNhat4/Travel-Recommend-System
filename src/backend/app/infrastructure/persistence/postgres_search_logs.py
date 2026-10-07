"""`SearchLogReader` / `SearchLogWriter` trên `app.search_logs` (DDL `db/vota_schema.sql`), qua `DATABASE_URL` (role vota_app).

Reader: head query cho prewarm. Writer: một INSERT mỗi lượt /search khi SEARCH_LOG_QUERIES bật — chạy ngoài request trong
`SearchLogRecorder`, nên lỗi ở đây được ném lên để recorder đếm, không bao giờ tới response."""
from __future__ import annotations

import logging
import uuid

import psycopg
from psycopg.types.json import Jsonb

from src.backend.app.application.ports.search_logs import SearchLogEntry

logger = logging.getLogger("uvicorn.error")

_SQL = """
    SELECT query, count(*) AS n, max(created_at) AS last_at
    FROM app.search_logs
    WHERE created_at >= now() - make_interval(days => %s)
    GROUP BY query
    ORDER BY n DESC, last_at DESC
    LIMIT %s
"""

_INSERT = """
    INSERT INTO app.search_logs
        (cdp_user_id, session_id, query, filters, result_product_ids, result_count, model_version, latency_ms)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""

#: Cùng trần với `SearchRequest.query` của contract.
MAX_QUERY_CHARS = 500


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


def _uuids(ids) -> list[uuid.UUID]:
    """`result_product_ids` là uuid[]: bỏ id không phải UUID (catalog giả của test) thay vì làm hỏng cả dòng."""
    out: list[uuid.UUID] = []
    for pid in ids:
        try:
            out.append(uuid.UUID(str(pid)))
        except ValueError:
            continue
    return out


class PostgresSearchLogWriter:
    def __init__(self, database_url: str, *, timeout_seconds: float = 5.0):
        self._database_url = database_url
        self._timeout = timeout_seconds

    @staticmethod
    def _params(entry: SearchLogEntry, cdp_user_id: str | None) -> tuple:
        return (cdp_user_id, entry.session_id, entry.query[:MAX_QUERY_CHARS],
                Jsonb(dict(entry.filters)) if entry.filters else None,
                _uuids(entry.result_product_ids), entry.result_count, entry.model_version, entry.latency_ms)

    def write(self, entry: SearchLogEntry) -> None:
        """Một INSERT trong một transaction. `cdp_user_id` có FK sang cdp.profiles: user chưa có profile CDP → ghi lại dòng
        với NULL (mất gán danh tính, không mất dòng)."""
        with psycopg.connect(self._database_url, connect_timeout=max(1, int(self._timeout))) as conn:
            try:
                conn.execute(_INSERT, self._params(entry, entry.cdp_user_id))
            except psycopg.errors.ForeignKeyViolation:
                if entry.cdp_user_id is None:
                    raise
                conn.rollback()
                conn.execute(_INSERT, self._params(entry, None))
