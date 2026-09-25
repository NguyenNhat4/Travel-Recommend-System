"""Use case của auth (auth §3.6, §3.8, §10.4). Không import FastAPI, psycopg hay redis — chỉ port.

Đăng ký là chỗ dễ sai nhất và lý do nằm ở quyền database:

    app.users.cdp_user_id  NOT NULL UNIQUE REFERENCES cdp.profiles (cdp_user_id)
    GRANT INSERT, UPDATE ON cdp.profiles TO cdp_writer;   -- vota_app KHÔNG có

Backend ghi app.* bằng vota_app (DATABASE_URL) nhưng chỉ ghi được cdp.profiles qua CdpClient
(CDP_DATABASE_URL, role cdp_writer). Hai connection, và AGENTS.md §6.2 cấm gói chung một transaction.
Nên thứ tự bị ép cứng: CDP trước, app.users sau, có bù trừ.

Hai lối vào dùng chung use case:
  * v1 (`/auth/login`, `/auth/register`) — client nội bộ, chỉ cần access token: `with_session=False`.
  * BFF (`/auth/session*`) — cần thêm refresh token gắn với một session_id: `with_session=True`.

Log theo auth §15.1; không bao giờ ghi thứ ở §15.2 (email thô, sid đầy đủ, token).
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
    RefreshTokenReuse,
    TokenInvalid,
    WeakPassword,
)
from src.backend.app.application.auth.principal import AuthenticatedUser, AuthPrincipal
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
from src.backend.app.domain.auth.privacy import hash_email, ip_prefix, short_sid
from src.backend.app.domain.auth.session import new_session_id

logger = logging.getLogger(__name__)

# Va chạm 60-bit gần như không xảy ra; 3 lần là để lỗi lập trình không thành vòng lặp vô hạn.
_MAX_ID_ATTEMPTS = 3
_PASSWORD_AMR = ("pwd",)


class ProfileCreator:
    """Phần CdpClient mà auth cần. Giữ hẹp để không kéo cả port CDP vào use case này."""

    async def ensure_profile(self, cdp_user_id: str, *, home_city: str | None = None) -> None:  # pragma: no cover - Protocol
        ...


@dataclass(frozen=True)
class AuthOutcome:
    user: AuthenticatedUser
    access_token: str
    expires_in: int
    amr: tuple[str, ...]
    # Chỉ có khi with_session=True (nhóm /auth/session*).
    refresh_token: str | None = None
    session_id: str | None = None


class _SessionIssuer:
    """Phát cặp token cho một user đã xác thực. Dùng chung cho đăng ký, đăng nhập và xoay token."""

    def __init__(self, tokens: TokenIssuer, refresh: RefreshTokenStore):
        self._tokens = tokens
        self._refresh = refresh

    async def issue(self, user: AuthenticatedUser, *, with_session: bool) -> AuthOutcome:
        session_id = new_session_id() if with_session else None
        access_token, expires_in = self._tokens.issue_access_token(
            user, session_id=session_id, amr=_PASSWORD_AMR
        )
        refresh_token = None
        if session_id is not None:
            refresh_token = await self._refresh.issue(user_id=user.user_id, session_id=session_id)
        return AuthOutcome(user, access_token, expires_in, _PASSWORD_AMR, refresh_token, session_id)


class RegisterUser:
    def __init__(
        self,
        *,
        users: UserRepository,
        hasher: PasswordHasher,
        cdp: ProfileCreator,
        tokens: TokenIssuer,
        refresh: RefreshTokenStore,
        limiter: RateLimiter,
        policy: PasswordPolicy | None = None,
    ):
        self._users = users
        self._hasher = hasher
        self._cdp = cdp
        self._sessions = _SessionIssuer(tokens, refresh)
        self._limiter = limiter
        self._policy = policy or PasswordPolicy()

    async def __call__(
        self, *, email: str, password: str, full_name: str, client_ip: str, with_session: bool = False
    ) -> AuthOutcome:
        await self._limiter.hit("register:ip", client_ip)

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
                logger.warning("auth.orphan_profile cdpUserId=%s reason=id_collision", cdp_user_id)
                continue
            except EmailAlreadyExists:
                # Thua cuộc đua với một request đăng ký khác cùng email.
                # Profile mồ côi: KHÔNG xoá. cdp_writer chỉ có INSERT/UPDATE trên cdp.profiles,
                # không có DELETE — nới quyền chỉ để dọn rác là đánh đổi sai. Một profile rỗng
                # không có event thì vô hại: không vào popular, không ảnh hưởng recall.
                logger.warning("auth.orphan_profile cdpUserId=%s reason=email_race", cdp_user_id)
                raise

            logger.info("auth.register.success userId=%s cdpUserId=%s", user.user_id, user.cdp_user_id)
            return await self._sessions.issue(user, with_session=with_session)

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
        self._sessions = _SessionIssuer(tokens, refresh)
        self._limiter = limiter
        self._attempts = attempts

    async def __call__(
        self,
        *,
        email: str,
        password: str,
        client_ip: str,
        user_agent_hash: str | None = None,
        with_session: bool = False,
    ) -> AuthOutcome:
        email = email.strip().lower()
        prefix = ip_prefix(client_ip)

        # Đếm cả hai trục: chỉ theo IP thì kẻ tấn công xoay proxy vẫn phá một tài khoản;
        # chỉ theo email thì spray một mật khẩu qua 2.000 email không chạm ngưỡng nào (auth §9.1).
        # ipwide đếm MỌI lần thử để chặn credential stuffing dù mật khẩu đúng hay sai.
        try:
            await self._limiter.hit("login:ipwide", client_ip)
            await self._limiter.check("login:email", email)
            await self._limiter.check("login:ip", client_ip)
        except RateLimited:
            logger.info("auth.login.failure reason=locked emailHash=%s ipPrefix=%s", hash_email(email), prefix)
            await self._attempts.record(
                email=email, user_id=None, ip_prefix=prefix, user_agent_hash=user_agent_hash,
                succeeded=False, failure_reason="locked",
            )
            raise

        user = await self._users.find_by_email(email)

        if user is None:
            # Vẫn băm một lần: không có dòng này, thời gian phản hồi cho biết email có tồn tại hay không.
            self._hasher.dummy_verify()
            await self._fail(email, None, client_ip, user_agent_hash, "unknown_email")
            raise InvalidCredentials("email hoặc mật khẩu không đúng")

        if not self._hasher.verify(password, user.password_hash):
            await self._fail(email, user.user_id, client_ip, user_agent_hash, "bad_password")
            raise InvalidCredentials("email hoặc mật khẩu không đúng")

        # Hash bcrypt của user seed cũ: nâng cấp ngay trong request đăng nhập, người dùng không thấy gì (auth §8.2).
        if self._hasher.needs_rehash(user.password_hash):
            await self._users.update_password_hash(user.user_id, self._hasher.hash(password))
            logger.info("auth.password_rehashed userId=%s", user.user_id)

        await self._limiter.reset("login:email", email)
        await self._limiter.reset("login:ip", client_ip)
        await self._users.touch_last_login(user.user_id)
        await self._attempts.record(
            email=email, user_id=user.user_id, ip_prefix=prefix, user_agent_hash=user_agent_hash,
            succeeded=True, failure_reason=None,
        )

        outcome = await self._sessions.issue(user, with_session=with_session)
        logger.info(
            "auth.login.success userId=%s amr=%s sid=%s", user.user_id, ",".join(outcome.amr),
            short_sid(outcome.session_id),
        )
        return outcome

    async def _fail(self, email, user_id, client_ip, user_agent_hash, reason) -> None:
        prefix = ip_prefix(client_ip)
        logger.info("auth.login.failure reason=%s emailHash=%s ipPrefix=%s", reason, hash_email(email), prefix)
        await self._limiter.register_failure("login:email", email)
        await self._limiter.register_failure("login:ip", client_ip)
        await self._attempts.record(
            email=email, user_id=user_id, ip_prefix=prefix, user_agent_hash=user_agent_hash,
            succeeded=False, failure_reason=reason,
        )


class RotateSession:
    """Đổi refresh token lấy cặp mới (auth §3.4, §10.4). Chỉ BFF gọi."""

    def __init__(self, *, users: UserRepository, tokens: TokenIssuer, refresh: RefreshTokenStore):
        self._users = users
        self._tokens = tokens
        self._refresh = refresh

    async def __call__(self, *, refresh_token: str) -> AuthOutcome:
        try:
            rotated = await self._refresh.rotate(refresh_token)
        except RefreshTokenReuse:
            # Adapter đã thu hồi cả family; đây là tín hiệu duy nhất cho biết token bị trộm.
            logger.error("auth.refresh_reuse")
            raise

        user = await self._users.find_by_id(rotated.user_id)
        if user is None:
            await self._refresh.revoke(rotated.token, reason="admin")
            raise TokenInvalid("user không còn tồn tại")

        access_token, expires_in = self._tokens.issue_access_token(
            user, session_id=rotated.session_id, amr=_PASSWORD_AMR
        )
        logger.debug("auth.session.rotated sid=%s reason=refresh", short_sid(rotated.session_id))
        return AuthOutcome(user, access_token, expires_in, _PASSWORD_AMR, rotated.token, rotated.session_id)


class RevokeSession:
    """Đăng xuất (auth §3.8 dòng G): thu hồi cả family của refresh token. Idempotent."""

    def __init__(self, *, refresh: RefreshTokenStore):
        self._refresh = refresh

    async def __call__(self, *, refresh_token: str) -> None:
        await self._refresh.revoke(refresh_token, reason="logout")
        logger.info("auth.logout")


class ChangePassword:
    """Đổi mật khẩu (auth §3.8 dòng J, §14.3): bắt nhập lại mật khẩu cũ, thu hồi mọi phiên KHÁC."""

    def __init__(
        self,
        *,
        users: UserRepository,
        hasher: PasswordHasher,
        refresh: RefreshTokenStore,
        policy: PasswordPolicy | None = None,
    ):
        self._users = users
        self._hasher = hasher
        self._refresh = refresh
        self._policy = policy or PasswordPolicy()

    async def __call__(self, *, principal: AuthPrincipal, current_password: str, new_password: str) -> int:
        user = await self._users.find_by_id(principal.user_id)
        if user is None:
            raise TokenInvalid("user không còn tồn tại")
        if not self._hasher.verify(current_password, user.password_hash):
            raise InvalidCredentials("mật khẩu hiện tại không đúng")
        try:
            new_password = self._policy.validate(new_password, email=user.email, full_name=user.display_name)
        except WeakPasswordError as exc:
            raise WeakPassword(exc.reasons) from exc

        await self._users.update_password_hash(user.user_id, self._hasher.hash(new_password))
        revoked = await self._refresh.revoke_all_for_user(
            user.user_id, reason="password_change", except_session_id=principal.session_id
        )
        logger.info("auth.password.changed userId=%s revokedTokens=%d", user.user_id, revoked)
        return revoked


class GetCurrentUser:
    def __init__(self, *, users: UserRepository):
        self._users = users

    async def __call__(self, principal: AuthPrincipal) -> AuthenticatedUser:
        user = await self._users.find_by_id(principal.user_id)
        # Token hợp lệ nhưng user đã bị xoá, hoặc token của user khác cùng sub: không tin token.
        if user is None or user.cdp_user_id != principal.cdp_user_id:
            raise TokenInvalid("principal không khớp app.users")
        return user
