from time import perf_counter

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from src.backend.app.application.itinerary.contracts import error_response
from src.backend.app.core.config import get_settings
from src.backend.app.core.request_context import current_request_id
from src.backend.app.core.security import JwtError, optional_cdp_user_id

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


@router.get("/recommendations")
def recommendations(request: Request, k: int = Query(5, ge=1, le=20), destination: str | None = None,
                    authorization: str | None = Header(default=None)):
    settings = get_settings()
    try:
        cdp_user_id = optional_cdp_user_id(
            authorization, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm
        )
    except JwtError as exc:
        request_id = current_request_id() or "recommendations"
        message = "Phiên đăng nhập không hợp lệ."
        if exc.code == "TOKEN_EXPIRED":
            message = "Phiên đăng nhập đã hết hạn."
        elif exc.code == "INTERNAL_ERROR":
            message = "Dịch vụ xác thực chưa được cấu hình."
        return JSONResponse(status_code=exc.status_code, content=error_response(exc.code, message, request_id))

    started = perf_counter()
    result = request.app.state.recommend(cdp_user_id, k=k, destination=destination)
    result["cdpUserId"] = cdp_user_id
    result.setdefault("diagnostics", {})["latencyMs"] = max(0, round((perf_counter() - started) * 1000))
    return result


@router.get("/popular")
def popular(request: Request, k: int = Query(4, ge=1, le=10)):
    return request.app.state.recommend(None, k=k)
