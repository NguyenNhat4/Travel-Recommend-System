"""Minimal JWT verification shared by read-only personalized endpoints."""

from __future__ import annotations

import jwt


class JwtError(Exception):
    def __init__(self, code: str, status_code: int):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def optional_cdp_user_id(authorization: str | None, *, secret: str, algorithm: str) -> str | None:
    if authorization is None:
        return None
    scheme, separator, token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not separator or not token.strip():
        raise JwtError("INVALID_TOKEN", 401)
    if not secret:
        raise JwtError("INTERNAL_ERROR", 500)
    try:
        claims = jwt.decode(
            token.strip(), secret, algorithms=[algorithm],
            options={"require": ["sub", "cdp_user_id", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise JwtError("TOKEN_EXPIRED", 401) from exc
    except jwt.PyJWTError as exc:
        raise JwtError("INVALID_TOKEN", 401) from exc
    cdp_user_id = claims.get("cdp_user_id")
    if not isinstance(cdp_user_id, str) or not cdp_user_id.strip():
        raise JwtError("INVALID_TOKEN", 401)
    return cdp_user_id
