"""`PostgresCdpReader`: timeout theo `CDP_TIMEOUT_SECONDS` và chỉ lỗi kết nối/timeout mới thành
`CdpUnavailableError` (hop-dong-tich-hop-cdp.md §6–§7). `psycopg.connect` được thay bằng bản giả, không cần Postgres.
"""
from datetime import date, datetime, timezone

import psycopg
import pytest

from src.backend.app.application.ports.cdp_client import CdpUnavailableError
from src.backend.app.infrastructure.cdp.postgres_cdp_reader import PostgresCdpReader

DSN = "postgresql://cdp_client_login:s3cret-pw@cdp.internal:5432/vota"


class _Cursor:
    def __init__(self, rows, executed):
        self.rows, self.executed = rows, executed

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows


class _Conn:
    def __init__(self, rows, executed):
        self.rows, self.executed = rows, executed

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return _Cursor(self.rows, self.executed)


def fake_connect(monkeypatch, *, rows=(), error=None) -> list[dict]:
    """Thay `psycopg.connect`; mỗi lần gọi ghi conninfo, kwargs và các câu lệnh đã chạy."""
    calls = []

    def connect(conninfo, **kwargs):
        call = {"conninfo": conninfo, "kwargs": kwargs, "executed": []}
        calls.append(call)
        if error is not None:
            raise error
        return _Conn(list(rows), call["executed"])

    monkeypatch.setattr(psycopg, "connect", connect)
    return calls


@pytest.mark.parametrize("error", [
    psycopg.OperationalError('connection failed: connection to server at "10.0.0.5", port 5432 failed: '
                             "Connection refused\n\tIs the server running on that host?"),
    psycopg.errors.QueryCanceled("canceling statement due to statement timeout"),
    psycopg.InterfaceError("the connection is closed"),
    ConnectionRefusedError("connection refused"),
    # Driver in lại DSN hoặc mật khẩu: message vẫn không được chứa chúng.
    psycopg.OperationalError(f"invalid connection info {DSN}"),
    psycopg.OperationalError("authentication failed: password s3cret-pw rejected"),
], ids=["operational", "statement_timeout", "interface", "os_error", "echoes_dsn", "echoes_password"])
def test_outage_becomes_cdp_unavailable(monkeypatch, error):
    fake_connect(monkeypatch, error=error)
    with pytest.raises(CdpUnavailableError) as caught:
        PostgresCdpReader(DSN).events_for_user("VP0000001")
    message = str(caught.value)
    assert caught.value.__cause__ is error
    assert type(error).__name__ in message
    assert "\n" not in message and "Is the server running" not in message  # chỉ dòng đầu
    assert "s3cret-pw" not in message and DSN not in message


def test_long_driver_message_is_truncated(monkeypatch):
    fake_connect(monkeypatch, error=psycopg.OperationalError("x" * 1000))
    with pytest.raises(CdpUnavailableError) as caught:
        PostgresCdpReader(DSN).purchase_events()
    assert len(str(caught.value)) < 300


def test_permission_error_is_not_swallowed(monkeypatch):
    # Sai quyền là lỗi cấu hình (DATABASE_URL thay vì CDP_DATABASE_URL): phải nổi lên, không hạ thành popular.
    fake_connect(monkeypatch, error=psycopg.errors.InsufficientPrivilege("permission denied for table events"))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        PostgresCdpReader(DSN).events_for_user("VP0000001")


SET_TIMEOUT = "SELECT set_config('statement_timeout', %s, true)"


@pytest.mark.parametrize("timeout, connect_timeout, statement_ms", [
    (2.0, 2, "2000"),
    (2.5, 3, "2500"),
    (0.5, 2, "500"),  # libpq coi connect_timeout dưới 2 là 2
])
def test_timeouts_follow_cdp_timeout_seconds(monkeypatch, timeout, connect_timeout, statement_ms):
    calls = fake_connect(monkeypatch)
    reader = PostgresCdpReader(DSN, timeout_seconds=timeout)
    reader.events_for_user("VP0000001")
    reader.purchase_events()
    per_request, bulk = calls
    assert per_request["kwargs"] == bulk["kwargs"] == {"connect_timeout": connect_timeout}
    # statement_timeout đặt trong transaction, trước câu SELECT, chỉ cho đường đọc theo request.
    assert per_request["executed"][0] == (SET_TIMEOUT, (statement_ms,))
    assert len(per_request["executed"]) == 2
    # Đọc lô lúc khởi động không bị statement_timeout cắt: chỉ đúng một câu SELECT.
    assert len(bulk["executed"]) == 1 and bulk["executed"][0][0] != SET_TIMEOUT


