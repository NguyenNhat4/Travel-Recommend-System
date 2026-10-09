"""Bearer → `AuthPrincipal` (auth §3.5, §3.11). Không import FastAPI.

Một chỗ duy nhất phân giải Bearer: `api/deps.py` (HTTP) và tool itinerary chạy trong tiến trình cùng dùng,
nên token hỏng luôn là 401 và không bao giờ bị hạ thành khách ở bất kỳ đường nào.
"""
from __future__ import annotations

from src.backend.app.application.auth.errors import TokenInvalid
from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.ports.auth import RevokedTokens, TokenVerifier
from src.backend.app.core.request_context import note_actor


def bearer_token(authorization: str | None) -> str | None:
    """Không có header → None (khách). Có header mà không phải Bearer hoặc token rỗng → TokenInvalid."""
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not token.strip():
        raise TokenInvalid("Authorization không phải Bearer")
    return token.strip()


async def verified_principal(token: str, verifier: TokenVerifier, revoked: RevokedTokens | None) -> AuthPrincipal:
    """Kiểm chữ ký/claim rồi danh sách thu hồi khẩn theo jti (auth §10.3 điểm 9)."""
    principal = verifier.verify(token)
    if principal.token_id and revoked is not None and await revoked.is_revoked(principal.token_id):
        raise TokenInvalid("jti đã bị thu hồi")
    note_actor("user", principal.cdp_user_id)
    return principal


async def principal_from_header(
    authorization: str | None, verifier: TokenVerifier, revoked: RevokedTokens | None
) -> AuthPrincipal | None:
    """Không có Bearer → None (khách). Bearer hỏng → TokenInvalid, KHÔNG hạ thành khách (§3.11 dòng 2)."""
    token = bearer_token(authorization)
    return await verified_principal(token, verifier, revoked) if token is not None else None
