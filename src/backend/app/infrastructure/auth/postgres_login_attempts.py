"""app.login_attempts — bằng chứng bền để điều tra (auth §16.2).

Không bao giờ lưu email thô hay IP đầy đủ: email băm SHA-256, IP rút về /24 (auth §15.2).
"""
from __future__ import annotations

import hashlib
import ipaddress
from datetime import datetime

import psycopg


def hash_email(email: str) -> str:
    return "sha256:" + hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def ip_prefix(raw: str) -> str:
    """/24 cho IPv4, /48 cho IPv6. Giá trị không parse được trả 'unknown' thay vì ném lỗi:
    ghi nhật ký đăng nhập không được phép làm hỏng chính lần đăng nhập đó."""
    try:
        addr = ipaddress.ip_address(raw.strip())
    except ValueError:
        return "unknown"
    net = 24 if addr.version == 4 else 48
    return str(ipaddress.ip_network(f"{addr}/{net}", strict=False))


class PostgresLoginAttemptLog:
    def __init__(self, database_url: str):
        self._database_url = database_url

    async def record(
        self,
        *,
        email: str,
        user_id: str | None,
        ip_prefix: str,
        user_agent_hash: str | None,
        succeeded: bool,
        failure_reason: str | None,
        at: datetime | None = None,
    ) -> None:
        async with await psycopg.AsyncConnection.connect(self._database_url) as conn:
            await conn.execute(
                """
                INSERT INTO app.login_attempts
                    (email_hash, user_id, ip_prefix, user_agent_hash, succeeded, failure_reason, attempted_at)
                VALUES (%s, %s::uuid, %s, %s, %s, %s, COALESCE(%s, now()))
                """,
                (hash_email(email), user_id, ip_prefix, user_agent_hash, succeeded, failure_reason, at),
            )
            await conn.commit()
