"""connect_async: thời hạn kết nối và dịch lỗi "không với tới DB" (NFR-REL-03, kế hoạch A1)."""
import asyncio
import time

import psycopg
import pytest

from src.backend.app.application.errors import DatabaseUnavailableError
from src.backend.app.application.ports.cdp_client import CdpUnavailableError
from src.backend.app.infrastructure.cdp.local_cdp_client import LocalCdpClient
from src.backend.app.infrastructure.persistence import db_connection

# Cổng 1 không có ai nghe: kết nối bị từ chối ngay, không cần DB thật.
DEAD_DSN = "postgresql://vota_app_login:vota@127.0.0.1:1/vota"


@pytest.fixture(autouse=True)
def _default_timeouts():
    db_connection.configure(connect_timeout_seconds=3, tcp_user_timeout_ms=15_000)
    yield
    db_connection.configure(connect_timeout_seconds=3, tcp_user_timeout_ms=15_000)


def test_unreachable_database_raises_application_error_quickly() -> None:
    started = time.monotonic()
    with pytest.raises(DatabaseUnavailableError):
        asyncio.run(db_connection.connect_async(DEAD_DSN))
    assert time.monotonic() - started < 5


def test_error_message_never_contains_the_dsn() -> None:
    with pytest.raises(DatabaseUnavailableError) as caught:
        asyncio.run(db_connection.connect_async(DEAD_DSN))
    assert "vota_app_login" not in str(caught.value) and "127.0.0.1" not in str(caught.value)


def test_timeouts_come_from_configure_and_callers_can_override(monkeypatch) -> None:
    seen: dict = {}

    async def fake_connect(dsn, **kwargs):
        seen.update(kwargs)
        return object()

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", fake_connect)
    db_connection.configure(connect_timeout_seconds=7, tcp_user_timeout_ms=9000)
    asyncio.run(db_connection.connect_async("postgresql://x/y", row_factory="r"))
    assert seen["connect_timeout"] == 7 and seen["tcp_user_timeout"] == 9000
    assert seen["keepalives"] == 1 and seen["row_factory"] == "r"

    asyncio.run(db_connection.connect_async("postgresql://x/y", connect_timeout=1))
    assert seen["connect_timeout"] == 1


@pytest.mark.parametrize("error", [psycopg.OperationalError("down"), OSError("net"), asyncio.TimeoutError()])
def test_driver_and_network_errors_become_database_unavailable(monkeypatch, error) -> None:
    async def fake_connect(dsn, **kwargs):
        raise error

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", fake_connect)
    with pytest.raises(DatabaseUnavailableError):
        asyncio.run(db_connection.connect_async("postgresql://x/y"))


def test_a_connect_that_never_returns_is_cut_off(monkeypatch) -> None:
    async def hang(dsn, **kwargs):
        await asyncio.sleep(60)

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", hang)
    db_connection.configure(connect_timeout_seconds=1, tcp_user_timeout_ms=15_000)
    started = time.monotonic()
    with pytest.raises(DatabaseUnavailableError):
        asyncio.run(db_connection.connect_async("postgresql://x/y"))
    assert time.monotonic() - started < 6  # connect_timeout + 2 giây lưới an toàn


def test_programming_errors_are_not_reported_as_unavailable(monkeypatch) -> None:
    async def fake_connect(dsn, **kwargs):
        raise psycopg.ProgrammingError("invalid dsn")

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", fake_connect)
    with pytest.raises(psycopg.ProgrammingError):
        asyncio.run(db_connection.connect_async("postgresql://x/y"))


def test_local_cdp_client_still_reports_cdp_unavailable() -> None:
    """Đăng ký tài khoản dựa vào CDP_UNAVAILABLE; lớp bọc mới không được đổi mã này."""
    with pytest.raises(CdpUnavailableError):
        asyncio.run(LocalCdpClient(DEAD_DSN).get_profile("VP0000001"))