def test_events_for_user_is_newest_first_with_tie_break_and_capped(monkeypatch):
    # cdp §6: tối đa 500 event mới nhất; cùng thời điểm thì event_id tăng dần (khớp thứ tự harness bench dựng lại).
    calls = fake_connect(monkeypatch)
    PostgresCdpReader(DSN).events_for_user("VP0000001")
    sql, params = calls[0]["executed"][1]
    assert sql.rstrip().endswith('ORDER BY "timestamp" DESC, event_id ASC LIMIT %s')
    assert params == ("VP0000001", 500)
    calls = fake_connect(monkeypatch)
    PostgresCdpReader(DSN, history_limit=20).events_for_user("VP0000001")
    assert calls[0]["executed"][1][1] == ("VP0000001", 20)


def test_default_timeout_is_two_seconds(monkeypatch):
    calls = fake_connect(monkeypatch)
    PostgresCdpReader(DSN).events_for_user("VP0000001")
    assert calls[0]["kwargs"] == {"connect_timeout": 2}
    assert calls[0]["executed"][0] == (SET_TIMEOUT, ("2000",))


def test_dsn_is_passed_unchanged_without_a_startup_options_parameter(monkeypatch):
    # `options` trong DSN (search_path...) không bị ghi đè, và pooler chế độ transaction không bị gửi tham số lạ.
    dsn = DSN + "?options=-c%20search_path%3Dcdp"
    calls = fake_connect(monkeypatch)
    PostgresCdpReader(dsn).events_for_user("VP0000001")
    assert calls[0]["conninfo"] == dsn
    assert "options" not in calls[0]["kwargs"]


def test_all_events_is_a_deterministic_bulk_read_without_statement_timeout(monkeypatch):
    calls = fake_connect(monkeypatch)
    PostgresCdpReader(DSN).all_events()
    (sql, params), = calls[0]["executed"]  # chỉ một câu SELECT, không set_config
    assert "WHERE" not in sql and params == ()
    assert sql.rstrip().endswith('ORDER BY cdp_user_id, "timestamp", event_id')


def test_all_events_until_cuts_at_the_store(monkeypatch):
    calls = fake_connect(monkeypatch)
    until = datetime(2026, 9, 24, tzinfo=timezone.utc)
    PostgresCdpReader(DSN).all_events(until=until)
    (sql, params), = calls[0]["executed"]
    assert 'WHERE "timestamp" < %s' in sql and params == (until,)


def test_all_profiles_is_a_deterministic_bulk_read_in_camel_case(monkeypatch):
    rows = [("VP0000002", "new", None, 0, "Member", [], "Hà Nội", None),
            ("VP0000001", "active", 3, 4, "Gold", ["hotel", "flight"], "TP. Hồ Chí Minh", "Nha Trang")]
    calls = fake_connect(monkeypatch, rows=rows)
    got = PostgresCdpReader(DSN).all_profiles()
    (sql, params), = calls[0]["executed"]          # một câu SELECT, không set_config (đọc lô)
    assert "FROM cdp.profiles" in sql and "ORDER BY cdp_user_id" in sql and params == ()
    assert got[1] == {"cdpUserId": "VP0000001", "lifecycleStage": "active", "daysSinceLastBooking": 3, "lifetimeOrderCount": 4,
                      "vinclubTier": "Gold", "purchasedVerticals": ["hotel", "flight"], "homeCity": "TP. Hồ Chí Minh",
                      "lastDestination": "Nha Trang"}
    assert got[0]["daysSinceLastBooking"] is None and got[0]["purchasedVerticals"] == []


def test_all_profiles_outage_becomes_cdp_unavailable(monkeypatch):
    fake_connect(monkeypatch, error=psycopg.OperationalError("connection refused"))
    with pytest.raises(CdpUnavailableError):
        PostgresCdpReader(DSN).all_profiles()


def test_all_events_outage_becomes_cdp_unavailable(monkeypatch):
    fake_connect(monkeypatch, error=psycopg.OperationalError("connection refused"))
    with pytest.raises(CdpUnavailableError):
        PostgresCdpReader(DSN).all_events()


def test_rows_keep_cdp_field_names(monkeypatch):
    row = ("VP0000001", "purchase", datetime(2026, 9, 18, 10, tzinfo=timezone.utc), "R1", "hotel",
           "T1", 1, 3400000, date(2026, 10, 5))
    fake_connect(monkeypatch, rows=[row])
    assert PostgresCdpReader(DSN).events_for_user("VP0000001") == [{
        "cdpUserId": "VP0000001", "eventName": "purchase", "timestamp": "2026-09-18T10:00:00+00:00",
        "productId": "R1", "taxonomy": "hotel", "eventGroupId": "T1", "quantity": 1,
        "unitPrice": 3400000.0, "usingDate": "2026-10-05",
    }]
