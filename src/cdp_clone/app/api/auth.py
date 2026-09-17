import hmac

from fastapi import Request

from src.cdp_clone.app.api.errors import ApiError


def require_service_token(request: Request) -> None:
    """CDP clone is internal: only Backend, seed scripts and jobs holding X-Service-Token may call it."""
    expected = request.app.state.settings.service_token.get_secret_value()
    provided = request.headers.get("X-Service-Token", "")
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        raise ApiError(401, "INVALID_TOKEN", "Service token không hợp lệ.")
