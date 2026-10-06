"""`PostgresSearchLogWriter`: một INSERT vào app.search_logs qua DATABASE_URL; `psycopg.connect` được thay bằng bản giả (như
test_postgres_cdp_reader.py), không cần Postgres. User chưa có profile CDP (FK) → ghi lại dòng với cdp_user_id NULL."""
import os
import uuid

import psycopg
import pytest
from psycopg.types.json import Jsonb

from src.backend.app.application.ports.search_logs import SearchLogEntry
from src.backend.app.infrastructure.persistence.postgres_search_logs import (
    MAX_QUERY_CHARS,
    PostgresSearchLogReader,
    PostgresSearchLogWriter,
)

DSN = "postgresql://vota_app_login:pw@db.internal:5432/vota"
PID = "11111111-1111-4111-8111-111111111111"


class _Conn:
    def __init__(self, call, fk_first):
        self.call, self.fk_first = call, fk_first

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.call["committed"] = exc[0] is None
        return False

    def execute(self, sql, params=None):
        self.call["executed"].append((sql, params))
        if self.fk_first and len(self.call["executed"]) == 1:
            raise psycopg.errors.ForeignKeyViolation("insert violates foreign key constraint")
        return self

    def rollback(self):
        self.call["rollbacks"] += 1

    def fetchall(self):
        return [("biển Nha Trang", 3, None)]


def fake_connect(monkeypatch, *, fk_first=False, error=None) -> list[dict]:
    calls = []

    def connect(conninfo, **kwargs):
        call = {"conninfo": conninfo, "kwargs": kwargs, "executed": [], "rollbacks": 0}
        calls.append(call)
        if error is not None:
            raise error
        return _Conn(call, fk_first)

    monkeypatch.setattr(psycopg, "connect", connect)
    return calls


def _entry(**kw):
    base = dict(query="resort Nha Trang", result_count=2, model_version="m1", result_product_ids=(PID, "H2"),
                filters={"priceMax": 2000000, "confidence": 1.0}, latency_ms=12, cdp_user_id="cdp-1", session_id="s1")
    return SearchLogEntry(**{**base, **kw})


def test_single_insert_with_typed_params(monkeypatch):
    calls = fake_connect(monkeypatch)
    PostgresSearchLogWriter(DSN, timeout_seconds=3).write(_entry())
    (call,) = calls
    assert call["conninfo"] == DSN and call["kwargs"] == {"connect_timeout": 3} and call["committed"]
    ((sql, params),) = call["executed"]
    assert "INSERT INTO app.search_logs" in sql
    cdp_user_id, session_id, query, filters, ids, count, model, latency = params
    assert (cdp_user_id, session_id, query, count, model, latency) == ("cdp-1", "s1", "resort Nha Trang", 2, "m1", 12)
    assert isinstance(filters, Jsonb) and filters.obj == {"priceMax": 2000000, "confidence": 1.0}
    assert ids == [uuid.UUID(PID)]                         # uuid[]: id không phải UUID bị bỏ, không làm hỏng dòng


def test_query_truncated_and_empty_filters_are_null(monkeypatch):
    calls = fake_connect(monkeypatch)
    PostgresSearchLogWriter(DSN).write(_entry(query="x" * 900, filters=None, result_product_ids=()))
    params = calls[0]["executed"][0][1]
    assert len(params[2]) == MAX_QUERY_CHARS and params[3] is None and params[4] == []


def test_unknown_cdp_profile_retries_once_without_identity(monkeypatch):
    calls = fake_connect(monkeypatch, fk_first=True)
    PostgresSearchLogWriter(DSN).write(_entry())
    call = calls[0]
    assert call["rollbacks"] == 1 and [p[0] for _, p in call["executed"]] == ["cdp-1", None] and call["committed"]


def test_connection_errors_propagate_to_the_recorder(monkeypatch):
    fake_connect(monkeypatch, error=psycopg.OperationalError("connection refused"))
    with pytest.raises(psycopg.OperationalError):
        PostgresSearchLogWriter(DSN).write(_entry())


def test_reader_still_returns_head_queries(monkeypatch):
    fake_connect(monkeypatch)
    assert PostgresSearchLogReader(DSN).head_queries(days=30, limit=5) == ["biển Nha Trang"]


@pytest.mark.skipif(os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
                    reason="set RUN_POSTGRES_INTEGRATION=1 to test against the seeded local database")
def test_round_trip_on_local_database():
    """Như tests/integration: DDL thật (uuid[], jsonb, FK cdp_user_id → cdp.profiles) bằng role vota_app; dọn dòng đã ghi."""
    url = os.getenv("DATABASE_URL", "postgresql://vota_app_login:vota@localhost:5432/vota")
    marker = f"__search_log_test__ {uuid.uuid4()}"
    PostgresSearchLogWriter(url).write(_entry(query=marker, cdp_user_id="no-such-cdp-profile"))
    try:
        with psycopg.connect(url) as conn:
            row = conn.execute("SELECT cdp_user_id, filters, result_product_ids, result_count FROM app.search_logs "
                               "WHERE query = %s", (marker,)).fetchone()
        assert row == (None, {"priceMax": 2000000, "confidence": 1.0}, [uuid.UUID(PID)], 2)
        assert marker in PostgresSearchLogReader(url).head_queries(days=1, limit=1000)
    finally:
        with psycopg.connect(url) as conn:
            conn.execute("DELETE FROM app.search_logs WHERE query = %s", (marker,))
