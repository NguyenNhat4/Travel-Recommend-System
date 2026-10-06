import sys
from datetime import datetime, timezone
from types import SimpleNamespace

from src.backend.app.infrastructure.cdp.postgres_cdp_reader import PostgresCdpReader


def test_postgres_cdp_reader_all_events_uses_read_adapter_and_stable_order(monkeypatch):
    row = ("u1", "purchase", datetime(2026, 1, 1, tzinfo=timezone.utc), "p1", "hotel", "trip1", 1, 100, None)

    class Cursor:
        sql = ""
        params = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params):
            self.sql, self.params = sql, params

        def fetchall(self):
            return [row]

    class Connection:
        def __init__(self):
            self.value = Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return self.value

    connection = Connection()
    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=lambda url: connection))

    events = PostgresCdpReader("postgresql://cdp-reader").all_events()

    assert connection.value.params == ()
    assert "FROM cdp.events" in connection.value.sql
    assert 'ORDER BY cdp_user_id, "timestamp", event_id' in connection.value.sql
    assert events == [{
        "cdpUserId": "u1",
        "eventName": "purchase",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "productId": "p1",
        "taxonomy": "hotel",
        "eventGroupId": "trip1",
        "quantity": 1,
        "unitPrice": 100.0,
        "usingDate": None,
    }]
