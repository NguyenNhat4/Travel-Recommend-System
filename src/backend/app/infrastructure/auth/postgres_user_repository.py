"""app.users qua role vota_app (DATABASE_URL).

Không bao giờ SELECT cdp.profiles ở đây: vota_app không có quyền đó. cdp_user_id đi cùng hàng user
chính vì vậy — gương app.users.cdp_user_id tồn tại để đăng nhập không phải hỏi sang CDP (auth §3.6.4).
"""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from src.backend.app.application.auth.errors import CdpUserIdTaken, EmailAlreadyExists
from src.backend.app.application.auth.principal import AuthenticatedUser

_COLUMNS = "user_id, email, password_hash, display_name, cdp_user_id, persona, email_verified_at"


def _to_user(row: dict) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=str(row["user_id"]),
        email=row["email"],
        password_hash=row["password_hash"],
        display_name=row["display_name"],
        cdp_user_id=row["cdp_user_id"],
        persona=row["persona"],
        email_verified=row["email_verified_at"] is not None,
    )


class PostgresUserRepository:
    def __init__(self, database_url: str):
        self._database_url = database_url

    async def find_by_email(self, email: str) -> AuthenticatedUser | None:
        async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
            row = await (
                await conn.execute(f"SELECT {_COLUMNS} FROM app.users WHERE email = %s", (email.lower(),))
            ).fetchone()
        return _to_user(row) if row else None

    async def find_by_id(self, user_id: str) -> AuthenticatedUser | None:
        async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
            try:
                row = await (
                    await conn.execute(f"SELECT {_COLUMNS} FROM app.users WHERE user_id = %s::uuid", (user_id,))
                ).fetchone()
            except psycopg.errors.InvalidTextRepresentation:
                return None  # sub không phải uuid: không tồn tại, không phải lỗi 500
        return _to_user(row) if row else None

    async def email_exists(self, email: str) -> bool:
        async with await psycopg.AsyncConnection.connect(self._database_url) as conn:
            row = await (
                await conn.execute("SELECT 1 FROM app.users WHERE email = %s", (email.lower(),))
            ).fetchone()
        return row is not None

    async def create(
        self, *, email: str, password_hash: str, display_name: str, cdp_user_id: str
    ) -> AuthenticatedUser:
        try:
            async with await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row) as conn:
                row = await (
                    await conn.execute(
                        f"""
                        INSERT INTO app.users (email, password_hash, display_name, cdp_user_id)
                        VALUES (%s, %s, %s, %s)
                        RETURNING {_COLUMNS}
                        """,
                        (email.lower(), password_hash, display_name, cdp_user_id),
                    )
                ).fetchone()
                await conn.commit()
        except psycopg.errors.UniqueViolation as exc:
            # Phân biệt hai ràng buộc: trùng email là lỗi người dùng (409), trùng cdp_user_id là
            # va chạm ID nội bộ mà caller xử lý bằng cách sinh lại.
            constraint = getattr(exc.diag, "constraint_name", "") or ""
            if "cdp_user_id" in constraint:
                raise CdpUserIdTaken(cdp_user_id) from exc
            raise EmailAlreadyExists(email) from exc
        return _to_user(row)

    async def update_password_hash(self, user_id: str, password_hash: str) -> None:
        async with await psycopg.AsyncConnection.connect(self._database_url) as conn:
            await conn.execute(
                "UPDATE app.users SET password_hash = %s WHERE user_id = %s", (password_hash, user_id)
            )
            await conn.commit()

    async def touch_last_login(self, user_id: str) -> None:
        async with await psycopg.AsyncConnection.connect(self._database_url) as conn:
            await conn.execute("UPDATE app.users SET last_login_at = now() WHERE user_id = %s", (user_id,))
            await conn.commit()
