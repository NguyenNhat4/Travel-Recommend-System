"""app.refresh_tokens — chuỗi rotation một-lần-dùng (auth §10.4, §16.2), qua role vota_app.

Token là chuỗi đục 256 bit, không phải JWT. Bảng chỉ giữ SHA-256; bản rõ chỉ tồn tại trong session
Redis của BFF. Ba luật:
  * Mỗi lần xoay: token cũ đánh dấu rotated (rotated_at + revoked_reason='rotation'), token mới cùng
    family, cùng session_id và cùng expires_at — refresh không kéo dài được absolute timeout 12h.
  * Token đã rotated bị dùng lại → thu hồi mọi token còn sống của user ('reuse_detected'): kẻ trộm và
    nạn nhân đều bị đăng xuất, và đó là tín hiệu duy nhất cho biết token đã lọt.
  * Đăng xuất thu hồi cả family của token; gọi lại với token đã thu hồi không lỗi.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

from src.backend.app.application.auth.errors import RefreshTokenInvalid, RefreshTokenReuse
from src.backend.app.application.ports.auth import RotatedRefreshToken


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_token() -> str:
    return "rt_" + secrets.token_urlsafe(32)


class PostgresRefreshTokenStore:
    def __init__(self, database_url: str, *, ttl_seconds: int = 43_200):
        self._database_url = database_url
        self._ttl = timedelta(seconds=ttl_seconds)

    async def _connect(self):
        return await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row)

    async def issue(self, *, user_id: str, session_id: str) -> str:
        token = _new_token()
        async with await self._connect() as conn:
            await conn.execute(
                """
                INSERT INTO app.refresh_tokens (user_id, family_id, token_hash, session_id, expires_at)
                VALUES (%s::uuid, %s::uuid, %s, %s, now() + %s)
                """,
                (user_id, str(uuid.uuid4()), _digest(token), session_id, self._ttl),
            )
            await conn.commit()
        return token

    async def rotate(self, token: str) -> RotatedRefreshToken:
        reuse_user: str | None = None
        async with await self._connect() as conn:
            async with conn.transaction():
                row = await (
                    await conn.execute(
                        """
                        SELECT token_id, user_id, family_id, session_id, expires_at, rotated_at, revoked_at
                        FROM app.refresh_tokens WHERE token_hash = %s FOR UPDATE
                        """,
                        (_digest(token),),
                    )
                ).fetchone()
                if row is None:
                    raise RefreshTokenInvalid("refresh token lạ")
                if row["rotated_at"] is not None:
                    await conn.execute(
                        """
                        UPDATE app.refresh_tokens SET revoked_at = now(), revoked_reason = 'reuse_detected'
                        WHERE user_id = %s AND revoked_at IS NULL
                        """,
                        (row["user_id"],),
                    )
                    reuse_user = str(row["user_id"])
                elif row["revoked_at"] is not None or row["expires_at"] <= datetime.now(timezone.utc):
                    raise RefreshTokenInvalid("refresh token đã thu hồi hoặc hết hạn")
                else:
                    new_token = _new_token()
                    await conn.execute(
                        """
                        UPDATE app.refresh_tokens
                        SET rotated_at = now(), revoked_at = now(), revoked_reason = 'rotation'
                        WHERE token_id = %s
                        """,
                        (row["token_id"],),
                    )
                    await conn.execute(
                        """
                        INSERT INTO app.refresh_tokens
                            (user_id, family_id, token_hash, session_id, expires_at)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (row["user_id"], row["family_id"], _digest(new_token), row["session_id"], row["expires_at"]),
                    )
        # Ném sau khi transaction đã commit, nếu không việc thu hồi hàng loạt bị rollback theo.
        if reuse_user is not None:
            raise RefreshTokenReuse(f"refresh token tái sử dụng, user {reuse_user}")
        return RotatedRefreshToken(new_token, str(row["user_id"]), row["session_id"])

    async def revoke(self, token: str, *, reason: str) -> None:
        async with await self._connect() as conn:
            await conn.execute(
                """
                UPDATE app.refresh_tokens SET revoked_at = now(), revoked_reason = %s
                WHERE revoked_at IS NULL AND family_id = (
                    SELECT family_id FROM app.refresh_tokens WHERE token_hash = %s
                )
                """,
                (reason, _digest(token)),
            )
            await conn.commit()

    async def revoke_all_for_user(
        self, user_id: str, *, reason: str, except_session_id: str | None = None
    ) -> int:
        async with await self._connect() as conn:
            cur = await conn.execute(
                """
                UPDATE app.refresh_tokens SET revoked_at = now(), revoked_reason = %s
                WHERE user_id = %s::uuid AND revoked_at IS NULL
                  AND (%s::text IS NULL OR session_id <> %s::text)
                """,
                (reason, user_id, except_session_id, except_session_id),
            )
            await conn.commit()
            return cur.rowcount
