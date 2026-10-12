"""app.login_attempts — bằng chứng bền để điều tra (auth §16.2).

Không bao giờ lưu email thô hay IP đầy đủ: email băm SHA-256, IP rút về /24 (auth §15.2).
"""
from __future__ import annotations

from datetime import datetime

# Giữ tên cũ cho caller đang import từ đây; hiện thực nằm ở domain để api/application dùng chung.
from src.backend.app.domain.auth.privacy import hash_email, ip_prefix  # noqa: F401
from src.backend.app.infrastructure.persistence.db_connection import connect_async


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
        async with await connect_async(self._database_url) as conn:
            await conn.execute(
                """
                INSERT INTO app.login_attempts
                    (email_hash, user_id, ip_prefix, user_agent_hash, succeeded, failure_reason, attempted_at)
                VALUES (%s, %s::uuid, %s, %s, %s, %s, COALESCE(%s, now()))
                """,
                (hash_email(email), user_id, ip_prefix, user_agent_hash, succeeded, failure_reason, at),
            )
            await conn.commit()
