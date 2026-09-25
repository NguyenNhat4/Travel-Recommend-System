"""Phát và kiểm JWT, RS256 (auth §10).

Bất đối xứng chứ không HS256: mọi bên kiểm token sẽ cần khoá, và với khoá đối xứng thì
"kiểm được" đồng nghĩa "ký được". Khoá riêng chỉ nằm ở FastAPI; BFF không ký gì.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from src.backend.app.application.auth.errors import TokenExpired, TokenInvalid
from src.backend.app.application.auth.principal import AuthenticatedUser, AuthPrincipal

# Allowlist CỨNG. Không bao giờ đọc header `alg` của token để chọn hàm kiểm — đó là đường vào của
# alg:none và của trò đánh tráo RS256→HS256 (ký bằng chính public key).
ALLOWED_ALGORITHMS = ("RS256", "ES256")
_REQUIRED_CLAIMS = ["exp", "iat", "nbf", "sub", "aud", "iss"]


# Tên cũ; lỗi thật là của application để tầng API dịch sang HTTP mà không import infrastructure.
InvalidToken = TokenInvalid


@dataclass(frozen=True)
class JwtConfig:
    private_key: str
    public_key: str
    issuer: str
    audience: str
    access_ttl_seconds: int = 600
    leeway_seconds: int = 60          # dung sai đồng hồ; không nới quá 60s
    algorithm: str = "RS256"
    key_id: str = "vota-1"

    def __post_init__(self) -> None:
        if self.algorithm not in ALLOWED_ALGORITHMS:
            raise ValueError(f"thuật toán không được phép: {self.algorithm}")


class JwtIssuer:
    def __init__(self, config: JwtConfig):
        self._c = config

    def issue_access_token(
        self, user: AuthenticatedUser, *, session_id: str | None, amr: tuple[str, ...]
    ) -> tuple[str, int]:
        now = datetime.now(timezone.utc)
        payload = {
            "iss": self._c.issuer,
            "aud": self._c.audience,
            "sub": user.user_id,
            # snake_case là ngoại lệ đã chốt cho claim JWT; body JSON luôn là cdpUserId
            # (hop-dong-tich-hop-backend.md §3.5).
            "cdp_user_id": user.cdp_user_id,
            "email": user.email,
            "email_verified": user.email_verified,
            "sid": session_id,
            "amr": list(amr),
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(seconds=self._c.access_ttl_seconds),
            "jti": uuid.uuid4().hex,
        }
        token = jwt.encode(
            payload, self._c.private_key, algorithm=self._c.algorithm, headers={"kid": self._c.key_id}
        )
        return token, self._c.access_ttl_seconds

    def verify(self, token: str) -> AuthPrincipal:
        """Kiểm đủ 10 điểm của auth §10.3 rồi dựng principal.

        Điểm 9 (danh sách thu hồi khẩn jwt:revoked) cần I/O nên kiểm ở dependency HTTP qua port
        RevokedTokens, dựa trên principal.token_id trả về từ đây.
        """
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise InvalidToken(str(exc)) from exc
        # Điểm 1: chỉ xác nhận alg khớp cấu hình, không dùng nó để chọn hàm kiểm.
        if header.get("alg") != self._c.algorithm:
            raise InvalidToken("alg không được phép")
        # Điểm 2 và 10.
        if header.get("kid") != self._c.key_id:
            raise InvalidToken("kid lạ")
        if header.get("typ", "JWT") != "JWT":
            raise InvalidToken("typ không phải JWT")
        try:
            claims = jwt.decode(
                token,
                self._c.public_key,
                # Tường minh, không lấy từ header token.
                algorithms=[self._c.algorithm],
                audience=self._c.audience,
                issuer=self._c.issuer,
                leeway=self._c.leeway_seconds,
                options={"require": _REQUIRED_CLAIMS, "verify_signature": True},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpired(str(exc)) from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidToken(str(exc)) from exc

        cdp_user_id = claims.get("cdp_user_id")
        if not isinstance(claims.get("sub"), str) or not claims["sub"].strip():
            raise InvalidToken("thiếu claim sub")
        if not isinstance(cdp_user_id, str) or not cdp_user_id.strip():
            # Token hợp lệ nhưng không mang danh tính nghiệp vụ: phiên pending_mfa hoặc token dựng sai.
            # Không có cdp_user_id thì không truy vấn được gì của người dùng, nên từ chối thẳng.
            raise InvalidToken("thiếu claim cdp_user_id")

        return AuthPrincipal(
            user_id=claims["sub"],
            cdp_user_id=cdp_user_id,
            email=claims.get("email", ""),
            session_id=claims.get("sid"),
            amr=tuple(claims.get("amr", ())),
            email_verified=bool(claims.get("email_verified", False)),
            token_id=claims.get("jti"),
        )

    def jwks(self) -> dict:
        """Public key cho service nội bộ tự kiểm token (auth §5, /.well-known/jwks.json)."""
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        key = load_pem_public_key(self._c.public_key.encode())
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key, as_dict=True)
        jwk.update({"kid": self._c.key_id, "use": "sig", "alg": self._c.algorithm})
        return {"keys": [jwk]}
