"""Mở kết nối PostgreSQL bất đồng bộ có thời hạn, và dịch lỗi "không với tới DB" sang lỗi của application.

Mọi adapter dùng `connect_async` thay cho `psycopg.AsyncConnection.connect` trực tiếp. Lý do: kết nối trần không
có thời hạn, nên khi VM DB treo mà cổng vẫn nhận SYN thì request treo theo timeout TCP của hệ điều hành. Ở đây:
  - `connect_timeout` chặn pha kết nối;
  - keepalive và `tcp_user_timeout` để phát hiện DB chết giữa chừng, mà không đặt `statement_timeout` (sẽ cắt nhầm
    truy vấn dài hợp lệ như nạp catalog);
  - `asyncio.wait_for` là lưới an toàn nếu driver không tôn trọng `connect_timeout`.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import psycopg

from src.backend.app.application.errors import DatabaseUnavailableError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Timeouts:
    connect_seconds: int = 3
    tcp_user_ms: int = 15_000


_timeouts = _Timeouts()


def configure(*, connect_timeout_seconds: int, tcp_user_timeout_ms: int) -> None:
    """Gọi một lần ở composition root (lifespan) với giá trị từ Settings."""
    global _timeouts
    _timeouts = _Timeouts(connect_seconds=connect_timeout_seconds, tcp_user_ms=tcp_user_timeout_ms)


def _params(overrides: dict) -> dict:
    base = {
        "connect_timeout": _timeouts.connect_seconds,
        "keepalives": 1,
        "keepalives_idle": 10,
        "keepalives_interval": 5,
        "keepalives_count": 3,
        "tcp_user_timeout": _timeouts.tcp_user_ms,
    }
    return {**base, **overrides}


async def connect_async(dsn: str, **kwargs) -> psycopg.AsyncConnection:
    """Mở kết nối; không với tới được thì ném `DatabaseUnavailableError` (đã bỏ chi tiết có thể chứa DSN)."""
    params = _params(kwargs)
    try:
        return await asyncio.wait_for(
            psycopg.AsyncConnection.connect(dsn, **params), timeout=params["connect_timeout"] + 2
        )
    except (psycopg.OperationalError, OSError, asyncio.TimeoutError) as exc:
        logger.warning("db.connect_failed error=%s", type(exc).__name__)
        raise DatabaseUnavailableError(f"PostgreSQL không với tới được: {type(exc).__name__}") from exc
