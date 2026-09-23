"""Use case của auth (auth §3.6). Không import FastAPI, psycopg hay redis — chỉ port.

Đăng ký là chỗ dễ sai nhất và lý do nằm ở quyền database:

    app.users.cdp_user_id  NOT NULL UNIQUE REFERENCES cdp.profiles (cdp_user_id)
    GRANT INSERT, UPDATE ON cdp.profiles TO cdp_writer;   -- vota_app KHÔNG có

Backend ghi app.* bằng vota_app (DATABASE_URL) nhưng chỉ ghi được cdp.profiles qua CdpClient
(CDP_DATABASE_URL, role cdp_writer). Hai connection, và AGENTS.md §6.2 cấm gói chung một transaction.
Nên thứ tự bị ép cứng: CDP trước, app.users sau, có bù trừ.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.backend.app.application.auth.errors import (
    CdpUnavailable,
    CdpUserIdTaken,
    EmailAlreadyExists,
    InvalidCredentials,
    RateLimited,
    WeakPassword,
)
from src.backend.app.application.auth.principal import AuthenticatedUser
from src.backend.app.application.ports.auth import (
    LoginAttemptLog,
    PasswordHasher,
    RateLimiter,
    RefreshTokenStore,
    TokenIssuer,
    UserRepository,
)
from src.backend.app.application.ports.cdp_client import CdpUnavailableError
from src.backend.app.domain.auth.identifiers import new_web_cdp_user_id
from src.backend.app.domain.auth.password import PasswordPolicy, WeakPasswordError

logger = logging.getLogger(__name__)

# Va chạm 60-bit gần như không xảy ra; 3 lần là để lỗi lập trình không thành vòng lặp vô hạn.
_MAX_ID_ATTEMPTS = 3


class ProfileCreator:
    """Phần CdpClient mà auth cần. Giữ hẹp để không kéo cả port CDP vào use case này."""

    async def ensure_profile(self, cdp_user_id: str, *, home_city: str | None = None) -> None:  # pragma: no cover - Protocol
        ...


@dataclass(frozen=True)
class AuthOutcome:
    user: AuthenticatedUser
    access_token: str
    expires_in: int
    refresh_token: str
    amr: tuple[str, ...]


class RegisterUser:
    def __init__(
        self,
        *,
        users: UserRepository,
        hasher: PasswordHasher,
        cdp: ProfileCreator,
        tokens: TokenIssuer,
        refresh: RefreshTokenStore,
        policy: PasswordPolicy | None = None,
    ):
        self._users = users
        self._hasher = hasher
        self._cdp = cdp
        self._tokens = tokens
        self._refresh = refresh
        self._policy = policy or PasswordPolicy()

    async def __call__(
        self, *, email: str, password: str, full_name: str, session_id: str
    ) -> AuthOutcome:
        email = email.strip().lower()
        try:
            password = self._policy.validate(password, email=email, full_name=full_name)
        except WeakPasswordError as exc:
            raise WeakPassword(exc.reasons) from exc

        # ① Kiểm sớm để không tạo profile rác cho một email chắc chắn trùng.
        #    Không thay được ràng buộc UNIQUE ở bước ④ — vẫn có cuộc đua giữa hai request.
        if await self._users.email_exists(email):
            raise EmailAlreadyExists(email)

        password_hash = self._hasher.hash(password)

        for _ in range(_MAX_ID_ATTEMPTS):
            cdp_user_id = new_web_cdp_user_id()

            # ③ CDP trước. Hỏng ở đây thì KHÔNG có user nào được tạo — trạng thái sạch.
            try:
                await self._cdp.ensure_profile(cdp_user_id)
            except CdpUnavailableError as exc:
                raise CdpUnavailable("không tạo được hồ sơ CDP") from exc

            # ④ app.users sau, trong một transaction của DATABASE_URL.
            try:
                user = await self._users.create(
                    email=email,
                    password_hash=password_hash,
                    display_name=full_name.strip(),
                    cdp_user_id=cdp_user_id,
                )
            except CdpUserIdTaken:
                # Trúng ID đã tồn tại: sinh lại. Profile vừa tạo thành mồ côi, xem ghi chú dưới.
                logger.warning("auth.orphan_profile cdp_user_id=%s reason=id_collision", cdp_user_id)
                continue
            except EmailAlreadyExists:
                # Thua cuộc đua với một request đăng ký khác cùng email.
                # Profile mồ côi: KHÔNG xoá. cdp_writer chỉ có INSERT/UPDATE trên cdp.profiles,
                # không có DELETE — nới quyền chỉ để dọn rác là đánh đổi sai. Một profile rỗng
                # không có event thì vô hại: không vào popular, không ảnh hưởng recall.
                logger.warning("auth.orphan_profile cdp_user_id=%s reason=email_race", cdp_user_id)
                raise

            access_token, expires_in = self._tokens.issue_access_token(
                user, session_id=session_id, amr=("pwd",)
            )
            refresh_token = await self._refresh.issue(user_id=user.user_id, session_id=session_id)
            return AuthOutcome(user, access_token, expires_in, refresh_token, ("pwd",))

        raise CdpUserIdTaken("không cấp được cdp_user_id sau nhiều lần thử")


class AuthenticateUser:
    def __init__(
        self,
        *,
        users: UserRepository,
        hasher: PasswordHasher,
        tokens: TokenIssuer,
        refresh: RefreshTokenStore,
        limiter: RateLimiter,
        attempts: LoginAttemptLog,
    ):
        self._users = users
        self._hasher = hasher
        self._tokens = tokens
        self._refresh = refresh
        self._limiter = limiter
        self._attempts = attempts

    async def __call__(
        self, *, email: str, password: str, session_id: str, ip_prefix: str, user_agent_hash: str | None = None
    ) -> AuthOutcome:
        email = email.strip().lower()

        # Đếm cả hai trục: chỉ theo IP thì kẻ tấn công xoay proxy vẫn phá một tài khoản;
        # chỉ theo email thì spray một mật khẩu qua 2.000 email không chạm ngưỡng nào (auth §9.1).
        try:
            await self._limiter.check("login:email", email)
            await self._limiter.check("login:ip", ip_prefix)
        except RateLimited:
            await self._attempts.record(
                email=email, user_id=None, ip_prefix=ip_prefix, user_agent_hash=user_agent_hash,
                succeeded=False, failure_reason="locked",
            )
            raise

        user = await self._users.find_by_email(email)

        if user is None:
            # Vẫn băm một lần: không có dòng này, thời gian phản hồi cho biết email có tồn tại hay không.
            self._hasher.dummy_verify()
            await self._fail(email, None, ip_prefix, user_agent_hash, "unknown_email")
            raise InvalidCredentials("email hoặc mật khẩu không đúng")

        if not self._hasher.verify(password, user.password_hash):
            await self._fail(email, user.user_id, ip_prefix, user_agent_hash, "bad_password")
            raise InvalidCredentials("email hoặc mật khẩu không đúng")

        # Hash bcrypt của user seed: nâng cấp ngay trong request đăng nhập, người dùng không thấy gì (auth §8.2).
        if self._hasher.needs_rehash(user.password_hash):
            await self._users.update_password_hash(user.user_id, self._hasher.hash(password))
            logger.info("auth.password_rehashed user_id=%s", user.user_id)

        await self._limiter.reset("login:email", email)
        await self._limiter.reset("login:ip", ip_prefix)
        await self._users.touch_last_login(user.user_id)
        await self._attempts.record(
            email=email, user_id=user.user_id, ip_prefix=ip_prefix, user_agent_hash=user_agent_hash,
            succeeded=True, failure_reason=None,
        )

        amr = ("pwd",)
        access_token, expires_in = self._tokens.issue_access_token(user, session_id=session_id, amr=amr)
        refresh_token = await self._refresh.issue(user_id=user.user_id, session_id=session_id)
        return AuthOutcome(user, access_token, expires_in, refresh_token, amr)

    async def _fail(self, email, user_id, ip_prefix, user_agent_hash, reason) -> None:
        await self._limiter.register_failure("login:email", email)
        await self._limiter.register_failure("login:ip", ip_prefix)
        await self._attempts.record(
            email=email, user_id=user_id, ip_prefix=ip_prefix, user_agent_hash=user_agent_hash,
            succeeded=False, failure_reason=reason,
        )
