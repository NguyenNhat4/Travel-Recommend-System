"""FastAPI dependency: lấy use case mà composition root (`main.py`) đã nối sẵn vào `app.state`.

Route chỉ nhận use case qua `Depends`, không tự dựng adapter hay agent (docs/prd/architecture.md §2, quy tắc 8).
"""
import hmac
import ipaddress
from typing import Any

from fastapi import Depends, Header, Request

from src.backend.app.application.auth.errors import AuthError, TokenInvalid, Unauthenticated
from src.backend.app.application.auth.principal import AuthPrincipal
from src.backend.app.application.itinerary.use_cases import PlanItinerary
from src.backend.app.core.config import Settings, get_settings


def get_plan_itinerary(request: Request) -> PlanItinerary:
    return request.app.state.plan_itinerary


def get_search(request: Request) -> Any:
    """None khi recsys bị tắt lúc khởi động; route search trả trang rỗng thay vì 500."""
    return getattr(request.app.state, "search", None)


def get_similar(request: Request) -> Any:
    return request.app.state.similar


def get_recommend(request: Request) -> Any:
    return request.app.state.recommend


# --- Auth (docs/spec/hop-dong-tich-hop-auth.md §3.5, §3.11, §9.4, §14.4) --------------------------

class ServiceTokenInvalid(AuthError):
    code = "INVALID_TOKEN"
    http_status = 401


class NotFoundError(AuthError):
    """Endpoint bị tắt ở môi trường này: trả 404 như thể không tồn tại."""

    code = "NOT_FOUND"
    http_status = 404


def get_token_verifier(request: Request) -> Any:
    return request.app.state.token_verifier


def get_auth_use_case(name: str):
    def dependency(request: Request) -> Any:
        return getattr(request.app.state, name)
    return dependency


def get_use_case(name: str):
    """Use case đã được composition root gắn vào `app.state` (booking, thanh toán)."""
    def dependency(request: Request) -> Any:
        return getattr(request.app.state, name)
    return dependency


def _bearer(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.casefold() != "bearer" or not token.strip():
        raise TokenInvalid("Authorization không phải Bearer")
    return token.strip()


def get_revoked_tokens(request: Request) -> Any:
    return getattr(request.app.state, "revoked_tokens", None)


async def _verified(token: str, verifier, revoked) -> AuthPrincipal:
    principal = verifier.verify(token)
    if principal.token_id and revoked is not None and await revoked.is_revoked(principal.token_id):
        raise TokenInvalid("jti đã bị thu hồi")
    return principal


async def optional_principal(
    authorization: str | None = Header(default=None), verifier=Depends(get_token_verifier),
    revoked=Depends(get_revoked_tokens),
) -> AuthPrincipal | None:
    """Không có Bearer → khách (None). Bearer hỏng → 401, KHÔNG hạ thành khách (§3.11 dòng 2)."""
    token = _bearer(authorization)
    return await _verified(token, verifier, revoked) if token is not None else None


async def conversation_owner(request: Request, authorization: str | None = Header(default=None)) -> str | None:
    """Chủ hội thoại của trợ lý = cdp_user_id của Bearer hợp lệ, để token được BFF làm mới vẫn cùng chủ.

    Không có hoặc hỏng Bearer → None, không 401: contract stream không khai báo 401; agent tự trả
    INVALID_TOKEN khi gọi Recommendation bằng token đó.
    """
    verifier = getattr(request.app.state, "token_verifier", None)
    if verifier is None:
        return None
    try:
        token = _bearer(authorization)
        return (await _verified(token, verifier, get_revoked_tokens(request))).cdp_user_id if token else None
    except AuthError:
        return None


async def current_principal(
    authorization: str | None = Header(default=None), verifier=Depends(get_token_verifier),
    revoked=Depends(get_revoked_tokens),
) -> AuthPrincipal:
    token = _bearer(authorization)
    if token is None:
        raise Unauthenticated("cần đăng nhập")
    return await _verified(token, verifier, revoked)


def require_service_token(
    x_service_token: str | None = Header(default=None), settings: Settings = Depends(get_settings)
) -> None:
    """So sánh hằng thời gian. Chưa cấu hình (hoặc < 32 ký tự) thì mọi request đều bị từ chối."""
    expected = settings.auth_service_token
    if len(expected) < 32 or not x_service_token or not hmac.compare_digest(
        x_service_token.encode(), expected.encode()
    ):
        raise ServiceTokenInvalid("X-Service-Token không hợp lệ")


def require_internal_api(settings: Settings = Depends(get_settings)) -> None:
    """/internal/* tắt ở production trừ khi bật tường minh (§14.4). Kiểm TRƯỚC service token."""
    if settings.app_env == "production" and not settings.internal_api_enabled:
        raise NotFoundError("không tồn tại")


def client_ip(request: Request, settings: Settings = Depends(get_settings)) -> str:
    """IP thật: chỉ đọc X-Forwarded-For khi peer thuộc TRUSTED_PROXIES (§9.4)."""
    peer = request.client.host if request.client else "unknown"
    try:
        peer_addr = ipaddress.ip_address(peer)
        networks = [ipaddress.ip_network(n.strip(), strict=False)
                    for n in settings.trusted_proxies.split(",") if n.strip()]
    except ValueError:
        return peer
    if not any(peer_addr in net for net in networks):
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    # Phần tử cuối không thuộc proxy tin cậy là client thật; phần tử đầu do client tự đặt được.
    for hop in reversed([h.strip() for h in forwarded.split(",") if h.strip()]):
        try:
            addr = ipaddress.ip_address(hop)
        except ValueError:
            return peer
        if not any(addr in net for net in networks):
            return hop
    return peer
def get_index(request: Request) -> Any:
    """None khi recsys bị tắt lúc khởi động; route catalog trả danh sách rỗng thay vì 500."""
    return getattr(request.app.state, "index", None)
