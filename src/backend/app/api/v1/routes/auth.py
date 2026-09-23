"""Auth (docs/spec/hop-dong-tich-hop-auth.md §5).

Hai nhóm:
  * v1 — /auth/register, /auth/login, /auth/me, /auth/demo-accounts: shape không đổi, cho client
    nội bộ, Agent, CLI và test. Không có refresh token.
  * Chỉ BFF — /auth/session, /auth/session/token, /auth/session/revoke: bắt X-Service-Token; trả
    thêm refresh token để BFF cất trong session Redis. Trình duyệt không bao giờ thấy các token này.
/auth/password dùng Bearer (BFF gắn từ session), không cần service token.
/auth/session/mfa/verify có trong contract nhưng không mount: 2FA ngoài phạm vi P0.
"""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, Request, Response, status

from src.backend.app.api.deps import (
    NotFoundError,
    client_ip,
    current_principal,
    get_auth_use_case,
    get_token_verifier,
    require_service_token,
)
from src.backend.app.api.v1.schemas.auth import (
    AuthResponse,
    AuthUser,
    DemoAccountListResponse,
    DemoAccountOut,
    LoginRequest,
    PasswordChangeRequest,
    RefreshRequest,
    RegisterRequest,
    SessionRequest,
    SessionResponse,
)
from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.core.config import Settings, get_settings

router = APIRouter(tags=["auth"])
well_known_router = APIRouter(tags=["auth"])


def _ua_hash(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    return "sha256:" + hashlib.sha256(ua.encode("utf-8")).hexdigest() if ua else None


@router.post("/auth/register", status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
async def register(body: RegisterRequest, ip: str = Depends(client_ip),
                   use_case=Depends(get_auth_use_case("register_user"))):
    outcome = await use_case(email=body.email, password=body.password, full_name=body.fullName, client_ip=ip)
    return AuthResponse.of(outcome)


@router.post("/auth/login", response_model=AuthResponse)
async def login(body: LoginRequest, request: Request, ip: str = Depends(client_ip),
                use_case=Depends(get_auth_use_case("authenticate_user"))):
    outcome = await use_case(email=body.email, password=body.password, client_ip=ip,
                             user_agent_hash=_ua_hash(request))
    return AuthResponse.of(outcome)


@router.get("/auth/me", response_model=AuthUser)
async def me(principal: AuthPrincipal = Depends(current_principal),
             use_case=Depends(get_auth_use_case("get_current_user"))):
    return AuthUser.of(await use_case(principal))


@router.get("/auth/demo-accounts", response_model=DemoAccountListResponse)
async def demo_accounts(settings: Settings = Depends(get_settings),
                        use_case=Depends(get_auth_use_case("list_demo_accounts"))):
    if settings.app_env == "production":
        raise NotFoundError("demo tắt ở production")
    return DemoAccountListResponse(accounts=[DemoAccountOut.of(a) for a in await use_case()])


# --- Chỉ BFF -------------------------------------------------------------------------------------

@router.post("/auth/session", response_model=SessionResponse, response_model_exclude_none=True,
             dependencies=[Depends(require_service_token)])
async def create_session(body: SessionRequest, request: Request, ip: str = Depends(client_ip),
                         use_case=Depends(get_auth_use_case("authenticate_user"))):
    outcome = await use_case(email=body.email, password=body.password, client_ip=ip,
                             user_agent_hash=_ua_hash(request), with_session=True)
    return SessionResponse.of(outcome)


@router.post("/auth/session/token", response_model=SessionResponse, response_model_exclude_none=True,
             dependencies=[Depends(require_service_token)])
async def rotate_session_token(body: RefreshRequest, use_case=Depends(get_auth_use_case("rotate_session"))):
    return SessionResponse.of(await use_case(refresh_token=body.refreshToken))


@router.post("/auth/session/revoke", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_service_token)])
async def revoke_session(body: RefreshRequest, use_case=Depends(get_auth_use_case("revoke_session"))):
    await use_case(refresh_token=body.refreshToken)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/auth/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: PasswordChangeRequest, principal: AuthPrincipal = Depends(current_principal),
                          use_case=Depends(get_auth_use_case("change_password"))):
    await use_case(principal=principal, current_password=body.currentPassword, new_password=body.newPassword)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@well_known_router.get("/.well-known/jwks.json")
def jwks(verifier=Depends(get_token_verifier)):
    return verifier.jwks()
